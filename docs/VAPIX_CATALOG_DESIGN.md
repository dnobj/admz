# VAPIX Operation Catalog — Design

## Problem

ADMZ needs a central knowledge base of VAPIX operations so that:

1. An LLM can build execution plans ("change resolution on lobby-cam")
2. A deterministic executor can carry them out (exact HTTP calls)
3. The knowledge scales to hundreds of CGIs, thousands of parameters,
   dozens of device models, and multiple firmware lineages

The catalog must be large, accurate, versioned, and community-improvable.

## Core Design Decisions

### 1. Organize by CGI, not by category

Every VAPIX operation hits exactly one CGI endpoint. That's an unambiguous
fact — unlike categories (is "set resolution" under "image" or "streaming"?).

The filesystem hierarchy mirrors the API surface:

```
vapix-catalog/
  cgi/
    param.cgi/
    com-ptz.cgi/
    basicdeviceinfo.cgi/
    ...
  config-rest/
    ssh/v2/
    param/v1beta/
    ...
```

No judgment calls about where something belongs. The CGI path IS the address.

### 2. One file per operation — keep files small

A single file for `param.cgi` would be thousands of lines. Instead, break
it down to the smallest useful unit:

- **Per action** for CGIs with distinct actions (list, update, add, remove)
- **Per parameter group** for `param.cgi`'s massive namespace
- **Per method** for JSON-RPC CGIs (getAllProperties, getSupportedVersions)
- **Per version** when versions have different method sets

Each file is self-contained: 20-80 lines of YAML describing one thing you
can do. An LLM can read it in one shot without drowning in context.

### 3. Separate the index from the reference

Operation files are **pure technical reference** — they describe a CGI
endpoint, its request format, parameters, and response format. No tags,
no categories, no opinions. Just facts about the API.

Tags live **only in the index files**. The index is the semantic routing
layer: "if you care about resolution, look at these files." This is a
clean separation of concerns:

- **Edit a CGI doc** when the API changes (new parameter, new version)
- **Edit the index** when you want to change how operations are discovered

They never couple. A CGI doc doesn't know or care what tags point to it.

### 4. Tags are non-exclusive, many-to-many

A single CGI file can appear under multiple tags. "Set HTTPS certificate"
can be indexed under both `security` and `network`. "PTZ preset" can be
under `ptz`, `preset`, and `automation`. No hierarchy, no exclusive
membership — just flat search terms.

### 5. Index files are hand-curated (CI-validated)

The index is maintained by humans (the people who understand the use
cases), not auto-generated from the CGI files. This keeps the routing
intentional — you decide what tags make sense for discoverability.

CI validates that every file path in the index actually exists, and
optionally warns about CGI files that appear in no index entry
(orphans that nobody can discover).

### 5. Git repo as the distribution mechanism

The catalog is a standalone git repository. ADMZ clones it locally
and reads files from disk. No database, no API server, no uptime
dependency. Updates come via `git pull`. Contributions come via PRs.

---

## Repository Structure

```
vapix-catalog/
│
├── cgi/                              # One directory per CGI endpoint
│   │
│   ├── param.cgi/
│   │   ├── _cgi.yaml                 # CGI-level metadata
│   │   ├── list.yaml                 # action=list
│   │   ├── update.yaml               # action=update
│   │   ├── add.yaml                  # action=add
│   │   ├── remove.yaml               # action=remove
│   │   ├── listdefinitions.yaml      # action=listdefinitions
│   │   └── groups/                   # one file per param group
│   │       ├── root.Brand.yaml
│   │       ├── root.Image.yaml
│   │       ├── root.ImageSource.yaml
│   │       ├── root.Network.yaml
│   │       ├── root.PTZ.yaml
│   │       ├── root.StreamProfile.yaml
│   │       ├── root.AudioSource.yaml
│   │       ├── root.IOPort.yaml
│   │       ├── root.HTTPS.yaml
│   │       ├── root.System.yaml
│   │       ├── root.Time.yaml
│   │       ├── root.Properties.yaml  # read-only capability flags
│   │       └── ...                   # dozens more
│   │
│   ├── com-ptz.cgi/
│   │   ├── _cgi.yaml
│   │   ├── continuouspantiltmove.yaml
│   │   ├── absolutepantiltmove.yaml
│   │   ├── gotoserverpresetname.yaml
│   │   ├── query-position.yaml
│   │   ├── query-presets.yaml
│   │   └── query-limits.yaml
│   │
│   ├── basicdeviceinfo.cgi/
│   │   ├── _cgi.yaml
│   │   ├── getAllProperties.yaml
│   │   ├── getAllUnrestrictedProperties.yaml
│   │   └── getSupportedVersions.yaml
│   │
│   ├── apidiscovery.cgi/
│   │   ├── _cgi.yaml
│   │   ├── getApiList.yaml
│   │   └── getSupportedVersions.yaml
│   │
│   ├── pwdgrp.cgi/
│   │   ├── _cgi.yaml
│   │   ├── add-user.yaml
│   │   ├── update-user.yaml
│   │   └── remove-user.yaml
│   │
│   ├── firmwaremanagement.cgi/
│   │   ├── _cgi.yaml
│   │   ├── status.yaml
│   │   ├── upgrade.yaml
│   │   ├── commit.yaml
│   │   └── rollback.yaml
│   │
│   ├── restart.cgi/
│   │   ├── _cgi.yaml
│   │   └── execute.yaml
│   │
│   ├── factorydefault.cgi/
│   │   ├── _cgi.yaml
│   │   └── execute.yaml
│   │
│   ├── hardfactorydefault.cgi/
│   │   ├── _cgi.yaml
│   │   └── execute.yaml
│   │
│   ├── dynamicoverlay.cgi/
│   │   ├── _cgi.yaml
│   │   ├── addimage.yaml
│   │   ├── addtext.yaml
│   │   ├── setimage.yaml
│   │   ├── remove.yaml
│   │   └── list.yaml
│   │
│   ├── io-port.cgi/
│   │   ├── _cgi.yaml
│   │   ├── set-state.yaml
│   │   └── get-state.yaml
│   │
│   ├── network_settings.cgi/
│   │   ├── _cgi.yaml
│   │   ├── getNetworkInfo.yaml
│   │   └── setNetworkInfo.yaml
│   │
│   ├── time.cgi/
│   │   ├── _cgi.yaml
│   │   ├── getDateTimeInfo.yaml
│   │   └── setDateTimeInfo.yaml
│   │
│   ├── ntp.cgi/
│   │   ├── _cgi.yaml
│   │   ├── getNTPInfo.yaml
│   │   └── setNTPInfo.yaml
│   │
│   ├── systemlog.cgi/
│   │   ├── _cgi.yaml
│   │   └── read.yaml
│   │
│   ├── serverreport.cgi/
│   │   ├── _cgi.yaml
│   │   └── read.yaml
│   │
│   ├── accesslog.cgi/
│   │   ├── _cgi.yaml
│   │   └── read.yaml
│   │
│   ├── applications-control.cgi/
│   │   ├── _cgi.yaml
│   │   ├── start.yaml
│   │   ├── stop.yaml
│   │   └── restart.yaml
│   │
│   ├── applications-upload.cgi/
│   │   ├── _cgi.yaml
│   │   └── upload.yaml
│   │
│   ├── applications-list.cgi/
│   │   ├── _cgi.yaml
│   │   └── list.yaml
│   │
│   └── lightcontrol.cgi/
│       ├── _cgi.yaml
│       ├── getServiceCapabilities.yaml
│       ├── getLightInformation.yaml
│       └── setLightControl.yaml
│
├── config-rest/                      # Generation 3 REST APIs
│   ├── ssh/
│   │   └── v2/
│   │       ├── _api.yaml
│   │       ├── list-users.yaml
│   │       ├── create-user.yaml
│   │       └── delete-user.yaml
│   ├── firewall/
│   │   └── v1/
│   │       ├── _api.yaml
│   │       ├── list-rules.yaml
│   │       ├── add-rule.yaml
│   │       └── delete-rule.yaml
│   └── param/
│       └── v1beta/
│           ├── _api.yaml
│           ├── get.yaml
│           └── update.yaml
│
├── devices/                          # Device capability profiles
│   ├── p1455-le.yaml
│   ├── p5655-e.yaml
│   ├── q3505-mk2.yaml
│   ├── q6215-le.yaml
│   ├── m3057-plve.yaml
│   └── ...
│
├── firmware/                         # Firmware changelog (API additions)
│   ├── axis-os-10.12.yaml
│   ├── axis-os-11.0.yaml
│   ├── axis-os-11.11.yaml
│   └── axis-os-12.3.yaml
│
├── index/                            # Semantic routing (tags → files)
│   ├── by-task.yaml                  # "I want to do X" → CGI files
│   ├── by-feature.yaml              # "device has feature Y" → CGI files
│   └── by-risk.yaml                 # risk classification → CGI files
│
├── schema/                           # YAML validation schemas
│   ├── operation.schema.yaml
│   ├── cgi.schema.yaml
│   ├── device-profile.schema.yaml
│   ├── param-group.schema.yaml
│   └── index.schema.yaml
│
├── scripts/
│   └── validate.py                   # validate YAML + index integrity
│
└── README.md
```

---

## File Formats

### `_cgi.yaml` — CGI-level metadata

Every CGI directory has a `_cgi.yaml` that describes the endpoint itself,
separate from its individual operations. This avoids repeating the same
base URL and auth info in every operation file.

```yaml
# cgi/param.cgi/_cgi.yaml
endpoint: /axis-cgi/param.cgi
generation: legacy-cgi          # legacy-cgi | json-rpc | config-rest
auth: digest                    # digest | basic | none
min_firmware: null              # available on all firmware
description: >
  Central parameter store. Read and write all device configuration
  via key=value pairs in the root.* namespace. The oldest and most
  universal VAPIX endpoint — works on every Axis device ever made.
```

```yaml
# cgi/basicdeviceinfo.cgi/_cgi.yaml
endpoint: /axis-cgi/basicdeviceinfo.cgi
generation: json-rpc
auth: digest
min_firmware: "6.50"
api_id: basic-device-info       # as reported by apidiscovery.cgi
description: >
  Device identity information (model, serial, firmware, SoC).
  JSON-RPC interface. The getAllUnrestrictedProperties method
  works without authentication on factory-default devices.
```

```yaml
# config-rest/ssh/v2/_api.yaml
base_path: /config/rest/ssh/v2
generation: config-rest
auth: digest
min_firmware: "12.3"
api_id: ssh
description: SSH user and access management via REST API.
```

### Operation file — legacy CGI action

```yaml
# cgi/param.cgi/update.yaml
id: param.cgi:update
cgi: param.cgi                    # references _cgi.yaml in same dir

method: GET
request:
  query:
    action: update
    # Additional params: key=value pairs for parameters to set
    # e.g. root.Image.I0.Resolution=1920x1080
  content_type: null              # GET request, no body

response:
  success: "OK"                   # body starts with "OK" on success
  error_prefix: "# Error:"       # error lines start with this

rollback:
  strategy: revert-params         # re-set to previous values
  description: >
    Read current values before update, store them, re-apply
    on rollback via another update call.

requires:
  auth_level: admin               # admin | operator | viewer
```

Note: **no tags in the operation file**. Tags live only in the index.

### Operation file — JSON-RPC method

