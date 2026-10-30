import asyncio
import sys

from alembic import context
from sqlalchemy.engine import Connection

from sentinelforge.core.config import Settings, get_settings
from sentinelforge.core.database import Base, create_engine
from sentinelforge.db import models  # noqa: F401 -- register domain metadata

target_metadata = Base.metadata


def migration_settings() -> Settings:
    return context.config.attributes.get("settings") or get_settings()


def run_migrations_offline() -> None:
    context.configure(
        url=migration_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_engine(migration_settings())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(
        run_migrations_online(),
        loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None,
    )
