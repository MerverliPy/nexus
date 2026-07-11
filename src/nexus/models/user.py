"""User model and authentication."""

import json

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine

from nexus.config import get_settings
from nexus.models.base import BaseModel

settings = get_settings()


class User(BaseModel):
    """User account model."""

    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # MFA fields (encrypted)
    totp_secret = Column(
        EncryptedType(String(32), settings.nexus_encryption_key, AesEngine, "pkcs5"),
        nullable=True,
    )
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    backup_codes = Column(
        EncryptedType(Text, settings.nexus_encryption_key, AesEngine, "pkcs5"),
        nullable=True,
    )

    # Relationships
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    refresh_sessions = relationship(
        "RefreshSession", back_populates="user", cascade="all, delete-orphan"
    )
    vendor_aliases = relationship(
        "VendorAlias", back_populates="user", cascade="all, delete-orphan"
    )

    def get_backup_codes(self) -> list[str]:
        """Decrypt and parse backup codes."""
        if not self.backup_codes:
            return []
        return json.loads(self.backup_codes)

    def set_backup_codes(self, codes: list[str]) -> None:
        """Encrypt and store backup codes."""
        self.backup_codes = json.dumps(codes)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
