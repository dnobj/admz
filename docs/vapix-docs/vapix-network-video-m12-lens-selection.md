---
title: M12 Lens Selection API
url: "https://developer.axis.com/vapix/network-video/m12-lens-selection/"
category: vapix
subcategory: network-video
sha256: af047fbc869f6200b0d3239eda6f43b0789be313e64ae4ef8ccaf19b988203fd
scraped_at: "2026-01-09T15:20:10.201Z"
page_height: 18954
---

# M12 Lens Selection API

The VAPIX® M12 Lens Selection API provides the ability to select M12 lenses with different field of views and distortions for individual camera sensors.

-   The API will extract information from a file with both lens data and lens distortion data, and update the field of view data to correspond to the selected lens.
-   This API is required in products that controls a remote PTZ camera and have exchangeable lenses.

warning

This API was deprecated prior to release and will not receive any updates.

## Overview

The API uses `/axis-cgi/m12-lensselection.cgi` as its communication interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getSupportedLenses` | Return a list of supported lenses. |
| `setCurrentLens` | Set the current lens for one of the sensors. |
| `getCurrentLenses` | Return the current lenses used by the camera sensors. |
| `getSupportedVersions` | Return a list of supported API versions. |

### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.M12LensSelection.M12LensSelection=yes`
-   **Property**: `Properties.M12LensSelection.Version=1.00`
-   **Firmware**: `6.50`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Get supported versions

This example will show you how to create a list of all API versions currently supported by your device.

1.  Retrieve a list of supported API versions.

`http://<servername>/axis-cgi/m12-lensselection.cgi`

**JSON input parameters**

```bash
{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

**Successful response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

**Error response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

See [getSupportedVersions](#getsupportedversions) for further details.

### Get supported lenses

This example will show you how to check what lenses to use for a camera sensor that will maintain full PTZ functionality.

1.  Retrieve a list of supported lenses.

`http://<servername>/axis-cgi/m12-lensselection.cgi`

**JSON input parameters**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedLenses",    "params": {        "listSensorIds": true    }}
```

2.  Parse the JSON response.

**Successful response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedLenses",    "data": \[        {            "lensId": 1,            "lensName": "M12 6 mm",            "sensorIds": \[1, 3\]        },        {            "lensId": 2,            "lensName": "M12 1.37 mm",            "sensorIds": \[2, 4\]        },        {            "lensId": 3,            "lensName": "M12 16 mm",            "sensorIds": \[\]        }    \]}
```

**Error response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedLenses",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

See [getSupportedLenses](#getsupportedlenses) for further details.

### Set current lens

This example will show you how to exchange lenses on a camera sensor while maintaining full PTZ functionality.

1.  Set the current lens.

`http://<servername>/axis-cgi/m12-lensselection.cgi`

**JSON input parameters**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "setCurrentLens",    "params": {        "sensorId": 1,        "lensId": 2    }}
```

2.  Parse the JSON response.

**Successful response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "setCurrentLens",    "data": {}}
```

**Error response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "setCurrentLens",    "error": {        "code": 1002,        "message": "Unsupported lens"    }}
```

See [setCurrentLens](#setcurrentlens) for further details.

### Get current lens

This example will show you how to check which lens that is currently used by the camera sensor.

1.  Get the current lens information.

`http://<servername>/axis-cgi/m12-lensselection.cgi`

**JSON input parameters**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getCurrentLenses",    "params": {        "sensorId": 3    }}
```

2.  Parse the JSON response.

**Successful response example**

This response example returns the lens ID and name for the specified sensor ID.

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getCurrentLenses",    "data": \[        {            "sensorId": 3,            "lensId": 2,            "lensName": "M12 1.37 mm"        }    \]}
```

This response example returns the lens ID and name of the current lens for all camera sensors.

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getCurrentLenses",    "data": \[        {            "sensorId": 1,            "lensId": 2,            "lensName": "M12 1.37 mm"        },        {            "sensorId": 2,            "lensId": 1,            "lensName": "M12 6 mm"        },        {            "sensorId": 3,            "lensId": 2,            "lensName": "M12 1.37 mm"        },        {            "sensorId": 4,            "lensId": 1,            "lensName": "M12 6 mm"        }    \]}
```

**Error response example**

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getCurrentLenses",    "error": {        "code": 1001,        "message": "Invalid sensor"    }}
```

