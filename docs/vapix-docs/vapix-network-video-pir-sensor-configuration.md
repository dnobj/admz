---
title: PIR sensor configuration
url: "https://developer.axis.com/vapix/network-video/pir-sensor-configuration/"
category: vapix
subcategory: network-video
sha256: 340fcfbd92b45111c9429856cc9070a162474940348a02e8e2e145564bf1ed32
scraped_at: "2026-01-09T15:20:41.256Z"
page_height: 17328
---

# PIR sensor configuration

The PIR sensor configuration API helps you list and configure the sensitivity of the PIR (passive infrared) sensors on your Axis device.

## Overview

The API uses `/axis-cgi/pirsensor.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `listSensors` | Lists all available PIR sensors. |
| `getSensitivity` | Retrieves the sensitivity set for a sensor. |
| `setSensitivity` | Sets the sensitivity for a sensor. |
| `getSupportedVersions` | Retrieves a list containing API versions supported by your product. |

info

Please note that this API is only applicable on devices with configurable PIR sensors.

### Identification

-   **API Discovery**: `id=pir-sensor-configuration`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Configure the PIR sensors on a device

These examples will show you how to update the sensitivity of the PIR sensor on your device.

**List available PIR sensors**

1.  Request a listing of the PIR sensors on your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "listSensors"}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "listSensors"}
```

2.  Parse the JSON response.

a) Successful response example. This response will list all sensors, and their IDs, on your device. If a sensor supports configurable sensitivity its entry will contain the parameter `sensitivityConfigurable` with the value `true`, while the parameter `sensitivity` will be showing the sensitivity value. Non configurable sensors will not list sensitivity in its entry and will instead contain the parameter `sensitivityConfigurable` with the value `false`. The sensor ID is used to identify the specific sensor when implementing or receiving the configured sensitivity.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "listSensors",    "data": {        "sensors": \[            {                "id": 0,                "sensitivityConfigurable": true,                "sensitivity": 0.05098038911819458            }        \]    }}
```

b) Successful response example. This response lists two sensors on the device, one of which is configurable.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "listSensors",    "data": {        "sensors": \[            {                "id": 12,                "sensitivityConfigurable": false            },            {                "id": 7,                "sensitivityConfigurable": true,                "sensitivity": 0.05098038911819458            }        \]    }}
```

c) Error response example.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "listSensors",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

**Set PIR sensor sensitivity**

1.  Set the sensitivity value for a PIR sensor.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setSensitivity",    "params": {        "id": 0,        "sensitivity": 0.5    }}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setSensitivity",    "params": {        "id": 0,        "sensitivity": 0.5    }}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setSensitivity"}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setSensitivity",    "error": {        "code": 2201,        "message": "Sensor does not have configurable sensitivity"    }}
```

**Retrieve PIR sensor sensitivity**

1.  Retrieve the configured PIR sensor’s sensitivity.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getSensitivity",    "params": {        "id": 0    }}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getSensitivity",    "params": {        "id": 0    }}
```

2.  Parse the JSON response.

a) The response will present you with the configured sensitivity information. Please note that this value may not be exactly the same as the one set with `setSensitivity` due to the accuracy of your senor’s sensitivity.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSensitivity",    "data": {        "sensitivity": 0.05098038911819458    }}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSensitivity",    "error": {        "code": 2200,        "message": "Invalid sensor ID"    }}
```

## API specifications
### listSensors

This method should be used when you want to list all PIR sensors on your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listSensors"}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listSensors"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="listSensors"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listSensors",  "data": {    "sensors": \[      {        "id": <integer>,        "sensitivityConfigurable": true,        "sensitivity": <number>      },      {        "id": <integer>,        "sensitivityConfigurable": false      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listSensors"` | The requested method. |
| `data.sensors[]` | Lists all sensors along with their features and data. |
| `data.sensors[].id<int>` | The sensor identifier. |
| `data.sensors[].sensitivityConfigurable<boolean>` | Indicator for whether the sensor sensitivity can be configured `true` or not `false`. |
| `data.sensors[].sensitivity<number>` | The sensor’s configured sensitivity, ranging from 0 to 1 (optional). |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<string>` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSensitivity

This method should be used when you want to retrieve the configured sensitivity of a specific sensor.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSensitivity"  "params": {    "id": <integer>  }}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSensitivity"  "params": {    "id": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSensitivity"` | The method that should be used. |
| `params` | Parameters retrieved by the method. |
| `params.id<int>` | The sensor identity getting its sensitivity configured. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSensitivity",  "data": {    "sensitivity": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSensitivity"` | The requested method. |
| `data.sensitivity<number>` | The configured sensitivity of the sensor, ranging from 0 to 1. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<string>` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| JSON code | Description |
| --- | --- |
| `2200` | Invalid sensor id. |
| `2201` | Sensor does not have configurable sensitivity. |

### setSensitivity

This method should be used when you want to configure the sensitivity of a specific sensor.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setSensitivity"  "params": {    "id": <integer>,    "sensitivity": <number>  }}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setSensitivity"  "params": {    "id": <integer>,    "sensitivity": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setSensitivity"` | The method that should be used. |
| `params` | Parameters retrieved by the method. |
| `params.id<int>` | The sensor identity getting its sensitivity configured. |
| `params.sensitivity<number>` | The sensitivity that should be set, ranging from 0 to 1. Please note that the resulting sensitivity may not match the requested value due to the accuracy of the configuration of the sensor and it will be rounded to a supported value. The client can then use `getSensitivity` or `listSensors` to query for the value. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setSensitivity"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setSensitivity"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<string>` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| JSON code | Description |
| --- | --- |
| `2200` | Invalid sensor id. |
| `2201` | Sensor does not have configurable sensitivity. |

### getSupportedVersions

This method should be used when you want to list all API versions supported by your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/pirsensor.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/pirsensor.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[ "<Major1>.<Minor1>", "<Major2>.<Minor2>" \]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `data.apiVersions[]=<list of versions>` | A list containing all supported major versions along with their highest minor version, e.g. `["1.4", "2.5"]`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<string>` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

| JSON code | Description |
| --- | --- |
| `1100` | Internal error |
| `2100` | API version not supported |
| `2101` | Invalid JSON |
| `2102` | Method not supported |
| `2103` | Required parameter missing |
| `2104` | Invalid parameter value specified |