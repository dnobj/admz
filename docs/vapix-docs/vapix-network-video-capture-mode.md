---
title: Capture mode
url: "https://developer.axis.com/vapix/network-video/capture-mode/"
category: vapix
subcategory: network-video
sha256: b99043d9870ae45aeddd48a510a3bda283de2c952bb41c59b2be8b489c5fd81c
scraped_at: "2026-01-09T15:19:23.322Z"
page_height: 8164
---

# Capture mode

## Description

The AXIS Capture mode API lets you use a collection of image sensor settings and also provides an interface for making changes and retrieving related information for the available capture modes.

### Model

The API consists of the CGI `/axis-cgi/capturemode.cgi`. All capture mode related operations can be performed by using this parameter and one of the following methods:

| Method | Description |
| --- | --- |
| `getCaptureModes` | Retrieves currently available capture modes. |
| `setCaptureMode` | Sets a capture mode for one of the channels. |

### Identification

-   **AXIS OS**: 8.50 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Get Capture mode

Use this example to query the API to return both the current and available capture modes for each channel.

Syntax

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/capturemode.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getCaptureModes"}'
```

```bash
POST /axis-cgi/capturemode.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getCaptureModes"}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getCaptureModes",    "data": \[        {            "channel": 0,            "captureMode": \[                {                    "captureModeId": 0,                    "enabled": true,                    "maxFPS": 120,                    "description": "1280x720 (16:9) @ 100/120 fps"                },                {                    "captureModeId": 1,                    "enabled": false,                    "description": "1920x1080 (16:9) @ 30/60 fps"                }            \]        },        {            "channel": 1,            "captureMode": \[                {                    "captureModeId": 0,                    "enabled": false,                    "description": "1280x720 (16:9) @ 100/120 fps"                },                {                    "captureModeId": 1,                    "enabled": true,                    "maxFPS": 29.97,                    "description": "1920x1080 (16:9) @ 30/60 fps"                }            \]        }    \]}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getCaptureModes--",    "error": {        "code": 4001,        "message": "Method field has invalid value (getCaptureModes--). Valid values: setCaptureMode, getCaptureModes"    }}
```

### Set Capture mode

Use this example to switch between the current and available capture modes. The new capture mode will not take effect until after a reboot.

Syntax

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/capturemode.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setCaptureMode",    "channel": 1,    "captureModeId": 2}'
```

```bash
POST /axis-cgi/capturemode.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setCaptureMode",    "channel": 1,    "captureModeId": 2}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setCaptureMode",    "data": {}}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setCaptureMode",    "error": {        "code": 8000,        "message": "Internal error. Check the log for details."    }}
```

## API specification
### getCaptureModes

Method for getting current and available capture modes.

**Request**

-   **Security level**: Viewer

```bash
POST /axis-cgi/capturemode.cgiHost: <servername>Content-Type: application/json
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The version of the API. |
| `context` | String | _Optional_. Context string. Client sets this value and the CGI sends it back in the response. |
| `method` | String | The operation to perform. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Syntax

```bash
{  "apiVersion": "Version number",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCaptureModes",  "data":  \[    {      "channel": channel\_index,      "captureMode":      \[        {          "captureModeId": The value/identifier to use when calling SetCaptureMode to set this capture mode,          "enabled": True if this is the current capture mode, otherwise false,          "maxFPS": Max frames per second. Optional, this item is guaranteed to exist only if "enabled" is true,          "description": "Friendly description of this capture mode"        }, ...      \]    }, ...  \]}
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Syntax

```bash
{  "apiVersion": "Version number",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCaptureModes",  "error":  {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

Error codes are listed in [Error codes](#error-codes).

### setCaptureMode

Method for setting a capture mode for one channel.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/capturemode.cgiHost: <servername>Content-Type: application/json
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The version of the API. |
| `context` | String | _Optional_. Context string. Set this value and the CGI sends it back in the response. |
| `method` | String | The operation to perform. |
| `channel` | Integer | The index number of the channel. |
| `captureModeId` | Integer | The index number of the of the capture mode. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Syntax

```bash
{    "apiVersion": "Version number",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCaptureMode",    "data": {}}
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Syntax

```bash
{  "apiVersion": "Version number",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setCaptureMode",  "error":  {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

Error codes are listed in [Error codes](#error-codes).

### Error codes

General error responses for Capture mode API.

| Code | Description |
| --- | --- |
| `2000` | Resource allocation failed. Check log for details. |
| `4000` | Invalid JSON format. Check message field for details. |
| `4001` | Parameter not found or invalid value/format. Check message field for details. |
| `8000` | Internal error. Check log for details. |