"""Tests for TOTP multi-factor authentication.

Split into:
- Pure unit tests for the security helpers (no DB / no network).
- End-to-end endpoint tests exercising enroll -> verify -> MFA login ->
  backup-code login -> disable (require the Postgres test DB).
"""

import pyotp
import pytest
from httpx import AsyncClient

from nexus.utils import security

# ── Pure helper unit tests ──────────────────────────────────────────────────


def test_generate_totp_secret_is_base32():
    secret = security.generate_totp_secret()
    assert isinstance(secret, str)
    assert len(secret) == 32
    # base32 alphabet
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)


def test_verify_totp_roundtrip():
    secret = security.generate_totp_secret()
    current = pyotp.TOTP(secret).now()
    assert security.verify_totp(secret, current) is True


def test_verify_totp_rejects_wrong_code():
    secret = security.generate_totp_secret()
    current = pyotp.TOTP(secret).now()
    wrong = "000000" if current != "000000" else "999999"
    assert security.verify_totp(secret, wrong) is False


def test_verify_totp_handles_missing_input():
    secret = security.generate_totp_secret()
    assert security.verify_totp(None, "123456") is False
    assert security.verify_totp(secret, None) is False
    assert security.verify_totp("", "") is False


def test_build_totp_uri():
    secret = security.generate_totp_secret()
    uri = security.build_totp_uri(secret, account_name="alice@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=Nexus" in uri
    assert secret in uri


def test_qr_code_data_uri():
    uri = "otpauth://totp/Nexus:alice@example.com?secret=ABC&issuer=Nexus"
    data_uri = security.qr_code_data_uri(uri)
    assert data_uri.startswith("data:image/png;base64,")
    assert len(data_uri) > 100


def test_generate_backup_codes():
    codes = security.generate_backup_codes()
    assert len(codes) == 10
    assert len(set(codes)) == 10  # unique
    for code in codes:
        assert len(code) == 9 and code[4] == "-"


def test_normalize_backup_code():
    assert security.normalize_backup_code("  abcd-1234 ") == "ABCD-1234"


# ── Endpoint flow tests (require Postgres test DB) ───────────────────────────


async def _register(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    """Register a user and return an Authorization header dict."""
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_mfa_full_flow(client: AsyncClient):
    email, password = "mfa_user@example.com", "TestPass123!"
    headers = await _register(client, email, password)

    # Enroll
    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    assert resp.status_code == 200, resp.text
    enroll = resp.json()
    secret = enroll["secret"]
    assert enroll["otpauth_uri"].startswith("otpauth://totp/")
    assert enroll["qr_code"].startswith("data:image/png;base64,")

    # Verify with a real code -> activates MFA and returns backup codes
    code = pyotp.TOTP(secret).now()
    resp = await client.post("/api/v1/auth/mfa/verify", headers=headers, json={"code": code})
    assert resp.status_code == 200, resp.text
    verify = resp.json()
    assert verify["mfa_enabled"] is True
    backup_codes = verify["backup_codes"]
    assert len(backup_codes) == 10

    # /me reflects MFA enabled
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["mfa_enabled"] is True

    # Login without a code is rejected
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 401
    assert "MFA code required" in resp.json()["detail"]

    # Login with a wrong code is rejected
    wrong = "000000" if code != "000000" else "999999"
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "totp_code": wrong},
    )
    assert resp.status_code == 401
    assert "Invalid MFA code" in resp.json()["detail"]

    # Login with a valid TOTP code succeeds
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "totp_code": pyotp.TOTP(secret).now()},
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_backup_code_login_is_single_use(client: AsyncClient):
    email, password = "backup_user@example.com", "TestPass123!"
    headers = await _register(client, email, password)

    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    secret = resp.json()["secret"]
    resp = await client.post(
        "/api/v1/auth/mfa/verify", headers=headers, json={"code": pyotp.TOTP(secret).now()}
    )
    backup_code = resp.json()["backup_codes"][0]

    # First use of the backup code works
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "totp_code": backup_code},
    )
    assert resp.status_code == 200, resp.text

    # Second use of the same backup code is rejected
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "totp_code": backup_code},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mfa_disable_requires_password(client: AsyncClient):
    email, password = "disable_user@example.com", "TestPass123!"
    headers = await _register(client, email, password)

    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    secret = resp.json()["secret"]
    await client.post(
        "/api/v1/auth/mfa/verify", headers=headers, json={"code": pyotp.TOTP(secret).now()}
    )

    # Wrong password is rejected
    resp = await client.post(
        "/api/v1/auth/mfa/disable", headers=headers, json={"password": "wrong"}
    )
    assert resp.status_code == 401

    # Correct password disables MFA
    resp = await client.post(
        "/api/v1/auth/mfa/disable", headers=headers, json={"password": password}
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.json()["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_enroll_conflict_when_already_enabled(client: AsyncClient):
    email, password = "conflict_user@example.com", "TestPass123!"
    headers = await _register(client, email, password)

    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    secret = resp.json()["secret"]
    await client.post(
        "/api/v1/auth/mfa/verify", headers=headers, json={"code": pyotp.TOTP(secret).now()}
    )

    # Enrolling again while enabled is a 400
    resp = await client.post("/api/v1/auth/mfa/enroll", headers=headers)
    assert resp.status_code == 400
