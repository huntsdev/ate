# ADR 0001: Phase 0 foundation boundaries

Status: adopted for this implementation under the user's instruction to use
`docs/` and subsequent updated architecture/roadmap. Later-phase designs remain
planned work, not implemented capabilities.

## Context

The user updated the architecture and roadmap during implementation. The new
baseline specifies an `apps/` monorepo, contract generation, synthetic fixtures,
CI, and `/api/v1/health`. The product/UI name remains ATÉ as requested; the
repository, Python package, and design documents use SentinelForge.

## Decisions

- Follow `apps/web`, `apps/api/sentinelforge`, and `apps/worker`. API and worker
  use one backend package and image, preserving the modular monolith.
- Select Celery with Redis; do not add RQ. The sole task is a synthetic no-op
  used to verify a real broker/worker round trip. Business jobs, durable job
  records, queue-specific orchestration, and retries arrive in later phases.
  Celery runs in Linux containers, not natively on Windows.
- Establish an empty Alembic baseline. Its only table is `alembic_version`;
  no domain tables or application seed writes exist. The image includes
  pgvector binaries, but extension activation is deferred to Phase 5 under the
  updated roadmap. Future domain entities begin in Phase 1.
- Use process health at `/api/v1/health` and `/health/live`, with required
  PostgreSQL/Redis checks at `/health/ready`. Optional provider integrations
  report `not_enabled` without network probes. Real provider adapters and their
  fake implementations belong to their integration phases; current health tests
  use injected deterministic probes, and browser tests use API fixtures.
- Use loopback-only development access without enterprise authentication. Keep
  DB/broker unexposed on an internal network. The web/API share a frontend
  network; the worker has a separate provider network for future outbound access.
  There are no simulation networks or executors.
- Start core services by default, with Elastic/Kibana opt-in under `elastic`.
  The optional local synthetic stack disables Elastic authentication; never
  reuse it for real telemetry or widen its network bindings. Real ingestion
  requires a separate least-privilege authenticated provider configuration.
- Pin Python/JS dependency resolution in uv/npm lockfiles, core/base images by
  digest, Elastic/Kibana at matching version 9.5.5, and CI actions by commit.
  Version selections were checked against official docs and registries.

## Resource budgets and consequences

Configured container memory ceilings: PostgreSQL 1 GiB, Redis 256 MiB, API
512 MiB, worker 512 MiB, production web 128 MiB; migration process 256 MiB while
running. Core steady ceilings total 2.375 GiB. Development web uses 512 MiB.
Optional Elastic adds 2 GiB (1 GiB JVM heap), Kibana 1 GiB. These are configured
ceilings, not measured consumption. Start with an 8–10 GiB Docker/WSL budget,
leaving room within 32 GB for Windows and native Ollama. Measure before model
selection or lab load; no performance or VRAM-fit claim is made in Phase 0.

Redis uses AOF/everysec and a 128 MiB no-eviction data limit within its container
budget; this does not replace durable PostgreSQL job state. Compose container
logs rotate at 10 MiB × 3. Future datasets initially target under 200 GB per the
architecture; no enforcement or retention worker is implemented yet. Monitor
disk usage manually until that work is delivered.

The local bootstrap PostgreSQL account can create databases for the isolated
persistence test. Before real data or business operations, separate migration
and application privileges. Normal shutdown preserves volumes; only the
documented destructive reset command removes them.

Sources: [Celery support/platform notes](https://docs.celeryq.dev/en/stable/getting-started/introduction.html),
[Compose startup dependencies](https://docs.docker.com/compose/how-tos/startup-order/),
[uv lock/sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/),
[pgvector images](https://github.com/pgvector/pgvector),
[Elastic local Docker setup](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-basic).
