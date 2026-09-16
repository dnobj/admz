# Plan: Drift review in the console chat — notices, triage, gated tools

Status: **approved; PR 1 built (#508), PR 2 and PR 3 not yet** — the decision records are
[ADR-0070](../decisions/0070-drift-is-reviewed-in-the-console-chat.md) (triage, tools, guidance) and
[ADR-0071](../decisions/0071-a-task-raises-a-notice-the-console-delivers-it.md) (notices and delivery),
both Proposed 2026-09-16. Three code PRs follow the docs merge; issues are filed from the slices below.
File:line references are against master `daa4159`.

## Context

Drift tracking and approval work well in the web UI (`/devices` → "Drifted (N)" expander: BASELINE vs
LIVE columns, per-row eye-slash → config-ignore rule, "Accept drift" with a note that becomes a git
changelog entry, "Revert N fields" targeted revert, a collapsed "read-only observed changes" group).
The owner wants the same review **through the console chat**: a notification/button in chat that can be
addressed conversationally, the LLM nudging what matters and what doesn't (`default→DEFAULT`,
`root.Properties.FirmwareManagement.Version 1.8→1.10` and firmware-added keys are noise; account and
network changes are not), reference guidance the LLM follows, and the mechanism framed as **tasks**: a
task's action raises a notification that is handled in chat.

Exploration found the primitives already exist and only need composing:

| Need | Existing seam |
|---|---|
| "drift newly detected" | `DriftAlertStore.process_report` returns `appeared/changed/cleared` — `admz/snapshot/drift_alerts.py:382-447`, called from `admz/snapshot/drift.py:314-319` on every check |
| task action that "notifies" | `notify` handler is a stub — `admz/tasks/handlers.py:305-312` |
| out-of-band message into a conversation | `role='event'` `[console]` rows via `ChatSessionStore.append_event` — `admz/chatbot/sessions.py:756` |
| LLM speaks first, no server-side actor | ADR-0066 resume turn: `resume_due` `sessions.py:842`, `GET/POST /api/chat/resume*` `admz/api/routes/chat.py:1142/:1171`, `chat.js:1178 maybeResumeConversation()` |
| buttons in chat | `operations.blocked_envelope` + `_ACTION_EXECUTORS` (`admz/operations.py:131`, `:1373`) → approval card in text chat and voice (`voice.js:215`) |
| conditional LLM guidance | `_INFERENCE_GUIDANCE` + `build_inference_section()` — `admz/chatbot/system_prompt.py:593`, wired `:840-846`; fencing registry `tests/test_prompt_fencing_completeness.py:55` |

What the chat lacks today: a targeted revert tool (only whole-baseline `restore_device`), any ignore-rule
tool, a `note` on `accept_baseline`, the `revertable` flag on drift rows (MCP `_check_drift` live-probes
and skips `_annotate_revertable`), and any parameter-importance knowledge. **Bug found:** the MCP
`accept_baseline` path bypasses the ADR-0047 active-demo guard (`_reject_accept_with_active_demos` is
REST-only, `admz/api/routes/snapshot.py:138-191`; neither `server.py:3752-3808` nor
`operations.py:659-702` runs it).

## Decisions (recorded in the ADRs; the owner may override)

| # | Decision | Answer |
|---|---|---|
| 1 | Delivery | Attention strip above the composer with Review / Snooze / Dismiss. Review writes a `[console]` note; the ADR-0066 resume turn makes the assistant lead. No server-side turn runner. |
| 2 | Nudge | Open notices are preloaded (fenced); the assistant mentions them once, one line, at the start of a conversation, and whenever asked. |
| 3 | Ignore rules from chat | Approval card (same class as `assign_demo_fragment`). Usually folded into the accept card. |
| 4 | Seed rule | Append `root.Properties.FirmwareManagement.*` to `_SEED_DEFAULT_RULES` (`admz/snapshot/ignore.py:61-95`). |
| 5 | Notices vs tasks | Tasks produce notices; notices are their own small table with `task_id`/`source` provenance (ADR-0037 non-goal at `0037:73-74`). |
| 6 | Triage | Deterministic code classifies (annotate-never-suppress, like `admz/snapshot/attribution.py`); the LLM narrates and proposes. |
| 7 | One card per review? | Composite-lite: `accept_baseline` gains `note` + `ignore_keys`. A revert is its own card because the accept must bless a fresh observation taken after it (`snapshot.py:225-229`, `server.py:3766`). A single-card composite waits for ADR-0062. |

