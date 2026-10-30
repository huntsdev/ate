We are building ATÉ, a standalone, self-hosted AI-powered Security Operations and Purple-Team Validation platform.

HARDWARE:
- Windows 11 development PC
- 32 GB DDR5 RAM
- NVIDIA RTX 4070 Ti, 12 GB VRAM
- ~611 GB free SSD storage
- Optional Dell R620 homelab for attack simulation

DEPLOYMENT:
- Docker Compose for application infrastructure
- Native Windows Ollama for GPU-assisted inference
- Services must support start/stop on demand
- Persist cases, audit history, and telemetry across restarts

STACK:
- React, TypeScript, Vite, Tailwind CSS
- FastAPI, Python, Pydantic, SQLAlchemy, Alembic
- PostgreSQL + pgvector
- Redis + asynchronous workers
- Elasticsearch + Kibana
- Ollama with configurable Qwen models
- Atomic Red Team / Caldera for isolated simulations

CORE MODULES:
1. Alert ingestion through provider adapters (Elastic first)
2. Case management with assignment, notes, evidence and audit history
3. Automated AI triage with evidence-grounded structured responses
4. Historical case retrieval and RAG
5. Purple-team adversary simulation and detection validation
6. Detection Engineering as Code
7. Analyst dashboards and reporting

ENGINEERING CONSTRAINTS:
- Use a modular monolith, not microservices initially.
- PostgreSQL is the source of truth for cases.
- Keep Elastic and LLM implementations behind adapters.
- AI must never autonomously execute remediation or approve detections.
- Preserve human review and audit logging.
- Treat logs and retrieved evidence as untrusted input.
- Design for graceful degradation when Ollama is offline.
- Use synthetic alerts for initial development.
- Include tests, migrations, documentation and health checks.
- Develop incrementally against explicit acceptance criteria.

ROADMAP:
Phase 0: Infrastructure and repository foundation
Phase 1: Domain model and persistence
Phase 2: Case management API and React dashboard
Phase 3: Elasticsearch ingestion and correlation
Phase 4: Local Ollama AI investigation engine
Phase 5: Historical case intelligence and RAG
Phase 6: Purple-team simulation and validation
Phase 7: Detection Engineering as Code
Phase 8: Hardening, testing, observability and release

FIRST TASK:
Inspect the repository. Draft AGENTS.md, docs/ARCHITECTURE.md, and docs/ROADMAP.md based on the specification above. Include an implementation plan, API boundaries, database entities, technical dependencies, validation strategy, and acceptance criteria. Identify missing architectural decisions.

Do not implement the entire platform in one pass. Begin with Phase 0 only after the architecture and plan have been reviewed.

CURRENT IMPLEMENTATION BASELINE:
- Follow docs/ARCHITECTURE.md and docs/ROADMAP.md, including their updated apps/ monorepo layout.
- The user directed implementation to use docs/ and explicitly authorized Phase 2 on 2026-10-28. Implement the local case-management API and analyst UI on Phase 1 persistence; Phase 3 ingestion and later integrations remain outside this scope.
- ATÉ is the current product/UI name; SentinelForge remains the repository/design name.
- Use modern, clean, cybersecurity-focused UI/UX with shadcn/ui components where applicable.
- Record concrete implementation choices in docs/ADR/; do not implement workflows beyond the authorized phase.
- Distinguish tests actually run from infrastructure checks requiring Docker Desktop.
- Phase 0 baseline `00c7bf2` now has passing hosted CI and isolated fresh-clone
  startup/persistence evidence; see `docs/PHASE_0_STATUS.md`. Phase 3 and later
  require scope review. New uncommitted changes have separate local evidence.
- Elastic configuration may be omitted or blank (ADR 0003). Native Ollama has
  `qwen3:8b` installed; application inference remains deferred to Phase 4.
- Phase 1 implements domain persistence, internal services and auditability;
  follow `docs/DATA-MODEL.md` and ADR 0004. Actual checks are recorded in
  `docs/PHASE_1_STATUS.md`.
- API/worker use a restricted database login; only the migration container gets
  owner credentials. Use `scripts/test-backend.ps1` for real PostgreSQL tests;
  plain pytest skips integrations without `ATE_TEST_DATABASE_URL`.
- Phase 2 implements the loopback single-user case API and a complete shadcn UI
  redesign. Follow ADR 0005 and `docs/API.md`; use server-selected local actor
  identity and expected-version writes. Do not widen access or add Phase 3+
  provider workflows without authorization.
