# Phase 0 implementation and validation

This is the historical Phase 0 closeout record. The user has since authorized
Phases 1 and 2; current results are in [PHASE_2_STATUS.md](PHASE_2_STATUS.md).

Status: Phase 0 baseline source, core Docker runtime, fresh-clone startup, and
hosted CI verified as of 2026-10-28. Optional Elastic-profile runtime remains
unverified and is not a required core exit criterion. At Phase 0 closeout,
later phases had not been implemented. The configuration follow-up had local validation;
it has not been pushed or run in hosted CI.

## Baseline and scope

The initial workspace contained only `AGENTS.md`, without application code or
Git metadata. The user directed implementation to use `docs/`, then supplied
updated architecture/roadmap documents during the work. Those updates were
reviewed and the code was moved into their `apps/` layout. ATÉ remains the
requested UI/product name; SentinelForge is the repository/design name.

No case/alert domain tables or business endpoints, Elastic ingestion, Ollama
inference, embeddings, simulation execution, or detection approval were added.
The only queued task is a synthetic no-op. Synthetic alert/case fixtures are
static files; database seeding awaits the Phase 1 schema.

## Changes delivered

- `apps/api`: FastAPI health/readiness, validated configuration, correlation
  IDs, JSON logging/redaction, SQLAlchemy connection/session foundation,
  empty Alembic baseline, tests, and quality/type tooling.
- `apps/worker`: Celery/Redis entry point sharing the backend package/image,
  concurrency limits, JSON serialization, and a synthetic smoke task.
- `apps/web`: responsive React/TypeScript/Vite/Tailwind dashboard, shadcn/ui
  components, TanStack Query, real API status, refresh/polling, and accessible
  loading/degraded/unreachable states. No invented case metrics.
- `packages/contracts`: OpenAPI export, generated frontend types, drift checks.
  `tests/fixtures`: explicitly synthetic and deterministic alert/case files.
- Compose core/dev stacks: private PostgreSQL/Redis, non-root API/web/worker,
  migration-before-API startup, loopback ports, data volumes, resource limits,
  rotating logs, optional Elastic/Kibana profile.
- CI definition: Python/frontend checks and a real core-stack integration job
  for migrations, proxy, broker, worker, and restart persistence.
- Windows lifecycle/persistence scripts, API documentation, README, runbook,
  and ADRs. AGENTS/architecture/roadmap notes reflect the implementation choices.

## Validation observed on Windows

| Check | Result |
| --- | --- |
| Python dependencies | `uv sync --locked` passed with managed Python 3.12.14 |
| Python quality | Ruff lint/format and mypy passed; 14 source files type-checked |
| Backend tests | 23 passed: settings/errors, health/failure/recovery/deadlines, redaction, baseline SQL, fixtures, Compose boundaries, worker unit contract |
| API contract | OpenAPI export and generated TypeScript drift checks passed |
| Frontend dependencies | Clean `npm ci` passed; audit reported zero vulnerabilities |
| Frontend quality | Formatting, lint, TypeScript, and production build passed |
| Browser tests | Eight Chromium desktop/mobile cases passed; includes automated WCAG checks, focus/overflow, malformed data, and outage recovery |
| Real API/browser smoke | Passed without intercepted requests: health 200, readiness 503 with PostgreSQL/Redis absent |
| Visual review | Inspected actual API-backed desktop/mobile captures under ignored `artifacts/` |
| Compose validation | Core, Elastic, dev, dev+Elastic configurations passed official standalone Compose v5.6.1 configuration checks |
| PowerShell | All three scripts parse; missing-install error and fallback discovery without Docker on PATH passed; credential helper also resolves |
| Documentation | All 21 local file links in README/docs resolved |

Additional engine-backed validation after Docker installation:

| Check | Result |
| --- | --- |
| Core images and cold startup | API/worker/migration and production web built successfully; all five long-running services became healthy |
| Migration / dependencies / worker | Smoke passed: baseline upgrade rerun twice, real PostgreSQL query, Redis PING, all API health routes, real queued Celery task result |
| Nginx proxy | Both `/api/v1/health` and `/api/v1/health/ready` returned 200 through host port 8080 |
| Restart persistence | Dedicated synthetic database record survived Compose down/up; post-restart smoke passed and test database cleanup succeeded |
| Actual browser / container UI | `npm run smoke:live` passed without intercepted requests; health 200 and readiness 200 through Nginx; desktop/mobile captures refreshed |
| Compose variants | Core, optional Elastic, and dev+Elastic configuration checks passed with the actual installed Docker CLI |
| Credential hygiene | `.env` confirmed ignored by Git; its existing password was single-quoted locally to prevent Compose dollar-sign interpolation; `.env.example` retains a quoted placeholder |

One idle `docker stats --no-stream` snapshot showed web 13.88 MiB, API 71.9 MiB,
worker 77.58 MiB, Redis 7.309 MiB, and PostgreSQL 24.46 MiB (about 195 MiB total).
This snapshot excludes Docker/WSL overhead and does not represent load/peak use
or the optional Elastic profile. The pinned Python container reports 3.12.16;
host source checks used managed Python 3.12.14, both within the 3.12 constraint.

The backend suite emits one upstream Starlette warning about its current httpx
TestClient compatibility path; tests pass. Mocked tests do not prove database
availability. The separate live browser smoke proves actual FastAPI responses
reach the page even with core infrastructure absent.

## Updated roadmap exit criteria

