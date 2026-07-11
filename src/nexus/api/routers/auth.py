"""Authentication router — register, login, refresh, TOTP MFA, and session management."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.user import User
from nexus.services.audit import log as audit_log  # noqa: N811
from nexus.services.sessions import (
    create_session,
    list_sessions,
    revoke_all_sessions,
    revoke_session,
    rotate_session,
)
from nexus.utils import ratelimit
from nexus.utils.dependencies import get_current_user
from nexus.utils.security import (
    build_totp_uri,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_backup_codes,
    generate_totp_secret,
    hash_password,
    normalize_backup_code,
    qr_code_data_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# MFA verification attempts before a temporary lockout.
MFA_MAX_ATTEMPTS = 5
MFA_LOCKOUT_SECONDS = 600  # 10 minutes


# ── Schemas ──────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None  # required when the account has MFA enabled


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    mfa_enabled: bool

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    detail: str


class MfaEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code: str  # base64 PNG data URI


class MfaVerifyRequest(BaseModel):
    code: str


class MfaVerifyResponse(BaseModel):
    mfa_enabled: bool
    backup_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str
    code: str | None = None


class SessionResponse(BaseModel):
    id: int
    ip_address: str | None
    user_agent: str | None
    device_name: str | None
    last_used_at: str  # ISO 8601
    is_current: bool = False  # marked by the caller

    model_config = {"from_attributes": True}


class SessionsListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class RevokeSessionResponse(BaseModel):
    detail: str
    revoked: int  # number of sessions removed


# ── Helpers ──────────────────────────────────────────────────────────────


def _consume_backup_code(user: User, code: str) -> bool:
    """If ``code`` matches an unused backup code, consume it and return True."""
    codes = user.get_backup_codes()
    target = normalize_backup_code(code)
    if any(normalize_backup_code(c) == target for c in codes):
        remaining = [c for c in codes if normalize_backup_code(c) != target]
        user.set_backup_codes(remaining)
        return True
    return False


def _capture(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and User-Agent from a request."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    ip, ua = _capture(request)
    await audit_log(
        db,
        user_id=user.id,
        action="register",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Track initial session
    payload = decode_token(refresh_token)
    jti = payload["jti"] if payload else None
    if jti:
        await create_session(db, user.id, jti, ip_address=ip, user_agent=ua)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password, and a TOTP/backup code when MFA is on."""
    ip, ua = _capture(request)
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        await audit_log(
            db,
            user_id=None,
            action="login_failed",
            resource_type="user",
            ip_address=ip,
            user_agent=ua,
            details={"email": body.email, "reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Second factor
    if user.mfa_enabled:
        if not body.totp_code:
            await audit_log(
                db,
                user_id=user.id,
                action="login_failed_mfa_required",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip,
                user_agent=ua,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code required",
            )

        rl_key = f"mfa:login:{user.id}"
        allowed, retry_after = await ratelimit.hit(
            rl_key, limit=MFA_MAX_ATTEMPTS, window_seconds=MFA_LOCKOUT_SECONDS
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many MFA attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        code_ok = verify_totp(user.totp_secret, body.totp_code) or _consume_backup_code(
            user, body.totp_code
        )
        if not code_ok:
            await audit_log(
                db,
                user_id=user.id,
                action="login_failed_invalid_mfa",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip,
                user_agent=ua,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

        await ratelimit.reset(rl_key)

    await audit_log(
        db,
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Track new session
    payload = decode_token(refresh_token)
    jti = payload["jti"] if payload else None
    if jti:
        await create_session(
            db, user.id, jti, ip_address=ip, user_agent=ua, device_name=ua
        )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Issue a new access token using a refresh token, with session rotation."""
    ip, ua = _capture(request)
    payload = decode_token(body.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    old_jti = payload.get("jti")

    access_token = create_access_token({"sub": user_id})
    new_refresh_token = create_refresh_token({"sub": user_id})

    new_payload = decode_token(new_refresh_token)
    new_jti = new_payload["jti"] if new_payload else None
    if new_jti:
        await rotate_session(
            db, old_jti=old_jti, new_jti=new_jti, ip_address=ip, user_agent=ua
        )

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return user


# ── Session management endpoints ──────────────────────────────────────────


@router.get("/sessions", response_model=SessionsListResponse)
async def get_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active refresh-token sessions for the current user.

    The bearer token used for this request is compared with each session's
    stored refresh token; the matching session is flagged as ``is_current``.
    """
    sessions = await list_sessions(db, user.id)
    ip, _ = _capture(request)

    result: list[SessionResponse] = []
    for s in sessions:
        result.append(
            SessionResponse(
                id=s.id,
                ip_address=str(s.ip_address) if s.ip_address else None,
                user_agent=s.user_agent,
                device_name=s.device_name,
                last_used_at=s.last_used_at.isoformat() if s.last_used_at else "",
                is_current=(str(s.ip_address) if s.ip_address else None) == ip,
            )
        )

    return SessionsListResponse(sessions=result, total=len(result))


@router.delete("/sessions/{session_id}", response_model=RevokeSessionResponse)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session (logs out that device)."""
    ok = await revoke_session(db, session_id, user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return RevokeSessionResponse(detail="Session revoked", revoked=1)


@router.delete("/sessions", response_model=RevokeSessionResponse)
async def delete_all_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for the current user (logout everywhere)."""
    count = await revoke_all_sessions(db, user.id)
    return RevokeSessionResponse(detail=f"{count} sessions revoked", revoked=count)


# ── MFA endpoints ──────────────────────────────────────────────────────────


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
async def mfa_enroll(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaEnrollResponse:
    """Begin MFA enrollment: generate a TOTP secret + QR code.

    The secret is stored but MFA is not activated until the user verifies a
    code via ``/mfa/verify``.
    """
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_totp_secret()
    user.totp_secret = secret
    uri = build_totp_uri(secret, account_name=user.email)

    ip, ua = _capture(request)
    await audit_log(
        db,
        user_id=user.id,
        action="mfa_enroll",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    return MfaEnrollResponse(secret=secret, otpauth_uri=uri, qr_code=qr_code_data_uri(uri))


@router.post("/mfa/verify", response_model=MfaVerifyResponse)
async def mfa_verify(
    request: Request,
    body: MfaVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaVerifyResponse:
    """Verify a TOTP code to activate MFA; returns one-time backup codes."""
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA enrollment has not been started",
        )

    rl_key = f"mfa:verify:{user.id}"
    allowed, retry_after = await ratelimit.hit(
        rl_key, limit=MFA_MAX_ATTEMPTS, window_seconds=MFA_LOCKOUT_SECONDS
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    if not verify_totp(user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    await ratelimit.reset(rl_key)

    backup_codes = generate_backup_codes()
    user.mfa_enabled = True
    user.set_backup_codes(backup_codes)

    ip, ua = _capture(request)
    await audit_log(
        db,
        user_id=user.id,
        action="mfa_activate",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    return MfaVerifyResponse(mfa_enabled=True, backup_codes=backup_codes)


@router.post("/mfa/disable", response_model=MessageResponse)
async def mfa_disable(
    request: Request,
    body: MfaDisableRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Disable MFA. Requires the account password to re-authenticate."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    user.mfa_enabled = False
    user.totp_secret = None
    user.backup_codes = None

    ip, ua = _capture(request)
    await audit_log(
        db,
        user_id=user.id,
        action="mfa_disable",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
        user_agent=ua,
    )

    return MessageResponse(detail="MFA disabled")
