"""Each test gets a new database and restricted login on a disposable server."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from sentinelforge.core.config import Settings, get_settings
from sentinelforge.core.database import create_engine, session_factory
from sentinelforge.db.bootstrap import RuntimeRoleSettings, provision_runtime_role
from sentinelforge.db.models import User
from sentinelforge.domains.types import ActorKind


@pytest.fixture
def database(monkeypatch):
    configured = os.getenv("ATE_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("Set ATE_TEST_DATABASE_URL to a disposable PostgreSQL admin connection")
    url = make_url(configured).set(drivername="postgresql")
    token = uuid4().hex
    name, role_name = f"ate_test_{token}", f"ate_test_app_{token}"
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        for key, value in {
            "ATE_POSTGRES_HOST": url.host,
            "ATE_POSTGRES_PORT": str(url.port or 5432),
            "ATE_POSTGRES_USER": url.username,
            "ATE_POSTGRES_PASSWORD": url.password,
            "ATE_POSTGRES_DB": name,
        }.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        owner = Settings()
        command.upgrade(config, "head")
        role = RuntimeRoleSettings(
            postgres_app_user=role_name, postgres_app_password="synthetic-runtime-test-password"
        )
        provision_runtime_role(owner, role)
        runtime = owner.model_copy(
            update={"postgres_user": role_name, "postgres_password": role.postgres_app_password}
        )
        yield owner, runtime, config
    finally:
        get_settings.cache_clear()
        with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))


@pytest_asyncio.fixture
async def sessions(database):
    engine = create_engine(database[1])
    try:
        yield session_factory(engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def actors(sessions):
    analyst, other, service, inactive = uuid4(), uuid4(), uuid4(), uuid4()
    async with sessions.begin() as session:
        session.add_all(
            [
                User(id=analyst, handle="synthetic-analyst", kind=ActorKind.HUMAN),
                User(id=other, handle="synthetic-other", kind=ActorKind.HUMAN),
                User(id=service, handle="synthetic-service", kind=ActorKind.SERVICE),
                User(
                    id=inactive, handle="synthetic-inactive", kind=ActorKind.HUMAN, is_active=False
                ),
            ]
        )
    return analyst, other, service, inactive
