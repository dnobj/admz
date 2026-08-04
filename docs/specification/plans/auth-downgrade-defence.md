# Plan: refuse to learn Basic-over-HTTP from a device challenge (GH #171)

## Context

`VapixExecutor._send_self_healing` relearns a device's connectivity profile from what the
far end says, and `run_execution_tail` persists it. #171 reports that a device — or anyone
answering at its address — can drive ADMZ from Digest down to **Basic over plain HTTP**,
putting the stored device admin password on the wire in base64, permanently.

The finding is real. An orientation pass verified it against master @ `b456ba3`, disproved
one of its sub-claims, corrected its `verify_ssl` reasoning, and found an amplification it
missed. This plan carries that forward, and settles the five things a fix has to decide.

The constraint that shapes everything below: **ADMZ must keep relearning.** Cameras really
do change auth policy, and a blanket "never downgrade" ratchet would strand a legitimately
reconfigured device *and* would not stop the leak — which happens before persistence. That
is the #250 shape, where the obvious fix destroys the thing it protects.

## Exploration verified (against `plan/auth-downgrade-defence`, cut from master @ b456ba3)

### The mechanism, quoted

`admz/executor/vapix.py:501-513` — the credential-exposing branch:

```python
        if response.status_code == 401:
            offered = _auth_method_from_challenge(
                response.headers.get("www-authenticate")
            )
            if offered and offered in ("basic", "digest") and offered != method:
                retry = await self._open_and_send(
                    scheme, host, port, request,
                    self._auth_for_method(offered, credentials), timeout,
                )
                if retry.status_code != 401:
                    response, method = retry, offered
                    learned = {**(learned or {}), "scheme": scheme, scheme: method}
```

`_auth_method_from_challenge` (`vapix.py:41-55`) is a substring match preferring Digest, so
an attacker offering *only* `Basic realm="x"` selects Basic. `_auth_for_method`
(`vapix.py:534-535`) returns `httpx.BasicAuth`. Persistence: `vapix.py:337-338` sets
`result.learned_auth`; `operations.py:233-235` is the **only** reader and passes it to
`_persist_learned_auth` (`operations.py:240-257`), which merges into the device record,
writes on delta only, and logs at INFO with **no audit row**.

### Measured, not argued

An in-process `httpx.MockTransport` probe (no sockets, no device) reproduced the exchange:

```
Digest attempt   req 1: Authorization = None            <- password never leaves
Basic retry      req 1: Authorization = Basic cm9vdDpzM2NyM3QtZmxlZXQtcHc=
                                        -> 'root:s3cr3t-fleet-pw'    PREEMPTIVE
attacker returns 500 (so nothing is persisted): 1 Authorization already sent
```

Three consequences, and each one constrains the design:

1. Under Digest the password genuinely never crosses the wire, so the downgrade is a real
   escalation rather than a restatement of network access.
2. `httpx.BasicAuth` sends the credential **preemptively on the first request**, before any
   response is seen.
3. **The leak precedes the acceptance test** at `vapix.py:512`. Anything that acts at
   persistence time is too late. This is why the fix has to sit before the retry is issued.

### One sub-claim of #171 is wrong

#171 states: *"For a device configured https/basic (the Axis Recommended default), refusing
TCP 443 is sufficient on its own."* It is not. The `ConnectError` flip calls
`_method_for_scheme(device, alt_scheme)` (`vapix.py:518-524`), which looks up the method for
the **new** scheme, and `_detect_auth_schemes` (`discovery/credential_probe.py:115-155`)
stores *both* protocol keys. Exercised:

```
profile {'http': 'digest', 'https': 'basic', 'scheme': 'https'}
443 refused -> _method_for_scheme(device, 'http') = digest      <- not basic
```

So the scheme flip is a real transport downgrade, and it *is* persisted, but it leaks no
credential by itself. **There is one credential-leaking input, not two: the
`WWW-Authenticate` header.** That is what the narrow rule targets.

### The amplification #171 missed

`admz/provisioning.py:129-136` prefers the fleet `default_password` over a generated one:

```python
    if password:
        new_password, source = password, "provided"
    else:
        fleet_default = fleet_settings.get("default_password")
        if fleet_default:
            new_password, source = fleet_default, "fleet_default"
```

Where that setting is set, **one leaked camera is a fleet-wide compromise**. This is the
single largest factor in the blast radius and it is not addressed by anything in this plan —
see "What this does not fix".

### A second, simpler downgrade path that needs its own issue

