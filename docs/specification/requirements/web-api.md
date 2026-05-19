# Requirements: web API

The FastAPI REST surface — co-equal entry point with the MCP server
([ADR-0008](../decisions/0008-mcp-and-rest-surfaces.md)).

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-API-001 — REST endpoints mirror the MCP tool surface ✅
Every MCP tool has a REST equivalent. The full set:

- `/api/devices/*` — CRUD on devices + accounts + credentials
- `/api/catalog/{query,execute,confirm}` — catalog-in-the-loop
- `/api/plans` + `/api/plans/{id}/execute` + `/api/plans/{id}` — plans
- `/api/snapshot/{device,fleet,restore,diff/{id},drift}` — snapshot
- `/api/discovery/{scan,register}` — discovery
- `/api/schedules` + `/api/schedules/{id}/run` — scheduling
- `/api/capture` + `/api/capture/{token}/status` — OOB capture JSON
- `/api/confirm/{token}/status` — confirm session polling
- `/api/fleet/settings` + `/api/fleet/settings/{key}` — fleet settings
- `/api/api-keys` + `/api/api-keys/{id}` — API key CRUD
- `/api/audit` — audit log read
- `/api/whoami` — current principal

### FR-API-002 — OpenAPI schema exposed at /api/docs ✅
FastAPI auto-generates Swagger UI at `/api/docs` and ReDoc at
`/api/redoc`. The schema reflects every route's request/response
shapes via Pydantic models. Useful for SDK generation and for
operators to validate calls without consulting docs.

### FR-API-003 — Health endpoints ✅
- `/health` — cheap liveness (returns 200 if process is up)
- `/api/health` — readiness, exercises `registry.list_devices()`

Both are in the auth-exempt list (see
[security.md](security.md) FR-AUTH-002).

### FR-API-004 — Browser-facing form endpoints ✅
- `GET /capture/{token}` + `POST /capture/{token}` — OOB credential
  entry form
- `GET /capture/fleet/{token}` + `POST /capture/fleet/{token}` —
  fleet-setting password capture
- `GET /confirm/{token}` + `POST /confirm/{token}` — dangerous-op
  confirmation form

These render HTML (Jinja2 templates) and respect the same
rate-limiting + lockout policies as the MCP-driven flows.

### FR-API-005 — Auth via the configured backend ✅
Every non-exempt route requires authentication. The auth middleware
populates `request.state.principal`; routes read it via
`Depends(get_current_principal)`. Backends:
- `none` (default, dev/test)
- `windows` (REMOTE_USER via reverse proxy)
- `api-key` (Bearer token)
- `composite` (both, in that order)

See [authentication.md](authentication.md).

### FR-API-006 — CORS allowlist driven by env ✅
`ADMZ_ALLOWED_ORIGINS` (comma-separated) controls allowed origins.
Default is the 4 localhost variants. Wildcard `*` is opt-in and
forces `allow_credentials=False` per the CORS spec.

### FR-API-007 — Routes return structured Pydantic responses ✅
Every endpoint declares a `response_model=...` so the OpenAPI schema
is accurate and clients can rely on shapes. Failures use FastAPI's
standard `HTTPException` with structured `detail`.

## Non-functional requirements

### NFR-API-001 — Audit events recorded at gated entry points ✅ (Phase 4D)
`get_device_credentials`, API-key minting/revocation, confirm-flow
completions all record audit entries with the authenticated
principal.

### NFR-API-002 — Server defaults to localhost bind ✅ (Phase 2B)
`python -m admz api` binds 127.0.0.1 by default. `0.0.0.0` requires
explicit `--host 0.0.0.0` AND (under windows/composite auth)
`ADMZ_AUTH_INSECURE_BIND_OK=true`.

### NFR-API-003 — TLS termination is the reverse proxy's job ✅
Uvicorn serves HTTP on localhost. IIS / nginx / Caddy terminates
TLS in front. ADMZ doesn't ship its own TLS handling.

## Known limitations

### KL-API-001 — `/api/devices/{id}/credentials` is gated but still plaintext ⚠️
Even with `tool_get_credentials_enabled=true`, the endpoint returns
the plaintext password. This is the deliberate design — there's no
"verify a credential" REST API that wouldn't require returning it.
Operators who turn this on accept the risk; the audit log records
every retrieval.

### KL-API-002 — No SDK generated yet 📋
The OpenAPI schema is exposed but no auto-generated Python / TS /
Go SDK ships with ADMZ. Operators using the REST surface from non-
Python clients write their own thin wrappers.

### KL-API-003 — No GraphQL surface 📋
REST is the only HTTP API. The OpenAPI surface is rich enough for
the common use cases.

### KL-API-004 — Server-side pagination is missing in some list endpoints 🚧
`GET /api/devices` returns the full list. At ~1,000 devices this is
fine; at 10,000+ it should be paginated. Same for `GET /api/api-keys`
and `GET /api/audit` (the audit endpoint at least supports a `limit`
parameter — paging via `since` works).

## References

- ADRs: [0008](../decisions/0008-mcp-and-rest-surfaces.md), [0021](../decisions/0021-windows-iwa-via-reverse-proxy.md), [0022](../decisions/0022-api-keys-for-agents.md)
- Cross-cutting reqs: [authentication.md](authentication.md), [security.md](security.md), [observability.md](observability.md)
- Deployment: [DEPLOYMENT_WINDOWS.md](../../DEPLOYMENT_WINDOWS.md)
- Code: `admz/api/main.py`, `admz/api/routes/`
