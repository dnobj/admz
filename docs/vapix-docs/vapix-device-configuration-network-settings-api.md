---
title: Network settings API
url: "https://developer.axis.com/vapix/device-configuration/network-settings-api/"
category: vapix
subcategory: device-configuration
sha256: 71259c11b11193ce9c2a4887e780b73b0826f316f2da2c265541c2054ea82f36
scraped_at: "2026-01-09T15:18:53.861Z"
page_height: 9324
---

# Network settings API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Description

The Network settings API makes it possible to configure the network settings on the device.

info

This API includes operations on sensitive data. You must use a secured channel for the communication transmissions.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Manage switch settings

Some devices have built-in switches that allow additional products to be connected for network connectivity. Switch support is dynamic and not always available. Use [`switch_supported`](#switch_supported) to check switch support on the device.

#### Get switch configuration

The switch entity [network-settings.v2.switch](#network-settingsv2switch) will return the current switch configuration if [`switch_supported`](#switch_supported) is `true`, otherwise not available.

```bash
{    "request": {        "operation": "GET",        "path": "network-settings.v2.switch"    },    "response": {        "status": "success",        "data": \[            {               "port": \[                    {                        "lowerState": "UP",                        "portId": "1",                        "remoteAddresses": \[                            "55:72:97:5a:c7:cf"                        \],                        "security\_supported": false,                        "enabled": true,                        "security": {                            "macSecState": "SECURED",                            "authServerEnabled": true,                            "authServerEnforced": "MACSEC\_SECURED",                            "authState": "AUTHENTICATED"                        }                    },                    {                        "lowerState": "DOWN",                        "portId": "2",                        "remoteAddresses": \[\],                        "security\_supported": true,                        "enabled": true,                        "security": {                            "macSecState": "UNKNOWN",                            "authServerEnabled": true,                            "authServerEnforced": "AUTHENTICATED",                            "authState": "UNKNOWN"                        }                    }                \]            }        \]    }}
```

#### Get switch port settings

Retrieve individual port settings from the collection of switch ports with [`portId`](#portid).

The switch port `security` settings are dynamically supported. Check [`security_supported`](#security_supported) for availability. [`security`](#network-settingsv2switchportsecurity) will be excluded if it is not supported.

```bash
{    "request": {        "operation": "GET",        "path": "network-settings.v2.switch.port\['1'\]"    },    "response": {        "status": "success",        "data": {                    "lowerState": "UP",                    "portId": "1",                    "remoteAddresses": \[                        "55:72:97:5a:c7:cf"                    \],                    "security\_supported": true,                    "enabled": true,                    "security": {                        "macSecState": "SECURED",                        "authServerEnabled": true,                        "authServerEnforced": "MACSEC\_SECURED",                        "authState": "AUTHENTICATED"                    }                }    }}
```

#### Set switch port settings

Set [`portId`](#portid) to configure individual port settings on the collection of switch ports.

-   To enable a port, set [`enabled`](#enabled) to `true`, which is the default value.
-   To disable a port, set [`enabled`](#enabled) to `false`.

The switch port `security` settings are dynamically supported. Check [`security_supported`](#security_supported) for availability. You can't set [`security`](#network-settingsv2switchportsecurity) if security settings are not supported.

```bash
{    "request": {        "operation": "SET",        "path": "network-settings.v2.switch.port\['1'\]",        "data": {            "enabled": true,            "security": {                "authServerEnabled": false,                "authServerEnforced": "NONE"            }        }    },    "response": {        "status": "success"    }}
```

## API definition
### Structure

```bash
network-settings.v2 (Root Entity)    ├── switch\_supported (Property)    ├── switch (Entity)        ├── port (Entity Collection)            ├── enabled (Property)            ├── lowerState (Property)            ├── portId (Property)            ├── remoteAddresses (Property)            ├── security\_supported (Property)            ├── security (Entity)                ├── authServerEnabled (Property)                ├── authServerEnforced (Property)                ├── authState (Property)                ├── macSecState (Property)
```

### Entities
#### network-settings.v2

-   **Description**: System wide network configurations
-   **Type**: Singleton
-   **Operations**
    -   Get
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### switch\_supported

-   **Description**: Indicates if switch is supported.
-   **Datatype**: boolean
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

#### network-settings.v2.switch

-   **Description**: Global switch configurations
-   **Type**: Singleton
-   **Operations**
    -   Get
-   **Attributes**
    -   **Dynamic Support**: Yes

#### network-settings.v2.switch.port

-   **Description**: Switch port configurations
-   **Type**: Collection (Key Property: [portId](#portid))
-   **Operations**
    -   Get
    -   Set
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### enabled

-   **Description**: Specifies if a network interface device is enabled.
-   **Datatype**: boolean
-   **Operations**
    -   Get
    -   Set (Permissions: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### lowerState

-   **Description**: Indicates if the network interface device status is UP or DOWN.
-   **Datatype**: [State](#state)
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### portId

-   **Description**: Switch port ID
-   **Datatype**: string
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### remoteAddresses

-   **Description**: List all stored remote MAC addresses observed on the switch port.
-   **Datatype**: [RemoteAddresses](#remoteaddresses)
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### security\_supported

-   **Description**: Indicates if security is supported.
-   **Datatype**: boolean
-   **Operations**
    -   Get
    -   Set (Permissions: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

#### network-settings.v2.switch.port.security

-   **Description**: Switch port security configurations
-   **Type**: Singleton
-   **Operations**
    -   Get
    -   Set
-   **Attributes**
    -   **Dynamic Support**: Yes

##### Properties
###### authServerEnabled

-   **Description**: Indicates if the authentication server is enabled.
-   **Datatype**: boolean
-   **Operations**
    -   Get
    -   Set (Permissions: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### authServerEnforced

-   **Description**: Indicates if the authentication server is enforced
-   **Datatype**: [AuthServerEnforced](#authserverenforced)
-   **Operations**
    -   Get
    -   Set (Permissions: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### authState

-   **Description**: Indicates the authentication state of the port
-   **Datatype**: [AuthState](#authstate)
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### macSecState

-   **Description**: Indicates the MACSec state of the port
-   **Datatype**: [MacSecState](#macsecstate)
-   **Operations**
    -   Get
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

### Data types
#### AuthServerEnforced

-   **Description**: Authentication server enforcement level
-   **Type**: string
-   **Enum Values**: `NONE`, `AUTHENTICATED`, `MACSEC_SECURED`

#### AuthState

-   **Description**: Authentication state type
-   **Type**: string
-   **Enum Values**: `UNKNOWN`, `AUTHENTICATED`, `AUTHENTICATING`, `STOPPED`, `FAILED`

#### MacAddress

-   **Description**: MAC address type
-   **Type**: string
-   **Pattern**: ^(\[0-9A-Fa-f\]{2}\[:\]){5}(\[0-9A-Fa-f\]{2})$

#### MacSecState

-   **Description**: MACsec state type
-   **Type**: string
-   **Enum Values**: `UNKNOWN`, `SECURED`, `CONNECTING`, `STOPPED`, `FAILED`

#### RemoteAddresses

-   **Description**: Remote addresses type
-   **Type**: array
-   **Element type**: [MacAddress](#macaddress)
-   **Null Value**: No

#### State

-   **Description**: Link state type
-   **Type**: string
-   **Enum Values**: `UP`, `DOWN`