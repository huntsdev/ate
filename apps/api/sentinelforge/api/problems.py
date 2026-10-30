from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError
from starlette.exceptions import HTTPException

from sentinelforge.domains.errors import (
    ActorNotAllowed,
    Conflict,
    DomainError,
    InvalidDisposition,
    InvalidTransition,
    NotFound,
    VersionConflict,
)


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    correlation_id: str
    errors: list[dict[str, str]] = []


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail


def problem_response(
    status: int,
    code: str,
    detail: str,
    correlation_id: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    titles = {
        400: "Bad request",
        403: "Access denied",
        404: "Not found",
        405: "Method not allowed",
        409: "Conflict",
        413: "Request too large",
        422: "Validation failed",
        500: "Internal server error",
        503: "Service unavailable",
    }
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=Problem(
            type=f"urn:ate:problem:{code}",
            title=titles.get(status, "Request failed"),
            status=status,
            detail=detail,
            code=code,
            correlation_id=correlation_id,
            errors=errors or [],
        ).model_dump(),
    )


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem(request: Request, exc: ApiProblem) -> JSONResponse:
        return problem_response(exc.status, exc.code, exc.detail, request.state.correlation_id)

    @app.exception_handler(DomainError)
    async def domain_problem(request: Request, exc: DomainError) -> JSONResponse:
        status, code = 422, "invalid_operation"
        if isinstance(exc, NotFound):
            status, code = 404, "not_found"
        elif isinstance(exc, VersionConflict):
            status, code = 409, "version_conflict"
        elif isinstance(exc, Conflict):
            status, code = 409, "association_conflict"
        elif isinstance(exc, ActorNotAllowed):
            status, code = 403, "actor_not_allowed"
        elif isinstance(exc, InvalidTransition):
            status, code = 409, "invalid_transition"
        elif isinstance(exc, InvalidDisposition):
            code = "invalid_disposition"
        return problem_response(status, code, str(exc), request.state.correlation_id)

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(item) for item in error["loc"]),
                "message": "Unexpected field"
                if error["type"] == "extra_forbidden"
                else "Invalid value",
            }
            for error in exc.errors()[:20]
        ]
        return problem_response(
            422,
            "validation_error",
            "Check the highlighted fields and try again.",
            request.state.correlation_id,
            errors,
        )

    @app.exception_handler(HTTPException)
    async def http_problem(request: Request, exc: HTTPException) -> JSONResponse:
        return problem_response(
            exc.status_code,
            "http_error",
            "The requested operation is unavailable.",
            request.state.correlation_id,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_problem(request: Request, exc: IntegrityError) -> JSONResponse:
        return problem_response(
            409,
            "data_conflict",
            "The change could not be committed. Reload and review your inputs.",
            request.state.correlation_id,
        )

    async def unavailable(request: Request, exc: Any) -> JSONResponse:
        return problem_response(
            503,
            "storage_unavailable",
            "Case storage is unavailable. Try again when services recover.",
            request.state.correlation_id,
        )

    app.add_exception_handler(OperationalError, unavailable)
    app.add_exception_handler(TimeoutError, unavailable)
