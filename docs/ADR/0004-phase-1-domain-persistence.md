# ADR 0004: Phase 1 domain persistence and auditability

Status: adopted under the user's explicit instruction to start Phase 1 on
2026-10-28. HTTP case workflows and the investigation UI remain Phase 2.

## Decisions

- Keep SQLAlchemy mappings in `sentinelforge/db/models.py`, PostgreSQL-specific
  allocation/deduplication in `db/repositories.py`, and validation/rules/commands
  in `domains/cases/`. Services take an explicit actor ID and correlation UUID;
  callers own the outer transaction. Each command uses a savepoint so a caught
  failure cannot leave a version claim or partial child write behind.
- Use application-generated UUIDs. Allocate `SF-YYYY-NNNNNN` display IDs from
  a yearly PostgreSQL counter using atomic upsert/returning. The UTC database
  transaction year determines the prefix. Allocation rolls back with creation;
  committed IDs are immutable and never reused. The yearly ceiling is 999,999;
  exhaustion fails rather than producing duplicate or malformed IDs.
- Use portable string enums with PostgreSQL check constraints. Resolution
  requires a human disposition; closing retains it; reopening clears it.
  Implement the architecture's transition graph in pure rules and a database
  guard. Service actors cannot resolve/close cases or write analyst notes.
  Notes can be edited only by their active human author. Closed cases must be
  reopened before other edits. These are internal service boundaries, not an
  authentication/RBAC implementation.
- Every successful case command claims an expected positive version using
  `UPDATE ... WHERE id = ... AND version = ... RETURNING`. This serializes
  changes to notes, links, evidence, assignments, details and status through
  the same case version. A stale version raises a recoverable conflict.
- Store one append-only event per case version. Capture actor ID, handle and
  kind, action, subject, reason, previous/new state, correlation ID, timestamp
  and PostgreSQL transaction ID. Note revisions retain their text in these
  events. PostgreSQL deferred triggers require matching audit records in the
  same transaction for case and child mutations. Separate triggers reject
  audit updates/deletes/truncation, case deletion and identity changes,
  unsupported note revisions, and evidence-content replacement.
- Source uniqueness is exactly `(provider, provider_scope, external_alert_id)`.
  Phase 1 imports are first-write-wins with a `created` result. Replays return
  the existing row; metadata refresh semantics belong to Phase 3. Alerts can
  link to multiple cases. Removing a link retains its provenance in audit;
  removing evidence marks it unlinked while retaining its source and snapshot.
- Store curated text only: alert/case summaries up to 8 KiB UTF-8; notes and
  optional evidence snapshots up to 16 KiB UTF-8. Audit before/after JSONB
  payloads each have a 64 KiB serialized limit. Evidence snapshots have a
  SHA-256 hash verified in Python and by a database constraint. Event and
  acquisition/import times are separate timezone-aware fields. References and
  text are untrusted data; nothing fetches, renders as HTML, or executes them.
- No automatic deletion, redaction claim, or raw telemetry storage. Retain
  notes, evidence and history through restarts; sensitivity is recorded as
  `synthetic`, `internal` or `restricted`. Automated redaction, retention,
  exports and tested backups remain required before real sensitive data.
- Add revision `0002_domain_persistence` after the original empty baseline.
  Its downgrade is permitted only when domain data/counters are empty; it
  refuses destructive removal of an existing case history.

## Database privileges

The migration container alone receives the owner login. It applies migrations
then provisions a separate `ate_app` login with a different password, no
superuser/database/role creation privileges, no inherited roles, and explicit
table grants. API/worker containers receive only this runtime login. It can
read/insert audit events but cannot update/delete/truncate them or write
Alembic revision state. It cannot create schema objects. Alert imports and
case links have select/insert access; only links can be deleted.

The ignored local `.env` receives a generated application password during this
implementation. Fresh installations set both example passwords. Bootstrap
reruns update the application password and grants without resetting volumes.
The owner password for an existing PostgreSQL volume is not changed by editing
`.env`. Database owners/superusers can deliberately alter schema/disable
triggers; this is audit protection for application operations, not protection
against a malicious database administrator. Runtime SQL access and actor IDs
are trusted internal inputs; Phase 2 must bind actor identity on the server.

## Validation

Use real PostgreSQL 17 for migrations, hash constraints, transaction rollback,
concurrent allocation/import/editing, role boundaries, audit rejection, note
history, and evidence retention. SQLite is not a substitute for these checks.
`scripts/test-backend.ps1` starts a disposable loopback-only database and runs
the full suite. CI supplies its own disposable PostgreSQL service.
`scripts/test-persistence.ps1` migrates/seeds a uniquely named database and
verifies the complete graph after Compose down/up without removing volumes.