## The flow, end to end

1. Scheduled `drift_audit` task (or a manual check) → `check_drift` → `process_report` → `appeared` → notice raised (`drift:<device_id>`, metadata only).
2. Console strip shows "Drift on AXIS C8110 · 4 fields · 59m" → **Review in chat** → `POST /api/notices/{id}/review` → `[console]` event row in the active (or a new) conversation → `maybeResumeConversation()` fires one gated turn.
3. Assistant calls `get_drift_review(device_id)` (cached, annotated) and narrates: high/medium rows with values first; low rows collapsed into one line ("3 firmware-managed/added keys and 1 case-only change — fw 12.9.57→12.11.77"); proposes ONE plan.
4. User agrees → `accept_baseline(note="fw 12.9.57→12.11.77 upgrade; MQTT prefix case normalised", ignore_keys=[...])` → one card. If anything is reverted: `revert_drift(fields)` card first → `[console]` success note → resume turn → `get_drift_review(refresh=true)` → accept card.
5. Accept resolves the notice as `accepted`; a revert resolves it at the next check; the user can dismiss or snooze.

---

## PR 1 — Triage knowledge + one review annotator (backend)

### New `admz/snapshot/triage.py`
Pure, deterministic, annotate-only. Adds `field["triage"] = {class, importance, recommendation, why, rule}`,
`summary["triage_context"]`, `summary["summary_by_class"]`, `summary["highest_importance"]`. Never removes a
row or touches `bucket`/`has_drift`/`revertable`. Wrapped in the same defensive try/except as
`annotate_attribution` (`attribution.py:284-285`). The ordered rule table is in ADR-0070 §1; matching is on
`canonical_key` with `ignore.py:102-107` semantics. Ordering is pinned by tests: identity before `added_key`;
`runtime_state` before network config; `read_only` below the security rules.

`report_context(summary, *, git_repo, device_info) -> TriageContext` is the module's only I/O (best-effort,
never raises): `baseline_firmware` from `fleet/<id>/device.yaml` at `baseline_sha` via `GitRepo.get_file`
(`admz/snapshot/git_repo.py:618-633`) — the engine writes `firmware_version` there (`engine.py:638-665`,
`:874-891`); `live_firmware` from `device.yaml@observed_sha` else the registry; `firmware_changed` when both
known and different; `last_accept` from `fleet/<id>/BASELINE.yaml@HEAD` when its `baseline_sha` matches.

### New `admz/snapshot/review.py`
- `annotate_revertable(summary, *, registry, device_id)` — moved verbatim from `snapshot.py:1100-1130`.
- `cached_drift_report(registry, device_id)` — moved from `snapshot.py:407-427` (stale-baseline guard kept).
- `revert_fields_for(registry, drift_detector, device_id, *, selected=None) -> (fields, not_found)` — moved from `snapshot.py:430-454`; carries `base_value` (dropped today at `:441-450`); `demo_set` still excluded.
- `annotate_review(summary, *, registry, git_repo=None, device_id)` — revertable → `annotate_attribution` → `annotate_triage(context=report_context(...))`, then `applicable_ignore_rules` (≤20) and `ignore_rule_count`.

Call sites: REST `check_drift` `snapshot.py:1161-1166`; MCP `_check_drift` single-device branch
`server.py:3838-3840`. `snapshot.py` keeps thin aliases. Update the literal-text assertions at
`tests/test_drift_attribution.py:455-461` to `annotate_review(`.

