import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint

from sentinelforge.core.config import Settings, get_settings
from sentinelforge.core.database import create_engine
from sentinelforge.core.health import Health, Readiness, ReadinessChecker, dependency_probes
from sentinelforge.core.logging import configure_logging


def create_app(
    settings: Settings | None = None, checker: ReadinessChecker | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if checker is not None:
            app.state.checker = checker
            yield
            return
        engine = create_engine(settings)
        redis = Redis.from_url(
            str(settings.redis_url),
            socket_connect_timeout=settings.readiness_timeout_seconds,
            socket_timeout=settings.readiness_timeout_seconds,
        )
        app.state.checker = ReadinessChecker(
            dependency_probes(engine, redis), settings.readiness_timeout_seconds
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="ATÉ", version="0.0.1", lifespan=lifespan)

    @app.middleware("http")
    async def request_logging(request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = str(uuid4())
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logging.getLogger("ate").error(
                "request_failed", extra={"correlation_id": correlation_id, "status_code": 500}
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Cache-Control"] = "no-store"
        logging.getLogger("ate").info(
            "request_complete",
            extra={
                "correlation_id": correlation_id,
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            },
        )
        return response

    @app.get("/api/v1/health", response_model=Health)
    @app.get("/api/v1/health/live", response_model=Health)
    async def live() -> Health:
        return Health()

    @app.get(
        "/api/v1/health/ready", response_model=Readiness, responses={503: {"model": Readiness}}
    )
    async def ready(request: Request) -> JSONResponse:
        result = await request.app.state.checker.check()
        return JSONResponse(
            status_code=200 if result.status == "ready" else 503, content=result.model_dump()
        )

    return app
