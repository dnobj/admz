# ADMZ MCP Tools Reference

Complete reference for the 33 tools the ADMZ MCP server exposes.

Group key:
- 🗂 = registry + accounts
- 🔐 = out-of-band credential capture
- 📡 = network discovery
- 📚 = catalog + operation execution
- 📋 = multi-step plans
- 📸 = snapshot / restore / drift
- ⏰ = scheduled snapshots

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
Add a new device.
- **Args:** `device_id`, `device_info` (object), `accounts` (object, optional)
- **Returns:** `{success, device_id}`
- **Errors:** `BackendError` (duplicate)

### `update_device`
Merge updates into a device's information.
- **Args:** `device_id`, `updates` (object)
- **Returns:** `{success, device_id, updates}`
- **Errors:** `DeviceNotFound`

### `delete_device`
Remove a device and cascade-delete its accounts.
- **Args:** `device_id`
- **Returns:** `{success, device_id}`

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

### `get_credentials`
Retrieve credentials (returns the actual password — sensitive).
- **Args:** `device_id`, `account_id` (default `"default"`), `requester` (string, optional)
- **Returns:** `{success, credentials: {username, password, ...}}`

---

## 🔐 Out-of-band credential capture

These tools generate one-time URLs the user opens in a browser. The
password is entered there and stored directly in the registry — it
never enters the LLM context.

### `capture_credentials`
Create a capture session and return the URL.
- **Args:** `device_id`, `account_id` (default `"default"`),
  `account_type` (default `"service"`), `purpose` (string, optional),
  `base_url` (default `http://localhost:8000`)
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
- **Returns:** `{success, device_id}`
- The device is created without credentials. Use `capture_credentials`
  to set them via the OOB flow.

---

## 📚 Catalog & operation execution

### `query_catalog`
Given a device and an intent (in natural language), return the relevant
catalog operations + parameter group docs.
- **Args:** `device_id`, `intent` (string), `family` (default `"vapix"`)
- **Returns:** `{success, operations, parameter_groups, device, risk_summary, notes}`
- **Recommended workflow:** call this first; pass the results to the LLM;
  the LLM picks an operation + params; then call `execute_operation`.

### `execute_operation`
Run a single catalog operation.
- **Args:** `device_id`, `operation_id`, `params` (object), `family` (default `"vapix"`)
- **Returns (success):** `{success: true, status_code, duration_ms, data}`
- **Returns (blocked):** `{blocked: true, risk_level: "dangerous", reason,
  confirm_token, confirm_tool: "confirm_dangerous_operation", message}`
- Dangerous operations are blocked until confirmed.

### `confirm_dangerous_operation`
Confirm and execute a previously-blocked dangerous operation.
- **Args:** `confirm_token`
- **Returns:** same as `execute_operation` success
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
- **Args:** `plan_id`
- **Returns:** `{success, plan_id, status, steps_total, steps_succeeded,
  steps_failed, steps_skipped, results, rollback_available}`

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
Build a plan that restores a device to a previous configuration.
- **Args:** `device_id`, `ref` (default `"HEAD"`), `facets` (array, optional)
- **Returns:** `{success, plan_id, steps, warnings, source_ref}`
- Does **not** execute — call `execute_plan` after review.

### `diff_device`
Show config changes for a device between two refs.
- **Args:** `device_id`, `ref_a` (default `"HEAD~1"`), `ref_b` (default `"HEAD"`)
- **Returns:** `{success, device_id, ref_a, ref_b, diff, recent_history}`

### `check_drift`
Compare live device state against git HEAD.
- **Args:** `device_id` (optional — if omitted, scans whole fleet),
  `tag_filter` (string, optional)
- **Returns:** single device: `{success, device_id, has_drift,
  facets_checked, facets_drifted, drifted_fields}`
- Returns fleet: `{success, count, drifted, reports: [...]}`

---

## ⏰ Scheduled snapshots

Schedules persist to `~/.admz/schedules.json` and survive server restarts.

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