### Accept: note, principal, guard
- New `admz/snapshot/accept_guard.py::check_accept_allowed(*, git_repo, demo_store, device_id, device_info)` raising `AcceptRefused(status=409|503, detail)` — body is `snapshot.py:164-191`, keeping the lazy `fragments.owning_demos` import so `tests/test_demos_routes.py:591-622` monkeypatches still bite. The REST helper becomes a 3-line wrapper.
- MCP schema (`server.py:1410-1442`) gains `note` (≤500), `ignore_keys` (≤50), `ignore_scope`. Handler: guard **before minting**; target = cached review's `observed_sha` else `latest_observed_sha`; validate/dedupe `ignore_keys` (mirror `IgnoreRuleModel`, `snapshot.py:1183-1197`); payload adds `note`, `accepted_by=str(self.principal)`, `ignore_rules`, `drifted_count`. Card text: `Accept the current observed config of <label> (<id>) as its new baseline (commit <sha12>, N facets; K drifted fields absorbed). Note: "<note>". Also exclude from drift tracking (<scope>): <keys>.`
- Executor `_action_accept_baseline` (`operations.py:659-702`): (1) guard again (demo store via `admz.api.context.get_context().demo_store`, pattern `operations.py:858`; fallback `admz.demos.store.get_store()`), refuse before touching the pointer; (2) `ignore.add_rules(action["ignore_rules"])`; (3) existing pointer move + BASELINE.yaml + `refresh_drift_after_accept`. Outcome `ignore_added_keys` → `OUTCOME_IDENTITY_KEYS` (`admz/audit.py:343-346`).
- Seed rule appended to `_SEED_DEFAULT_RULES`.

### Tests
`tests/test_drift_triage.py`, `tests/test_drift_review.py`, `tests/test_accept_guard.py`; edits to
`test_drift_attribution.py`, `test_drift_cache.py`, `test_mcp_destructive_gate.py:445-520`. Claims and
mutations: ADR-0070 verification table.

---

## PR 2 — Chat tools + prompt guidance

New `admz/mcp/tools/drift_review.py` (pattern `device_removal.py`), appended to `MIGRATED_TOOLS` after
`device_removal.TOOLS` (`admz/mcp/tools/__init__.py:71`); handlers on `ADMZMCPServer`; `TOOL_HANDLERS`
(`admz/mcp/dispatch.py:410-487`); names appended at the END of `EXPECTED_TOOL_ORDER`
(`tests/test_mcp_tool_order.py`). Nested args validated in the handlers (`_validate_tool_args` covers flat
ids only, `server.py:157-175`). Docs mirror: `docs/MCP_TOOLS_REFERENCE.md:524-589`.

| Tool | Kind | Contract |
|---|---|---|
| `get_drift_review(device_id, refresh=false, classes?, include_fields=true, limit=40)` | read-only | cached diff else live; `annotate_review`; compact output (`context`, `summary_by_class`, `highest_importance`, `counts`, `fields[]` importance-desc with values truncated to 80 chars, `more`, `applicable_ignore_rules`); under the 6000-char cap (`client.py:1244-1290`). `check_drift` keeps live-probing; its description points reviews here. |
| `accept_baseline(...)` | gated action (PR 1) | description rewritten: cause-based `note`; `ignore_keys`; refuses on active demo; the order rule revert → `[console]` note → `get_drift_review(refresh=true)` → accept. |
| `revert_drift(device_id, fields?, note?)` | gated plan | `review.revert_fields_for(selected=…)` → `RestoreBuilder.build_targeted_revert_plan` (`restore.py:155-289`) → `plan_engine.create_plan(on_failure="stop")` → `operations.execute_gated_plan` (`server.py:3649` pattern) → one envelope with `reverting`, `skipped[{reason}]`, `not_found`, `warnings`; no steps → `NothingToRevert`. Cross-process approval via `plan_steps_json` (`operations.py:1568-1571`). |
| `ignore_config_keys(keys[1..50], scope="global", reason?)` | gated action `add_ignore_rules` | validate, dedupe (nothing new → `already_present`, no card); `create_action_session(action="add_ignore_rules", device_id=<id or "fleet">)` at the default class, pinned `url_only`; card names every key and the scope; executor `_action_add_ignore_rules` → `ignore.add_rules`. `_note_target` (`confirm.py:374-387`) gains the fleet-wide sentence. |
| `list_config_ignore_rules(scope?)` | read-only | `ignore.get_rules()` filtered + count. |
| `list_notices(status="open", kind?, device_id?)` / `dismiss_notice(notice_id, note?)` | read-only / ungated, audited | mirror PR 3's REST; schemas here (order-frozen), handlers land with PR 3. |

