"""Tasks router — CRUD for user tasks."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.api.ws_manager import manager
from nexus.database import get_db
from nexus.models.task import Task
from nexus.models.user import User
from nexus.utils.dependencies import get_current_user
from nexus.utils.recurrence import next_occurrence
from nexus.services.scheduling import detect_conflicts, parse_nl_date, suggest_free_slots

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Schemas ──────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: int = 0
    due_date: datetime | None = None
    recurrence_rule: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = None
    due_date: datetime | None = None
    recurrence_rule: str | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str
    priority: int
    due_date: datetime | None = None
    recurrence_rule: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task for the authenticated user."""
    task = Task(
        user_id=user.id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        due_date=body.due_date,
        recurrence_rule=body.recurrence_rule,
        status="pending",
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    task_data = TaskResponse.model_validate(task).model_dump(mode="json")
    await manager.broadcast(user.id, "task_created", task_data)
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    priority_min: int | None = Query(None, alias="priority_min"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tasks for the authenticated user, with optional filters."""
    query = select(Task).where(Task.user_id == user.id)

    if status_filter:
        query = query.where(Task.status == status_filter)
    if priority_min is not None:
        query = query.where(Task.priority >= priority_min)

    query = query.order_by(Task.priority.desc(), Task.due_date.asc().nullslast())
    result = await db.execute(query)
    return result.scalars().all()


# ── Smart scheduling ───────────────────────────────────────────────────


@router.get("/suggest-time")
async def suggest_time(
    text: str = Query(..., description="Natural language date/time text"),
):
    """Parse natural language into a datetime.

    Example: 'tomorrow 3pm' → 2026-07-12T15:00:00
    """
    result = parse_nl_date(text)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Could not parse: {text}")
    return {"text": text, "datetime": result.isoformat()}


@router.get("/suggest-slot")
async def suggest_slot(
    date: str | None = Query(None, description="Date to find slots on (YYYY-MM-DD, or NL like 'tomorrow')"),
    count: int = Query(3, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suggest free time slots for scheduling a new task."""
    target_date: datetime | None = None
    if date:
        parsed = parse_nl_date(date)
        if parsed is None:
            raise HTTPException(status_code=400, detail=f"Could not parse date: {date}")
        target_date = parsed

    slots = await suggest_free_slots(user.id, db, date=target_date, count=count)
    return {"slots": slots, "count": len(slots)}


@router.get("/{task_id}/conflicts")
async def task_conflicts(
    task_id: int,
    window_minutes: int = Query(60, ge=15, le=480),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detect tasks that conflict with this task's due date/time."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.due_date is None:
        return {"task_id": task_id, "conflicts": [], "detail": "Task has no due date"}

    conflicts = await detect_conflicts(
        task_id, task.due_date, user.id, db, window_minutes=window_minutes
    )
    return {"task_id": task_id, "conflicts": conflicts, "window_minutes": window_minutes}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single task by ID."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a task (partial update)."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    task_data = TaskResponse.model_validate(task).model_dump(mode="json")
    await manager.broadcast(user.id, "task_updated", task_data)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a task."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.flush()
    task_data = {"id": task_id}
    await manager.broadcast(user.id, "task_deleted", task_data)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a task as completed."""
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "completed"
    await db.flush()
    await db.refresh(task)
    task_data = TaskResponse.model_validate(task).model_dump(mode="json")
    await manager.broadcast(user.id, "task_updated", task_data)

    # If task has a recurrence rule, generate the next instance
    if task.recurrence_rule:
        next_due = next_occurrence(task.recurrence_rule, after=task.due_date or datetime.utcnow())
        if next_due:
            new_task = Task(
                user_id=user.id,
                title=task.title,
                description=task.description,
                priority=task.priority,
                due_date=next_due,
                recurrence_rule=task.recurrence_rule,
                status="pending",
            )
            db.add(new_task)
            await db.flush()
            await db.refresh(new_task)
            new_task_data = TaskResponse.model_validate(new_task).model_dump(mode="json")
            await manager.broadcast(user.id, "task_created", new_task_data)

    return task
