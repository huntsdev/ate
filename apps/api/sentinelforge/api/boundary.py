"""Loopback single-user boundary, write protection, and bounded HTTP bodies."""

import logging
import secrets
import time
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sentinelforge.api.problems import problem_response
from sentinelforge.core.config import Settings


class LocalBoundary:
    def __init__(self, app: ASGIApp, settings: Settings, csrf_token: str):
        self.app, self.settings, self.csrf_token = app, settings, csrf_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id, started = str(uuid4()), time.monotonic()
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        headers = Headers(scope=scope)
        status_code, response_started = 500, False

        async def send_response(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started, status_code = True, message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-correlation-id", correlation_id.encode()),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"cross-origin-resource-policy", b"same-origin"),
                ]
            await send(message)

        async def reject(status: int, code: str, detail: str) -> None:
            await problem_response(status, code, detail, correlation_id)(
                scope, receive, send_response
            )

        try:
            host = headers.get("host", "").lower().split(":")[0]
            if len(headers.getlist("host")) != 1 or host not in self.settings.trusted_hosts:
                await reject(400, "invalid_host", "Only the local development host is supported.")
                return
            origin = headers.get("origin")
            if origin is not None and origin not in self.settings.browser_origins:
                await reject(403, "invalid_origin", "This browser origin is not allowed.")
                return
            if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
                token = headers.get("x-ate-csrf", "")
                if origin is None or not secrets.compare_digest(
                    token.encode(), self.csrf_token.encode()
                ):
                    await reject(
                        403, "csrf_invalid", "Reload the local session before saving this change."
                    )
                    return
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 65536:
                        await reject(413, "request_too_large", "Requests are limited to 64 KiB.")
                        return
                    if not message.get("more_body", False):
                        break
                replayed = False

                async def replay() -> Message:
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, replay, send_response)
            else:
                await self.app(scope, receive, send_response)
        except Exception as exc:
            logging.getLogger("ate").error(
                "request_failed",
                extra={"correlation_id": correlation_id, "error_type": type(exc).__name__},
            )
            if not response_started:
                await reject(500, "internal_error", "The request could not be completed.")
        finally:
            logging.getLogger("ate").info(
                "request_complete",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )
