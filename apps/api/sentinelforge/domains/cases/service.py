"""Atomic case commands; the caller owns commit/rollback of the outer transaction."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelforge.db.models import Alert, Case, CaseAlert, CaseEvent, CaseNote, Evidence, User
from sentinelforge.db.repositories import ImportedAlert, Repository
from sentinelforge.domains.cases.rules import transition_disposition
from sentinelforge.domains.cases.schemas import (
    AlertInput,
    CaseDetails,
    EvidenceInput,
    LinkInput,
    NoteInput,
    Reason,
    Transition,
)
from sentinelforge.domains.errors import (
    ActorNotAllowed,
    Conflict,
    DomainError,
    InvalidTransition,
    NotFound,
)
from sentinelforge.domains.types import ActorKind, CaseStatus

reason_adapter = TypeAdapter(Reason)


def case_snapshot(case: Case, *, version: int | None = None) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "display_id": case.display_id,
        "title": case.title,
        "summary": case.summary,
        "severity": case.severity.value,
        "status": case.status.value,
        "disposition": case.disposition.value if case.disposition else None,
        "assigned_to": str(case.assigned_to) if case.assigned_to else None,
        "version": case.version if version is None else version,
    }


def note_snapshot(note: CaseNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "author_id": str(note.author_id),
        "body": note.body,
        "revision": note.revision,
    }


class CaseService:
    def __init__(self, session: AsyncSession, actor_id: UUID, correlation_id: UUID | None = None):
        self.session = session
        self.actor_id = actor_id
        self.correlation_id = correlation_id or uuid4()
        self.repository = Repository(session)

    async def _actor(self, *, human: bool = False) -> User:
        actor = await self.session.get(User, self.actor_id, populate_existing=True)
        if actor is None or not actor.is_active or (human and actor.kind != ActorKind.HUMAN):
            raise ActorNotAllowed(
                "An active human analyst is required" if human else "An active actor is required"
            )
        return actor

    @asynccontextmanager
    async def _edit(
        self, case_id: UUID, expected_version: int, *, human: bool = False, reopening: bool = False
    ) -> AsyncIterator[tuple[Case, User, dict[str, Any]]]:
        # A failed command rolls back its version claim and writes even if the
        # caller catches the domain error and continues the outer transaction.
        async with self.session.begin_nested():
            actor = await self._actor(human=human)
            case = await self.repository.claim_case(case_id, expected_version)
            if case.status == CaseStatus.CLOSED and not reopening:
                raise InvalidTransition("Reopen a closed case before editing")
            before = case_snapshot(case, version=case.version - 1)
            yield case, actor, before
            await self.session.flush()

    def _record(
        self,
        case: Case,
        actor: User,
        action: str,
        subject_id: UUID,
        reason: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        for payload in (before, after):
            if (
                payload is not None
                and len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 65536
            ):
                raise DomainError("Audit state exceeds the 64 KiB serialized storage budget")
        self.session.add(
            CaseEvent(
                case_id=case.id,
                case_version=case.version,
                actor_id=actor.id,
                actor_handle=actor.handle,
                actor_kind=actor.kind,
                action=action,
                subject_id=subject_id,
                reason=reason_adapter.validate_python(reason),
                before=before,
                after=after,
                correlation_id=self.correlation_id,
            )
        )

    async def create_case(self, data: CaseDetails, *, case_id: UUID | None = None) -> Case:
        async with self.session.begin_nested():
            actor = await self._actor()
            case = Case(
                id=case_id or uuid4(),
                display_id=await self.repository.allocate_display_id(),
                **data.model_dump(),
                status=CaseStatus.NEW,
                disposition=None,
                created_by=actor.id,
                version=1,
            )
            self.session.add(case)
            await self.session.flush()
            self._record(
                case,
                actor,
                "case_created",
                case.id,
                "Case created",
                None,
                {"case": case_snapshot(case)},
            )
            await self.session.flush()
        return case

    async def update_details(
        self, case_id: UUID, expected_version: int, data: CaseDetails, reason: str
    ) -> Case:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            case.title, case.summary, case.severity = data.title, data.summary, data.severity
            self._record(
                case,
                actor,
                "details_updated",
                case.id,
                reason,
                {"case": before},
                {"case": case_snapshot(case)},
            )
        return case

    async def assign(
        self, case_id: UUID, expected_version: int, assignee_id: UUID | None, reason: str
    ) -> Case:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            if assignee_id is not None:
                assignee = await self.session.get(User, assignee_id, populate_existing=True)
                if assignee is None or not assignee.is_active or assignee.kind != ActorKind.HUMAN:
                    raise ActorNotAllowed("Assignee must be an active human analyst")
            case.assigned_to = assignee_id
            self._record(
                case,
                actor,
                "case_assigned",
                case.id,
                reason,
                {"case": before},
                {"case": case_snapshot(case)},
            )
        return case

    async def transition(self, case_id: UUID, expected_version: int, data: Transition) -> Case:
        terminal = data.status in {CaseStatus.RESOLVED, CaseStatus.CLOSED}
        async with self._edit(case_id, expected_version, human=terminal, reopening=True) as (
            case,
            actor,
            before,
        ):
            case.disposition = transition_disposition(
                case.status, data.status, case.disposition, data.disposition
            )
            case.status = data.status
            self._record(
                case,
                actor,
                "status_changed",
                case.id,
                data.reason,
                {"case": before},
                {"case": case_snapshot(case)},
            )
        return case

    async def import_alert(self, data: AlertInput) -> ImportedAlert:
        async with self.session.begin_nested():
            actor = await self._actor()
            return await self.repository.import_alert(data, actor.id)

    async def link_alert(
        self, case_id: UUID, expected_version: int, alert_id: UUID, data: LinkInput
    ) -> CaseAlert:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            if await self.session.get(Alert, alert_id) is None:
                raise NotFound("Alert not found")
            if (
                await self.session.scalar(
                    select(CaseAlert.id).where(
                        CaseAlert.case_id == case_id, CaseAlert.alert_id == alert_id
                    )
                )
                is not None
            ):
                raise Conflict("Alert is already linked to this case")
            link = CaseAlert(
                id=uuid4(),
                case_id=case_id,
                alert_id=alert_id,
                linked_by=actor.id,
                method=data.method,
                reason=data.reason,
            )
            self.session.add(link)
            self._record(
                case,
                actor,
                "alert_linked",
                link.id,
                data.reason,
                {"case": before},
                {"case": case_snapshot(case), "alert_id": str(alert_id), "method": data.method},
            )
        return link

    async def unlink_alert(
        self, case_id: UUID, expected_version: int, alert_id: UUID, reason: str
    ) -> None:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            link = await self.session.scalar(
                select(CaseAlert).where(
                    CaseAlert.case_id == case_id, CaseAlert.alert_id == alert_id
                )
            )
            if link is None:
                raise NotFound("Case alert link not found")
            self._record(
                case,
                actor,
                "alert_unlinked",
                link.id,
                reason,
                {
                    "case": before,
                    "alert_id": str(alert_id),
                    "method": link.method,
                    "link_reason": link.reason,
                    "linked_by": str(link.linked_by),
                    "linked_at": link.linked_at.isoformat(),
                },
                {"case": case_snapshot(case)},
            )
            await self.session.delete(link)

    async def add_note(self, case_id: UUID, expected_version: int, data: NoteInput) -> CaseNote:
        async with self._edit(case_id, expected_version, human=True) as (case, actor, before):
            note = CaseNote(
                id=uuid4(), case_id=case_id, author_id=actor.id, body=data.body, revision=1
            )
            self.session.add(note)
            self._record(
                case,
                actor,
                "note_added",
                note.id,
                "Analyst note added",
                {"case": before},
                {"case": case_snapshot(case), "note": note_snapshot(note)},
            )
        return note

    async def edit_note(
        self, case_id: UUID, expected_version: int, note_id: UUID, data: NoteInput, reason: str
    ) -> CaseNote:
        async with self._edit(case_id, expected_version, human=True) as (case, actor, before):
            note = await self.session.scalar(
                select(CaseNote)
                .where(CaseNote.id == note_id, CaseNote.case_id == case_id)
                .execution_options(populate_existing=True)
            )
            if note is None:
                raise NotFound("Case note not found")
            if note.author_id != actor.id:
                raise ActorNotAllowed("Only the note author can edit it")
            old_note = note_snapshot(note)
            note.body, note.revision, note.edited_at = (
                data.body,
                note.revision + 1,
                datetime.now(UTC),
            )
            self._record(
                case,
                actor,
                "note_edited",
                note.id,
                reason,
                {"case": before, "note": old_note},
                {"case": case_snapshot(case), "note": note_snapshot(note)},
            )
        return note

    async def add_evidence(
        self, case_id: UUID, expected_version: int, data: EvidenceInput, reason: str
    ) -> Evidence:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            digest = (
                sha256(data.snapshot.encode("utf-8")).hexdigest()
                if data.snapshot is not None
                else None
            )
            evidence = Evidence(
                id=uuid4(),
                case_id=case_id,
                acquired_by=actor.id,
                **data.model_dump(),
                snapshot_sha256=digest,
            )
            self.session.add(evidence)
            self._record(
                case,
                actor,
                "evidence_linked",
                evidence.id,
                reason,
                {"case": before},
                {
                    "case": case_snapshot(case),
                    "evidence": {**data.model_dump(mode="json"), "snapshot_sha256": digest},
                },
            )
        return evidence

    async def unlink_evidence(
        self, case_id: UUID, expected_version: int, evidence_id: UUID, reason: str
    ) -> None:
        async with self._edit(case_id, expected_version) as (case, actor, before):
            evidence = await self.session.scalar(
                select(Evidence)
                .where(
                    Evidence.id == evidence_id,
                    Evidence.case_id == case_id,
                    Evidence.unlinked_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
            if evidence is None:
                raise NotFound("Linked evidence not found")
            evidence.unlinked_at, evidence.unlinked_by = datetime.now(UTC), actor.id
            self._record(
                case,
                actor,
                "evidence_unlinked",
                evidence.id,
                reason,
                {
                    "case": before,
                    "evidence_id": str(evidence.id),
                    "source_ref": evidence.source_ref,
                    "snapshot_sha256": evidence.snapshot_sha256,
                },
                {"case": case_snapshot(case), "unlinked_at": evidence.unlinked_at.isoformat()},
            )
