---
title: Custom HTTP header API
url: "https://developer.axis.com/vapix/network-video/custom-http-header-api/"
category: vapix
subcategory: network-video
sha256: 2a9b848bbfac2835618aacf1d876e643331be9ff202168b6613981731ea5ad99
scraped_at: "2026-01-09T15:19:28.019Z"
page_height: 17502
---

# Custom HTTP header API

The VAPIX® Custom HTTP header API makes it possible to add and remove a custom HTTP header to the HTTP responses on your Axis products.

## Overview

The API implements `/axis-cgi/customhttpheader.cgi` as its communications interface to handle custom HTTP headers to the HTTP responses and supports the following methods:

| Method | Description |
| --- | --- |
| `list` | Lists the custom headers available on your device. |
| `set` | Sets a custom header to your device. |
| `remove` | Removes a custom header from your device. |
| `getSupportedVersions` | Retrieve a list of supported API versions. |

### Identification

-   **API Discovery**: `id=customhttpheader`
-   **AXIS OS**: 9.80 and later

Please note that Axis OS version `10.11` is required before you can add multiple headers at once.

### Default custom HTTP headers

Some devices come with pre-installed custom HTTP headers. Use the `list` method to see all headers. The pre-installed headers can be removed with the `remove` method.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Add a custom header

Use this example to add a custom HTTP header to your device in order to extend functionality, such as adding a header with an unique ID for the device. Standard headers that can be added includes Cross-origin Resource Sharing, X-Frame-Options and Set-Cookie.

#### Set CORS header

1.  Set the Cross-Origin Resource Sharing (CORS) header. This will tell your browser/application that domains specified in the header have permission to make a cross-origin request to the server, i.e. the header allowing the browser to break the same-origin policy.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "set",    "params": {        "Access-Control-Allow-Origin": "http://axis.trusted.example.server.com"    }}'
    ```
    
    ```bash
    POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "set",    "params": {        "Access-Control-Allow-Origin": "http://axis.trusted.example.server.com"    }}
    ```
    
2.  The CORS header will now be included in all responses from the web server once it has been restarted.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "set",    "data": {        "Access-Control-Allow-Origin": "http://axis.trusted.example.server.com"    }}
    ```
    

#### Set a Cookie header

1.  Set a Cookie header. This is used when you want to send cookies from the server to your browser/application.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "OpticalContext",    "method": "set",    "params": {        "Set-Cookie": "device=123; Max-Age=200"    }}'
    ```
    
    ```bash
    POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "OpticalContext",    "method": "set",    "params": {        "Set-Cookie": "device=123; Max-Age=200"    }}
    ```
    
2.  The Set-Cookie header will now be included in all responses from the web server once it has been restarted.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "set",    "data": {        "Set-Cookie": "deviceId=123; Max-Age=200"    }}
    ```
    

### List custom headers

Use this example to retrieve a list of all the custom headers that have been added to the device.

1.  Request a list of custom headers.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "list"}'
    ```
    
    ```bash
    POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "list"}
    ```
    
2.  The JSON response in this example will showcase what it will look like if you had three custom headers installed on your device.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "list",    "data": {        "Set-Cookie": "deviceId=123; Max-Age=200",        "CustomName": "CustomValue",        "Another-Example": "Another-value"    }}
    ```
    

### Remove a custom header

Use this example to remove a custom header from your device. The header is identified by its header name, meaning that any header value is optional and can be omitted.

1.  Remove the Set-Cookie header.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "remove",    "params": {        "Set-Cookie": "deviceId=123; Max-Age=200"    }}'
    ```
    
    ```bash
    POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "remove",    "params": {        "Set-Cookie": "deviceId=123; Max-Age=200"    }}
    ```
    
2.  The Set-Cookie header will not be included in the by the web server once it has restarted.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "OptionalContext",    "method": "remove",    "data": {        "Set-Cookie": "deviceId=123; Max-Age=200"    }}
    ```
    

### Get supported versions

Use this example to retrieve a list of API versions that are supported by your device.

1.  Request a list containing the supported API versions.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "context": "<ID string>",    "method": "getSupportedVersions"}'
    ```
    
    ```bash
    POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "context": "<ID string>",    "method": "getSupportedVersions"}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "<ID string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "<major>.<minor>"\]    }}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.0",    "context": "<ID string>",    "method": "getSupportedVersions",    "error": {        "code": <error code>,        "message": "<error message>"    }}
    ```
    

## API specification
### list

This API method is used when you want to retrieve a list of all custom headers that has been added to the product.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "list"}'
```

```bash
POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "list"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="list"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "list",  "data": {    "<CustomHeaderName>": "<CustomHeaderValue>"    ...  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="list"` | The operation that was performed. |
| `data.CustomHeaderName` | The name of the header |
| `data.CustomHeaderValue` | The content of the header. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "list",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="list"` | The operation that was performed. |
| `error.code` | The code representing the error that occurred in the request. |
| `error.message` | Explains the error that occurred. |

**Error codes**

See [Error codes](#error-codes) for a complete list of potential error codes for this API.

### set

This API method is used when you want to set a custom header on your product.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "set",    "params": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}'
```

```bash
POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "set",    "params": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="set"` | The operation that should be performed. |
| `params.CustomHeaderName` | The name of the header. |
| `params.CustomHeaderValue` | The content of the header. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "set",    "data": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="set"` | The operation that was performed. |
| `data.CustomHeaderName` | The name of the header |
| `data.CustomHeaderValue` | The content of the header. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "set",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="set"` | The operation that was performed. |
| `error.code` | The code representing the error that occurred in the request. |
| `error.message` | Explains the error that occurred. |

**Error codes**

See [Error codes](#error-codes) for a complete list of potential error codes for this API.

### remove

This API method is used when you want to remove a custom header on your product.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "remove",    "params": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}'
```

```bash
POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "remove",    "params": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="remove"` | The operation that should be performed. |
| `params.CustomHeaderName` | The name of the header. |
| `params.CustomHeaderValue` | The content of the header. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "remove",    "data": {        "<CustomHeaderName>": "<CustomHeaderValue>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="remove"` | The operation that was performed. |
| `data.CustomHeaderName` | The name of the header |
| `data.CustomHeaderValue` | The content of the header. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "remove",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="remove"` | The operation that was performed. |
| `error.code` | The code representing the error that occurred in the request. |
| `error.message` | Explains the error that occurred. |

**Error codes**

See [Error codes](#error-codes) for a complete list of potential error codes for this API.

### getSupportedVersions

This API method is used when you want to retrieve the supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/customhttpheader.cgi" \\  --data '{    "context": "<ID string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/customhttpheader.cgiHost: <servername>Content-Type: application/json{    "context": "<ID string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="remove"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "<ID string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "<major>.<minor>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="remove"` | The operation that was performed. |
| `data.apiVersions` | Response specific data. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<ID string>",  "method": "getSupportedVersions",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` | The context that was used the request was made (optional). |
| `method="remove"` | The operation that was performed. |
| `error.code` | The code representing the error that occurred in the request. |
| `error.message` | Explains the error that occurred. |

**Error codes**

See [Error codes](#error-codes) for a complete list of potential error codes for this API.

### Error codes

The following error codes are used by all API methods:

| Code | Description |
| --- | --- |
| `1100` | Internal error. Refer to message field or logs. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON format. |
| `2102` | Method does not exist. |