```yaml
# cgi/basicdeviceinfo.cgi/getAllProperties.yaml
id: basicdeviceinfo.cgi:getAllProperties
cgi: basicdeviceinfo.cgi

method: POST
min_api_version: "1.0"

request:
  content_type: application/json
  body:
    apiVersion: "1.0"
    method: getAllProperties

response:
  format: json
  data_path: data.propertyList    # where the useful data lives
  fields:
    - Architecture                # SoC architecture (e.g. "armv7hf")
    - Brand                       # always "AXIS"
    - ProdFullName                # e.g. "AXIS P5655-E PTZ Dome..."
    - ProdNbr                     # e.g. "P5655-E"
    - ProdType                    # e.g. "Network Camera"
    - SerialNumber                # device serial
    - Version                     # firmware version
    - Soc                         # e.g. "Axis Artpec-7"

requires:
  auth_level: viewer
  # getAllUnrestrictedProperties works with auth_level: none
```

Again — no tags here. Pure technical reference.

### Operation file — config-rest endpoint

```yaml
# config-rest/ssh/v2/create-user.yaml
id: config-rest:ssh:v2:create-user
api: ssh/v2                       # references _api.yaml

method: POST
path: /users                      # appended to base_path

request:
  content_type: application/json
  body:
    username: "{username}"
    sshKey: "{public_key}"

response:
  format: json
  success_status: 201

rollback:
  strategy: delete
  method: DELETE
  path: "/users/{username}"

requires:
  auth_level: admin
  min_firmware: "12.3"
```

### Parameter group file

These are the big ones — each documents a `param.cgi` parameter namespace.
Separated into their own files because `param.cgi` has dozens of groups.

```yaml
# cgi/param.cgi/groups/root.Image.yaml
group: root.Image
cgi: param.cgi
read_action: list                 # param.cgi?action=list&group=Image
write_action: update              # param.cgi?action=update

description: >
  Per-view image settings. Uses channel indexing: root.Image.I0,
  root.Image.I1, etc. Channel 0 is the default view.

channel_indexed: true             # root.Image.I{n}.Parameter
channel_key: "I"                  # the index prefix

parameters:
  Resolution:
    type: enum
    description: Image resolution for this view channel.
    valid_values_from: Properties.Image.Resolution
    example_values: ["1920x1080", "1280x720", "640x480"]
    auth_level: admin

  Compression:
    type: integer
    description: JPEG compression level (0=lowest, 100=highest).
    range: [0, 100]
    default: 30
    auth_level: operator

  Rotation:
    type: enum
    description: Image rotation angle.
    valid_values: ["0", "90", "180", "270"]
    auth_level: admin

  Enabled:
    type: boolean
    description: Whether this view channel is active.
    valid_values: ["yes", "no"]
    auth_level: admin

  Name:
    type: string
    description: Human-readable name for this view channel.
    auth_level: admin

  Mirror:
    type: enum
    description: Enable horizontal mirror of image.
    valid_values: ["yes", "no"]
    auth_level: admin

requires:
  properties:
    - Properties.Image.Resolution
```

No tags. The index files handle discoverability.

### Device profile

```yaml
# devices/p5655-e.yaml
model: P5655-E
full_name: AXIS P5655-E PTZ Dome Network Camera
product_type: ptz-dome-camera
soc: Artpec-7

capabilities:
  ptz: true
  digital_ptz: true
  audio_input: true
  audio_output: false
  io_ports: 4
  sd_card: true
  ir_led: true
  max_resolution: "1920x1080"

# Firmware version → which APIs are available
# Used to resolve operations when firmware is known
firmware_support:
  "10.12":
    cgis:
      - param.cgi
      - com-ptz.cgi
      - basicdeviceinfo.cgi
      - apidiscovery.cgi
      - pwdgrp.cgi
      - restart.cgi
      - factorydefault.cgi
      - systemlog.cgi
      - dynamicoverlay.cgi
      - applications-control.cgi
      - lightcontrol.cgi
    config_rest: []
  "11.0":
    cgis:
      - param.cgi
      - com-ptz.cgi
      - basicdeviceinfo.cgi
      - apidiscovery.cgi
      - pwdgrp.cgi
      - restart.cgi
      - factorydefault.cgi
      - systemlog.cgi
      - dynamicoverlay.cgi
      - applications-control.cgi
      - lightcontrol.cgi
      - network_settings.cgi
      - ntp.cgi
      - time.cgi
      - firmwaremanagement.cgi
    config_rest: []
  "12.3":
    cgis:
      - param.cgi
      - com-ptz.cgi
      - basicdeviceinfo.cgi
      - apidiscovery.cgi
      - pwdgrp.cgi
      - restart.cgi
      - factorydefault.cgi
      - systemlog.cgi
      - dynamicoverlay.cgi
      - applications-control.cgi
      - lightcontrol.cgi
      - network_settings.cgi
      - ntp.cgi
      - time.cgi
      - firmwaremanagement.cgi
    config_rest:
      - ssh/v2
      - firewall/v1
      - param/v1beta

```

Device profiles also carry no tags — they're pure facts about hardware.

---

## Index Files — The Routing Layer

Index files are the **only place tags exist**. They live in `index/` and
map search terms to CGI file paths. The CGI files themselves know nothing
about tags — they're pure technical reference.

This separation means:
- **Edit a CGI doc** when the API changes (new parameter, new version)
- **Edit an index** when you want to change how operations are discovered
- They never couple. A CGI doc doesn't know or care what tags point to it.

Index files are **hand-curated** — maintained by people who understand the
use cases. CI validates that every path referenced actually exists, and
warns about CGI files not referenced by any index entry (orphans).

### Why multiple index files?

A single monolithic index would work, but splitting by concern keeps
each file focused and easier to maintain:

| Index file | Purpose | Who cares |
|---|---|---|
| `by-task.yaml` | "I want to do X" | LLM building a plan |
| `by-feature.yaml` | "Does this device support Y?" | Resolver filtering |
| `by-risk.yaml` | Risk/safety classification | Executor guardrails |

### `index/by-task.yaml` — Task-oriented routing

"The user wants to accomplish X — which CGI files are relevant?"

```yaml
# index/by-task.yaml
#
# Maps task-oriented search terms to the CGI files that can
# accomplish them. This is the primary index the LLM uses
# when building execution plans.
#
# Tags are non-exclusive: a CGI file can appear under many tags.
# Tags are flat: no hierarchy, no parent-child relationships.

change-resolution:
  - cgi/param.cgi/groups/root.Image.yaml
  - cgi/param.cgi/groups/root.StreamProfile.yaml

configure-ptz:
  - cgi/com-ptz.cgi/continuouspantiltmove.yaml
  - cgi/com-ptz.cgi/absolutepantiltmove.yaml
  - cgi/com-ptz.cgi/gotoserverpresetname.yaml
  - cgi/com-ptz.cgi/query-position.yaml
  - cgi/com-ptz.cgi/query-presets.yaml
  - cgi/com-ptz.cgi/query-limits.yaml
  - cgi/param.cgi/groups/root.PTZ.yaml

manage-users:
  - cgi/pwdgrp.cgi/add-user.yaml
  - cgi/pwdgrp.cgi/update-user.yaml
  - cgi/pwdgrp.cgi/remove-user.yaml
  - config-rest/ssh/v2/list-users.yaml
  - config-rest/ssh/v2/create-user.yaml
  - config-rest/ssh/v2/delete-user.yaml

configure-network:
  - cgi/param.cgi/groups/root.Network.yaml
  - cgi/network_settings.cgi/getNetworkInfo.yaml
  - cgi/network_settings.cgi/setNetworkInfo.yaml

configure-time:
  - cgi/time.cgi/getDateTimeInfo.yaml
  - cgi/time.cgi/setDateTimeInfo.yaml
  - cgi/ntp.cgi/getNTPInfo.yaml
  - cgi/ntp.cgi/setNTPInfo.yaml
  - cgi/param.cgi/groups/root.Time.yaml

manage-overlays:
  - cgi/dynamicoverlay.cgi/addimage.yaml
  - cgi/dynamicoverlay.cgi/addtext.yaml
  - cgi/dynamicoverlay.cgi/setimage.yaml
  - cgi/dynamicoverlay.cgi/remove.yaml
  - cgi/dynamicoverlay.cgi/list.yaml

manage-applications:
  - cgi/applications-control.cgi/start.yaml
  - cgi/applications-control.cgi/stop.yaml
  - cgi/applications-control.cgi/restart.yaml
  - cgi/applications-upload.cgi/upload.yaml
  - cgi/applications-list.cgi/list.yaml

configure-io:
  - cgi/io-port.cgi/set-state.yaml
  - cgi/io-port.cgi/get-state.yaml
  - cgi/param.cgi/groups/root.IOPort.yaml

configure-image:
  - cgi/param.cgi/groups/root.Image.yaml
  - cgi/param.cgi/groups/root.ImageSource.yaml

configure-streaming:
  - cgi/param.cgi/groups/root.StreamProfile.yaml
  - cgi/param.cgi/groups/root.Image.yaml

configure-audio:
  - cgi/param.cgi/groups/root.AudioSource.yaml

configure-ir:
  - cgi/lightcontrol.cgi/getLightInformation.yaml
  - cgi/lightcontrol.cgi/setLightControl.yaml

configure-security:
  - cgi/pwdgrp.cgi/add-user.yaml
  - cgi/pwdgrp.cgi/update-user.yaml
  - cgi/pwdgrp.cgi/remove-user.yaml
  - cgi/param.cgi/groups/root.HTTPS.yaml
  - config-rest/ssh/v2/list-users.yaml
  - config-rest/ssh/v2/create-user.yaml
  - config-rest/ssh/v2/delete-user.yaml
  - config-rest/firewall/v1/list-rules.yaml
  - config-rest/firewall/v1/add-rule.yaml
  - config-rest/firewall/v1/delete-rule.yaml

upgrade-firmware:
  - cgi/firmwaremanagement.cgi/status.yaml
  - cgi/firmwaremanagement.cgi/upgrade.yaml
  - cgi/firmwaremanagement.cgi/commit.yaml
  - cgi/firmwaremanagement.cgi/rollback.yaml

restart-device:
  - cgi/restart.cgi/execute.yaml

factory-reset:
  - cgi/factorydefault.cgi/execute.yaml
  - cgi/hardfactorydefault.cgi/execute.yaml

get-diagnostics:
  - cgi/systemlog.cgi/read.yaml
  - cgi/serverreport.cgi/read.yaml
  - cgi/accesslog.cgi/read.yaml

identify-device:
  - cgi/basicdeviceinfo.cgi/getAllProperties.yaml
  - cgi/basicdeviceinfo.cgi/getAllUnrestrictedProperties.yaml

discover-capabilities:
  - cgi/apidiscovery.cgi/getApiList.yaml
  - cgi/param.cgi/groups/root.Properties.yaml
  - cgi/param.cgi/groups/root.Brand.yaml
```

### `index/by-feature.yaml` — Capability-based routing

"This device has feature Y — which CGIs relate to that feature?"

Used by the resolver to pre-filter operations based on device capabilities
(from `Properties.*` or `apidiscovery.cgi`).

```yaml
# index/by-feature.yaml
#
# Maps device capabilities/features to the CGI files that
# require or relate to that capability. Used during device
# resolution: "this camera has PTZ, so these files apply."

Properties.PTZ.PTZ:
  - cgi/com-ptz.cgi/continuouspantiltmove.yaml
  - cgi/com-ptz.cgi/absolutepantiltmove.yaml
  - cgi/com-ptz.cgi/gotoserverpresetname.yaml
  - cgi/com-ptz.cgi/query-position.yaml
  - cgi/com-ptz.cgi/query-presets.yaml
  - cgi/com-ptz.cgi/query-limits.yaml
  - cgi/param.cgi/groups/root.PTZ.yaml

Properties.Audio.Audio:
  - cgi/param.cgi/groups/root.AudioSource.yaml

Properties.IO.NbrOfInputs:
  - cgi/io-port.cgi/set-state.yaml
  - cgi/io-port.cgi/get-state.yaml
  - cgi/param.cgi/groups/root.IOPort.yaml

Properties.LightControl.LightControl2:
  - cgi/lightcontrol.cgi/getLightInformation.yaml
  - cgi/lightcontrol.cgi/setLightControl.yaml
  - cgi/lightcontrol.cgi/getServiceCapabilities.yaml

Properties.Image.Resolution:
  - cgi/param.cgi/groups/root.Image.yaml
  - cgi/param.cgi/groups/root.StreamProfile.yaml
```

