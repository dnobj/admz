# ADMZ MCP Tools Reference

Reference for the **75 tools** the ADMZ MCP server exposes (plus whatever an
enabled platform module appends — ACS Pro contributes its own once connected).
The frozen wire order lives in `tests/test_mcp_tool_order.py`.

> Note: a `get_credentials` MCP tool used to exist. It was **removed**
> (CR-1) because returning plaintext passwords into LLM context violates
> the project's stated invariant. Use `create_temp_credentials` when the
> LLM needs to authenticate against a device.

> Known gap, flagged rather than papered over: eight tools shipped without an
> entry here — `search_activity`, `demo_setup_status`, `survey_demo_evidence`,
> `infer_demos`, `list_demo_proposals`, `confirm_demo_proposal`,
> `dismiss_demo_proposal`, and `set_event_ingest`. Their schemas and
> descriptions are authoritative in `admz/mcp/tools/`.

Group key:
- 🗂 = registry + accounts
- 🩺 = health + reboot recovery
- 🔐 = out-of-band credential capture
- 🔑 = provisioning &amp; temp credentials
- 📡 = network discovery
- 📚 = catalog + knowledge + capabilities
- ⚙️ = operation execution
- 📋 = multi-step plans
- 📸 = snapshot / restore / drift
- ⏰ = scheduled snapshots
- 🎛 = fleet settings
- 💾 = firmware
- 🧯 = advanced capability inventory (read-only)

---

## 🗂 Devices & accounts

### `list_devices`
List every device in the registry (no credentials returned).
- **Args:** none
- **Returns:** `{success, count, devices}`

### `get_device`
Get one device by ID or nickname.
- **Args:** `device_id` (string, also accepts nickname)
- **Returns:** `{success, device}`
- **Errors:** `DeviceNotFound`

### `search_devices`
Search by tags, location, or model.
- **Args:** `tags` (array), `location` (string), `model` (string) — all optional
- **Returns:** `{success, count, devices, filters}`

### `register_device`
Add a new device, then resolve its credentials automatically (see
`onboard_device` for the resolution order).
- **Args:** `device_id`, `device_info` (object), `accounts` (object, optional)
- **Returns:** `{success, device_id, onboarding: {status, …}}`
- **Errors:** `BackendError` (duplicate)

### `onboard_device`
Resolve credentials for a registered device server-side — no password
enters the conversation. Order: verify stored credentials
(`already_credentialed`) → factory-defaulted device auto-provisioned from
fleet settings (`provisioned`) → fleet `default_username`/`default_password`
pair tried and saved if it authenticates (`fleet_credentials_saved`) →
otherwise a capture session is opened (`credentials_needed` +
`capture_url`; the chat console renders it as a secure form card).
`register_device` runs this automatically for new devices.
- **Args:** `device_id`
- **Returns:** `{status, device_id, message, …}` (never a password)

### `update_device`
Merge updates into a device's information.
- **Args:** `device_id`, `updates` (object)
- **Returns:** `{success, device_id, updates}`
- **Errors:** `DeviceNotFound`

