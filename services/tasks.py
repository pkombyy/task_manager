import uuid
from typing import Any

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.task import Task, TaskPriority, TaskStatus
from schemas.task import TaskCreate

TERMINAL_STATUSES: tuple[TaskStatus, ...] = (
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
)


async def create_task(session: AsyncSession, data: TaskCreate) -> Task:
    task = Task(
        title=data.title,
        description=data.description,
        priority=data.priority,
        status=TaskStatus.NEW,
    )
    session.add(task)
    await session.flush()
    return task


async def mark_pending(session: AsyncSession, task_id: uuid.UUID) -> None:
    await session.execute(
        update(Task)
        .where(Task.id == task_id, Task.status == TaskStatus.NEW)
        .values(status=TaskStatus.PENDING)
    )


async def get_task(session: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def list_tasks(
    session: AsyncSession,
    *,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Task]]:
    stmt: Select = select(Task)
    filters: list = []
    if status:
        filters.append(Task.status == status)
    if priority:
        filters.append(Task.priority == priority)
    if filters:
        stmt = stmt.where(and_(*filters))
    total_stmt = select(func.count()).select_from(stmt.subquery())
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)

    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    items_result = await session.execute(stmt)
    items = list[Any](items_result.scalars().all())
    return total, items


async def cancel_task(session: AsyncSession, task_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.status.not_in(list[Any](TERMINAL_STATUSES)),
        )
        .values(status=TaskStatus.CANCELLED)
        .returning(Task.id)
    )
    updated = result.scalar_one_or_none()
    return updated is not None


def pick_queue_name(priority: TaskPriority, *, settings) -> str:
    mapping: dict[TaskPriority, str] = {
        TaskPriority.HIGH: settings.queue_high,
        TaskPriority.MEDIUM: settings.queue_medium,
        TaskPriority.LOW: settings.queue_low,
    }
    return mapping[priority]


async def update_to_in_progress(session: AsyncSession, task: Task) -> None:
    task.status = TaskStatus.IN_PROGRESS
    await session.flush()


async def finalize_task(
    session: AsyncSession,
    task: Task,
    *,
    success: bool,
    result: str | None = None,
    error: str | None = None,
) -> None:
    task.finished_at = func.now()
    if success:
        task.status = TaskStatus.COMPLETED
        task.result = result
    else:
        task.status = TaskStatus.FAILED
        task.error = error
    await session.flush()


def non_terminal_statuses() -> tuple[TaskStatus, ...]:
    return (TaskStatus.NEW, TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

