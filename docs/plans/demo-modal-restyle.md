# Plan: restyle the create-demo + add-signal dialogs to match the Axis Signal UI

Status: **planned, not implemented** (tracked by the linked GitHub issue).

## Context

Operator report (2026-07-18): the create-demo dialog "looks sort of crummy" and reads
like an older UI. Investigated first — **nothing was reverted and no deploy was
missed**: the 2026-07-16 polish (`cdac27b`, part of the open PR #108 stack) is live —
it replaced the "pick devices later" dead end with a device checklist and made signals
pick from watched events. That polish was **functional**, not visual. What remains is
an aesthetic/consistency gap, and it has a structural cause:

- The shared form/modal vocabulary (`.fld`, `.radio-row`, hints, picklist) is **not in
  the shared stylesheet** (`admz/api/static/css/admz.css`) — `demos.html` and
  `tasks.html` each carry their own `<style>` copies, so the demo dialogs drift from
  the look of the rest of the app.
- The dialogs lean on inline `style=` attributes (26 in `demos.html`, 30 in
  `demo_detail.html`; the well-behaved `edit_device.html` has 9), producing cramped,
  inconsistent spacing and typography.
- The create-demo form is one unsectioned column mixing name/narrative, device
  scoping radios, a scrolling checklist, and the baseline/scenario choice.

## Changes (UI-only; no backend or behavior changes)

1. **Promote the form/modal vocabulary into `admz/api/static/css/admz.css`**: `.fld`,
   `.radio-row`, `.rb`, `.hint`, a new `.picklist` / `.picklist-item`, and modal
   section headers. Delete the duplicated per-template `<style>` copies in
   `demos.html` and `tasks.html` where identical (visual no-op there).
2. **Create-demo modal (`admz/api/templates/demos.html`)**: sectioned layout (About /
   Devices / Config) with the section-label treatment used elsewhere in the app;
   remove all inline `style=` attributes in favor of the shared classes; device
   picklist gains a filter input and a "N of M selected" count (the fleet is 14+
   devices); device model rendered as muted metadata, consistent hint typography and
   spacing. Keep every element id (`f-name`, `device-picklist`, `pick-device`, …) —
   the JS and route tests must not notice.
3. **Add-signal modal (`admz/api/templates/demo_detail.html`)**: the same pass —
   shared classes, no inline styles, consistent watched-event picker presentation
   (keep `s-watch-scope` and the picker behavior untouched).

## Branch note (important)

`demos.html` / `demo_detail.html` on `master` predate the picklist and signal-picker
work — those changes live in the **open PR #108 → #109 → #111 stack**. The
implementation branch must stack on the current tip of that stack (or land after it
merges); branching off `master` would conflict with #108.

## Verification

- Template route tests green unchanged (ids preserved).
- Browser pass on the live dev service: create-demo and add-signal dialogs at desktop
  and narrow widths, light + dark; screenshots in the PR.
- Live smoke: create a throwaway demo via the restyled modal (tag scope and explicit
  device list both), add a signal from a watched event, then delete the demo.
- `grep -c 'style=' demos.html demo_detail.html` drops to ~0 for the dialog markup.
