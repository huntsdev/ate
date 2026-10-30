from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from sentinelforge.domains.types import CaseStatus, Disposition, Sensitivity, Severity

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
SourceRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    @field_validator("*")
    @classmethod
    def no_null_bytes(cls, value: Any) -> Any:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("text must not contain null bytes")
        return value


def bounded_summary(value: str) -> str:
    if len(value.encode("utf-8")) > 8192:
        raise ValueError("summary exceeds 8192 UTF-8 bytes")
    return value


class CaseDetails(Input):
    title: ShortText
    severity: Severity = Severity.MEDIUM
    summary: str = Field(default="", max_length=8192)

    _bounded_summary = field_validator("summary")(bounded_summary)


class Transition(Input):
    status: CaseStatus
    disposition: Disposition | None = None
    reason: Reason


class AlertInput(Input):
    provider: ShortText
    provider_scope: ShortText
    external_alert_id: ShortText
    title: ShortText
    severity: Severity
    observed_at: AwareDatetime
    source_ref: SourceRef
    rule_id: ShortText | None = None
    host: ShortText | None = None
    user_name: ShortText | None = None
    summary: str = Field(default="", max_length=8192)

    _bounded_summary = field_validator("summary")(bounded_summary)


class NoteInput(Input):
    body: str = Field(min_length=1, max_length=16384)

    @field_validator("body")
    @classmethod
    def bounded_body(cls, value: str) -> str:
        if not value.strip() or len(value.encode("utf-8")) > 16384:
            raise ValueError("note must contain text within 16384 UTF-8 bytes")
        return value


class EvidenceInput(Input):
    provider: ShortText
    provider_scope: ShortText
    source_event_id: ShortText
    source_ref: SourceRef
    observed_at: AwareDatetime
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    snapshot: str | None = Field(default=None, max_length=16384)

    @field_validator("snapshot")
    @classmethod
    def bounded_snapshot(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 16384:
            raise ValueError("snapshot exceeds 16384 UTF-8 bytes")
        return value


class LinkInput(Input):
    reason: Reason
    method: Annotated[str, StringConstraints(pattern=r"^(manual|synthetic|correlation)$")] = (
        "manual"
    )
