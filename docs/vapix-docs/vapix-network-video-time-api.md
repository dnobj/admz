---
title: Time API
url: "https://developer.axis.com/vapix/network-video/time-api/"
category: vapix
subcategory: network-video
sha256: 30db01da146ea1b34286c7aa2f971fb531bbeb3ec1b8bdc88cf2edff46cb37e3
scraped_at: "2026-01-09T15:21:20.731Z"
page_height: 30760
---

# Time API

info

This API will be deprecated as of AXIS OS version 12.4 and will no longer receive updates. It is replaced by the Device Configuration [Time API](/vapix/device-configuration/time-api/).

The Time API makes it possible to get and set time, date and time zone information. There currently exist two different time zone formats:

-   The Time Zone Database is provided by IANA (_Internet Assigned Numbers Authority_) and offers an easy way to set the time zone. An example of such a time zone format is `Europe/Stockholm` and once the time zone is selected the daylight saving rules will be applied for that time zone, as the database is updated to reflect changes in the time zones. Thus, an updated version of the database will be included through the AXIS OS upgrades and be applied without the need to change the time zone setting.
-   The POSIX format (_Portable Operating System Interface_). Example of such a time zone format is `CET-1CEST,M3.5.0,M10.5.0/3`.

The API uses the `/axis-cgi/time.cgi` and consists of the following methods:

| Methods | Description |
| --- | --- |
| `getDateTimeInfo` | Get system date, time, time zone and local time. See [Retrieve Date and Time information](#retrieve-date-and-time-information) for additional information. |
| `getAll` | Get all properties returned from `getDateTimeInfo` plus a list of available time zones in the IANA format. |
| `setDateTime` | Set system date and time UTC. See [Set Date and Time](#set-date-and-time) for additional information. |
| `setTimeZone` | Set system time zone in the IANA format. |
| `setPosixTimeZone` | Set system time zone in the POSIX format and the DST flag. |
| `resetTimeZone` | Manually reset the set time zones back to the device default value. DHCP time zone will be used by default when available. |
| `getSupportedVersions` | Get API versions supported by the product. |

## Overview

The API consists of an authenticated CGI which should be called using the HTTP POST method, and with JSON formatted data as input. The API includes a number of methods, which makes it possible to:

-   get and set the date and time.
-   get the local date and time.
-   get and set the time zone.
-   reset time zone to default.
-   list available time zones.

The available time zones are the ones provided by IANA, and are usually referred to as _tz_ or _zoneinfo_. They are periodically updated to reflect changes made by political bodies, UTC offsets and daylight-saving rules.

**DHCP time zone**

The DHCP time zone will be used by default when available and if no manual configuration of the time zone has been done. DHCP time zone will not be used even if it’s available on the network once a time zone has been manually configured. The time zone needs to be reset to re-enable the DHCP time zone. The following priority order is considered for the time zone:

-   1.  Manually set time zone
-   2.  DHCP time zone (if available)
-   3.  Default time zone

Once DHCP time zone is utilized, it will be kept until either a new DHCP time zone is received through the network or a manual time zone is configured. If the DHCP lease is expired and no time zone information is received anymore, the previously obtained DHCP time zone will be kept.

### Identification

-   **API Discovery**: `id=time-service`
-   **AXIS OS**: 9.30 and later

For information about the API Discovery, see [API Discovery service](/vapix/network-video/api-discovery-service/).

### Obsoletes

This API deprecates the following methods:

-   `date.cgi`: This method was removed in AXIS OS version 11.0.
-   `Time.POSIXTimeZone` and `Time.DST.Enabled`: Both of these methods are fully supported by the Time API, but can also be accessed through the legacy `/axis-cgi/param.cgi`. Note that these parameters will be removed in AXIS OS version 13.0 and no longer be usable after that.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

All requests made to Time API is done through a HTTP request with a proper JSON body, while all the responses to the API calls will be returned as JSON data.

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json
```

### Retrieve information

Use this example to receive the current time, date and time zone information on the device, the latter whom also includes a list of supported time zones in different formats, which is dependent on whether:

-   if the time zone has been set with the IANA format, the `get` operation will include the IANA format, but it can also include the POSIX format if it is available in the IANA Time Zone Database.
-   if the time zone has been set with the POSIX format, the `get` operation will only include the POSIX format.

The `dstEnabled` will be available in the response if a POSIX format string is returned.

#### Retrieve Date and Time information

1.  Request current date and time information with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getDateTimeInfo"}
```

2.  There are six possible JSON responses, where the time zone information may differ. Please note that not all of the different JSON responses will be shown below. Possible names for the `data` responses are listed in the table below.

a) Parse the JSON response, which only includes time zone information in an IANA format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getDateTimeInfo",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm"    }}
```

b) Parse the JSON response, which will include only time zone information in the POSIX format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getDateTimeInfo",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true    }}
```

