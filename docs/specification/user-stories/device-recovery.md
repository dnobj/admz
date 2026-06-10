# User stories: device recovery

After a reboot/restart-class operation, the device goes offline for ~30–90 s
and recovers on its own. ADMZ should be able to *watch* that recovery tail and
report concretely whether the device came back — instead of leaving the
operator to guess. Implements [GH #49](https://github.com/dnobj/admz/issues/49) v1.

## US-REC-001 — "Is it back up yet?" after an approved reboot

**As an** operator who just approved a reboot in chat, **I want to** ask "is
it back?" and get a concrete answer, **so that** I know when it's safe to keep
working with the device.

**Acceptance criteria:**
1. After an approved reboot executes (or when the user asks "is it up yet?"),
   the assistant calls `await_device_recovery(device_id)` — not
   `get_device_health` (whose cache lags reboots).
2. A returned `status="recovered"` reports it concretely (e.g. "back online
   after 47 s"), evidenced by a changed `bootid` or a fresh uptime — not just
   a single healthy ping on the pre-reboot boot.
3. If the device comes back factory-defaulted (`needsetup: true`), the
   assistant says so — it needs provisioning, not just a reconnect.

**Related requirements:** [device-recovery](../requirements/device-recovery.md), [mcp-server](../requirements/mcp-server.md).

## US-REC-002 — Keep waiting across the chat watchdog

**As an** operator on a device with a slow boot, **I want** the recovery check
to keep waiting past a single tool call, **so that** a long reboot still gets a
definitive answer without the chat turn timing out.

**Acceptance criteria:**
1. A reboot that hasn't completed within `timeout_s` (default 90, kept under
   the ~120 s chat watchdog) returns `status="still_waiting"` with a
   `baseline_bootid`.
2. The assistant re-invokes `await_device_recovery` passing that
   `baseline_bootid` (up to ~2 more times) so detection continues across
   calls, then concludes the device may need power/network attention if it
   still hasn't returned.
3. The continuation reliably detects the down→up transition even though it
   spans multiple calls (the baseline carries the pre-reboot boot id).

**Related requirements:** [device-recovery](../requirements/device-recovery.md), [web-chatbot](../requirements/web-chatbot.md).

## US-REC-003 — Don't be fooled by a too-early or wrong-creds check

**As an** operator, **I want** the recovery check to be honest about edge
cases, **so that** I'm not told "recovered" when it wasn't, or left waiting
when the device is actually up but rejecting credentials.

**Acceptance criteria:**
1. A check that runs *before* the device goes down (it answers healthy with
   the old boot id and high uptime) is **not** reported as recovered — it
   keeps polling for the real down→up transition.
2. A device that is up but rejecting credentials returns
   `status="auth_failed"` within a couple of probes rather than burning the
   full timeout.
3. A single transient `401` mid-boot does not abort — only two consecutive
   auth failures do.

**Related requirements:** [device-recovery](../requirements/device-recovery.md).

## Known limitations

- ⚠️ **Synchronous v1 only.** No background job, REST endpoint, or live UI
  card yet — a long reboot relies on the assistant re-invoking with the
  `baseline_bootid`. The job-store + live-card design is open in #49 as v2.
- 📋 **No automatic post-reboot reconciliation.** Recovery reports the device
  is back; acting on a `needsetup` device (re-provisioning) is a separate,
  explicit follow-up.
