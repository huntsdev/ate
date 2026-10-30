from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from sentinelforge.api.schemas import AlertOut, CaseOut
from sentinelforge.db.models import Alert, Case, CaseAlert, User
from sentinelforge.domains.cases.rules import TRANSITIONS
from sentinelforge.domains.errors import NotFound
from sentinelforge.domains.types import CaseStatus


async def require_case(session: AsyncSession, case_id: UUID) -> Case:
    row = await session.get(Case, case_id, populate_existing=True)
    if row is None:
        raise NotFound("Case not found")
    return row


async def case_outputs(session: AsyncSession, rows: list[Case]) -> list[CaseOut]:
    if not rows:
        return []
    owner_ids = {row.assigned_to for row in rows if row.assigned_to is not None}
    owners = {
        user.id: user.handle
        for user in await session.scalars(select(User).where(User.id.in_(owner_ids)))
    }
    sources: dict[UUID, set[str]] = defaultdict(set)
    for case_id, provider in await session.execute(
        select(CaseAlert.case_id, Alert.provider)
        .join(Alert, CaseAlert.alert_id == Alert.id)
        .where(CaseAlert.case_id.in_([row.id for row in rows]))
    ):
        sources[case_id].add(provider)
    return [
        CaseOut.model_validate(row).model_copy(
            update={
                "owner_handle": owners.get(row.assigned_to) if row.assigned_to else None,
                "sources": sorted(sources[row.id]),
                "allowed_transitions": [
                    status for status in CaseStatus if status in TRANSITIONS[row.status]
                ],
            }
        )
        for row in rows
    ]


async def case_output(session: AsyncSession, case_id: UUID) -> CaseOut:
    return (await case_outputs(session, [await require_case(session, case_id)]))[0]


async def alert_outputs(session: AsyncSession, rows: list[Alert]) -> list[AlertOut]:
    if not rows:
        return []
    count_rows = (
        await session.execute(
            select(CaseAlert.alert_id, func.count())
            .where(CaseAlert.alert_id.in_([row.id for row in rows]))
            .group_by(CaseAlert.alert_id)
        )
    ).all()
    counts = {alert_id: count for alert_id, count in count_rows}
    return [
        AlertOut.model_validate(row).model_copy(update={"linked_case_count": counts.get(row.id, 0)})
        for row in rows
    ]


def search_text(
    value: str, *columns: ColumnElement[Any] | InstrumentedAttribute[Any]
) -> ColumnElement[bool]:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(*(column.ilike(f"%{escaped}%", escape="\\") for column in columns))


def severity_order(column: ColumnElement[Any] | InstrumentedAttribute[Any]) -> ColumnElement[int]:
    return sql_case({"low": 1, "medium": 2, "high": 3, "critical": 4}, value=column, else_=0)
