"""Phase 1 relational source of truth; tables are created only by Alembic."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sentinelforge.core.database import Base
from sentinelforge.domains.types import ActorKind, CaseStatus, Disposition, Sensitivity, Severity


def enum_type(enum: type, name: str) -> Enum:
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("length(trim(handle)) > 0", name="ck_users_handle"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    handle: Mapped[str] = mapped_column(String(128), unique=True)
    kind: Mapped[ActorKind] = mapped_column(enum_type(ActorKind, "actor_kind"))
    auth_source: Mapped[str] = mapped_column(String(64), default="local", server_default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseNumberCounter(Base):
    __tablename__ = "case_number_counters"
    __table_args__ = (
        CheckConstraint("year BETWEEN 1 AND 9999", name="ck_case_counter_year"),
        CheckConstraint("last_value BETWEEN 1 AND 999999", name="ck_case_counter_value"),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_cases_title"),
        CheckConstraint("octet_length(summary) <= 8192", name="ck_cases_summary_bytes"),
        CheckConstraint("display_id ~ '^SF-[0-9]{4}-[0-9]{6}$'", name="ck_cases_display_id"),
        CheckConstraint("version > 0", name="ck_cases_version"),
        CheckConstraint(
            "(status IN ('resolved', 'closed') AND disposition IS NOT NULL) OR "
            "(status NOT IN ('resolved', 'closed') AND disposition IS NULL)",
            name="ck_cases_disposition",
        ),
        Index("ix_cases_status_updated", "status", "updated_at"),
        Index("ix_cases_assigned_to", "assigned_to"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_id: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    severity: Mapped[Severity] = mapped_column(enum_type(Severity, "case_severity"))
    status: Mapped[CaseStatus] = mapped_column(enum_type(CaseStatus, "case_status"))
    disposition: Mapped[Disposition | None] = mapped_column(
        enum_type(Disposition, "case_disposition")
    )
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_scope", "external_alert_id", name="uq_alert_source"),
        CheckConstraint(
            "length(trim(provider)) > 0 AND length(trim(provider_scope)) > 0 "
            "AND length(trim(external_alert_id)) > 0 AND length(trim(title)) > 0 "
            "AND length(trim(source_ref)) > 0",
            name="ck_alerts_nonblank",
        ),
        CheckConstraint("octet_length(summary) <= 8192", name="ck_alerts_summary_bytes"),
        Index("ix_alerts_observed_at", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(256))
    provider_scope: Mapped[str] = mapped_column(String(256))
    external_alert_id: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))
    severity: Mapped[Severity] = mapped_column(enum_type(Severity, "alert_severity"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    imported_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    source_ref: Mapped[str] = mapped_column(String(2048))
    rule_id: Mapped[str | None] = mapped_column(String(256))
    host: Mapped[str | None] = mapped_column(String(256))
    user_name: Mapped[str | None] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")


class CaseAlert(Base):
    __tablename__ = "case_alerts"
    __table_args__ = (
        UniqueConstraint("case_id", "alert_id", name="uq_case_alert"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_case_alert_reason"),
        CheckConstraint(
            "method IN ('manual','synthetic','correlation')", name="ck_case_alert_method"
        ),
        Index("ix_case_alerts_alert_id", "alert_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"))
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id", ondelete="RESTRICT"))
    linked_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    method: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(1000))


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "length(trim(provider)) > 0 AND length(trim(provider_scope)) > 0 "
            "AND length(trim(source_event_id)) > 0 AND length(trim(source_ref)) > 0",
            name="ck_evidence_nonblank",
        ),
        CheckConstraint("octet_length(snapshot) <= 16384", name="ck_evidence_snapshot_bytes"),
        CheckConstraint(
            "(snapshot IS NULL AND snapshot_sha256 IS NULL) OR "
            "(snapshot IS NOT NULL AND snapshot_sha256 IS NOT NULL AND "
            "snapshot_sha256 = encode(sha256(convert_to(snapshot, 'UTF8')), 'hex'))",
            name="ck_evidence_snapshot_hash",
        ),
        CheckConstraint(
            "(unlinked_at IS NULL AND unlinked_by IS NULL) OR "
            "(unlinked_at IS NOT NULL AND unlinked_by IS NOT NULL)",
            name="ck_evidence_unlinked",
        ),
        Index("ix_evidence_case_observed", "case_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(256))
    provider_scope: Mapped[str] = mapped_column(String(256))
    source_event_id: Mapped[str] = mapped_column(String(256))
    source_ref: Mapped[str] = mapped_column(String(2048))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acquired_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    sensitivity: Mapped[Sensitivity] = mapped_column(enum_type(Sensitivity, "evidence_sensitivity"))
    snapshot: Mapped[str | None] = mapped_column(Text)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64))
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class CaseNote(Base):
    __tablename__ = "case_notes"
    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) > 0 AND octet_length(body) <= 16384", name="ck_case_notes_body"
        ),
        CheckConstraint("revision > 0", name="ck_case_notes_revision"),
        Index("ix_case_notes_case_created", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseEvent(Base):
    __tablename__ = "case_events"
    __table_args__ = (
        UniqueConstraint("case_id", "case_version", name="uq_case_event_version"),
        CheckConstraint("case_version > 0", name="ck_case_events_version"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_case_events_reason"),
        CheckConstraint(
            "octet_length(before::text) <= 65536 AND octet_length(after::text) <= 65536",
            name="ck_case_events_payload_bytes",
        ),
        Index("ix_case_events_actor", "actor_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"))
    case_version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_handle: Mapped[str] = mapped_column(String(128))
    actor_kind: Mapped[ActorKind] = mapped_column(enum_type(ActorKind, "event_actor_kind"))
    action: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str] = mapped_column(String(1000))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    correlation_id: Mapped[UUID] = mapped_column()
    transaction_id: Mapped[int] = mapped_column(BigInteger, server_default=text("txid_current()"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