### `index/by-risk.yaml` — Risk classification

Used by the executor to enforce safety policies. Operations tagged
`dangerous` require extra confirmation. Operations tagged `read-only`
are always safe.

```yaml
# index/by-risk.yaml
#
# Risk classification for executor guardrails.

read-only:
  - cgi/basicdeviceinfo.cgi/getAllProperties.yaml
  - cgi/basicdeviceinfo.cgi/getAllUnrestrictedProperties.yaml
  - cgi/apidiscovery.cgi/getApiList.yaml
  - cgi/systemlog.cgi/read.yaml
  - cgi/serverreport.cgi/read.yaml
  - cgi/accesslog.cgi/read.yaml
  - cgi/param.cgi/groups/root.Properties.yaml
  - cgi/param.cgi/groups/root.Brand.yaml
  - cgi/param.cgi/list.yaml
  - cgi/com-ptz.cgi/query-position.yaml
  - cgi/com-ptz.cgi/query-presets.yaml
  - cgi/com-ptz.cgi/query-limits.yaml
  - cgi/lightcontrol.cgi/getLightInformation.yaml
  - cgi/lightcontrol.cgi/getServiceCapabilities.yaml
  - cgi/applications-list.cgi/list.yaml
  - cgi/dynamicoverlay.cgi/list.yaml

dangerous:
  - cgi/factorydefault.cgi/execute.yaml
  - cgi/hardfactorydefault.cgi/execute.yaml
  - cgi/firmwaremanagement.cgi/upgrade.yaml
  - cgi/firmwaremanagement.cgi/rollback.yaml
  - cgi/pwdgrp.cgi/remove-user.yaml
  - config-rest/ssh/v2/delete-user.yaml
  - config-rest/firewall/v1/delete-rule.yaml

service-affecting:
  - cgi/restart.cgi/execute.yaml
  - cgi/param.cgi/groups/root.Network.yaml
  - cgi/network_settings.cgi/setNetworkInfo.yaml
```

---

## How ADMZ Consumes the Catalog

### Integration point

```
admz/
├── admz/
│   ├── vapix/
│   │   ├── __init__.py
│   │   ├── catalog.py           # reads YAML from local clone
│   │   ├── resolver.py          # filters ops for a specific device
│   │   └── index.py             # tag index loader and search
│   └── ...
└── .vapix-catalog/              # git clone (or submodule)
    └── (the repo structure above)
```

### Resolution flow

When the LLM (or any client) needs to know what operations are available
for a specific device and task:

```
1. User/LLM query: "change resolution on lobby-cam"

2. Resolver maps intent to index keys: ["change-resolution"]

3. Task index lookup — reads index/by-task.yaml:
   change-resolution →
     - cgi/param.cgi/groups/root.Image.yaml
     - cgi/param.cgi/groups/root.StreamProfile.yaml

4. Device filter — reads lobby-cam's model + firmware from registry:
   Model: P1455-LE, Firmware: 11.6
   Device profile says: supports param.cgi? Yes.
   → supports config-rest/param? No (needs 12.3+).
   → Filter out any config-rest/ files.

5. Risk check — reads index/by-risk.yaml:
   root.Image.yaml is not in "dangerous" or "service-affecting"
   → No extra confirmation needed.

6. Load only the matching files:
   - cgi/param.cgi/_cgi.yaml                (endpoint metadata)
   - cgi/param.cgi/update.yaml              (how to write params)
   - cgi/param.cgi/groups/root.Image.yaml   (resolution params)

7. Return to LLM: ~60 lines of YAML describing exactly how to
   change resolution on this specific camera.
```

The LLM context window only ever sees the small filtered subset —
not the hundreds of operation files in the full catalog.

### MCP tool interface

```
get_available_operations(
    device_id="lobby-cam",        # device in registry
    task="change-resolution"      # maps to index/by-task.yaml key
) → list of matching operation YAML content (already filtered for device)
```

---

## Central Repo → Local Sync

### Initial setup

```bash
# Clone the catalog into the ADMZ data directory
git clone https://github.com/org/vapix-catalog.git ~/.admz/vapix-catalog
```

Or configure via ADMZ:

```yaml
# ~/.admz/config.yaml
vapix_catalog:
  repo: https://github.com/org/vapix-catalog.git
  local_path: ~/.admz/vapix-catalog
  auto_update: true              # git pull on startup
  branch: main
```

### Update flow

```
admz startup
  → check if ~/.admz/vapix-catalog exists
    → no:  git clone
    → yes: git pull (if auto_update=true)
  → load index/by-task.yaml into memory (primary lookup)
  → load index/by-risk.yaml into memory (safety checks)
  → load index/by-feature.yaml into memory (device filtering)
  → ready to resolve operations
```

### Offline operation

The catalog is fully local after the initial clone. No network dependency
at runtime. Works in air-gapped environments — just copy the repo manually.

---

## Catalog Maintenance

### Who maintains it

The catalog is maintained by a small group of contributors who:
- Understand the VAPIX API surface (have access to real devices)
- Understand the YAML schema and file conventions
- Are comfortable with git workflows (branches, PRs, reviews)
- Have write access to the catalog repo

This is intentionally **not** automated from field clients. Automated
edge-discovery-to-PR pipelines add significant complexity (auth token
management on every client, merge conflict resolution, validation of
auto-generated YAML, noisy PRs from edge-case devices) for questionable
value. The catalog is a curated knowledge base, not a telemetry sink.

### How contributions happen

A contributor with access to a device (e.g., a new model or firmware):

```
1. Manually query the device to understand its API surface:
   - GET  /axis-cgi/basicdeviceinfo.cgi → model, firmware, soc
   - POST /axis-cgi/apidiscovery.cgi    → supported API list
   - GET  /axis-cgi/param.cgi?action=list&group=Properties → capabilities
   - GET  /axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema

2. Write or update YAML files in a feature branch:
   - New device profile in devices/
   - New or updated operation files in cgi/
   - Updated index entries in index/

3. Open a PR. CI validates:
   - YAML schema conformance
   - Index file paths point to real files
   - No duplicate operation IDs

4. Another contributor reviews and merges.
```

### Clients are read-only consumers

ADMZ client installations only ever **read** the catalog. They `git clone`
on first run and `git pull` on startup. They never write to the repo,
never open PRs, never need repo credentials beyond read access.

This keeps the client simple and the catalog clean.

---

## Device Interrogation — Runtime Capability Discovery

The catalog tells you "what operations exist in VAPIX." But for a specific
device on the network, you need to ask IT what it actually supports. This
is **device interrogation** — a built-in MCP operation that probes a real
device and caches the results locally.

This is distinct from the catalog:

| | Central catalog | Device interrogation |
|---|---|---|
| Answers | "What VAPIX operations exist?" | "What does THIS device support?" |
| Source | Hand-curated YAML files | Live queries to the device |
| Storage | Git repo (read-only clone) | Local device registry (SQLite/Vault) |
| When | Pulled on startup | Run on-demand per device |

### Why bake it into the MCP

Device interrogation is always the same sequence of VAPIX calls. It doesn't
need LLM judgment — it's deterministic. Making it a native MCP tool means:

- The LLM can trigger it with a single call, no plan needed
- Results are structured and stored consistently
- It runs fast (direct HTTP calls, no LLM round-trips)
- It's the foundation for everything else — you need to know what a device
  supports before the resolver can filter catalog operations for it

### Interrogation depths

Not every situation needs a full probe. A tiered approach lets you get
just what you need:

```
interrogate_device(
    device_id="lobby-cam",        # must exist in registry with IP + creds
    depth="standard"              # "basic" | "standard" | "full"
)
```

#### `basic` — Identity only (~1 second, 1-2 HTTP calls)

Answers: "What is this device?"

```
Calls:
  1. POST /axis-cgi/basicdeviceinfo.cgi
     → method: getAllProperties

Stores:
  - model (ProdNbr)
  - full_name (ProdFullName)
  - product_type (ProdType)
  - serial_number (SerialNumber)
  - firmware_version (Version)
  - soc (Soc)
  - architecture (Architecture)
```

Useful for: initial device registration, quick verification after
network discovery, confirming a device is reachable and responsive.

#### `standard` — Identity + API surface (~3-5 seconds, 3-4 HTTP calls)

Answers: "What is this device and what can it do?"

```
Calls:
  1. POST /axis-cgi/basicdeviceinfo.cgi
     → method: getAllProperties

  2. POST /axis-cgi/apidiscovery.cgi
     → method: getApiList
     → returns: list of supported API IDs + versions

  3. GET /axis-cgi/param.cgi?action=list&group=Properties
     → returns: all Properties.* capability flags
     → e.g. Properties.PTZ.PTZ=yes, Properties.Audio.Audio=yes

  4. GET /axis-cgi/param.cgi?action=list&group=Brand
     → returns: brand identity (redundant but cross-validates)

Stores (in addition to basic):
  - supported_apis: [{id, version, name, status}, ...]
  - capabilities: {ptz: true, audio: true, io_ports: 4, ...}
  - properties_raw: {Properties.PTZ.PTZ: "yes", ...}
  - interrogation_depth: "standard"
  - interrogation_timestamp: "2026-02-12T..."
```

This is the default. Gives the resolver everything it needs to
filter catalog operations for this device. Enough for most tasks.

#### `full` — Complete parameter introspection (~10-30 seconds, many HTTP calls)

Answers: "What is every configurable parameter on this device?"

```
Calls (in addition to standard):
  5. GET /axis-cgi/param.cgi?action=listdefinitions
        &listformat=xmlschema&group=Image
     → returns: every Image.* parameter with type, valid values, ranges

  6. GET /axis-cgi/param.cgi?action=listdefinitions
        &listformat=xmlschema&group=StreamProfile
     → returns: every StreamProfile.* parameter

  7. GET /axis-cgi/param.cgi?action=listdefinitions
        &listformat=xmlschema&group=Network
     → (repeat for each major param group)

  8. For each JSON-RPC API discovered in step 2:
     POST /axis-cgi/{api}.cgi → method: getSupportedVersions
     → returns: exact version range supported

Stores (in addition to standard):
  - param_definitions: {group: {param: {type, values, range}, ...}, ...}
  - api_versions: {api_id: [versions], ...}
  - interrogation_depth: "full"
```

This is expensive but gives complete device knowledge. Useful when
a catalog contributor is documenting a new device, or when the LLM
needs to know exact valid values for a parameter.

### What gets stored and where

Interrogation results go into the **existing device registry** — the
same SQLite or Vault backend that already stores device metadata. They
are stored as part of the device's metadata, not in the catalog repo.

```python
# Conceptual — stored in registry metadata for the device
{
    "device_id": "lobby-cam",
    "ip": "192.168.1.100",
    "model": "P5655-E",

    # From interrogation:
    "interrogation": {
        "depth": "standard",
        "timestamp": "2026-02-12T14:30:00Z",
        "firmware_version": "11.8.2",
        "soc": "Artpec-7",
        "supported_apis": [
            {"id": "basic-device-info", "version": "1.2"},
            {"id": "api-discovery", "version": "1.0"},
            {"id": "io-port-management", "version": "1.0"},
            {"id": "stream-profiles", "version": "1.0"},
            ...
        ],
        "capabilities": {
            "ptz": true,
            "audio": true,
            "io_ports": 4,
            "sd_card": true,
            "ir_led": true,
            "max_resolution": "1920x1080"
        }
    }
}
```

