---
title: OAK API
url: "https://developer.axis.com/vapix/network-video/oak-api/"
category: vapix
subcategory: network-video
sha256: bbee114664e17bbfd29913112fd641a1a5ed6e7c22170161ee821d08ffbdc8c1
scraped_at: "2026-01-09T15:20:23.994Z"
page_height: 7224
---

# OAK API

## Description

The OAK (Owner Authentication Key) API makes it possible to retrieve the OAK from an Axis device and authenticate its owner towards the AXIS O3C Dispatcher service.

info

Please note that this operation requires unhindered internet access from the device, i.e. involving a proxy server will cause the OAK retrieval to fail.

### Model

The API implements `/axis-cgi/oak.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getOAK` | Retrieves the product specific OAK. |
| `getSupportedVersions` | Retrieves the API version supported by your device. |

### Identification

-   **API Discovery**: `id=oak`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Retrieve OAK

Use this example to retrieve the owner authentication key to register your device. This operation requires unhindered internet access from your device, i.e. involving a proxy server will cause the OAK retrieval to fail.

1.  Request the OAK with the following JSON request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/oak.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getOAK"}'
```

```bash
POST /axis-cgi/oak.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getOAK"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getOAK",    "data": {        "oak": "OAK"    }}
```

## API specifications
### getOAK

This API method is used to retrieve the owner authentication key. Please note that this operation requires unhindered internet access from your device, i.e. involving a proxy server will cause the OAK retrieval to fail and the error response `1100 - Internal error` will be returned.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/oak.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getOAK"}'
```

```bash
POST /axis-cgi/oak.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getOAK"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<ID string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getOAK"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getOAK",    "data": {        "oak": "<oak string>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<ID string>` | The context that was used when the request was made (optional). |
| `method="getOAK"` | The operation that was performed. |
| `data.oak` | The owner authentication key. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exist for this method. See [Error handling](#error-handling) for a full list of potential error codes and general errors.

### getSupportedVersions

This API method is used to retrieve a list of supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/oak.cgi" \\  --data '{    "context": "<ID string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/oak.cgiHost: <servername>Content-Type: application/json{    "context": "<ID string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<ID string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<ID string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | The context that was used when the request was made (optional). |
| `method="getSupportedVersions"` | The operation that was performed. |
| `data.apiVersions` | An array containing the supported versions. |
| `data.apiVersions[]=<list of versions>` | Lists all supported major versions along with their highest supported minor version. |
| `<list of versions>` | The list of `"<major>.<minor>"` versions, e.g. `["1.0"]`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exist for this method. See [Error handling](#error-handling) for a full list of potential error codes and general errors.

### Error handling

The following table lists the general errors that can occur for any of the JSON requests.

| Code | Description |
| --- | --- |
| `1100` | Internal error. |
| `2000` | Invalid request. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON data. |
| `2102` | Method does not exist. |
| `2103` | Missing parameter method. |

**Error response body syntax**

All potential failures will return with the following JSON response.

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<ID string>",  "method": "<method string>",  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code` | Container for the error code. |
| `error.message` | Container for the message about the occurred failure. |