c) Parse the JSON response, which will include time zone information in both the IANA and POSIX format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getDateTimeInfo",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm",        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true    }}
```

d) Parse the JSON response, which will include the time zone information in both IANA and POSIX, as well as the time zone retrieved via DHCP and an indicator if the DHCP time is utilized.

```bash
{    "apiVersion": "1.1",    "context": "Client defined request ID",    "method": "getDateTimeInfo",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm",        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true,        "dhcpTimeZone": "Europe/Berlin",        "dhcpTimeZoneUtilized": false    }}
```

| Parameter | Description |
| --- | --- |
| `dateTime` | System date and time presented in UTC. The format is in ISO 8601. |
| `localDateTime` | Local date and time. The format is ISO 8601. |
| `maxYearSupported` | The latest year that the date can be set to. |
| `timeZone` | System time zone in the IANA format. |
| `posixTimeZone` | System time zone in the POSIX format. |
| `dstEnabled` | `true` means that it will activate the DST settings of the POSIX time zone string. `false` means that it will ignore the DST settings of the POSIX time zone string. Always `true` if the IANA time zone format is present. Omitted if POSIX time zones aren’t available. |
| `dhcpTimeZone` | Time zone retrieved through DHCP, in either the IANA or POSIX format. This is omitted if DHCP time zone isn’t available. Introduced in API version 1.1. |
| `dhcpTimeZoneUtilized` | `true` means that the DHCP time zone is used by the system. `false` means that the DHCP is not used. Omitted if DHCP time zone isn’t available. Introduced in API version 1.1. |

#### Retrieve Date and Time Information and List of Available Time Zones

1.  Request current date and time information and list of available time zones with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAll"}
```

2.  There are six possible JSON responses, where the time zone information may differ. Please note that not all of the different JSON responses will be shown below. The names that can be included in the response `data` are listed in the table below.

a) Parse the JSON response which includes only time zone information in the IANA format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAll",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm",        "timeZones": \["Africa/Abidjan", "Africa/Accra"\]    }}
```

b) Parse the JSON response which includes only time zone information in the POSIX format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAll",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true,        "timeZones": \["Africa/Abidjan", "Africa/Accra"\]    }}
```

c) Parse the JSON response which includes time zone information in both IANA and POSIX format.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAll",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm",        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true,        "timeZones": \["Africa/Abidjan", "Africa/Accra"\]    }}
```

d) Parse the JSON response, which will include the time zone information in both IANA and POSIX, as well as the time zone retrieved via DHCP and an indicator if the DHCP time is utilized.

```bash
{    "apiVersion": "1.1",    "context": "Client defined request ID",    "method": "getAll",    "data": {        "dateTime": "2018-11-19T13:26:53Z",        "localDateTime": "2018-11-19T14:26:53+01:00",        "maxYearSupported": 2069,        "timeZone": "Europe/Stockholm",        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true,        "dhcpTimeZone": "Europe/Berlin",        "dhcpTimeZoneUtilized": false,        "timeZones": \["Africa/Abidjan", "Africa/Accra"\]    }}
```

| Parameter | Description |
| --- | --- |
| `dateTime` | System date and time presented in UTC. The format is in ISO 8601. |
| `localDateTime` | Local date and time. The format is ISO 8601. |
| `maxYearSupported` | The latest year that the date can be set to. |
| `timeZone` | System time zone in the IANA format. |
| `posixTimeZone` | System time zone in the POSIX format. |
| `dstEnabled` | `true` means that it will activate the DST settings of the POSIX time zone string. `false` means that it will ignore the DST settings of the POSIX time zone string. Always `true` if the IANA time zone format is present. Omitted if POSIX time zones aren’t available. |
| `dhcpTimeZone` | Time zone retrieved through DHCP, in either the IANA or POSIX format. This is omitted if DHCP time zone isn’t available. Introduced in API version 1.1. |
| `dhcpTimeZoneUtilized` | `true` means that the DHCP time zone is used by the system. `false` means that the DHCP is not used. Omitted if DHCP time zone isn’t available. Introduced in API version 1.1. |
| `timeZones` | List supported time zones in the IANA format. |

### Set properties

Use this example to set the time, date and time zone on the device.

#### Set Date and Time

1.  Request set date and time with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setDateTime",    "params": {        "dateTime": "2018-12-24T14:28:53Z"    }}
```

