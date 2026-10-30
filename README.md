# ATÉ

ATÉ is a self-hosted security operations and purple-team validation platform.
The repository and longer-term design use the SentinelForge name. Phase 2 adds
a complete analyst workspace: database-backed overview, searchable cases and
alerts, evidence, notes/revisions, assignment, lifecycle decisions and audit
history. The UI uses a graphite/mint theme and shadcn components throughout.
External ingestion, AI assistance and simulations remain later phases.

## Start on Windows

Install Docker Desktop with its WSL2/Linux-container backend and Docker Compose.
Start Docker Desktop, open PowerShell in this directory, then run:

```powershell
Copy-Item .env.example .env
# Edit .env: set different ATE_POSTGRES_PASSWORD and ATE_POSTGRES_APP_PASSWORD values.
.\scripts\stack.ps1 Start
.\scripts\stack.ps1 Smoke
```

Open **http://127.0.0.1:8080**. API documentation is at
http://127.0.0.1:8080/docs. The stack does not require Ollama, Elastic, or a GPU.
Published ports bind to loopback. This is single-user local development with
a server-selected analyst and browser write protection, without multiuser sign-in.

Leave `ATE_ELASTIC_URL=` blank while Elastic is unconfigured. Native Windows
Ollama can remain installed with `qwen3:8b`; Phase 2 does not invoke inference.

```powershell
.\scripts\stack.ps1 Status
.\scripts\stack.ps1 Logs
.\scripts\stack.ps1 Stop
.\scripts\stack.ps1 Start -Dev       # source reload for API/web
.\scripts\stack.ps1 Stop -Dev
.\scripts\stack.ps1 Start -Elastic   # optional synthetic-only Elastic/Kibana
.\scripts\stack.ps1 Stop -Elastic
```

Normal stop/start preserves named volumes. Volume persistence is not a backup.
See [RUNBOOK.md](docs/RUNBOOK.md) before resetting data or changing profiles.

The migration container applies the schema and provisions the restricted API/
worker database login. To explicitly seed a small synthetic investigation:

```powershell
docker compose exec -T api python -m sentinelforge.seed_demo
.\scripts\test-backend.ps1          # complete suite with disposable PostgreSQL
.\scripts\test-persistence.ps1 -Dev # use -Dev only if the dev stack is running
```

The seed is idempotent and preserves analyst edits. You can also import a
synthetic alert, create/link a case, preserve evidence, add notes, assign,
resolve/close, review history and reopen entirely in the browser.

| Route | Workspace |
| --- | --- |
| `/` | Operational overview with real case counts |
| `/cases`, `/cases/:id` | Searchable case queue and tabbed investigation workspace |
| `/alerts`, `/alerts/:id` | Synthetic alert queue, source context and case linkage |
| `/system` | Live service health and optional integration status |

Live browser acceptance checks create marked synthetic records and restart the
local stack without removing volumes. Run only on the synthetic development
deployment, using the same dev/production mode as the active stack:

```powershell
Set-Location apps/web
$env:ATE_LIVE_ALLOW_RESTART = '1'
$env:ATE_LIVE_DEV = '1' # use '0' for the production Nginx stack
npm.cmd run test:live
Remove-Item Env:ATE_LIVE_ALLOW_RESTART
Remove-Item Env:ATE_LIVE_DEV
Set-Location ../..
```

## Check the source

Install uv 0.12.12 and Node.js 26.8.1 (Node 24+ also satisfies the web manifest).
uv installs the pinned Python 3.12.14 runtime when needed. No system Python is
required for the following commands.

```powershell
Set-Location apps/api
uv sync --locked
uv run --locked ruff check . ../worker ../../scripts
uv run --locked ruff format --check . ../worker ../../scripts
uv run --locked python -m mypy
uv run --locked python -m pytest -q
uv run --locked python ../../scripts/export_openapi.py --check
Set-Location ../web
npm.cmd ci
npm.cmd run contracts:check
npm.cmd run format:check
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd test
Set-Location ../..
```

GitHub Actions defines these checks plus real core-stack migration, broker,
worker, proxy, real browser workflows and restart-persistence checks. No live external providers or GPU
are required. Plain pytest skips PostgreSQL integration tests unless
`ATE_TEST_DATABASE_URL` is configured; `scripts/test-backend.ps1` supplies a
disposable instance. See [Phase 2 status](docs/PHASE_2_STATUS.md),
[Phase 1 history](docs/PHASE_1_STATUS.md), and
[Phase 0 history](docs/PHASE_0_STATUS.md) for observed results and limitations.

## Repository map

| Path | Purpose |
| --- | --- |
| `apps/api/sentinelforge` | FastAPI API/local boundary, domain services, persistence and health |
| `apps/worker` | Celery entry point using the same Python package |
| `apps/web` | React/TypeScript/Vite/Tailwind, shadcn/ui, React Router, TanStack Query |
| `packages/contracts` | Generated OpenAPI; frontend types derive from it |
| `tests/fixtures` | Deterministic synthetic inputs for the explicit demo seed |
| `infrastructure` | Web proxy configuration |
| `scripts` | Windows lifecycle, contract export, and persistence checks |
| `docs/ADR` | Recorded foundation, persistence, API and UI decisions |

Read [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md),
[roadmap](docs/ROADMAP.md), [implemented API](docs/API.md),
[data model](docs/DATA-MODEL.md), and [operating runbook](docs/RUNBOOK.md).
