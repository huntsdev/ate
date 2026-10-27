# ATÉ

ATÉ is a self-hosted security operations and purple-team validation platform.
The repository and longer-term design use the SentinelForge name. Phase 0
provides infrastructure, API health, and a modern shadcn/ui status dashboard.
Case management, alert ingestion, AI triage, and simulations are later phases.

## Start on Windows

Install Docker Desktop with its WSL2/Linux-container backend and Docker Compose.
Start Docker Desktop, open PowerShell in this directory, then run:

```powershell
Copy-Item .env.example .env
# Edit .env and replace ATE_POSTGRES_PASSWORD with your own local password.
.\scripts\stack.ps1 Start
.\scripts\stack.ps1 Smoke
```

Open **http://127.0.0.1:8080**. API documentation is at
http://127.0.0.1:8080/docs. The stack does not require Ollama, Elastic, or a GPU.
Published ports bind to loopback; this foundation has no authentication and is
for local development only.

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
worker, proxy, and restart-persistence checks. No live external providers or GPU
are required. See [Phase 0 status](docs/PHASE_0_STATUS.md) for results actually
observed in this environment and checks that remain unverified.

## Repository map

| Path | Purpose |
| --- | --- |
| `apps/api/sentinelforge` | FastAPI modular monolith, settings, health, DB foundation |
| `apps/worker` | Celery entry point using the same Python package |
| `apps/web` | React/TypeScript/Vite/Tailwind, shadcn/ui, TanStack Query |
| `packages/contracts` | Generated OpenAPI; frontend types derive from it |
| `tests/fixtures` | Deterministic synthetic alert/case files; no domain seed writes yet |
| `infrastructure` | Web proxy configuration |
| `scripts` | Windows lifecycle, contract export, and persistence checks |
| `docs/ADR` | Recorded Phase 0 decisions |

Read [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md),
[roadmap](docs/ROADMAP.md), [implemented API](docs/API.md), and
[operating runbook](docs/RUNBOOK.md). Phase 1 has not been implemented.
