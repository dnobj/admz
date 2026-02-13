---
title: Time API
url: "https://developer.axis.com/vapix/device-configuration/time-api/"
category: vapix
subcategory: device-configuration
sha256: abe7a1156f3f392e00d74ab4473a553d84a848a44854519b2e79904d2ebdbd9b
scraped_at: "2026-01-09T15:19:07.357Z"
page_height: 15512
---

# Time API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

The VAPIX® Time API enables the configuration and management of time, date and time zone information on your Axis device. There currently exist two different time zone formats:

-   The Time Zone Database is provided by IANA (_Internet Assigned Numbers Authority_) and offers an easy way to set the time zone. An example of such a time zone format is `Europe/Stockholm` and once the time zone is selected the daylight saving rules will be applied for that time zone, as the database is updated to reflect changes in the time zones. Thus, an updated version of the database will be included through the AXIS OS upgrades and be applied without the need to change the time zone setting.
-   The POSIX format (_Portable Operating System Interface_). Example of such a time zone format is `CET-1CEST,M3.5.0,M10.5.0/3`.

It supports the setting of IANA, POSIX, and DHCP time zone, which are all mutually exclusive with each other (DHCP time zone through the `dhcp.enabled` property). Which time zone the device currently uses can be checked with the [Active time zone](#activetimezone) property (see [Use Cases](#use-cases)).

## Obsoletes

This API deprecates the following methods:

-   `/axis-cgi/time.cgi`: This method, found in the [Time API](/vapix/network-video/time-api/), is fully replaced in favor of this API.
-   `Time.POSIXTimeZone` and `Time.DST.Enabled`: These can be accessed through the legacy `/axis-cgi/param.cgi`, but are also available through this API. Note that these parameters will be removed in AXIS OS version 13.0 and no longer be usable after that.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases

The most common use cases are listed below. Retrieving specific properties are done by requesting the path to that property. Use [Get all settings](#get-all-settings) to get a list of all retrievable properties.

### Get all settings

Get all available settings by retrieving the endpoint `time.v2`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2"
```

```bash
GET /config/rest/time/v2Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "time": {            "dateTime": "2024-07-04T15:16:05Z",            "localDateTime": "2024-07-04T17:16:05+02:00",            "maxSupportedYear": 2069        },        "timeZone": {            "activeTimeZone": "Europe/Stockholm",            "dhcp": {                "enabled": false,                "timeZone": null            },            "iana": {                "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",                "timeZone": "Europe/Stockholm"            },            "posix": {                "dstEnabled": true,                "timeZone": null            }        }    }}
```

### Get all time settings

Get time settings by retrieving the `time` endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/time"
```

```bash
GET /config/rest/time/v2/timeHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "time": {            "dateTime": "2024-07-04T15:16:05Z",            "localDateTime": "2024-07-04T17:16:05+02:00",            "maxSupportedYear": 2069        }    }}
```

### Get all time zone settings

Get time zone settings by retrieving the `timeZone` endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone"
```

```bash
GET /config/rest/time/v2/timeZoneHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "timeZone": {            "activeTimeZone": "Europe/Stockholm",            "dhcp": {                "enabled": false,                "timeZone": null            },            "iana": {                "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",                "timeZone": "Europe/Stockholm"            },            "posix": {                "dstEnabled": true,                "timeZone": null            }        }    }}
```

### Get the active time zone

Check the current time zone by retrieving the `timeZone.activeTimeZone`. The retrieved time zone can either be in IANA or POSIX format.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone/activeTimeZone"
```

```bash
GET /config/rest/time/v2/timeZone/activeTimeZoneHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": "Europe/Copenhagen"}
```

### Set time and date

Set time and date via the `time.dateTime` endpoint. The field is represented in UTC in the ISO 8601 format.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/time/dateTime" \\  --data '{    "data": "1995-11-07T12:00:00Z"}'
```

```bash
PATCH /config/rest/time/v2/time/dateTimeHost: <servername>Content-Type: application/json{    "data": "1995-11-07T12:00:00Z"}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Set the DHCP time zone

Use the DHCP provided time zone by setting the `timeZone.dhcp.enabled` property to `true`. This operation sets `timeZone.iana.timeZone` and `timeZone.posix.timeZone` to `null`, and `timeZone.activeTimeZone` to the DHCP time zone, `timeZone.dhcp.timeZone`, supplied from the network if given, else the factory default time zone. Enabling this property works as a reset for the time zone properties, since this is the factory default state.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone/dhcp/enabled" \\  --data '{    "data": true}'
```

```bash
PATCH /config/rest/time/v2/timeZone/dhcp/enabledHost: <servername>Content-Type: application/json{    "data": true}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Set the IANA time zone

Set an IANA time zone. A list of possible IANA time zone values are retrieved with the action `timeZone.iana.getTimeZoneList`, which will return a list of time zone objects.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone/iana/getTimeZoneList" \\  --data '{    "data": {}}'
```

```bash
POST /config/rest/time/v2/timeZone/iana/getTimeZoneListHost: <servername>Content-Type: application/json{    "data": {}}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "timeZone": "Europe/Copenhagen"        },        {            "timeZone": "Europe/Prague"        },        {            "timeZone": "..."        }    \]}
```

Set the IANA time zone by calling:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone/iana/timeZone" \\  --data '{    "data": "Europe/Copenhagen"}'
```

