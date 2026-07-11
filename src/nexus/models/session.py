"""Refresh session model — tracks valid refresh tokens server-side.

Each row corresponds to one issued refresh token. The ``jti`` (JWT ID)
claim stored alongside the device fingerprint allows individual session
revocation and concurrent device limiting.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from nexus.models.base import BaseModel


class RefreshSession(BaseModel):
    """One active refresh-token session for a user."""

    __tablename__ = "refresh_sessions"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti = Column(String(64), unique=True, nullable=False, index=True)  # JWT ID claim
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    device_name = Column(String(255), nullable=True)
    last_used_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="refresh_sessions")

    def __repr__(self) -> str:
        return f"<RefreshSession(id={self.id}, user_id={self.user_id})>"
