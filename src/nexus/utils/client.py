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


def login(email: str, password: str, totp_code: str | None = None) -> dict:
    """Login and store tokens. Supply ``totp_code`` when MFA is enabled."""
    body: dict = {"email": email, "password": password}
    if totp_code:
        body["totp_code"] = totp_code
    resp = _request(
        "POST",
        "/api/v1/auth/login",
        auth=False,
        json_body=body,
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


# ── MFA Commands ───────────────────────────────────────────────────────


def mfa_enroll() -> dict:
    """Begin MFA enrollment: returns secret, otpauth URI, and QR data URI."""
    resp = _request("POST", "/api/v1/auth/mfa/enroll")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def mfa_verify(code: str) -> dict:
    """Verify a TOTP code to activate MFA; returns one-time backup codes."""
    resp = _request("POST", "/api/v1/auth/mfa/verify", json_body={"code": code})
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def mfa_disable(password: str, code: str | None = None) -> dict:
    """Disable MFA (requires the account password)."""
    body: dict = {"password": password}
    if code:
        body["code"] = code
    resp = _request("POST", "/api/v1/auth/mfa/disable", json_body=body)
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Session Commands ────────────────────────────────────────────────────


def list_sessions() -> dict:
    """List active refresh-token sessions."""
    resp = _request("GET", "/api/v1/auth/sessions")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def revoke_session(session_id: int) -> dict:
    """Revoke a single session by ID."""
    resp = _request("DELETE", f"/api/v1/auth/sessions/{session_id}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def revoke_all_sessions() -> dict:
    """Revoke all sessions for the current user (logout everywhere)."""
    resp = _request("DELETE", "/api/v1/auth/sessions")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Note / Research Commands ────────────────────────────────────────────


def create_note(
    title: str,
    content: str,
    project_id: int | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Create a note."""
    body: dict = {"title": title, "content": content}
    if project_id:
        body["project_id"] = project_id
    if tags:
        body["tags"] = tags
    resp = _request("POST", "/api/v1/research/notes", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def search_notes(query: str, limit: int = 10) -> list[dict]:
    """Semantic/full-text search over notes."""
    resp = _request(
        "POST", "/api/v1/research/notes/search", json_body={"query": query, "limit": limit}
    )
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def list_notes(project_id: int | None = None, tag: str | None = None) -> list[dict]:
    """List notes with optional filters."""
    params = []
    if project_id:
        params.append(f"project_id={project_id}")
    if tag:
        params.append(f"tag={tag}")
    qs = "?" + "&".join(params) if params else ""
    resp = _request("GET", f"/api/v1/research/notes{qs}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Research Commands ───────────────────────────────────────────────────


def search_papers(query: str, limit: int = 10) -> list[dict]:
    """Search arXiv papers."""
    resp = _request("GET", f"/api/v1/research/research/papers?q={query}&limit={limit}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def export_note(note_id: int, fmt: str = "md") -> dict:
    """Export a note to the given format."""
    resp = _request(
        "POST",
        f"/api/v1/research/notes/{note_id}/export",
        json_body={"format": fmt},
    )
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def get_note_history(note_id: int) -> dict:
    """Get git version history for a note."""
    resp = _request("GET", f"/api/v1/research/notes/{note_id}/history")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def restore_note(note_id: int, commit: str) -> dict:
    """Restore a note to a previous version by commit hash."""
    resp = _request(
        "POST",
        f"/api/v1/research/notes/{note_id}/restore",
        json_body={"commit": commit},
    )
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def research_plan(topic: str) -> dict:
    """Generate a research plan from a topic (LLM-powered)."""
    resp = _request("POST", "/api/v1/research/research/plan", json_body={"topic": topic})
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Portfolio Commands ──────────────────────────────────────────────────


def create_portfolio(name: str, target_allocation: dict | None = None) -> dict:
    """Create an investment portfolio."""
    body: dict = {"name": name}
    if target_allocation:
        body["target_allocation"] = target_allocation
    resp = _request("POST", "/api/v1/portfolio", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def add_holding(
    portfolio_id: int,
    ticker: str,
    quantity: float,
    cost_basis: float,
    asset_class: str = "stocks",
    last_price: float | None = None,
) -> dict:
    """Add a holding to a portfolio."""
    body: dict = {
        "portfolio_id": portfolio_id,
        "ticker": ticker,
        "quantity": quantity,
        "cost_basis": cost_basis,
        "asset_class": asset_class,
    }
    if last_price is not None:
        body["last_price"] = last_price
    resp = _request("POST", "/api/v1/portfolio/holdings", json_body=body)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def portfolio_analytics(portfolio_id: int) -> dict:
    """Get valuation and allocation for a portfolio."""
    resp = _request("GET", f"/api/v1/portfolio/{portfolio_id}/analytics")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def portfolio_rebalance(portfolio_id: int) -> dict:
    """Get rebalancing recommendations."""
    resp = _request("GET", f"/api/v1/portfolio/{portfolio_id}/rebalance")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def net_worth() -> dict:
    """Get current net worth."""
    resp = _request("GET", "/api/v1/portfolio/networth/current")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Notification Commands ───────────────────────────────────────────────


def create_notification(title: str, body: str | None = None, priority: str = "normal") -> dict:
    """Enqueue a notification."""
    payload: dict = {"title": title, "priority": priority}
    if body:
        payload["body"] = body
    resp = _request("POST", "/api/v1/notifications", json_body=payload)
    if resp.status_code == 201:
        return resp.json()
    raise APIError(resp)


def send_digest(priority: str | None = None) -> dict:
    """Bundle and send pending notifications now."""
    qs = f"?priority={priority}" if priority else ""
    resp = _request("POST", f"/api/v1/notifications/digest{qs}")
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


def forecast_spending(horizon_days: int = 30) -> dict:
    """Get spending forecast."""
    resp = _request("GET", f"/api/v1/finance/analytics/forecast?horizon_days={horizon_days}")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


# ── Vendor Normalization ────────────────────────────────────────────────


def list_vendors(search: str | None = None) -> list[dict]:
    """List vendor aliases."""
    from urllib.parse import quote

    url = "/api/v1/finance/vendors"
    if search:
        url += f"?search={quote(search)}"
    resp = _request("GET", url)
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def list_distinct_vendors() -> list[dict]:
    """List distinct vendor names from transactions."""
    resp = _request("GET", "/api/v1/finance/vendors/distinct")
    if resp.status_code == 200:
        return resp.json()
    raise APIError(resp)


def merge_vendors(raw_names: list[str], canonical_name: str) -> dict:
    """Merge raw vendor names into a canonical name."""
    resp = _request(
        "POST",
        "/api/v1/finance/vendors/merge",
        json={"raw_names": raw_names, "canonical_name": canonical_name},
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
