---
title: LLDP Configuration API
url: "https://developer.axis.com/vapix/device-configuration/lldp-configuration-api/"
category: vapix
subcategory: device-configuration
sha256: c9a33165ecbb29e561998c30059ba09c48298b68b4eb24201f3367178d1f7830
scraped_at: "2026-01-09T15:18:48.851Z"
page_height: 10680
---

# LLDP Configuration API

The VAPIX® LLDP Configuration API makes it possible to activate and deactivate LLDP (Link Layer Discovery Protocol) as well as get neighbors information.

info

This API includes operations on sensitive data. You must use a secured channel for the communication transmissions.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Manage LLDP

Activate/deactivate LLDP and retrieve neighbor information.

#### activate/deactivate LLDP

The state of the LLDP can be changed by setting the `lldp.v1.activated` property.

info

IEEE 802.3bt specifications requires that type 4 or higher-powered PoE Powered Device (PD) supports LLDP for Data Link Layer (DLL) classification. Type 2 PDs are required by the IEEE 802.3at specifications to support DLL negotiation. Please observe that 802.1D compliant switches do not forward LLDP packets. Deactivating LLDP will deactivate fabric attach network automation. Deactivating LLDP may cause unexpected behavior. Proceed with caution.

Example

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/lldp/v1/activated" \\  --data '{  "data": true}'
```

```bash
PATCH /config/rest/lldp/v1/activatedHost: <servername>Content-Type: application/json{  "data": true}
```

```bash
200 OKContent-Type: application/json{  "status": "success",  "information": \[    "string"  \],  "warnings": \[    "string"  \]}
```

#### Check if LLDP is active

The state of the LLDP can be checked by getting the `lldp.v1.activated` property.

Example

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/lldp/v1/activated"
```

```bash
GET /config/rest/lldp/v1/activatedHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": true,  "information": \[      "string"  \],  "warnings": \[    "string"  \]}
```

#### Get all neighbors

All neighbor information from all LLDP configured interfaces can be retrieved by getting the `lldp.v1.neighbors` property.

