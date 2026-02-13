---
title: Radar Properties
url: "https://developer.axis.com/vapix/radar/radar-properties/"
category: vapix
subcategory: radar
sha256: a620a583103253c5e8e5fb21ba67f8593a38b5b09499a1dba513cce153b3790b
scraped_at: "2026-01-09T15:22:10.839Z"
page_height: 5373
---

# Radar Properties

The VAPIX® Radar Properties API makes it possible to inspect a multitude of radar properties, including the minimum and maximum detection ranges, the number of radar objects, object speed, pairing status and more.

## Overview
### Identification

-   **API Discovery**: `id=radar-properties`
-   **Parameter** `Properties.Radar.Properties.Version`

### Limitations

This API is available on all Axis devices with radar support.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases

The following example will show you how to fetch all radar characteristics. Additional details can be found in the [API Specifications](#api-specifications) below.

1.  Send a [getRadarProperties](#getradarproperties) request to check which capabilities are available on the radar. Examples on properties include radar detection range and angle settings.

## API Specifications
### getRadarProperties

Retrieve all radar properties.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/properties.cgi#getRadarProperties" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarProperties"}'
```

```bash
POST /properties.cgi#getRadarPropertiesHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarProperties"}
```

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getRadarProperties"` |  | The API method that is called in the request. |

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarProperties",    "data": {        "device": "D2210-VE",        "minDetectionRange": 10,        "maxDetectionRange": 100,        "minHorizontalAngle": -30,        "maxHorizontalAngle": 30,        "minVerticalAngle": -20,        "maxVerticalAngle": 20,        "maxRadarObjects": 50,        "maxObjectSpeed": 120.5,        "networkPaired": true    }}
```

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="getRadarProperties"` |  | The requested API method. |
| `device=<string>` | `"D2210-VE"` | The product number of the radar device. |
| `minDetectionRange=<integer>` | 10 | The minimum detection range. |
| `maxDetectionRange=<integer>` | 100 | The maximum detection range. |
| `minHorizontalAngle=<integer>` | \-30 | The minimum horizontal angle. |
| `maxHorizontalAngle=<integer>` | 30 | The maximum horizontal angle. |
| `minVerticalAngle=<integer>` | \-20 | The minimum vertical angle. |
| `maxVerticalAngle=<integer>` | 20 | The maximum vertical angle. |
| `maxRadarObjects=<integer>` | 50 | The maximum number of radar objects. |
| `maxObjectSpeed=<number>` | 120.5 | The maximum object speed. |
| `networkPaired=<boolean>` | `true` | Checks if the radar device is paired with another device. Can be either `true` or `false`. |

_Error response_

_400 Bad request_

```bash
Status: 400 Bad RequestContent-Type: text/plain
```

_500 Internal server error_

```bash
500 Internal server errorContent-Type: text/plain
```

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarProperties",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="getRadarProperties"` |  | The requested API method. |
| `error.code=<integer>` | `1100` | The error code. |
| `error.message=<string>` | Internal error. | The error message for the corresponding error code. |

| Error code | Error message |
| --- | --- |
| `1100` | Internal error. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing. |
| `2104` | Invalid parameter value specified. |
| `2105` | Authorization failed. |
| `2106` | Authentication failed. |
| `2107` | Transport level error. |