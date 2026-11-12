"""Database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=settings.app_debug and settings.app_env == "development",
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    global _sync_engine, _sync_session_factory
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.database_url_sync,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
        _sync_session_factory = sessionmaker(
            _sync_engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sync_engine


def get_sync_session_factory():
    get_sync_engine()
    return _sync_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise