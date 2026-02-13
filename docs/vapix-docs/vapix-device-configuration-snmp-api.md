---
title: SNMP Configuration API
url: "https://developer.axis.com/vapix/device-configuration/snmp-api/"
category: vapix
subcategory: device-configuration
sha256: bc8a5d10fa42e1949ca3aeca6113a50d92cda2174cdb0049e1ff2101e643fe2c
scraped_at: "2026-01-09T15:19:01.212Z"
page_height: 15753
---

# SNMP Configuration API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Description

The VAPIX SNMP Configuration API makes it possible to configure the SNMP settings on the device. There are three different versions of SNMP that can be configured. Version 1 and 2 share some settings that are applied to both versions. These settings include configuration of what kind of trap messages to receive.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### General SNMP settings

General settings that affect all the versions of SNMP.

Set the property `snmp.v1.enabled` to `true` to enable SNMP, to `false` to turn it off. By default SNMP is turned off.

Use the property `snmp.v1.transportProtocol` to set what transport protocol SNMP should use. Valid values are `tcp` or `udp`. Default value is `udp`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1" \\  --data '{    "data": {        "enabled": true,        "transportProtocol": "tcp"    }}'
```

```bash
PATCH /config/rest/snmp/v1Host: <servername>Content-Type: application/json{    "data": {        "enabled": true,        "transportProtocol": "tcp"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Get number of times SNMP has started

Use the property `snmp.v1.engineBoots` to get the number of times SNMP has started.

Example:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/engineBoots"
```

```bash
GET /config/rest/snmp/v1/engineBootsHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": 1}
```

### Settings for SNMP V1

SNMP V1 share settings with SNMP V2. See [Common settings for SNMP V1 and V2](#common-settings-for-snmp-v1-and-v2) for more information about the settings.

#### Enable SNMP V1

To enable SNMP V1, set the property `snmp.v1.snmpV1.enabled` to `true`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV1/enabled" \\  --data '{    "data": true}'
```

```bash
PATCH /config/rest/snmp/v1/snmpV1/enabledHost: <servername>Content-Type: application/json{    "data": true}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Settings for SNMP V2

SNMP V2 share settings with SNMP V1. See [Common settings for SNMP V1 and V2](#common-settings-for-snmp-v1-and-v2) for more information about the settings.

#### Enable SNMP V2

To enable SNMP V2, set the property `snmp.v1.snmpV2.enabled` to `true`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV2/enabled" \\  --data '{    "data": true}'
```

```bash
PATCH /config/rest/snmp/v1/snmpV2/enabledHost: <servername>Content-Type: application/json{    "data": true}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Common settings for SNMP V1 and V2

These settings are applied to both SNMP V1 and V2.

#### Set the common SNMP settings

-   To receive trap messages from the device, use `snmp.v1.snmpV1V2Common.address` to set the address of the management server.
-   To set the community name for read operations, modify the property `snmp.v1.snmpV1V2Common.readCommunity`. Default value is `public`.
-   To set the community name for write operations, modify the property `snmp.v1.snmpV1V2Common.writeCommunity`. Default value is `write`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV1V2Common" \\  --data '{    "data": {        "address": "0.0.0.0",        "readCommunity": "string",        "writeCommunity": "string"    }}'
```

```bash
PATCH /config/rest/snmp/v1/snmpV1V2CommonHost: <servername>Content-Type: application/json{    "data": {        "address": "0.0.0.0",        "readCommunity": "string",        "writeCommunity": "string"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Enable trap related settings

-   To enable trap reporting, set the property `snmp.v1.snmpV1V2Common.trap.enabled` to `true`. To turn it off set it to `false`. Default value is `false`.
-   An SNMP community is the group of devices and management station running SNMP. Community names are used to identify groups. Modify the property `snmp.v1.snmpV1V2Common.trap.community` to set the community to use when sending a trap message to the management system.
-   To enable trap messages when authentication fails, set the property `snmp.v1.snmpV1V2Common.trap.authFailEnabled` to `true`. To turn it off set it to `false`. Default value is `false`.
-   To enable trap messages when the device is rebooted or restarted, set the property `snmp.v1.snmpV1V2Common.trap.coldStartEnabled` to `true`. To turn it off set the property to `false`. Default value is `false`.
-   To enable trap messages when a link changes from down to up, set the property `snmp.v1.snmpV1V2Common.trap.linkUpEnabled` to `true`. To turn it off set the property to `false`. Default value is `false`.
-   To enable trap messages when a link changes from up to down, set the property `snmp.v1.snmpV1V2Common.trap.linkDownEnabled` to `true`. To turn it off set the property to `false`. Default value is `false`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV1V2Common/trap" \\  --data '{    "data": {        "authFailEnabled": true,        "coldStartEnabled": true,        "community": "string",        "enabled": true,        "linkUpEnabled": true,        "linkDownEnabled": true    }}'
```

```bash
PATCH /config/rest/snmp/v1/snmpV1V2Common/trapHost: <servername>Content-Type: application/json{    "data": {        "authFailEnabled": true,        "coldStartEnabled": true,        "community": "string",        "enabled": true,        "linkUpEnabled": true,        "linkDownEnabled": true    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Get all common settings for SNMP V1 and V2

Use `snmp.v1.snmpV1V2Common` to get all the common settings for SNMP V1 and V2. The response includes if trap messages are enabled and what kind of trap messages are enabled.

Example:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV1V2Common"
```

```bash
GET /config/rest/snmp/v1/snmpV1V2CommonHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "address": "0.0.0.0",            "readCommunity": "public",            "trap": {                "authFailEnabled": true,                "coldStartEnabled": true,                "community": "public",                "enabled": true,                "linkUpEnabled": true            },            "writeCommunity": "write"        }    \]}
```

### Settings for SNMP V3

-   To enable SNMP V3, set the property `snmp.v1.snmpV3.enabled` to `true`. Set it to `false` to turn it off. Default value is `false`.
-   To enable user password for SNMP V3, set the property `snmp.v1.snmpV3.userPasswd` to `true`.
-   To turn off user password for SNMP V3, set the property `snmp.v1.snmpV3.userPasswdSet` to `false`. Default value is `false`.

Example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/snmp/v1/snmpV3" \\  --data '{    "data": {        "enabled": true,        "userPasswd": "password"    }}'
```

```bash
PATCH /config/rest/snmp/v1/snmpV3Host: <servername>Content-Type: application/json{    "data": {        "enabled": true,        "userPasswd": "password"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## Structure

```bash
snmp.v1 (Root Entity)    ├── enabled    ├── engineBoots    ├── transportProtocol    ├── snmpV1 (Entity)        ├── enabled    ├── snmpV1V2Common (Entity)        ├── address        ├── readCommunity        ├── writeCommunity        ├── trap (Entity)            ├── authFailEnabled            ├── coldStartEnabled            ├── community            ├── enabled            ├── linkDownEnabled            ├── linkUpEnabled    ├── snmpV2 (Entity)        ├── enabled    ├── snmpV3 (Entity)        ├── enabled        ├── userPasswd        ├── userPasswdSet
```

### Entities
#### snmp.v1

-   **Description:** SNMP root entity
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `enabled`, `engineBoots`, `transportProtocol`, `snmpV1V2Common`, `snmpV1`, `snmpV2`, `snmpV3`

#### snmp.v1.snmpV1

-   **Description:** V1 snmp support
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `enabled`

#### snmp.v1.snmpV1V2Common

-   **Description:** Entity that has common properties for snmp V1 and V2c
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `readCommunity`, `writeCommunity`, `address`, `trap`

#### snmp.v1.snmpV1V2Common.trap

-   **Description:** Trap
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `authFailEnabled`, `coldStartEnabled`, `community`, `enabled`, `linkUpEnabled`, `linkDownEnabled`

#### snmp.v1.snmpV2

-   **Description:** V2c snmp support
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set:
        -   Fields: `enabled`

#### snmp.v1.snmpV3

-   **Description:** V3 snmp support
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `enabled`, `userPasswd`, `userPasswdSet`

### Properties
#### snmp.v1.enabled

-   **Description:** Status of snmpd service
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.engineBoots

-   **Description:** Number of times snmpd has been started
-   **Data Type:** `EngineBootsType`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.transportProtocol

-   **Description:** Transport protocol string
-   **Data Type:** `TransportProtocolEnum`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1.enabled

-   **Description:** Status of V1 snmp support
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.address

-   **Description:** Trap address
-   **Data Type:** `TrapAddressType`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.readCommunity

-   **Description:** Read Community string
-   **Data Type:** `CommunityNameType`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.writeCommunity

-   **Description:** Write Community string
-   **Data Type:** `CommunityNameType`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.authFailEnabled

-   **Description:** Status of trap authentication failure
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.coldStartEnabled

-   **Description:** Status of trap coldstart
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.community

-   **Description:** Trap community
-   **Data Type:** `CommunityNameType`
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.enabled

-   **Description:** Status of trap usage
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.linkDownEnabled

-   **Description:** Status of trap link down
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV1V2Common.trap.linkUpEnabled

-   **Description:** Status of trap link up
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV2.enabled

-   **Description:** Status of V2c snmp support
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV3.enabled

-   **Description:** Status of V3 snmp support
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV3.userPasswd

-   **Description:** Initial password
-   **Data Type:** `UserPasswdType`
-   **Operations:**
    -   Set
        -   Permissions: admin

#### snmp.v1.snmpV3.userPasswdSet

-   **Description:** Status of initial password
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: viewer, operator, admin
    -   Set
        -   Permissions: admin

### Data types
#### CommunityNameType

```bash
{    "minLength": 1,    "maxLength": 32,    "type": "string"}
```

#### EngineBootsType

```bash
{    "minimum": 0,    "type": "integer"}
```

#### TransportProtocolEnum

```bash
{    "enum": \["tcp", "udp"\],    "type": "string"}
```

#### TrapAddressType

```bash
{    "maxLength": 46,    "type": "string"}
```

#### UserPasswdType

```bash
{    "minLength": 8,    "maxLength": 50,    "type": "string"}
```