### How interrogation connects to the catalog resolver

```
1. LLM: "change resolution on lobby-cam"

2. Resolver checks: does lobby-cam have interrogation data?
   → Yes, standard depth, from 2 hours ago.

3. From interrogation data:
   - firmware: 11.8.2 → supports param.cgi, not config-rest
   - Properties.Image.Resolution exists → image operations apply

4. From catalog index (by-task.yaml):
   - "change-resolution" → root.Image.yaml, root.StreamProfile.yaml

5. Both files reference param.cgi, device supports param.cgi → match.

6. Load and return those files to the LLM.
```

If the device hasn't been interrogated yet:

```
1. LLM: "change resolution on lobby-cam"

2. Resolver checks: no interrogation data for lobby-cam.

3. Returns: "Device lobby-cam has not been interrogated.
   Run interrogate_device first to discover its capabilities."

   (Or: resolver auto-triggers a basic interrogation if the
   device has credentials in the registry.)
```

### MCP tool definition

```python
Tool(
    name="interrogate_device",
    description=(
        "Probe a device over VAPIX to discover its model, firmware, "
        "supported APIs, and capabilities. Results are cached in the "
        "device registry and used by the catalog resolver to determine "
        "which operations are available for this device. "
        "Depth: 'basic' (identity only, fast), 'standard' (identity + "
        "API surface + capabilities, default), 'full' (complete parameter "
        "introspection, slow but exhaustive)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Device ID or nickname from the registry"
            },
            "depth": {
                "type": "string",
                "enum": ["basic", "standard", "full"],
                "default": "standard",
                "description": "How deeply to probe the device"
            }
        },
        "required": ["device_id"]
    }
)
```

### When to interrogate (event-driven, not polled)

A device's capability set doesn't change during normal operation. An
AXIS P5655 running firmware 11.8 supports the same APIs today as it
will next week. Interrogation is therefore **event-driven**, not
time-based. There's no polling loop or periodic re-probe.

**Triggers:**

| Event | Action | Depth |
|---|---|---|
| Device first added to registry | Auto-interrogate | standard |
| Firmware upgrade detected | Re-interrogate | standard |
| Factory reset detected | Re-interrogate | standard |
| User/LLM explicitly requests | On-demand | any (user picks) |

**How firmware upgrades are detected:** The `basic` depth is cheap
(one HTTP call, ~1 second). A lightweight version check can be done
opportunistically — e.g., before executing an operation, the executor
makes a quick basicdeviceinfo call and compares the returned firmware
version against the cached one. If it differs, flag the interrogation
data as stale and suggest re-interrogation before proceeding. This is
NOT periodic polling — it's a cheap side-check on an operation that
was already going to talk to the device anyway.

