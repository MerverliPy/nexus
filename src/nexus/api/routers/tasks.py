"""Tasks router — CRUD for user tasks."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database import get_db
from nexus.models.task import Task
from nexus.models.user import User
from nexus.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Schemas ──────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 0
    due_date: Optional[datetime] = None
    recurrence_rule: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None
    recurrence_rule: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: int
    due_date: Optional[datetime] = None
    recurrence_rule: Optional[str] = None
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
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_min: Optional[int] = Query(None, alias="priority_min"),
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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single task by ID."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
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
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a task."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.flush()


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a task as completed."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "completed"
    await db.flush()
    await db.refresh(task)
    return task
