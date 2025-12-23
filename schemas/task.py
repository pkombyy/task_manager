# ruff: noqa: I001
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.task import TaskPriority, TaskStatus

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)


class TaskRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: str | None
    error: str | None

    model_config = ConfigDict(from_attributes=True)


class TaskList(BaseModel):
    total: int
    items: list[TaskRead]


class TaskStatusRead(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

