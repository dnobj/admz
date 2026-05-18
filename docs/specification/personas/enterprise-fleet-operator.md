# Persona: Enterprise Fleet Operator

## Profile

**Who:** An IT/security operations engineer at a large organization (corporate campus, transit authority, retail chain, stadium, hospital) responsible for hundreds to thousands of Axis devices in production.

**Technical level:** Comfortable with infrastructure-as-code, secret management, automation, CI/CD. Uses HashiCorp Vault or similar for production secrets. Writes scripts and runbooks. Reviews and approves changes; rarely makes them ad-hoc.

**Scale:** 100–10,000 devices spread across multiple physical locations, often segmented by VLAN or subnet. Mixed device types: cameras (PTZ, fixed, thermal), access controllers, intercoms, network speakers, network switches.

**Frequency of use:** Daily for monitoring; weekly for planned changes; rarely for incident response (where speed matters most).

## Goals

- **Store device credentials in Vault**, not in another database. Existing secret-management discipline must extend to Axis devices.
- **Rotate credentials at scale** when an employee leaves, when a credential leaks, or per policy schedule.
- **Apply a configuration change to N devices** without logging into N web UIs.
- **Track and audit who changed what**, when, and with what authorization.
- **Validate planned changes** in dev before production via CI on the config repo.
- **Detect unauthorized changes** to production devices and alert.
- **Stage a major change** (firmware upgrade, password rotation, certificate rollout) as a reviewable, approvable, rollbackable plan.
- **Snapshot every device nightly** to enable point-in-time restore.

## Pains today (without ADMZ)

- Credentials are inconsistent across Vault, spreadsheets, shared password managers, and operator memory.
- Bulk operations are scripted ad-hoc, often poorly tested, with no rollback.
- Auditing "who changed what" is impossible — devices keep no useful audit log of their own.
- Drift between intended and actual device state goes undetected until something breaks.
- Firmware upgrades on a few hundred devices are a multi-day operator-driven slog.

## Use cases (links to user stories)

- [Device onboarding](../user-stories/device-onboarding.md) — discovery + bulk provision.
- [Credential management](../user-stories/credential-management.md) — Vault-backed storage, rotation.
- [Snapshot and restore](../user-stories/snapshot-and-restore.md) — nightly snapshot at fleet scale.
- [Drift and monitoring](../user-stories/drift-and-monitoring.md) — scheduled drift checks.
- [Firmware operations](../user-stories/firmware-operations.md) — fleet-wide firmware upgrade with LTS-aware path.
- [Network discovery](../user-stories/network-discovery.md) — find new devices on production subnets.

## What ADMZ owes this persona

- **Vault as a first-class backend.** AppRole and token auth. Standard Vault KV-v2 paths (`secret/data/devices/...`).
- **Bulk operations as plans.** Anything that touches N devices is staged, validated, and approvable before execution.
- **Risk-classified operations.** Anything `dangerous` is blocked behind explicit confirmation regardless of who initiates it.
- **Audit trail.** Git history of the config repo is the canonical record of *what* changed. An audit log of credential access and operation execution is a known gap that must be addressed.
- **Scaling.** Plan engine parallelizes across devices. Discovery handles subnet-scale. Snapshot of 1000 devices completes in minutes, not hours.
- **CI hooks.** The config repo is a real git repo with branches, PRs, schemas, and CI on every PR.
- **Configuration drift detection.** Scheduled drift checks across the fleet with summary reports.

## What ADMZ doesn't owe this persona (current limits — see known gaps in capability requirements)

- **Authentication to ADMZ itself.** As of 2026-05-17 there is no web/REST auth. Production deployment requires network-level controls (private subnet, VPN, reverse proxy with auth). This is the largest known gap.
- **Continuous monitoring.** Drift detection is poll-based. No webhook/event-driven path. Real-time monitoring needs a separate observability stack.
- **Per-user RBAC inside ADMZ.** No user model. Anyone with network access has full power.
- **Automated credential rotation.** Manual rotation works; scheduled rotation policies are a planned capability.
- **Federation across ADMZ instances.** One ADMZ per fleet. Federation is out of scope.

## Anti-personas

- Not the Experience Center operator — different scale, different rhythm, different tolerance for unauthenticated tools.
- Not the LLM agent — though the LLM agent may operate on this persona's behalf.
- Not a casual user — this persona is the *system operator*, not an end user of the surveillance system.