`update_device`'s MCP schema (`mcp/server.py:735-753`) declares `updates` as a bare
`{"type": "object"}`, and `_update_device` (`mcp/server.py:2211-2223`) passes it straight to
`registry.update_device`, which does `info.update(updates)` (`sqlite_backend.py:504-521`).
There is **no protected-device-key list anywhere in the tree**, and `update_device` is not
gated, risk-classified, or in the destructive-tool set.

So a model can today write `updates={"auth": {"scheme": "http", "http": "basic"}}` and reach
the same persistent end state as #171 with **no device, no network position, and no
challenge header**. That is out of scope here, but it is a hard dependency for D2 — see
below — and it should be filed separately.

---

## D1 — The narrow rule

**Refuse to *learn* Basic when the channel is plaintext HTTP.**

**Where.** In `_send_self_healing`, inside the `if response.status_code == 401:` branch,
**before** `self._open_and_send(...)` is called with the Basic auth object. Not at
persistence — measured above, that is too late.

**What it compares.** Three values already in scope at that point:

| | |
|---|---|
| `offered == "basic"` | the method the challenge asks for |
| `scheme == "http"` | the channel we would send it over |
| no operator pin for `(device, "http", "basic")` | D2 |

All three must hold for the refusal to fire. Every other combination is untouched:
Basic→Digest, Digest→Basic **over HTTPS**, `none`→anything, and both `ConnectError` scheme
flips continue exactly as today.

**What it does on refusal — proceed without learning, do not raise.** The retry is skipped
and the original `401` response is returned to the caller unchanged.

That choice is deliberate and the alternative was considered. Raising a new exception would
introduce a failure mode through every caller of the executor — the health monitor
(`fleet/health.py:468, 523, 595`), the plan engine, MCP and REST — turning a device blip into
an unhandled error in paths that today handle only `ConnectError`/`TimeoutException`. And it
would not be more truthful: the request *did* fail with a 401, which is exactly what the
caller is equipped to report. Returning the 401 keeps the existing error surface and loses
nothing, because the alternative to refusing is not "success", it is "success purchased with
a plaintext password".

The refusal is **loud**: a `WARNING` naming the device and the challenge, plus the audit row
from D3. A silent refusal would reproduce the original defect in the opposite direction.

**Why this specific combination and not a general rule.** ADR-0007 records that *"Axis's
'Recommended' auth policy on AXIS OS 11+ explicitly mandates digest-over-HTTP and
basic-over-HTTPS."* Basic-over-HTTP is therefore not a posture a stock Axis device adopts —
it is the one combination that is both dangerous and abnormal. That is what makes a targeted
rule affordable where a ratchet is not.

**Evidence it does not break the feature.** `tests/test_executor_self_healing.py:95-105`
(`test_method_relearn_digest_to_basic`) exercises the relearn with `scheme="https"`, which
this rule **permits**, and no test in the suite asserts a Basic-over-plain-HTTP relearn.
So the narrow rule passes the existing suite unchanged, where a blanket ratchet would fail
`test_method_relearn_digest_to_basic` outright.

### Honest cost

This *does* strand a device genuinely configured Basic-over-HTTP, until an operator pins it.
That is a real regression for that one configuration, and the plan should not pretend
otherwise. It is acceptable because (a) ADR-0007 says stock Axis does not produce it,
(b) the failure is loud and explains itself rather than silent, and (c) D2 gives the operator
a documented way out. A blanket ratchet strands *every* downgrade combination, silently, and
still leaks — which is the distinction.

## D2 — The operator pin, and its blocking dependency

**Shape.** Per-device, because the need is per-device. A device record gains an explicit
`auth_pin` key, separate from `auth`:

```python
device_info["auth_pin"] = {"http": "basic"}   # operator-approved, this device only
```

Separate from `auth` on purpose: `_persist_learned_auth` does `merged.update(learned)`, so
anything living inside `auth` shares a namespace with the values self-heal rewrites. A
distinct top-level key cannot be clobbered by that merge and is trivially readable at the
decision point.

