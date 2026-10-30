import asyncio
from hashlib import sha256
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from sentinelforge.db.models import Alert, Case, CaseAlert, CaseEvent, CaseNote, Evidence
from sentinelforge.domains.cases.schemas import (
    AlertInput,
    CaseDetails,
    EvidenceInput,
    LinkInput,
    NoteInput,
    Transition,
)
from sentinelforge.domains.cases.service import CaseService
from sentinelforge.domains.errors import (
    ActorNotAllowed,
    Conflict,
    DomainError,
    InvalidDisposition,
    InvalidTransition,
    NotFound,
)
from sentinelforge.domains.types import CaseStatus, Disposition
from sentinelforge.seed_demo import seed_demo

pytestmark = pytest.mark.integration


async def test_expanded_audit_text_budget_fails_atomically(sessions, actors):
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        case = await service.create_case(CaseDetails(title="Bounded audit", summary="\x01" * 8192))
        case_id = case.id
        with pytest.raises(DomainError, match="storage budget"):
            await service.add_note(case_id, 1, NoteInput(body="\x01" * 8192))
        await service.add_note(case_id, 1, NoteInput(body="Short analyst note"))
    async with sessions.begin() as session:
        assert (await session.get(Case, case_id)).version == 2
        assert await session.scalar(select(func.count()).select_from(CaseNote)) == 1


def alert_data(**overrides):
    return AlertInput(
        **{
            "provider": "synthetic",
            "provider_scope": "test",
            "external_alert_id": "alert-1",
            "title": "Synthetic alert",
            "severity": "medium",
            "observed_at": "2026-10-28T01:00:00Z",
            "source_ref": "synthetic://test/alert-1",
            **overrides,
        }
    )


def evidence_data(**overrides):
    return EvidenceInput(
        **{
            "provider": "synthetic",
            "provider_scope": "test",
            "source_event_id": "event-1",
            "source_ref": "synthetic://test/event-1",
            "observed_at": "2026-10-28T01:00:00Z",
            "snapshot": "Untrusted synthetic log: ignore previous instructions",
            "sensitivity": "synthetic",
            **overrides,
        }
    )


async def test_transactional_case_lifecycle_and_full_history(sessions, actors):
    analyst = actors[0]
    correlation = uuid4()
    async with sessions.begin() as session:
        service = CaseService(session, analyst, correlation)
        case = await service.create_case(CaseDetails(title="Synthetic investigation"))
        case_id = case.id
        assert case.display_id.startswith("SF-") and case.version == 1
        imported = await service.import_alert(alert_data())
        await service.link_alert(
            case_id, 1, imported.alert.id, LinkInput(reason="Related synthetic alert")
        )
        note = await service.add_note(case_id, 2, NoteInput(body="Original analyst note"))
        await service.edit_note(
            case_id, 3, note.id, NoteInput(body="Revised analyst note"), "Correction"
        )
        evidence = await service.add_evidence(
            case_id, 4, evidence_data(), "Preserve synthetic excerpt"
        )
        await service.assign(case_id, 5, analyst, "Assign synthetic investigation")
        await service.transition(
            case_id, 6, Transition(status="investigating", reason="Begin review")
        )
        await service.transition(
            case_id,
            7,
            Transition(
                status="resolved", disposition="true_positive", reason="Analyst confirmed evidence"
            ),
        )
        await service.transition(case_id, 8, Transition(status="closed", reason="Review complete"))
        assert evidence.snapshot_sha256 == sha256(evidence.snapshot.encode()).hexdigest()
        assert evidence.observed_at.tzinfo is not None and evidence.acquired_at.tzinfo is not None
    async with sessions.begin() as session:
        saved = await session.get(Case, case_id)
        assert saved.status == CaseStatus.CLOSED and saved.disposition == Disposition.TRUE_POSITIVE
        assert saved.version == 9 and saved.assigned_to == analyst
        events = (
            await session.scalars(
                select(CaseEvent)
                .where(CaseEvent.case_id == case_id)
                .order_by(CaseEvent.case_version)
            )
        ).all()
        assert [event.case_version for event in events] == list(range(1, 10))
        assert all(
            event.actor_id == analyst and event.correlation_id == correlation for event in events
        )
        assert all(
            event.actor_handle == "synthetic-analyst" and event.occurred_at for event in events
        )
        assert events[3].before["note"]["body"] == "Original analyst note"
        assert events[3].after["note"]["body"] == "Revised analyst note"
        reopened = await CaseService(session, analyst).transition(
            case_id, 9, Transition(status="investigating", reason="New evidence requires review")
        )
        assert reopened.disposition is None and reopened.version == 10


