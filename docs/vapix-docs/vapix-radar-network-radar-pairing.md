---
title: Network Radar Pairing
url: "https://developer.axis.com/vapix/radar/network-radar-pairing/"
category: vapix
subcategory: radar
sha256: a97336e655f51039c0b4efc5eb2c3b6ce651e38e15374184b9e9f16a45fea8a5
scraped_at: "2026-01-09T15:22:02.165Z"
page_height: 16406
---

# Network Radar Pairing

The VAPIX® Network Radar Pairing API makes it possible to add a radar sensor input to cameras with no built-in hardware support. The camera can then be used to configure radar sensor settings.

The radar will appear just like a built-in hardware radar sensor and can be interacted with through the common platform events/action interface available on the camera.

## Identification

-   **API Discovery**: `id=network-radar-pairing`

## Limitations

This API is not supported by all devices.

The radar view video stream doesn't have a separate image source for the radar view stream when active on a camera. Instead, the radar view is drawn as an overlay above the image video stream and will not mask the image.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Configure and activate a network radar pairing

The following examples will show you how to configure the address and settings required for the camera to use an Axis radar as a radar sensor. Additional examples can be found in the [API Specifications](#api-specifications) chapter below.

1.  Send a [setRadarConnection](#setradarconnection) request with credentials for the radar connection.
2.  Send a [setActive](#setactive) request to activate the connection.
3.  Send a [getRadarConnection](#getradarconnection) request to check the state.

## API Specifications
### getRadarConnection

Retrieve the network radar pairing configuration and all of its setting information.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#getRadarConnection" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarConnection"}'
```

```bash
POST /networkradarpairing.cgi#getRadarConnectionHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarConnection"}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarConnection",    "data": {        "address": "192.168.0.90",        "user": "john",        "state": "ok"    }}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getRadarConnection",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### setRadarConnection

Set the network radar pairing configuration and its information.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#setRadarConnection" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setRadarConnection",    "params": {        "address": "192.168.0.90",        "user": "john",        "password": "doe",        "state": "ok",        "tls-certificate-cn": "axis-1234567890ab-eccp256-1"    }}'
```

```bash
POST /networkradarpairing.cgi#setRadarConnectionHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setRadarConnection",    "params": {        "address": "192.168.0.90",        "user": "john",        "password": "doe",        "state": "ok",        "tls-certificate-cn": "axis-1234567890ab-eccp256-1"    }}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setRadarConnection",    "data": {}}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setRadarConnection",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### clearConfiguration

Clear all stored configurations from the network radar pairing. The request will fail if the function is active.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#clearConfiguration" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "clearConfiguration"}'
```

```bash
POST /networkradarpairing.cgi#clearConfigurationHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "clearConfiguration"}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "clearConfiguration",    "data": {}}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "clearConfiguration",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### getActive

Retrieve the activation state of the network radar pairing. The method will fail is no configuration can be located.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#getActive" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getActive"}'
```

```bash
POST /networkradarpairing.cgi#getActiveHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getActive"}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getActive",    "data": {        "active": true    }}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getActive",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### setActive

Activate an already configured network radar pairing. The method will fail is no configuration can be located. If the active state of the network radar pairing already matches the state in the request, it will succeed.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#setActive" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setActive",    "params": {        "active": true    }}'
```

```bash
POST /networkradarpairing.cgi#setActiveHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setActive",    "params": {        "active": true    }}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setActive",    "data": {}}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setActive",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### getSupportedVersions

Retrieve a list containing all major and minor API versions supported by the device.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/networkradarpairing.cgi#getSupportedVersions" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /networkradarpairing.cgi#getSupportedVersionsHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions"}
```

**Responses**

_Successful response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

_Error response_

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

See [Parameter descriptions](#parameter-descriptions) for a detailed parameter list.

### Parameter descriptions

**`getRadarConnection` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getRadarConnection"` |  | The API method that is called in the request. |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="getRadarConnection"` |  | The requested API method. |
| `address=<string>` | `192.168.0.90` | The IP address. |
| `user=<string>` | "john" | The user name. |
| `state=<string>` | `failed` | The current state of the network radar pairing.  
Valid values:  
`failed`: Catch all failure statuses.  
`address-failed`: Address resolution failed.  
`connect-failed`: Connecting to the radar device failed.  
`authentication-failed`: Authentication to the radar device failed.  
`transfer-failed`: Data transfer failed.  
`not-configured`: There is no configured Network Radar Pairing.  
`not-active`: The Network Radar Pairing is not active.  
`ok`: Configured, active and no error. |

**`setRadarConnection` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="setRadarConnection"` |  | The API method that is called in the request. |
| `address=<string>` | `192.168.0.90` | The IP address. |
| `user=<string>` | "john" | The user name. |
| `password=<string>` | "doe" | The remote radar account password.  
Minimum: 1  
Maximum: 64 |
| `tls-certificate-cn=<string>`  
_Optional_ | "axis-1234567890ab-eccp256-1" | The common name for which the remote radar's certificate is issued. |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="setRadarConnection"` |  | The requested API method. |

**`clearConfiguration` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="clearConfiguration"` |  | The API method that is called in the request. |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="clearConfiguration"` |  | The requested API method. |

**`getActive` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getActive"` |  | The API method that is called in the request. |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="getActive"` |  | The requested API method. |
| `active=<boolean>` | `true` | Valid values:  
`true`, `false` |

**`setActive` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="setActive"` |  | The API method that is called in the request. |
| `active=<boolean>` | `true` | Valid values:  
`true`, `false` |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="setActive"` |  | The requested API method. |

**`getSupportedVersions` parameters**

_Request_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version that is used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The user sets this value in the request and the application will echo it back in the response. |
| `method="getSupportedVersions"` |  | The API method that is called in the request. |

_Response_

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 1.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method="getSupportedVersions"` |  | The requested API method. |
| `apiVersions=<string>` | 1.0 | A list containing all supported major versions along with their highest minor version, such as `1.0` and `1.2`. |

**`Error response` parameters**

| Parameter | Example value | Description |
| --- | --- | --- |
| `apiVersion=<string>` | 2.0 | The API version used in the request. |
| `context=<string>`  
_Optional_ | _my context_ | The context set by the user in the request. |
| `method=<string>` |  | The requested API method. |
| `error.code=<integer>` | `1100` | The error code. |
| `error.message=<string>` | Internal error. | The error message for the corresponding error code. |

_Error codes_

| JSON code | Error code | Error message |
| --- | --- | --- |
|  | `2100` | API version not supported. |
| `400 Bad request` | `2101` | Invalid JSON. |
|  | `2102` | Method not supported. |
|  | `2103` | Required parameter missing. |
|  | `2104` | Invalid parameter value specified. |
| `401 Authentication failed` | `2106` | Authentication failed. |
| `403 Authorization failed` | `2105` | Authorization failed. |
| `405 Method not allowed` | `2107` | Transport level error. |
| `411 Length required` | `2107` | Transport level error. |
| `413 Payload too large` | `2107` | Transport level error. |
|  | `2200` | Configuration cannot be changed or removed while enabled. |
|  | `2201` | Missing configuration. |
|  | `2202` | Usability test of the configuration failed. |
| `500 Internal error` | `1100` | Internal error. |