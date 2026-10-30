import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelforge.api.problems import ApiProblem
from sentinelforge.db.models import User
from sentinelforge.domains.identity import LOCAL_ANALYST_ID
from sentinelforge.domains.types import ActorKind


async def transaction(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions.begin() as session:
        yield session


Session = Annotated[AsyncSession, Depends(transaction, scope="function")]


async def local_analyst(session: Session) -> User:
    actor = await session.get(User, LOCAL_ANALYST_ID)
    if (
        actor is None
        or not actor.is_active
        or actor.kind != ActorKind.HUMAN
        or actor.auth_source != "local"
    ):
        raise ApiProblem(
            503,
            "local_actor_unavailable",
            "The local analyst identity is unavailable. Rerun database bootstrap.",
        )
    return actor


Analyst = Annotated[User, Depends(local_analyst, scope="function")]


def write_capability(
    request: Request,
    csrf_token: Annotated[
        str,
        Header(
            alias="X-ATE-CSRF",
            min_length=1,
            description="Write token from GET /api/v1/session; "
            "an allowed browser Origin is also required.",
        ),
    ],
) -> None:
    if not secrets.compare_digest(csrf_token.encode(), request.app.state.csrf_token.encode()):
        raise ApiProblem(403, "csrf_invalid", "Reload the local session before saving this change.")
