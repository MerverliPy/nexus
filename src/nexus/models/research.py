"""Note and research project models."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from nexus.models.base import BaseModel


class ResearchProject(BaseModel):
    """Research project workspace."""

    __tablename__ = "research_projects"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active", nullable=False)  # active, completed, archived

    # Relationships
    user = relationship("User")
    notes = relationship("Note", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ResearchProject(id={self.id}, name='{self.name}')>"


class Note(BaseModel):
    """Personal wiki note with semantic search capability."""

    __tablename__ = "notes"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id = Column(
        Integer, ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=True
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(ARRAY(String), nullable=True, index=True)

    # Vector embedding for semantic search (1536 dimensions for text-embedding-3-small)
    embedding = Column(Vector(1536), nullable=True)

    source_url = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=True)  # web, paper, book, conversation

    # Relationships
    user = relationship("User", back_populates="notes")
    project = relationship("ResearchProject", back_populates="notes")
    outgoing_links = relationship(
        "NoteLink",
        foreign_keys="NoteLink.from_note_id",
        back_populates="from_note",
        cascade="all, delete-orphan",
    )
    incoming_links = relationship(
        "NoteLink",
        foreign_keys="NoteLink.to_note_id",
        back_populates="to_note",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title}')>"


class NoteLink(BaseModel):
    """Bidirectional link between notes."""

    __tablename__ = "note_links"

    from_note_id = Column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_note_id = Column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    from_note = relationship("Note", foreign_keys=[from_note_id], back_populates="outgoing_links")
    to_note = relationship("Note", foreign_keys=[to_note_id], back_populates="incoming_links")

    def __repr__(self) -> str:
        return f"<NoteLink(from={self.from_note_id}, to={self.to_note_id})>"
