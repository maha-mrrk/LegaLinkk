"""Async database engine and session management."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Callers are responsible for committing or rolling back transactions.
    The session is closed automatically when the request finishes.
    """
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Yield a session backed by a short-lived, isolated engine.

    Celery runs each task inside its own ``asyncio.run`` event loop. Reusing the
    module-level pooled engine across those loops raises "attached to a different
    loop" errors, so background tasks get a dedicated ``NullPool`` engine that is
    disposed as soon as the task finishes.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
