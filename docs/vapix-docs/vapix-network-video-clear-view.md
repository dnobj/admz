---
title: Clear view
url: "https://developer.axis.com/vapix/network-video/clear-view/"
category: vapix
subcategory: network-video
sha256: 33700cd87c31a7a9ea69ad3df815479b2e3751889b906488981ad9d35b2449b6
scraped_at: "2026-01-09T15:19:26.445Z"
page_height: 24074
---

# Clear view

## Description

The Clear view API makes it possible to activate functions that keeps your Axis camera lens and/or dome clean. This is useful in environments where water from rain and ice or dust particles are common issues. The API features functions that lets you clear water droplets by using either the wiper or speed dry functionality in cameras where this option is present.

### Model

The API implements `/axis-cgi/clearviewcontrol.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getSupportedVersions` | Retrieves a list of the API versions supported by the CGI. |
| `getServiceInfo` | Retrieves a list containing the Clear view service information (static values only). |
| `getStatus` | Retrieves the Clear view service status for one service (dynamic values). |
| `start` | Initiates the Clear view function for one service. |
| `stop` | Halts the Clear view function. |

### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.ClearView.ClearView=yes`
-   **AXIS OS**: 7.10 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Detect supported versions

Use this example to check if Clear view is supported on your camera and potential limitations that might be implemented.

1.  Request Clear view protocol version support using `POST`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
    ```
    
    ```bash
    POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "2.1",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "2.1"\]    }}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "2.1",    "context": "my context",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error, could not complete request."    }}
    ```
    

### Get service info

Use this example to retrieve a list containing supported information about the Clear view controller service.

1.  Request a list of the Clear view service information using `POST`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "data": {        "serviceInfo": \[            {                "id": 0,                "type": "wiper",                "durationVariable": true,                "durationMin": 5,                "durationMax": 120,                "durationDefault": 5,                "idleTimeMin": 0,                "stoppable": true            },            {                "id": 1,                "type": "speeddry",                "durationVariable": false,                "durationDefault": 10,                "idleTimeMin": 15,                "stoppable": false            }        \]    }}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "error": {        "code": 3000,        "message": "The requested API version is not supported."    }}
    ```
    

**API reference**

getServiceInfo

-   [getServiceInfo](#getserviceinfo)

### Start cleaning view

Use this example to remove water droplets from your device.

**Initiate Clear view**

1.  Start the Clear view operation with the default duration using `POST`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0    }}'
    ```
    
    ```bash
    POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0    }}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "data": {}}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "error": {        "code": 1002,        "message": "Device in incompatible state."    }}
    ```
    

**Start Clear view with a specified duration**

1.  Initiate Clear view on a specified device with duration using `POST`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0,        "duration": 30    }}'
    ```
    
    ```bash
    POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0,        "duration": 30    }}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "data": {}}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "error": {        "code": 1003,        "message": "Requested duration outside supported limits."    }}
    ```
    

### Stop cleaning view

Use this example to halt a currently running cleaning function.

**Stop cleaning view**

1.  Halt any currently running Clear view operation on a service using `POST`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "params": {        "id": 1    }}'
    ```
    
    ```bash
    POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "params": {        "id": 1    }}
    ```
    
2.  Parse the JSON response
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "data": {}}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "error": {        "code": 2004,        "message": "Method not supported."    }}
    ```
    

### Get status

Use this example to check if Clear view is currently active or when it can be activated again.

1.  Request status and availability from the device using `POST`.
    
    `http://<servername>/axis-cgi/clearviewcontrol.cgi`
    
    JSON input parameters
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "params": {        "id": 0    }}
    ```
    
2.  The following example response will appear for idle devices.
    
    JSON output parameters
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "data": {        "state": "idle"    }}
    ```
    
3.  The following example response will appear for running devices where `idleTimeMin` is not defined (i.e. set to 0).
    
    JSON output parameters
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "data": {        "state": "running",        "stopsIn": 23    }}
    ```
    

## API specification
### getSupportedVersions

This method is used when you want to retrieve a list containing the API versions supported by your device. The returned list consists of all supported major versions along with their highest supported minor versions.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "<Major.Minor>",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The context used when the request was made (optional). |
| `method` | String | The operation that was performed. |
| `data` | JSON object | A container for the response specific parameters. |
| `apiVersions` | Array | The supported API versions, presented in the format Major.Minor. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the error message. |

**Error codes**

No specific errors exists for this method. See [General error codes](#general-error-codes) for a complete list.

### getServiceInfo

This method is used when you want to retrieve a list containing the Clear view service info.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "params": {}}'
```

