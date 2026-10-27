# Phase 0 implementation and validation

Status: Phase 0 source and local core Docker runtime validated. Hosted CI,
fresh-clone execution, and optional Elastic-profile runtime remain unverified.
Later phases have not been implemented.

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
| Fresh clone starts with documented commands | Local cold image build/startup passed from initially empty volumes; separate fresh-clone execution unrun |
| `/api/v1/health` and frontend load API data | Passed against native FastAPI/Vite and the actual Docker API/Nginx/browser stack |
| Migration and persistence through down/up | Passed real migration, rerun, database persistence, cleanup, and post-restart worker smoke |
| CI passes without GPU or external lab/providers | Workflow supplied; hosted execution unrun, no Git remote/CI run available |
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

The core stack is running at `http://127.0.0.1:8080`; the migration service has
exited successfully, and API, worker, web, PostgreSQL, and Redis are healthy.
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

Hosted CI/fresh-clone execution and optional-profile startup still need their
own results; no hosted CI pass is claimed. Resource ceilings in
[ADR 0001](ADR/0001-phase-0-foundation.md) are limits; the idle snapshot above
does not establish workload headroom. Phase 1 requires its own scope review.
