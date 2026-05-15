---
title: Network Pairing API
url: "https://developer.axis.com/vapix/device-configuration/network-pairing-api/"
category: vapix
subcategory: device-configuration
sha256: 6d3b4e4060b1ebb0af00d234655b4e96aac603846ff9a9baa320389c3d74d846
scraped_at: "2026-01-09T15:18:52.444Z"
page_height: 18857
---

# Network Pairing API

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in **BETA** stage. The API is provided for testing purposes and is subject to backward-incompatible changes, including modifications to functionality, behavior, and availability. You shouldn't use it in a production environment.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Description

Configuring and managing Network Pairing (edge-to-edge) functionalities. A Network Pairing allows the pairing device to connect to and use functionalities on a remote paired device.

The VAPIX Network Pairing API makes it possible to configure connections with remote devices, making it possible to extend the functionality of the primary device.

warning

This API includes sending sensitive data over the network and should only be used over a secured channel.

## Plugins

Network Pairing uses a plugin system, allowing different models to exclude features not needed on the units. Therefore, API consumers must check whether or not a plugin is supported before attempting to access its functionality. This is done by sending a `GET` request to the property `networkpairing.v1.plugins/<plugin_name>_supported`.

For example, to check if the siren light plugin is supported, send the following request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  --header "Accept: application/json" \\  "http://<servername>/config/rest/networkpairing/v1/plugins/siren\_light\_supported"
```

```bash
GET /config/rest/networkpairing/v1/plugins/siren\_light\_supportedHost: <servername>Content-Type: application/jsonAccept: application/json
```

Example response:

```bash
200 OKContent-Type: application/json{    "data": true}
```

## Use Cases
### Manage pairings

Pairings are located in the `networkpairing.v1.pairings` collection which can be queried to configure connections to remote devices. The expected users of the API are video management systems (VMS) or web UI clients.

#### Add a pairing

New pairings can be configured by sending a `POST` request to `networkpairing.v1.pairings`. The request body must contain the address to the remote device, a username to the remote device, as well as the password for said user. The password can be updated but never read after a pairing has been created.

warning

All communication between the devices will be encrypted. To ensure that no unauthorized actor can impersonate a remote device, the remote device's certificate common name (CN) must be provided if it differs from the address used to connect to the device. The CN can be located at `System > Security > [Certificate name] > Certificate information > Issued to > Common name (CN)` in the remote device's web GUI, ex: `axis-12345abcd67e-eccp256-1`.

For example, to add a new pairing, send the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings" \\  --data '{    "data": {        "address": "192.168.0.2",        "certificate\_common\_name": "axis-12345abcd67e-eccp256-1",        "description": "Device in hallway with analytics turned on.",        "nice\_name": "HallwayAnalytics",        "password": "password",        "username": "user"    }}'
```

```bash
POST /config/rest/networkpairing/v1beta/pairingsHost: <servername>Content-Type: application/json{    "data": {        "address": "192.168.0.2",        "certificate\_common\_name": "axis-12345abcd67e-eccp256-1",        "description": "Device in hallway with analytics turned on.",        "nice\_name": "HallwayAnalytics",        "password": "password",        "username": "user"    }}
```

Example response:

```bash
200 OKContent-Type: application/json{    "data": {        "address": "192.168.0.2",        "features": \[            {                "category": "SirenLight",                "capabilities": \[                    {                        "enabled": true,                        "name": "Actions"                    }                \]            }        \],        "certificate\_common\_name": "axis-12345abcd67e-eccp256-1",        "description": "Device in hallway with analytics turned on.",        "id": "1",        "model\_name": "AXIS D4100-E",        "nice\_name": "HallwayAnalytics",        "username": "User",        "connection\_status": "connected"    }}
```

#### Edit a pairing

Existing pairings can be edited by sending a `PATCH` request to a pairing's individual properties.

For example, to update the certificate common name for a pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings/1/certificate\_common\_name" \\  --data '{    "data": "axis-12345abcd67e-rsa2048-1"}'
```

```bash
PATCH /config/rest/networkpairing/v1beta/pairings/1/certificate\_common\_nameHost: <servername>Content-Type: application/json{    "data": "axis-12345abcd67e-rsa2048-1"}
```

Example response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Remove a pairing

Existing pairings can be removed by sending a `DELETE` request to an entry in the collection

For example, to remove the pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings/1"
```