### Prompt
- `_DRIFT_REVIEW_GUIDANCE` beside `_INFERENCE_GUIDANCE` (`system_prompt.py:593`), rendered only when the attention section is non-empty; content per ADR-0070 §6. Descriptions of `accept_baseline`/`revert_drift`/`get_drift_review` carry the same order sentence (`test_mcp_tool_order.py:150-161` precedent).
- Rewrite `system_prompt.py:191-198` (three moves per field); keep `:185-190`, `:199-207`; demos block `:441-443` → `get_drift_review`; `[console]` bullet `:319-323` gains the review clause.
- `build_attention_section()` in `admz/chatbot/context.py` (cache-only, degrade-to-`""`): open notices (≤10) + drifted devices from `drift_status_for` (`admz/snapshot/drift_status.py:39-77`; ≤20). Fields through `sanitize_display_text`; ages via `_age` (`context.py:307`). New kwarg `attention_section` on `build_system_prompt` (`:723-734`), slot after `{inference_section}` (`:470`), rendered as guidance + `_fence('ATTENTION DATA', …)`. Register in `FENCED_SECTIONS`. Wire at `chat.py:253-263`, `chat.py:693-703`, `voice.py:238-244`.

### Tests
`tests/test_mcp_drift_tools.py` (harness `tests/mcp_harness.py`, fixtures as `test_mcp_destructive_gate.py:44-120`);
`tests/e2e/test_24_drift_review_chat.py` (pattern `test_21_gated_actions_chat.py`).

---

## PR 3 — Notices backbone + console delivery

### Store — new `admz/notices/store.py` (pattern `TaskStore`, `admz/tasks/store.py:227-281`)
Schema and API per ADR-0071 §1: `raise_notice`, `resolve`, `handle`, `snooze`, `mark_reviewed`, `get`, `list`,
`count_open`, `sweep`; singleton `notices_store`; partial unique index on live `subject_key`.

### Producers — new `admz/notices/producers.py`
`Provenance` contextvar + `notice_provenance(source, task_id, notify_console)`; `drift_notices_enabled()`
(literal `.get("drift_notices_enabled")` for the setting-policy scanner; add to `KNOWN_SETTING_KEYS`
`admz/setting_policy.py:131`); `drift_transition(alert, report)`; `event_notice(task, message)`;
`backfill_drift_notices(registry)` at startup beside `admz/api/main.py:219-297`.

Wiring: `drift.py:318` nested best-effort producer call; `handlers.py:192` provenance wrap;
`handlers.py:305-312` real `_run_notify` returning `notice_id`; `operations.py:628`
`refresh_drift_after_accept(..., accepted_by="")` resolving `accepted` **before** `:646`, threaded from
`operations.py:691`, `snapshot.py:258`, `:632`; `health.py:2063` `_AUDITABLE_OUTCOME_KEYS += ("notice_id",)`.

