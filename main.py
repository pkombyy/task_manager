import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1.tasks import router as tasks_router
from core.config import settings
from db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env == "local":
        await init_db()
    yield


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Сервис асинхронных задач: создание, список с фильтрами, чтение, отмена, статус. "
            "Задачи публикуются в RabbitMQ с приоритетными очередями."
        ),
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        lifespan=lifespan,
    )

    app.include_router(tasks_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

