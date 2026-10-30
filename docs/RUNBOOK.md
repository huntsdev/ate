# ATÉ operating runbook — through Phase 2

## Prerequisites and configuration

Use Windows 11, WSL2, and Docker Desktop in Linux-container mode. Ensure
`docker version` can reach the daemon and `docker compose version` succeeds.
An 8–10 GiB WSL/Docker budget is a starting allocation; measure consumption
before enabling Elastic or running a model. The R620 is not required.

Initial machine inspection found WSL not installed and no Docker CLI. In an
Administrator PowerShell terminal, run `wsl --install` and restart Windows as
instructed. This installs WSL2 with Ubuntu. Then install
[Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/),
start it, and select the WSL2 engine with Linux containers. Reopen PowerShell
and verify `wsl --version`, `docker version`, and `docker compose version`.
See [Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install)
and [Docker's WSL2 settings](https://docs.docker.com/desktop/features/wsl/).

For host source checks, use uv 0.12.12 (managed Python 3.12.14) and Node.js
26.8.1. CI uses those versions. The committed lockfiles select exact Python
and JavaScript packages. Do not update all dependencies implicitly during setup:
use `uv sync --locked` and `npm.cmd ci`.

Copy `.env.example` to `.env`, choose different owner/application PostgreSQL
passwords (at least 12 characters each), and keep the file out of source control. Compose reads `.env`
and passes selected settings to containers; it is not baked into images.
Keep the single quotes around both password values when replacing their example
value. Compose treats dollar signs in single-quoted values literally; unquoted
or double-quoted passwords can trigger variable substitution. Database URLs are
constructed with SQLAlchemy URL objects, not string concatenation.

`.env.example` documents all current settings. Credentials are server-only;
never add them as `VITE_*` values. Changing an environment password does not
change a password already stored in a PostgreSQL volume. Rotate it inside
PostgreSQL and update `.env` together; do not delete data to rotate credentials.

`ATE_POSTGRES_USER`/`ATE_POSTGRES_PASSWORD` belong to the owner/migration
container. API and worker receive `ATE_POSTGRES_APP_USER` (default `ate_app`)
and `ATE_POSTGRES_APP_PASSWORD` as their effective database credentials. The
migration container provisions this restricted login on both new and existing
volumes. The current workspace already has a generated application password;
no user setup or owner-password change is required for the Phase 1 upgrade.
Changing the application password and rerunning `stack.ps1 Migrate` applies
that password to the role; recreate API/worker containers to pick it up.
Reserve the configured application role for this project; bootstrap refuses
privileged roles or roles with memberships.

Leave `ATE_ELASTIC_URL=` blank until an Elastic endpoint is selected. Omitted
and blank values are supported; a nonblank value must be an HTTP(S) URL.
The optional synthetic profile's internal address is
`http://elasticsearch:9200`. Neither configuring that URL nor starting the
profile enables ingestion through Phase 2. See [ADR 0003](ADR/0003-optional-provider-configuration.md).

## Start, stop, and inspect

From the repository root:

```powershell
.\scripts\stack.ps1 Validate
.\scripts\stack.ps1 Start
.\scripts\stack.ps1 Status
.\scripts\stack.ps1 Smoke
.\scripts\stack.ps1 Logs
.\scripts\stack.ps1 Stop
```

`Start` builds images and waits up to 300 seconds for service health. Initial
downloads can exceed that; inspect status/logs and retry once downloads finish.
`Stop` runs `down` without `-v`, preserving data. `Restart` performs down/up,
also preserving volumes. `Logs` shows bounded API/worker/web logs. Standard
`docker compose logs postgres redis` inspects infrastructure separately.

Add `-Dev` consistently, including to `test-persistence.ps1`, to use the development override. It bind-mounts API,
worker, and web source; API/web reload source changes. Restart the worker after
editing its tasks. Rebuild images after changing lockfiles or manifests.

The container frontend uses polling for Windows source mounts. Vite preserves
the browser Host header instead of forwarding its internal Docker hostname;
the API accepts only loopback hosts. If changing the dev proxy configuration,
restart `web` so the new proxy options are active. Nginx preserves the browser
Host for API/docs requests too.

Add `-Elastic` to start/stop optional Elasticsearch and Kibana. These are local,
synthetic-only services with security disabled and loopback published ports.
They are not connected to any ingestion flow. Do not use production API keys
or data with this profile. Stop with the same profile to include those services.

| Host address | Purpose |
| --- | --- |
| `127.0.0.1:8080` | Web and same-origin API proxy; `ATE_WEB_PORT` overrides |
| `127.0.0.1:8000` | Direct API; `ATE_API_PORT` overrides |
| `127.0.0.1:9200` | Optional local Elastic only |
| `127.0.0.1:5601` | Optional Kibana only |
| No published port | PostgreSQL 5432 and Redis 6379 remain on the private network |

## Health, migrations, and persistence

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/v1/health
Invoke-RestMethod http://127.0.0.1:8080/api/v1/health/ready
.\scripts\stack.ps1 Migrate
.\scripts\test-persistence.ps1
# Optional: also proves synthetic Elastic-document persistence.
.\scripts\test-persistence.ps1 -Elastic
docker stats --no-stream
docker system df
```

The `migrate` service applies Alembic and restricted-role provisioning before
API/worker startup. Revision `0002_domain_persistence` adds the Phase 1 tables
after the original empty baseline. The smoke command reruns bootstrap twice
using the migration container, checks the runtime login/revision and Redis,
checks all health routes, and verifies a real queued synthetic task result.
API and worker cannot run schema migrations or change Alembic revision state.

Phase 2 also provisions the server-owned `local-analyst` actor. No new schema
revision is required for the HTTP/UI layer. Do not replace its reserved UUID or
reactivate it by modifying browser requests. If the actor is missing/inactive,
business routes fail safely with `local_actor_unavailable`; database bootstrap
must resolve that state. This local mode does not implement multiuser sign-in.

Seed synthetic data explicitly, using the restricted application login:

```powershell
docker compose exec -T api python -m sentinelforge.seed_demo
.\scripts\test-backend.ps1
```

The seed creates two synthetic actors and one investigation with a linked alert,
note, evidence snapshot and audit events. Rerunning it does not overwrite an
existing investigation. Demo case data is never seeded on startup. The local
analyst identity is provisioned separately by database bootstrap. Case HTTP
routes and analyst screens are available; see [API.md](API.md) and
[DATA-MODEL.md](DATA-MODEL.md).

`test-backend.ps1` requires uv and Docker, starts a temporary PostgreSQL container
using the pinned Compose image and a random loopback port, runs all backend
tests, then stops/removes only that disposable container. It does not use app
volumes or credentials. Alternatively, set `ATE_TEST_DATABASE_URL` to a
disposable PostgreSQL admin URL and run pytest; each integration test creates
and drops only its uniquely named `ate_test_<uuid>` database and test role.
Without that variable, plain pytest explicitly skips the integration tests.

The persistence test deliberately recreates local containers. It creates a
uniquely named `ate_phase1_probe_<uuid>` database through the owner-only migration
container, migrates it, and stores a complete synthetic case graph. It runs
down/up without deleting volumes, verifies cases, alerts, notes/revisions,
links, evidence/hash, assignment, disposition and audit events, then drops only
that database. With `-Elastic`, it similarly creates/verifies/removes only a
uniquely named synthetic index in the Compose Elastic instance. Do not run it
against a deployment serving analysts. Cleanup failures print the exact token
or index for manual cleanup once services recover.

Volumes are `ate_postgres_data`, `ate_redis_data`, and `ate_elastic_data` under
the fixed Compose project name. Do not run concurrent test stacks using that
same project name. Check `docker volume ls` and `docker compose config --volumes`
before any reset. Never use `docker compose config` output in a public report;
the full form can expose interpolated secrets. Use `config --quiet` for checks.

## Analyst workspace and browser validation

Open `/` for the overview, `/cases` for the case queue, `/alerts` for the alert
queue, and `/system` for health. The browser supports the complete synthetic
investigation workflow. Case detail offers overview, linked alerts, evidence,
notes and audit-history tabs. Closed cases must be reopened before editing.
Source references/snapshots are plain untrusted data; HTTP(S) references open
separately, and other reference schemes remain text.

The server selects `local-analyst` as the audit actor. Assignment changes the
owner, not the actor. Mutations require the local write token plus an allowed
Origin; browser code manages them in memory. On API restart, reload the page or
use the form's session-reload action, review the preserved draft and save again.
After a version conflict, explicitly reload the latest case and review the draft.
Nothing automatically retries a mutation or overwrites a newer case version.

From `apps/web`, `npm.cmd test` runs the isolated browser suite without a live
database. `npm.cmd run smoke:live` checks the actual system page read-only.
The live suite below writes clearly marked synthetic records and restarts the
stack. Use only the local synthetic deployment; do not run it while others are
using the same Compose project. Set the mode to match the current stack:

```powershell
Set-Location apps/web
$env:ATE_LIVE_ALLOW_RESTART = '1'
$env:ATE_LIVE_DEV = '1' # use '0' for the production Nginx mode
npm.cmd run test:live
Remove-Item Env:ATE_LIVE_ALLOW_RESTART
Remove-Item Env:ATE_LIVE_DEV
Set-Location ../..
```

The suite uses UI controls to import/link/create, preserve evidence, revise a
note, assign, resolve/close, restart, reload and reopen the same case with its
history intact. It also verifies two-tab conflict/draft recovery on desktop and
mobile. Restart tests are skipped without the explicit restart variable. Live
traces are under ignored `apps/web/test-results-live`; UI captures are under
ignored `artifacts/`. Synthetic acceptance records remain in the local database.
CI runs this against its disposable production Compose deployment.

## Native Windows Ollama

Ollama is installed and managed separately on Windows. Through Phase 2 the app only validates
the configured URL and model string; no inference requests or model downloads
occur. `ATE_OLLAMA_URL` defaults to `http://host.docker.internal:11434` and
`ATE_OLLAMA_MODEL` is an unbenchmarked configurable Qwen placeholder.

On 2026-10-28, `ollama list` and the native runtime's read-only model inventory
confirmed that `qwen3:8b` is installed (5,225,388,164 bytes), matching this
workspace's configuration. No inference or GPU benchmark was performed.
Use `ollama list` to check an existing installation before downloading a model.

To prepare the native runtime separately, download and install
[Ollama for Windows](https://ollama.com/download/windows). Reopen PowerShell
after installation, then download the model matching the current configuration:

```powershell
ollama --version
ollama pull qwen3:8b
ollama run qwen3:8b "Reply with one sentence confirming local inference works."
ollama ps
ollama stop qwen3:8b
```

The official [Qwen3 8B model page](https://ollama.com/library/qwen3:8b) lists
the current tag at approximately 5.2 GB with Q4_K_M quantization. This is a
starting candidate for the 12 GB GPU; context/cache memory adds to model
weights, and actual fit/performance must be measured in Phase 4. `ollama ps`
shows the processor allocation after loading. `ollama stop` unloads the model;
the native background runtime is managed separately through its Windows tray.
See [Ollama's Windows guide](https://docs.ollama.com/windows) for driver/runtime
requirements. Downloading/testing a model does not enable ATÉ inference: the
application integration is still deferred to Phase 4.

Before Phase 4, verify container-to-host routing and Ollama's listener. If a
non-loopback listener is needed, constrain it with Windows firewall rules to
the Docker/WSL sources. Do not expose the unauthenticated API publicly or add
an Ollama service to Compose. No GPU or host model is needed for current tests.

## Local source development without Docker

Backend liveness and the web shell can run on the host even without database
services. Readiness is correctly unavailable in that mode:

```powershell
Set-Location apps/api
uv sync --locked
$env:ATE_POSTGRES_PASSWORD = 'synthetic-local-only-password'
$env:ATE_POSTGRES_HOST = '127.0.0.1'
$env:ATE_REDIS_URL = 'redis://127.0.0.1:6379/0'
uv run --locked python -m uvicorn sentinelforge.main:create_app --factory --port 8000 --no-access-log
# In another PowerShell terminal, from the repository root:
Set-Location apps/web
npm.cmd ci
npm.cmd run dev
```

Open the Vite URL printed by the command. Its `/api` proxy reaches host port
8000; the container dev override supplies `API_PROXY_TARGET=http://api:8000`.
Run the Celery worker in Linux containers only; native Windows worker execution
is not supported by Celery. Host-only checks do not prove Docker operation.

## Troubleshooting

- Docker not found: lifecycle and persistence scripts check PATH, then standard
  per-user and all-users Docker Desktop locations. A newly installed Desktop
  is discovered even in a terminal with an older PATH. The discovered directory
  is added only to the current process PATH so Docker's credential helper can
  also run. For direct `docker` commands, reopen the terminal after installation
  or add Docker Desktop's `resources\bin` directory to your user PATH. Custom
  installations must be on PATH. Discovery does not start Docker Desktop;
  start the desktop application separately if the daemon is unavailable.
- Daemon unavailable: confirm Linux containers, WSL2 integration, and virtualization.
- PowerShell execution policy blocks scripts: use the displayed native Compose
  commands or an appropriate session-scoped policy under your local policy.
- Port occupied: change `ATE_WEB_PORT`/`ATE_API_PORT`, then recreate services.
- API unreachable: inspect `api`/`migrate` logs and `/health`; confirm the proxy
  points at the API. A 503 readiness response lists failed core dependencies.
- PostgreSQL authentication failure: verify volume credentials, not just `.env`.
- Redis unavailable: inspect broker health and its data limit; `noeviction`
  intentionally rejects writes when full instead of deleting queued data.
- Elastic exits: inspect its memory limit, available disk, and WSL
  `vm.max_map_count` requirements for the pinned version in the official Elastic
  Docker documentation. Do not enable it to troubleshoot unrelated API issues.
- Slow UI update: status polls every 30 seconds; Refresh status performs an
  immediate check. Failed responses clear dependency claims to Unknown.
- The runtime login is now separate from the migration owner. Long-term telemetry
  retention, automatic redaction, authentication, backups and tested restores
  remain unfinished. Continue using synthetic data.

## Reset and backup warning

Static fixture files are immutable; the explicit seed above writes a persistent
demo case in Phase 1. There is no case deletion/reset API. A nonempty domain
migration downgrade is rejected to preserve history; downgrade/upgrade tests
operate on disposable empty databases. Restore a backup or use a deliberately
disposable deployment for a complete reset.

Normal shutdown is safe for named volumes. A **separate destructive reset** is:

```powershell
docker compose --profile elastic down --volumes
```

This permanently deletes this project's PostgreSQL, Redis, and Elastic data.
Use only for an intentional disposable development reset, after checking the
project and taking any required backup. There is no automatic reset on startup
or shutdown. Persistent volumes are not backups. Logical backup and tested
restore procedures must be delivered before storing valuable or real data.

## Human Notes
- [x] Ollama Downloaded
- [x] Qwen 3:8b downloaded
- [ ] Download and setup ELK Stack
