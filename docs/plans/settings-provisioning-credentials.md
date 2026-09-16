# Plan: fold Fleet Settings into Settings (provisioning credentials)

**Status:** shipped 2026-09-16 (this PR). Source: the owner's design handoff
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
  setting key, the audit rows and the MCP text are unchanged.

## The per-row "tried" pills are gone, deliberately

`stored_tried` is a posture flag, not a per-device status: with
`MAX_STORED == MAX_ATTEMPTS_PER_PASS` every stored entry is tried unless the
prompt-always posture is on, so a pill per row read as a per-device claim ADMZ
cannot make. The page states the posture once — the stored count, the fallback
clause, and a note when nothing stored is tried. The flags are still computed in
`_entry_credentials_view` and still pinned, on the view model
(`tests/test_entry_promotion.py`) and in `tests/test_entry_credentials.py`.

## Deferred (owner's choice, this PR's scope)

The handoff also folds **Configuration tracking** and **GitHub config backup**
into summary rows inside the Configuration repository card, and reduces
**Modules** to a summary row plus a Configure button. Those only restyle cards
whose editors must keep working (the ignore-list textarea, the GitHub connect
flow, the ACS form), so they are a follow-up rather than part of the credential
consolidation.
