"""LLM API usage and cost tracking model."""

from sqlalchemy import Column, DateTime, DECIMAL, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from nexus.models.base import BaseModel


class LLMUsage(BaseModel):
    """Track every LLM API call for cost monitoring and budget alerts."""

    __tablename__ = "llm_usage"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model = Column(String(100), nullable=False, index=True)  # e.g. "anthropic/claude-sonnet-4"
    provider = Column(String(50), nullable=False)  # e.g. "openrouter", "anthropic"
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(DECIMAL(10, 6), nullable=False, default=0)
    endpoint = Column(String(255), nullable=True)  # Which feature triggered this call
    duration_ms = Column(Float, nullable=True)

    # Relationships
    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<LLMUsage(id={self.id}, model='{self.model}', "
            f"tokens={self.prompt_tokens}+{self.completion_tokens}, "
            f"cost=${self.estimated_cost_usd})>"
        )