```bash
POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used in the request. |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be performed. |
| `params` | JSON object | Container for the method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "data": {        "serviceInfo": \[            {                "id": 0,                "type": "wiper",                "durationVariable": true,                "durationMin": 5,                "durationMax": 120,                "durationDefault": 5,                "idleTimeMin": 0,                "stoppable": true            },            {                "id": 1,                "type": "speeddry",                "durationVariable": false,                "durationDefault": 10,                "idleTimeMin": 15,                "stoppable": false            }        \]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The context used when the request was made (optional). |
| `method` | String | The operation that was performed. |
| `data` | JSON object | A container for the response specific parameters. |
| `serviceInfo` | Array | The supported Clear view services. |
| `id` | Integer | The ID of the clear view device. |
| `type` | String | Defined types are `wiper` and `speeddry`. |
| `durationVariable` | Boolean | The duration control. |
| `durationMin` | Integer | Present if `durationVariable` = true. |
| `durationMax` | Integer | Present if `durationVariable` = true. |
| `durationDefault` | Integer | The default duration, measured in seconds. |
| `stoppable` | Boolean | The stop-command for the device. |
| `idleTimeMin` | Integer | Should be included if the device needs to rest between runs, measured in seconds. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceInfo",    "error": {        "code": 3000,        "message": "The requested API version is not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the error message. |

**Error codes**

No specific errors exists for this method. See [General error codes](#general-error-codes) for a complete list.

### getStatus

This method is used when you want to retrieve the Clear view status.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "params": {        "id": 0    }}'
```

```bash
POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used in the request. |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be performed. |
| `params` | JSON object | Container for the method specific parameters. |
| `id` | Integer | The device ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "data": {        "status": {            "state": "running",            "stopsIn": 3,            "availableIn": 13        }    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The context used when the request was made (optional). |
| `method` | String | The operation that was performed. |
| `data` | JSON object | A container for the response specific parameters |
| `status` | JSON object | The status of the clear view service. |
| `id` | Integer | The ID of the clear view device. |
| `state` | String | Defined states are `idle`, `running` and `waiting`. |
| `stopsIn` | Integer | Present if the state parameter is running. |
| `availableIn` | Integer | Present if `idleTimeMin > 0` and the state parameter is either running or waiting. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getStatus",    "error": {        "code": 1001,        "message": "The requested Clear View device id is not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the error message. |

**Error codes**

No specific errors exists for this method. See [General error codes](#general-error-codes) for a complete list.

### start

This method is used when you want to initiate a Clear view service.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0,        "duration": 10    }}'
```

```bash
POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "params": {        "id": 0,        "duration": 10    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used in the request. |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be performed. |
| `params` | JSON object | Container for the method specific parameters. |
| `id` | Integer | The device ID. |
| `duration` | Integer | The duration, measured in seconds (optional). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The context used when the request was made (optional). |
| `method` | String | The operation that was performed. |
| `data` | JSON object | A container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "start",    "error": {        "code": 1001,        "message": "The requested Clear View device id is not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the error message. |

**Error codes**

No specific errors exists for this method. See [General error codes](#general-error-codes) for a complete list.

### stop

This method is used when you want to halt a Clear view service.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/clearviewcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "params": {        "id": 0    }}'
```

```bash
POST /axis-cgi/clearviewcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used in the request. |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be performed. |
| `params` | JSON object | Container for the method specific parameters. |
| `id` | Integer | The device ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The context used when the request was made (optional). |
| `method` | String | The operation that was performed. |
| `data` | JSON object | A container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "stop",    "error": {        "code": 1001,        "message": "The requested Clear View device id is not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the error message. |

**Error codes**

No specific errors exists for this method. See [General error codes](#general-error-codes) for a complete list.

### General error codes

| Code | Description |
| --- | --- |
| `1000` | Invalid parameter value. |
| `1001` | The requested Clew View device ID is not supported. |
| `1002` | Device in incompatible state. |
| `1003` | Requested duration outside supported limits. |
| `1005` | Temperature out of range. |
| `2000` | Out of memory. |
| `2001` | Access forbidden (similar to HTTP 403). |
| `2002` | HTTP request type not supported. Only POST supported. |
| `2003` | The requested API version is not supported. |
| `2004` | Method not supported. |
| `4000` | The provided JSON input was invalid. |
| `4001` | A mandatory input parameter was not found in the input. |
| `4002` | The type of a provided JSON parameter was incorrect. |
| `8000` | Internal error. |