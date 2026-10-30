Phase 1 implements typed case rules and transaction-scoped services in `cases/`.
Persistence mappings/repositories remain in `db/`. See `docs/DATA-MODEL.md` for
invariants and service boundaries. Phase 2 exposes them through `api/` and the analyst UI;
provider adapters, model orchestration and execution domains remain deferred.
