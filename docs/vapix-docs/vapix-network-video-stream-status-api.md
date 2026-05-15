---
title: Stream status API
url: "https://developer.axis.com/vapix/network-video/stream-status-api/"
category: vapix
subcategory: network-video
sha256: 0bab9fa657a9c3bc0e7b9833c4ae1e0900967812e782d2d60a437a85cc5d7cc0
scraped_at: "2026-01-09T15:21:09.333Z"
page_height: 8628
---

# Stream status API

## Description

The Stream status API makes it possible to list streams on a device.

### Model

The API implements `/axis-cgi/streamstatus.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getAllStreams` | Lists all running streams on a device. |
| `getSupportedVersions` | Retrieves a list of supported API versions. |

### Identification

-   **API Discovery**: `id=streamstatus`

### Limitations

-   Currently, the API can only handle RTSP streams.
-   If there is something wrong with the information of a stream, that stream will be excluded from the 200 OK response of the CGI. Additionally an error print will be printed to the syslog.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### List all running streams on a device

1.  Request all running streams.
    
2.  Parse the JSON response that contains all running streams on the device.
    

See [getAllStreams](#getallstreams)

## API specification
### getAllStreams

Use this method to list all running streams on a device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamstatus.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getAllStreams"}'
```

```bash
POST /axis-cgi/streamstatus.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getAllStreams"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getAllStreams"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getAllStreams",    "data": {        "streams": \[            {                "destination\_address": "192.168.0.1",                "destination\_port": 32986,                "direction": "outgoing",                "encrypted": false,                "id": 11,                "media": "video",                "mime": "video/x-h264",                "multicast": false,                "options": {                    "audio": "0",                    "video": "1"                },                "path": "/axis-media/media.amp",                "source\_address": "192.168.0.141",                "source\_port": 50000,                "state": "playing",                "stream\_protocol": "RTP",                "transport\_protocol": "UDP",                "user\_agent": "GStreamer/1.22.0"            }        \]    }}
```

| Parameter | Data type | Description |
| --- | --- | --- |
| `apiVersion` | string | The requested API version in the format "Major.Minor". |
| `context` | string | The user sets this value and the application echoes it back in the response (optional). |
| `method` | string | The method that should be used. |
| `data` | object | Container for streams. |
| `streams` | array | Array of streams. |
| `destination_address` | string | The IPv4 or IPv6 address of the client. |
| `destination_port` | integer | The port of the client. |
| `direction` | string | Direction of the stream. Enum values: `incoming`, `outgoing` |
| `encrypted` | boolean | Indicates whether the stream is encrypted or not. |
| `id` | integer | The ID of the stream. It should be one or greater than one. |
| `media` | string | The media type. Enum values: `audio`, `metadata`, `video` |
| `mime` | string | The MIME type. Enum values: `audio/mpeg`, `application/x-onvif-metadata+xml`, `video/x-h264`, `audio/x-opus`, `audio/x-adpcm`, `audio/x-mulaw`, `audio/x-raw`, `image/jpeg`, `video/x-h265` |
| `multicast` | boolean | Optional. Indicates whether the stream uses multicast or not. |
| `options` | object | Container for URL options in a stream request. See [Public parameter description](/vapix/network-video/video-streaming/#public-parameter-description) and [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url). |
| `path` | string | The server path. |
| `source_address` | string | The IPv4 or IPv6 address of the server. |
| `source_port` | integer | The port of the server. |
| `state` | string | The current state of the streaming pipeline. Enum values: `paused`, `playing` |
| `stream_protocol` | string | The stream protocol that is used. |
| `transport_protocol` | string | The transport protocol that is used. Enum values: `TCP`, `UDP` |
| `user_agent` | string | Information about the client. |

**Return value - Error**

-   **HTTP Code**: `400`, `401`, `403`, `405`, `411`, `413`, `500`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getAllStreams",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Invalid JSON | `2101` | The request is not in valid Json format. |
| Method not supported | `2102` | The method in the request is not supported. |
| Required parameter missing | `2103` | Some required parameters are missing in the request. |
| Invalid parameter value specified | `2104` | Some parameters have an invalid value. |
| Authentication failed | `2106` | Couldn't authenticate. |
| Transport level error | `2107` | There is an error on the transport level. |
| Internal error | `1100` | There is an internal error. |

### getSupportedVersions

The API method can be used to retrieve a list of available supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamstatus.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/streamstatus.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |
| `apiVersions=<list of versions>` | Lists all supported major versions along with their highest supported minor version. e.g. \["1.4", "2.5"\]. |

**Return value - Error**

-   **HTTP Code**: `400`, `401`, `403`, `405`, `411`, `413`, `500`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getSupportedVersions",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| API version not supported | `2100` | The API version is not supported. |
| Invalid JSON | `2101` | The request is not in valid Json format. |
| Method not supported | `2102` | The method in the request is not supported. |
| Required parameter missing | `2103` | Some required parameters are missing in the request. |
| Invalid parameter value specified | `2104` | Some parameters have an invalid value. |
| Authorization failed | `2105` | Authorization failure. |
| Authentication failed | `2106` | Authentication failure. |
| Transport level error | `2107` | There is an error on the transport level. |
| Internal error | `1100` | There is an internal error. |