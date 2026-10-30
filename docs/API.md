# Implemented API through Phase 2

FastAPI/Pydantic is the contract authority. The checked-in
[OpenAPI document](../packages/contracts/openapi.json) generates
[frontend types](../apps/web/src/lib/api.generated.ts). `/docs` serves the API
reference. See [ADR 0005](ADR/0005-phase-2-local-case-workspace.md) for the local
access, transaction and UI decisions.

## Local identity and request protection

The deployment is loopback single-user development. Business requests use the
server-owned `local-analyst`; clients cannot supply an audit actor. Database
bootstrap provisions this identity without overwriting/reactivating a conflicting
record. Formal authentication/RBAC is required before LAN or multiuser access.

`GET /api/v1/session` returns `{mode: "local_single_user", actor, csrf_token}`.
Unsafe methods require both an allowed `Origin` and `X-ATE-CSRF` from that
response. Tokens rotate on API restart and must not be placed in URLs or logs.
The frontend holds its token in memory and requires an explicit session reload
before retrying a rejected write. OpenAPI documents the write-token header.

Only `127.0.0.1`/`localhost` Host names and loopback browser origins are accepted.
Compose generates the allowed origins from the configured web/API ports and
the local source-test/dev ports 4173/5173. Cross-origin CORS access is not enabled.
The API enforces a 64 KiB request-body ceiling before parsing. This local mode
does not authenticate different operating-system users or defend against
malicious software already running as the local user.

Responses include server-generated `X-Correlation-ID`, `Cache-Control: no-store`,
and content/frame restrictions. Validation/database errors omit input values,
credentials and database exception details.

## Routes

All paths below use the `/api/v1` prefix. Lists return
`{items, total, limit, offset}` unless stated otherwise.

| Method / path | Behavior |
| --- | --- |
| `GET /health`, `/health/live` | Process check: `alive`, `service: ate`, `phase: 2`; no network probes |
| `GET /health/ready` | PostgreSQL/Redis checks; 200 `ready` or 503 `not_ready` |
| `GET /session` | Local actor and write token |
| `GET /users` | Up to 100 active human assignment candidates; JSON array |
| `GET /dashboard` | Database counts, open severity mix, status totals and six recent cases |
| `GET /cases` | Search/filter/sort/page cases |
| `POST /cases` | Create case (201), optionally link `alert_id` in the same transaction |
| `GET /cases/{case_id}` | Case details, source labels, owner handle and permitted next statuses |
| `PATCH /cases/{case_id}` | Update supplied title/summary/severity with reason and version |
| `POST /cases/{case_id}/assignment` | Assign/unassign an active human owner |
| `POST /cases/{case_id}/transitions` | Validate lifecycle change and analyst disposition |
| `GET /alerts` | Search/filter/sort/page normalized alert metadata |
| `POST /alerts` | Explicit synthetic import; 201 on insertion, 200 on replay; `{alert, created}` |
| `GET /alerts/{alert_id}` | Alert plus its most recent 25 linked cases; total link count retained |
| `GET /cases/{case_id}/alerts` | Linked alerts with link reason, method, actor and time |
| `POST /cases/{case_id}/alerts` | Link an existing alert with a reason (201) |
| `DELETE /cases/{case_id}/alerts/{alert_id}` | Unlink with reason; original alert and audit provenance remain |
| `GET /cases/{case_id}/notes` | Notes with author handles, current body/revision and timestamps |
| `POST /cases/{case_id}/notes` | Add local analyst note (201) |
| `PATCH /cases/{case_id}/notes/{note_id}` | Author-only edit with reason; old body retained in audit |
| `GET /cases/{case_id}/evidence` | Evidence references/snapshots, hashes, acquisition provenance and unlinked records |
| `POST /cases/{case_id}/evidence` | Preserve bounded evidence or reference only (201) |
| `DELETE /cases/{case_id}/evidence/{evidence_id}` | Mark evidence unlinked with reason; retained content stays immutable |
| `GET /cases/{case_id}/timeline` | Audit events ordered by descending committed case version |

There is no case deletion route: close/reopen retains investigation history.
No provider-ingestion, model, simulation or detection-approval routes exist.

## Queries and writes

Case lists accept `q` (title/display ID/summary), `status`, `severity`, `owner`
(UUID), `unassigned`, `provider`, `sort=updated_at|created_at|severity`, and
`order=asc|desc`. Source matching includes linked alerts without duplicating
case rows. Alert lists accept `q` (title/external ID/host/user), `severity`,
`provider`, `linked`, `sort=observed_at|imported_at|severity`, and `order`.
Search treats `%` and `_` literally. Sort keys are allowlisted and ties use UUID.

Default page size is 25 (1–100); offsets are bounded to 0–100000. Audit pages
default to 20 and cap at 50. Notes and linked alerts use descending creation/
link time; evidence uses descending acquisition time. Related cases in alert
detail are bounded rather than an unbounded nested collection.

All case mutations after creation require `expected_version` (positive integer;
booleans are rejected). Detail patches require at least one non-null changed
detail plus `reason`; status/disposition/actor fields are forbidden there.
Assignment uses nullable `assignee_id`; transitions use `status`, optional
`disposition`, and `reason`. A resolution requires an explicit analyst
disposition; closing retains it and reopening clears the current value.

Creation/details/assignment/transitions return authoritative `CaseOut`.
Child mutations return `{case: CaseOut, subject_id}` with the resulting version;
GET the relevant child list to inspect its contents. Notes carry `body`; evidence
uses the Phase 1 bounded provenance schema. For unlink, DELETE has a JSON body
containing `expected_version` and `reason`.

Case creation with alert linkage is atomic. Function-scoped transaction
dependencies finish commit/deferred audit checks before sending success. A
failed validation, missing reference or stale version does not partially create
a case or advance its version. There are no automatic mutation retries.

Manual imports accept only provider `synthetic`, `.invalid` hosts when provided,
and `synthetic://` references. Repeated provider/scope/external-ID keys return the
first saved alert. Snapshot text/source references remain untrusted inputs;
they are never executed or fetched by these routes. See
[DATA-MODEL.md](DATA-MODEL.md) for byte budgets and retention invariants.

## Problem details and availability

Failures use `application/problem+json` with `type`, `title`, `status`, `detail`,
`code`, `correlation_id`, and a bounded `errors[{field,message}]` list.

| Status | Examples |
| --- | --- |
| 400 | `invalid_host` |
| 403 | `invalid_origin`, `csrf_invalid`, `actor_not_allowed` |
| 404 | `not_found` |
| 409 | `version_conflict`, `association_conflict`, `invalid_transition`, `data_conflict` |
| 413 | `request_too_large` |
| 422 | `validation_error`, `invalid_disposition`, `invalid_operation` |
| 503 | `storage_unavailable`, `local_actor_unavailable` |

The UI retains drafts on errors. A stale-version write is blocked until the
analyst explicitly reloads and reviews the latest case. Readiness executes
PostgreSQL `SELECT 1` and Redis `PING` concurrently under a configurable
per-probe deadline. Liveness remains available during dependency outages.
Elastic/Ollama health reports `not_enabled` without contacting either provider;
it does not describe whether a native host process is running.

## Regenerate contracts

From the repository root:

```powershell
uv run --directory apps/api --locked python ../../scripts/export_openapi.py
Set-Location apps/web
npm.cmd run contracts:generate
npm.cmd run contracts:check
Set-Location ../..
```

The exporter uses synthetic settings and never connects to PostgreSQL. Regenerate
both files after response/input/header changes; CI rejects drift. Never add
credentials or a live session token to generated artifacts.
