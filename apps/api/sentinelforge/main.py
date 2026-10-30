import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from sentinelforge.api.boundary import LocalBoundary
from sentinelforge.api.problems import install_problem_handlers
from sentinelforge.api.routes import router
from sentinelforge.core.config import Settings, get_settings
from sentinelforge.core.database import create_engine, session_factory
from sentinelforge.core.health import Health, Readiness, ReadinessChecker, dependency_probes
from sentinelforge.core.logging import configure_logging


def create_app(
    settings: Settings | None = None, checker: ReadinessChecker | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.sessions = session_factory(engine)
        redis = Redis.from_url(
            str(settings.redis_url),
            socket_connect_timeout=settings.readiness_timeout_seconds,
            socket_timeout=settings.readiness_timeout_seconds,
        )
        app.state.checker = checker or ReadinessChecker(
            dependency_probes(engine, redis), settings.readiness_timeout_seconds
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="ATÉ", version="0.0.1", lifespan=lifespan)

    app.state.csrf_token = secrets.token_urlsafe(32)
    app.add_middleware(LocalBoundary, settings=settings, csrf_token=app.state.csrf_token)
    install_problem_handlers(app)
    app.include_router(router)

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
