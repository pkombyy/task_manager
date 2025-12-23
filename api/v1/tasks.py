import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_session
from models.task import TaskPriority, TaskStatus
from schemas.task import TaskCreate, TaskList, TaskRead, TaskStatusRead
from services.queue import publish_task
from services.tasks import cancel_task, create_task, get_task, list_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
    description="Создаёт новую задачу, публикует её в очередь по приоритету. "
    "При выключенном AUTO_STATUS_UPDATES статус остаётся NEW.",
)
async def create_task_endpoint(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    task = await create_task(session, payload)
    await session.commit()

    # Publish to RabbitMQ; статус оставляем как есть (авто-обновление управляется воркером)
    await publish_task(task.id, task.priority)
    if settings.auto_status_updates:
        task.status = TaskStatus.PENDING
        await session.commit()
        await session.refresh(task)

    return TaskRead.model_validate(task)


@router.get(
    "",
    response_model=TaskList,
    summary="Получить список задач",
    description="Возвращает задачи с пагинацией и фильтрами по статусу и приоритету.",
)
async def list_tasks_endpoint(
    status_filter: TaskStatus | None = Query(
        None,
        alias="status",
        description="Фильтр по статусу задачи.",
    ),
    priority_filter: TaskPriority | None = Query(
        None,
        alias="priority",
        description="Фильтр по приоритету задачи.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Размер страницы (1-200).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Смещение для пагинации.",
    ),
    session: AsyncSession = Depends(get_session),
) -> TaskList:
    total, items = await list_tasks(
        session,
        status=status_filter,
        priority=priority_filter,
        limit=limit,
        offset=offset,
    )
    return TaskList(total=total, items=[TaskRead.model_validate(t) for t in items])


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Получить задачу",
    description="Возвращает полную информацию о задаче по идентификатору.",
)
async def get_task_endpoint(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    task = await get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return TaskRead.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отменить задачу",
    description="Помечает задачу CANCELLED, если она не завершена. "
    "Не затрагивает задачи в конечных статусах.",
)
async def cancel_task_endpoint(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    deleted = await cancel_task(session, task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отменить: задача не найдена или уже завершена",
        )
    await session.commit()


@router.get(
    "/{task_id}/status",
    response_model=TaskStatusRead,
    summary="Получить статус задачи",
    description="Короткий ответ по статусу и временным меткам исполнения.",
)
async def get_status_endpoint(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskStatusRead:
    task = await get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return TaskStatusRead(
        id=task.id,
        status=task.status,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error=task.error,
    )

