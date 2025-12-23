import os
from importlib import import_module, reload
from typing import AsyncIterator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from db.base import Base


@pytest_asyncio.fixture()
async def app() -> AsyncIterator[FastAPI]:
    db_path = "test_tasks.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["APP_ENV"] = "test"
    config_module = import_module("core.config")
    reload(config_module)
    session_module = import_module("db.session")
    reload(session_module)
    application_module = import_module("main")
    reload(application_module)
    application = application_module.create_app()
    try:
        yield application
    finally:
        await session_module.engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest_asyncio.fixture()
async def test_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    session_module = import_module("db.session")
    engine = session_module.engine
    assert "tasks" in Base.metadata.tables, "Task model not registered in Base metadata"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        )
        assert result.scalar_one() == "tasks", "tasks table not created"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