### REST — new `admz/api/routes/notices.py` (include after `main.py:535`, prefix `/api`)
`GET /api/notices`; `POST /api/notices/{id}/review` (404 / 409 `not_open` / 409 `continuation_in_flight` via new
`ChatSessionStore.has_live_resume_claim`; active conversation else `create_conversation(title=…,
title_source="snippet", make_active=True)`; `append_event`; `mark_reviewed`; audit `notice.review`);
`POST /api/notices/review` (batch, 1–20); `POST /api/notices/{id}/dismiss`; `POST /api/notices/{id}/snooze`
(1–720 h). Note wording per ADR-0071 §4. Anonymous allowed on all.

### Console
- `_console.html:92-97`: `#chat-notices` above `#chat-actions`; ids added to the header comment `:3-5`; rows are `.pending-row`; >3 collapses to "N more — Review all"; CSS beside `.pending-widget` (`admz.css:559-568`).
- `chat.js`: `loadNotices(force)` (15 s throttle), `renderNoticeRow`, `reviewNotice`/`reviewNotices` (bail if `resumeInFlight || sendBtn.disabled`; on 200 either `openConversation(id).then(maybeResumeConversation)` — `openConversation` `:1015` must return its promise — or `replayMessage("event", note)` + `maybeResumeConversation()`), `dismissNotice`, `snoozeNotice`. Hooks: page load after `rehydratePendingActions()` (`:1237`), `visibilitychange` (`:1227`), the resume `.finally` (`:1213`), `?review_notice=<id>`. Never touch `resetTranscript()` (`:989-996`).
- Nav badge `admz/api/templating.py:390` (pattern `_demo_count()` `:127`); `tasks.html` Notices section after `:35-43`; `JOB_LABELS` (`:267-273`) gains `notify`.
- `build_attention_section()` starts listing open notices.

### Tests
`tests/test_notices_store.py`, `tests/test_notices_producers.py`, `tests/test_notices_routes.py` (fixture shape
`tests/test_chat_resume.py:20-77`), `tests/e2e/MANUAL_notices_tests.md`. Claims and mutations: ADR-0071
verification table.

---

## Phase 2 (separate issues)
- `accept_baselines(device_ids, note, ignore_keys?)` sibling tool (ADR-0069 shape; FR-DRF-019).
- True single-card `resolve_drift` composite after ADR-0062.
- UI hint chip in `index.html` `mkRow` (`:557-617`) reading `f.triage.class`; resolve a notice on a post-revert recheck; purge notices in `purge_orphaned_device_state`.

## Verification (end to end)
1. Unit/route tests per PR; the full suite from the worktree in the foreground; CI is the authority.
2. Prompt pins: byte-identical when nothing is drifted and no notice is open.
3. Live e2e on a dev instance with an isolated `ADMZ_HOME` (never `:4242`), `ADMZ_DEV_AUTO_APPROVE=1`: drift a lab device → check → strip shows the notice → Review → the assistant narrates classes and firmware context → accept card with note → `BASELINE.yaml` has the note and principal → notice `accepted` → strip empty. Second run with a `security_sensitive` change: the assistant asks before proposing a revert → `revert_drift` card → resume turn → `refresh=true` → accept card.
4. Guard regression: an active demo on the device → chat accept refused before any card; a card minted before activation → executor refuses, pointer unchanged.
5. Manual browser checklist.

## Risks found while planning
- Every event row is a fresh claim key (`sessions.py:869-914`): the server 409 and the client in-flight guard both stay.
- `maybeResumeConversation`/`resume-due` resolve the **active** conversation (`chat.js:1178`, `chat.py:1158`) — hence the documented deviation when Review creates one.
- No post-revert recheck exists; the notice outlives a revert until the next check unless the model refreshes as told.
- `tests/test_drift_attribution.py:455-461` asserts literal call-site text.
- The guidance section costs roughly 700 tokens per turn while any device is drifted.

## Sequence
Nothing is written in `C:\admz\admz-dev`. Docs PR from a sibling worktree → merge → three `status: ready`
issues (PR 1, PR 2, PR 3) citing the FR ids → implemented serially in worktrees branched from `origin/master`.
PR 3 is independent of PR 2 except the notice lines in `build_attention_section`.
