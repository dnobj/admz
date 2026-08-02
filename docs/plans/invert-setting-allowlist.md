# Plan: invert the fleet-setting write model — deny by default for the LLM

**Issue:** [#212](https://github.com/dnobj/admz/issues/212) (consolidates #168, #195, #203, #177; supersedes them).
**Decision record:** [ADR-0053](../specification/decisions/0053-llm-writable-fleet-settings.md).
**Amends:** [ADR-0020](../specification/decisions/0020-protected-fleet-settings.md), which established the deny-list this plan inverts.
**Baseline:** master `a55fe5a`.

---

## Goal

Make a fleet setting **unwritable by the chat model unless someone explicitly
declared it writable**. Today the default is the other way round: a new setting
is LLM-writable the moment it exists, and is protected only if the author
remembered to add it to `PROTECTED_SETTING_KEYS`.

The measurable outcome: **the next fleet setting anyone adds is protected by
forgetting rather than exposed by it.**

## Non-goals

- **Not** a new confirmation gate. ADR-0034 is untouched; this changes *which
  keys a low-privilege caller may write*, never *whether* an approval fires.
- **Not** a change to who may write from the web. Authenticated principals keep
  every write path they have today. This is about the MCP/LLM surface.
- **Not** the audit redaction fix. `redact_structure` is blind to every
  `{key, value}`-shaped tool argument, not just this one — that is
  [#217](https://github.com/dnobj/admz/issues/217) and needs its own change.
- **Not** the missing authorization on `POST /api/events/control` — tracked as
  [#164](https://github.com/dnobj/admz/issues/164).
- **Not** a CLI for protected keys. ADR-0020's "small Phase-5 follow-up" stays
  open; inversion makes it *more* wanted, not less, and it is called out under
  Risks.

---

## Current state — the evidence

### The predicate, in full

```python
# admz/fleet_settings.py:132
return is_confirm_level_key(key) or key in PROTECTED_SETTING_KEYS
```

Clause 1 is **derived** — the namespace rule #176 added, which is why an
invented risk class is already refused. Clause 2 is **enumerated**, and every
failure in this cluster is a clause-2 failure.

### The argument: three enumerations, three different answers

This is the single strongest reason to invert rather than patch a fifth time.
Three independent attempts to enumerate the unprotected keys — by three
different methods — produced three different answers, and **each found keys the
others missed**:

| Enumeration | Method | Found | Missed |
|---|---|---|---|
| #212 §1 + amendment | regex over `^[A-Z][A-Z0-9_]*(SETTING\|FLEET\|KEY)` constants, then a manual amendment | 8 | the 5 `event_*`, the 3 `acs_fb_*`, both `snapshot_gc_*` |
| Orientation grep | literal-grep for `fleet_settings.get(` / `_fs().get(` / `*_KEY =` | 10 | the 5 `event_*`, the 3 `acs_fb_*` |
| Call-path sweep | follow every writer/reader call path per module | 18 | — (but found nothing the first two found that it didn't) |

#212's own amendment diagnoses the failure mode precisely and then reproduces
it: its regex required `[A-Z]` at position 0, so `_TOKEN_KEY`
(`acs_webhook_token`) was invisible. My literal-grep inherited a different blind
spot — it matched `_KEY\s*=\s*"` and `fleet_settings.get(`, so it missed keys
read through a module-local `_settings()` helper with the literal inline
(`admz/events/config.py`) and keys read through a `_setting()` wrapper
(`admz/modules/acs_pro/firebird.py`).

**A guard test keyed on naming convention inherits whichever blind spot its
author had.** That is why the scanner below must resolve constants and follow
call paths rather than match names — and why the durable fix is to stop
enumerating the *unsafe* set at all.

### The 18 unprotected keys — reproduced

Isolated `ADMZ_HOME` under `%TEMP%`, driving the real
`ADMZMCPServer._set_fleet_setting` handler. No device or production contact.
`PROTECTED_SETTING_KEYS` size = 30.

```
=== REAL HANDLER: ADMZMCPServer._set_fleet_setting() ===
  WROTE   event_topic_filters            admz/events/config.py:89
  WROTE   event_store_categories         admz/events/config.py:102
  WROTE   event_ingest_tag               admz/events/config.py:115
  WROTE   event_store_max_rows           admz/events/config.py:129
  WROTE   event_store_retention_days     admz/events/config.py:134
  WROTE   acs_fb_fbclient                admz/modules/acs_pro/firebird.py:75
  WROTE   acs_fb_install                 admz/modules/acs_pro/firebird.py:78
  WROTE   acs_fb_data_dir                admz/modules/acs_pro/firebird.py:86
  WROTE   snapshot_gc_enabled            admz/snapshot/maintenance.py:262
  WROTE   snapshot_gc_aggressive         admz/snapshot/maintenance.py:263
  --- controls (must all refuse) ---
  refused confirm_level_action           control
  refused gemini_api_key                 control
  refused acs_firebird_enabled           control
```

Plus the eight already reproduced in #212: `acs_pro`, `config_ignore_patterns`,
`config_ignore_rules`, `config_ignore_seed_version`, `default_password`,
`default_username`, `health_verify_credentials`, `acs_webhook_token`.

**18 of the ~44 known fleet-setting keys — 41% — are writable by the chat
model.** Treat 18 as a floor, not a total: three enumerations have now
disagreed, and the fourth method has not been tried.

### The consequences are not cosmetic

Same isolation, driving the real accessors before and after the real handler:

```
=== BEFORE (defaults) ===
  events.topic_filters()         = ['//.']
  events.events_max_rows()       = 50000
  events.events_retention_days() = 30
  firebird.fbclient_path()       = C:\Program Files\...\Firebird3_x64\fbclient.dll

=== AFTER SIX CHAT TURNS ===
  events.topic_filters()         = ['onvif://never/matches']   <-- ingest matches nothing
  events.events_max_rows()       = 1                            <-- retention collapsed
  events.events_retention_days() = 0                            <-- retention collapsed
  events.tag_filter()            = 'no-such-tag'                <-- watches no device
  firebird.fbclient_path()       = ...\evil.dll                 <-- LLM-chosen native lib
```

The event keys are the same class of harm as #203's `config_ignore_patterns`:
they do not break anything visibly, they quietly stop ADMZ from *recording*
things. `event_store_retention_days=0` plus `event_store_max_rows=1` discards
the event history; `topic_filters` and `event_ingest_tag` stop it being
collected at all.

### A recurring shape, now seen three times: guard the switch, leave the target writable

| Feature | Guarded | Not guarded |
|---|---|---|
| ACS Pro module (#195) | `acs_event_ingest_enabled`, `acs_firebird_enabled` (children) | `acs_pro` (the parent switch + `server_url`) |
| Firebird reader (new) | `acs_firebird_enabled` (the switch) | `acs_fb_fbclient`, `acs_fb_install`, `acs_fb_data_dir` (its inputs) |
| Event ingest | `event_ingest_enabled` (the switch) | `event_topic_filters`, `event_store_*`, `event_ingest_tag` (its behaviour) |

Three instances of one mistake, arrived at independently by three different
authors. A deny-list cannot fix this class because the mistake is *deciding
which half of a feature is dangerous* — and that judgement is made at 2am by
whoever adds the setting. Deny-by-default removes the judgement.

### Severity note on `acs_fb_fbclient` — latent, not live

Stated carefully, because the first reading overstates it. The path does reach a
native library load:

```python
# admz/modules/acs_pro/firebird.py:110-131  _connect_copy()
fb = fbclient_path()                                  # <- acs_fb_fbclient
os.environ.setdefault("FIREBIRD", os.path.dirname(fb))
if not driver_config.fb_client_library.value:
    driver_config.fb_client_library.value = fb        # <- the DLL the driver loads
con = connect(tmp, ...)
```

But every path to `_connect_copy` first checks `firebird_enabled()` →
`capabilities.is_active("acs.firebird_read")` → `acs_firebird_enabled`, **which
is protected and which the LLM cannot write** (refused in the run above). It
also needs `firebird-driver` installed and an ACS config DB present.

So this is **pre-positioning, not execution**: the model can silently set the
path today, and it becomes live only if an operator later enables a protected
capability for legitimate reasons. The operator flipping that switch has no
prompt to re-verify the paths, and `/acs` renders the switch, not the paths.
That is a real risk and it is worth fixing — it is *not* an LLM-to-code-execution
bug, and the ADR must not claim it is.

This is the same severity discipline that corrected the
`POST /api/events/control` finding: reachability has to be asserted against the
deployed configuration, not the default one.

### The enforcement surface is one line

`is_protected_setting` has exactly **one** production caller:
`admz/mcp/server.py:3598`. There is no generic REST fleet-settings write route —
`admz/api/routes/devices.py:729/737/748` are `GET` only. Every other writer is a
purpose-built authenticated handler writing fixed keys.

`admz/fleet_settings.py:126` and `admz/authz.py:171` both say "REST handlers and
the MCP tool"; the REST half is stale and should be corrected.

**Consequence for this plan: the blast radius is one predicate and one call
site.** That is why this is a small change wearing a large issue.

### FR-SEC-012 has already drifted the same way

`docs/specification/requirements/security.md` FR-SEC-012 lists **three** things
as protected: the `confirm_level_*` namespace, `confirm_password_hash`, and
`tool_get_credentials_enabled`. The set actually holds **30** keys — the
chatbot, health, survey, capability and GitHub App keys are all absent from the
requirement.

Even the requirement document could not keep an enumerated deny-list current.
Under inversion FR-SEC-012 becomes a sentence that cannot go stale: *"the MCP
tool may write only the keys in `LLM_WRITABLE_SETTING_KEYS`; everything else is
refused."*

### The allow-set was validated by attempted falsification, not by assumption

An allow-set of two keys derived from documentation is exactly the kind of
design that breaks a real chat flow and gets reverted. So it was attacked rather
than assumed: an exhaustive search for **any** evidence that the model writes,
or is told to write, a third key. Searched and found nothing in:

- the whole demos subsystem (`admz/demos/**`, 16 modules) — zero matches for
  `fleet_setting` / `set_fleet`. Demo *fragments* (ADR-0047) are device config
  keys in git, not fleet settings;
- `admz/chatbot/system_prompt.py`, read in full (737 lines) — no occurrence of
  `set_fleet_setting`; the only fleet-settings references are **reads**
  (`:278`, `:332`). Both conditional blocks were checked, and
  `_CAPABILITIES_GUIDANCE:504-506` says the opposite outright — *"You cannot
  turn any of these on or off. There is no tool for it, deliberately"*;
- module-contributed prompt sections — the only non-empty contributor is
  `admz/modules/acs_pro/__init__.py:20-51`, which instructs no settings write;
- every `admz/mcp/tools/*.py`, `admz/chatbot/**`, `admz/operations.py`;
- `docs/` — no user story, requirement or walkthrough has the model set any key
  other than the credential pair;
- every test: **one** asserts a successful `set_fleet_setting` write
  (`tests/test_confirm_store.py:495-500`, `default_username`); every other is a
  refusal assertion.

The five `event_*` keys are the only genuine loss, and they are an
*undocumented, untested, never-written* operator escape hatch rather than a chat
flow — which is why §9 restores them via the CLI instead of the allow-set.

### The spec already asked for something stricter — and it was never built

Two accepted documents say `set_fleet_setting` should not be in the chat
model's toolset **at all**:

- ADR-0024 §42-44 — *"defaulting to a safety-conscious allowlist that excludes
  the most sensitive ones (`get_credentials`, `set_fleet_setting`, etc.)"*
- `user-stories/chatbot-driven-workflows.md:119-123` (US-CB-006) — *"likely `*`
  minus `get_credentials`, `create_temp_credentials`,
  `cleanup_temp_credentials`, `set_fleet_setting`"*

**Neither is implemented.** There is no allow/deny-list code anywhere in
`admz/` (`chatbot_tool_allowlist`, `tool_denylist`, `ALLOWLIST`, `DENYLIST` →
zero hits), and `admz/chatbot/mcp_bridge.py:41-100` does no filtering — `:51`
says it *"exposes the same 19 tools that external MCP clients see"*.

Two consequences. First, this inversion is **less** restrictive than what the
spec already decided, which considerably lowers the risk that it is the wrong
call. Second, it is a fifth instance of the same pattern as the four failures: a
control that exists in prose and not in code. It is out of scope here — but it
should be filed, after checking it is not already tracked, because the
chatbot tool surface is a broader question than fleet settings.

### What #176 established, and what transfers

`admz/confirm_policy.py` is a **leaf importing nothing from `admz`**, created
because `confirm_store` already imports `fleet_settings` at module scope, so
deriving upward is a cycle.

What transfers is the **leaf placement**, not the derivation: `confirm_level_*`
was derivable because a closed policy table already existed. No such table
exists for "all fleet settings" — that absence is the problem. So this plan
creates the declaration rather than deriving one.

---

## Design

### 1. `admz/setting_policy.py` — a new leaf

Same slot and same constraint as `confirm_policy.py`: imports nothing from
`admz`, so `fleet_settings` can import it without a cycle and the stdio MCP
subprocess can load it without dragging in FastAPI.

```python
#: The ONLY fleet-setting keys the chat model may write through the generic
#: MCP set_fleet_setting tool. Everything else is refused.
#:
#: Adding a key here grants the LLM write access to it. That is the whole
#: point of the list being short: the diff should read as a grant.
LLM_WRITABLE_SETTING_KEYS: frozenset = frozenset({
    "default_password",
    "default_username",
})

def is_llm_writable(key: str) -> bool: ...
```

Named for what it **grants**, not what it withholds. `UNPROTECTED_SETTING_KEYS`
(as #212 §4 suggested) describes the same set but invites the opposite reflex:
a contributor hitting a red test reaches for the shortest path out, and "add my
key to the not-protected list" reads as bookkeeping. "Add my key to
`LLM_WRITABLE_SETTING_KEYS`" reads as a grant, and a reviewer asks why.

### 2. The predicate inverts

```python
# admz/fleet_settings.py
def is_protected_setting(key: str) -> bool:
    return not is_llm_writable(key)
```

The `confirm_level_*` namespace rule becomes redundant. **Keep it anyway**, as a
second clause that can only ever refuse more:

```python
    return is_confirm_level_key(key) or not is_llm_writable(key)
```

It costs nothing, it documents the invariant the personas and glossary promise,
and it means a mistaken entry in the allow-set still cannot reopen #152.

### 3. `PROTECTED_SETTING_KEYS` survives, derived and non-authoritative

Nine test sites and five spec documents reference the name. Deleting it to make
a point would turn nine assertions into assertions about nothing — the exact
vacuity #176 diagnosed.

It stays, redefined as *"every known protected key"*, with a docstring stating
plainly that **it no longer decides anything** — `is_llm_writable` does — and
that it exists for documentation and for the guard tests. Its contents are the
union of today's 30 plus the 18 newly protected keys, derived from the scanner's
key inventory so it cannot drift from reality again.

### 4. Capture-only for `default_password`

The spec already says the model must never handle the value:

- `docs/specification/user-stories/credential-management.md:82-87` — *"The LLM
  calls `set_fleet_setting(key="default_password")` (with `value` omitted)."*
- `docs/specification/user-stories/device-onboarding.md:84-85` — *"set via the
  OOB `/capture/fleet/{token}` flow — **never typed into the LLM chat**."*
- `docs/specification/requirements/mcp-server.md:53-56` (FR-MCP-008).
- `admz/chatbot/system_prompt.py:302-306` — *"NEVER ask for, accept, echo, or
  pass a password as a tool argument in chat."*

The code allows what the prose forbids. So: `set_fleet_setting("default_password",
value=<anything>)` is **refused**; value-omitted returns the capture URL exactly
as today. This makes the code match FR-MCP-008 rather than adding a restriction,
and as a side effect no password value ever reaches the tool call — which closes
#217's leak *for this tool* at the source. #217 still ships separately: a
name-only redactor is blind to every `{key, value}`-shaped tool.

`default_username` keeps its ordinary value write — it is not a secret, it is
the documented other half of the credential pair, and it is the positive control
in `tests/test_confirm_store.py:481-500`.

### 5. The capture path — one gate to add, and one trap not to fall into

`_set_fleet_setting(key, value=None)` creates a capture session for **any** key
whose name contains `"password"` (`admz/mcp/server.py:3608`) — a substring test,
not an allow-list — and `admz/api/routes/capture.py:325-326` then writes it with
no protected-key check at all. Both sites must consult `is_llm_writable`, so
that `some_other_password` cannot mint a session and a stale or forged session
cannot write a non-allow-listed key.

**The trap.** `capture_store.create_fleet_session()` has exactly **one** caller
in the entire codebase — `admz/mcp/server.py:3610` — and it sits *below* the
protection gate at `server.py:3598`:

```
3598   if is_protected_setting(key):  return {"success": False, ...}   # gate
...
3610   session = capture_store.create_fleet_session(...)               # sole caller
```

`admz/api/routes/capture.py:325-326` is in turn the only non-MCP writer of
`default_password` / `default_username`, and its form is unreachable without a
token that only line 3610 can mint.

So **protecting `default_password` would kill the capture-URL generator, and
with it the only path to the only other writer of the credential pair.** Both
keys would become settable only by hand-editing SQLite.

This plan does not hit that trap — `default_password` and `default_username` are
the two allow-listed keys, so the gate does not fire and line 3610 stays
reachable. It is documented here because it is a landmine for anyone who later
"tightens" the allow-set, and because it explains why §4 refuses *a supplied
value* rather than protecting the key outright. The distinction is load-bearing,
not stylistic.

A regression test must assert that `set_fleet_setting("default_password")` with
the value omitted still returns a capture URL.

### 6. `set_event_ingest` is deliberately outside this model

The MCP tool `set_event_ingest` (`admz/mcp/tools/demos.py:382-399` →
`admz/mcp/server.py:2567-2585` → `admz/operations.py:916`) writes
`event_ingest_enabled` — **a protected key** — without consulting
`is_protected_setting`. It is gated instead by an ADR-0034 approval card.

This is correct and must not be "fixed". Two different doors:

- The **generic** `set_fleet_setting` tool is governed by the allow-set.
- A **purpose-built** tool for one setting is governed by its own gate, which
  is stronger — a human approves each use.

The ADR states this explicitly so a future reader does not route
`set_event_ingest` through the allow-set and silently remove its approval card,
or add `event_ingest_enabled` to the allow-set to "make it consistent".

### 7. Audit — the two cheap fixes here, the leak in #217

MCP writes *are* audited, contrary to #203's framing: the `call_tool` wrapper
records `mcp.set_fleet_setting` at `admz/mcp/server.py:1767-1781`. Two defects
are in scope:

- **The setting key is absent from `resource`.** `_tool_resource`
  (`server.py:263-284`) appends only `device_id`/`account_id`/`operation_id`, so
  an audit query cannot find writes to a given key. Web rows encode it
  (`confirm_settings:levels`). Fix: append the key.
- **Refusals record `success=True`.** The protected-key refusal returns a dict
  rather than raising, so `audit_success` stays True (`server.py:1735`). A
  blocked attempt — precisely the interesting event — is indistinguishable from
  a successful write. Fix: mark the refusal.

Out of scope, in #217: `_sanitize_tool_args` → `redact_structure` masks by key
*name*, and the argument is literally named `value`, so a supplied password is
recorded in cleartext.

### 8. The scanner test — resolve constants, do not match names

The guard that makes the inversion durable. It must enumerate from **behaviour**,
because the three-way enumeration disagreement above proves name-matching
inherits its author's blind spot.

Shape: walk `admz/**` with `ast`, collect every string literal that reaches
`fleet_settings.get/set/delete` or a module-local `_settings()`/`_fs()`/
`_setting()` wrapper, **resolving module-level constants bound to string
literals** (`USER_SETTING_KEY = "config_ignore_patterns"`, `_TOKEN_KEY = "..."`,
`FLEET_KEY = "acs_pro"`). Assert every key found is either in
`LLM_WRITABLE_SETTING_KEYS` or in `PROTECTED_SETTING_KEYS`.

Constant resolution is what makes it cover #177's three sites:
`admz/github_app/secrets.py:26-29` and `admz/chatbot/config.py:61-62` bind
literals to constants, and `admz/fleet/health.py:115-149` uses inline literals
(the residual #176 left open). All three then need no hand-maintained agreement
list — the agreement is checked by construction. This is the sense in which
#212 §4 is right that the scanner subsumes #177, and the sense in which it is
only right *if* the scanner resolves constants.

Known limit, to be stated in the test's docstring rather than papered over: a
key computed at runtime (an f-string, a `%` format, a name from config) is
invisible to a static scanner. `confirm_level_*` is exactly that case, which is
why its **namespace** rule is kept in §2 rather than retired.

### 9. Nine orphaned keys, and the CLI that unblocks them

**This is the finding that shapes the migration, and the most likely cause of a
revert if ignored.**

An exhaustive per-key write-path sweep found that **nine of the eighteen keys
have no writer at all except `set_fleet_setting`** — no authenticated route, no
settings form, no CLI, no environment-variable fallback. A template sweep across
`admz/api/templates/**.html` for all eighteen names returned **zero matches**,
so no UI path was missed.

| Key(s) | Non-MCP writer | Effect of protecting it |
|---|---|---|
| `config_ignore_patterns` | `web.py:661`, Settings → ignore-patterns textarea | none — human path exists |
| `config_ignore_rules` | `snapshot.py:1166-1168` → `ignore.py:231` | none — human path exists |
| `acs_pro` | `acs_pro/routes.py:56` → `config.py:105`, Settings → Modules card | none — human path exists |
| `acs_webhook_token` | `acs_pro/routes.py:286` → `webhook.py:49`, /acs Regenerate button | none — human path exists |
| `config_ignore_seed_version` | `ignore.py:258`, startup lifespan only | none operationally — self-maintaining marker |
| `snapshot_gc_enabled`, `snapshot_gc_aggressive` | none | **none — both keys are entirely inert.** Setters *and* readers have zero production callers; the CLI `admz maint gc --aggressive` passes its flag straight to `run_gc()`. Already flagged at `docs/specification/review-2026-06-10.md:221` |
| `event_topic_filters`, `event_store_categories`, `event_ingest_tag`, `event_store_max_rows`, `event_store_retention_days` | **none** | five documented "fleet-overridable" operator controls become hand-edit-SQLite-only |
| `health_verify_credentials` | **none** | removes the documented escape hatch at `requirements/fleet-health.md:70`; credential verification becomes permanently forced on |
| `acs_fb_fbclient`, `acs_fb_install`, `acs_fb_data_dir` | **none** | a non-standard ACS install has **no remedy**: `firebird_available()` reports `"fbclient.dll not found"` and `/acs` surfaces that reason with no field to fix it |

Note `POST /api/events/control` does **not** help: it writes
`event_ingest_enabled` / `acs_event_ingest_enabled` / `acs_firebird_enabled` —
three *different* keys, all already protected. It never touches the five filter
and retention keys.

**The options, and why the third wins.**

1. **Widen the allow-set to include the nine.** Rejected. It re-grants the model
   exactly the controls this issue exists to take away, including a native
   library path and the event-retention dials.
2. **Protect them and accept the degradation.** Rejected. Nine documented
   operator overrides silently become unusable. That is the shape of change
   that gets reverted, and it would be reverted correctly.
3. **Protect them and add `python -m admz settings` — adopted.** ADR-0020
   already lists "no CLI for protected keys" as a known negative consequence and
   a *"small Phase-5 follow-up"*. Inversion is what makes it load-bearing: one
   subcommand restores operator control over **all** protected keys at once —
   today's 30, the 18 newly protected, and every key added later — with no
   per-key UI work and no new web surface.

The accountability model is the one ADR-0020 already describes: writes from an
authenticated principal are allowed because that caller is accountable. Someone
running `python -m admz settings set` has service control on the box, which is
strictly more authority than a browser session. The subcommand writes an audit
row with a `cli` principal source, mirroring `capabilities.set_enabled`.

Ships in the **same PR** as the inversion. Splitting it would mean merging a
commit that knowingly removes nine operator controls and promising to restore
them later.

Two smaller options the owner may prefer for a subset, recorded but not adopted:
`acs_fb_*` could instead take environment-variable fallbacks (the pattern
`admz/capabilities.py` uses, and arguably the better fit for a path override on
an oddly-installed machine); `health_verify_credentials` could become a declared
row in `admz/capabilities.py` and inherit the `/settings/advanced` toggle for
free. Both are additive to the CLI, not alternatives to it.

---

## File-level implementation

### New

| File | What |
|---|---|
| `admz/setting_policy.py` | `LLM_WRITABLE_SETTING_KEYS`, `is_llm_writable`. Leaf; imports nothing from `admz`. |
| `tests/test_setting_policy.py` | The scanner; inversion behaviour; capture-path gate; the allow-set is exactly two keys. |
| `docs/specification/decisions/0053-llm-writable-fleet-settings.md` | This decision. *(ships in the plan PR)* |

### Changed

| File | What |
|---|---|
| `admz/fleet_settings.py` | `is_protected_setting` inverts; `PROTECTED_SETTING_KEYS` redefined as derived + non-authoritative, docstring says so; module docstring's "Known keys" list corrected. |
| `admz/mcp/server.py` | `_set_fleet_setting`: refuse a supplied value for `default_password`; gate the capture branch on the allow-set; drop the now-unused `PROTECTED_SETTING_KEYS` import at line 45. `_tool_resource`: include the setting key. `call_tool`: refusals audit as `success=False`. |
| `admz/api/routes/capture.py` | Gate the `fleet_settings.set` at 325-326 on `is_llm_writable`. |
| `admz/mcp/tools/fleet.py` | Tool description: say the tool writes only the fleet credential pair, and that a password is set via the capture URL, never by value. The description is the model's contract — it should not advertise more than the code allows. |
| `admz/__main__.py` | New `settings` subcommand — `get` / `set` / `delete` / `list` — the operator path to every protected key (§9). Audited with a `cli` principal source, mirroring `capabilities.set_enabled`. |
| `admz/authz.py` | Docstring at 171: correct the stale "REST handlers" claim. |
| `docs/specification/requirements/security.md` | FR-SEC-012 rewritten around the allow-set; note the 30-vs-3 drift it had. |
| `docs/specification/requirements/mcp-server.md` | FR-MCP-008: the value-omitted capture flow is now enforced, not just described. |
| `docs/specification/decisions/0020-protected-fleet-settings.md` | Amendment pointing to ADR-0053; the deny-list model is superseded. |
| `tests/test_fleet_health.py` | The `health_*` equality lock at 878-881 — see Migration risk. |
| `tests/test_credential_gate_split.py` | The negative assertion at 217 — see Migration risk. |

---

## Test plan

### Success cases

- `default_username` writes (the existing positive control, `test_confirm_store.py:481-500`, must still pass unchanged).
- `default_password` with value omitted returns a capture URL — **the §5 trap
  regression test**; this is the assertion that fails loudly if anyone later
  promotes `default_password` out of the allow-set.
- The capture submit at `/capture/fleet/{token}` still writes the pair.
- `set_event_ingest` still works and still produces its approval card.
- `admz settings set <protected key>` writes, and emits an audit row with a
  `cli` principal source — asserted for at least one key from each orphaned
  group (`event_*`, `health_verify_credentials`, `acs_fb_*`), since restoring
  those nine controls is the CLI's reason for existing.

### Failure cases

- Each of the 18 keys is refused, **parametrised over a list derived from the
  scanner** rather than hardcoded — the #176 lesson: a literal is fine as an
  expectation, never as the iteration source for a coverage claim.
- `default_password` **with** a value is refused.
- A capture session cannot be created for a non-allow-listed key containing
  `"password"` (e.g. `some_other_password`).
- An invented key is refused.
- A `confirm_level_*` key invented at runtime is still refused (the namespace
  rule survives the inversion).

### Guard

- The scanner finds every key in the 18-key list and every key in
  `PROTECTED_SETTING_KEYS` — i.e. it would have caught all four failures. Assert
  this against a fixture of the known-44 so the scanner itself cannot silently
  regress to finding nothing.
- `LLM_WRITABLE_SETTING_KEYS` has exactly two members, so growing it is a
  deliberate test edit.

### Full suite

`C:/admz/admz/.venv/Scripts/python.exe -m pytest -q` — ~3,230 tests, ~15 min,
isolated `ADMZ_HOME`. Foreground/background with a blocking wait; a partial run
is not a green run.

---

## Migration risk

| Risk | Detail | Handling |
|---|---|---|
| **`tests/test_fleet_health.py:878-881`** | `==` equality lock over the `health_*` slice of `PROTECTED_SETTING_KEYS`. Adding `health_verify_credentials` breaks it **by design**. | Update in the same PR. Do **not** loosen `==` to `⊇` — #176's PR body explains why the lock exists. |
| **`tests/test_credential_gate_split.py:217`** | Asserts `"web_reveal_credentials_enabled" not in PROTECTED_SETTING_KEYS`. Under inversion the set means something different and this may flip. | It encodes a real CR-3 distinction. Decide deliberately; do not mechanically edit. |
| **`acs_pro` becomes unwritable from chat** | Protecting the module master switch means ACS can no longer be enabled from a chat turn. | `POST /api/acs/config` exists (`admz/modules/acs_pro/routes.py:53-63`), so a web path remains. Confirm it is reachable and works **before** protecting the key. |
| **Nine orphaned keys** | `event_*` ×5, `health_verify_credentials`, `acs_fb_*` ×3 have **no** non-MCP writer, no UI, no env fallback. Protecting them removes nine documented operator controls. | **Resolved by §9** — the `admz settings` CLI ships in the same PR. This was the single most likely cause of a revert; it is why the CLI is in scope rather than deferred. |
| **The capture-branch trap** | `create_fleet_session` has one caller, below the gate; it is the only path to the only non-MCP writer of the credential pair. | Both keys stay allow-listed, so the gate never fires on them. Regression test asserts the capture URL still issues. Documented in §5 as a landmine for future tightening. |
| **ADR-0020's known gap** | "No CLI for protected keys" was already a listed negative consequence; inversion moves 18 more keys behind it. | Closed by §9 rather than widened. Record in ADR-0053 that the follow-up is now done. |
| **Nine test sites reference `PROTECTED_SETTING_KEYS`** | If the name lost its meaning they would go vacuous. | Mitigated by design §3 — the name survives with real contents. |
| **`tests/test_mcp_tools_split.py:43`** | `assert names == {"get_fleet_settings", "set_fleet_setting"}` — an equality lock on the fleet tool names. | Safe: this plan changes the tool *description*, not its name, and does not remove it. Noted so a future "just drop the tool" reading of ADR-0024 knows where it will fail. |

---

## PR slicing

1. **Plan PR (docs only)** — this file + ADR-0053. Merge before implementation,
   per `docs/specification/process.md`. Issue moves `status: planning` →
   `status: ready`.
2. **Implementation PR** — `setting_policy.py`, the inversion, the capture-path
   gate, the two audit fixes, the scanner test, and every doc whose behaviour
   description changes (FR-SEC-012, FR-MCP-008, ADR-0020 amendment). One PR:
   the inversion and its guard test are not independently shippable, and the
   process rule is that the PR shipping behaviour also fixes the docs describing
   it.

#217 (audit redaction) and #164 (events authz) ship separately and are not
blocked by this.

---

## Acceptance criteria

- [ ] Every one of the 18 reproduced keys is refused by `set_fleet_setting`.
- [ ] `default_username` still writes; `default_password` still returns a
      capture URL when the value is omitted; `default_password` **with** a value
      is refused.
- [ ] The capture branch and the capture-submit route both consult the allow-set.
- [ ] `admz settings set/get/delete/list` works against every protected key, is
      audited, and is documented — so none of the nine orphaned controls is lost.
- [ ] `set_event_ingest` still works, still gated by its approval card, and the
      ADR says why it is outside the model.
- [ ] The scanner resolves module-level constants and finds all three #177 sites.
- [ ] Audit rows for MCP setting writes carry the key in `resource`; refusals
      record `success=False`.
- [ ] `PROTECTED_SETTING_KEYS` still exists with real contents; all nine
      existing test sites still assert something true.
- [ ] FR-SEC-012 no longer enumerates, and its 30-vs-3 drift is noted as fixed.
- [ ] Full suite green.

---

## Open decisions for the owner

1. **`tests/test_credential_gate_split.py:217`** — the negative assertion on
   `web_reveal_credentials_enabled`. Recommended: keep the assertion and make it
   explicit that the key is web-writable-but-not-LLM-writable, which is what
   CR-3 meant. Flagging because it is the one test whose *intent* the inversion
   changes rather than its mechanics.
2. **Whether `default_username` should also be capture-only.** Recommended: no.
   It is not a secret, the capture page already writes it alongside the
   password, and it is the only successful-write test in the repo — making it
   capture-only would remove the positive control that proves
   `_set_fleet_setting` does not refuse *everything*.
