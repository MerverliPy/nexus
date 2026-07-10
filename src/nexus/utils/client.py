"""HTTP client for Nexus API."""

import json
import os
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
    resp = httpx.request(
        method, url, headers=headers, json=json_body, timeout=15
    )

    # If 401 and we have a refresh token, try refreshing once
    if resp.status_code == 401 and auth:
        if _try_refresh():
            token = _get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = httpx.request(
                method, url, headers=headers, json=json_body, timeout=15
            )

    return resp


# ── Auth Commands ──────────────────────────────────────────────────────


def register(email: str, password: str) -> dict:
    """Register a new user and store tokens."""
    resp = _request("POST", "/api/v1/auth/register", auth=False, json_body={
        "email": email,
        "password": password,
    })
    if resp.status_code == 201:
        data = resp.json()
        _update_tokens(data["access_token"], data["refresh_token"])
        return {"status": "success", "detail": f"Registered {email}"}
    raise APIError(resp)


def login(email: str, password: str) -> dict:
    """Login and store tokens."""
    resp = _request("POST", "/api/v1/auth/login", auth=False, json_body={
        "email": email,
        "password": password,
    })
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


def create_task(title: str, description: str | None = None, priority: int = 0) -> dict:
    """Create a new task."""
    body: dict = {"title": title, "priority": priority}
    if description:
        body["description"] = description
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
