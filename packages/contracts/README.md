FastAPI/Pydantic owns the API contract. `openapi.json` is generated with
`scripts/export_openapi.py`. The frontend generates `src/lib/api.generated.ts`
with `npm run contracts:generate`; CI checks both artifacts for drift.

See [API.md](../../docs/API.md) for implemented routes and regeneration commands.