2.  Parse the JSON response which echoes the value of `params` object in the `data` object if successful.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setDateTime",    "data": {        "dateTime": "2018-12-24T14:28:53Z"    }}
```

Please note that the `dateTime` parameter is in the UTC format, which should be formatted as `[YYYY]-[MM]-[DD]T[hh]:[mm]:[ss]Z`.

#### Set Time Zone

`setTimeZone` is the preferred way of setting the time zone on the device.

See [setTimeZone](#settimezone) for additional information. The `setTimeZone` will turn off use of DHCP time zone.

1.  Request set time zone with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setTimeZone",    "params": {        "timeZone": "Europe/Stockholm"    }}
```

2.  Parse the JSON response which echoes the value of `params` object in the `data` object if successful.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setTimeZone",    "data": {        "timeZone": "Europe/Stockholm"    }}
```

info

Please note that this request will set a new IANA time zone and clear any previous POSIX time zone. The POSIX string in the Time Zone Database will not be affected.

#### Set POSIX Time Zone

Be aware that `setPosixTimeZone` is not the recommended way when setting the time zone. Instead, use the preferred method `setTimeZone` in the [Set Time Zone](#set-time-zone) section. The `setPosizTimeZone` parameter will turn off the use of DHCP time zones.

1.  Request set POSIX time zone with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPosixTimeZone",    "params": {        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "enableDst": true    }}
```

2.  Parse the JSON response, which echoes the value of `params` object in the `data` object if successful.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPosixTimeZone",    "data": {        "posixTimeZone": "CET-1CEST,M3.5.0,M10.5.0/3",        "dstEnabled": true    }}
```

info

Please note that this request will set a new POSIX time zone and clear any previous IANA time zones.

#### Reset time zone

Reset the time zone to device default. The device will use DHCP time zones if it is available.

1.  Request set POSIX time zone with the following JSON request.

```bash
{    "apiVersion": "1.1",    "context": "Client defined request ID",    "method": "resetTimeZone"}
```

2.  Parse the JSON response status in the `data` object if successful.

```bash
{    "apiVersion": "1.1",    "context": "Client defined request ID",    "method": "resetTimeZone",    "data": {        "status": "success"    }}
```

info

Please note that this request will clear any previous IANA and POSIX time zones.

## API specification
### getDateTimeInfo

Use `getDateTimeInfo` to retrieve all the date and time related properties provided by the Time API.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getDateTimeInfo"}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getDateTimeInfo"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that should be used. |
| `context=<ID string>` | _Optional_. The client sets this value, while the server echoes the date back in the response. If set, it will be present in the response regardless of whether the response was successful or not. |
| `method=getDateTimeInfo` | _Required_. Specifies that the `getDateTimeInfo` operation is performed. |

**Return value - Success**

A successful response may contain time zone information in one of the following formats:

-   **IANA**: The get operation will include this format, however, it can also come with the POSIX format as long as it is available in the IANA Time Zone Database.
-   **POSIX**: The get operation will include this format.

Additionally, DHCP time zone information may be included in the successful responses if the DHCP time zone is obtained from the network.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "getDateTimeInfo",  "data": {    "dateTime": "<date and time>",    "maxYearSupported": <Max supported year integer>,    "localDateTime": "<local date and time>",    "timeZone": "<IANA time zone id>"    "posixTimeZone": <POSIX time zone string>,    "dstEnabled": <DST flag>,    "dhcpTimeZone": "<IANA time zone id or POSIX time zone string>",    "dhcpTimeZoneUtilized": <DHCP utilization flag>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.dateTime` | The system date and time in UTC, presented in the ISO 8601 format. |
| `data.maxYearSupported` | The latest year that the date can be set to. |
| `data.localDateTime` | The local date and time in the ISO 8601 format. |
| `data.timeZone` | The system time zone in IANA format, for example `Europe/Stockholm`. Omitted if the IANA time zone isn’t available. |
| `data.posixTimeZone` | The system time zone in the POSIX format, for example `EST5EDT,M3.2.0,M11.1.0`. Omitted if the POSIX time zone isn’t available. |
| `data.dstEnabled` | The DST flag for controlling the POSIX time zone string: Always `true` if the IANA time zone format is present. Omitted if the POSIX time zone isn’t available. `true` means it will activate the DST settings of the POSIX time zone string. `false` means it will ignore the DST settings of the POSIX time zone string. |
| `data.dhcpTimeZone` | The DHCP time zone that can be in either the IANA or POSIX format. Omitted if the DHCP time zone isn’t available. Introduced in API version 1.1. |
| `data.dhcpTimeZoneUtilized` | The DHCP time zone utilization flag. It will indicate if the DHCP time zone is used by the system. Omitted if DHCP time zone isn’t available. Introduced in API version 1.1. `true` means that DHCP time zone is used by the system. `false` means that DHCP time zone is not used by the system. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### getAll

