# ADR-0018: `expect_timeout` semantics for reboot-style operations

**Status:** Accepted, in production.
**Date:** Original design 2026-03; recorded as ADR 2026-05-18.

## Context

Some operations are *supposed* to make the device disappear:
- `restart.cgi` — graceful reboot
- `factorydefault.cgi:factory-reset` — wipe and reboot
- `hardfactorydefault.cgi:hard-factory-reset` — power-cycle wipe
- `firmwaremanagement.cgi:upgrade` — flash firmware then reboot

The executor's normal contract: HTTP request completes → parse
response → return `StepResult(success=True)`. For reboot ops, the
device drops the connection mid-response. From `httpx`'s perspective
that's a `TimeoutException` (or `ConnectError`). From the operator's
perspective the operation worked exactly as intended — the timeout
*is* the success signal.

We needed a way to distinguish "the device hung up because the
operation succeeded" from "the device is unreachable because something
broke" without baking knowledge of specific CGI names into the
executor.

## Decision

Operations that expect to terminate their own connection declare it in
their YAML:

```yaml
# catalog/vapix/cgi/restart.cgi/unversioned/restart.yaml
id: restart.cgi:restart
risk_level: dangerous
response:
  format: text
  expect_timeout: true   # <-- the marker
```

The executor (`admz/executor/vapix.py`) handles
`httpx.TimeoutException` specifically: if `operation["response"]["expect_timeout"]`
is True, it converts the timeout into a success with a warning:

```python
StepResult(
    success=True,
    warnings=[
        f"Request timed out after {effective_timeout}s "
        "(expected — device is rebooting)"
    ],
)
```

Operations that don't declare it get the normal failure mode — a
timeout returns `success=False`.

## Consequences

**Positive:**
- The executor stays generic — no list of "restart-like CGIs" embedded
  in code.
- New reboot-style operations get correct behavior by adding a flag
  to their YAML; no Python change.
- The warning surfaces the asymmetry to the LLM/operator: "this
  succeeded, but check back in 30 seconds to confirm the device came
  up."

**Negative:**
- If a non-reboot operation legitimately times out, the catalog
  better not have `expect_timeout: true` on it. Sanity check:
  `risk_level: dangerous` operations with this flag are a tiny set
  (≤6 today); reviewable.
- The success-with-warning return shape makes plan engine logic
  slightly more nuanced — "did this step succeed?" isn't just a bool
  for these ops.

**Alternatives considered:**
- **Hardcode the CGI list in the executor.** Rejected: violates
  ADR-0003's "catalog is data" principle and forces a Python release
  every time a new reboot-shaped operation lands.
- **Catch all timeouts as success.** Obviously wrong — masks real
  failures.

## References

- Catalog operations using this flag:
  - `cgi/restart.cgi/unversioned/restart.yaml`
  - `cgi/factorydefault.cgi/unversioned/factory-reset.yaml`
  - `cgi/hardfactorydefault.cgi/unversioned/hard-factory-reset.yaml`
  - `cgi/firmwaremanagement.cgi/1.0/upgrade.yaml`
- Code: `admz/executor/vapix.py::VapixExecutor.execute` — `TimeoutException` handler
- Requirements: [executor](../requirements/executor.md), [reliability](../requirements/reliability.md)
