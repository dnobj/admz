---
title: Pencil privacy filter
url: "https://developer.axis.com/vapix/network-video/pencil-privacy-filter/"
category: vapix
subcategory: network-video
sha256: 6670e4a0cf8fab283785d2266fa081a05a32814cf03d1a6cb88175166eb8876b
scraped_at: "2026-01-09T15:20:39.703Z"
page_height: 16991
---

# Pencil privacy filter

The VAPIX® Pencil privacy filter API provides the information that makes it possible to add a black and white "pencil image" effect to the video stream. By using this API, you will also be able to:

-   Activate/Deactivate the image effect
-   Choose filter types and settings, referred to as `flags` in this API
-   Check information regarding the currently active filter type
-   Request a list of capabilities for all available filter types and flags.

## Overview

The API implements `/axis-cgi/pencil.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| [List supported API versions](#list-supported-api-versions) | List supported API versions. |
| [Request all filter capabilities](#request-all-filter-capabilities) | Check all available filters and flags. |
| [Apply filter settings](#apply-filter-settings) | Change the values for a valid filter type and one or more flags. |
| [Check filter settings](#check-filter-settings) | Check the values and settings for a valid filter type and its current flag values. |
| [Select filter](#select-filter) | Request a filter change. The filter can either be activated or deactivated. |
| [Request filter information](#request-filter-information) | Request status information about a currently active filter. |

### Identification

-   **API Discovery**: `id=pencil-privacy-filter`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## API specifications
### List supported API versions

This method should be used when you want to list all API versions supported by your device.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getSupportedVersions"` | The method that should be used. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested method. |
| `apiVersions[]=<list of versions>` | A list containing all supported API versions along with their highest supported minor version. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)

### Apply filter settings

This method should be used when you want to set the parameter values for the filters.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setFilterSettings",    "params": \[        {            "type": "pencil",            "flags": {                "inverted": true,                "threshold": 45            }        }    \]}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setFilterSettings",    "params": \[        {            "type": "pencil",            "flags": {                "inverted": true,                "threshold": 45            }        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setFilterSettings"` | The method that should be used. |
| `type=<string>` | The filter type that will receive new or updated flags. |
| `flags=<object>` _Optional_ | The flags, which will differ depending on the filter type. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setFilterSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setFilterSettings"` | The requested method. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)
-   [500 Internal error](#500-internal-error)

### Check filter settings

This method should be used when you want to request information regarding the settings for a given filter type.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterSettings",    "params": \[        {            "type": "pencil"        }    \]}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterSettings",    "params": \[        {            "type": "pencil"        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getFilterSettings"` | The method that should be used. |
| `type=<string>` | The filter that will be checked. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterSettings",    "data": \[        {            "type": "pencil",            "flags": {                "inverted": true,                "threshold": 23            }        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getFilterSettings"` | The requested method. |
| `type=<string>` | The requested filter type. |
| `flags=<object>` _Optional_ | The flags, which will differ depending on the filter type. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)
-   [500 Internal error](#500-internal-error)

### Select filter

This method should be used when you want to select which filter that should be active.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setSelectedFilter",    "params": \[        {            "type": "none"        }    \]}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setSelectedFilter",    "params": \[        {            "type": "none"        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setSelectedFilter"` | The method that should be used. |
| `type=<string>` | The filter type that should be active. `none` will deactivate the filter. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setSelectedFilter"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setSelectedFilter"` | The requested method. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)
-   [500 Internal error](#500-internal-error)

### Request filter information

This method should be used when you want to check the current filter information.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSelectedFilter"}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSelectedFilter"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getSelectedFilter"` | The method that should be used. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSelectedFilter",    "data": {        "type": "pencil"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSelectedFilter"` | The requested method. |
| `type=<string>` | The current filter type. Will be `none` if no filter is active. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)
-   [500 Internal error](#500-internal-error)

### Request all filter capabilities

This method should be used when you want to request filter information from all available filters, along with their supported parameters and flags.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pencil.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterCapabilities"}'
```

```bash
POST /axis-cgi/pencil.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getFilterCapabilities"` | The method that should be used. |

**Successful response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getFilterCapabilities",    "data": {        "filters": \[            {                "type": "pencil",                "description": "string",                "flags": \[                    {                        "<flag\_name>": {                            "type": "bool",                            "description": "string"                        }                    },                    {                        "<flag\_name>": {                            "type": "integer",                            "min": 0,                            "max": 255,                            "description": "string"                        }                    }                \]            }        \]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getFilterCapabilities"` | The requested method. |
| `filters=<array>` | List of available filters. |
| `type=<string>` | The filter type. |
| `description=<string>` | Describes the `type` parameters. |
| `flags=<array>` | Flags available for a particular filter. |

**Error responses**

-   [400 Bad request](#400-bad-request)
-   [401 Authentication failed](#401-authentication-failed)
-   [403 Authorization failed](#403-authorization-failed)
-   [413 Transport Level Error](#413-transport-level-error)
-   [500 Internal error](#500-internal-error)

## General error responses
### 400 Bad request

-   **HTTP Code**: 400 Bad request
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "method",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="method"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

### 401 Authentication failed

-   **HTTP Code**: 401 Authentication failed
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "method",    "error": {        "code": 2106,        "message": "Authentication failed."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="method"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

### 403 Authorization failed

-   **HTTP Code**: 403 Authorization failed
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "method",    "error": {        "code": 2105,        "message": "Authorization failed."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="method"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

### 413 Transport Level Error

-   **HTTP Code**: 413 Transport Level Error
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "method",    "error": {        "code": 2107,        "message": "Transport Level Error."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="method"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

### 500 Internal error

-   **HTTP Code**: 500 Internal error
-   **Content-Type**: `application/json`

Response body example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "method",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="method"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |