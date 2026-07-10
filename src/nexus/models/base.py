"""Base model with common fields."""

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func

from nexus.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BaseModel(Base, TimestampMixin):
    """Abstract base model with id and timestamps."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
