# Phase 2 implementation and validation

Status: Phase 2 implemented and locally validated on 2026-10-28. The user
authorized the case-management slice and then explicitly requested a complete,
distinctive modern enterprise-style UI redesign using shadcn components.
Phase 3 provider ingestion and later capabilities remain unimplemented.
Changes are uncommitted/unpushed; no new hosted CI pass is claimed.

## Delivered

- Database-backed operational overview, case and alert queues, search, filters,
  allowlisted sorting, bounded pagination and direct detail routes.
- A complete graphite/mint visual redesign: custom vector mark/favicon,
  operations navigation, compact tables, severity distribution, responsive
  layouts and a tabbed investigation workspace. Existing and CLI-generated
  shadcn components provide the controls, cards, dialogs, fields, selects,
  tabs, tables, loading skeletons and badges. No remote image/font is required.
- Browser case creation (standalone or atomically linked to an alert), synthetic
  alert import, association correction, preserved evidence/references/hashes,
  analyst notes/revisions, assignment, human disposition, closure, reopening
  and inspectable audit before/after state.
- Versioned FastAPI routes on the Phase 1 domain services. No domain schema
  change or empty migration was added; head remains `0002_domain_persistence`.
  Database bootstrap provisions the separate server-owned local analyst.
- Explicit local-only Host/Origin boundary, process-scoped browser write token,
  request size limit, safe problem details and generated request correlation.
  Browser payloads cannot select an audit actor. Transaction/deferred audit
  commit occurs before a successful HTTP response.
- Structured errors and draft retention. A version conflict requires explicit
  reload and review before a second save. Old note bodies and unlinked evidence
  remain available. AI assistance is marked not enabled; no assessments or
  metrics are invented.
- Generated OpenAPI/TypeScript contracts include the required write header.
  React Router 8.5.1 is pinned; route modules load on demand. The largest final
  production JavaScript chunk is approximately 438 kB minified (139 kB gzip),
  with separate operations, case, form and system chunks.
- CI definition now includes real PostgreSQL API checks and live desktop/mobile
  analyst workflows on the production Compose stack, without optional providers
  or GPU. Browser suites use separate artifact directories.

## Observed checks

| Check | Result |
| --- | --- |
| Backend suite | **99 passed** through disposable PostgreSQL runner: 69 non-integration checks and 30 real PostgreSQL integration checks |
| HTTP workflow | Import/replay, create/link, notes/revision, evidence, assignment, triage/investigation/resolution/closure/reopening and server-owned audit actor passed |
| HTTP failure paths | Host/Origin/token/actor injection rejection, synthetic-import validation, query bounds, literal wildcard search, body ceiling, redacted errors, unavailable storage/actor and no false success on deferred-commit failure passed |
| Relationships/concurrency | Case source filters do not duplicate rows, link/unlink retains history, duplicate links have a distinct error, concurrent stale edits have one winner and one conflict |
| Python quality | Ruff lint/format and mypy passed; 34 source files type-checked |
| Contracts | OpenAPI export/drift and generated TypeScript checks passed |
| Frontend quality | Formatting, lint, TypeScript and production build passed; dependency installation reported zero audit vulnerabilities |
| Isolated browser suite | **14 passed**, desktop/mobile: health/outage recovery, malformed readiness, keyboard skip link, contrast/accessibility, loading/empty/error case views and untrusted title rendering |
| Live development browser | Desktop/mobile analyst workflow and two-tab conflict scenarios passed against Vite/FastAPI, without intercepted requests |
| Final production browser | **4 passed** against built Nginx/FastAPI containers: complete analyst workflow with actual down/up and two-tab draft recovery, on desktop and mobile |
| Keyboard/modal checks | Dialog Escape closes correctly and restores its invoking case action; included in final desktop/mobile live workflow |
| Runtime/persistence | Case, linked alert, revised note, evidence snapshot/hash, assignment, disposition and all ten pre-reopen audit events survived the actual restart; reopening retained history and added version/event eleven |
| Real system smoke | Health 200/readiness 200 through Nginx and real browser, no intercepted requests; database revision/restricted login, Redis and real Celery no-op smoke passed |
| Visual review | Actual dashboard/case desktop/mobile captures inspected; live acceptance also captured case/history after restart |

The original upstream Starlette TestClient deprecation and Node color-environment
warnings remain without test failures. An initial mobile run collided with the
parallel isolated suite's trace directory; separate output directories fixed it,
and the complete final production run passed all four scenarios cleanly.

The first live proxy check also caught Vite's shorthand proxy rewriting Host to
the internal API hostname. Explicit `changeOrigin: false` fixed the local boundary;
Windows container source uses polling. Production docs/API proxy requests preserve
Host as well. The frontend image now builds as the node user with owned COPY
layers, avoiding a repeated recursive chown of dependency files.

## Runtime and limits

The deployment is restored to development mode at `http://127.0.0.1:8080`.
All five long-running services are healthy; migration/bootstrap completed.
Source reload is enabled and normal stop/start preserves application volumes.
Live acceptance leaves clearly marked synthetic cases/alerts for review;
it does not delete case history or reset application data.

This is an enterprise-style UI for single-user loopback development, without
multiuser sign-in or RBAC. Formal access control is required before LAN access.
Manual imports are synthetic only. There are no Elastic queries, Ollama calls,
GPU benchmarks, RAG, simulations, detection approval or remediation workflows.
No optional Elastic-profile runtime or new hosted CI execution is claimed.

Decisions and usage: [ADR 0005](ADR/0005-phase-2-local-case-workspace.md),
[API.md](API.md), [RUNBOOK.md](RUNBOOK.md), [ROADMAP.md](ROADMAP.md).
