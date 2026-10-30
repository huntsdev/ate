"""Explicit, idempotent synthetic seed; never runs during application startup."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelforge.core.config import get_settings
from sentinelforge.core.database import create_engine, session_factory
from sentinelforge.db.models import Case, User
from sentinelforge.domains.cases.schemas import (
    AlertInput,
    CaseDetails,
    EvidenceInput,
    LinkInput,
    NoteInput,
)
from sentinelforge.domains.cases.service import CaseService
from sentinelforge.domains.types import ActorKind

DEMO_ANALYST = UUID("00000000-0000-4000-8000-000000000100")
DEMO_IMPORTER = UUID("00000000-0000-4000-8000-000000000101")
DEMO_CASE = UUID("00000000-0000-4000-8000-000000000001")


def load_fixtures() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    if not fixture_dir.exists():
        fixture_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
    alert = json.loads((fixture_dir / "synthetic_alert.json").read_text(encoding="utf-8"))
    case_data = json.loads((fixture_dir / "synthetic_case.json").read_text(encoding="utf-8"))
    if alert.get("synthetic") is not True or case_data.get("synthetic") is not True:
        raise ValueError("Demo seed requires synthetic fixtures")
    return alert, case_data


async def seed_demo(session: AsyncSession) -> Case:
    alert, case_data = await asyncio.to_thread(load_fixtures)
    for actor_id, handle, kind in (
        (DEMO_ANALYST, "demo-analyst", ActorKind.HUMAN),
        (DEMO_IMPORTER, "demo-importer", ActorKind.SERVICE),
    ):
        await session.execute(
            insert(User)
            .values(
                id=actor_id,
                handle=handle,
                kind=kind,
                auth_source="synthetic",
            )
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        existing_actor = await session.get(User, actor_id, populate_existing=True)
        if existing_actor is None or existing_actor.handle != handle or existing_actor.kind != kind:
            raise ValueError("Reserved demo actor identity is already in use")
    existing = await session.get(Case, DEMO_CASE)
    if existing is not None:
        if existing.created_by != DEMO_ANALYST:
            raise ValueError("Reserved demo case identity is already in use")
        return existing
    service = CaseService(session, DEMO_ANALYST)
    imported = await CaseService(session, DEMO_IMPORTER).import_alert(
        AlertInput(
            **{
                key: alert[key]
                for key in (
                    "provider",
                    "provider_scope",
                    "external_alert_id",
                    "title",
                    "severity",
                    "observed_at",
                    "host",
                    "summary",
                )
            },
            source_ref="synthetic://fixtures/alert-0001",
        )
    )
    case = await service.create_case(CaseDetails(title=case_data["title"]), case_id=DEMO_CASE)
    await service.link_alert(
        case.id,
        1,
        imported.alert.id,
        LinkInput(reason="Explicit synthetic demonstration", method="synthetic"),
    )
    await service.add_note(
        case.id, 2, NoteInput(body="Synthetic data only. No commands are executed.")
    )
    await service.add_evidence(
        case.id,
        3,
        EvidenceInput(
            provider="synthetic",
            provider_scope=alert["provider_scope"],
            source_event_id="event-0001",
            source_ref="synthetic://fixtures/event-0001",
            observed_at=alert["observed_at"],
            sensitivity="synthetic",
            snapshot=alert["summary"],
        ),
        "Preserve deterministic synthetic evidence",
    )
    return case


async def run_seed() -> None:
    engine = create_engine(get_settings())
    try:
        async with session_factory(engine).begin() as session:
            case = await seed_demo(session)
            display_id = case.display_id
        print(f"Synthetic demo ready: {display_id}. No external providers contacted.")
    finally:
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(
            run_seed(), loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None
        )
    except Exception as exc:
        raise SystemExit(f"Synthetic seed failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