**Not LLM-writable — and this is the part that needs work first.** ADR-0053 inverted fleet
settings to deny-by-default after the enumerated deny-list failed four times in the same
direction (#152, #168, #195, #203). The same reasoning applies here with more force, because
`auth_pin` exists specifically to re-enable the thing the rule forbids.

But `LLM_WRITABLE_SETTING_KEYS` governs **fleet settings**, and `auth_pin` is **device
info** — a namespace with no protection at all today. As established above, `update_device`
accepts an unconstrained `updates` object and is ungated, so a pin placed in device info
would be writable by the model on day one, and so would the `auth` dict it protects.

**Therefore D2 is blocked on closing that gap**, and the plan should not pretend a pin is
meaningful before it is. Two options, to be decided when that issue is picked up:

1. **A protected-device-key set** mirroring `PROTECTED_SETTING_KEYS` — deny-by-default over
   `update_device`'s `updates`, with `auth`, `auth_pin` and credentials in it. Fixes the
   larger hole and the pin together. Preferred.
2. **Keep the pin out of device info entirely** — an env var or a config file the MCP surface
   cannot reach. Cheaper, but leaves `auth` itself writable, which is the bigger problem.

Recommendation: (1), as a prerequisite issue rather than part of this change.

**Interaction with `setting_policy.py`:** none, if the pin is device info. If a future
revision moves it to a fleet setting it must be added to `KNOWN_SETTING_KEYS` and **not** to
`LLM_WRITABLE_SETTING_KEYS`, and it would then be protected automatically by
`is_protected_setting`'s deny-by-default.

## D3 — The audit row

`_persist_learned_auth` (`operations.py:240-257`) logs at INFO and writes no audit row. A
device's auth profile silently becoming weaker is exactly what the audit trail is for.

Follow #276's precedent (`api/routes/confirm.py:308-318`): an **explicit allow-list of
identifier fields, key-only, with a comment saying it must stay one** — never `**learned`
and never anything derived from credentials.

```python
audit_log.record(
    requester=..., action="device.auth_profile_changed", resource=f"device:{device_id}",
    details={
        # Allow-listed identifiers ONLY. Never the credential, never the
        # WWW-Authenticate header verbatim, never **learned. This list must
        # stay an allow-list: the values here are chosen, not spread.
        "from_scheme": ..., "from_method": ...,
        "to_scheme": ...,   "to_method": ...,
        "trigger": "challenge" | "connect-error",
        "pinned": bool,
    },
)
```

`AuditLog.record` (`audit.py:152-166`) already swallows DB errors with a warning, so adding
this cannot break an operation.

Emit it on **every** profile change, not only downgrades — an upgrade is equally worth
seeing, and a rule that only records the bad case tells you nothing about the baseline.

## D4 — The unauthenticated probe: recommended NO, and here is why

#171 suggests that on `ConnectError`, ADMZ should retry the alternate scheme
*unauthenticated* first, to confirm something Axis-shaped is there before spending the
credential. On inspection this buys much less than it appears to, and the plan declines it
as a security measure.

An attacker who wants the credential simply answers the probe with a `401`. The probe
distinguishes "something is listening" from "nothing is listening"; it does not distinguish
the real device from an impersonator, which is the actual threat. Against an active attacker
it is worth approximately nothing.

Its residual value is against *accidental* misdirection — an unrelated service on port 80,
a recycled DHCP lease — where it would stop the credential going somewhere merely wrong
rather than hostile. That is a real but small benefit.

**Cost:** one extra round trip, only on the `ConnectError` path, which already involves a
TCP refusal and is the slow path by definition. So it is cheap. It can be skipped entirely
when the alternate scheme's method is `none` (nothing to spend).

**Recommendation:** treat it as optional hygiene, not as part of the #171 fix, and do not let
its presence create the impression that the flip is now safe. Note also that after D1 the
flip alone cannot select Basic-over-HTTP anyway — `_method_for_scheme` returns the
per-scheme method, measured above — so the credential it would protect is a Digest exchange,
which does not transmit the password.

## D5 — What this does NOT fix

State these in the PR. Each is a place someone could reasonably assume more was delivered.

1. **Digest→Basic over HTTPS is untouched, by design.** `{"https": "basic"}` is the Axis
   default, so this is the *normal* path and the plaintext rides inside TLS. With
   `ADMZ_VERIFY_SSL=false` (the default, #1) an on-path attacker can terminate that TLS and
   read it. This is a residual leak and the narrow rule does not close it.
2. **A compromised device reads the Basic credential regardless.** It is the legitimate TLS
   endpoint. No transport rule can help; the only defences are not using Basic at all, or
   not sharing one credential across the fleet.
3. **The fleet-wide `default_password` amplification is orthogonal and probably matters
   more.** Per-device credentials would turn a fleet compromise back into a single-device
   one. That is a bigger and separate piece of work.
4. **Anything acting at persistence time is too late** — measured. D3's audit row makes the
   downgrade *visible*, it does not prevent the leak. Do not let the audit row be mistaken
   for the fix.
5. **`update_device` remains unguarded** until the prerequisite issue lands, so the profile
   this rule protects can still be rewritten directly through the MCP surface.

## Not a blanket ratchet

Recorded explicitly because it is the failure mode this design is steering around, and a
future reader will be tempted by it.

A general "protection may only increase" rule over `(scheme, method)` would: strand any
camera legitimately reconfigured downward, break
`test_method_relearn_digest_to_basic` (which relearns to Basic over HTTPS, a *safe*
downgrade), and still not prevent the leak, because the credential is sent before the
learned profile is evaluated. It looks stronger and is strictly worse. If a proposal starts
drifting toward it, that is the signal to stop.

## ADR — amend ADR-0007, cross-reference ADR-0039

**Recommendation: amend [ADR-0007](../decisions/0007-per-protocol-auth.md).**

ADR-0007 owns per-protocol auth detection and storage, and already states the Axis
`Recommended` policy that this rule rests on. What changes is a constraint on *how that
profile may be learned* — the same decision, one layer deeper — so it belongs there rather
than in a new record. A new ADR would imply a new architectural direction; this is a bound on
an existing one.

[ADR-0039](../decisions/0039-platform-and-pluggable-modules.md) owns the persistence half
(`self_heals()`, `admz/executor/base.py:24`) and should gain a cross-reference to the
amended section, because the audit row in D3 lands on its side of the boundary.

## Risks

| risk | mitigation |
|---|---|
| A device genuinely on Basic-over-HTTP becomes unreachable | Loud 401 + WARNING + audit row naming the device; D2's pin. ADR-0007 says stock Axis does not produce this posture |
| The rule is read as closing #171 completely | D5 is explicit that HTTPS Basic and the fleet credential remain |
| The pin becomes a model-writable bypass | D2 is blocked on the `update_device` guard; do not ship the pin before it |
| The audit row leaks a credential | Allow-list, key-only, with a comment; #276's precedent and its review |
| Someone "simplifies" the rule into a ratchet | The section above, plus `test_method_relearn_digest_to_basic` failing under it |

## Tests

- **The rule fires:** challenge offers Basic on `scheme="http"` → no Basic retry is issued,
  the 401 is returned, `learned is None`. Assert on the *requests seen* by a
  `MockTransport`, not only the return value — the property is "no `Authorization: Basic`
  crossed the wire", which is what the orientation probe measured.
- **The rule does not over-fire:** the same challenge on `scheme="https"` still relearns —
  i.e. `test_method_relearn_digest_to_basic` passes unchanged.
- **Anti-vacuity:** pair every refusal case with an acceptance case on the same fixture. "No
  Basic on the wire" is trivially true if the request never happened, so assert the Digest
  attempt *did* occur.
- **The pin re-enables it** (once D2's prerequisite lands), and only for the pinned device.
- **The audit row** contains the identifier fields and, asserted explicitly, does **not**
  contain the password or the raw challenge header.

## Out of scope (follow-up issues)

- **`update_device` accepts an unconstrained `updates` and is ungated** — a model can rewrite
  `auth` directly, reaching #171's end state with no device involved. Needs its own issue;
  D2 is blocked on it.
- **Fleet-wide `default_password`** — the blast-radius multiplier. Per-device credentials are
  a separate design.
- **#1 (`ADMZ_VERIFY_SSL=false`)** stays closed. The orientation pass established that where
  #171 is worst — the attacker *is* the device — `verify_ssl` is irrelevant, because a
  compromised camera is the legitimate TLS endpoint; and the case where it matters still
  needs the LAN position #1 already assumed. Recorded so the surface resemblance does not
  reopen it.

## Critical files

| file | role |
|---|---|
| `admz/executor/vapix.py:501-513` | where D1's check goes — before the retry, not after |
| `admz/executor/vapix.py:41-55` | `_auth_method_from_challenge`, the attacker-controlled input |
| `admz/executor/vapix.py:518-524` | `_method_for_scheme` — why the flip alone selects digest |
| `admz/operations.py:240-257` | `_persist_learned_auth` — D3's audit row |
| `admz/audit.py:152-166` | `AuditLog.record`, already failure-tolerant |
| `tests/test_executor_self_healing.py:95-105` | the test proving the rule is narrow enough |
| `admz/mcp/server.py:735-753, 2211-2223` | the unguarded `update_device` path D2 depends on |
| `docs/specification/decisions/0007-per-protocol-auth.md` | the ADR to amend |