Example

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/lldp/v1/neighbors"
```

```bash
GET /config/rest/lldp/v1/neighborsHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": \[    {      "TTL": 120,      "age": 0,      "chassisID": {        "subType": "MACAddress",        "value": "34:98:b5:ab:5a:b3"      },      "ifName": "eth0",      "mgmtIP": {        "subType": "IPv4",        "value": "192.168.0.115"      },      "portDescr": null,      "portID": {        "subType": "LocallyAssigned",        "value": "g1"      },      "protocol": "LLDP",      "sysDescr": "GS110TPv3 8-Port Gigabit Smart Managed Pro Switch with PoE+ and 2 SFP Ports",      "sysName": null    },    {      "TTL": 120,      "age": 10,      "chassisID": {        "subType": "MACAddress",        "value": "ac:cc:8e:fd:1f:ca"      },      "ifName": "eth1",      "mgmtIP": {        "subType": "IPv4",        "value": "10.10.1.145"      },      "portDescr": "eth0",      "portID": {        "subType": "MACAddress",        "value": "ac:cc:8e:fd:1f:ca"      },      "protocol": "LLDP",      "sysDescr": "AXIS S3008 Recorder 11.10+snapshot-20240202",      "sysName": "ax-accc8efd1fca"    }  \]  "information": \[    "string"  \],  "warnings": \[    "string"  \]}
```

## API definition
### Structure

```bash
lldp.v1 (Root Entity)| - activated (Property)| - neighbors (Property)
```

### Entities

**lldp.v1**

-   **Description:** Main configuration options
-   **Type:** Singleton
-   **Operation:**
    -   `GET`
-   **Attributes:**
    -   _Dynamic support_: No

_Properties_

_activated_

-   **Description:** LLDP state
-   **Datatype:** Boolean
-   **Operations:**
    -   `GET` (Permissions: admin)
    -   `SET` (Permissions: admin)
-   **Attributes:**
    -   _Nullable_: No
    -   _Dynamic Support_: No
    -   _Dynamic Enum_: No
    -   _Dynamic Rang_: No

_neighbors_

-   **Description:** Information about neighbors on the interface
-   **Datatype:** Neighbors
-   **Operations:**
    -   `GET` (Permissions: admin)
-   **Attributes:**
    -   _Nullable_: No
    -   _Dynamic Support_: No
    -   _Dynamic Enum_: No
    -   _Dynamic Rang_: No

_Actions_

This entity has no actions.

### Data types

_ChassisID_

-   **Description:** The chassis ID type
-   **Type:** Complex
-   **Fields:**
    -   **subType**
        -   _Description_: Chassis ID subtype
        -   _Type_: `ChassisIDSubType`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **value**
        -   _Description_: A chassis ID of the type specified by the subType field
        -   _Type_: String
        -   _Nullable_: No
        -   _Gettable_: No

_ChassisIDSubType_

-   **Description:** The type of the identifier used for the chassis.
-   **Type:** String
-   **Enum Values:**
    -   `"ChassisComponent"`
    -   `"InterfaceAlias"`
    -   `"PortComponent"`
    -   `"MACAddress"`
    -   `"NetworkAddress"`
    -   `"InterfaceName"`
    -   `"LocallyAssigned"`

_MgmtIP_

-   **Description:** The chassis ID type
-   **Type:** Complex
-   **Fields:**
    -   **subType**
        -   _Description_: Management IP address subtype
        -   _Type_: `MgmtIPSubType`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **value**
        -   _Description_: A management IP address of the type specified by the subType field
        -   _Type_: String
        -   _Nullable_: No
        -   _Gettable_: No

_MgmtIPSubType_

-   **Description:** The type of the address used for the management IP
-   **Type:** String
-   **Enum Values:**
    -   `"IPv4"`
    -   `"IPv6"`

_Neighbor_

-   **Description:** Neighbor information
-   **Type:** Complex
-   **Fields:**
    -   **TTL**
        -   _Description_: Time To Live
        -   _Type_: `PositiveInt`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **age**
        -   _Description_: Age of the neighbor information in seconds from epoch
        -   _Type_: `PositiveInt`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **chassisID**
        -   _Description_: The chassis ID of the neighbor
        -   _Type_: `ChassisID`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **ifName**
        -   _Description_: Name of the interface from which the information is received
        -   _Type_: String
        -   _Nullable_: No
        -   _Gettable_: No
    -   **mgmtIP**
        -   _Description_: Management IP of the neighbor
        -   _Type_: `MgmtIP`
        -   _Nullable_: Yes
        -   _Gettable_: No
    -   **portDescr**
        -   _Description_: Port description of the neighbor
        -   _Type_: String
        -   _Nullable_: Yes
        -   _Gettable_: No
    -   **portID**
        -   _Description_: Port ID of the neighbor
        -   _Type_: `PortID`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **protocol**
        -   _Description_: The protocol used
        -   _Type_: `Protocol`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **sysDescr**
        -   _Description_: System description of the neighbor
        -   _Type_: String
        -   _Nullable_: Yes
        -   _Gettable_: No
    -   **sysName**
        -   _Description_: System hostname of the neighbor
        -   _Type_: String
        -   _Nullable_: Yes
        -   _Gettable_: No

_Neighbors_

-   **Description:** A list of neighbor information
-   **Type:** Array
-   **Element type:** `Neighbor`
-   **Null Value:** No

_PortID_

-   **Description:** The port ID type
-   **Type:** Complex
-   **Fields:**
    -   **subType**
        -   _Description_: Port ID subtype
        -   _Type_: `PortIDSubType`
        -   _Nullable_: No
        -   _Gettable_: No
    -   **value**
        -   _Description_: A port ID of the type specified by the subType field
        -   _Type_: String
        -   _Nullable_: No
        -   _Gettable_: No

_PortIDSubType_

-   **Description:** The type of the identifier used for the port
-   **Type:** String
-   **Enum Values:**
    -   `"InterfaceAlias"`
    -   `"PortComponent"`
    -   `"MACAddress"`
    -   `"NetworkAddress"`
    -   `"InterfaceName"`
    -   `"AgentCircuitID"`
    -   `"LocallyAssigned"`

_PositiveInt_

-   **Description:** Positive integer type
-   **Type:** Integer
-   **Minimum Value:** 0

_Protocol_

-   **Description:** The type of the identifier used for the chassis
-   **Type:** String
-   **Enum Values:**
    -   `"LLDP"`
    -   `"CDPv1"`
    -   `"CDPv2"`