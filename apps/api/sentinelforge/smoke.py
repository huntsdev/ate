"""Real-infrastructure smoke checks, run inside the API container."""

import asyncio
import json
import urllib.request

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import text

from sentinelforge.core.config import get_settings
from sentinelforge.core.database import create_engine


async def infrastructure() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    redis = Redis.from_url(str(settings.redis_url), socket_timeout=3, socket_connect_timeout=3)
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            )
            assert await connection.scalar(text("SELECT count(*) FROM cases")) is not None
            assert not await connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
        assert await redis.ping()
    finally:
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    stage = "database_and_broker"
    try:
        asyncio.run(infrastructure())
        stage = "api"
        for route in ("health", "health/live", "health/ready"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:8000/api/v1/{route}", timeout=8
            ) as response:
                assert response.status == 200
        stage = "worker_task"
        from worker import noop

        result = noop.delay()
        try:
            assert result.get(timeout=15) == {"status": "ok"}
        finally:
            result.forget()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": [
                        "migration_head",
                        "restricted_postgres",
                        "redis",
                        "api",
                        "worker_task",
                    ],
                }
            )
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "stage": stage, "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
