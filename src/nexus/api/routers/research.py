"""Research & knowledge router — notes, wiki-links, projects, semantic search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.research import Note, NoteLink, ResearchProject
from nexus.models.user import User
from nexus.services.embeddings import embed, is_available
from nexus.services.research import export_note, generate_plan, synthesize_sources
from nexus.utils.credibility import score as credibility_score
from nexus.utils.dependencies import get_current_user
from nexus.utils.wikilinks import extract_wikilinks

router = APIRouter(prefix="/api/v1/research", tags=["research"])


# ── Schemas ──────────────────────────────────────────────────────────────


class NoteCreate(BaseModel):
    title: str
    content: str
    project_id: int | None = None
    tags: list[str] | None = None
    source_url: str | None = None
    source_type: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    project_id: int | None = None
    tags: list[str] | None = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    project_id: int | None
    tags: list[str] | None
    source_url: str | None
    source_type: str | None
    has_embedding: bool = False

    model_config = {"from_attributes": True}


class NoteLinkInfo(BaseModel):
    id: int
    title: str


class BacklinksResponse(BaseModel):
    note_id: int
    outgoing: list[NoteLinkInfo]
    incoming: list[NoteLinkInfo]


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResult(BaseModel):
    id: int
    title: str
    snippet: str
    score: float
    method: str  # "semantic" or "fulltext"


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: str

    model_config = {"from_attributes": True}


class ArxivPaper(BaseModel):
    title: str
    summary: str
    authors: list[str]
    published: str
    pdf_url: str
    arxiv_id: str
    primary_category: str
    credibility: float = 1.0


class ResearchPlanRequest(BaseModel):
    topic: str


class ResearchPlanResponse(BaseModel):
    topic: str
    questions: list[str]


class ExportRequest(BaseModel):
    format: str = "md"  # md, pdf, html, docx


class ExportResponse(BaseModel):
    file: str
    format: str


# ── Helpers ──────────────────────────────────────────────────────────────


async def _resolve_links(db: AsyncSession, note: Note, user_id: int) -> int:
    """Parse [[wiki-links]] in note.content, create NoteLink rows to existing
    notes owned by the same user. Returns the number of links created.
    """
    titles = extract_wikilinks(note.content)
    if not titles:
        return 0

    # Remove existing outgoing links (rebuild on each save)
    existing = await db.execute(select(NoteLink).where(NoteLink.from_note_id == note.id))
    for link in existing.scalars().all():
        await db.delete(link)

    created = 0
    for title in titles:
        target = await db.execute(
            select(Note).where(
                Note.user_id == user_id,
                func.lower(Note.title) == title.lower(),
                Note.id != note.id,
            )
        )
        target_note = target.scalar_one_or_none()
        if target_note is not None:
            db.add(NoteLink(from_note_id=note.id, to_note_id=target_note.id))
            created += 1
    return created


def _to_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=note.content,
        project_id=note.project_id,
        tags=list(note.tags) if note.tags else None,
        source_url=note.source_url,
        source_type=note.source_type,
        has_embedding=note.embedding is not None,
    )


# ── Note endpoints ─────────────────────────────────────────────────────────


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Create a note, generate an embedding, and resolve [[wiki-links]]."""
    note = Note(
        user_id=user.id,
        project_id=body.project_id,
        title=body.title,
        content=body.content,
        tags=body.tags,
        source_url=body.source_url,
        source_type=body.source_type,
    )
    # Embed title + content (None if no provider available)
    note.embedding = embed(f"{body.title}\n\n{body.content}")
    db.add(note)
    await db.flush()
    await _resolve_links(db, note, user.id)
    await db.refresh(note)

    # Auto-commit to git versioning
    from nexus.utils.versioning import save_note_version

    save_note_version(note.id, note.title, note.content)

    return _to_response(note)


