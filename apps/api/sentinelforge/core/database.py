import math

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from sentinelforge.core.config import Settings


class Base(DeclarativeBase):
    """Shared model metadata; schema changes are applied only through Alembic."""


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=0,
        pool_timeout=settings.readiness_timeout_seconds,
        connect_args={
            "connect_timeout": max(1, math.ceil(settings.readiness_timeout_seconds)),
            "options": f"-c statement_timeout={int(settings.readiness_timeout_seconds * 1000)}",
        },
        hide_parameters=True,
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