```bash
DELETE /config/rest/networkpairing/v1beta/pairings/1Host: <servername>Content-Type: application/json
```

Example response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### List all pairings

Existing pairings can be listed by sending a `GET` request to the collection

Example request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings"
```

```bash
GET /config/rest/networkpairing/v1beta/pairingsHost: <servername>Content-Type: application/json
```

Example response:

```bash
200 OKContent-Type: application/json{    "data": \[        {            "address": "192.168.0.2",            "features": \[                {                    "category": "SirenLight",                    "capabilities": \[                        {                            "enabled": true,                            "name": "Actions"                        }                    \]                }            \],            "certificate\_common\_name": "axis-12345abcd67e-eccp256-1",            "description": "Device in hallway with analytics turned on.",            "id": "1",            "model\_name": "AXIS D4100-E",            "nice\_name": "HallwayAnalytics",            "username": "User",            "connection\_status": "disconnected"        }    \]}
```

#### Get capabilities provided by a pairing

To list what functionality is provided by a given pairing, send a `GET` request to the pairing's feature collection.

For example, to get the features of a pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings/1/features"
```

```bash
GET /config/rest/networkpairing/v1beta/pairings/1/featuresHost: <servername>Content-Type: application/json
```

Example response:

```bash
200 OKContent-Type: application/json{    "data": \[        {            "category": "SirenLight",            "capabilities": \[                {                    "enabled": true,                    "name": "Actions"                }            \]        }    \]}
```

#### Toggle functionality on existing pairing

When creating a new pairing, all available features will be enabled. To disable or reenable a functionality from a paired device, send a `PATCH` request to the `enabled` property for that capability.

warning

Toggling a feature won't affect the remote device, only whether or not the feature is usable on the host.

For example, to disable the `Actions` capability of the `SirenLight` feature for a pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/pairings/1/features/SirenLight/capabilities/Actions/enabled" \\  --data '{    "data": false}'
```

```bash
PATCH /config/rest/networkpairing/v1beta/pairings/1/features/SirenLight/capabilities/Actions/enabledHost: <servername>Content-Type: application/json{    "data": false}
```

Example response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Siren and Light Plugin

The `siren_light` plugin allows devices to use remote siren units, such as the `AXIS D4100-E`, as receivers for event actions. For example, by triggering a deterring sound and light on the remote device if motion is detected by the host during nighttime.

#### List all available profiles on remote device

A list of profiles that can be stopped or started on a paired device, send a `GET` request to `networkpairing.v1.plugins.siren_light.profiles.{pairingID}`.

For example, to list all profiles for a pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/plugins/siren\_light/profiles/1"
```

```bash
GET /config/rest/networkpairing/v1beta/plugins/siren\_light/profiles/1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "data": {        "names": \[            "Loud noise",            "Police sirens"        \],        "pairing": "1"    }}
```

#### Get capabilities of paired device

The supported capabilities of the remote device can be retrieved by sending a `GET` request to `networkpairing.v1.plugins.siren_light.features.{pairingID}`. The data will contain an array with one or both of "siren" and "light", based on what type of the device the pairing has been made to.

