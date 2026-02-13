---
title: Video streaming indicator
url: "https://developer.axis.com/vapix/network-video/video-streaming-indicator/"
category: vapix
subcategory: network-video
sha256: c5b4a1d6cf721be91490a3f7b28f75b88f93aa1f9889b914460eadc4b9c25903
scraped_at: "2026-01-09T15:21:25.318Z"
page_height: 21918
---

# Video streaming indicator

## Description

The Video streaming indicator API makes it possible to superimpose an animation over the video stream to see if the stream is live even when the scene doesn’t contain any motion.

### Model

The API consists of the CGI `/axis-cgi/videostreamingindicator.cgi` and the following methods:

| Method | Description |
| --- | --- |
| `get` | Get the current settings for the indicator. |
| `set` | Update the settings for the indicator. |
| `on` | Enable the indicator. |
| `off` | Disable the indicator. |
| `show` | Show the indicator for 5 seconds (non-adjustable). |
| `getSupportedVersions` | Get versions of the API supported by the product. |

### Identification

-   **API Discovery**: `id=video-streaming-indicator`
-   **Property**: `Properties.VideoStreamingIndicator.VideoStreamingIndicator=yes`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Configure the indicator

Use the following examples to configure the look of the indicator.

#### Get configuration

1.  Get the current configuration.

```bash
{    "apiVersion": "1.0",    "method": "get"}
```

2.  Parse the JSON response.

a) Successful response example that gives the current configuration.

```bash
{    "apiVersion": "1.0",    "method": "get",    "data": {        "indicatorSize": "H2",        "position": "topLeft",        "color": "red",        "bgColor": "transparent",        "size": \[64, 64\],        "isActive": false    }}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "get",    "error": {        "code": 1003,        "message": "Invalid parameter"    }}
```

#### Set configuration

1.  Update the configuration.

```bash
{    "apiVersion": "1.0",    "method": "set",    "params": {        "indicatorSize": "H3",        "position": \[0.0, 0.0\],        "color": "semiTransparent",        "bgColor": "transparent"    }}
```

2.  Parse the JSON response.

a) Successful response example that gives the current configuration.

```bash
{    "apiVersion": "1.0",    "method": "set",    "data": {        "indicatorSize": "H3",        "position": \[0.0, 0.0\],        "color": "semiTransparent",        "bgColor": "transparent",        "size": \[128, 128\],        "isActive": false    }}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "set",    "error": {        "code": 1003,        "message": "Invalid parameter"    }}
```

### Enable and disable the indicator

Use the following examples to activate/deactivate the indicator.

#### Enable the indicator

1.  Enable the indicator.

```bash
{    "apiVersion": "1.0",    "method": "on"}
```

2.  Parse the JSON response.

a) Successful response example. The response will be empty.

```bash
{    "apiVersion": "1.0",    "method": "on",    "data": {}}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "on",    "error": {        "code": 1003,        "message": "Invalid parameter"    }}
```

**API references:**

[on](#on)

#### Disable the indicator

1.  Disable the indicator.

```bash
{    "apiVersion": "1.0",    "method": "off"}
```

2.  Parse the JSON response.

a) Successful response example. The response will be empty.

```bash
{    "apiVersion": "1.0",    "method": "off",    "data": {}}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "off",    "error": {        "code": 1003,        "message": "Invalid parameter"    }}
```

**API references:**

[off](#off)

## API specification
### get

Use `get` to receive the current configuration of the indicator.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "apiVersion": <string>,  "method": "get",  "context": <string>}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "method": "get",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the response. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="get"` | Specifies that the `get` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": <string>,  "method": "get",  "context": "<string>",  "data": {    "indicatorSize": <"small" | "medium" | "large" | "H1" | "H2" | "H3" | "H4" | "H5">,    "position": <"topLeft" | "topRight" | "bottomLeft" | "bottomRight"> | \[<decimal>, <decimal>\],    "color": <"black" | "white" | "red" | "semiTransparent">,    "bgColor": <"black" | "white" | "transparent">,    "size": \[<integer>,<integer>\],    "isActive": <boolean>  }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The current version of the API. |
| `context=<string>` |  | The string echoed back if it is provided by the client in the corresponding request. |
| `method="get"` |  | The method described in this section. |
| `data.indicatorSize` | `small` `medium` `large` `H1` `H2` `H3` `H4` `H5` ([1](#user-content-fn-1)) | The new size of the indicator. |
| `data.position` | `topLeft` `topRight` `bottomLeft` `bottomRight` | The position of the indicator, that can either be a predefined value or an array with x and y coordinates. Coordinates are normalized in the range `[-1.0, 1.0]`. |
| `data.color` | `black` `white` `red` `semiTransparent` | The color of the indicator. |
| `data.bgColor` | `black` `white` `transparent` | The background color of the indicator. |
| `data.size` |  | The size of the indicator’s bounding box. |
| `data.isActive` |  | Flag showing if the indicator is currently active or not. |

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### set

Use `set` to update the configuration of the indicator.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "apiVersion": <string>,  "method": "set",  "context": "<string>",  "params": {    "indicatorSize": <"small" | "medium" | "large" | "H1" | "H2" | "H3" | "H4" | "H5">,    "position": <"topLeft" | "topRight" | "bottomLeft" | "bottomRight"> | \[<decimal>, <decimal>\],    "color": <"black" | "white" | "red" | "semiTransparent">,    "bgColor": <"black" | "white" | "transparent">  }}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "method": "set",  "context": "<string>",  "params": {    "indicatorSize": <"small" | "medium" | "large" | "H1" | "H2" | "H3" | "H4" | "H5">,    "position": <"topLeft" | "topRight" | "bottomLeft" | "bottomRight"> | \[<decimal>, <decimal>\],    "color": <"black" | "white" | "red" | "semiTransparent">,    "bgColor": <"black" | "white" | "transparent">  }}
```