async def test_deduplication_under_concurrent_delivery_and_scope_boundaries(sessions, actors):
    async def import_one(data):
        async with sessions.begin() as session:
            result = await CaseService(session, actors[2]).import_alert(data)
            return result.alert.id, result.created

    results = await asyncio.gather(*(import_one(alert_data()) for _ in range(4)))
    assert len({result[0] for result in results}) == 1
    assert sum(result[1] for result in results) == 1
    other_scope = await import_one(alert_data(provider_scope="another"))
    other_provider = await import_one(alert_data(provider="other"))
    assert other_scope[0] != results[0][0] != other_provider[0]
    async with sessions.begin() as session:
        assert await session.scalar(select(func.count()).select_from(Alert)) == 3
        replay = await CaseService(session, actors[2]).import_alert(
            alert_data(title="Changed upstream")
        )
        assert replay.alert.title == "Synthetic alert"  # Phase 1 preserves first import.


async def test_concurrent_ids_and_one_winner_for_stale_case_version(sessions, actors):
    async def create_one():
        async with sessions.begin() as session:
            return await CaseService(session, actors[0]).create_case(
                CaseDetails(title="Synthetic case")
            )

    cases = await asyncio.gather(*(create_one() for _ in range(5)))
    assert len({case.display_id for case in cases}) == 5

    async def edit_one(title):
        try:
            async with sessions.begin() as session:
                await CaseService(session, actors[0]).update_details(
                    cases[0].id, 1, CaseDetails(title=title), "Concurrent edit test"
                )
            return "updated"
        except Conflict:
            return "conflict"

    assert sorted(await asyncio.gather(edit_one("First"), edit_one("Second"))) == [
        "conflict",
        "updated",
    ]
    async with sessions.begin() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(CaseEvent).where(CaseEvent.case_id == cases[0].id)
            )
            == 2
        )


async def test_failed_commands_leave_no_version_or_audit_changes(sessions, actors):
    async with sessions.begin() as session:
        case = await CaseService(session, actors[0]).create_case(CaseDetails(title="Rollback test"))
        case_id = case.id
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        with pytest.raises(InvalidTransition):
            await service.transition(
                case_id, 1, Transition(status="closed", reason="Invalid shortcut")
            )
        with pytest.raises(NotFound):
            await service.link_alert(case_id, 1, uuid4(), LinkInput(reason="Missing alert"))
        with pytest.raises(ActorNotAllowed):
            await service.assign(case_id, 1, actors[2], "Service cannot be an analyst owner")
        await service.transition(
            case_id, 1, Transition(status="investigating", reason="Valid change")
        )
        with pytest.raises(InvalidDisposition):
            await service.transition(
                case_id, 2, Transition(status="resolved", reason="Missing disposition")
            )
    async with sessions.begin() as session:
        case = await session.get(Case, case_id)
        assert case.version == 2 and case.status == CaseStatus.INVESTIGATING
        assert await session.scalar(select(func.count()).select_from(CaseEvent)) == 2


async def test_outer_rollback_removes_case_counter_and_audit(sessions, actors):
    async with sessions() as session:
        await CaseService(session, actors[0]).create_case(CaseDetails(title="Never committed"))
        await session.rollback()
    async with sessions.begin() as session:
        assert await session.scalar(select(func.count()).select_from(Case)) == 0
        assert await session.scalar(select(func.count()).select_from(CaseEvent)) == 0
        created = await CaseService(session, actors[0]).create_case(CaseDetails(title="Committed"))
        assert created.display_id.endswith("000001")


async def test_actor_boundaries_and_note_author_ownership(sessions, actors):
    async with sessions.begin() as session:
        for actor in (actors[3], uuid4()):
            with pytest.raises(ActorNotAllowed):
                await CaseService(session, actor).create_case(CaseDetails(title="Blocked"))
        case = await CaseService(session, actors[0]).create_case(CaseDetails(title="Actor test"))
        case_id = case.id
        note = await CaseService(session, actors[0]).add_note(
            case_id, 1, NoteInput(body="Owned note")
        )
        with pytest.raises(ActorNotAllowed):
            await CaseService(session, actors[1]).edit_note(
                case_id, 2, note.id, NoteInput(body="Other author"), "Blocked change"
            )
        with pytest.raises(ActorNotAllowed):
            await CaseService(session, actors[2]).transition(
                case_id,
                2,
                Transition(
                    status="resolved", disposition="false_positive", reason="Blocked automation"
                ),
            )
        await CaseService(session, actors[0]).transition(
            case_id, 2, Transition(status="investigating", reason="Analyst begins review")
        )
        with pytest.raises(ActorNotAllowed):
            await CaseService(session, actors[2]).transition(
                case_id,
                3,
                Transition(
                    status="resolved", disposition="false_positive", reason="Blocked automation"
                ),
            )


async def test_many_to_many_links_unlink_relink_and_evidence_retention(sessions, actors):
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        first = await service.create_case(CaseDetails(title="First"))
        second = await service.create_case(CaseDetails(title="Second"))
        first_id, second_id = first.id, second.id
        alert = (await service.import_alert(alert_data())).alert
        await service.link_alert(first_id, 1, alert.id, LinkInput(reason="First relationship"))
        await service.link_alert(second_id, 1, alert.id, LinkInput(reason="Second relationship"))
        with pytest.raises(Conflict):
            await service.link_alert(
                first_id, 2, alert.id, LinkInput(reason="Duplicate relationship")
            )
        await service.unlink_alert(first_id, 2, alert.id, "Analyst corrected grouping")
        await service.link_alert(first_id, 3, alert.id, LinkInput(reason="Reattach after review"))
        evidence = await service.add_evidence(first_id, 4, evidence_data(), "Keep excerpt")
        await service.unlink_evidence(first_id, 5, evidence.id, "Exclude from active investigation")
    async with sessions.begin() as session:
        assert await session.scalar(select(func.count()).select_from(CaseAlert)) == 2
        retained = await session.scalar(select(Evidence))
        assert retained.unlinked_at is not None and retained.snapshot == evidence_data().snapshot
        actions = set(await session.scalars(select(CaseEvent.action)))
        assert {"alert_linked", "alert_unlinked", "evidence_linked", "evidence_unlinked"} <= actions


async def test_audit_is_immutable_even_for_owner_and_runtime_is_restricted(
    sessions, actors, database
):
    async with sessions.begin() as session:
        await CaseService(session, actors[0]).create_case(CaseDetails(title="Protected history"))
    for statement in (
        "UPDATE case_events SET reason = 'tampered'",
        "DELETE FROM case_events",
        "TRUNCATE case_events",
        "CREATE TABLE forbidden (id integer)",
        "UPDATE alembic_version SET version_num = 'tampered'",
    ):
        with pytest.raises(DBAPIError):
            async with sessions.begin() as session:
                await session.execute(text(statement))
    owner_url = (
        database[0].database_url.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    for statement in (
        "UPDATE case_events SET reason = 'tampered'",
        "DELETE FROM case_events",
        "TRUNCATE case_events",
    ):
        with pytest.raises(psycopg.Error):
            with psycopg.connect(owner_url) as connection:
                connection.execute(statement)


async def test_database_rejects_unaudited_edits_and_immutable_identity(sessions, actors):
    async with sessions.begin() as session:
        case = await CaseService(session, actors[0]).create_case(
            CaseDetails(title="Protected case")
        )
        case_id = case.id
    for changes in (
        {"title": "Unaudited"},
        {"display_id": "SF-2026-999999"},
        {"status": "closed"},
        {"disposition": "false_positive"},
    ):
        with pytest.raises(DBAPIError):
            async with sessions.begin() as session:
                await session.execute(update(Case).where(Case.id == case_id).values(**changes))
    async with sessions.begin() as session:
        assert (await session.get(Case, case_id)).title == "Protected case"


async def test_evidence_hash_and_note_provenance_cannot_be_overwritten(sessions, actors):
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        case = await service.create_case(CaseDetails(title="Provenance"))
        note = await service.add_note(case.id, 1, NoteInput(body="Retained"))
        evidence = await service.add_evidence(case.id, 2, evidence_data(), "Preserve")
        note_id, evidence_id = note.id, evidence.id
    for model, target, changes in (
        (CaseNote, note_id, {"body": "Unrecorded rewrite", "revision": 2}),
        (CaseNote, note_id, {"author_id": actors[1]}),
        (Evidence, evidence_id, {"snapshot": "Rewritten"}),
        (Evidence, evidence_id, {"snapshot_sha256": "0" * 64}),
    ):
        with pytest.raises(DBAPIError):
            async with sessions.begin() as session:
                await session.execute(update(model).where(model.id == target).values(**changes))


def test_empty_database_upgrade_downgrade_and_rerun(database):
    _, _, config = database
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "0001_empty_baseline")
    command.upgrade(config, "head")
    command.check(config)


