---
title: Find my device
url: "https://developer.axis.com/vapix/network-video/find-my-device/"
category: vapix
subcategory: network-video
sha256: 930718ba776219325c41b6256ca6e15b8a033e8973e6f9b66a9928b9daa313d1
scraped_at: "2026-01-09T15:19:48.528Z"
page_height: 11764
---

# Find my device

## Description

The Find my device API makes it possible to locate an Axis device, for instance by playing a sound or flashing a status LED. As this is a generic API, the identification methods available on your device and the ones described herein may vary.

Implementing a method with this API while another API is using the same functions might lead to unexpected behavior. For example, triggering an audio clip at the same time as the device is playing something else, might interrupt the audio due to the higher priority of the Find my device API or become mixed.

### Model

The API implements `/axis-cgi/findmydevice.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `find` | Initiates the mechanism that locates the device. |
| `stop` | Halts the mechanism that locates the device. |
| `getSupportedVersions` | Lists supported API versions. |

### Identification

-   **API Discovery**: `id=findmydevice`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Find my device

Use this example to locate your device when you are setting up a system with either visible or audible aid. The example will also show you the required steps to stop the search sequence.

#### Find

1.  Request `find` with the following JSON syntax:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "find",    "params": {        "duration": 10    }}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "find",    "params": {        "duration": 10    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "find",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "find",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

#### Stop

1.  Request `stop` with the following JSON syntax:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "123",    "method": "stop"}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "123",    "method": "stop"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.1",    "context": "123",    "method": "stop",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.1",    "context": "123",    "method": "stop",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

#### Get supported versions

Use this example to retrieve a list of API versions supported on your device.

1.  Get a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Failed response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

## API specification
### find

This API method is used when you want to initiate the mechanism that locates the device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "find",  "params": {    "duration": <integer>  }}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "find",  "params": {    "duration": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="find"` | The operation that should be performed. |
| `params.duration=<integer>` | The user sets this value to specify how long the search sequence shall last. This parameter is specified in seconds with the upper limit being 3600 seconds (optional). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "find",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="find"` | The operation that was performed. |
| `data` | No data will return in a successful request. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a full list of potential errors.

### stop

This API method is used when you want to halt the mechanism that locates the device during the middle of a duration-period set by the `find` parameter.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "stop"}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "stop"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="stop"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "stop",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="stop"` | The operation that was performed. |
| `data` | No data will return in a successful request. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a full list of potential errors.

### getSupportedVersions

This API method is used when you want to retrieve a list of supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/findmydevice.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/findmydevice.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": <string>  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context that was used when the request was made. |
| `method="getSupportedVersions"` | The operation that was performed. |
| `data.apiVersions[]=<list of versions>` | Specifies the list of supported versions and includes all major versions together with their highest supported minor version. |
| `<list of versions>` | The list of "<Major>.<Minor>" versions, e.g. \["1.4", "2.5"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

### General error codes

The following table lists the errors that can occur for any API method.

| Code | Description |
| --- | --- |
| `1100` | Internal error([1](#user-content-fn-1)) |
| `2100` | API version not supported. |
| `2101` | Invalid JSON format. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing or invalid |
| `2104` | Invalid parameter value specified |
| `2200` | Transport layer error (e.g. request not HTTP POST) |
| `2201` | Busy, already performing method |

## Footnotes

1.  Out-of-memory errors will also return this error code. [↩](#user-content-fnref-1)