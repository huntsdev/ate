# Phase 1 implementation and validation

This is the Phase 1 closeout record. The user has since authorized Phase 2;
current results are in [PHASE_2_STATUS.md](PHASE_2_STATUS.md).

Status: Phase 1 implementation and local acceptance criteria passed on
2026-10-28. The user explicitly authorized this phase. Changes have not been
committed/pushed; no new hosted CI result is claimed. Phase 2 was planned at
that closeout and is now implemented as recorded in its separate status file.

## Delivered

- Eight domain tables: users/service actors, yearly case counters, cases,
  alerts, case-alert links, notes, evidence and immutable audit events.
- Explicit Alembic revision `0002_domain_persistence` after the original empty
  baseline, with database constraints/indexes and audit/provenance guards.
  Downgrade refuses a nonempty domain schema.
- Typed input schemas and pure transition/disposition rules; transaction-scoped
  services for case creation/details, assignment, lifecycle changes, alert
  import/linking, notes/revisions and evidence retention/unlinking.
- Transaction-safe yearly IDs, concurrent source deduplication, expected-version
  conflicts, savepoint rollback, human-only dispositions/notes and author-only
  note edits. Case mutation and its audit event commit together.
- Separate migration-owner and restricted API/worker credentials. Generated an
  application password in the ignored `.env` without changing the existing
  owner password. Bootstrap applies schema/grants on existing volumes without
  a data reset, and checks password/role separation.
- Explicit idempotent synthetic demo seed, disposable PostgreSQL test runner,
  domain-graph restart probe, and CI PostgreSQL service for integration tests.
- Health now reports `phase: 1`; generated OpenAPI/frontend types and browser
  health fixtures are updated. The only HTTP routes remain health/readiness.

## Observed checks

| Check | Result |
| --- | --- |
| Backend suite | **79 passed**, no skips through `scripts/test-backend.ps1`: 63 non-integration checks and 16 real PostgreSQL integration checks |
| Concurrent persistence | Unique case IDs under concurrent creation; exactly one stored alert under repeated concurrent delivery; one winner and one conflict for concurrent stale edits |
| Lifecycle and actor rules | Transition matrix, invalid dispositions, inactive/unknown actors, service disposition rejection, note author boundary, case scoping and closed-case edit guard passed |
| Atomicity and history | Failed-command savepoints, complete outer rollback, preserved note revisions, reference-only evidence, retained unlinked evidence and serialization-budget rollback passed |
| Database enforcement | Immutable audit update/delete/truncate rejection, unaudited case/child rejection, immutable identity/evidence and restricted-runtime DDL/Alembic-write rejection passed |
| Migrations | Fresh-database upgrade, rerun, empty downgrade/re-upgrade, metadata drift check and nonempty-downgrade refusal passed |
| Source quality | Ruff lint/format and mypy (26 source files) passed; locked dependencies unchanged |
| API/contracts | OpenAPI export and generated TypeScript contract checks passed |
| Web quality | Formatting, lint, TypeScript and production build passed |
| Browser suite | **Eight passed**, covering desktop/mobile health, outages/recovery, malformed responses and accessibility |
| Existing deployment upgrade | Development images built and revision applied on the existing Phase 0 volume; migration bootstrap reran twice; API/worker use the restricted login |
| Actual restart persistence | `scripts/test-persistence.ps1 -Dev` migrated/seeded a dedicated synthetic database, recreated containers without deleting volumes, verified the complete graph/all nine audit events, and cleaned up that database |
| Real stack/browser | All five long-running services healthy; real migration-head/PostgreSQL/Redis/worker smoke passed; live browser smoke returned health 200/readiness 200 with no intercepted requests |
| Explicit demo | Seed executed twice through the actual restricted API login; both returned `SF-2026-000001` without creating duplicates |
| Repository checks | All 41 relative documentation links resolve; all PowerShell scripts parse; core/optional/dev Compose configurations and whitespace checks passed; `.env` remains ignored |

The backend retains one upstream Starlette TestClient deprecation warning;
all tests pass. Browser execution emitted existing Node color-environment
warnings without failures. Windows native async database checks use a selector
event loop for Psycopg compatibility; application containers run Linux.

Disposable integration containers and their test databases/roles were removed.
The restart probe's temporary database was removed, while normal application
volumes were preserved. The development deployment remains running at
`http://127.0.0.1:8080` with source reload and one persistent synthetic demo.

## Boundaries and remaining work

The status dashboard is still the Phase 0 shell. There are no case HTTP routes,
case screens, authentication sessions, provider ingestion, model calls, RAG or
simulation workflows. The internal actor ID is a trusted caller input; Phase 2
must bind it to server-side authentication/local-user context before exposing
business endpoints. No real telemetry or credentials were added to fixtures.

Optional Elastic/Kibana runtime, container-to-host Ollama routing/inference,
GPU benchmarking, and a new hosted CI run were not executed. The updated CI
definition supplies PostgreSQL and requires neither optional provider nor GPU.
The passing hosted run recorded in [PHASE_0_STATUS.md](PHASE_0_STATUS.md) covers
the previous baseline only.

See [DATA-MODEL.md](DATA-MODEL.md),
[ADR 0004](ADR/0004-phase-1-domain-persistence.md), and
[RUNBOOK.md](RUNBOOK.md) for invariants, tradeoffs, and repeatable commands.
