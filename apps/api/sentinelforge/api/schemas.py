from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from sentinelforge.domains.cases.schemas import (
    AlertInput,
    CaseDetails,
    EvidenceInput,
    Input,
    NoteInput,
    Reason,
    ShortText,
    Transition,
    bounded_summary,
)
from sentinelforge.domains.types import ActorKind, CaseStatus, Disposition, Sensitivity, Severity


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(Output):
    id: UUID
    handle: str
    kind: ActorKind
    is_active: bool


class LocalSession(BaseModel):
    mode: Literal["local_single_user"] = "local_single_user"
    actor: UserOut
    csrf_token: str


class CaseOut(Output):
    id: UUID
    display_id: str
    title: str
    summary: str
    severity: Severity
    status: CaseStatus
    disposition: Disposition | None
    assigned_to: UUID | None
    owner_handle: str | None = None
    created_by: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    sources: list[str] = []
    allowed_transitions: list[CaseStatus] = []


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class CasePage(Page[CaseOut]):
    pass


class AlertOut(Output):
    id: UUID
    provider: str
    provider_scope: str
    external_alert_id: str
    title: str
    severity: Severity
    observed_at: datetime
    imported_at: datetime
    source_ref: str
    rule_id: str | None
    host: str | None
    user_name: str | None
    summary: str
    linked_case_count: int = 0


class AlertPage(Page[AlertOut]):
    pass


class AlertDetail(AlertOut):
    cases: list[CaseOut]


class LinkedAlertOut(AlertOut):
    link_id: UUID
    linked_at: datetime
    linked_by: UUID
    reason: str
    method: str


class LinkedAlertPage(Page[LinkedAlertOut]):
    pass


class NoteOut(Output):
    id: UUID
    case_id: UUID
    author_id: UUID
    author_handle: str
    body: str
    revision: int
    created_at: datetime
    edited_at: datetime | None


class NotePage(Page[NoteOut]):
    pass


class EvidenceOut(Output):
    id: UUID
    case_id: UUID
    provider: str
    provider_scope: str
    source_event_id: str
    source_ref: str
    observed_at: datetime
    acquired_at: datetime
    acquired_by: UUID
    acquired_by_handle: str = ""
    sensitivity: Sensitivity
    snapshot: str | None
    snapshot_sha256: str | None
    unlinked_at: datetime | None
    unlinked_by: UUID | None


class EvidencePage(Page[EvidenceOut]):
    pass


class EventOut(Output):
    id: UUID
    case_id: UUID
    case_version: int
    actor_id: UUID
    actor_handle: str
    actor_kind: ActorKind
    action: str
    subject_id: UUID
    reason: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    correlation_id: UUID
    occurred_at: datetime


class EventPage(Page[EventOut]):
    pass


class Dashboard(BaseModel):
    open_cases: int
    total_cases: int
    unassigned_open_cases: int
    unlinked_alerts: int
    severity_counts: dict[Severity, int]
    status_counts: dict[CaseStatus, int]
    recent_cases: list[CaseOut]


class CreateCase(CaseDetails):
    alert_id: UUID | None = None


class Versioned(Input):
    expected_version: StrictInt = Field(ge=1)


class CasePatch(Versioned):
    title: ShortText | None = None
    summary: str | None = Field(default=None, max_length=8192)
    severity: Severity | None = None
    reason: Reason

    @field_validator("summary")
    @classmethod
    def check_summary(cls, value: str | None) -> str | None:
        return bounded_summary(value) if value is not None else None

    @model_validator(mode="after")
    def changes_required(self) -> Self:
        changes = self.model_fields_set & {"title", "summary", "severity"}
        if not changes or any(getattr(self, key) is None for key in changes):
            raise ValueError("Supply at least one non-null case detail")
        return self


class Assignment(Versioned):
    assignee_id: UUID | None
    reason: Reason


class TransitionCommand(Transition, Versioned):
    pass


class AddNote(NoteInput, Versioned):
    pass


class EditNote(AddNote):
    reason: Reason


class AlertLink(Versioned):
    alert_id: UUID
    reason: Reason


class Unlink(Versioned):
    reason: Reason


class AddEvidence(EvidenceInput, Versioned):
    reason: Reason


class CaseMutation(BaseModel):
    case: CaseOut
    subject_id: UUID


class SyntheticAlert(AlertInput):
    provider: Literal["synthetic"] = "synthetic"
    provider_scope: ShortText = "manual"
    source_ref: str = Field(default="synthetic://manual", min_length=1, max_length=2048)

    @field_validator("source_ref")
    @classmethod
    def synthetic_reference(cls, value: str) -> str:
        if not value.startswith("synthetic://"):
            raise ValueError("Manual development alerts require a synthetic reference")
        return value

    @field_validator("host")
    @classmethod
    def synthetic_host(cls, value: str | None) -> str | None:
        if value is not None and not value.endswith(".invalid"):
            raise ValueError("Synthetic hostnames must end in .invalid")
        return value


class AlertImport(BaseModel):
    alert: AlertOut
    created: bool