```bash
PATCH /config/rest/time/v2/timeZone/iana/timeZoneHost: <servername>Content-Type: application/json{    "data": "Europe/Copenhagen"}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

Successfully assigning an IANA time zone will also set `timeZone.posix.timeZone` to `null` and `timeZone.dhcp.enabled` to `false`. Thus, the `timeZone.activeTimeZone` property will reflect the `timeZone.iana.timeZone` property.

### Set the POSIX time zone

Set the POSIX time zone with the `timeZone.posix.timeZone` property. The time zone can be set together with the `timeZone.posix.dstEnabled` flag to toggle whether the daylight savings time should be enabled or not. Successfully assigning a POSIX time zone will also set `timeZone.iana.timeZone` to `null` and `timeZone.dhcp.enabled` to `false`. Thus, the `timeZone.activeTimeZone` property will reflect the `timeZone.posix.timeZone` property.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/time/v2/timeZone/posix" \\  --data '{    "data": {        "timeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": false    }}'
```

```bash
PATCH /config/rest/time/v2/timeZone/posixHost: <servername>Content-Type: application/json{    "data": {        "timeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": false    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
time.v2 (Root Entity)    ├── time (Entity)        ├── dateTime (Property)        ├── localDateTime (Property)        ├── maxSupportedYear (Property)    ├── timeZone (Entity)        ├── activeTimeZone (Property)        ├── dhcp (Entity)            ├── enabled (Property)            ├── timeZone (Property)        ├── iana (Entity)            ├── posixTimeZone (Property)            ├── timeZone (Property)            ├── getTimeZoneList (Action)        ├── posix (Entity)            ├── dstEnabled (Property)            ├── timeZone (Property)
```

### Entities
#### time.v2

-   **Description**: The Time API root object.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties

This entity has no properties

##### Actions

This entity has no actions.

#### time.v2.time

-   **Description**: Handle date and time configuration.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

This it the entity that handles everything pertaining to date and time management.

##### Properties
###### dateTime

-   **Description**: The system date and time in UTC. The format is in ISO 8601. The date should be between Unix time (`UTC 1970-01-01T00:00:00`) and the last second of the year declared in `maxSupportedYear`.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### localDateTime

-   **Description**: The local date and time. The format is in ISO 8601.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### maxSupportedYear

-   **Description**: Latest year that the date can be set to.
-   **Datatype**: `integer`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### time.v2.timeZone

-   **Description**: Handle all settings related to time zones.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

This is the entity that handles everything pertaining to time zone management.

##### Properties
###### activeTimeZone

-   **Description**: The currently active system time zone. Will be either the IANA or POSIX time zone if they have been manually set. If `dhcp.enabled` is set to true it will be the DHCP time zone if it was available from the network, otherwise the factory default time zone will be used.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### time.v2.timeZone.dhcp

-   **Description**: Handle DHCP time zone configuration.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### enabled

-   **Description**: Flag which enables the device to use DHCP time zone from the network. Default value is true. Setting this property to true will reset the device's time zone to use the DHCP time zone, but only if the network is able to supply it. Otherwise, the factory default time zone will be used.' This property is mutually exclusive with `iana.timeZone` and `posix.timeZone`. Can only be set to `false` together with a valid `iana.timeZone` or `posix.timeZone`.
-   **Datatype**: `boolean`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### timeZone

-   **Description**: The DHCP time zone supplied by the network. Can be in either the IANA or POSIX format. Is set to `null` if the DHCP time zone isn't available.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
-   **Attributes**
    -   **Nullable**: Yes
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### time.v2.timeZone.iana

-   **Description**: Handle IANA time zone configuration.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### posixTimeZone

-   **Description**: The time zone in POSIX format corresponding to the time of the last transition.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
-   **Attributes**
    -   **Nullable**: Yes
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### timeZone

-   **Description**: The system time zone in the IANA format. Example `Europe/Prague`. If set to a valid value, `dhcp.enabled` will be set to `false` and `posix.timeZone` will be set to `null`.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: Yes
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions
###### getTimeZoneList

-   **Description**: List of all time zones on the device
-   **Request Datatype**: Empty Object
-   **Response Datatype**: `datatypes.TimeZonesArray`
-   **Trigger Permissions**: `operator`

#### time.v2.timeZone.posix

-   **Description**: Handle POSIX time zone configuration.
-   **Type**: `Singleton`
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: `dstEnabled`, `timeZone`
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### dstEnabled

-   **Description**: The DST flag for controlling the POSIX time zone string. `true` means it will activate the DST settings of the POSIX time zone string. `false` means it will ignore the DST settings of the POSIX time zone string. During import the `dstEnabled` is only updated together with a valid `posix.timeZone`.
-   **Datatype**: `boolean`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### timeZone

-   **Description**: The system time zone in the POSIX format. Example `EST5EDT,M3.2.0,M11.1.0`. If set to a valid value, `dhcp.enabled` will be set to `false` and `iana.timeZone` will be set to `null`.
-   **Datatype**: `string`
-   **Operations**
    -   **`GET`** (**Permissions:** viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: Yes
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

### Data types
#### TimeZoneEntry

-   **Description**: An object containing time zone information.
-   **Type**: `complex`
-   **Fields**
    -   **timeZone**
        -   **Description**: The time zone string.
        -   **Type**: `string`
        -   **Nullable**: No / **Gettable**: No

#### TimeZonesArray

-   **Description**: An array containing objects of time zone entries.
-   **Type**: `array`
-   **Element type**: `TimeZoneEntry`
-   **Null Value**: No