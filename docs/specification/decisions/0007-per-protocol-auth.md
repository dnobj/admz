# ADR-0007: Per-protocol auth detection and storage

**Status:** Accepted, in production.
**Date:** Original design 2026-03; recorded as ADR 2026-05-18.

## Context

Axis devices have **per-protocol auth policies**. On the same device:
- HTTP requests may require **digest** authentication.
- HTTPS requests may require **basic** authentication (because TLS
  already protects the credential in transit).
- Some operations may use **bearer** tokens.
- Factory-default devices may accept **no auth** for a small subset
  of endpoints (the device-discovery surface).

Axis's "Recommended" auth policy on AXIS OS 11+ explicitly mandates
digest-over-HTTP and basic-over-HTTPS. If ADMZ blindly uses one auth
scheme regardless of protocol, half the operations on a modern device
return 401 even with valid credentials.

## Decision

ADMZ **probes** each scheme on first contact (typically during
`provision_device` or `test_device_credentials`) and **persists**
the detected method per protocol on the device record:

```yaml
# in registry: device_info["auth"]
auth:
  http: digest
  https: basic
  scheme: http   # preferred default scheme
```

The probing logic (`admz/discovery/credential_probe.py::_detect_auth_schemes`)
sends a no-auth request and parses the `WWW-Authenticate` header from
the 401 response. The result is stored in `device_info["auth"]`.

The executor (`admz/executor/vapix.py::_resolve_auth`) uses the
scheme-appropriate handler at request time:

```python
def _resolve_auth(device, credentials, scheme="http"):
    auth_info = device.get("auth", {})
    method = auth_info.get(scheme) or device.get("auth_method", "digest")
    if method == "digest": return httpx.DigestAuth(...)
    if method == "basic":  return httpx.BasicAuth(...)
    if method == "bearer": return _BearerAuth(...)
    if method == "none":   return None
    ...
```

Legacy `auth_method` (a single string) is supported as fallback for
devices added before the per-protocol probe existed.

## Consequences

**Positive:**
- ADMZ Just Works on devices following Axis's recommended policy
  without operator configuration.
- The auth dict is JSON-serializable and lives in the same
  `device_info` blob — no schema migration.
- The probe is cheap (one 401 round-trip per scheme per device) and
  cached on the device record forever.

**Negative:**
- The probe code path adds complexity. Devices with weird auth
  configurations (custom realms, OAuth) need executor changes.
- If an operator changes the device's auth policy from Axis's defaults
  manually (e.g. via the device's web UI), the cached value drifts.
  Re-probing via `test_device_credentials` re-detects.

**Alternatives considered:**
- **Always use digest.** Rejected — basic-over-HTTPS is what Axis
  recommends for AXIS OS 11+ and what some endpoints (REST APIs)
  require.
- **Probe per request.** Rejected — adds latency for every operation;
  the auth policy doesn't change often.

## References

- ADR-0008 — MCP + REST surfaces (which routes go through the executor)
- ADR-0009 — OOB credential capture
- Requirements: [executor](../requirements/executor.md), [credential-storage](../requirements/credential-storage.md)
- Code: `admz/discovery/credential_probe.py`, `admz/executor/vapix.py`
- VAPIX docs: <https://developer.axis.com/vapix/authentication/>
