# Persona: Experience Center Operator

## Profile

**Who:** A staff member at an Axis Experience Center responsible for the demo fleet — typically a mix of cameras, intercoms, network speakers, access controllers, and audio devices that get reconfigured constantly for demos, customer visits, training sessions, and experiments.

**Technical level:** Comfortable with Axis devices and the web UI. Knows VAPIX exists but doesn't write code against it. Uses git for tracked changes but isn't a git power user.

**Scale:** 10–200 devices. Few-to-dozens of demo "configurations" they want to maintain in parallel.

**Frequency of use:** Daily. Configurations change for every customer visit; baseline gets re-established between visits.

## Goals

- **Snapshot a working setup** before changing anything, so they can return to it later.
- **Restore a device** to a previous state when a demo breaks it or the next customer needs a different setup.
- **Fork a known-good config** as the starting point for a new camera, instead of building from a factory default.
- **Diff two demo setups** to understand what's actually different between them.
- **Tag a configuration** before a customer visit ("pre-Acme-visit-2026-05-12") so it's trivially restorable.
- **See history** for blame/audit purposes — who changed bitrate on camera-conference-03 last Tuesday?
- **Roll back drift** when someone logs into a device's own web UI mid-demo and changes things.
- **Tell visitors "here's how this was configured"** with receipts (the git commit + the diff).

## Pains today (without ADMZ)

- Configurations exist only on the device — no version history, no diff, no rollback.
- Logging into 30 devices' web UIs individually to set up a multi-camera demo is hours of work.
- After a customer visit, devices are in unknown state; the only recovery is rebuilding from memory or screenshots.
- "Make camera-B match camera-A" requires reading every parameter on A, comparing manually, and applying.
- Demos that involve changing PTZ presets, view areas, privacy masks, stream profiles, *and* event rules across multiple devices are too risky to do live without a known-good restore point.

## Use cases (links to user stories)

- [Snapshot and restore](../user-stories/snapshot-and-restore.md) — the central workflow.
- [Demo workflows](../user-stories/demo-workflows.md) — tag, branch, restore patterns specific to this persona.
- [Drift and monitoring](../user-stories/drift-and-monitoring.md) — detecting mid-demo edits.
- [Device onboarding](../user-stories/device-onboarding.md) — adding new demo devices.

## What ADMZ owes this persona

- **Diff, history, restore, fork, branch, tag** — the top six priorities from `docs/EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md` §2.
- **All device types treated equally** — not camera-first. Access controllers, speakers, intercoms get the same snapshot/restore treatment.
- **Stable serialization** — two snapshots of an unchanged device produce a byte-identical commit. Otherwise diffs are useless.
- **Safe restore order** — network changes applied last (so the device doesn't disconnect mid-restore), users carefully (so they're not locked out), firmware first if it's changing.
- **Configurations in git, credentials never** — public certs in git, private keys in the credential store.
- **A web UI that doesn't require terminal skills** — but power users get the same surface via the REST API or MCP.

## What ADMZ doesn't owe this persona (out of scope for them specifically)

- **Multi-fleet federation.** If the customer has two Experience Centers, they run two ADMZ instances. (Profiles can be copied between repos manually.)
- **Real-time alerting** when a demo device drifts. Drift detection is poll-based.
- **Direct VMS / video-storage management.** ADMZ manages configuration, not video.

## How this persona uses ADMZ

Two paths, neither exclusive:

1. **Via a bundled web chatbot** (📋 planned — see
   [web-chatbot-user](web-chatbot-user.md) and
   [ADR-0024](../decisions/0024-bundled-web-chatbot.md)). This is
   expected to be the primary path for most Experience Center
   operators: open a browser, type "snapshot the lobby cameras before
   the Acme visit," see the work happen with inline approval cards
   for anything destructive.
2. **Via an existing MCP-capable agent** (Claude Code, etc.) for
   power users. Same tool surface, same safety gates, but the
   operator hosts the conversation themselves.

Until the chatbot lands, the practical path for non-developer
operators is the existing web UI's CRUD interfaces — clunkier than
the chatbot will be, but it covers the workflows.

## Anti-personas (what this persona is *not*)

- Not a developer adding catalog entries (see [catalog-contributor](catalog-contributor.md)).
- Not a security officer setting confirmation policy (see [security-conscious-operator](security-conscious-operator.md)) — though they do need the policy to allow their daily workflow.
- Not an LLM agent — though they may *direct* an LLM (via chatbot or external MCP client) that drives ADMZ for them.
