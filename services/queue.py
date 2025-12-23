import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, cast

import aio_pika

from core.config import settings
from models.task import TaskPriority
from services.tasks import pick_queue_name


@asynccontextmanager
async def get_rabbit_connection() -> AsyncIterator[aio_pika.RobustConnection]:
    connection = cast(
        aio_pika.RobustConnection,
        await aio_pika.connect_robust(settings.rabbitmq_url),
    )
    try:
        yield connection
    finally:
        await connection.close()


async def publish_task(task_id: uuid.UUID, priority: TaskPriority, *, attempts: int = 0) -> None:
    """Отправить идентификатор задачи в очередь нужного приоритета."""
    queue_name = pick_queue_name(priority, settings=settings)
    async with get_rabbit_connection() as connection:
        channel = await connection.channel()
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps({"task_id": str(task_id)}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={"attempt": attempts},
            ),
            routing_key=queue_name,
        )

