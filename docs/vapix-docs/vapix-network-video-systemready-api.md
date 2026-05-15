---
title: Systemready API
url: "https://developer.axis.com/vapix/network-video/systemready-api/"
category: vapix
subcategory: network-video
sha256: f38eaa5e1739d88cf4769b493c30108adde84101beed6d06e89b6e1c5f7723dc
scraped_at: "2026-01-09T15:21:13.986Z"
page_height: 8605
---

# Systemready API

The VAPIX® Systemready API makes it possible to find out, without authentication, if the Axis device is ready to handle external communication, configurations and video streaming on either the first or a consecutive boot up.

## Overview

The API uses the `/axis-cgi/systemready.cgi` as its communication interface and supports the following methods:

| Methods | Description |
| --- | --- |
| `systemready` | Query to check if the system is ready. |
| `getSupportedVersions` | Retrieve a list of supported API versions. |

### Identification

-   **API Discovery**: `id=systemready`
-   **AXIS OS**: 9.50 and later

### Obsoletes

This CGI replaces polling of APIs such as `getBrandInfo`, which were used determine when the system was ready.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### How to use Systemready

This example will show you how to test if your device is ready to receive and handle requests.

1.  Check if the system is ready with the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/systemready.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "my context",    "method": "systemready",    "params": {        "timeout": 20    }}'
```

```bash
POST /axis-cgi/systemready.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "my context",    "method": "systemready",    "params": {        "timeout": 20    }}
```

Please note that it will take up to 20 seconds before the system responds.

2.  The response will appear if the system is or becomes ready during the timeout. If `needsetup` is `yes` the system is lacking an initial admin user, which must first be created using `/axis-cgi/pwdgrp.cgi`. It is not possible to call an API that requires authentication otherwise. Additional fields include:

-   `uptime` shows how many seconds the device has been active since it was last booted.
-   `bootid` is a string used for the current boot up of the device.
-   `previewmode` will be included in the response if the device is in preview mode.

Successful response

```bash
{    "apiVersion": "1.4",    "context": "my context",    "method": "systemready",    "data": {        "systemready": "yes",        "needsetup": "no",        "uptime": "7800",        "bootid": "ebe1fa05-2ff7-4062-874c-68a466a9eaed"    }}
```

Successful response with active preview mode

```bash
{    "apiVersion": "1.4",    "context": "my context",    "method": "systemready",    "data": {        "systemready": "yes",        "needsetup": "no",        "uptime": "120",        "bootid": "ebe1fa05-2ff7-4062-874c-68a466a9eaed",        "previewmode": "7200"    }}
```

## API specification
### systemready

This method should be used to check if the system is ready for operation.

**Request**

-   **Security level**: Anonymous

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/systemready.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "systemready",  "params": {    "timeout": <timeout seconds>  }}'
```

```bash
POST /axis-cgi/systemready.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "systemready",  "params": {    "timeout": <timeout seconds>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context` | The user sets this value and the application echoes it back in the response (optional). |
| `method` | The method that should be used. |
| `params` | Method specific parameters. Optional for some methods. |
| `timeout` | The maximum time `/axis-cgi/systemready.cgi` will take before returning a response. Valid responses are either `yes` or `no`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "systemready",    "data": {        "systemready": "yes/no",        "needsetup": "yes/no",        "uptime": "<seconds from when the device was started in seconds>",        "bootid": "<unique boot id string>",        "previewmode": "<previewmode duration in seconds>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context set by the user in the request (optional). |
| `method` | The requested method. |
| `data` | Response specific data. |
| `systemready` | The system ready status. Accepted values are `yes` and `no`. |
| `needsetup` | Setup related parameter. If the returning value is `yes` an initial admin user must first be created using `/axis-cgi/pwdgrp.cgi`. |
| `uptime` | The device boot uptime, presented in seconds. |
| `bootid` | The device boot id string. |
| `previewmode` | Included when preview mode is enabled. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": <string>  "method": "systemready",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context set by the user in the request (optional). |
| `method` | The requested method. |
| `error` | Error specific data. |
| `code` | The error code. |
| `message` | The error message for the corresponding error code. |

### getSupportedVersions

This method should be used when you want to retrieve a list containing all API versions supported by your device.

**Request**

-   **Security level**: Anonymous

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/systemready.cgi" \\  --data '{    "context": "<string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/systemready.cgiHost: <servername>Content-Type: application/json{    "context": "<string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context` | The user sets this value and the application echoes it back in the response (optional). |
| `method` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "context": "<string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "<major>.<minor>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `context` | The context set by the user in the request (optional). |
| `method` | The requested method. |
| `data` | Response specific data. |
| `apiVersions` | A list containing all supported major versions along with their highest minor version, e.g. `["1.0", "1.2"]`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <error code>,    "message": "<error message>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context set by the user in the request (optional). |
| `method` | The requested method. |
| `error` | The error specific data. |
| `code` | The error code. |
| `message` | The error message for the corresponding error code. |

### General error codes

The following table lists the general errors that can occur to any CGI method.

| Code | Description |
| --- | --- |
| `1000` | Internal error. Refer to message field or logs. |
| `9000` | Internal error. |