Use `getAll` to retrieve all date and time related properties provided by the Time API, including a list of supported time zones.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getAll"}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getAll"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that is used. |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method=getAll` | _Required_. Specifies that the `getAll` operation is performed. |

**Return value - Success**

A successful response may contain time zone information in one of the following formats:

-   **IANA**: The get operation will include this format, however, it can also come with the POSIX format as long as it is available in the IANA Time Zone Database.
-   **POSIX**: The get operation will include this format.

Additionally, DHCP time zone information may be included in the successful responses if the DHCP time zone is obtained from the network.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "getAll",  "data": {    "dateTime": "<date and time>",    "maxYearSupported": <Max supported year integer>,    "localDateTime": "<local date and time>",    "timeZone": "<IANA time zone id>"    "posixTimeZone": <POSIX time zone string>,    "dstEnabled": <DST flag>,    "dhcpTimeZone": "<IANA time zone id or POSIX time zone string>",    "dhcpTimeZoneUtilized": <DHCP utilization flag>,    "timeZones": \["<IANA time zone id1>", "<IANA time zone id2>", ...\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.dateTime` | The system date and time in UTC, presented in the ISO 8601 format. |
| `data.maxYearSupported` | The latest year that the date can be set to. |
| `data.localDateTime` | The local date and time in the ISO 8601 format. |
| `data.timeZone` | The system time zone in IANA format, for example `Europe/Stockholm`. Omitted if the IANA time zone isn’t available. |
| `data.posixTimeZone` | The system time zone in the POSIX format, for example `EST5EDT,M3.2.0,M11.1.0`. Omitted if the POSIX time zone isn’t available. |
| `data.dstEnabled` | The DST flag for controlling the POSIX time zone string: Always `true` if the IANA time zone format is present. Omitted if the POSIX time zone isn’t available. `true` means it will activate the DST settings of the POSIX time zone string. `false` means it will ignore the DST settings of the POSIX time zone string. |
| `data.dhcpTimeZone` | The DHCP time zone that can be in either the IANA or POSIX format. Omitted if the DHCP time zone isn’t available. Introduced in API version 1.1. |
| `data.dhcpTimeZoneUtilized` | The DHCP time zone utilization flag. It will indicate if the DHCP time zone is used by the system. Omitted if DHCP time zone isn’t available. Introduced in API version 1.1. `true` means that DHCP time zone is used by the system. `false` means that DHCP time zone is not used by the system. |
| `data.timeZones[]` | Contains an array of time zones in the IANA format. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### setDateTime

