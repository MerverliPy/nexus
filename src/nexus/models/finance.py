"""Transaction and Account models."""

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine

from nexus.config import get_settings
from nexus.models.base import BaseModel

settings = get_settings()


class Account(BaseModel):
    """Financial account model (checking, savings, credit card, investment)."""

    __tablename__ = "accounts"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)  # checking, savings, credit_card, investment
    institution = Column(String(255), nullable=True)
    balance = Column(DECIMAL(12, 2), default=0, nullable=False)

    # Encrypted credentials (Plaid token, API keys, etc.)
    encrypted_credentials = Column(
        EncryptedType(Text, settings.nexus_encryption_key, AesEngine, "pkcs5"), nullable=True
    )

    last_synced_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="accounts")
    transactions = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', type='{self.account_type}')>"


class Transaction(BaseModel):
    """Financial transaction model."""

    __tablename__ = "transactions"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    amount = Column(DECIMAL(12, 2), nullable=False)
    vendor = Column(String(255), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    transaction_date = Column(Date, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    receipt_url = Column(String(500), nullable=True)
    raw_data = Column(JSON, nullable=True)  # OCR output, original bank description, etc.

    # Relationships
    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, amount={self.amount}, vendor='{self.vendor}')>"


class VendorAlias(BaseModel):
    """Normalization mapping: raw vendor name → canonical name."""

    __tablename__ = "vendor_aliases"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_name = Column(String(255), nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)

    # Relationships
    user = relationship("User", back_populates="vendor_aliases")

    def __repr__(self) -> str:
        return f"<VendorAlias(id={self.id}, '{self.raw_name}' → '{self.canonical_name}')>"
