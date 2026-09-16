# Plan: fold Fleet Settings into Settings (provisioning credentials)

**Status:** shipped 2026-09-16 in two PRs — the credentials card (#499), then
the summary rows below. Source: the owner's design handoff
`design_handoff_fleet_settings` (`Settings (redesigned).dc.html`), recreated as
Jinja on the classes already in `admz/api/static/css/admz.css`.

## Why

`/fleet-settings` carried three controls — the fleet root password, the entry
list, and the raw settings table — on markup whose classes (`.account-info`,
`.no-accounts`, `.button`, `.password-reveal`, `.actions-footer`) are defined
only in `static/css/style.css`, which `base.html` never links. The page
therefore rendered unstyled, set no `nav_active` / `crumb_tail`, and duplicated
a Settings page that already had a card + setting-row system.

## What shipped

- **`/settings` gains a "Provisioning credentials" card** (`id="provisioning-credentials"`):
  the fleet root password row (status badge, the rotation caveat, a collapsed
  form) and the entry-credential row (stored count, help, one row per entry with
  a remove form, a collapsed add form), then one lock line about the gate.
  Opening one form closes the other; a refused write re-renders with the form
  reopened and the flash above it.
- **A collapsed "Advanced · raw fleet settings"** `<details class="card">` with
  every key, sensitive values still placeholdered and fetched from the gated
  reveal endpoint. Three CSS rules were added for the disclosure marker.
- **`/fleet-settings` redirects** to `/settings#provisioning-credentials`, and
  `fleet_settings.html` is deleted. The three POST endpoints keep their URLs,
  their gates and their audit rows, and render `/settings`.
- **Removed:** the "Credentials & secrets" card (three fixed "enforced" rows —
  policy statements with no control), the "Back to Devices" footer, and the
  multi-paragraph explanations. The Health-monitoring row that linked to the
  retired page now states the poller's actual interval, timeout and state.
- **Copy:** "Break-glass root password" → "Fleet root password" in the UI. The
  setting key and the audit rows are unchanged. This first pass renamed the row
  only. The owner found the old name still in the flash beneath it, and the
  follow-up on 2026-09-16 renamed it in everything an operator reads, the MCP
  text included (FR-CRED-014). That follow-up also moved the fleet root
  password to the front of the sign-in order (ADR-0068's amendment).

## The per-row "tried" pills are gone, deliberately

`stored_tried` is a posture flag, not a per-device status: with
`MAX_STORED == MAX_ATTEMPTS_PER_PASS` every stored entry is tried unless the
prompt-always posture is on, so a pill per row read as a per-device claim ADMZ
cannot make. The page states the posture once — the stored count, the fallback
clause, and a note when nothing stored is tried. The flags are still computed in
`_entry_credentials_view` and still pinned, on the view model
(`tests/test_entry_promotion.py`) and in `tests/test_entry_credentials.py`.

## Follow-up: the summary rows (shipped 2026-09-16)

The owner first scoped #499 to the credentials, then asked for the rest:

- **Card order** now matches the handoff: Safety policy, Provisioning
  credentials, Health monitoring, Configuration repository, Modules, Advanced.
  The **Network discovery** card is gone — it is not in the design, and its only
  control linked to the API docs; discovery runs from Devices and the console.
- **Configuration repository** carries two summary rows. *Configuration
  tracking* counts built-in ignores, scoped rules and custom patterns, and its
  full editor (scoped-rule removal, the pattern textarea) opens in place. It is
  open after a save and when the page is reached at `#config-tracking`, the
  anchor the save redirect and drift pages use. *GitHub config backup* is the
  row itself: status badge, then Connect, Finish/Cancel or Test/Disconnect, with
  the connect flow's flashes on the row it redirects to (`#github-backup`).
- **Modules** is one row per module; ACS Pro's form opens in place behind
  Configure, with every element id its script uses unchanged.
- **Health monitoring** now shows what the monitor runs with
  (`fleet.health.effective_settings`). #499 re-derived defaults in the template
  and got two wrong: an unset interval read "300s" while the monitor ran every
  60s — production has no interval key — and an unset verify flag hid
  "verifying credentials", whose default is on.
