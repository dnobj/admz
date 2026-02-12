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
