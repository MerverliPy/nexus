"""Security utilities: password hashing, JWT tokens, and TOTP MFA."""

from __future__ import annotations

import base64
import io
import secrets
from datetime import UTC, datetime, timedelta

import pyotp
import qrcode
from jose import JWTError, jwt
from passlib.context import CryptContext

from nexus.config import get_settings

settings = get_settings()

# Password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Default issuer shown in authenticator apps (e.g. Google Authenticator)
TOTP_ISSUER = "Nexus"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.nexus_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.nexus_secret_key, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """Create a long-lived JWT refresh token with a unique jti claim."""
    import secrets as _secrets

    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.nexus_refresh_token_expire_days)
    to_encode.update(
        {"exp": expire, "type": "refresh", "jti": _secrets.token_hex(16)}
    )
    return jwt.encode(to_encode, settings.nexus_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload dict or None on failure."""
    try:
        payload = jwt.decode(token, settings.nexus_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


# ── TOTP / Multi-Factor Authentication ─────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a new base32 TOTP secret suitable for authenticator apps."""
    return pyotp.random_base32()


def build_totp_uri(secret: str, account_name: str, issuer: str = TOTP_ISSUER) -> str:
    """Build an ``otpauth://`` provisioning URI for authenticator apps."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def verify_totp(secret: str | None, code: str | None, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code against a secret.

    ``valid_window=1`` tolerates one time step (±30s) of clock drift.
    Returns False for any missing/malformed input rather than raising.
    """
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=valid_window)
    except Exception:  # noqa: BLE001 - never let a malformed code raise
        return False


def qr_code_data_uri(data: str) -> str:
    """Render ``data`` as a QR-code PNG and return it as a base64 data URI."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf)  # qrcode's PIL image defaults to PNG
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate ``count`` single-use backup codes in ``XXXX-XXXX`` format."""
    codes: list[str] = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()  # 8 hex characters
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def normalize_backup_code(code: str) -> str:
    """Normalize a backup code for comparison (uppercase, trimmed)."""
    return code.strip().upper()
