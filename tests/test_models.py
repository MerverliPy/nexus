"""Test database models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.models.task import Task
from nexus.models.user import User


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test user creation."""
    user = User(
        email="newuser@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_create_task(db_session: AsyncSession, test_user: User):
    """Test task creation."""
    task = Task(
        user_id=test_user.id,
        title="Test task",
        description="This is a test",
        status="pending",
        priority=1,
    )
    db_session.add(task)
    await db_session.flush()
    await db_session.refresh(task)

    assert task.id is not None
    assert task.title == "Test task"
    assert task.user_id == test_user.id


@pytest.mark.asyncio
async def test_user_task_relationship(db_session: AsyncSession, test_user: User):
    """Test user-task relationship."""
    task1 = Task(user_id=test_user.id, title="Task 1", status="pending")
    task2 = Task(user_id=test_user.id, title="Task 2", status="completed")

    db_session.add_all([task1, task2])
    await db_session.flush()

    # Refresh to load relationships
    await db_session.refresh(test_user)

    assert len(test_user.tasks) == 2