Use `setDateTime` to set the date and time.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setDateTime",    "params": {        "dateTime": "<date and time>"    }}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setDateTime",    "params": {        "dateTime": "<date and time>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that is used. |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method=setDateTime` | _Required_. Specifies that the `setDateTime` operation is performed. |
| `params.dateTime=<date and time>` | _Required_. Specifies that the date and time are set in UTC. The `dateTime` should be formatted as `[YYYY]-[MM]-[DD]T[hh]:[mm]:[ss]Z` and be between the epoch and the last second of the year declared by `maxYearSupported`. (Example: `2018-12-24T20:30:45Z`). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setDateTime",    "data": {        "dateTime": "<date and time>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.dateTime` | Echoes the date and time value that has been set. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### setTimeZone

Use `setTimeZone` to set the time zone. This will set a new IANA time zone, clearing any previous POSIX time zones, although its string in the Time Zone Database will not be affected.

`setTimeZone` is the preferred way of setting a time zone on the device, since it uses an uniform naming convention, such as `Europe/Stockholm`, which is easier to understand than the POSIX style. The Time Zone Database is commonly used in Linux distributions.

**Request**

-   **Security level**: `Operator`

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setTimeZone",    "params": {        "timeZone": "<IANA time zone>"    }}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setTimeZone",    "params": {        "timeZone": "<IANA time zone>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that is used. |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method=setTimeZone` | _Required_. Specifies that the `setTimeZone` operation is performed. |
| `params.timeZone=<IANA time zone>` | _Required_. Specifies which IANA time zone that should be set. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "setTimeZone",    "data": {        "timeZone": "<IANA time zone>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.timeZone` | Echoes the time zone value that has been set. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### setPosixTimeZone

Use `setPosixTimeZone` to set the POSIX time zone. This will set a new POSIX time zone and clear the previous IANA time zones. This method is not the recommend way of setting the time zone, as the POSIX style format has a complex structure and the enabled DST requires manual configuration. Instead, [setTimeZone](#settimezone) is the preferred method.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "setPosixTimeZone",  "params": {    "posixTimeZone": "<POSIX time zone string>",    "enableDst": <DST flag>  }}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "setPosixTimeZone",  "params": {    "posixTimeZone": "<POSIX time zone string>",    "enableDst": <DST flag>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that is used. |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method=setPosixTimeZone` | _Required_. Specifies that the `setPosixTimeZone` operation is performed. |
| `params.posixTimeZone=<POSIX time zone>` | _Required_. Specifies that the POSIXtime zone should be set, for example `EST5EDT,M3.2.0,M11.1.0`. |
| `params.enableDst=<DST flag>` | _Required_. Set to `true` to activate the DST settings of the POSIX time zone string. Set to `false` to ignore the DST setting of the POSIX time zone string. |

**Return value-Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "setPosixTimeZone",  "data": {    "posixTimeZone": "<POSIX time zone string>",    "dstEnabled": <DST flag>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.posixTimeZone` | Echoes the set value of the time zone. |
| `data.dstEnabled` | Echoes the set values of the DST flag. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### resetTimeZone

Use `resetTimeZone` to reset time zones back to the device default value. The DHCP time zone will be used when available.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "resetTimeZone"}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "resetTimeZone"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | _Required_. The API version that is used. |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method=resetTimeZone` | _Required_. Specifies that the `resetTimeZone` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "resetTimeZone",    "data": {        "status": "success"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.status` | Indicate operation success with `success`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### getSupportedVersions

Use `getSupportedVersions` to retrieve supported API versions.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/time.cgi" \\  --data '{    "context": "<ID string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/time.cgiHost: <servername>Content-Type: application/json{    "context": "<ID string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<ID string>` | _Optional_. The client sets this value and the server echoes the data back in the response. If it is set, it will be present in the response, regardless of whether the response is successful or not. |
| `method="getSupportedVersions"` | _Required_. Specifies that the `getSupportedVersions` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "context": "<ID string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Major1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `data.apiVersions` | Contains an array of supported versions. |
| `data.apiVersions[]=<list of versions>` | Contains a list of supported "<Major>.<Minor>" versions, e.g. \["1.4","2.5"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

There currently doesn’t exist any specific error response for this method.

**Error codes**

General errors are listed in [Error handling](#error-handling).

### Error handling

The following table lists general errors that can occur for any JSON requests. As there currently doesn’t exist any specific error responses, a general JSON error response is listed below. Descriptions will only be used to describe the type of error code that appears and detailed information on the fault will be provided in the message field in the error structure.

| Code | Description |
| --- | --- |
| `1000` | Internal error. Refer to message field or logs. |
| `2000` | Invalid request. Only HTTP request type POST is supported. |
| `2001` | Request body too large. |
| `3000` | Invalid JSON data. |
| `4000` | Method does not exist. |
| `4001` | The specified version is not supported. |
| `4002` | Authorization failed. |
| `4003` | Missing parameter(s). |
| `4004` | Invalid parameter(s). |

All failures are returned with the following JSON response:

Error response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "<method string>",  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | _Optional_. Text string echoed back if provided by the client in the corresponding request. |
| `method` | The method that is used to produce the response. |
| `error.code` | Contains the error code. This value can be a method specific and/or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**HTTP status codes**

Some HTTP requests might fail before the JSON parser can be called. These errors are returned in the JSON body when the service is executed, which means that the client must be able to handle HTTP error codes. Specifically HTTP errors `401` and `403` will be returned if the authentication fails.