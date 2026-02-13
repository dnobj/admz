---
title: Image stabilization API
url: "https://developer.axis.com/vapix/network-video/image-stabilization-api/"
category: vapix
subcategory: network-video
sha256: a7e63df7ad7ef029774e4d3d24a89affcb60c55236e5127a64b52597e5e74d7b
scraped_at: "2026-01-09T15:19:59.865Z"
page_height: 33828
---

# Image stabilization API

## Description

The Image stabilization API lets you control different aspects of image stabilization. You can view values related to the current status of the image stabilization including if image stabilization is enabled, which type of image stabilization is configured as well as the configured values for EIS (Electrical Image Stabilization). You can also perform start or stop operations to enable or disable image stabilization.

The type of image stabilization can be changed between EIS and OIS (Optical Image Stabilization) on a supported device. Additional values can also be configured for EIS. The EIS specific values are margin, focal length and if demo mode should be enabled.

### Identification

-   **API discovery**: `id=image-stabilization`

### Obsoletes

EIS related parameters `Stabilizer`, `StabilizerMargin`, and `StabilizerFocalLength` in `/axis-cgi/param.cgi` are obsoleted.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Enable image stabilization

1.  Send a [getEnabled](#getenabled) request with `params.id=0`.
2.  Read the [getEnabled](#getenabled) response to know if image stabilization is enabled.
3.  Send a [setEnabled](#setenabled) request with `params.id=0` and `enabled=true` to enable image stabilization.
4.  Read the [setEnabled](#setenabled) response.

### Set image stabilization type to OIS

1.  Send a [getType](#gettype) request with `params.id=0`.
2.  Read the [getType](#gettype) response to know which type of image stabilization is currently configured.
3.  Send a [getCapabilities](#getcapabilities) request.
4.  Read the [getCapabilities](#getcapabilities) response to know if OIS is supported.
5.  Send a [setType](#settype) request with `params.id=0` and `type=OIS`.
6.  Read the [setType](#settype) response.

### Set manual focal length

1.  Send a [getCapabilities](#getcapabilities) request.
2.  Read the [getCapabilities](#getcapabilities) response to know if manual focal length is supported.
3.  Send a [setEISFocalLength](#seteisfocallength) request with `params.id=0` and specified `focalLength`.
4.  Read the [setEISFocalLength](#seteisfocallength) response.

## API specification
### getSupportedVersions

Use this method to get a list of supported major and minor API versions.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "1.1"\]    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `apiVersions` | Array | The supported API versions presented in the format "Major.Minor". |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getCapabilities

Use this method to list the image stabilization capabilities supported by your device.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getCapabilities"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getCapabilities",    "data": {        "channels": \[            {                "id": 0,                "EISSupport": true,                "OISSupport": false,                "manualFocalLength": true,                "minFocalLength": 7000,                "maxFocalLength": 70000            },            {                "id": 1,                "EISSupport": true,                "OISSupport": false,                "manualFocalLength": false            }        \]    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.channels` | Array | An array of image stabilization settings. |
| `data.channels.id` | Integer | The ID of the camera image channel. |
| `data.channels.EISSupport` | Boolean | Indicates if the camera supports EIS. |
| `data.channels.OISSupport` | Boolean | Indicates if the camera supports OIS. |
| `data.channels.manualFocalLength` | Boolean | Indicates if focal length is configured manually. |
| `data.channels.minFocalLength` | Integer | The minimum value for focal length with a range between 4000-120000. Only available when `manualFocalLength`\= `true`. |
| `data.channels.maxFocalLength` | Integer | The maximum value for focal length with a range between 4000-120000. Only available when `manualFocalLength`\= `true`. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getCapabilities",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getEnabled

Use this method to check if image stabilization is enabled or not.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getEnabled",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getEnabled",    "data": {        "enabled": true    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.enabled` | Boolean | Indicates if image stabilization is enabled. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getEnabled",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setEnabled

Use this method to enable or disable image stabilization.

**Request**

-   **Permission**: Admin, Operator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "setEnabled",    "params": {        "id": 0,        "enabled": true    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |
| `params.enabled` | Boolean | `true` to enable image stabilization. `false` to disable image stabilization. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabled",    "data": {}}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "setEnabled",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getType

Use this method to get which type of image stabilization (EIS or OIS) is configured for your device.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getType",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getType",    "data": {        "type": "EIS"    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.type` | String | The type of image stabilization configured. Enum values: `EIS`, `OIS` |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "getType",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setType

Use this method to configure which type of image stabilization (EIS or OIS) for your device.

**Request**

-   **Permission**: Admin, Operator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "setType",    "params": {        "id": 0,        "type": "EIS"    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |
| `params.type` | Integer | Specify the type of image stabilization to configure. Enum values: `EIS`, `OIS` |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setType",    "data": {}}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "setType",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getEISMargin

Use this method to get the configured margin for EIS. Return "Method not supported" if EIS is not supported.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getEISMargin",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getEISMargin",    "data": {        "margin": 4000    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.margin` | Integer | The configured margin for EIS with a range between 0–9999. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "getEISMargin",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setEISMargin

Use this method to configure margin for EIS. Return "Method not supported" if EIS is not supported.

**Request**

-   **Permission**: Admin, Operator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "setEISMargin",    "params": {        "id": 0,        "margin": 4000    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |
| `data.margin` | Integer | Specify the margin for EIS with a range between 0–9999. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getEISMargin",    "data": {        "margin": 4000    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.margin` | Integer | The configured margin for EIS with a range between 0–9999. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "setEISMargin",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getEISFocalLength

Use this method to get the manually configured focal length for EIS. Return "Method not supported" if EIS or manual focal length is not supported.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getEISFocalLength",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getEISFocalLength",    "data": {        "focalLength": 10000    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.focalLength` | Integer | The configured focal length for EIS with a range between `minFocalLength` and `maxFocalLength`. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "getEISFocalLength",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setEISFocalLength

Use this method to manually configure focal length for EIS. Return "Method not supported" if EIS or manual focal length is not supported.

**Request**

-   **Permission**: Admin, Operator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "setEISFocalLength",    "params": {        "id": 0,        "focalLength": 10000    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |
| `params.focalLength` | Integer | Specify the focal length to configure with a range between `minFocalLength` and `maxFocalLength`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setEISFocalLength",    "data": {}}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "setEISFocalLength",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getEISDemo

Use this method to check if demo is enabled for EIS. Return "Method not supported" if EIS is not supported.

**Request**

-   **Permission**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "getEISDemo",    "params": {        "id": 0    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getEISDemo",    "data": {        "demo": false    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.demo` | Boolean | Indicates if demo is enabled. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "getEISDemo",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setEISDemo

Use this method to enable or disable demo for EIS. Return "Method not supported" if EIS is not supported.

**Request**

-   **Permission**: Admin, Operator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1",    "context": "my context",    "method": "setEISDemo",    "params": {        "id": 0,        "demo": false    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version to use (optional). |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Container for the method specific parameters listed below. |
| `params.id` | Integer | The ID of the camera image channel. |
| `params.demo` | Boolean | `true` to enable demo. `false` to disable demo. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setEISDemo",    "data": {        "demo": false    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `data.demo` | Boolean | Indicates if demo is enabled. |

**Return value - Failure**

-   **HTTP Code**: `400 Bad request`, `401 Authentication failed`, `403 Authorization failed`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": "setEISDemo",  "error": {    "code": <integer error code>,    "message": "The error message"  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). Only available for `403` error. |
| `method` | String | The performed method. Only available for `403` error. |
| `error` | Object | The error object. |
| `error.code` | Integer | The error code. |
| `error.message` | String | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### General error codes

This table lists the general error codes that can occur for any API method. Method specific errors are listed under the respective descriptions.

| Code | Description |
| --- | --- |
| `1100` | Internal error. |
| `1200` | Invalid stabilization type. |
| `2101` | Invalid JSON. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing. |
| `2104` | Invalid parameter value specified. |
| `2105` | Authorization failed. |
| `2106` | Authentication failed. |
| `2100` | API version not supported. |