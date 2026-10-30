import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from sentinelforge.core.health import ReadinessChecker, dependency_probes
from sentinelforge.main import create_app


def test_liveness_never_probes_dependencies(settings):
    probe = AsyncMock(side_effect=AssertionError("liveness queried a dependency"))
    checker = ReadinessChecker({"postgres": probe, "redis": probe}, 0.1)
    with TestClient(create_app(settings, checker)) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response.json()["optional_dependencies"] == {
        "elastic": "not_enabled",
        "ollama": "not_enabled",
    }
    assert response.headers["X-Correlation-ID"]
    assert response.headers["Cache-Control"] == "no-store"
    probe.assert_not_called()


def test_readiness_with_only_required_dependencies(settings):
    postgres, redis = AsyncMock(), AsyncMock()
    checker = ReadinessChecker({"postgres": postgres, "redis": redis}, 0.1)
    with TestClient(create_app(settings, checker)) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"postgres": "healthy", "redis": "healthy"},
    }
    postgres.assert_awaited_once()
    redis.assert_awaited_once()


@pytest.mark.parametrize("failed", ["postgres", "redis"])
def test_dependency_failure_is_redacted_and_recoverable(settings, failed):
    probes = {"postgres": AsyncMock(), "redis": AsyncMock()}
    probes[failed].side_effect = RuntimeError("password=synthetic-do-not-leak")
    checker = ReadinessChecker(probes, 0.1)
    with TestClient(create_app(settings, checker)) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["dependencies"][failed] == "unavailable"
        assert "synthetic-do-not-leak" not in response.text
        assert client.get("/api/v1/health/live").status_code == 200
        probes[failed].side_effect = None
        assert client.get("/api/v1/health/ready").status_code == 200


async def test_readiness_times_out_concurrently():
    cancelled = []

    async def slow():
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    checker = ReadinessChecker({"postgres": slow, "redis": slow}, 0.05)
    started = time.monotonic()
    result = await checker.check()
    assert time.monotonic() - started < 0.5
    assert result.status == "not_ready"
    assert result.dependencies == {"postgres": "unavailable", "redis": "unavailable"}
    assert len(cancelled) == 2


async def test_probes_execute_sql_and_ping():
    connection = AsyncMock()
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
    redis = AsyncMock()
    redis.ping.return_value = True
    probes = dependency_probes(engine, redis)
    await probes["postgres"]()
    await probes["redis"]()
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    redis.ping.assert_awaited_once()
    redis.ping.return_value = False
    with pytest.raises(ConnectionError):
        await probes["redis"]()