| Criterion | Evidence / remaining work |
| --- | --- |
| Fresh clone starts with documented commands | Passed remote clone of `00c7bf2`, isolated project/new volumes, synthetic credentials, web/proxy health, migrations, worker, and restart persistence |
| `/api/v1/health` and frontend load API data | Passed against native FastAPI/Vite and the actual Docker API/Nginx/browser stack |
| Migration and persistence through down/up | Passed real migration, rerun, database persistence, cleanup, and post-restart worker smoke |
| CI passes without GPU or external lab/providers | Hosted API, web, and infrastructure jobs passed for `00c7bf2`; see dated verification below |
| Stop preserves volumes; destructive reset separate | Passed actual down/up synthetic persistence check; no volumes deleted |

## Environmental limits and next verification

During initial validation Docker and WSL were unavailable. The user has since
installed WSL 3.0.3 and Docker Desktop 4.97.0 with Compose 5.6.1. The Docker CLI
was found at `%LOCALAPPDATA%/Programs/DockerDesktop/resources/bin/docker.exe`;
the `desktop-linux` engine was reached directly and core Compose configuration
validation passed with the existing `.env`.

The initial startup was blocked by the example password. After the user set a
password, an older terminal PATH still could not resolve the newly installed
CLI. Shared discovery in `scripts/docker.ps1` now checks PATH and standard
per-user/all-users Desktop locations. It adjusts only the current process PATH,
including support for the Docker credential helper. Both lifecycle and
persistence scripts use the shared resolver. The existing local password was
single-quoted to preserve its literal dollar sign; the password itself was not
replaced. The template/runbook now demonstrate safe quoting.

At the end of the original runtime check, the core stack ran at
`http://127.0.0.1:8080`; the migration service exited successfully, and API,
worker, web, PostgreSQL, and Redis were healthy.
Optional Elastic/Kibana and inference were not enabled. The earlier temporary
Compose configuration checks are separate from the engine-backed results above.

To repeat local verification with Docker Desktop running, use
[RUNBOOK.md](RUNBOOK.md):

```powershell
.\scripts\stack.ps1 Start
.\scripts\stack.ps1 Smoke
.\scripts\test-persistence.ps1
# Optional synthetic telemetry-volume verification:
.\scripts\test-persistence.ps1 -Elastic
docker stats --no-stream
.\scripts\stack.ps1 Stop -Elastic
```

The initial validation did not include hosted CI or a separate fresh clone;
those checks now have the dated results below. Optional-profile startup remains
unverified. Resource ceilings in
[ADR 0001](ADR/0001-phase-0-foundation.md) are limits; the idle snapshot above
does not establish workload headroom. Phase 1 requires its own scope review.

## Phase 0 closeout verification — 2026-10-28

- Git remote is now `https://github.com/huntsdev/ate.git`. The GitHub Actions
  [baseline run](https://github.com/huntsdev/ate/actions/runs/40444887595) for
  `00c7bf2320bcb5c501f34ca8d60495f6ecbfb9c5` completed successfully. Each of
  `api`, `web`, and `infrastructure` reports `success` through the GitHub API.
- Cloned that remote commit into the ignored directory
  `artifacts/phase0-fresh-clone-663e666cd761`. Used a generated synthetic
  password, `COMPOSE_PROJECT_NAME=ate_clone_663e666cd761`, and host ports
  18080/18000 to keep the check separate from the development deployment.
- The documented `stack.ps1 Validate`, `Start`, and `Smoke` commands passed.
  Both health/readiness routes returned 200 through the web proxy, and the web
  HTML loaded successfully. `test-persistence.ps1` verified a synthetic record
  across down/up, cleaned up its test database, and passed the real worker
  smoke after restart. The clone project was stopped without deleting volumes.
  This used a clean checkout and new volumes on the existing Docker host;
  it does not claim validation on a newly installed Windows machine.
- Native `ollama list` and the read-only `/api/tags` inventory confirm
  `qwen3:8b` is installed, matching `.env`. No model generation, download,
  container-to-host inference check, or GPU benchmark was performed.
- [ADR 0003](ADR/0003-optional-provider-configuration.md) records support for
  omitted/blank Elastic configuration. Updated the local `.env` placeholder
  to blank without changing the database credentials or Ollama settings.
- Current backend checks passed: 27 tests, Ruff lint/format, mypy (14 source
  files), and OpenAPI drift validation. Tests cover blank/whitespace and
  configured Elastic URLs plus invalid URL rejection. The existing upstream
  TestClient deprecation warning remains. Core and dev+Elastic Compose
  configuration validation passed; the optional services were not started.
- Started the current workspace with `stack.ps1 Start -Dev` and the blank
  Elastic URL. All five long-running services are healthy, the baseline
  migration completed, and `stack.ps1 Smoke -Dev` passed the real database,
  broker, and worker checks. `npm run smoke:live` passed with no intercepted
  requests: health 200 and readiness 200, including desktop/mobile captures.
  The development stack remains running at `http://127.0.0.1:8080` with source
  reload enabled. Stop it with `stack.ps1 Stop -Dev`; named volumes persist.
- Documentation validation passed: all 25 relative file links in README,
  AGENTS, and docs resolve. `.env` remains ignored by Git.

The successful hosted run covers the committed baseline, not this uncommitted
follow-up. No push or new hosted run was performed. Phase 1 (domain tables,
migrations, and auditability) is the next implementation scope to review.
