"""Task model."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from nexus.models.base import BaseModel


class Task(BaseModel):
    """Task/todo item model."""

    __tablename__ = "tasks"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(20), default="pending", nullable=False, index=True
    )  # pending, in_progress, completed, cancelled
    priority = Column(Integer, default=0, nullable=False)
    due_date = Column(DateTime, nullable=True, index=True)
    recurrence_rule = Column(String(100), nullable=True)  # RRULE format
    context = Column(JSON, nullable=True)  # Flexible metadata

    # Relationships
    user = relationship("User", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"
