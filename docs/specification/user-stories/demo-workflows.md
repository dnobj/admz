# User stories: demo workflows (Experience Center)

The original use case ADMZ was sharpened around. Axis Experience Centers cycle their device fleets through demo configurations for visitors, training sessions, and experiments — often multiple times per day. The workflows below are the patterns that make that sustainable.

## US-DW-001 — Tag a baseline before a customer visit

**As an** Experience Center operator preparing for the Acme visit tomorrow, **I want to** snapshot all the lobby cameras and tag the snapshot with the visit name **so that** I can restore to it after the visit even if I forget what I changed.

**Acceptance criteria:**
1. The operator selects the devices (tag filter `lobby`, explicit `device_ids`, or "all").
2. A single `snapshot_fleet(tag_filter="lobby", message="pre-acme-visit-2026-06-01")` call captures every applicable facet on each device into one git commit.
3. The operator can apply a named tag to the commit:
   ```
   git -C ~/.admz/config-repo tag pre-acme-visit-2026-06-01 HEAD
   ```
   (Future enhancement: an MCP `tag_snapshot` tool that does this in one call.)
4. The tag survives ADMZ restarts (it's in the git repo, not in-process state).

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md).

## US-DW-002 — Set up a demo configuration

**As an** operator preparing for a specific demo, **I want to** apply a known-good configuration to each demo device.

**Acceptance criteria:**
1. The operator describes the desired state to their LLM (or chatbot) — e.g. "set lobby cameras to demo-mode-bitrate-8mbps, enable privacy masks for outdoor view areas, switch PTZ to home preset 3."
2. The LLM calls `query_catalog` to find the right operations, builds a plan via `create_plan`, and presents it for review.
3. Dangerous steps in the plan (if any) require explicit `confirm_dangerous=true`.
4. `execute_plan(plan_id)` applies the configuration; per-step results stream back.
5. The operator can immediately snapshot the *post-demo-setup* state to verify it matches expectations and to have a second restore point.

**Related requirements:** [plans](../requirements/plans.md), [catalog](../requirements/catalog.md).

**Related stories:** [llm-driven-configuration](llm-driven-configuration.md).

## US-DW-003 — Restore after the visit

**As an** operator at the end of the customer visit, **I want to** restore the lobby cameras to the pre-visit baseline **without** trying to remember what changed.

**Acceptance criteria:**
1. `restore_device(device_id, ref="pre-acme-visit-2026-06-01")` (or the equivalent for each device, or a future `restore_fleet` tool) reads facet YAMLs from the tagged commit.
2. A plan is built with the appropriate write operations. The plan is **not** auto-executed — the operator reviews it first.
3. The plan respects facet `restore_order` hints (network last, firmware first if changing, users carefully).
4. Any dangerous steps in the restore plan are gated by the same two-gate flow as any other plan.
5. After restore, a `check_drift(device_id)` verifies the device matches the tagged state.

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md), [drift-detection](../requirements/drift-detection.md).

## US-DW-004 — Detect mid-demo drift

**As an** operator who notices a demo isn't behaving as expected, **I want to** quickly see what configuration drifted from the baseline.

**Acceptance criteria:**
1. `check_drift(device_id)` reads live state, diffs against the latest commit on the branch, returns a `DriftReport` listing every (facet, path, expected, actual) tuple.
2. The drift report is human-readable when shown in chat or rendered in the web UI (table or per-facet sections).
3. Drift is detected without modifying the device or the git repo — pure observation.

**Related requirements:** [drift-detection](../requirements/drift-detection.md).

**Related stories:** [drift-and-monitoring](drift-and-monitoring.md).

## US-DW-005 — Fork a known-good config to a new device

**As an** operator with `camera-conference-01` perfectly configured, **I want to** stand up `camera-conference-03` with the same settings as a starting point.

**Acceptance criteria:** 📋 (planned — `fork_device_config` MCP tool exists in the design doc but not yet implemented).

When implemented:
1. The operator picks the source device and the target.
2. ADMZ copies `config/` and `device.yaml` from `fleet/camera-conference-01/` to `fleet/camera-conference-03/`.
3. Device-specific fields (host, hostname, IP, MAC) are overridden from the target's registry entry.
4. The operator reviews the diff via a PR (if a remote repo is configured) or as plain `git diff`, then applies via `restore_device`.

## US-DW-006 — Branch-based demo workflows

**As an** operator running parallel demo configurations (one for customer A, one for customer B), **I want to** maintain them as separate branches.

**Acceptance criteria:** 📋 (planned — see EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md §12, deferred decision).

The Experience Center design doc notes this was considered for v1 but deferred. Tag + restore is sufficient for the common case; branches add complexity (which branch is active, switching branches mid-demo, etc.) that wasn't worth the v1 weight. Revisit if operators actually run into the limit.

## US-DW-007 — Quick-restore button in the chatbot

**As an** Experience Center operator using the bundled chatbot, **I want to** say "restore lobby cameras to pre-acme-visit-2026-06-01" and have it happen with one inline approval click.

**Acceptance criteria:** 📋 (planned — depends on the web chatbot landing).

When the chatbot ships (per [ADR-0024](../decisions/0024-bundled-web-chatbot.md)):
1. Natural-language restore requests resolve to `restore_device`/`restore_fleet` calls.
2. The proposed plan renders as an inline approval card with the affected devices and step counts.
3. One [Approve] click runs the plan; per-device progress streams back into the chat.

## Known limitations

- 📋 **No `fork_device_config` yet.** Manual `cp -r` in the config-repo works, but isn't ergonomic.
- 📋 **No branch-based parallel demo support.** Tag + restore is the v1 answer.
- 📋 **No `tag_snapshot` MCP tool.** Operators tag manually via `git tag` in the config-repo for now.
- 📋 **No "make camera B match camera A" diff-and-apply tool** — combination of snapshot + restore manually achieves this; first-class workflow would be nicer.
- ⚠️ **Rollback breadth.** Only `param.cgi:update` operations have automatic pre-read rollback. A restore that touches REST APIs or SOAP services has no rollback data captured.
