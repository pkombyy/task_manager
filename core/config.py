from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─── Приложение ─────────────────────────────────────────────────────────
    app_name: str = Field(default="task_manager")
    app_env: Literal["local", "test", "prod"] = Field(default="local")
    api_prefix: str = Field(default="/api/v1")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # ─── База данных ────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://task_user:task_pass@postgres:5432/tasks"
    )

    # ─── RabbitMQ ───────────────────────────────────────────────────────────
    rabbitmq_url: str = Field(default="amqp://guest:guest@rabbitmq/")

    queue_high: str = Field(default="tasks.high")
    queue_medium: str = Field(default="tasks.medium")
    queue_low: str = Field(default="tasks.low")
    rabbitmq_prefetch: int = Field(default=10, ge=1)
    retry_max_attempts: int = Field(default=3, ge=0)
    retry_backoff_seconds: int = Field(default=2, ge=0)
    worker_requeue_on_fail: bool = Field(default=False)
    auto_status_updates: bool = Field(default=False)

    # ─── Воркер ─────────────────────────────────────────────────────────────
    worker_concurrency: int = Field(default=4, ge=1)
    task_execution_timeout: int = Field(default=300, ge=1)
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9000, ge=1, le=65535)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
    )


settings = Settings()
