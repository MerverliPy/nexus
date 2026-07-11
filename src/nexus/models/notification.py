"""Notification and notification-preference models."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from nexus.models.base import BaseModel


class Notification(BaseModel):
    """A single notification queued for delivery or bundling."""

    __tablename__ = "notifications"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    # Priority controls delivery timing:
    #   urgent -> sent immediately
    #   normal -> bundled into the next hourly digest
    #   digest -> bundled into the daily summary
    priority = Column(String(20), nullable=False, default="normal", index=True)
    channel = Column(String(20), nullable=False, default="telegram")  # telegram/email/local
    status = Column(
        String(20), nullable=False, default="pending", index=True
    )  # pending, sent, failed
    sent_at = Column(DateTime, nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, priority='{self.priority}', status='{self.status}')>"


class NotificationPreference(BaseModel):
    """Per-user notification delivery preferences."""

    __tablename__ = "notification_preferences"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    digest_hour = Column(Integer, nullable=False, default=9)  # daily summary hour (0-23, UTC)
    urgent_immediate = Column(Boolean, nullable=False, default=True)
    bundle_normal = Column(Boolean, nullable=False, default=True)
    telegram_chat_id = Column(String(64), nullable=True)  # overrides global config

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id}, digest_hour={self.digest_hour})>"
