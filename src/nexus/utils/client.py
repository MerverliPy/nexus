"""HTTP client for Nexus API."""

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import httpx

# Token storage
NEXUS_DIR = Path.home() / ".nexus"
TOKEN_FILE = NEXUS_DIR / "token.json"


def _ensure_dir() -> None:
    NEXUS_DIR.mkdir(parents=True, exist_ok=True)


def _get_base_url() -> str:
    return os.environ.get("NEXUS_API_URL", "http://localhost:8000")


def _load_tokens() -> dict:
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_tokens(data: dict) -> None:
    _ensure_dir()
    TOKEN_FILE.write_text(json.dumps(data, indent=2))


def _get_access_token() -> str | None:
    tokens = _load_tokens()
    return tokens.get("access_token")


def _get_refresh_token() -> str | None:
    tokens = _load_tokens()
    return tokens.get("refresh_token")


def _update_tokens(access_token: str, refresh_token: str | None = None) -> None:
    tokens = _load_tokens()
    tokens["access_token"] = access_token
    if refresh_token:
        tokens["refresh_token"] = refresh_token
    _save_tokens(tokens)


def logged_in() -> bool:
    """Check if we have a stored access token."""
    return _get_access_token() is not None


def get_access_token() -> str | None:
    """Get the current access token."""
    return _get_access_token()


def _try_refresh() -> bool:
    """Try to refresh the access token using the stored refresh token."""
    refresh_token = _get_refresh_token()
    if not refresh_token:
        return False
    try:
        resp = httpx.post(
            f"{_get_base_url()}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _update_tokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
            )
            return True
    except (httpx.RequestError, KeyError):
        pass
    return False


def _request(
    method: str,
    path: str,
    auth: bool = True,
    json_body: Any = None,
) -> httpx.Response:
    """Make an HTTP request, automatically handling auth and token refresh."""
    headers = {"Content-Type": "application/json"}

    if auth:
        token = _get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

    url = f"{_get_base_url()}{path}"
    resp = httpx.request(method, url, headers=headers, json=json_body, timeout=15)

    # If 401 and we have a refresh token, try refreshing once
    if resp.status_code == 401 and auth:
        if _try_refresh():
            token = _get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = httpx.request(method, url, headers=headers, json=json_body, timeout=15)

    return resp


# ── Auth Commands ──────────────────────────────────────────────────────


def register(email: str, password: str) -> dict:
    """Register a new user and store tokens."""
    resp = _request(
        "POST",
        "/api/v1/auth/register",
        auth=False,
        json_body={
            "email": email,
            "password": password,
        },
    )
    if resp.status_code == 201:
        data = resp.json()
        _update_tokens(data["access_token"], data["refresh_token"])
        return {"status": "success", "detail": f"Registered {email}"}
    raise APIError(resp)


def login(email: str, password: str) -> dict:
    """Login and store tokens."""
    resp = _request(
        "POST",
        "/api/v1/auth/login",
        auth=False,
        json_body={
            "email": email,
            "password": password,
        },
    )
    if resp.status_code == 200:
        data = resp.json()
        _update_tokens(data["access_token"], data["refresh_token"])
        return {"status": "success", "detail": f"Logged in as {email}"}
    raise APIError(resp)


def get_me() -> dict:
    """Get current user info."""
    resp = _request("GET", "/api/v1/auth/me")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Task Commands ──────────────────────────────────────────────────────


def create_task(
    title: str,
    description: str | None = None,
    priority: int = 0,
    due_date: str | None = None,
    recurrence_rule: str | None = None,
) -> dict:
    """Create a new task."""
    body: dict = {"title": title, "priority": priority}
    if description:
        body["description"] = description
    if recurrence_rule:
        body["recurrence_rule"] = recurrence_rule
    if due_date:
        # Try natural language parsing
        from nexus.utils.dates import parse_natural_date

        parsed = parse_natural_date(due_date)
        if parsed:
            body["due_date"] = parsed.isoformat()
        else:
            # Fallback: send raw string and let the API handle it
            body["due_date"] = due_date
    resp = _request("POST", "/api/v1/tasks", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def list_tasks(status: str | None = None) -> list[dict]:
    """List tasks with optional status filter."""
    params = f"?status={status}" if status else ""
    resp = _request("GET", f"/api/v1/tasks{params}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Finance Commands ────────────────────────────────────────────────────


def list_accounts() -> list[dict]:
    """List all accounts."""
    resp = _request("GET", "/api/v1/finance/accounts")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def create_account(
    name: str, account_type: str, institution: str | None = None, balance: float = 0
) -> dict:
    """Create a new account."""
    body: dict = {"name": name, "account_type": account_type, "balance": balance}
    if institution:
        body["institution"] = institution
    resp = _request("POST", "/api/v1/finance/accounts", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def create_transaction(
    amount: float,
    vendor: str | None = None,
    category: str | None = None,
    description: str | None = None,
    account_id: int | None = None,
    date_str: str | None = None,
) -> dict:
    """Create a new transaction."""
    from nexus.utils.dates import parse_natural_date

    body: dict = {"amount": amount}

    if vendor:
        body["vendor"] = vendor
    if category:
        body["category"] = category
    if description:
        body["description"] = description
    if account_id:
        body["account_id"] = account_id

    if date_str:
        parsed = parse_natural_date(date_str)
        body["transaction_date"] = parsed.date().isoformat() if parsed else date_str
    else:
        body["transaction_date"] = date.today().isoformat()

    resp = _request("POST", "/api/v1/finance/transactions", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def list_transactions(
    category: str | None = None,
    vendor: str | None = None,
    account_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List transactions with optional filters."""
    params = []
    if category:
        params.append(f"category={category}")
    if vendor:
        params.append(f"vendor={vendor}")
    if account_id:
        params.append(f"account_id={account_id}")
    if date_from:
        params.append(f"from={date_from}")
    if date_to:
        params.append(f"to={date_to}")
    params.append(f"limit={limit}")

    qs = "?" + "&".join(params) if params else ""
    resp = _request("GET", f"/api/v1/finance/transactions{qs}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def import_csv(filepath: str) -> dict:
    """Import transactions from a CSV file."""
    import httpx

    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with open(filepath, "rb") as f:
        files = {"file": (filepath, f, "text/csv")}
        resp = httpx.post(
            f"{_get_base_url()}/api/v1/finance/transactions/import",
            headers=headers,
            files=files,
            timeout=30,
        )
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Error ──────────────────────────────────────────────────────────────


class APIError(Exception):
    """Raised when the API returns a non-success response."""

    def __init__(self, response: httpx.Response):
        self.status_code = response.status_code
        try:
            detail = response.json().get("detail", response.text)
        except (json.JSONDecodeError, KeyError):
            detail = response.text
        self.detail = detail
        super().__init__(f"HTTP {response.status_code}: {detail}")
