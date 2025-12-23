import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import aio_pika
from prometheus_client import Counter, Histogram, start_http_server
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from db.base import Base
from models.task import Task, TaskStatus
from services.queue import publish_task
from services.tasks import finalize_task, non_terminal_statuses, update_to_in_progress

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker[AsyncSession](
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
logger = logging.getLogger(__name__)
TASKS_PROCESSED = Counter(
    "tasks_processed_total",
    "Количество обработанных задач",
    ["status"],
)
TASK_DURATION = Histogram(
    "task_duration_seconds",
    "Длительность выполнения задачи",
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Схема БД доступна")


async def process_task(task_id: uuid.UUID) -> None:
    # Имитация полезной работы (I/O bound) — здесь будет реальная логика
    await asyncio.sleep(1)


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process(requeue=settings.worker_requeue_on_fail):
        failed = False
        start_time = datetime.now(timezone.utc)
        attempts = int(message.headers.get("attempt", 0) or 0) if message.headers else 0  # type: ignore[arg-type]
        try:
            payload = json.loads(message.body.decode())
            task_id = uuid.UUID(payload["task_id"])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.exception("Не удалось разобрать сообщение: %s", exc)
            return

        async with session_scope() as session:
            task: Task | None = await session.get(Task, task_id)
            if not task or task.status not in non_terminal_statuses():
                logger.info(
                    "Пропуск сообщения для task=%s со статусом %s",
                    task_id,
                    getattr(task, "status", None),
                )
                return

            task.started_at = task.started_at or datetime.now(timezone.utc)
            if settings.auto_status_updates:
                await update_to_in_progress(session, task)
                await session.commit()
                logger.info("Задача %s переведена в IN_PROGRESS", task_id)

            try:
                await asyncio.wait_for(
                    process_task(task_id),
                    timeout=settings.task_execution_timeout,
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                failed = True
                logger.exception("Задача %s завершилась ошибкой: %s", task_id, exc)
                if attempts < settings.retry_max_attempts:
                    if settings.auto_status_updates:
                        task.status = TaskStatus.PENDING
                        await session.flush()
                        await session.commit()
                    delay = settings.retry_backoff_seconds * (2 ** attempts)
                    logger.info(
                        "Переотправка задачи %s, попытка %s, задержка %.2f c",
                        task_id,
                        attempts + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    await publish_task(task.id, task.priority, attempts=attempts + 1)
                    TASKS_PROCESSED.labels(status="retry").inc()
                    return
                if settings.auto_status_updates and not settings.worker_requeue_on_fail:
                    await finalize_task(
                        session,
                        task,
                        success=False,
                        error=str(exc),
                    )
                    await session.commit()
                    TASKS_PROCESSED.labels(status="failed").inc()
                    return
                if settings.worker_requeue_on_fail:
                    TASKS_PROCESSED.labels(status="failed").inc()
                    raise RuntimeError("Ошибка обработки, возвращаем в очередь")
            else:
                if settings.auto_status_updates:
                    await finalize_task(
                        session,
                        task,
                        success=True,
                        result="Task completed",
                    )
                    await session.commit()
                logger.info("Задача %s завершена", task_id)

            if settings.auto_status_updates:
                await session.commit()
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            TASK_DURATION.observe(duration)
            if failed:
                TASKS_PROCESSED.labels(status="failed").inc()
            else:
                TASKS_PROCESSED.labels(status="completed").inc()


async def consume() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    if settings.metrics_enabled:
        start_http_server(settings.metrics_port)
        logger.info("Метрики Prometheus запущены на :%s", settings.metrics_port)
    await ensure_tables()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    queues = [settings.queue_high, settings.queue_medium, settings.queue_low]
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=settings.rabbitmq_prefetch)

        for queue_name in queues:
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.consume(handle_message, no_ack=False)  # type: ignore[arg-type]

        await asyncio.Future()  # keep alive


def main() -> None:
    asyncio.run(consume())


if __name__ == "__main__":
    main()