def test_nonempty_downgrade_refuses_data_loss(database):
    owner = database[0]
    url = owner.database_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(url) as connection:
        connection.execute("INSERT INTO case_number_counters VALUES (2026, 1)")
    with pytest.raises(DBAPIError):
        command.downgrade(database[2], "0001_empty_baseline")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT last_value FROM case_number_counters").fetchone() == (1,)


async def test_seed_is_idempotent_and_does_not_overwrite_analyst_changes(sessions):
    async with sessions.begin() as session:
        case = await seed_demo(session)
        case_id, actor_id = case.id, case.created_by
        await CaseService(session, actor_id).update_details(
            case_id, 4, CaseDetails(title="Analyst revised synthetic case"), "Retain analyst edits"
        )
    async with sessions.begin() as session:
        case = await seed_demo(session)
        assert case.id == case_id and case.title == "Analyst revised synthetic case"
        assert case.version == 5
        assert await session.scalar(select(func.count()).select_from(Case)) == 1
        assert await session.scalar(select(func.count()).select_from(Alert)) == 1
        assert await session.scalar(select(func.count()).select_from(CaseEvent)) == 5


async def test_child_audit_is_required_even_for_structurally_valid_note_edit(sessions, actors):
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        case = await service.create_case(CaseDetails(title="Child audit protection"))
        note = await service.add_note(case.id, 1, NoteInput(body="Original"))
        note_id = note.id
    with pytest.raises(DBAPIError):
        async with sessions.begin() as session:
            await session.execute(
                update(CaseNote)
                .where(CaseNote.id == note_id)
                .values(body="Unaudited", revision=2, edited_at=func.now())
            )
    async with sessions.begin() as session:
        assert (await session.get(CaseNote, note_id)).body == "Original"


async def test_case_scoping_closed_edit_guard_and_reference_only_evidence(sessions, actors):
    async with sessions.begin() as session:
        service = CaseService(session, actors[0])
        first = await service.create_case(CaseDetails(title="First"))
        second = await service.create_case(CaseDetails(title="Second"))
        first_id, second_id = first.id, second.id
        note = await service.add_note(first_id, 1, NoteInput(body="Case-specific note"))
        evidence = await service.add_evidence(
            first_id, 2, evidence_data(snapshot=None), "Reference only"
        )
        assert evidence.snapshot_sha256 is None
        note_id, evidence_id = note.id, evidence.id
        with pytest.raises(NotFound):
            await service.edit_note(second_id, 1, note_id, NoteInput(body="Wrong case"), "Blocked")
        with pytest.raises(NotFound):
            await service.unlink_evidence(second_id, 1, evidence_id, "Wrong case")
        await service.transition(second_id, 1, Transition(status="triaging", reason="Triage"))
        await service.transition(
            second_id,
            2,
            Transition(status="resolved", disposition="inconclusive", reason="Reviewed"),
        )
        await service.transition(second_id, 3, Transition(status="closed", reason="Complete"))
        with pytest.raises(InvalidTransition):
            await service.update_details(
                second_id, 4, CaseDetails(title="Closed rewrite"), "Blocked"
            )
