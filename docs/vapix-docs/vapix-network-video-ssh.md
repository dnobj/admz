---
title: SSH
url: "https://developer.axis.com/vapix/network-video/ssh/"
category: vapix
subcategory: network-video
sha256: e302350490c970c1473eb3e8bac783b366bd4943ebaff86bc0feb900da75ef90
scraped_at: "2026-01-09T15:21:04.301Z"
page_height: 13852
---

# SSH

## Description

The SSH (Secure shell) API makes it possible to retrieve and configure the SSH functions on an Axis device.

### Model

The API implements `/axis-cgi/ssh.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getSshInfo` | Retrieve the SSH configuration currently on the Axis device in the form of a status section that will indicate whether the SSH functionality is either enabled or disabled. |
| `getSupportedVersions` | Retrieve a list of all API versions supported by the product. |
| `setSshConfiguration` | Set the state of the SSH functionality to enabled. |

### Identification

-   **API Discovery**: `id=ssh`

### Obsoletes

This CGI renders the process of retrieving and setting SSH parameters through the `/axis-cgi/param.cgi` obsolete. Devices that support both `/axis-cgi/param.cgi` and the SSH API will yield the same result regardless of method.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Configure the SSH functionality on the Axis device

Use this example to configure your Axis device to enable SSH functionality.

1.  Retrieve the SSH configuration for your Axis device using the url below with the POST method. The configuration will then be presented to you.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getSshInfo",    "params": {}}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getSshInfo",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getSshInfo",    "data": {        "enabled": true    }}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "error": {        "code": 1000,        "message": "Internal error"    }}
```

This error will occur if the CGI encounters an internal error that makes it abort the operation.

3.  Check the retrieved information and apply the new configurations.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setSshConfiguration",    "params": {        "enabled": true    }}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setSshConfiguration",    "params": {        "enabled": true    }}
```

4.  The VMS will receive the a response and inform you of the result.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setSshConfiguration",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "error": {        "code": 4003,        "message": "Missing parameter(s)"    }}
```

This error will occur if the VMS has sent an incomplete request that was missing one or more of the required parameters.

### Retrieve the supported API versions

Use this example to check which API version you should use when you want to communicate with the Axis device.

1.  Request a list containing the supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "2.1"\]    }}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

This error will occur if the CGI encounters an internal error that causes it to abort the operation.

See [getSupportedVersions](#getsupportedversions) for further instructions.

## API specifications
### getSshInfo

This API method is used to retrieve information about the SSH configuration from an Axis device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSshInfo"}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSshInfo"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSshInfo"` | The performed method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSshInfo",  "data": {    "enabled": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="getSshInfo"` | The method that was performed. |
| `data.enabled=<boolean>` | A boolean returning one of the following responses: `true`: SSH functionality is enabled and running `false`: SSH functionality is disabled and not running |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSshInfo",  "error": {    "code": <error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="getSshInfo"` | The method that was performed. |
| `error.code=<error code>` | The error code describing the kind of error that occurred. |
| `error.message=<string>` | The error message describing the error to the user. |

**Error code**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getSupportedVersions

This API method will show you a list of supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions",  "params": {}}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions",  "params": {}}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The performed method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[<string>\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="getSupportedVersions"` | The method that was performed. |
| `data.apiVersions=[<string>]` | A list containing the supported API versions. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="getSupportedVersions"` | The method that was performed. |
| `error.code=<integer>` | The error code describing the kind of error that occurred. |
| `error.message=<string>` | The error message describing the error to the user. |

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setSshConfiguration

This API method is used to apply SSH functionality to an Axis device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/ssh.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setSshConfiguration",  "params": {    "enabled": <boolean>  }}'
```

```bash
POST /axis-cgi/ssh.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setSshConfiguration",  "params": {    "enabled": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setSshConfiguration"` | The performed method. |
| `params.enabled=<boolean>` | Specifies the desired enabled state of the SSH functionality. `true`: The functionality is enabled and running. `false`: The functionality is disabled and not running. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setSshConfiguration",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="setSshConfiguration"` | The method that was performed. |
| `data` | This field is empty, since this particular request, when successfully executed, doesn’t return any data. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setSshConfiguration",  "error": {    "code": <error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used. |
| `context=<string>` | A text string echoed back if it was provided in the corresponding request (optional). |
| `method="setSshConfiguration"` | The method that was performed. |
| `error.code=<error code>` | The error code describing the kind of error that occurred. |
| `error.message=<string>` | The error message describing the error to the user. |

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### General error codes

These error codes are used by all API methods.

Please note that for internal CGI errors (`1000`) the HTTP response code is set to `500`, whereas for any other CGI error the HTTP response code will be `200`.

User authentication and authorization to use the CGIs are performed on the HTTP level and, if unsuccessful, will return the HTTP error code `401`. The authorization of the internal services used by the CGIs are performed after both the HTTP authentication and authorization has passed, meaning it will always return the HTTP code `200` regardless of the outcome. Should it fail during the latter stage, the response will consist of an HTTP code `200` as well as JSON data containing the error `4002` (Authorization failed), which means that the CGI couldn't be authorized and thus unable to complete its task. This does not mean that you weren’t able to access the CGI itself.

| Error code | Description |
| --- | --- |
| `1000` | Internal error |
| `2000` | Invalid request |
| `2001` | Request body too large |
| `3000` | Invalid JSON data |
| `4000` | Method does not exist |
| `4001` | The specified version is not supported |
| `4002` | Authorization failed |
| `4003` | Missing parameter(s) |
| `4004` | Invalid parameter(s) |