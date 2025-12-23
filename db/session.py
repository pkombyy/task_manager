# ruff: noqa: I001
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from db.base import Base


engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker[AsyncSession](
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async DB session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables in dev mode (migrations should be used in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

