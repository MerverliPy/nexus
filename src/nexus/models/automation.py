"""Automation and audit log models."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from nexus.models.base import BaseModel


class Automation(BaseModel):
    """Scheduled automation/workflow."""
    
    __tablename__ = "automations"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    automation_type = Column(String(50), nullable=False)  # cron, file_watch, email_rule, webhook
    schedule = Column(String(100), nullable=True)  # For cron: '0 9 * * 1', 'every 30m'
    trigger_config = Column(JSON, nullable=True)  # File patterns, email filters, webhook URLs
    action_config = Column(JSON, nullable=True)  # What to execute
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), nullable=True)  # success, failure, pending
    run_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="automations")
    
    def __repr__(self) -> str:
        return f"<Automation(id={self.id}, name='{self.name}', type='{self.automation_type}')>"


class AuditLog(BaseModel):
    """Immutable audit trail for sensitive actions."""
    
    __tablename__ = "audit_logs"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # login, transaction_create, etc.
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
