"""phase 1 domain persistence

Revision ID: 0002_domain_persistence
Revises: 0001_empty_baseline
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_domain_persistence"
down_revision = "0001_empty_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_number_counters",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("last_value BETWEEN 1 AND 999999", name="ck_case_counter_value"),
        sa.CheckConstraint("year BETWEEN 1 AND 9999", name="ck_case_counter_year"),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("handle", sa.String(length=128), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "human", "service", name="actor_kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("auth_source", sa.String(length=64), server_default="local", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(handle)) > 0", name="ck_users_handle"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handle"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=256), nullable=False),
        sa.Column("provider_scope", sa.String(length=256), nullable=False),
        sa.Column("external_alert_id", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="alert_severity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("imported_by", sa.Uuid(), nullable=False),
        sa.Column("source_ref", sa.String(length=2048), nullable=False),
        sa.Column("rule_id", sa.String(length=256), nullable=True),
        sa.Column("host", sa.String(length=256), nullable=True),
        sa.Column("user_name", sa.String(length=256), nullable=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint(
            "length(trim(provider)) > 0 AND length(trim(provider_scope)) > 0 "
            "AND length(trim(external_alert_id)) > 0 AND length(trim(title)) > 0 "
            "AND length(trim(source_ref)) > 0",
            name="ck_alerts_nonblank",
        ),
        sa.CheckConstraint("octet_length(summary) <= 8192", name="ck_alerts_summary_bytes"),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_scope", "external_alert_id", name="uq_alert_source"
        ),
    )
    op.create_index("ix_alerts_observed_at", "alerts", ["observed_at"], unique=False)
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "low",
                "medium",
                "high",
                "critical",
                name="case_severity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "new",
                "triaging",
                "investigating",
                "resolved",
                "closed",
                name="case_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "disposition",
            sa.Enum(
                "true_positive",
                "benign_positive",
                "false_positive",
                "inconclusive",
                name="case_disposition",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("assigned_to", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status IN ('resolved', 'closed') AND disposition IS NOT NULL) OR "
            "(status NOT IN ('resolved', 'closed') AND disposition IS NULL)",
            name="ck_cases_disposition",
        ),
        sa.CheckConstraint("display_id ~ '^SF-[0-9]{4}-[0-9]{6}$'", name="ck_cases_display_id"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_cases_title"),
        sa.CheckConstraint("octet_length(summary) <= 8192", name="ck_cases_summary_bytes"),
        sa.CheckConstraint("version > 0", name="ck_cases_version"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_id"),
    )
    op.create_index("ix_cases_assigned_to", "cases", ["assigned_to"], unique=False)
    op.create_index("ix_cases_status_updated", "cases", ["status", "updated_at"], unique=False)
    op.create_table(
        "case_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("linked_by", sa.Uuid(), nullable=False),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.CheckConstraint(
            "method IN ('manual','synthetic','correlation')", name="ck_case_alert_method"
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_case_alert_reason"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["linked_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "alert_id", name="uq_case_alert"),
    )
    op.create_index("ix_case_alerts_alert_id", "case_alerts", ["alert_id"], unique=False)
    op.create_table(
        "case_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_handle", sa.String(length=128), nullable=False),
        sa.Column(
            "actor_kind",
            sa.Enum(
                "human",
                "service",
                name="event_actor_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column(
            "before", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "after", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "transaction_id",
            sa.BigInteger(),
            server_default=sa.text("txid_current()"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("case_version > 0", name="ck_case_events_version"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_case_events_reason"),
        sa.CheckConstraint(
            "octet_length(before::text) <= 65536 AND octet_length(after::text) <= 65536",
            name="ck_case_events_payload_bytes",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "case_version", name="uq_case_event_version"),
    )
    op.create_index("ix_case_events_actor", "case_events", ["actor_id"], unique=False)
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(trim(body)) > 0 AND octet_length(body) <= 16384", name="ck_case_notes_body"
        ),
        sa.CheckConstraint("revision > 0", name="ck_case_notes_revision"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_case_notes_case_created", "case_notes", ["case_id", "created_at"], unique=False
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=256), nullable=False),
        sa.Column("provider_scope", sa.String(length=256), nullable=False),
        sa.Column("source_event_id", sa.String(length=256), nullable=False),
        sa.Column("source_ref", sa.String(length=2048), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acquired_by", sa.Uuid(), nullable=False),
        sa.Column(
            "sensitivity",
            sa.Enum(
                "synthetic",
                "internal",
                "restricted",
                name="evidence_sensitivity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=True),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(snapshot IS NULL AND snapshot_sha256 IS NULL) OR "
            "(snapshot IS NOT NULL AND snapshot_sha256 IS NOT NULL AND "
            "snapshot_sha256 = encode(sha256(convert_to(snapshot, 'UTF8')), 'hex'))",
            name="ck_evidence_snapshot_hash",
        ),
        sa.CheckConstraint(
            "(unlinked_at IS NULL AND unlinked_by IS NULL) OR "
            "(unlinked_at IS NOT NULL AND unlinked_by IS NOT NULL)",
            name="ck_evidence_unlinked",
        ),
        sa.CheckConstraint(
            "length(trim(provider)) > 0 AND length(trim(provider_scope)) > 0 "
            "AND length(trim(source_event_id)) > 0 AND length(trim(source_ref)) > 0",
            name="ck_evidence_nonblank",
        ),
        sa.CheckConstraint("octet_length(snapshot) <= 16384", name="ck_evidence_snapshot_bytes"),
        sa.ForeignKeyConstraint(["acquired_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unlinked_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_case_observed", "evidence", ["case_id", "observed_at"], unique=False
    )
    create_guards()


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM users) OR EXISTS (SELECT 1 FROM cases)
                OR EXISTS (SELECT 1 FROM alerts) OR EXISTS (SELECT 1 FROM case_number_counters) THEN
                RAISE EXCEPTION 'Refusing to drop nonempty domain schema; restore a backup instead';
            END IF;
        END $$
    """)
    drop_guards()
    op.drop_index("ix_evidence_case_observed", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_case_notes_case_created", table_name="case_notes")
    op.drop_table("case_notes")
    op.drop_index("ix_case_events_actor", table_name="case_events")
    op.drop_table("case_events")
    op.drop_index("ix_case_alerts_alert_id", table_name="case_alerts")
    op.drop_table("case_alerts")
    op.drop_index("ix_cases_status_updated", table_name="cases")
    op.drop_index("ix_cases_assigned_to", table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_alerts_observed_at", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("users")
    op.drop_table("case_number_counters")


def create_guards() -> None:
    op.execute("""
        CREATE FUNCTION ate_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Retained records cannot be modified or deleted';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER case_events_immutable BEFORE UPDATE OR DELETE ON case_events
        FOR EACH ROW EXECUTE FUNCTION ate_reject_mutation()
    """)
    op.execute("""
        CREATE TRIGGER case_events_no_truncate BEFORE TRUNCATE ON case_events
        FOR EACH STATEMENT EXECUTE FUNCTION ate_reject_mutation()
    """)
    op.execute("""
        CREATE FUNCTION ate_guard_case() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.display_id IS DISTINCT FROM OLD.display_id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
                RAISE EXCEPTION 'Case identity and provenance are immutable';
            END IF;
            IF NEW.version < OLD.version OR NEW.version > OLD.version + 1 THEN
                RAISE EXCEPTION 'Invalid case version';
            END IF;
            IF NEW.status <> OLD.status AND NOT (
                (OLD.status = 'new' AND NEW.status IN ('triaging', 'investigating')) OR
                (OLD.status = 'triaging' AND NEW.status IN ('investigating', 'resolved')) OR
                (OLD.status = 'investigating' AND NEW.status = 'resolved') OR
                (OLD.status = 'resolved' AND NEW.status IN ('closed', 'investigating')) OR
                (OLD.status = 'closed' AND NEW.status = 'investigating')
            ) THEN
                RAISE EXCEPTION 'Invalid case transition';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER cases_guard BEFORE UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION ate_guard_case()
    """)
    op.execute("""
        CREATE TRIGGER cases_no_delete BEFORE DELETE ON cases
        FOR EACH ROW EXECUTE FUNCTION ate_reject_mutation()
    """)
    op.execute("""
        CREATE FUNCTION ate_require_case_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM case_events WHERE case_id = NEW.id
                AND case_version = NEW.version AND transaction_id = txid_current()
            ) THEN
                RAISE EXCEPTION 'Case mutation requires an audit event in the same transaction';
            END IF;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER cases_require_audit AFTER INSERT OR UPDATE ON cases
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ate_require_case_audit()
    """)
    op.execute("""
        CREATE FUNCTION ate_require_child_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            row_data jsonb;
            expected_action text;
        BEGIN
            IF TG_OP = 'DELETE' THEN row_data := to_jsonb(OLD);
            ELSE row_data := to_jsonb(NEW); END IF;
            IF TG_TABLE_NAME = 'case_alerts' AND TG_OP = 'INSERT' THEN
                expected_action := 'alert_linked';
            ELSIF TG_TABLE_NAME = 'case_alerts' AND TG_OP = 'DELETE' THEN
                expected_action := 'alert_unlinked';
            ELSIF TG_TABLE_NAME = 'case_notes' AND TG_OP = 'INSERT' THEN
                expected_action := 'note_added';
            ELSIF TG_TABLE_NAME = 'case_notes' AND TG_OP = 'UPDATE' THEN
                expected_action := 'note_edited';
            ELSIF TG_TABLE_NAME = 'evidence' AND TG_OP = 'INSERT' THEN
                expected_action := 'evidence_linked';
            ELSIF TG_TABLE_NAME = 'evidence' AND TG_OP = 'UPDATE' THEN
                expected_action := 'evidence_unlinked';
            ELSE
                RAISE EXCEPTION 'Unsupported case child mutation';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM case_events WHERE case_id = (row_data->>'case_id')::uuid
                AND subject_id = (row_data->>'id')::uuid AND action = expected_action
                AND transaction_id = txid_current()
            ) THEN
                RAISE EXCEPTION 'Case child mutation requires an audit event';
            END IF;
            RETURN NULL;
        END $$
    """)
    for table in ("case_alerts", "case_notes", "evidence"):
        op.execute(f"""
            CREATE CONSTRAINT TRIGGER {table}_require_audit
            AFTER INSERT OR UPDATE OR DELETE ON {table} DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION ate_require_child_audit()
        """)
    op.execute("""
        CREATE FUNCTION ate_guard_note() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id <> OLD.id OR NEW.case_id <> OLD.case_id
                OR NEW.author_id <> OLD.author_id OR NEW.created_at <> OLD.created_at
                OR NEW.revision <> OLD.revision + 1 OR NEW.edited_at IS NULL THEN
                RAISE EXCEPTION 'Invalid note revision or provenance';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER case_notes_guard BEFORE UPDATE ON case_notes
        FOR EACH ROW EXECUTE FUNCTION ate_guard_note()
    """)
    op.execute("""
        CREATE FUNCTION ate_guard_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'unlinked_at' - 'unlinked_by') IS DISTINCT FROM
                (to_jsonb(OLD) - 'unlinked_at' - 'unlinked_by')
                OR OLD.unlinked_at IS NOT NULL
                OR NEW.unlinked_at IS NULL OR NEW.unlinked_by IS NULL THEN
                RAISE EXCEPTION 'Evidence content and provenance are immutable';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER evidence_guard BEFORE UPDATE ON evidence
        FOR EACH ROW EXECUTE FUNCTION ate_guard_evidence()
    """)


def drop_guards() -> None:
    for trigger, table in (
        ("case_events_immutable", "case_events"),
        ("case_events_no_truncate", "case_events"),
        ("cases_guard", "cases"),
        ("cases_no_delete", "cases"),
        ("cases_require_audit", "cases"),
        ("case_notes_guard", "case_notes"),
        ("evidence_guard", "evidence"),
        *((f"{table}_require_audit", table) for table in ("case_alerts", "case_notes", "evidence")),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
    for function in (
        "ate_reject_mutation",
        "ate_guard_case",
        "ate_require_case_audit",
        "ate_require_child_audit",
        "ate_guard_note",
        "ate_guard_evidence",
    ):
        op.execute(f"DROP FUNCTION {function}()")