@router.get("/notes", response_model=list[NoteResponse])
async def list_notes(
    project_id: int | None = Query(None),
    tag: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    """List notes, optionally filtered by project or tag."""
    q = select(Note).where(Note.user_id == user.id)
    if project_id is not None:
        q = q.where(Note.project_id == project_id)
    if tag:
        q = q.where(Note.tags.any(tag))
    q = q.order_by(Note.updated_at.desc()).limit(limit)
    result = await db.execute(q)
    return [_to_response(n) for n in result.scalars().all()]


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return _to_response(note)


@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    body: NoteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if body.title is not None:
        note.title = body.title
    if body.content is not None:
        note.content = body.content
    if body.project_id is not None:
        note.project_id = body.project_id
    if body.tags is not None:
        note.tags = body.tags

    # Re-embed and re-resolve links if content/title changed
    if body.title is not None or body.content is not None:
        note.embedding = embed(f"{note.title}\n\n{note.content}")
        await db.flush()
        await _resolve_links(db, note, user.id)

    await db.flush()
    await db.refresh(note)

    # Auto-commit to git versioning
    from nexus.utils.versioning import save_note_version

    save_note_version(note.id, note.title, note.content)

    return _to_response(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    await db.delete(note)


@router.get("/notes/{note_id}/backlinks", response_model=BacklinksResponse)
async def get_backlinks(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BacklinksResponse:
    """Return outgoing and incoming links for a note."""
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # Outgoing
    out_q = await db.execute(
        select(Note.id, Note.title)
        .join(NoteLink, NoteLink.to_note_id == Note.id)
        .where(NoteLink.from_note_id == note_id)
    )
    outgoing = [NoteLinkInfo(id=r.id, title=r.title) for r in out_q.all()]

    # Incoming
    in_q = await db.execute(
        select(Note.id, Note.title)
        .join(NoteLink, NoteLink.from_note_id == Note.id)
        .where(NoteLink.to_note_id == note_id)
    )
    incoming = [NoteLinkInfo(id=r.id, title=r.title) for r in in_q.all()]

    return BacklinksResponse(note_id=note_id, outgoing=outgoing, incoming=incoming)


# ── Versioning ──────────────────────────────────────────────────────────


@router.get("/notes/{note_id}/history")
async def get_note_history(
    note_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return git history for a note."""
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    from nexus.utils.versioning import get_note_history

    return {"note_id": note_id, "entries": get_note_history(note_id)}


@router.post("/notes/{note_id}/restore")
async def restore_note_version(
    note_id: int,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a note to a previous version by commit hash.

    Body: {"commit": "abc1234"}
    """
    commit_hash = body.get("commit", "")
    if not commit_hash:
        raise HTTPException(status_code=400, detail="commit hash is required")

    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    from nexus.utils.versioning import restore_note

    content = restore_note(note_id, commit_hash)
    if content is None:
        raise HTTPException(status_code=404, detail="Version not found")

    note.content = content
    await db.flush()
    return {"note_id": note_id, "content": content, "restored_from": commit_hash[:8]}


# ── Search ───────────────────────────────────────────────────────────────


@router.post("/notes/search", response_model=list[SearchResult])
async def search_notes(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    """Hybrid search: semantic (pgvector) when embeddings exist, else full-text.

    Falls back to full-text search over title+content when no embedding
    provider is configured.
    """
    query_vec = embed(body.query) if is_available() else None

    if query_vec is not None:
        # Semantic search via cosine distance
        distance = Note.embedding.cosine_distance(query_vec)
        result = await db.execute(
            select(Note, distance.label("dist"))
            .where(Note.user_id == user.id, Note.embedding.isnot(None))
            .order_by("dist")
            .limit(body.limit)
        )
        return [
            SearchResult(
                id=row.Note.id,
                title=row.Note.title,
                snippet=row.Note.content[:200],
                score=round(1.0 - float(row.dist), 4),
                method="semantic",
            )
            for row in result.all()
        ]

    # Full-text fallback (works offline, no embeddings required)
    pattern = f"%{body.query}%"
    result = await db.execute(
        select(Note)
        .where(
            Note.user_id == user.id,
            or_(Note.title.ilike(pattern), Note.content.ilike(pattern)),
        )
        .order_by(Note.updated_at.desc())
        .limit(body.limit)
    )
    notes = result.scalars().all()
    return [
        SearchResult(
            id=n.id,
            title=n.title,
            snippet=n.content[:200],
            score=1.0,
            method="fulltext",
        )
        for n in notes
    ]


# ── Project endpoints ──────────────────────────────────────────────────────


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = ResearchProject(
        user_id=user.id, name=body.name, description=body.description, status="active"
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    result = await db.execute(
        select(ResearchProject)
        .where(ResearchProject.user_id == user.id)
        .order_by(ResearchProject.created_at.desc())
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


# ── Research workflow ──────────────────────────────────────────────────────


@router.post("/plan", response_model=ResearchPlanResponse)
async def plan_research(body: ResearchPlanRequest):
    """Generate research questions for a topic (LLM-powered when available)."""
    from nexus.config import get_settings

    s = get_settings()
    questions = await generate_plan(
        body.topic,
        openrouter_api_key=s.openrouter_api_key,
        default_model=s.llm_default_model,
    )
    if questions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM provider unavailable (no API key configured or network error)",
        )
    return ResearchPlanResponse(topic=body.topic, questions=questions)


@router.get("/papers", response_model=list[ArxivPaper])
async def search_papers(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search arXiv for academic papers. Returns credibility-scored results."""
    from nexus.services.research import search_arxiv

    papers = await search_arxiv(q, max_results=limit)
    scored: list[ArxivPaper] = []
    for p in papers:
        rated = p.copy()
        rated["credibility"] = credibility_score(p.get("pdf_url", ""))
        scored.append(ArxivPaper(**rated))
    return scored


@router.post("/synthesize")
async def synthesize_research(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synthesize findings from multiple notes into a structured analysis.

    Body: {"note_ids": [1, 2, 3], "save_as_note": true, "project_id": 5}
    """
    from nexus.config import get_settings

    note_ids = body.get("note_ids", [])
    if not isinstance(note_ids, list) or len(note_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 note_ids")
    save_as_note = body.get("save_as_note", False)
    project_id = body.get("project_id")

    s = get_settings()
    result = await synthesize_sources(
        note_ids,
        user.id,
        db,
        openrouter_api_key=s.openrouter_api_key,
        default_model=s.llm_default_model,
    )
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Synthesis failed — LLM unavailable or fewer than 2 valid notes found",
        )

    # Optionally save result as a new note
    if save_as_note:
        note = Note(
            user_id=user.id,
            project_id=project_id,
            title=result["title"],
            content=result["content"],
            tags=["research", "synthesis"],
        )
        db.add(note)
        await db.flush()
        await db.refresh(note)
        result["saved_note_id"] = note.id

    return result


# ── Export ──────────────────────────────────────────────────────────────────


@router.post("/notes/{note_id}/export", response_model=ExportResponse)
async def export_note_endpoint(
    note_id: int,
    body: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:

    from nexus.models.research import Note as NoteModel

    result = await db.execute(
        select(NoteModel).where(NoteModel.id == note_id, NoteModel.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    exported = export_note(_to_response(note).model_dump(), fmt=body.format)
    if exported is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export to {body.format} failed (pandoc may not be installed). "
            "Export to 'md' format is always available.",
        )
    return ExportResponse(**exported)
