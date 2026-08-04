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

### Amendment 2026-08-04 — a profile may not be *learned* down to Basic on a plaintext channel (#171)

The decision above says the stored profile is detected from the device's own
`WWW-Authenticate` header, and `_send_self_healing` re-detects it on a 401 at
request time. That header is **attacker-controlled**: anything answering at the
device's address can offer `Basic realm="x"`, and ADMZ would relearn Basic and
retry — with `httpx.BasicAuth`, which sends
`Authorization: Basic base64(user:pass)` **preemptively on the first request**.
Under Digest the password never crosses the wire at all, so this is a genuine
escalation rather than a restatement of network access, and it persists.

**The bound:** the executor refuses to **learn** `basic` from a challenge when
the channel is not TLS. It proceeds without learning and returns the 401; it
does not raise, because the request genuinely did 401 and every caller already
handles that.

Three things this deliberately does *not* do, each load-bearing:

1. **It does not refuse to *use* Basic over HTTP.** A device whose stored
   profile already says `{"http": "basic"}` — because an operator configured it,
   or the `credential_probe` detected it on first contact — authenticates on the
   first attempt and never reaches the relearn branch. That is the operator's
   escape hatch, and it is why the rule can ship without a pin surface.
2. **It is not a "protection may only increase" ratchet.** Such a rule would
   strand any camera legitimately reconfigured downward, break the *safe*
   Digest→Basic-over-HTTPS relearn (the Axis "Recommended" posture this ADR
   exists to support), and still not prevent the leak — the credential is sent
   before the learned profile is ever evaluated. It looks stronger and is
   strictly worse.
3. **It does not touch Digest→Basic over HTTPS.** That is the Axis default and
   the plaintext rides inside TLS. With `ADMZ_VERIFY_SSL=false` an on-path
   attacker can still terminate that TLS and read it; that is a known residual,
   not something this amendment closes.

The narrowness is affordable precisely *because* of the policy recorded in
Context above: Axis's "Recommended" policy mandates digest-over-HTTP and
basic-over-HTTPS, so Basic-over-plaintext is the one combination that is both
dangerous and abnormal — not a posture a stock Axis device adopts.

Because the credential is spent before persistence, the check sits in
`_send_self_healing` *before the retry is issued*. Anything acting at
persistence time is too late; see ADR-0039, which owns that half.

Full reasoning, the measurement, and the residual leaks this does not close:
[plans/auth-downgrade-defence.md](../plans/auth-downgrade-defence.md).

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
