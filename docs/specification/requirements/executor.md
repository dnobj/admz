# Requirements: executor

Takes a catalog operation + device + credentials + parameters and
performs the HTTP call. One executor per API generation.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-EXE-001 — BaseExecutor ABC ✅
`admz/executor/base.py::BaseExecutor` defines the contract:
- `family` property — string label this executor handles
  (`vapix`, future: `acs`, `aoa`)
- `execute(operation, device, credentials, params)` → `StepResult`

Executors are registered by family and dispatched by the plan
engine and direct-call MCP tool.

### FR-EXE-002 — Four-generation executors under VapixExecutor ✅
`admz/executor/vapix.py::VapixExecutor` is a generation-dispatching
wrapper. The four implementations:

| Class | Generation | Verb / shape |
|---|---|---|
| `LegacyCgiExecutor` | `legacy-cgi` | GET with query params, text response |
| `JsonRpcExecutor` | `json-rpc` | POST JSON-RPC envelope |
| `ConfigRestExecutor` | `config-rest` | REST verbs against `/config/rest/...` |
| `SoapExecutor` | `soap` | POST SOAP envelope with action header |

The wrapper picks the implementation based on the operation's
`_generation` field (set by the loader from `_api.yaml`).

### FR-EXE-003 — Per-protocol auth scheme detection ✅
Different VAPIX endpoints use different auth schemes (digest over
HTTP, basic over HTTPS, none for unauthenticated probes). See
[ADR-0007](../decisions/0007-per-protocol-auth.md). The executor
honors the `_api.yaml` `auth` field and the credential probe
detects per-host schemes (FR-DISC-007).

### FR-EXE-004 — Parameter substitution ✅
Operation YAML `request.query` and `request.body` templates
reference parameters via `${name}` syntax. The executor substitutes
caller-supplied values, validates against the param_rules, and
encodes appropriately for the generation (form-encoded for legacy
CGI, JSON body for JSON-RPC, XML for SOAP).

### FR-EXE-005 — Response parsing ✅
Per `response.format` in YAML:
- `text` — return body string; check for `error_prefix` to flag
  errors that arrived as 200 OK with `# Error: …` content
- `json` — parse JSON; surface `error` / `data` fields
- `xml` — parse SOAP envelope; surface `Fault`
- `binary` — return bytes (e.g. jpg snapshot, server report tar)

### FR-EXE-006 — StepResult shape ✅
`admz/executor/models.py::StepResult`:
- `success` — bool
- `data` — parsed response (dict / str / bytes)
- `error` — error string (when `success=False`)
- `http_status` — int
- `duration_ms` — float
- `request_summary` — dict for audit/debug

### FR-EXE-007 — Read current values for rollback ✅
For `rollback.strategy = revert-params` ops, the executor's
caller (plan engine) first invokes the operation's `read_action`
(usually `list`) and stores the pre-write values. On rollback the
plan engine replays an update with the stored values.

### FR-EXE-008 — Timeout per request ✅
Default 30s per HTTP call, overridable via plan step config. See
[ADR-0018](../decisions/0018-expect-timeout-semantics.md) for the
intentional timeout semantics on long-running ops (firmware
upgrade, factory reset).

### FR-EXE-009 — SSL verification configurable ✅
`verify_ssl_default()` from `admz/ssl_config.py` returns True
unless `ADMZ_VERIFY_SSL=false`. Per-device `verify_ssl` override
in the registry takes precedence. Cameras commonly use
self-signed certs; production deployments should set
`verify_ssl=true` per device after installing a trusted cert.

## Non-functional requirements

### NFR-EXE-001 — No state between calls ✅
Executors hold no per-device or per-session state. Each call is
self-contained — credentials and operation come in as args. This
lets the same executor serve many devices concurrently with no
locking.

### NFR-EXE-002 — Credentials never logged ✅
Request summaries (`StepResult.request_summary`) include URL,
method, param names, and HTTP status — never the Authorization
header content or password values. Logs follow the same rule.

### NFR-EXE-003 — Independent of catalog loader ✅
The executor receives a parsed operation dict, not a YAML path.
This keeps it unit-testable without a catalog fixture and lets
hybrid raw-HTTP calls (ADR-0013) flow through the same path.

## Known limitations

### KL-EXE-001 — Only digest auth is fully implemented for legacy-cgi ⚠️
`LegacyCgiExecutor` does digest auth via httpx's
`DigestAuth`. Basic-auth fallback works but isn't exercised — most
Axis devices reject Basic on HTTP and require digest. HTTPS deployments
with Basic work via `httpx.BasicAuth`. The credential probe
(FR-DISC-007) tries both.

### KL-EXE-002 — SOAP support is operation-by-operation ⚠️
`SoapExecutor` works for the catalogued operations (currently
certificate management). Adding a new SOAP API still requires
manual SOAP envelope crafting in YAML — there's no auto-derived
schema from WSDL. See [ADR-0013](../decisions/0013-hybrid-yaml-and-raw.md).

### KL-EXE-003 — JSON-RPC error envelope handling is generation-specific ⚠️
Axis JSON-RPC APIs vary in how they signal errors — some use
`{"error": {...}}`, some put errors in `data.status`. The
executor's parser handles the common cases but new APIs may need
per-operation `response.error_path` hints (planned).

### KL-EXE-004 — No request retry on transient failures ⚠️
A single 503 or connection reset surfaces as a failed StepResult.
The plan engine's FailurePolicy.CONTINUE keeps the rest of the
plan moving, but the failed step doesn't retry. Devices that
flake on first contact (just-rebooted) need an explicit health
check step rather than an automatic retry. See
[reliability.md](reliability.md) KL-REL-002.

## References

- ADRs: [0007](../decisions/0007-per-protocol-auth.md), [0013](../decisions/0013-hybrid-yaml-and-raw.md), [0018](../decisions/0018-expect-timeout-semantics.md)
- Cross-cutting: [reliability.md](reliability.md), [security.md](security.md)
- Sibling: [catalog.md](catalog.md), [plans.md](plans.md)
- Code: `admz/executor/`