### `update_device_tags`
Add and/or remove tags on a device — the ergonomic way to edit tags
(preserves the device's other tags; deduped, order-preserving). Metadata
only, not gated.
- **Args:** `device_id`, `add` (array, optional), `remove` (array, optional)
- **Returns:** `{success, device_id, tags, added, removed}`
- **Errors:** `DeviceNotFound`

### `delete_device`
Request removing a device and its accounts (ADR-0034: **widget-gated**).
- **Args:** `device_id`
- **Returns:** a blocked envelope `{blocked, confirm_token, confirm_url, ...}`
  — the registry row is removed only after the user approves the on-screen
  confirmation card. The physical device is untouched; git config history
  is retained.

### `list_accounts`
List accounts on a device (no passwords).
- **Args:** `device_id`
- **Returns:** `{success, count, accounts}`

### `add_account`
Add an account to a device.
- **Args:** `device_id`, `account_id`, `account_data` (object — typically
  `username`, `password`, `type`)
- **Returns:** `{success, device_id, account_id}`

### `delete_account`
Remove an account from a device.
- **Args:** `device_id`, `account_id`
- **Returns:** `{success, device_id, account_id}`

---

## 🩺 Health & recovery

### `get_device_health`
Cached reachability status for one device (from the background health
monitor — no network call fires).
- **Args:** `device_id`
- **Returns:** `{success, device_id, status, ...}`
- **Status values:** `online`, `unreachable` (the host did not answer at
  all), `limited_api` (up, and ADMZ **can** read and track it over legacy CGI
  — it just has no JSON-RPC surface; a T85 PoE switch is the usual case. Treat
  as healthy; don't promise arbitrary config pushes), `reachable_no_api` (up,
  but nothing ADMZ can read answered — genuinely unmanageable, though still
  *not* offline), `auth_failed`, `needs_setup`, `unknown`

### `get_fleet_health`
Cached reachability status for every registered device.
- **Args:** none
- **Returns:** `{success, total, counts, devices}`

### `await_device_recovery`
Wait for a device to come back after a reboot/restart. **Live-polls**
the device's `systemready` API (unlike the cached health tools) until it
confirms a completed reboot — boot id changed, uptime reset, or an
offline period followed by a healthy response.
- **Args:** `device_id`; optional `timeout_s` (default 90, clamped
  5–600 — keep ≤90 from chat, the stream aborts tool calls after ~120s),
  `poll_interval_s` (default 3, clamped 1–30), `baseline_bootid`
  (pass the value from a previous `still_waiting` result to continue
  detection across calls)
- **Returns:** `{success, recovered, status, device_id, waited_s, polls,
  offline_observed, not_ready_observed, bootid, uptime_s, needsetup,
  baseline_bootid, message}`
- **Status values:** `recovered` (definitive — evidence of a real boot
  cycle), `still_waiting` (budget exhausted; call again with the returned
  `baseline_bootid`), `auth_failed` (device is UP but rejected stored
  credentials on 2 consecutive probes — fails fast instead of polling out
  the budget)
- A healthy response on the *pre-reboot* boot (old boot id, high uptime)
  is **not** reported as recovered — the poller waits for the down/up
  transition. `needsetup: true` means the device came back
  factory-defaulted (e.g. after factory reset) and needs provisioning.
- **Errors:** `DeviceNotFound`, `OperationNotFound` (systemready missing
  from the catalog)

### `queue_device_recovery`
Pre-authorize a **trigger-based** recovery (the counterpart to the
time-based snapshot schedules). When the device next reports
factory-defaulted (`needsetup`), the health-monitor sweep automatically
re-provisions it — so a factory reset from chat doesn't block on the
~1–2 min reboot. The actual provision runs only because it was authorized
here, up front; the password comes from the fleet default and is never
shown.
- **Args:** `device_id` (required); `intent` (only `reprovision` for now);
  `username` (default `root`)
- **Returns:** `{success, queued, pending_id, device_id, trigger, message}`
- Requires an authenticated principal (anonymous may not arm it) and the
  health monitor to be enabled (it is the evaluator). The pending action
  is fire-once, expires after 24h, and is cancellable.
- **Errors:** `DeviceNotFound`, `PermissionDenied` (anonymous)

### `list_device_recovery`
List active (pending) deferred recovery actions. Read-only.
- **Args:** optional `device_id` to scope to one device (omit for all)
- **Returns:** `{success, count, pending:[{pending_id, device_id, action,
  trigger, approved_by, expires_at, description}]}`

### `cancel_device_recovery`
Cancel a still-pending deferred recovery by id.
- **Args:** `pending_id` (required)
- **Returns:** `{success, cancelled, message}` (`success: false` if it
  already fired or the id is unknown)

### `list_tasks`
Unified view of ALL automated tasks (ADR-0037): time-based **schedules**
(recurring snapshot / drift_audit / survey) AND trigger-based **detection** tasks
(one-shot — e.g. re-provision when a device returns factory-defaulted). Use for
"what's scheduled or queued?". Read-only. Creating/managing still uses the
per-kind tools (`create_snapshot_schedule` …, `queue_device_recovery` …), which
share the same store.
- **Args:** optional `device_id` (tasks targeting it), optional `kind`
  (`schedule` | `detection`)
- **Returns:** `{success, count, tasks:[{id, trigger_kind, action_type, when,
  status, …}]}` — `when` reads "every 6h" or "when on_needs_setup"

---

## 🧾 Audit search

### `search_audit_log`
Search the who-did-what audit log — every operation, **approval**, schedule run,
recovery, login, and config change. Answers "who factory-defaulted device X?",
"who approved the reboot of Y?", "what did `<user>` change today?", "what failed
in the last day?". Read-only. The definitive "who did the destructive thing" row
is usually `confirm.approve` (carries the approver + device + operation, and for
a rule create/delete the `rule_id`/`config_id` it acted on — so "who created rule
175?" joins by id, not by matching the rule name across rows).
- **Args (all optional, AND-ed):** `device_id` (matches resource + details),
  `actor` (requester substring), `action` (substring, e.g. `execute_operation`,
  `confirm.approve`, `recovery`), `query` (free text), `within` (`'24h'`/`'7d'`),
  `since`/`before` (ISO-8601 or unix), `success` (bool), `limit` (default 30,
  max 200). Always pass a time range to keep results relevant.
- **Returns:** `{success, count, window, entries:[{time, actor, auth_source,
  action, resource, success, summary, error}]}` — `summary` is a curated digest
  (op / approved_by / risk / rule_id / …), never the raw args.
- For **drift over time** use `get_drift_alerts` instead — drift transitions live
  in a separate table, not the audit log.

---

## 🔐 Out-of-band credential capture

These tools generate one-time URLs the user opens in a browser. The
password is entered there and stored directly in the registry — it
never enters the LLM context.

### `capture_credentials`
Create a capture session and return the URL.
- **Args:** `device_id`, `account_id` (default `"default"`),
  `account_type` (default `"service"`), `purpose` (string, optional),
  `base_url` (default `http://localhost:4242`, from `ADMZ_BASE_URL`)
- **Returns:** `{success, url, token, device_id, account_id, expires_in_seconds}`
- **TTL:** 10 minutes

### `check_capture_status`
Poll whether the user has entered credentials yet.
- **Args:** `token`
- **Returns:** `{success, status, device_id, account_id, message}`
- **Status values:** `pending`, `completed`, `expired_or_not_found`

---

## 📡 Network discovery

### `discover_network_devices`
Scan the local network for Axis devices. Runs mDNS, SSDP, ONVIF, ARP,
HTTP probe, SNMP in parallel and merges results by MAC.
- **Args:** `timeout` (number, default 5.0), `axis_only` (bool, default false),
  `subnet` (string, optional), `enable_ping` (bool, default false)
- **Returns:** `{success, count, devices: [...]}`
- Devices are **not** auto-registered.

### `register_discovered_device`
Add a discovered device to the registry.
- **Args:** `device_id`, `ip_address`, `mac_address` (optional),
  `model` (optional), `hostname` (optional), `device_type` (optional),
  `tags` (array, optional)
- **Returns:** a **blocked envelope** — `{success: false, blocked: true,
  risk_level, confirmation_level, confirm_token, confirm_url}`. Since #199 this
  tool registers nothing on its own: a scan chose the device, so the operator
  approves a blast radius rather than a device.
- On approval the registration **and** credential onboarding run together — and
  onboarding is the part that writes: a factory-defaulted unit gets an admin
  account created on it (`pwdgrp.cgi:add-user`, `group=root`).

> **Corrected 2026-08-04 (#214).** This entry documented the pre-gate return
> shape and said onboarding "runs automatically after registration". An agent
> written against it would treat the blocked envelope as a failure and retry,
> rather than surfacing the approval link to the operator.

### `reconcile_device_addresses`
Run a discovery scan and update any registered device whose **MAC** now
answers at a different **IP** (DHCP moved it). Follows the MAC, not the stale
IP — fixes the "looks online but ADMZ says unreachable" case. Read-only
except for correcting the stored `host`; never registers new devices.
- **Args:** `subnet` (string, optional CIDR), `timeout` (number, default 5.0)
- **Returns:** `{success, discovered, updated, changes: [{device_id,
  old_host, new_ip}], message}`

---

## 🔑 Provisioning & temp credentials

### `provision_device`
Probe a device, then take state-appropriate action: factory-default →
create admin user; legacy default → store; unknown → error. Auto-registers
the device using its MAC if `device_id` is omitted. Generated passwords
are stored under account `default` and **never returned** in the response
— the executor uses them internally, and for human login you mint a
short-lived account with `create_temp_credentials`.
- **Args:** `device_id?` or `host?` (one required), `username` (default
  `"root"`), `password?` (else fleet default or 24-char generated),
  `force_change` (bool, default `false`)
- **Returns:** `{success, device_id, host, status, action_taken,
  username, password_source, auto_registered, detail}`
- **Password source precedence:** explicit > fleet `default_password` >
  generated.

### `test_device_credentials`
Probe a host with no-auth, legacy `root/pass`, and up to 5 user-supplied
passwords. Returns auth status; passwords are never echoed.
- **Args:** `host?` or `device_id?`, `username?`, `password?`,
  `passwords` (array, max 5), `store?` (bool — save working creds to
  registry under account `default`)
- **Returns:** `{success, status, auth_method, auth, device_info, …}`
  (with `include_credentials=false` masking).

### `create_temp_credentials`
Create a short-lived device user via `pwdgrp.cgi:add-user`. Username
pattern `at_<8 hex>`, 16-char URL-safe password, TTL 60–3600s, max 3
active per device. Password **is returned in plaintext** (this is the
whole point — short-lived creds the LLM can use directly).
- **Args:** `device_id`, `permissions` (`"viewer"` | `"operator"` |
  `"admin"`), `ttl_seconds` (default 600)
- **Returns:** `{success, device_id, username, password,
  expires_at, permissions}`
- A background loop reaps expired temp users via `pwdgrp.cgi:remove-user`.

### `cleanup_temp_credentials`
No args → list active temp creds (metadata only). `device_id` →
remove expired creds for that device. `device_id + username` → remove
immediately.
- **Args:** `device_id?`, `username?`
- **Returns:** depends on call shape; metadata or removal results.

---

## 📚 Catalog, knowledge, capabilities

### `query_catalog`
Given a device and an intent (in natural language), return the relevant
catalog operations + parameter group docs. Also merges in knowledge
hints — always probes the `vapix-support` topic plus the user's intent.
- **Args:** `device_id`, `intent` (string), `family` (default `"vapix"`)
- **Returns:** `{success, operations, parameter_groups, device, risk_summary, notes}`
- **Recommended workflow:** call this first; pass the results to the LLM;
  the LLM picks an operation + params; then call `execute_operation`.

### `query_knowledge`
Look up product-specific hints for a device (separate from the catalog).
Returns advice from `catalog/knowledge/{products,series,product-lines}/`
about API support, limitations, and device-specific workflows.
- **Args:** `device_id`, `topic?` (e.g. `"vapix-support"`, `"poe"`,
  `"audio"`)
- **Returns:** `{success, device_id, model, hints: [...], levels_loaded,
  notes}`. Each hint has `id, topic, summary, text, tags, source_level,
  source_file`.

### `check_api_support`
Check whether a device's (model, firmware) supports a specific catalog
API based on the pre-populated `catalog/capabilities/models/<model>.yaml`
snapshot. Lets the LLM filter plan steps before execution rather than
discovering at execute time that the device doesn't speak the API. Omit
`api_id` to retrieve the full snapshot.
- **Args:** `device_id`, `api_id?`
- **Returns:** `{success, device_id, model, firmware, api_id, supported,
  api_version, snapshot: {firmware, discovered, api_count, apis?}, notes}`

---

## ⚙️ Operation execution

### `execute_operation`
Run a single catalog operation.
- **Args:** `device_id`, `operation_id`, `params` (object), `family` (default `"vapix"`)
- **Returns (success):** `{success: true, status_code, duration_ms, data}`
- **Returns (blocked):** `{blocked: true, risk_level, confirmation_level, reason,
  confirm_token, confirm_tool: "confirm_dangerous_operation",
  confirm_url: "/confirm/{token}", message}`
- Any operation above the configured `none` confirmation level is blocked
  **without executing**, per the multi-level policy (ADR-0006, configurable at
  `/confirm-settings`). The effective level (`llm_confirm` / `url_only` /
  `url_and_password`) is returned as `confirmation_level`. Defaults:
  read-only/normal → run inline; service-affecting → `url_only`; dangerous →
  `url_and_password` (both device-affecting classes require the deterministic
  widget by default — the LLM cannot self-approve a `url_*` gate). MCP, REST,
  and plans all enforce this identically via the
  shared core (`admz/operations.py`).

### `confirm_dangerous_operation`
Confirm and execute an operation `execute_operation` blocked at the
`llm_confirm` level. (Name kept for backward compat; works for any
`llm_confirm`-level op.)
- **Args:** `confirm_token` — must come from a prior blocked `execute_operation`
  response in this conversation.
- **Returns:** the executed result, with `confirmed: true`.
- `url_only` / `url_and_password` ops **cannot** be confirmed here — they must
  be approved via the web form at the returned `confirm_url` (which collects the
  explicit click and, for `url_and_password`, the password). Approving there now
  also **executes** the held operation.
- Tokens are single-use and expire after **5 minutes**.

---

## 📋 Multi-step plans

### `create_plan`
Validate and stage a multi-step plan.
- **Args:** `description` (string), `steps` (array of `{operation_id,
  device_id, params, depends_on?, description?}`), `on_failure`
  (`"stop"` | `"skip_dependents"` | `"continue"`, default `"stop"`)
- **Returns:** `{plan_id, description, step_count, risk_summary, steps,
  dangerous_steps}`
- Plan is staged but **not executed**.

### `execute_plan`
Execute an approved plan. Steps on different devices run in parallel.
- **Args:** `plan_id`, `confirm_dangerous` (bool, default `false`)
- **Returns (executed):** `{success, plan_id, status, steps_total,
  steps_succeeded, steps_failed, steps_skipped, results, rollback_available}`
- **Returns (blocked):** the plan goes through the **same per-risk gate** as a
  single op (ADR-0005/0006). Its required level is the strictest level across
  its steps. `llm_confirm`-tier plans run when called with
  `confirm_dangerous: true` (else `{blocked: true, retry_with:
  {confirm_dangerous: true}}`); `url_*`-tier plans return `{blocked: true,
  confirm_url}` and must be approved via the web form (which then runs the
  plan). Under default config a `dangerous` step ⇒ `url_and_password` ⇒
  web/widget approval required.

### `get_plan_status`
Check progress of a running plan.
- **Args:** `plan_id`
- **Returns:** `{success, plan_id, status, completed_steps, total_steps, ...}`

---

## 📸 Snapshots, restore, drift

All snapshots commit to a local git repo at `$ADMZ_CONFIG_REPO_PATH`.
Set `$ADMZ_CONFIG_REPO_REMOTE` to also push to a remote.

### `snapshot_device`
Capture a device's full configuration and commit to git.
- **Args:** `device_id`, `message` (string, optional commit message)
- **Returns:** `{success, device_id, status, git_sha, facets_succeeded,
  facets_failed, succeeded, failed}`

### `snapshot_fleet`
Snapshot many devices in parallel into a single commit.
- **Args:** `tag_filter` (string, optional), `message` (string, optional)
- **Returns:** `{success, count, results: [...]}`

### `restore_device`
Build a plan that restores a device to a previous configuration. **Omit
`ref` to revert the device to its blessed baseline** (the usual "undo this
drift" case, ADR-0031); pass a ref to restore another point in history.
- **Args:** `device_id`, `ref` (optional — default: the device's
  `baseline_sha`), `facets` (array, optional)
- **Returns:** `{success, plan_id, steps, warnings, source_ref}`
- Does **not** execute — call `execute_plan` after review.

### `accept_baseline`
Accept/promote an observed configuration as a device's new blessed
**baseline** (ADR-0031). Use after `check_drift` when the user confirms the
drift is intentional. Metadata-only (no device traffic), but it re-points
what drift means and what restore replays — so it executes only via the
standard link/widget approval (ADR-0034).
- **Args:** `device_id`, `commit_sha` (optional — default: the device's
  latest recorded observation)
- **Returns:** a blocked envelope `{blocked, confirm_token, confirm_url, ...}`
  (ADR-0034) — the baseline is re-pointed only after the user approves the
  on-screen confirmation card.
- Errors immediately (no widget) when there is no observation to accept, or
  when the target commit holds no config for the device.

### `diff_device`
Show config changes for a device between two refs.
- **Args:** `device_id`, `ref_a` (default `"HEAD~1"`), `ref_b` (default `"HEAD"`)
- **Returns:** `{success, device_id, ref_a, ref_b, diff, recent_history}`

### `check_drift`
Compare a device's live state against its **baseline** (`baseline_sha`), not
git HEAD (ADR-0031). Each check also **records what it observed** into the git
config repo as an `Audit:` commit (commit-on-change — an unchanged device
records nothing new) and advances the device's `latest_observed_sha`; an audit
never moves the baseline pointer.
- **Args:** `device_id` (optional — if omitted, scans whole fleet),
  `tag_filter` (string, optional)
- **Returns:** single device: `{success, device_id, has_drift, no_baseline,
  observed_sha, facets_checked, facets_drifted, drifted_fields}`
  (`no_baseline=true` when the device has no blessed baseline yet — that is
  *not* "in sync"; the observation is still recorded and promotable later)
- Returns fleet: `{success, count, drifted, reports: [...]}`

### `get_drift_alerts`
Read the drift-alert history that `check_drift` writes as a side effect
of every run (transitions: `appeared`, `changed`, `cleared`). Read-only —
no device traffic, no commits.
- **Args:** `device_id` (optional — omit for all), `since` (optional
  timestamp lower bound), `limit` (optional)
- **Returns:** `{success, count, alerts: [...]}`

---

## ⏰ Scheduled snapshots

Schedules persist as rows in the unified `tasks` table (ADR-0037) and survive
server restarts. The pre-ADR-0037 `~/.admz/schedules.json` is legacy: it is read
once by the migration (`admz/paths.py::schedules_path`) and never written.

### `create_snapshot_schedule`
Create a recurring snapshot schedule.
- **Args:** `schedule_id`, `description`, `interval` (e.g. `"30m"`, `"2h"`,
  `"1d"`), `tag_filter` (optional), `device_ids` (array, optional)
- **Returns:** `{success, schedule}`

### `list_snapshot_schedules`
List all schedules with their status.
- **Args:** none
- **Returns:** `{success, count, schedules}`

### `update_snapshot_schedule`
Update an existing schedule (interval, enabled, tag filter, description).
- **Args:** `schedule_id`, plus any of `interval`, `enabled`, `tag_filter`, `description`
- **Returns:** `{success, schedule}`

### `delete_snapshot_schedule`
Remove a schedule.
- **Args:** `schedule_id`
- **Returns:** `{success, message}`

### `run_snapshot_schedule`
Manually trigger a scheduled snapshot right now.
- **Args:** `schedule_id`
- **Returns:** `{success, schedule_id, devices_snapshot, succeeded, failed}`

---

## 🎛 Fleet settings

Fleet-wide settings persist in SQLite (`fleet_settings` table). Since
ADR-0053, protection is **deny-by-default**: every key outside the
LLM-writable allow-set (`default_username`, plus `default_password` via
capture URL only) is protected and can only be changed via the web UI.
Examples: `confirm_level_*`, `confirm_password_hash`,
`confirm_approver_groups`.

### `get_fleet_settings`
List all settings. Password-shaped values are returned masked
(`****** (N chars)`) — never plaintext.
- **Args:** none
- **Returns:** `{success, count, settings: {key: value_or_mask}}`

### `set_fleet_setting`
Set, delete, or capture a fleet-wide setting. Protected keys are
rejected with `{success: false, error: "..."}`. For password-class keys
(`key` contains `"password"`), omitting `value` generates a
`/capture/fleet/{token}` URL so the password never enters the LLM
context.
- **Args:** `key`, `value?`
- **Returns:** `{success, action: "set"|"delete"|"capture", key, …}` —
  shape depends on action. Capture flow returns `{capture_url, token}`.

---

## 💾 Firmware

Cached firmware lives in `~/.admz/firmware/*.bin`. Source: Axis public
FTP at `https://www.axis.com/ftp/pub_soft/{MPQT,PACS}/`.

### `download_firmware`
Fetch a firmware `.bin` from Axis FTP, cache locally, and compute an
LTS-aware upgrade path for cross-major upgrades.
- **Args:** `model?` or `device_id?` (one required), `version?` (omit
  for latest), `check_only?` (don't actually download — just check)
- **Returns:** `{success, model, version, file_path, file_size,
  upgrade_path, already_cached}` or error envelope including
  `FirmwareLoginRequiredError` when the FTP redirects to login.

### `import_firmware`
Scan a local directory (default `~/Downloads`) for Axis `.bin` files and
copy them into the firmware cache. `scan_only=true` previews without
copying.
- **Args:** `directory?`, `scan_only?`, `device_id?`
- **Returns:** `{success, count, imported: [...], skipped: [...]}`

### `list_cached_firmware`
List files currently in the firmware cache.
- **Args:** none
- **Returns:** `{success, count, files: [{model, version, file_name,
  file_path, file_size}, ...]}`

---

## 🔔 Device automation rules

Create/list/delete device **event action rules** (run an action when an event
fires). ADMZ never hand-assembles the SOAP — axis-api-atlas's rule builder
composes the device-proven rule from the model's survey; ADMZ runs it behind the
approval gate. See ADR-0043.

### `list_rule_capabilities`
Read-only: the event **conditions** (triggers) and **actions** a device's model
supports for rules, plus the device's current rules. Call this first to pick a
`condition_id` + `action_token`.
- **Args:** `device_id`
- **Returns:** `{available, model, conditions: [{id, label, topic, params, ...}],
  actions: [{token, label, params: [{name, label, choices, secret}],
  needs_capture}], current_rules: [{rule_id, name, enabled, primary_action}]}`
  — or `{available: false, reason}` when the model isn't surveyed.

### `create_action_rule`
Compose and create a rule (GATED — returns a confirmation card; the rule is
created only after approval). To edit a rule, delete + recreate.
- **Args:** `device_id`, `condition_id`, `action_token`, `param_choices?`
  (keyed by param label or SOAP name — never secrets), `rule_name?`
- **Returns:** a blocked/`url_only` confirm envelope. For a notification/send-*
  action that needs recipient credentials, instead returns
  `{needs_recipient_credentials: true, capture_url: "/capture/rule/<token>"}` —
  the user enters the login/password on that secure form (never in chat), then
  approves. On approval: `{success, rule_id, config_id}`.

### `delete_action_rule`
Remove a rule (and its linked action configuration) by id (GATED).
- **Args:** `device_id`, `rule_id`
- **Returns:** a `url_only` confirm envelope; on approval `{success,
  removed_rule, removed_config}`.

---

## 🎬 Demos (ADR-0046/0047)

The experience-center unit of work: named devices (each with a role) + the
config that makes it work (an owned *fragment* over each device's baseline) +
signals + narrative. Every tool below takes `demo` = the demo's **name**
(case-insensitive, unique) or id.

### `list_demos`
Every demo with computed readiness (state, blockers, devices, active flag).
Read-only, cache-backed — never probes a device.
- **Returns:** `{success, count, demos: [{name, readiness: {state, blockers,
  devices}, active, scenario_name, …}]}`

### `get_demo`
Full detail for one demo: per-device readiness rows, the owned config
fragment per role, signals with last-seen, narrative.
- **Args:** `demo`

### `create_demo` / `update_demo` / `delete_demo`
Metadata CRUD — nothing is pushed to any device. Scope by `tag` (picks up
newly-tagged devices) or `device_ids`. `update_demo` takes only the fields to
change; `delete_demo` also removes the demo's fragments from the working tree
(git history keeps them).
- **Args (create):** `name` (required), `narrative?`, `tag?`, `device_ids?`,
  `roles?` (device_id→role), `signals?`

### `assign_demo_fragment`
Capture currently-drifted fields into the demo's owned fragment (GATED —
returns the approval card; values are re-read from the live diff at apply
time). Run `check_drift` first and pick fields from that diff.
- **Args:** `demo`, `fields: [{device_id, facet, path}]`, `role?`
- **Returns:** a blocked/`url_only` confirm envelope; on approval
  `{success, added, skipped, warnings, commit_sha}`.

### `adopt_demo`
Mark a demo ACTIVE without pushing anything (GATED — its owned keys stop
counting as drift). Guards re-run at apply time: same-key overlap with
another active demo or a device held by a legacy scenario refuse cleanly.
- **Args:** `demo`

### `deactivate_demo`
Stop claiming the demo's keys (direct, no gate — it only reveals drift).
- **Args:** `demo`

### `prepare_demo` / `end_demo`
Load / unload a SIDELINED demo's scenario as ONE gated config-push plan
(both return the plan's confirm envelope). Refused for baseline demos.
- **Args:** `demo`

---

## 🧯 Advanced capabilities (ADR-0052)

ADMZ declares its powerful / dangerous / privileged-install switches in one
registry (`admz/capabilities.py`). This tool is the agent's window onto it —
the same read `GET /api/capabilities` serves, so both answer *"what non-default
powers is this installation running with?"* identically.

**There is deliberately no tool to enable or disable a capability, and there
never should be.** These switches decide who may satisfy a confirmation gate
(`dev.auto_approve`) and who the calling principal even is (`dev.test_auth`) —
an LLM that can turn them on is not gated at all. The refusal is enforced
twice: no tool exists, and every capability's `setting_key` is in
`PROTECTED_SETTING_KEYS`, so the generic `set_fleet_setting` refuses them too
(ADR-0020). Enabling one stays an env var + a service restart, or a
reveal-gated, typed-acknowledged, audited toggle on `/settings/advanced`.

### `get_advanced_capabilities`
Read the advanced-capability registry: every declared capability, its danger
class, whether it is on and from where. Read-only, no arguments.
- **Args:** none
- **Returns:** `{success, capabilities: [{id, title, description, danger,
  severity, production_appropriate, enable_via, env_var, setting_key,
  companion_env, since, notes, enabled, source, toggleable}, ...],
  active: [id, ...], auth_backend: {backend, anonymous}}`
- `danger` is one of `dev-only` / `dangerous` / `privileged` /
  `test-suppressor` / `internal`; `source` is `"env"`, `"setting"`, or `""`
  when off (env wins — a setting cannot turn off an env-forced capability).
- `env_var` / `setting_key` are the knob **names**, never their values — the
  same discipline `/api/health`'s id list follows.
- `auth_backend` is read-only *context*, not a capability (Master resolution 5):
  `ADMZ_AUTH_BACKEND` already emits its own startup warning, and registering it
  would leave every dev box permanently flagged.
- A capability changes *who* the principal is or *what* runs in the background.
  It never removes a confirmation gate — ADR-0034 applies in full.

---

## Common error envelopes

When a tool fails, it returns one of:

```json
{"error": "DeviceNotFound", "message": "..."}
{"error": "AccountNotFound", "message": "..."}
{"error": "PermissionDenied", "message": "..."}
{"error": "BackendError", "message": "..."}
{"error": "ADMZError", "message": "..."}
{"error": "InternalError", "message": "..."}
{"error": "NotImplemented", "message": "..."}
```
