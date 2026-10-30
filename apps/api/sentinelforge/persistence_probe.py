"""Migrate/verify a uniquely named synthetic database, never the application DB."""

import argparse
import asyncio
import re
import sys
from hashlib import sha256

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import select

from sentinelforge.core.config import Settings, get_settings
from sentinelforge.core.database import create_engine, session_factory
from sentinelforge.db.models import Alert, Case, CaseAlert, CaseEvent, CaseNote, Evidence
from sentinelforge.domains.cases.schemas import NoteInput, Transition
from sentinelforge.domains.cases.service import CaseService
from sentinelforge.domains.types import CaseStatus, Disposition
from sentinelforge.seed_demo import DEMO_ANALYST, DEMO_CASE, seed_demo


async def prepare(settings: Settings) -> None:
    engine = create_engine(settings)
    try:
        async with session_factory(engine).begin() as session:
            case = await seed_demo(session)
            note = await session.scalar(select(CaseNote).where(CaseNote.case_id == case.id))
            assert note is not None
            service = CaseService(session, DEMO_ANALYST)
            await service.edit_note(
                case.id,
                4,
                note.id,
                NoteInput(body="Synthetic revised note"),
                "Verify retained note revisions",
            )
            await service.assign(case.id, 5, DEMO_ANALYST, "Synthetic persistence owner")
            await service.transition(
                case.id, 6, Transition(status="investigating", reason="Review")
            )
            await service.transition(
                case.id,
                7,
                Transition(
                    status="resolved",
                    disposition="inconclusive",
                    reason="Synthetic analyst disposition",
                ),
            )
            await service.transition(
                case.id, 8, Transition(status="closed", reason="Synthetic review complete")
            )
    finally:
        await engine.dispose()


async def verify(settings: Settings) -> None:
    engine = create_engine(settings)
    try:
        async with session_factory(engine).begin() as session:
            case = await session.get(Case, DEMO_CASE)
            assert case is not None and case.version == 9 and case.status == CaseStatus.CLOSED
            assert case.disposition == Disposition.INCONCLUSIVE and case.assigned_to == DEMO_ANALYST
            note = await session.scalar(select(CaseNote).where(CaseNote.case_id == case.id))
            assert note and note.revision == 2 and note.body == "Synthetic revised note"
            link = await session.scalar(select(CaseAlert).where(CaseAlert.case_id == case.id))
            assert link and await session.get(Alert, link.alert_id) is not None
            evidence = await session.scalar(select(Evidence).where(Evidence.case_id == case.id))
            assert evidence and evidence.snapshot is not None
            assert evidence.snapshot_sha256 == sha256(evidence.snapshot.encode()).hexdigest()
            events = list(
                await session.scalars(
                    select(CaseEvent)
                    .where(CaseEvent.case_id == case.id)
                    .order_by(CaseEvent.case_version)
                )
            )
            assert [event.case_version for event in events] == list(range(1, 10))
            assert all(event.actor_id == DEMO_ANALYST and event.occurred_at for event in events)
            assert events[4].before and events[4].before["note"]["revision"] == 1
            assert events[4].after and events[4].after["note"]["revision"] == 2
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify", "cleanup"])
    parser.add_argument("token")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{32}", args.token):
        parser.error("token must be a lowercase UUID hex string")
    name = f"ate_phase1_probe_{args.token}"
    settings = get_settings()
    url = settings.database_url.set(drivername="postgresql")
    try:
        with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as admin:
            if args.action == "cleanup":
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
                print("Synthetic persistence database cleaned up.")
                return
            if args.action == "prepare":
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        probe_settings = settings.model_copy(update={"postgres_db": name})
        if args.action == "prepare":
            config = Config("alembic.ini")
            config.attributes["settings"] = probe_settings
            command.upgrade(config, "head")
        operation = prepare(probe_settings) if args.action == "prepare" else verify(probe_settings)
        asyncio.run(
            operation, loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None
        )
        print(f"Synthetic domain persistence probe {args.action}: passed.")
    except Exception as exc:
        raise SystemExit(f"Persistence probe failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