For example, to get the capabilities of a pairing with ID `1`:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/networkpairing/v1beta/plugins/siren\_light/features/1"
```

```bash
GET /config/rest/networkpairing/v1beta/plugins/siren\_light/features/1Host: <servername>Content-Type: application/json
```

Example response:

```bash
200 OKContent-Type: application/json{    "data": {        "supported": \[            "siren",            "light"        \],        "pairing": "1"    }}
```

## API Definition
### Structure

```bash
networkpairing.v1 (Root Entity)
```

#### Entities
#### id

**Description**: Configured pairings

-   **Type**: Collection (Key Property: [id](#id))
-   **Operations**
    -   **Get**
    -   **Add** (**Permissions**: admin)
        -   **Required properties**: address, password, username
        -   **Optional properties**: certificate\_common\_name, description, nice\_name

##### Properties
###### address

-   **Description**: The network address of the remote device. Must be a FQDN DNS name, an IPv4 address (dotted quad notation), or an IPv6 address.
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### certificate\_common\_name

-   **Description**: Remote device server certificate common name.
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
    -   **Set** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### connection\_status

-   **Description**: Connectivity status of the remote device.
-   **Datatype**: [ConnectionStatus](#connection_status)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### description

-   **Description**: Description of the pairing.
-   **Datatype**: [PairingDescription](#description)
-   **Operations**
    -   **Get** (**Permissions:** admin)
    -   **Set** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### id

-   **Description**: The pairing identifier.
-   **Datatype**: [PairingID](#id)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### model\_name

-   **Description**: The detected model name of the remote device
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### nice\_name

-   **Description**: Short, user friendly, name of a pairing.
-   **Datatype**: [PairingNiceName](#nice_name)
-   **Operations**
    -   **Get** (**Permissions:** admin)
    -   **Set** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### password

-   **Description**: The password of the user account on the remote device to use when accessing it.
-   **Datatype**: string
-   **Operations**
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### username

-   **Description**: The name of the user account on the remote device to use when accessing it.
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

###### features

-   **Description**: Available capabilities
-   **Type**: Collection (Key Property: [category](#features))
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### features\_category

-   **Description**: The capability category name
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

###### features\_capabilities

-   **Description**: Available capabilities
-   **Type**: Collection (Key Property: [name](#features_capabilities))
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### enabled

-   **Description**: The capability is administratively enabled
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (**Permissions:** admin)
    -   **Set** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### name

-   **Description**: Name of a pairing capability.
-   **Datatype**: string
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

#### networkpairing.v1.plugins

-   **Description**: Plugins loaded on the device
-   **Type**: Singleton
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### siren\_light\_supported

-   **Description**:
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

###### networkpairing.v1.plugins.siren\_light

-   **Description**: SirenLight plugin
-   **Type**: Singleton
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: Yes

##### Properties

This entity has no properties.

##### Actions

This entity has no actions.

* * *

###### capabilities

-   **Path**: `/networkpairing/v1beta/plugins/siren_light/capabilities`
-   **Description**: Capabilities on remote devices
-   **Type**: Collection (Key Property: [pairing](#capabilities))
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### pairing\_id

-   **Description**: Unique identifier of a pairing.
-   **Datatype**: [PairingID](#pairing_id)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

###### supported

-   **Path**: `/networkpairing/v1beta/plugins/siren_light/capabilities`
-   **Description**: Array containing string representations of capabilities supported by the device
-   **Datatype**: [SLCapabilities](#supported)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

###### profiles

-   **Path**: `/networkpairing/v1beta/plugins/siren_light/profiles`
-   **Description**: The SirenLight profiles available on paired devices
-   **Type**: Collection (Key Property: [pairing](#profiles))
-   **Operations**
    -   **Get**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### names

-   **Description**: Profile names
-   **Datatype**: [SLProfileNames](#names)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### pairing

-   **Description**: The pairing providing the profiles
-   **Datatype**: [PairingID](#pairing)
-   **Operations**
    -   **Get** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

* * *

### Data Types
#### ConnectionStatus

-   **Description**: Status of the connection between the host and remote device.
-   **Datatype**: string
-   **Enum Values**: "connected", "disconnected", "error\_unknown", "error\_authentication", "error\_certificate"

#### PairingDescription

-   **Description**: Description of a network pairing.
-   **Datatype**: string
-   **Maximum Length**: 200

#### PairingID

-   **Description**: Assigned pairing id.
-   **Datatype**: string
-   **Pattern**:`^[1-9][0-9]*$`

#### PairingNiceName

-   **Description**: Short, user friendly, name of a pairing.
-   **Datatype**: string
-   **Maximum Length**: 50

#### SLCapability

-   **Description**: SirenLight capability.
-   **Datatype**: string
-   **Enum Values**: "siren", "light"

#### SLProfileNames

-   **Description**: Profile name.
-   **Datatype**: array
-   **Null Value**: No