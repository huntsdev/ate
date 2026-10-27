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
- The user directed implementation to use docs/. Phase 0 only is authorized in this session.
- ATÉ is the current product/UI name; SentinelForge remains the repository/design name.
- Use modern, clean, cybersecurity-focused UI/UX with shadcn/ui components where applicable.
- Record concrete Phase 0 choices in docs/ADR/; do not implement later-phase business workflows.
- Distinguish tests actually run from infrastructure checks requiring Docker Desktop.
