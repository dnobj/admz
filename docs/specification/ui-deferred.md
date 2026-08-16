# Deliberately deferred UI surfaces — the register

A UI surface that looks unfinished is one of two things: a defect, or a decision. This
file exists so that an automated review can tell them apart without asking. **If a surface
is listed here, it is a decision** — an autonomous UI/UX audit must not report it as a
gap, and a reviewer should not read its absence as neglect.

Two rules keep this file honest:

- **A row is a pointer, not a description.** The durable *why* lives in the requirement
  that owns the deferral (`📋` / `⚠️📋` markers, `KL-*` sections) — this table only points at
  it. Restating the reason here would create a second copy that goes stale
  ([process.md](process.md), "prefer deleting the paraphrase to updating it").
- **Every row has a GitHub issue labelled `status: future`.** The spec records that a thing
  is deferred (build state); the issue records that it is *tracked* (work state) and is
  where the discussion happens when it is un-deferred. A row without an issue is
  incomplete; an issue without a row is invisible to the audit. Both are findings.

Rows are removed when the surface ships — in the same PR, per process.md.

## The register

| Surface (what a user would look for) | What exists today | Owning spec ID(s) | Tracking issue |
|---|---|---|---|
| **Organization selection / switching** — pick or change the active Org | The topbar shows an org *label* (`build_nav` picks the first non-default Org, else `default`); no switcher, no Org CRUD in the UI | [hierarchy.md](requirements/hierarchy.md) FR-HIER-013 📋, KL-HIER-004 | _to be filed_ |
| **Site management** — create / rename / move devices between Sites from the UI | The sidebar Site *switcher* works (`/ui/site/{site_id}`, cookie-scoped); management is registry-level only | [hierarchy.md](requirements/hierarchy.md) FR-HIER-013 📋 | _to be filed_ |
| **Site-scoped authorization** — restrict who sees which Site | Every authenticated principal sees the whole fleet | [hierarchy.md](requirements/hierarchy.md) NFR-HIER-004, KL-HIER-001 | _to be filed_ |
| **Per-Site settings** — a different `default_password` etc. per Site | `fleet_settings` is global | [hierarchy.md](requirements/hierarchy.md) KL-HIER-002 | _to be filed_ |
| **Saved tag selectors ("smart groups")** in the sidebar | Flat tags only | [hierarchy.md](requirements/hierarchy.md) KL-HIER-003, ADR-0032 | _to be filed_ |
| **Network discovery page** — run a scan and review results in the browser | No route, template or nav entry; only `POST /api/discovery/scan` and the chat tool. The Settings card's *Run discovery* control currently links to the API docs. Direction is being designed by the owner | [discovery.md](requirements/discovery.md); [#404](https://github.com/dnobj/admz/issues/404) (`status: planning`) | #404 |
| **Drift dashboard** — a page listing drifted devices/keys fleet-wide | Drift renders per device (grouped by rule, #247); no fleet-wide page. English rendering of a rule diff is separately deferred | [web-ui.md](requirements/web-ui.md) KL-UI-003 📋 | [#248](https://github.com/dnobj/admz/issues/248) (rendering); dashboard: _to be filed_ |
| **Bulk device edit** — edit many devices at once | Per-device forms only | [web-ui.md](requirements/web-ui.md) KL-UI-004 📋 | _to be filed_ |
| **Attention-first UI (no persistent left nav)** | The current page-based nav | — (idea stage) | [#122](https://github.com/dnobj/admz/issues/122) |
| **Strict CSP (no `unsafe-inline`)** | 699 inline constructs remain | — | [#277](https://github.com/dnobj/admz/issues/277) |
| **Restyle of the create-demo / add-signal dialogs** | Plan merged, awaiting a Build session — a known inconsistency, not a new finding | plan `docs/plans/demo-modal-restyle.md` | [#116](https://github.com/dnobj/admz/issues/116) (`status: ready`) |

_"to be filed"_ rows are the bootstrap debt of this register: the first run of the UI audit
loop files one `status: future` issue per row (after searching open **and** closed issues
for an existing one) and replaces the placeholder with the number in a docs PR.

## What is **not** deferred — do not add these here

Things a reviewer might be tempted to excuse but which are ordinary work, and should be
reported or fixed:

- A control that does nothing, or leads somewhere unrelated to its label.
- A page reachable from the nav or from another page that 404s or 500s.
- Two pages doing the same job in different visual vocabularies when neither is listed
  above (the register is for *absent* surfaces; *duplicated* ones are findings).
- Documentation that describes UI which does not exist, or omits UI that does.

## How the audit uses this file

The autonomous UI/UX audit loop (contract: `C:\admz\.claude\loops\track-ui.md`, outside
the repo) reads this table before filing anything. Its rule is:

1. Matches a row → not a finding. Silent.
2. Looks deferred but has no row → propose the row **and** file the `status: future` issue,
   in one docs PR. That PR is the finding.
3. Neither → an ordinary finding: a fix PR when the change is small and safe, an issue
   otherwise.
