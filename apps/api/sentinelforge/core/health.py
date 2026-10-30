import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Probe = Callable[[], Awaitable[None]]


class Health(BaseModel):
    status: Literal["alive"] = "alive"
    service: Literal["ate"] = "ate"
    phase: Literal[2] = 2
    optional_dependencies: dict[str, Literal["not_enabled"]] = {
        "elastic": "not_enabled",
        "ollama": "not_enabled",
    }


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, Literal["healthy", "unavailable"]]


class ReadinessChecker:
    def __init__(self, probes: dict[str, Probe], timeout: float):
        self.probes = probes
        self.timeout = timeout

    async def check(self) -> Readiness:
        async def run(name: str, probe: Probe) -> tuple[str, Literal["healthy", "unavailable"]]:
            try:
                await asyncio.wait_for(probe(), timeout=self.timeout)
                return name, "healthy"
            except Exception:
                # Never return provider exception details to clients or logs.
                return name, "unavailable"

        dependencies = dict(await asyncio.gather(*(run(n, p) for n, p in self.probes.items())))
        return Readiness(
            status="ready" if all(v == "healthy" for v in dependencies.values()) else "not_ready",
            dependencies=dependencies,
        )


def dependency_probes(engine: AsyncEngine, redis: Redis) -> dict[str, Probe]:
    async def postgres() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def broker() -> None:
        if not await redis.ping():
            raise ConnectionError("Redis did not acknowledge PING")

    return {"postgres": postgres, "redis": broker}