| Parameter | Valid value | Description |
| --- | --- | --- |
| `apiVersion` |  | The current version of the API. |
| `context=<string>` |  | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="set"` |  | Specifies that the `set` operation is performed. |
| `indicatorSize=<"small" | "medium" | "large">` | `small` `medium` `large` `H1` `H2` `H3` `H4` `H5` | _Optional_. Specifies the size of the indicator. |
| `position=<"topLeft" | "topRight" | "bottomLeft" | "bottomRight"> | [<decimal>,<decimal>]` | `topLeft` `topRight` `bottomLeft` `bottomRight` | _Optional_. Specifies the position of the indicator. The position can either be a predefined value or an array with x and y coordinates. Coordinates are normalized in the range `[-1.0, 1.0]`. |
| `color=<"black" | "white" | "red" | "semiTransparent">` | `black` `white` `red` `semiTransparent` | _Optional_. Specifies the color of the indicator. |
| `bgColor=<"black" | "white" | "transparent">` | `black` `white` `transparent` | _Optional_. Specifies the background color of the indicator. |

info

Any optional parameters omitted in the request will maintain their current value.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": <string>,  "method": "set",  "context": "<string>",  "data": {    "indicatorSize": <"small" | "medium" | "large" | "H1" | "H2" | "H3" | "H4" | "H5">,    "position": <"topLeft" | "topRight" | "bottomLeft" | "bottomRight"> | \[<decimal>, <decimal>\],    "color": <"black" | "white" | "red" | "semiTransparent">,    "bgColor": <"black" | "white" | "semiTransparent" | "transparent">,    "size": \[<integer>, <integer>\],    "isActive": <boolean>  }}
```

| Parameter | Valid value | Description |
| --- | --- | --- |
| `apiVersion` |  | The current version of the API. |
| `context=<string>` |  | The string echoed back if it is provided by the client in the corresponding request. |
| `method="set"` |  | The method described in this section. |
| `data.indicatorSize` | `small` `medium` `large` `H1` `H2` `H3` `H4` `H5` | The new size of the indicator. |
| `data.position` | `topLeft` `topRight` `bottomLeft` `bottomRight` | The position of the indicator, which can either be a predefined value or an array with x and y coordinates. Coordinates are normalized in the range `[-1.0, 1.0]`. |
| `data.color` | `black` `white` `red` `semiTransparent` | The color of the indicator. |
| `data.bgColor` | `black` `white` `transparent` | The background color of the indicator. |
| `data.size` |  | The size of the bounding box of the indicator. |
| `data.isActive` |  | Flag showing if the indicator is currently active or not. |

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### on

Use `on` to enable the indicator.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "apiVersion": <string>,  "method": "on",  "context": <string>}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "method": "on",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="on"` | Specifies that the `on` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": <string>,  "method": "on",  "context": "<string>",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method="on"` | The method described in this section. |

Successful calls also contains an empty data object in the response.

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### off

Use `off` to disable the indicator.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "apiVersion": <string>,  "method": "off",  "context": <string>}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "method": "off",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="off"` | Specifies that the `off` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": <string>,  "method": "off",  "context": "<string>",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method="off"` | The method described in this section. |

Successful calls also contains an empty data object in the response.

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### show

Use `show` to show the indicator for 5 seconds (non-adjustable).

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "apiVersion": <string>,  "method": "show",  "context": <string>}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "method": "show",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="show"` | Specifies that the `show` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": <string>,  "method": "show",  "context": "<string>",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method="show"` | The method described in this section. |

Successful calls also contains an empty data object in the response.

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### getSupportedVersions

Use `getSupportedVersions` to retrieve a list of supported API versions.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/videostreamingindicator.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/videostreamingindicator.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="getSupportedVersions"` | Specifies that the `getSupportedVersions` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersion": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method="getSupportedVersions"` | The method described in this section. |
| `data.apiVersion[]=<list of versions>` | The list of supported versions, with each major versions listed together with their highest supported minor version. |
| `<list of versions>` | List of <Major>.<Minor> versions, e.g. \["1.4", "2.5"\]. |

**Return value - Failure**

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

### Error codes

| Error code | Description |
| --- | --- |
| `1000` | Internal error. |
| `1001` | The requested API version is not supported. |
| `1002` | Invalid method. |
| `1003` | Invalid parameter. |
| `1004` | The provided input was invalid. |

## Footnotes

1.  "H1", "H2" and "H3" corresponds to "small", "medium" and "large". "H4" and "H5" are additional, larger sizes. [↩](#user-content-fnref-1)