See [getCurrentLenses](#getcurrentlenses) for further details.

## API Specifications
### getSupportedVersions

Retrieve a list of supported API versions.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/m12-lensselection.cgi" \\  --data '{    "context": "<string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/m12-lensselection.cgiHost: <servername>Content-Type: application/json{    "context": "<string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>`  
_Optional_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getSupportedVersions"` | The API method called in the request. |

**Responses**

_Successful response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "context": "<string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \[ "<Major1>.<Minor1>", "<Major2>.<Minor2>" \]    }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested API method. |
| `data.apiVersions[]=<list of versions>` | List of supported versions. Includes all major versions along with their highest minor version. |
| `<list of versions>` | List of `“<Major>.<Minor>"` versions, for example `["1.4", "2.5"]`. |

_Error response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedVersions",    "error": {        "code": <integer error code>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested API method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSupportedLenses

Retrieve a list of supported lenses.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/m12-lensselection.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedLenses",    "params": {        "listSensorIds": <boolean>    }}'
```

```bash
POST /axis-cgi/m12-lensselection.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedLenses",    "params": {        "listSensorIds": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that should be used. |
| `context=<string>`  
_Optional_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getSupportedLenses"` | The API method called in the request. |
| `params=<listSensorIds>`  
_Optional_ | The user sets this value and the server will add an array of sensor IDs for the currently used lens. |

**Responses**

_Successful response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedLenses",    "data": \[        {            "lensId": <integer>,            "lensName": <string>,            "sensorIds": \[<integer>, ...\]        },        ...    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getSupportedLenses"` | The requested API method. |
| `data=<array>` | Container for response specific parameters listed below. |
| `lensId=<integer>` | The lens ID. |
| `lensName=<string>` | The lens name. |
| `sensorIds=<array of integers>` | An array of sensor IDs where the lens is used. |

_Error response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedLenses",    "error": {        "code": <integer error code>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getSupportedLenses"` | The requested API method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getCurrentLenses

Retrieve the current lens for each camera sensor.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/m12-lensselection.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getCurrentLenses",    "params": {        "sensorId": <integer>    }}'
```

```bash
POST /axis-cgi/m12-lensselection.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getCurrentLenses",    "params": {        "sensorId": <integer>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that should be used. |
| `context=<string>`  
_Optional_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getCurrentLenses"` | The API method called in the request. |
| `params=<sensorId>`  
_Optional_ | The user sets this value and the server will get the current lens for the specified sensor ID. |

**Responses**

_Successful response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getCurrentLenses",    "data": \[        {            "sensorId": <integer>,            "lensId": <integer>,            "lensName": <string>        },        ...    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getCurrentLenses"` | The requested API method. |
| `data=<array>` | Container for response specific parameters listed below. |
| `sensorId=<integer>` | The sensor ID. |
| `lensId=<integer>` | The lens ID. |
| `lensName=<string>` | The lens name. |

_Error response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getCurrentLenses",    "error": {        "code": <integer error code>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="getCurrentLenses"` | The requested API method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setCurrentLens

Set the current lens for a sensor.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/m12-lensselection.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "setCurrentLens",    "params": {        "sensorId": <integer>,        "lensId": <integer>    }}'
```

```bash
POST /axis-cgi/m12-lensselection.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "setCurrentLens",    "params": {        "sensorId": <integer>,        "lensId": <integer>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that should be used. |
| `context=<string>`  
_Optional_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="setCurrentLens"` | The API method called in the request. |
| `params=<sensorId>` | The sensor ID that should be set. |
| `params=<lensId>` | The lens ID that should be set. |

**Responses**

_Successful response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "setCurrentLens",    "data": {    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="setCurrentLens"` | The requested API method. |

_Error response_

-   **HTTP Code**: `200 OK`
-   **Content-Type**: application/json

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "setCurrentLens",    "error": {        "code": <integer error code>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version used in the request. |
| `context=<string>`  
_Optional_ | The context set by the user in the request. |
| `method="setCurrentLens"` | The requested API method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

| Code | Description |
| --- | --- |
| `1000` | Invalid parameter value. |
| `1001` | Invalid sensor. |
| `1002` | Unsupported lens. |
| `2000` | Out of memory. |
| `2001` | Access forbidden (similar to HTTP 403). |
| `2002` | HTTP request type not supported. Only POST supported. |
| `2003` | The requested API version is not supported. |
| `2004` | Method not supported. |
| `4000` | The provided JSON input was invalid. |
| `4001` | A mandatory input parameter was not found in the input. |
| `4002` | The type of a provided JSON parameter was incorrect. |
| `8000` | Internal error, could not complete request. |