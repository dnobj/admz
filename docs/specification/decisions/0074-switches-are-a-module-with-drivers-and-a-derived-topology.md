# ADR-0074 — Switches are a module: drivers behind one contract, and a topology ADMZ derives

**Status:** Proposed (2026-11-11). Docs-only. This is the decision half of #15; a plan with PR-sized slices follows acceptance.
**Relates to:** [ADR-0039](0039-platform-and-pluggable-modules.md) (platform + modules) · [ADR-0040](0040-acs-pro-module.md) (ACS Pro, the module this one takes its shape from) · [ADR-0034](0034-uniform-widget-gating.md) (one human gate, no flat refusals) · [ADR-0037](0037-unified-tasks.md) (tasks) · [ADR-0071](0071-a-task-raises-a-notice-the-console-delivers-it.md) (notices) · [ADR-0072](0072-discovered-devices-are-added-from-the-chat-in-one-click.md) (discovered devices are added from the chat) · [ADR-0073](0073-the-mcp-server-is-a-tool-server-not-a-runtime.md) (the web service is the only runtime) · [ADR-0009](0009-oob-credential-capture.md) (credential capture) · [ADR-0029](0029-axis-api-atlas-as-maintained-reusable-asset.md) (the atlas) · review-2026-11-09 S-1 (the gate reads only the operation's risk word)

## Context

**What the lab already showed.** Three things happened on the owner's bench that ADMZ could not see:

- A PoE switch in "reserved power by class" mode reserved more than its supply and refused power to two ports, while actual draw was a sixth of the supply. One of the two devices was ADMZ's, and the most ADMZ could report was `unreachable`. The switch knew why, and said so in its own status text.
- Four Axis devices were plugged into the switch that ADMZ does not manage.
- The two devices ADMZ lists as unreachable were on none of the switch's ports. Unplugged or moved is a different problem from not answering.

**What exists.** #15 holds this year's research on the AXIS T8516. It has no VAPIX. Its real interface is a legacy text web API behind a form login, over HTTP only. It answers `200` for paths that do not exist, and its `param.cgi` is a read-only mirror. Programmatic login was the blocker.

The owner has since built a standalone command-line tool that solves the login and does the rest: per-port PoE status and configuration, the MAC table, LLDP neighbours, PoE on and off, priority and power-management mode, and saving running config to startup. Its lessons are specific:

- a PoE change posts the whole form, so it is a read-modify-write, and the switch can ignore a change without saying so;
- a change lands in running config and is lost at reboot unless saved;
- one endpoint flushes the MAC table;
- a config export carries the administrator credential in a reversible encoding.

**What the owner asked for.** Port mapping and PoE control in ADMZ, under three constraints: the switches will not always be AXIS T85, there will often be many of them, and they will be arranged in a hierarchy or a daisy chain.

**What the platform gives.** ADR-0039's module contract (executors, tools, routes, nav, prompt section, task handlers), with ACS Pro as the worked example of a module that is invisible until connected and joins to devices by MAC. ADR-0073: background work runs in the web service only. ADR-0034: every destructive action goes through the approval widget, and nothing is flatly refused.

## Decision

### 1. Switches are module #3, and not rows in the device registry

`admz/modules/switches/` has zero footprint until a switch source is added: the ADR-0039 predicate, as `acs_enabled()` does it.

A switch is infrastructure the fleet hangs from. It is often not an Axis device, and none of the device lifecycle applies to it: onboarding, baselines, drift, firmware, the `admz` account. The T8516 was registered as a device for a time, and was reported `unreachable` through more than ten thousand polls because every device feature assumed VAPIX (#138). So the module owns its own tables and its own credentials. It joins to devices by canonical MAC, the registry's key, as ACS Pro does.

### 2. A source yields switches, and a driver speaks to a source

**A source** is one way of reaching switches: an address, a credential and a driver. A T8516 is a source that yields one switch. A controller (UniFi, Omada, Meraki) is a source that yields many. This is what lets "many switches" be one configuration step at a site that has a controller.

**A driver** implements one small contract and declares which parts of it the switch supports:

| Capability | Call | What it returns or does |
|---|---|---|
| identity | `identify()` | chassis MAC, model, firmware, name |
| ports | `ports()` | a stable port key, a display name, link state, speed |
| MAC table | `mac_table()` | MAC, VLAN, port, static or learned |
| neighbours | `neighbours()` | LLDP: local port, remote chassis and port, system name and description, capabilities, management address |
| PoE status | `poe_status()` | per port: admin state, detection status in the switch's own words, class, allocated, drawn. Per switch: supply and reservation mode |
| PoE write | `set_poe(port, on)` | optional |
| PoE policy | `set_poe_priority()`, `set_poe_mode()` | optional |
| persistence | `save()`, `has_unsaved_changes()` | optional |

A capability a driver lacks is a feature that switch does not have, and the UI says so ("this switch does not report per-port draw"). It is never emulated.

**Two drivers to start:**

- `axis_t85`, a port of the owner's tool: form login with a reused session, body inspection for the soft-404, and the text formats #15 and the tool record.
- `snmp`, the standards: IF-MIB for ports, BRIDGE-MIB and Q-BRIDGE-MIB for the MAC table, LLDP-MIB for neighbours, and POWER-ETHERNET-MIB (RFC 3621) for PoE state and the admin on/off. `pysnmp` is already a dependency. This covers most managed switches for reads. Per-port measured draw is vendor-specific and is a declared gap.

Vendor and controller drivers are added when a site needs one, and nothing else in the module changes when one is.

**Protocol knowledge lives in the atlas** (ADR-0029): endpoints, field layouts, OIDs, quirks, and the catalog entries for the operations in §5. Driver code lives in ADMZ.

### 3. Topology is derived, stored without vendor terms, and dated

The module stores sources, switches (keyed by chassis MAC), ports, and two kinds of observation, each with first-seen and last-seen times:

- **sightings:** this MAC was learned on this port of this switch, on this VLAN;
- **links:** this port's LLDP neighbour is that chassis, on that port.

From them ADMZ computes, and can always recompute:

- **Which ports are links between switches.** In order of confidence: the LLDP neighbour is another managed switch; the neighbour advertises the bridge capability; or, with no LLDP at all, more MACs sit behind the port than a threshold, which marks it "probably a switch or an uplink". The tool's working threshold is four.
- **Where a device is.** A device's MAC appears on every switch along its path. Its access port is the sighting on a port that is not a link. The answer says how it is known:
  - `direct`: the port's LLDP neighbour is the device itself;
  - `sole`: it is the only MAC on the port;
  - `shared`: several MACs sit behind a port that is not a known link (an unmanaged switch, a PoE extender, a device with a pass-through port), and all of them are listed;
  - `transit`: it is seen only on links, so it sits beyond the managed part of the network.
- **Which way is up.** The tree is rooted where ADMZ itself is: the port on which ADMZ's own MAC is sighted, or its gateway's MAC when ADMZ is on another subnet. "Behind a port" means everything whose path to ADMZ passes through that port. This is what the approval card in §5 names.
- **Where a device was.** A MAC ages out of a switch within minutes of going quiet. The last sighting is kept, and it is what turns "unreachable" into "last on port 12 of the lobby switch at 10:32, and that port's link is now down".

**ADMZ does not keep an inventory of everything on the network.** Individual sightings are stored for registered devices, for MACs with an Axis vendor prefix (the list discovery already uses), for managed switches, and for ADMZ's own path. Every other MAC is counted per port, with its vendor prefix, and is not stored. An approval card can then say "and three devices ADMZ does not manage" without ADMZ holding a list of whose laptops those are.

**Not modelled in the first version**, and said in the UI where it matters: link aggregation, stacking beyond what a driver presents as one switch, per-VLAN topologies, and links that spanning tree has blocked.

### 4. Polling is a task in the web service

One module task handler (ADR-0037) polls each source on a schedule the operator can see and change. It runs in the web service and nowhere else (ADR-0073). Each source has one session, reused, and requests to a source are serialised. The T85's login travels in clear text over HTTP, so logging in on every request would send it hundreds of times a day.

### 5. Reads are free; writes go through the gate, and the gate is told the blast radius

- **A source is read-only until the operator turns writes on for it.** Until then the driver is not asked to hold a credential that can write. An SNMP read community is enough for everything in §3.
- **Operations are catalog entries in a new `switch` family.** They are driver-neutral and go through the same gate spine as device and ACS Pro operations: PoE off, on and cycle on a port; PoE priority; PoE reservation mode; save.
- **Every one of them is at least `service-affecting`.** Priority and mode decide who loses power when the budget runs out. Save persists whatever is in running config, including changes someone else made.
- **The approval card names what will lose power.** It is computed from the topology at request time: each registered device behind that port by name, and a count of everything else. If the port powers a switch or an extender, that is everything behind it. The set is recomputed at approval time. If it has changed, the approval is void and a fresh card is offered.
- **Risky ports escalate; they are not refused** (ADR-0034). A port that is a link between switches, that has a switch behind it, or that lies on ADMZ's own path is `dangerous` (`url_and_password`). The card says ADMZ may lose contact with everything behind it, including its own means of turning the port back on.
- **Unknown fails closed.** A port whose observations are older than two polling intervals is treated as a link.
- **The gate has to accept a raise-only floor from the caller.** Today `resolve_confirmation` reads the operation's risk word and nothing else, which is review-2026-11-09 S-1's finding for `param.cgi:update` (#526). One mechanism serves both: the caller supplies a floor computed from the call's target, the gate takes the stricter of that and the catalog's word, and nothing can lower it (#456's one severity scale).
- **Every write is read back**, and a write that did not take is reported as a failure. There is one writer per switch at a time, in the web service.
- **A power cycle is one operation that ADMZ owns to the end.** Before power is cut, the intent ("this port is on again by this time") is written to the task store, so a web service that restarts mid-cycle completes it. A cycle never saves.
- **ADMZ never saves implicitly.** A change stays in running config until the operator approves a save. The switch page shows unsaved changes where the driver can tell.
- **Never exposed:** flushing the MAC table, uploading or restoring a config, firmware.
- **Never stored or shown:** a config export.

### 6. Switch credentials are captured out of band and stored encrypted

A switch login or an SNMP secret is entered on a capture page (ADR-0009), never in the chat. It is stored with the same encryption as device credentials, and is never returned by a tool or written to a log. The add-switch page says plainly when a driver's login travels unencrypted, as the T85's does. It recommends a dedicated account where the switch offers one, and SNMPv3 with privacy over v2c.

### 7. What ADMZ does with it

- **Device page:** switch, port, how the location is known, link state, PoE class and draw.
- **A cause beside the verdict.** [ADR-0064](0064-a-device-admz-cannot-authenticate-to-is-never-online.md)'s reachability verdicts do not change. An unreachable device gains an explanation from the switch: link down; power refused, with the switch's own reason; not seen on any port since a given time; or seen on a different port.
- **Notices** (ADR-0071) when a registered device's port reports a PoE fault or a budget refusal.
- **Unmanaged Axis devices** become discovery candidates through the existing add flow (ADR-0072, #404). They are reported and never added automatically.
- **A budget view per switch:** supply, reserved and drawn, per port, with a warning when the reservation mode is refusing ports that actual draw would carry.
- **Chat tools.** Reads: list switches, a switch's ports, where a device is, a switch's budget. Writes: the operations in §5, gated.

## Consequences

- A new module, a new catalog family in the atlas, a handful of tables and a poller. Tools live in the module as `ToolSpec`s, so `ADMZMCPServer` does not grow (review-2026-11-09 A-1, #537).
- The gate gains a caller-supplied, raise-only floor. This is the one change outside the module, and #526 needs it independently.
- These are the first credentials ADMZ stores for something that is not an Axis device.
- A wrong topology becomes a way to cut power to the wrong thing. That is why §5 fails closed on stale data, why the card is recomputed at approval, and why the build order puts the multi-switch model before any write.
- A large switch's MAC table runs to thousands of rows. Storing only the sightings §3 names keeps the tables small and the privacy question short.

## Build order

1. **This record, then a plan** with PR-sized slices, the `FR-SW-*` requirements and the user stories.
2. **Read-only T85.** Source, driver reads, tables, the poll task, a switch page with the port map, the device-page line, the read tools. The first measurement is whether the T8516 answers SNMP. If it serves the standard MIBs, the T85 driver shrinks to what SNMP cannot do.
3. **The SNMP driver and the multi-switch model:** links, access-port resolution with its confidence, the tree. It is proven on at least one chain of two switches before step 5 begins.
4. **Explanations, notices, discovery candidates and the budget view.**
5. **Gated PoE writes:** the gate's floor, the card, read-back, the cycle with its guaranteed re-enable, and explicit save. T85 first, then SNMP where the switch allows writes.

Steps 2 to 4 change nothing on any switch.

## Alternatives considered

- **Register a switch as a device.** It would reuse the registry's credentials, tags and health. Every device feature would then have to special-case it, which is the state #138 describes, and a controller that fronts twenty switches has no device shape.
- **Port the tool as it is, T85 only.** This is the fastest, and it fails the first constraint. It would also put the T85's port numbering and field names into the store and the UI.
- **SNMP only.** It may turn out to be enough for T85 reads; step 2 measures that. It cannot be assumed for writes: many switches ship with SNMP writes off, and PoE reservation mode has no standard object.
- **Read the topology from a network management system** (LibreNMS, NetBox, Netdisco). These are mature, and one would have to be deployed at every site before ADMZ could say which port a camera is on. The source contract leaves room for one as a driver later.
- **Refuse risky ports outright.** This contradicts ADR-0034.

## Open questions for the owner

1. **Which switch types come next?** The answer picks the first driver after the two above. A controller-managed family would also exercise "one source, many switches" early.
2. **Unmanaged devices:** counts and a vendor prefix only, as §3 proposes, or the full table?
3. **PoE policy writes:** are priority and reservation mode in the first write slice, or only on, off and cycle?
4. **Sites:** a switch belongs to one Site ([ADR-0032](0032-tags-replace-groups.md)), and a link may cross Sites. Is that enough for the hierarchies you have in mind?
