# ADR 0005: Phase 2 local case workspace and HTTP boundary

Status: adopted under the user's authorization to start Phase 2 and subsequent
request for a complete modern enterprise-style UI redesign on 2026-10-28.

## Application boundary

Expose the existing Phase 1 services through versioned FastAPI routes; retain
PostgreSQL as the source of truth and the existing schema/migration history.
No ingestion adapter, model call or simulation execution is introduced.
Closing/reopening replaces destructive case deletion; there is no case delete
route. Child unlink operations retain their provenance/history.

All business endpoints resolve a server-owned local analyst UUID. Database
bootstrap creates an active human `local-analyst` with `auth_source=local` at
reserved UUID `00000000-0000-4000-8000-000000000200`. It does not reactivate or
silently overwrite a conflicting/inactive identity. Browser bodies cannot
select an actor; assignment chooses an owner without changing the audit actor.
The existing demo analyst remains a separate synthetic identity.

This is explicitly **loopback single-user development**, with no sign-in,
multiuser session authentication, RBAC or enterprise identity claim. Compose
continues to publish only loopback ports. The API additionally allows only
loopback Host names and loopback browser origins; configuration cannot enable
an external host/origin. A different deployment mode requires authentication
and an architecture review first.

`GET /api/v1/session` returns the local actor and a process-scoped random write
token. Unsafe methods require an allowed Origin and `X-ATE-CSRF`; tokens stay
in frontend query memory, never URLs, browser storage or logs. There is no
permissive CORS policy. This prevents ordinary cross-site browser writes and
DNS rebinding; it does not defend against malicious software already running
as the local user. A restarted API rotates its token, so a failed write asks
the analyst to reload the session and review the preserved draft before retry.
Requests have a 64 KiB body ceiling enforced before parsing, including chunked
bodies. No inference/evidence text is executed or rendered as HTML.

## Transactions, queries and errors

Use a function-scoped FastAPI yield dependency for the outer database
transaction. Commit, including deferred audit constraints, must finish before
the HTTP success response is sent. Route handlers serialize explicit Pydantic
response models and call Phase 1 commands with server correlation/actor IDs.
Every case mutation after creation requires a positive integer
`expected_version`; no actor or lifecycle fields are accepted in detail patches.

List queries have allowlisted sort keys, stable UUID tie-breakers, bounded
offsets and page sizes (1–100; audit timeline at most 50). Search escapes LIKE
wildcards and uses bound parameters. Case-source filtering uses EXISTS so
multiple alert links do not duplicate cases or inflate counts. Owner/source
and link counts are batched per page. Dashboard counts and severity distribution
come from PostgreSQL, never frontend sample metrics. Related cases in an alert
detail are bounded to the most recently updated 25, with the total relationship
count reported separately.

Errors use `application/problem+json` with a code, status, safe detail, generated
correlation ID and bounded field-error list. Validation errors do not echo input
values or database exception messages. Stale versions have `version_conflict`;
an existing relationship has `association_conflict`. Storage outages are 503.
No automatic mutation retry occurs after a conflict or token change.

Manual alert import is explicitly synthetic in this phase: provider `synthetic`,
reserved `.invalid` hostnames if supplied, and synthetic references. Imports are
idempotent and retain the first record. External read-only adapters arrive in
Phase 3. Manually entered evidence has analyst provenance, not a claim that a
provider adapter verified it.

## UI and routing

Use React Router 8.5.1 in declarative browser mode, pinned in the lockfile, with
routes `/`, `/cases`, `/cases/:id`, `/alerts`, `/alerts/:id`, and `/system`.
Keep TanStack Query for server state and generated OpenAPI types for contracts.
Route modules load on demand. Preserve URLs for list filters/pagination and
support direct navigation through the Vite/Nginx SPA fallbacks.

The redesign uses a graphite palette, restrained mint accents, a custom vector
brand mark, an operations sidebar, compact data tables and a tabbed case
workspace. Use the existing shadcn Button/Card/Badge components and CLI-generated
Dialog, Input, Textarea, Label, Select, Tabs, Table and Skeleton components.
All use the repository's `cn` utility and locally maintained theme tokens.
No remote image/font dependency, fake metrics, invented model findings or dead
navigation is added. Severity, lifecycle status and analyst disposition have
distinct labels and presentations; AI assistance is explicitly not enabled.

Mutation dialogs keep drafts on failure. A version conflict disables saving
until the analyst explicitly reloads the latest version, reviews the retained
draft and chooses to save. Notes and source text remain plain text. Evidence
references are links only for HTTP(S), with other schemes displayed as text.

Vite's proxy must explicitly preserve the browser Host (`changeOrigin: false`)
to match the local-only API boundary. Container development uses polling for
Windows bind-mounted source. Nginx preserves the browser Host for API/docs
requests too. Neither proxy widens the backend's trusted origins.

## Verification

Test API flows with real PostgreSQL, including actor/origin/token rejection,
redacted validation, commit failure/rollback, concurrency and query boundaries.
Browser checks cover responsive health, loading, errors, empty views, keyboard
operation, untrusted text, dialog accessibility and the real analyst flow.
The live workflow creates synthetic records through UI controls, preserves
evidence/notes, records a human disposition, restarts Compose without removing
volumes, reloads the saved case and reopens it with history intact. Restart
tests require explicit `ATE_LIVE_ALLOW_RESTART=1` on the local synthetic stack.

Sources: [React Router declarative installation](https://reactrouter.com/start/declarative/installation),
[FastAPI function-scoped dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope).