**The timestamp is a safety net, not a scheduler.** The stored
`interrogation_timestamp` exists so the resolver can warn about very
old data ("interrogation data is 6 months old — firmware may have
changed"), not to trigger automatic re-probes. The warning threshold
is configurable (default: 30 days) and just surfaces an advisory, it
doesn't block operations.

```yaml
# ~/.admz/config.yaml
interrogation:
  auto_on_register: true           # interrogate when device is added
  stale_warning_days: 30           # warn if data older than this
  auto_version_check: true         # compare firmware version before ops
```

**Auto-interrogation on device registration:**

```
register_device("lobby-cam", ip="192.168.1.100", ...)
  → device saved to registry
  → if auto_on_register and credentials available:
      → run interrogate_device("lobby-cam", depth="standard")
      → cache results immediately
  → device ready for catalog-resolved operations
```

This means a newly registered device with credentials is immediately
usable — no separate "now run interrogation" step needed.

---

## Plan Approval and Execution Safety

Two separate gates protect the user from unwanted device changes.
They live at different layers and serve different purposes:

```
┌─────────────────────────────────────────────────────────┐
│  User / Chat UI                                         │
│                                                         │
│  "Change the resolution to 4K on lobby-cam"             │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  LLM                                              │  │
│  │                                                   │  │
│  │  Resolves catalog → builds plan → presents it:    │  │
│  │  "I'll set Image.I0.Resolution=3840x2160 via      │  │
│  │   param.cgi on lobby-cam. Proceed?"               │  │
│  │                                                   │  │
│  │  ┌─ GATE 1: Plan Approval (semantic) ──────────┐  │  │
│  │  │  User sees the plan in natural language.     │  │  │
│  │  │  Can approve, decline, or decline with       │  │  │
│  │  │  feedback ("no, that camera is 1080p max,    │  │  │
│  │  │  try 1080p instead").                        │  │  │
│  │  │  This is conversational — the LLM adjusts.   │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │                                                   │  │
│  │  User approves → LLM calls MCP tool               │  │
│  │                                                   │  │
│  │  ┌───────────────────────────────────────────┐    │  │
│  │  │  MCP Server                               │    │  │
│  │  │                                           │    │  │
│  │  │  ┌─ GATE 2: Risk Check (mechanical) ──┐   │    │  │
│  │  │  │  Catalog says this op is:           │   │    │  │
│  │  │  │  - read-only → execute immediately  │   │    │  │
│  │  │  │  - normal → execute (Gate 1 enough) │   │    │  │
│  │  │  │  - service-affecting → warn + exec  │   │    │  │
│  │  │  │  - dangerous → BLOCK, return error  │   │    │  │
│  │  │  │    with explanation back to LLM     │   │    │  │
│  │  │  └─────────────────────────────────────┘   │    │  │
│  │  │                                           │    │  │
│  │  │  Execute → return result                  │    │  │
│  │  └───────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Gate 1: Plan Approval (LLM/client layer)

**Purpose:** "Is this the right plan?"

This is a semantic question only the user can answer. The LLM
proposes a plan in natural language, the user reads it and decides.

```
LLM: "I'll change the resolution on lobby-cam to 4K by setting
      Image.I0.Resolution=3840x2160 via param.cgi. This will
      interrupt the current video stream briefly. Proceed?"

User options:
  → "Yes"
  → "No" (LLM asks what to do instead)
  → "No — that camera maxes out at 1080p, use that instead"
       (LLM adjusts and re-proposes)
  → "Yes, and also bump the compression to 30"
       (LLM incorporates and re-proposes or just does both)
```

This is standard LLM tool-use behavior. In Claude Code, the
permission mode controls whether the LLM asks before each tool
call or auto-executes. The plan presentation is just the LLM
being a good assistant — describing what it's about to do.

**This gate does NOT live in the MCP server.** The MCP server
has no concept of "the user wants 1080p not 4K" — that's a
conversational concern. The MCP server just executes operations.

### Gate 2: Risk Check (MCP server layer)

**Purpose:** "Is this operation safe to execute?"

This is a mechanical check based on the catalog's risk
classification (by-risk.yaml). It catches cases where:

- The LLM misunderstands the severity of an operation
- The user approves a plan without realizing step 3 of 5 is
  a factory reset
- A client other than Claude Code calls the MCP with no
  permission model at all

```
Risk level     │ MCP behavior
───────────────┼──────────────────────────────────────────
read-only      │ Execute immediately, no check
normal         │ Execute (Gate 1 was sufficient)
service-       │ Execute, but include a warning in the
affecting      │ response: "Note: this interrupted the
               │ video stream for ~2 seconds"
dangerous      │ BLOCK execution. Return an error to the
               │ LLM: "This operation (factory reset) is
               │ classified as dangerous. The user must
               │ explicitly confirm via confirm_dangerous_
               │ operation() before it will execute."
```

The `dangerous` category is intentionally small — only factory
resets, firmware operations, user deletion, firewall changes.
Everything else flows through without MCP-side blocking.

### Why both gates matter

The gates serve different trust boundaries:

**Gate 1 alone is not enough** because:
- The LLM might present a dangerous operation casually ("I'll
  just reset the network settings...") and the user might say
  "sure" without understanding the implication
- Not all MCP clients have Claude Code's permission model —
  a script or a different LLM client might call the MCP
  directly with no human in the loop
- Defense in depth: the catalog KNOWS which operations are
  destructive — that knowledge should be enforced, not just
  informational

**Gate 2 alone is not enough** because:
- The MCP has no concept of user intent — it can't tell the
  user "you said 4K but this camera maxes at 1080p"
- Most operations are not dangerous, and an MCP-side gate on
  every operation would be redundant and annoying
- The user needs to see the plan in context, not as a raw
  tool call — "I'll set these 3 parameters" is more useful
  than "confirm: param.cgi action=update&group=root.Image..."

### The `confirm_dangerous_operation` flow

When Gate 2 blocks a dangerous operation, the flow is:

```
1. LLM calls: execute_operation(device="lobby-cam",
              operation="factory-reset", ...)

2. MCP returns error:
   {
     "blocked": true,
     "risk_level": "dangerous",
     "reason": "Factory reset will erase all configuration
                including accounts, network settings, and
                installed applications.",
     "confirm_token": "abc123",
     "confirm_tool": "confirm_dangerous_operation"
   }

3. LLM presents this to the user:
   "The MCP server blocked this because factory reset is
    classified as dangerous. It will erase all configuration.
    Do you want me to confirm and proceed?"

4. User: "Yes, I understand, go ahead"

5. LLM calls: confirm_dangerous_operation(
              confirm_token="abc123")

6. MCP executes the operation.
```

The confirm token is single-use and short-lived (5 minutes).
This prevents replay and ensures the confirmation is fresh.

### Configurable MCP safety mode

Different deployments need different safety levels:

```yaml
# ~/.admz/config.yaml
safety:
  mode: "standard"          # "permissive" | "standard" | "strict"
```

| Mode | read-only | normal | service-affecting | dangerous |
|---|---|---|---|---|
| `permissive` | execute | execute | execute | warn + execute |
| `standard` | execute | execute | warn + execute | block |
| `strict` | execute | warn + execute | block | block |

- **permissive**: Lab/test environment. Trust the LLM + user.
  Still warns on dangerous ops but doesn't block.
- **standard**: Default. Blocks only the truly dangerous stuff.
  Good for managed deployments where the user knows what
  they're doing but mistakes are costly.
- **strict**: Production/critical infrastructure. Even
  service-affecting operations (restart, network changes)
  require explicit confirmation via the MCP. For environments
  where an accidental stream interruption is unacceptable.

### Summary: where each concern lives

```
Concern                          │ Where it's handled
─────────────────────────────────┼───────────────────────
"Is this the right operation?"   │ LLM (Gate 1)
"Did I pick the right device?"   │ LLM (Gate 1)
"Are the parameter values right?"│ LLM (Gate 1)
User wants to modify the plan    │ LLM (conversational)
User wants to decline the plan   │ LLM (conversational)
"Is this operation destructive?" │ MCP (Gate 2, catalog)
"Block factory resets"           │ MCP (Gate 2, config)
"Warn on service interruptions"  │ MCP (Gate 2, config)
"Is this client authorized?"     │ MCP (auth, future)
```

---

## MCP Execution Model — How the Catalog Is Actually Used

This is the most important design decision: where does the
intelligence live for translating "change the resolution" into
an actual HTTP call to the device?

### The three options

#### Option A: Typed MCP tools (one tool per operation)

```
MCP tools:
  - set_resolution(device_id, width, height)
  - get_resolution(device_id)
  - set_compression(device_id, level)
  - create_ssh_user(device_id, username, public_key)
  - factory_reset(device_id)
  - ... hundreds more
```

The MCP server contains all the translation logic. The LLM just
picks the right tool and fills in the arguments.

**Pros:**
- Type-safe — parameters are validated before execution
- Easy for the LLM — just pick a tool from the list
- Each tool is testable in isolation

**Cons:**
- **Hundreds of tools.** VAPIX has ~120 operations, param.cgi
  alone has ~50 parameter groups. Tool lists this long degrade
  LLM tool selection accuracy significantly.
- **Every new operation = new code.** Adding a catalog YAML file
  isn't enough; you also need a new Python function, tests,
  parameter mapping. The catalog becomes redundant — the real
  logic is in Python.
- **Combinatorial parameter complexity.** `param.cgi` takes
  arbitrary `key=value` pairs from dozens of namespaces. You'd
  need either one mega-tool with hundreds of optional parameters,
  or hundreds of small tools — one per parameter group.
- **Doesn't scale to multi-family.** Adding ACS means writing
  another set of typed tools. Undocumented APIs can't have typed
  tools since their signatures aren't known in advance.

**Verdict: doesn't scale. Ruled out.**

#### Option B: Raw HTTP passthrough

```
MCP tools:
  - execute_http(device_id, method, path, headers, body)
```

The MCP server is a dumb HTTP proxy. The LLM reads docs and
constructs the full HTTP request.

**Pros:**
- Maximally flexible — any HTTP call to any API
- Trivially simple MCP server
- Works for any API family, including undocumented

**Cons:**
- **No guardrails.** The LLM can call any endpoint — the risk
  model can't classify arbitrary paths it hasn't seen before.
- **LLM must handle auth, URL construction, response parsing.**
  Digest auth is particularly tricky — it's a multi-step
  challenge-response. LLMs can't do this.
- **No generation awareness.** The LLM has to know whether to
  use query params (legacy CGI) vs JSON body (JSON-RPC) vs
  RESTful paths (config-rest). Error-prone.
- **Hallucination risk.** Without the catalog constraining what's
  valid, the LLM may invent endpoints or parameters.

**Verdict: too dangerous, too error-prone. Ruled out.**

#### Option C: Catalog-in-the-loop (the right answer)

```
MCP tools (for operations):
  - query_catalog(device_id, intent)        → returns docs
  - execute_operation(device_id, operation_id, params)  → executes
```

Two tools. That's it. The LLM reads documentation, decides what
to do, and the MCP server handles the mechanical execution.

**How it works, step by step:**

```
User: "Set lobby-cam to 1080p"

Step 1 — LLM calls query_catalog:
┌────────────────────────────────────────────────────┐
│ query_catalog(                                     │
│   device_id = "lobby-cam",                         │
│   intent = "set resolution"                        │
│ )                                                  │
└────────────────────────────────────────────────────┘

Step 2 — MCP server runs the resolver:
  a. Maps "set resolution" to index key "change-resolution"
  b. Reads index/by-task.yaml → gets file paths:
     - vapix/cgi/param.cgi/groups/root.Image.yaml
     - vapix/cgi/param.cgi/update.yaml
     - vapix/cgi/param.cgi/_cgi.yaml
  c. Checks device profile: lobby-cam is P1455-LE fw 11.6,
     supports param.cgi, no config-rest yet
  d. Loads the matching files (~60 lines of YAML)
  e. Checks risk: root.Image is "normal" risk

Step 3 — MCP returns documentation to LLM:
┌────────────────────────────────────────────────────┐
│ {                                                  │
│   "operations": [                                  │
│     {                                              │
│       "id": "param.cgi:update",                    │
│       "endpoint": "/axis-cgi/param.cgi",           │
│       "method": "GET",                             │
│       "params_template": {                         │
│         "action": "update",                        │
│         "root.Image.I0.Resolution": "<value>"      │
│       },                                           │
│       "parameter_docs": {                          │
│         "Resolution": {                            │
│           "type": "enum",                          │
│           "valid_values_from":                      │
│             "Properties.Image.Resolution",          │
│           "examples": ["1920x1080", "1280x720"]    │
│         }                                          │
│       },                                           │
│       "risk_level": "normal",                      │
│       "notes": "Will briefly interrupt stream"     │
│     }                                              │
│   ],                                               │
│   "device": {                                      │
│     "model": "P1455-LE",                           │
│     "firmware": "11.6",                            │
│     "generation": "legacy-cgi"                     │
│   }                                                │
│ }                                                  │
└────────────────────────────────────────────────────┘

Step 4 — LLM reads the docs and proposes a plan:
  "I'll set lobby-cam to 1080p by calling param.cgi:update
   with root.Image.I0.Resolution=1920x1080. This may briefly
   interrupt the stream. Proceed?"

Step 5 — User approves. LLM calls execute_operation:
┌────────────────────────────────────────────────────┐
│ execute_operation(                                  │
│   device_id = "lobby-cam",                         │
│   operation_id = "param.cgi:update",               │
│   params = {                                       │
│     "root.Image.I0.Resolution": "1920x1080"        │
│   }                                                │
│ )                                                  │
└────────────────────────────────────────────────────┘

Step 6 — MCP server handles the mechanical parts:
  a. Looks up operation_id in catalog → gets endpoint, method,
     generation, auth requirements
  b. Gets credentials from registry for lobby-cam
  c. Builds the HTTP request based on generation:
     - legacy-cgi: GET /axis-cgi/param.cgi?action=update&
                   root.Image.I0.Resolution=1920x1080
     - json-rpc: POST with JSON body (if it were that type)
     - config-rest: PUT/POST to REST path (if it were that type)
  d. Handles digest auth (challenge-response)
  e. Makes the HTTP call
  f. Parses the response according to the operation's
     response format spec
  g. Returns structured result to LLM

Step 7 — MCP returns result:
┌────────────────────────────────────────────────────┐
│ {                                                  │
│   "success": true,                                 │
│   "operation_id": "param.cgi:update",              │
│   "device_id": "lobby-cam",                        │
│   "response": "OK",                                │
│   "warnings": ["Stream may have briefly restarted"]│
│ }                                                  │
└────────────────────────────────────────────────────┘

Step 8 — LLM tells user:
  "Done. Resolution set to 1920x1080 on lobby-cam."
```

### Why Option C is right

**The LLM handles what it's good at:**
- Reading documentation and understanding which parameters to use
- Choosing between multiple valid approaches
- Explaining tradeoffs to the user ("this will interrupt the stream")
- Adjusting when the user gives feedback ("not 4K, use 1080p")

**The MCP server handles what code is good at:**
- Digest auth (multi-step challenge-response — LLMs can't do this)
- URL construction from generation-specific rules
- Response parsing and error extraction
- Risk classification (mechanical lookup)
- Credential retrieval from the registry

**The catalog is the intelligence:**
- Adding a new operation means adding a YAML file. No code changes.
- The resolver filters docs based on device capability — the LLM
  only sees operations that work on the target device.
- The risk model constrains what can be executed.
- Undocumented APIs work the same way — the YAML just has
  `status: undocumented` and the LLM warns the user.

### The execute_operation tool in detail

```python
# This is the entire execution logic — one tool, all operations.

async def execute_operation(
    device_id: str,
    operation_id: str,
    params: Dict[str, str],
) -> Dict[str, Any]:
    """
    Execute a catalog operation against a device.

    The operation_id comes from query_catalog results.
    The params come from the LLM's reading of the docs.
    """
    # 1. Load operation spec from catalog
    operation = catalog.get_operation(operation_id)
    if not operation:
        return {"error": f"Unknown operation: {operation_id}"}

    # 2. Risk check (Gate 2)
    risk = catalog.get_risk_level(operation_id)
    if risk == "dangerous":
        return block_dangerous(operation_id, operation)

    # 3. Get credentials + device info
    device = registry.get_device_info(device_id)
    creds = registry.get_credentials(device_id)

    # 4. Build HTTP request based on generation
    request = build_request(operation, device, params)
    #   - legacy-cgi → GET with query params
    #   - json-rpc → POST with JSON body
    #   - config-rest → REST method + path + JSON body

    # 5. Execute with auth
    response = await http_client.request(
        method=request.method,
        url=f"https://{device['host']}{request.path}",
        params=request.query_params,
        json=request.json_body,
        auth=DigestAuth(creds['username'], creds['password']),
    )

    # 6. Parse response per operation spec
    result = parse_response(operation, response)

    # 7. Add warnings if service-affecting
    if risk == "service-affecting":
        result["warnings"] = [operation.get("service_impact", "")]

    return result
```

The `build_request` function is the only part that needs to know
about VAPIX generations. It's ~50 lines covering three cases:

```python
def build_request(operation, device, params):
    gen = operation["generation"]

    if gen == "legacy-cgi":
        # params become query parameters
        query = {"action": operation["request"]["query"]["action"]}
        query.update(params)
        return Request(
            method=operation["method"],
            path=operation["endpoint"],
            query_params=query,
        )

    elif gen == "json-rpc":
        # params go into JSON body
        body = dict(operation["request"]["body"])
        body["params"] = params
        return Request(
            method="POST",
            path=operation["endpoint"],
            json_body=body,
        )

    elif gen == "config-rest":
        # params become JSON body, path from operation
        return Request(
            method=operation["method"],
            path=operation["base_path"] + operation.get("path", ""),
            json_body=params,
        )
```

That's it. Three generation handlers. Not hundreds of typed tools.

### MCP tool inventory (complete)

With the catalog-in-the-loop model, the full set of MCP tools is:

```
Registry tools (existing):
  list_devices            — list all devices
  get_device              — device info by ID/nickname
  search_devices          — filter by tags, model, location
  list_accounts           — accounts for a device
  get_credentials         — retrieve auth credentials
  register_device         — add a device
  add_account             — add account to device
  update_device           — update device metadata
  delete_device           — remove a device
  delete_account          — remove an account
  capture_credentials     — generate OOB credential entry URL
  check_capture_status    — check if credentials were entered

Catalog + execution tools (new):
  query_catalog           — "what can I do on this device for X?"
                            Returns filtered operation docs.
  execute_operation       — run a catalog operation against a device.
                            Handles auth, HTTP, response parsing.
  confirm_dangerous       — confirm a blocked dangerous operation
                            (single-use token from execute_operation)

Interrogation tools (new):
  interrogate_device      — discover device capabilities,
                            populate device profile in registry

Discovery tools (new, from network discovery work):
  scan_network            — discover devices on the network
  probe_device            — targeted probe of a specific IP
```

That's ~17 tools total. The LLM sees a clean, manageable list.
The complexity lives in the catalog YAML, not in tool proliferation.

### Why this works for non-VAPIX families too

The same two-tool pattern (`query_catalog` + `execute_operation`)
works for every API family. The catalog YAML describes the operation.
The executor adapter handles the transport:

```
LLM: query_catalog("acs-server-01", "list recordings")
MCP: loads acs/rest/recordings/list.yaml → returns docs
LLM: reads docs, calls execute_operation(
       "acs-server-01", "acs:recordings:list", {date: "2024-01-15"})
MCP: ACSExecutor builds REST request with Windows auth → executes
```

The LLM doesn't know or care whether it's talking to a camera
via VAPIX or a server via ACS REST. It reads docs, picks params,
calls `execute_operation`. The MCP server routes to the right
executor adapter based on the operation's family prefix.

### When the LLM calls query_catalog multiple times

Sometimes the LLM needs to learn before it can act. This is
expected and efficient:

```
Round 1: query_catalog("lobby-cam", "change resolution")
  → LLM learns: Resolution is an enum, valid values come
    from Properties.Image.Resolution. But what are the
    actual valid values for this specific camera?

Round 2: execute_operation("lobby-cam",
           "param.cgi:list", {group: "Properties.Image"})
  → LLM gets: Properties.Image.Resolution=1920x1080,1280x720,...
  → Now it knows the valid enum values for this camera.

Round 3: execute_operation("lobby-cam",
           "param.cgi:update",
           {"root.Image.I0.Resolution": "1920x1080"})
  → Done.
```

Three tool calls, total. The first returns ~60 lines of YAML.
The second returns device-specific property values. The third
makes the change. This is how an expert human would do it too:
check the docs, check the device, make the change.

---

## Execution Plans — Batch Operations with Single Approval

### The problem with step-by-step approval

The execution model above works for single operations. But real
configuration tasks often require many calls:

- **Deploy a camera from scratch**: set hostname, IP config,
  resolution, compression, framerate, motion detection zones,
  user accounts, NTP, DNS, HTTPS cert, ONVIF settings.
  Easily 20-40 VAPIX calls.

- **Standardize a fleet**: apply the same configuration to 50
  cameras. That's 50 × 20 = 1,000 calls.

- **Audit compliance**: read configuration from every device,
  compare against a baseline. Hundreds of read-only calls.

Requiring the user to approve each call individually makes this
unusable. The user wants to describe the goal, review the plan
once, hit "go", and walk away.

### The plan as the approval artifact

An execution plan is a concrete, ordered list of operations with
actual parameters — not a vague description, but the real calls
the MCP will make. The LLM generates it. The user approves it.
The MCP executes it autonomously.

```
User: "Set up parking-cam with our standard outdoor config"

LLM: (calls query_catalog multiple times to gather the right
      operations, reads the "standard outdoor" config template
      from previous conversations or a config file)

LLM presents plan:
┌─────────────────────────────────────────────────────────┐
│  Execution plan for parking-cam (P3265-LVE, fw 11.11)  │
│                                                         │
│  14 operations, estimated time: ~8 seconds              │
│  Risk summary: 0 dangerous, 2 service-affecting,        │
│                12 normal                                │
│                                                         │
│  Step  Operation                   Risk    Params       │
│  ─────────────────────────────────────────────────────  │
│   1    param.cgi:update            normal  hostname     │
│        root.Network.HostName = "parking-cam"            │
│                                                         │
│   2    param.cgi:update            normal  resolution   │
│        root.Image.I0.Resolution = "1920x1080"           │
│        root.Image.I0.Compression = 30                   │
│                                                         │
│   3    param.cgi:update            normal  framerate    │
│        root.Image.I0.MaxFrameRate = 15                  │
│                                                         │
│   4    param.cgi:update            svc-aff stream prof  │
│        root.StreamProfile.S0.Name = "Main"              │
│        root.StreamProfile.S0.Parameters = ...           │
│        NOTE: may restart active streams                  │
│                                                         │
│  ...10 more steps...                                    │
│                                                         │
│  14    param.cgi:update            normal  NTP          │
│        root.Time.NTPServer = "pool.ntp.org"             │
│                                                         │
│  Approve this plan? [yes / edit / cancel]               │
└─────────────────────────────────────────────────────────┘
```

The user sees exactly what will happen. They can:
- **Approve** → MCP executes all 14 steps autonomously
- **Edit** → "skip step 4, I'll set stream profiles separately"
- **Cancel** → nothing happens

### Plan data structure

```python
@dataclass
class PlanStep:
    """One operation in an execution plan."""
    step_number: int
    operation_id: str              # "param.cgi:update"
    device_id: str                 # "parking-cam"
    params: Dict[str, str]         # the actual parameters
    description: str               # human-readable summary
    risk_level: str                # from catalog
    depends_on: List[int] = []     # step numbers this depends on
    condition: Optional[str] = None  # "only if step 2 succeeded"

@dataclass
class ExecutionPlan:
    """A batch of operations approved for autonomous execution."""
    plan_id: str                   # unique identifier
    created_by: str                # "llm-session-xyz"
    created_at: datetime
    description: str               # "Standard outdoor config for parking-cam"
    steps: List[PlanStep]
    risk_summary: Dict[str, int]   # {"normal": 12, "service-affecting": 2}
    status: str                    # "pending_approval" | "approved" | "executing"
                                   # | "completed" | "failed" | "cancelled"
    approval_token: Optional[str]  # set when user approves
    results: List[StepResult] = [] # populated during execution
```

### Plan-aware MCP tools

The MCP gets three new tools for plan management:

```
Plan tools:
  create_plan         — LLM submits a complete plan for approval
  execute_plan        — execute an approved plan (autonomous)
  get_plan_status     — check progress of a running plan
```

#### `create_plan` — LLM submits a plan

The LLM calls this after using `query_catalog` to figure out
what operations are needed. The plan contains concrete operation
calls, not abstract intents.

```python
async def create_plan(
    description: str,
    steps: List[Dict],        # [{operation_id, device_id, params, ...}]
) -> Dict[str, Any]:
    """
    Validate and store an execution plan.

    Does NOT execute — returns the plan for user review.
    """
    # 1. Validate every operation_id exists in catalog
    # 2. Validate params against operation specs where possible
    # 3. Compute risk summary from catalog risk classifications
    # 4. Check for dangerous operations — flag them prominently
    # 5. Verify all referenced devices exist in registry
    # 6. Store plan with status="pending_approval"

    return {
        "plan_id": plan.plan_id,
        "status": "pending_approval",
        "step_count": len(steps),
        "risk_summary": risk_summary,
        "dangerous_steps": [...],     # highlighted for the LLM
        "estimated_duration_seconds": estimate,
        "plan_summary": formatted_table,  # for LLM to show user
    }
```

The LLM receives this back and presents it to the user. The plan
summary is formatted so the LLM can display it clearly. The LLM
does NOT need to reformat — it can pass through the summary.

#### `execute_plan` — run an approved plan

```python
async def execute_plan(
    plan_id: str,
) -> Dict[str, Any]:
    """
    Execute all steps in an approved plan.

    Runs autonomously — does not pause for per-step approval.
    Returns results for all steps.
    """
    plan = plan_store.get(plan_id)

    results = []
    for step in plan.steps:
        # Check dependencies
        if not dependencies_met(step, results):
            results.append(StepResult(
                step=step.step_number,
                status="skipped",
                reason="dependency failed",
            ))
            continue

        # Execute (same logic as execute_operation)
        result = await execute_single_operation(
            step.device_id,
            step.operation_id,
            step.params,
        )
        results.append(result)

        # On failure: check plan's failure policy
        if not result.success:
            if plan.on_failure == "stop":
                break
            elif plan.on_failure == "skip_dependents":
                continue  # deps will be auto-skipped
            # "continue" → keep going regardless

    return {
        "plan_id": plan_id,
        "status": "completed" if all_ok else "failed",
        "steps_total": len(plan.steps),
        "steps_succeeded": count_ok,
        "steps_failed": count_fail,
        "steps_skipped": count_skip,
        "results": results,
        "duration_seconds": elapsed,
    }
```

#### `get_plan_status` — check progress

For long-running plans (fleet operations), the LLM (or user)
can poll for progress:

```python
async def get_plan_status(plan_id: str) -> Dict[str, Any]:
    return {
        "plan_id": plan_id,
        "status": plan.status,
        "progress": f"{completed}/{total}",
        "current_step": current_step_number,
        "results_so_far": results,
        "errors": [r for r in results if not r.success],
    }
```

### Plan execution: what the MCP does autonomously

Once approved, plan execution requires NO further LLM interaction.
The MCP server iterates through steps sequentially:

```
execute_plan("plan-abc123")

  Step 1/14: param.cgi:update on parking-cam
    → GET /axis-cgi/param.cgi?action=update&
          root.Network.HostName=parking-cam
    → 200 OK ✓  (142ms)

  Step 2/14: param.cgi:update on parking-cam
    → GET /axis-cgi/param.cgi?action=update&
          root.Image.I0.Resolution=1920x1080&
          root.Image.I0.Compression=30
    → 200 OK ✓  (89ms)

  ...

  Step 14/14: param.cgi:update on parking-cam
    → GET /axis-cgi/param.cgi?action=update&
          root.Time.NTPServer=pool.ntp.org
    → 200 OK ✓  (76ms)

  Plan complete: 14/14 succeeded, 0 failed, 0 skipped
  Total duration: 6.2 seconds
```

The user walks away after approval. The LLM presents the final
results when the user comes back.

### Failure handling policies

Plans have a configurable failure policy:

```yaml
on_failure: stop            # abort remaining steps (safe default)
on_failure: skip_dependents # skip steps that depend on failed step,
                            # continue independent steps
on_failure: continue        # keep going regardless (for reads/audits)
```

The LLM chooses the appropriate policy based on the task:
- Deploying a camera → `stop` (partial config is worse than none)
- Auditing a fleet → `continue` (one unreachable camera shouldn't
  stop the audit of 49 others)
- Sequential dependencies → `skip_dependents` (if hostname fails,
  skip HTTPS cert that needs the hostname, but still do NTP)

### Rollback on plan failure

When a plan fails partway through and `on_failure: stop`:

```
Step 1: set hostname         ✓
Step 2: set resolution       ✓
Step 3: set stream profile   ✗ FAILED (invalid parameter)
Step 4-14: not executed

Plan failed at step 3. Steps 1-2 succeeded.
Rollback available for steps 1-2.
```

The MCP returns the failure plus a rollback plan:

```json
{
  "status": "failed",
  "failed_at_step": 3,
  "error": "Invalid parameter: root.StreamProfile.S0.Parameters",
  "rollback_available": true,
  "rollback_plan_id": "rollback-abc123",
  "rollback_steps": [
    {"step": 2, "operation": "param.cgi:update",
     "params": {"root.Image.I0.Resolution": "1280x720",
                "root.Image.I0.Compression": 20},
     "description": "Revert resolution to previous values"},
    {"step": 1, "operation": "param.cgi:update",
     "params": {"root.Network.HostName": "axis-accc8e012345"},
     "description": "Revert hostname to previous value"}
  ]
}
```

How does it know the previous values? Before each write operation,
the executor reads the current value using the corresponding
read operation. This is why the operation YAML files include
`rollback.strategy`:

```yaml
# From param.cgi/update.yaml
rollback:
  strategy: revert-params
  description: >
    Read current values before update, store them, re-apply
    on rollback via another update call.
```

The plan executor does this automatically:

```python
# Before executing a write step:
if operation.rollback and operation.rollback.strategy == "revert-params":
    # Read current values first
    current = await execute_single_operation(
        step.device_id,
        "param.cgi:list",
        {group: extract_group(step.params)},
    )
    # Store for potential rollback
    step.rollback_data = current
```

The rollback plan is itself a plan — it goes through the same
approval flow. The LLM presents it to the user:

"Plan failed at step 3 (invalid stream profile parameter).
Steps 1-2 already applied (hostname + resolution). Want me
to roll back those changes?"

### Fleet plans — the same config on many devices

For fleet operations, the LLM generates a plan with repeated
operations across multiple devices:

```
User: "Apply standard outdoor config to all parking cameras"

LLM: (searches for devices with tag "parking", finds 12 cameras)
     (generates plan: 14 operations × 12 devices = 168 steps)

Plan summary:
  168 operations across 12 devices
  12 cameras: parking-01 through parking-12
  14 config steps per camera (same as single-camera plan)
  Risk: 0 dangerous, 24 service-affecting, 144 normal
  Estimated duration: ~45 seconds

  Failure policy: skip_dependents
  (if one camera is unreachable, continue with the rest)
```

The plan is flat — 168 steps. But the LLM presents it grouped
by device for readability. Internally it's a simple list that
the executor iterates through.

For fleet plans, parallelism is desirable. The executor could
run operations on different devices concurrently (since they're
independent), while keeping operations on the same device
sequential:

```python
# Group steps by device
by_device = group_by(plan.steps, key=lambda s: s.device_id)

# Execute devices in parallel, steps within each device sequential
results = await asyncio.gather(*[
    execute_device_steps(device_id, steps)
    for device_id, steps in by_device.items()
])
```

This turns 168 sequential calls (~45s) into 12 parallel batches
of 14 calls (~4s). The user barely waits.

### Plan storage and history

Plans are persisted so they can be:
- **Audited**: "who ran what on which devices and when?"
- **Re-run**: "apply the same plan to 5 new cameras"
- **Templated**: "save this as the standard outdoor config plan"

```
admz plan history
  PLAN-001  2024-01-15 14:30  "Deploy parking-cam"        14 steps  ✓ completed
  PLAN-002  2024-01-15 15:00  "Fleet: outdoor standard"  168 steps  ✓ completed
  PLAN-003  2024-01-16 09:15  "Audit NTP compliance"      50 steps  ✓ completed
  PLAN-004  2024-01-16 10:00  "Update firmware lobby-cam"   3 steps  ✗ failed step 2

admz plan show PLAN-001
  (displays full plan with results)

admz plan rerun PLAN-001 --device new-parking-cam
  (creates a new plan from template, replacing device_id)
```

### Updated MCP tool inventory

```
Registry tools (existing):
  list_devices, get_device, search_devices,
  list_accounts, get_credentials,
  register_device, add_account, update_device,
  delete_device, delete_account,
  capture_credentials, check_capture_status

Catalog tools:
  query_catalog           — "what can I do on this device for X?"

Single-operation execution:
  execute_operation       — run one operation (for exploration,
                            one-off reads, interactive use)
  confirm_dangerous       — confirm a blocked dangerous operation

Plan execution:
  create_plan             — submit a multi-step plan for review
  execute_plan            — run an approved plan autonomously
  get_plan_status         — check progress of a running plan

Interrogation:
  interrogate_device      — discover device capabilities

Discovery:
  scan_network            — find devices on the network
  probe_device            — targeted probe of a specific IP
```

21 tools total. Clean separation between interactive use
(query_catalog + execute_operation) and batch use
(create_plan + execute_plan).

---

## Implementation Roadmap — What Needs to Be Built

Here's everything that needs to exist for the catalog-in-the-loop
architecture with execution plans. Grouped by component, roughly
in build order.

### 1. Catalog repository (the YAML files)

**Status:** not started — needs a new repo
**What it is:** the `operations-catalog` git repo

```
operations-catalog/
├── vapix/
│   ├── cgi/
│   │   ├── param.cgi/
│   │   │   ├── _cgi.yaml
│   │   │   ├── list.yaml
│   │   │   ├── update.yaml
│   │   │   └── groups/
│   │   │       ├── root.Image.yaml
│   │   │       ├── root.Network.yaml
│   │   │       └── ...
│   │   ├── basicdeviceinfo.cgi/
│   │   ├── apidiscovery.cgi/
│   │   └── ...
│   ├── devices/
│   ├── firmware/
│   └── index/
│       ├── by-task.yaml
│       ├── by-feature.yaml
│       └── by-risk.yaml
├── schema/
│   └── *.schema.yaml
└── scripts/
    └── validate.py
```

**Build approach:** start with 5-10 of the most common CGIs
(param.cgi, basicdeviceinfo.cgi, network.cgi, time.cgi,
apidiscovery.cgi). These cover the majority of daily configuration
tasks. Add more incrementally.

**Priority:** HIGH — everything else depends on this.

### 2. Catalog loader (`admz/catalog/`)

**Status:** not started
**What it does:** reads YAML from the local catalog clone

```python
# admz/catalog/loader.py

class CatalogLoader:
    """Reads operation YAML files from the catalog directory."""

    def __init__(self, catalog_path: str):
        self.catalog_path = Path(catalog_path)

    def get_operation(self, operation_id: str) -> Operation:
        """Load a single operation by ID."""

    def get_cgi_metadata(self, cgi_name: str) -> CgiMetadata:
        """Load _cgi.yaml for a CGI endpoint."""

    def get_parameter_group(self, group: str) -> ParameterGroup:
        """Load a param.cgi parameter group file."""

    def get_device_profile(self, model: str) -> DeviceProfile:
        """Load a device capability profile."""
```

**Complexity:** LOW — it's just YAML file loading with caching.

### 3. Resolver (`admz/catalog/resolver.py`)

**Status:** not started
**What it does:** the query_catalog brain — maps intent + device
to filtered operation docs

```python
# admz/catalog/resolver.py

class CatalogResolver:
    """Maps (device, intent) → relevant operation documents."""

    def __init__(self, loader: CatalogLoader, registry: DeviceRegistry):
        self.loader = loader
        self.registry = registry
        self.task_index = loader.load_index("by-task")
        self.risk_index = loader.load_index("by-risk")

    def resolve(
        self,
        device_id: str,
        intent: str,
    ) -> ResolverResult:
        """
        1. Map intent to index keys (fuzzy/semantic match)
        2. Look up file paths from task index
        3. Filter by device capabilities (model, firmware)
        4. Load matching files
        5. Annotate with risk levels
        6. Return filtered docs
        """
```

**Complexity:** MEDIUM — the intent-to-index-key mapping is the
interesting part. Options:
- Simple keyword matching (fast, good enough for v1)
- Embedding similarity against index keys (better for v2)
- LLM does the mapping itself (pass the index keys to the LLM
  and let it pick — surprisingly effective)

### 4. Executor (`admz/executor/`)

**Status:** not started
**What it does:** builds and sends HTTP requests from operation specs

```
admz/executor/
├── base.py            # abstract executor interface
├── vapix.py           # VAPIX executor (digest auth, 3 generations)
├── http_client.py     # shared async HTTP with retry, timeout
└── models.py          # Request, Response, StepResult dataclasses
```

Key implementation detail — the `build_request` function:

```python
# admz/executor/vapix.py

class VAPXExecutor(BaseExecutor):

    async def execute(self, operation, device, params) -> StepResult:
        creds = await self.registry.get_credentials(device.device_id)
        request = self.build_request(operation, device, params)

        response = await self.http_client.request(
            method=request.method,
            url=f"https://{device.host}{request.path}",
            params=request.query_params,
            json=request.json_body,
            auth=DigestAuth(creds.username, creds.password),
            timeout=operation.get("timeout", 10),
        )

        return self.parse_response(operation, response)

    def build_request(self, operation, device, params):
        gen = operation["generation"]
        if gen == "legacy-cgi":
            ...  # query params
        elif gen == "json-rpc":
            ...  # JSON body
        elif gen == "config-rest":
            ...  # REST path + body
```

**Complexity:** MEDIUM — digest auth handling is the fiddly part,
but `httpx` handles it natively. The three generation handlers
are straightforward.

**Dependency:** needs catalog loader + device registry.

### 5. Plan engine (`admz/plans/`)

**Status:** not started
**What it does:** plan creation, validation, execution, rollback

```
admz/plans/
├── models.py          # PlanStep, ExecutionPlan, StepResult
├── engine.py          # plan validation, execution loop
├── rollback.py        # pre-read values, generate rollback plans
└── store.py           # plan persistence (SQLite)
```

**Complexity:** MEDIUM-HIGH — the execution loop with dependency
tracking, failure policies, rollback data capture, and parallel
fleet execution is the most complex new component.

**Dependency:** needs executor + catalog loader.

### 6. MCP tool additions (`admz/mcp/server.py`)

**Status:** existing server needs new tools added
**What to add:**

```python
# New tools:
#   query_catalog    → CatalogResolver.resolve()
#   execute_operation → Executor.execute()
#   confirm_dangerous → risk gate confirmation
#   create_plan      → PlanEngine.create()
#   execute_plan     → PlanEngine.execute()
#   get_plan_status  → PlanEngine.status()
#   interrogate_device → Interrogator.interrogate()
#   scan_network     → DiscoveryOrchestrator.scan()
#   probe_device     → DiscoveryOrchestrator.probe()
```

**Complexity:** LOW — these are thin wrappers that delegate to
the components above. The MCP tools are glue code.

**Dependency:** needs all of the above.

### 7. Interrogator (`admz/interrogator/`)

**Status:** not started
**What it does:** discovers device capabilities via API calls

```
admz/interrogator/
├── base.py            # abstract interrogator interface
├── vapix.py           # VAPIX: basicdeviceinfo → apidiscovery → properties
└── models.py          # InterrogationResult, DeviceCapabilities
```

The interrogator is what populates the device profile in the
registry — so the resolver knows what operations a device supports.

**Complexity:** MEDIUM — the VAPIX interrogation flow has 3 stages
that must be tried in order, with graceful fallback for older
firmware that doesn't support apidiscovery.

**Dependency:** needs executor (it makes VAPIX calls to interrogate).

### Build order

```
                    ┌─────────────────┐
                    │  1. Catalog repo │ ← YAML files, no code
                    │     (YAML)       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  2. Catalog     │ ← load + cache YAML
                    │     loader      │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
       ┌────────▼───┐  ┌────▼─────┐  ┌───▼──────────┐
       │ 3. Resolver │  │4. Exec-  │  │ 5. Interro-  │
       │   (query)   │  │  utor    │  │    gator     │
       └────────┬────┘  └────┬─────┘  └───┬──────────┘
                │            │            │
                └────────────┼────────────┘
                             │
                    ┌────────▼────────┐
                    │  6. Plan engine │ ← validation, execution,
                    │                 │   rollback, fleet parallel
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  7. MCP tools   │ ← thin wrappers
                    │                 │
                    └─────────────────┘
```

Steps 3, 4, 5 can be built in parallel since they only depend
on the loader. The plan engine depends on the executor. MCP tools
depend on everything.

### What already exists and just needs wiring

- **Device registry** ✓ — SQLite + Vault backends, working
- **Network discovery** ✓ — mDNS, SSDP, ONVIF, ARP, HTTP probe
- **MCP server** ✓ — registry tools working, just needs new tools
- **Credential capture** ✓ — OOB web flow working
- **Factory pattern** ✓ — backend selection working

### What's new

| Component | New files | Estimated size | Complexity |
|---|---|---|---|
| Catalog repo (YAML) | ~50 initially | ~3K lines YAML | Low (manual) |
| Catalog loader | 2-3 .py | ~200 lines | Low |
| Resolver | 1-2 .py | ~300 lines | Medium |
| Executor | 3-4 .py | ~400 lines | Medium |
| Plan engine | 3-4 .py | ~500 lines | Medium-High |
| Interrogator | 2-3 .py | ~300 lines | Medium |
| MCP tool additions | 1 .py (extend) | ~300 lines | Low |
| **Total new code** | **~15 files** | **~2,000 lines** | |

~2,000 lines of new Python code to go from "registry only" to
"full catalog-in-the-loop with execution plans." The catalog
YAML is the larger effort, but it's incremental — start with
5-10 CGIs, add more as needed.

---

## Catalog Size Estimation

Rough estimate of the full catalog at maturity:

| Content | Files | Avg lines | Total lines |
|---|---|---|---|
| CGI metadata (`_cgi.yaml`) | ~25 | 10 | 250 |
| CGI operations | ~120 | 40 | 4,800 |
| param.cgi groups | ~50 | 60 | 3,000 |
| config-rest operations | ~30 | 35 | 1,050 |
| Device profiles | ~80 | 80 | 6,400 |
| Firmware changelogs | ~10 | 30 | 300 |
| Index files | 3 | ~100 | 300 |
| Schemas | 5 | 50 | 250 |
| **Total** | **~323** | | **~16,350** |

~16K lines of YAML across ~320 small files. Trivially fits in a git repo.
Clones in under a second. The 3 index files are ~100 lines each — load
instantly into memory.

At query time, the resolver reads an index key, gets 2-6 file paths,
loads those specific files (< 300 lines total), and returns them to
the LLM. The rest of the catalog is never touched.

---

## CI Validation

The catalog repo would have CI that runs on every PR:

1. **Schema validation** — all YAML files conform to their schema
2. **Index integrity** — every file path in `index/*.yaml` actually exists
3. **Orphan detection** — warn about CGI operation files not referenced
   by any index entry (unreachable via search)
4. **Referential integrity** — `_cgi.yaml` exists for every CGI directory,
   device profiles reference CGIs that exist in `cgi/`
5. **Duplicate detection** — no two operations have the same `id`

---

## Key Properties of This Design

| Property | How it's achieved |
|---|---|
| **Unambiguous organization** | Filesystem mirrors CGI paths — no category debates |
| **Small files** | One operation per file, 20-80 lines each |
| **Clean separation** | CGI files = pure reference; index files = routing/tags |
| **Non-exclusive routing** | Tags in index files — a CGI can appear under many tags |
| **Fast lookup** | Read index key → get 2-6 file paths → load only those |
| **Version-aware** | Per-version directories where APIs diverge |
| **Community-improvable** | Git repo with PR workflow and CI validation |
| **Offline-capable** | Local clone, no runtime network dependency |
| **LLM-friendly** | YAML is readable; filtered subsets fit in context easily |
| **Scales to hundreds of ops** | ~320 files at maturity, index files stay small |

---

## Beyond VAPIX — Multi-API-Family Architecture

VAPIX is the first API family ADMZ supports, but not the last.
Planned future families include:

| API family | What it talks to | Protocol | Auth model |
|---|---|---|---|
| `vapix` | Axis cameras/devices (on-device) | HTTP to device IP | Digest/Basic per-device |
| `vapix-undocumented` | Same devices, unofficial endpoints | HTTP to device IP | Same as vapix |
| `acs` | AXIS Camera Station (VMS) | REST to Windows server | Windows auth / API key |
| `aoa` | AXIS Object Analytics (ACAP) | VAPIX + ACAP framework APIs | Digest (via device) |
| `onvif` | Any ONVIF-conformant device | SOAP/WS to device IP | WS-Security tokens |
| `body-worn` | AXIS Body Worn Manager | REST to cloud/server | OAuth/API key |

Each family has fundamentally different:
- **Transport**: HTTP to a device IP vs REST to a server vs SOAP
- **Authentication**: Digest auth vs Windows auth vs API keys vs OAuth
- **Discovery**: apidiscovery.cgi vs ACS server API vs ONVIF probes
- **Operation shape**: CGI params vs JSON REST vs SOAP envelopes

But they share:
- **Risk classification**: A factory reset is dangerous whether it's VAPIX or ACS
- **Plan approval**: Gate 1 (semantic) and Gate 2 (safety) apply to all families
- **Index concept**: "I want to do X" → "here are the operations" works for any API
- **Device/target registry**: Everything has an address, credentials, capabilities

### What to namespace now (cheap, prevents pain later)

#### 1. Catalog directory: top-level API family prefix

Current design:
```
vapix-catalog/
├── cgi/
├── config-rest/
├── devices/
├── firmware/
└── index/
```

Better — add a top-level family directory:
```
operations-catalog/
├── vapix/
│   ├── cgi/
│   ├── config-rest/
│   ├── devices/
│   ├── firmware/
│   └── index/
│
├── vapix-undocumented/
│   ├── endpoints/
│   ├── index/
│   └── README.md              # discovery notes, status, caveats
│
├── acs/
│   ├── rest/                  # ACS REST API operations
│   ├── servers/               # ACS server profiles (like devices/)
│   └── index/
│
├── aoa/                       # may be thin — wraps VAPIX ACAP APIs
│   ├── operations/
│   └── index/
│
└── schema/                    # shared schemas (risk levels, etc.)
```

This is just a directory rename. All existing file references become
`vapix/cgi/param.cgi/...` instead of `cgi/param.cgi/...`. The resolver
prefixes the family when loading files.

The catalog repo name also changes from `vapix-catalog` to
`operations-catalog` (or `admz-catalog`). VAPIX is still the majority
of the content, but it's no longer the only resident.

#### 2. Index files: scoped per family, plus a cross-family index

Each API family has its own `index/` with `by-task.yaml`, `by-risk.yaml`,
etc. These are self-contained — `vapix/index/by-task.yaml` only
references files under `vapix/`.

Additionally, a top-level cross-family index enables queries that
span families:

```yaml
# index/by-task.yaml (cross-family)
#
# Maps tasks to operations across all API families.
# Entries reference family-scoped paths.

configure-analytics:
  - vapix/cgi/param.cgi/groups/root.Analytics.yaml
  - aoa/operations/configure-scenario.yaml

manage-recordings:
  - vapix/cgi/record.cgi/start.yaml
  - acs/rest/recordings/list.yaml
  - acs/rest/recordings/export.yaml

manage-users:
  - vapix/cgi/pwdgrp.cgi/add-user.yaml
  - acs/rest/users/create.yaml
```

The resolver checks: does the target device/server support this
API family? If lobby-cam is a VAPIX device, filter out the `acs/`
entries. If acs-server-01 is an ACS instance, filter out `vapix/`.

#### 3. Registry: API family as a device property

The device registry already stores metadata per device. Add an
`api_families` field:

```python
# A camera
{
    "device_id": "lobby-cam",
    "api_families": ["vapix"],           # discovered via interrogation
    "host": "192.168.1.100",
    ...
}

# A camera with analytics
{
    "device_id": "parking-cam",
    "api_families": ["vapix", "aoa"],    # AOA detected via ACAP list
    "host": "192.168.1.101",
    ...
}

# An ACS server
{
    "device_id": "acs-server-01",
    "api_families": ["acs"],
    "host": "192.168.1.200",
    "port": 55756,
    ...
}
```

The resolver uses `api_families` to know which catalog subtrees
are relevant for a given target.

#### 4. Executor: adapter per API family

The executor — the component that actually makes HTTP calls — needs
to know HOW to talk to each family:

```
admz/
├── executor/
│   ├── base.py                # abstract: execute(operation, target) → result
│   ├── vapix.py               # digest auth, HTTP to device IP, CGI conventions
│   ├── acs.py                 # Windows auth or API key, REST to server
│   ├── aoa.py                 # thin wrapper around vapix executor
│   └── onvif.py               # SOAP/WS-Security (future)
```

Each adapter handles:
- Building the HTTP request from operation YAML
- Authentication for its family
- Response parsing
- Error mapping to a common format

The MCP tool `execute_operation` delegates to the right adapter
based on the operation's API family prefix:

```python
def execute_operation(operation_path, device_id, params):
    family = operation_path.split("/")[0]   # "vapix", "acs", etc.
    adapter = get_executor(family)          # VAPIXExecutor, ACSExecutor
    device = registry.get_device(device_id)
    return adapter.execute(operation_path, device, params)
```

#### 5. Interrogation: adapter per API family

Same pattern as the executor. How you discover capabilities is
family-specific:

```
VAPIX interrogation:
  basicdeviceinfo.cgi → apidiscovery.cgi → Properties.*

ACS interrogation:
  GET /acs/api/version → GET /acs/api/capabilities
  → enumerate cameras, users, recording schedules

AOA interrogation:
  VAPIX interrogation first, then:
  list installed ACAPs → check if AOA is installed
  → query AOA-specific config endpoints
```

But the interface is the same:

```python
class Interrogator(ABC):
    @abstractmethod
    async def interrogate(self, device, depth) -> InterrogationResult:
        ...

class VAPIXInterrogator(Interrogator): ...
class ACSInterrogator(Interrogator): ...
```

### Undocumented APIs — a special case

Undocumented APIs are interesting because they're **discovered at
runtime**, not curated in advance. During VAPIX interrogation,
`apidiscovery.cgi` may return API IDs that aren't in the catalog.

```
apidiscovery returns:
  - basic-device-info (v1.2)      → in catalog ✓
  - io-port-management (v1.0)     → in catalog ✓
  - custom-firmware-api (v1.0)    → NOT in catalog ✗

Action:
  1. Store in device's interrogation data under "unknown_apis"
  2. Log: "Device lobby-cam reports API 'custom-firmware-api'
           not found in catalog"
  3. Optionally: attempt getSupportedMethods on the unknown CGI
     to discover its operations automatically
  4. Store raw method list under vapix-undocumented/ locally
  5. Flag for potential catalog contribution
```

The `vapix-undocumented/` directory in the catalog is for APIs
that have been manually investigated and documented (with caveats),
not for auto-discovered raw method lists. The auto-discovered data
lives in the local device registry until someone investigates and
promotes it to the catalog.

```yaml
# vapix-undocumented/endpoints/custom-analytics.yaml
#
# Status: discovered, partially documented
# Source: reverse-engineering from browser dev tools
# Tested on: P1455-LE fw 11.8, Q6215-LE fw 11.11
# Caveats:
#   - Not documented by Axis, may break on firmware updates
#   - No stability guarantees
#   - Use at own risk

endpoint: /axis-cgi/analytics-internal.cgi
generation: json-rpc
status: undocumented            # catalog resolver shows a warning
stability: unstable             # shown to LLM so it can warn the user
discovered_via: apidiscovery    # or "browser-devtools", "firmware-analysis"

methods:
  getScenarios:
    description: "List configured analytics scenarios (internal)"
    request: { method: getScenarios }
    response_shape: { scenarios: [{ id, name, type }] }
```

Operations with `status: undocumented` trigger a warning in the
resolver response: "This operation is undocumented and may not be
stable across firmware versions." The LLM surfaces this to the user.

### What stays generic (no changes needed)

These components are already API-family-agnostic:

- **Risk classification model**: `read-only / normal / service-affecting
  / dangerous` applies to any API. Factory reset via VAPIX and
  "delete all recordings" via ACS are both `dangerous`.
- **Plan approval gates**: Gate 1 (semantic, LLM layer) and Gate 2
  (risk check, MCP layer) work regardless of API family.
- **Device registry interface**: Already stores arbitrary metadata.
  Adding `api_families` is a new field, not a schema change.
- **Network discovery**: Already protocol-agnostic (mDNS, SSDP,
  ONVIF, HTTP probes). The `DeviceType` enum already includes
  `ACCESS_CONTROL` and `NETWORK_SWITCH`.
- **MCP tool interface**: `get_available_operations(device_id, task)`
  doesn't change — it just returns results from multiple families.

### Migration path: VAPIX-first, extend later

The architecture supports multiple families, but we build VAPIX
first and add families incrementally:

```
Phase 1 (now):     VAPIX catalog only, but directory structure
                   already has the vapix/ prefix.
                   Executor has VAPIXExecutor.
                   Interrogation has VAPIXInterrogator.

Phase 2:           Add vapix-undocumented/ for known unofficial APIs.
                   Interrogation flags unknown APIs from apidiscovery.
                   No new executor needed (same HTTP transport).

Phase 3:           Add aoa/ — thin layer, mostly references VAPIX
                   operations + ACAP-specific config endpoints.

Phase 4:           Add acs/ — new executor (REST + Windows auth),
                   new interrogator, new catalog subtree.
                   ACS server profiles in acs/servers/.

Phase 5 (future):  ONVIF, Body Worn, third-party integrations.
```

Each phase adds a directory to the catalog, an executor adapter,
and an interrogator adapter. The resolver, risk model, plan approval,
MCP tools, and device registry don't change — they're already
family-agnostic.
