# ADR-0030: Survey / contributor mode — distributed read-only API discovery feeding axis-api-atlas via GitHub PRs

**Status:** ✅ Implemented and merged. Survey mode ships in `admz/survey/`
(collector, validator, secret-scan gate, bundler, fork-and-PR) with a
`/survey` UI route and a `survey` scheduler job type (ADR-0026).
**Date:** 2026-06-06. **Updated:** 2026-06-10.
**Relates to:** ADR-0029 (axis-api-atlas as a maintained reusable asset), ADR-0010 (Fernet encryption), ADR-0009 (OOB credential capture), ADR-0026 (job_type scheduler dispatch), ADR-0007 (per-protocol auth), [axis-api-atlas `docs/design/survey-contributor-mode.md`](https://github.com/mrdnlabs/axis-api-atlas/blob/main/docs/design/survey-contributor-mode.md)

---

## Context

The Axis API Atlas (ADR-0029) grows by someone pointing a discovery tool at a real
device. The number of Axis models/firmwares in the field vastly exceeds what any
one maintainer can physically access. ADMZ is being distributed to a set of
trusted internal experience-center operators who already have fleets and an
interest in this data.

We want those deployments to **help map the long tail**: surface devices/firmware
the atlas has never seen, and confirm that cataloged-but-untested ops actually work
on real hardware — then feed that back for review. The hard constraints:

- credentials and site-sensitive data must **never** leave the operator's site;
- we do **not** want to run an LLM on contributor systems (cost, trust, and the
  enrichment work is better centralized);
- contributions must be **reviewable**, not blindly trusted;
- it must be **opt-in** and obvious about what it sends.

Consumer-only installs do not participate; this is a deliberate, per-install opt-in.

## Decision

Add an opt-in **survey / contributor mode** to ADMZ that surveys reachable devices
read-only, redacts everything site-sensitive, and submits findings to
`mrdnlabs/axis-api-atlas` as **GitHub pull requests** authenticated with a
contributor-supplied fine-grained PAT (fork-and-PR; never a push to upstream).
Offline bundle export is the fallback for air-gapped sites.

Key choices:

1. **Deterministic on the edge, enrichment central.** The collector produces only
   deterministic artifacts — capability snapshots, OpenAPI **schemas**, draft ops
   (via `axis_api_atlas.tools.seed_from_openapi`, safe-default risk), and
   validation evidence. All LLM/human enrichment (synonyms, descriptions, risk
   confirmation) happens at PR-review time, not on contributor systems.
2. **Read-only by default; risk-tiered validation.** Discovery is GET/DCA/OpenAPI
   only. Validation maps to the catalog's own `risk_level`: Tier 0 (read-only) runs
   anywhere opted-in; Tier 1 (service-affecting) runs only on devices the operator
   tags `lab`/`test`, per-op opt-in, via **idempotent write-back** (read current
   value → write it back unchanged → confirm); Tier 2 (dangerous) is never run.
3. **Credentials never leave site.** The collector authenticates with the
   operator's own stored creds (per-protocol, ADR-0007). Bundles carry no secrets;
   serials are HMAC-hashed by default. The PAT is stored **encrypted** with the
   registry Fernet key (ADR-0010), never as plaintext, never exposed to MCP.
4. **Defence in depth on secrets.** Edge redaction (allow-list) **plus** a
   fail-closed secret scanner that the atlas CI runs on every PR. A single finding
   fails the PR — the bundle is rejected, not "fixed".
5. **Nothing auto-merges.** PRs are proposals. CI gates them; the maintainer
   promotes (`contrib.cli promote`) and enriches before merge.

Mechanics live in `admz/survey/` (collector, redact, diff, validate, bundle,
github, runner) with a default-OFF settings page (`/settings/survey`, disclosure +
"preview exactly what gets sent" + run-now) and a `survey` scheduler job_type
(ADR-0026). The ingest format, validator, secret scanner, seeder, and promote step
live in the atlas's `axis_api_atlas.contrib` / `.tools` packages.

## Consequences

- The atlas gains a multi-contributor growth path without ADMZ re-embedding catalog
  data (it stays a pure consumer of the package per ADR-0029).
- A new secret (the PAT) lives in ADMZ; it is encrypted at rest and PROTECTED from
  MCP writes, but it is still a credential to safeguard and rotate.
- Survey mode contacts devices on a schedule when enabled — a background loop that,
  like the health poller, is opt-in and gated so the LLM cannot enable it.
- Tier-1 write-back, though designed to be net-zero, still issues a write to a
  service-affecting endpoint; it is therefore lab-only + per-op opt-in and wants
  live validation before being relied on.
- Liability of writes on production hardware is bounded by tagging: production
  devices are read-only with no UI override.

## Alternatives considered

- **Branch-on-upstream instead of fork-and-PR.** Lower friction for the trusted
  cohort, but requires write access for every contributor; rejected for least
  privilege and to survive the program growing.
- **Phone-home to a bespoke ingest service.** More moving parts and a server to run
  and secure; GitHub PRs reuse infrastructure we already have and make review and
  provenance native.
- **Run enrichment on the edge.** Rejected: puts LLM cost/trust on contributors and
  fragments the curation that keeps the atlas coherent.
