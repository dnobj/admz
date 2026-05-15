---
title: PTZ Autotracker API
url: "https://developer.axis.com/vapix/network-video/ptz-autotracker-api/"
category: vapix
subcategory: network-video
sha256: 0a4968b9018c6d7983e9dbd0fff3d072f02b682fa237246e600aebf10b49a532
scraped_at: "2026-01-09T15:20:45.024Z"
page_height: 49940
---

# PTZ Autotracker API

## Description

The PTZ Autotracker API will show you the steps required to track moving objects with your Axis PTZ camera. The Autotracker itself comes pre-installed on supported cameras and the API consists of a number of CGIs used for querying status and information, and controlling the Autotracker functions, divided into the following sub-groups:

-   The general settings, including filters, GUI view settings, etc.
-   A switch with which you can turn on and off the profile tracking.
-   Functions for the metadata stream, which are also used to set the image rotation.
-   The on/off switch for the automatic profile (zone) triggers.
-   The profile (zone) configurations.

### Model

The API implements the following CGIs and methods:

The PTZ Autotracker POST CGIs

| URL | User | Description |
| --- | --- | --- |
| `http://<servername>/axis-cgi/ptz-autotracking/admin.cgi` | Admin | Checks and changes the tracker settings. |
| `http://<servername>/axis-cgi/ptz-autotracking/operator.cgi` | Operator | Checks and changes the tracker settings. |
| `http://<servername>/axis-cgi/ptz-autotracking/viewer.cgi` | Viewer | Checks the tracker settings. |

The PTZ Autotracker API functions

| Method | Description |
| --- | --- |
| `setViewportConfig` | Configures the Autotracker to include the camera’s rotation setting. |
| `getViewportConfig` | Returns the camera’s current rotation setting. |
| `setAutotrackingSettings` | Changes the general PTZ Autotracker settings. |
| `getAutotrackingSettings` | Lists the general PTZ Autotracker settings. |
| `setAutotrackingTarget` | Starts following an object visible in the video stream. |
| `getAutotrackingTarget` | Returns the currently tracked object. |
| `setApplicationSettings` | Sets general application settings. |
| `getApplicationSettings` | Returns general application settings. |
| `setAutotrackingState` | Enable/disables the automatic tracking in the zones. |
| `getAutotrackingState` | Returns the state of the automatic tracking in the zones. |
| `addProfile` | Creates a new profile. |
| `updateProfile` | Changes the settings for an existing profile. |
| `getProfile` | Returns the profile settings. |
| `deleteProfile` | Removes the profile. |

### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 9.10 and later
-   **API Discovery**: `id=autotracking-2`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Get supported versions

Use this example to check which version of the PTZ Autotracker that exists for your device.

1.  Request version support for the PTZ Autotracker protocol.

-   **User level**: Admin, Operator, Viewer

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSupportedVersions",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": "1.0"    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 1003    }}
```

### Set and get the current settings

Use this example to retrieve a list of the general settings for the PTZ Autotracker.

#### Get settings

1.  Request the current general settings for the autotracker.

-   **User level**: Admin, Operator, Viewer

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "data": {        "minObjectSize": {            "width": 7,            "height": 7,            "enabled": true        },        "minObjectLifespan": {            "time": 3,            "enabled": true        },        "profiles": \[            {                "id": 1,                "name": "Profile 1",                "preset": -1,                "enabled": false            },            {                "id": 2,                "name": "Profile 2",                "preset": -1,                "enabled": false            },            {                "id": 3,                "name": "Profile 3",                "preset": 5,                "enabled": false            }        \]    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "error": {        "code": 1003    }}
```

#### Update current settings

1.  Update the autotracker settings.

-   **User level**: Admin, Operator

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingSettings",    "params": {        "minObjectSize": {            "width": 3,            "height": 3,            "enabled": false        }    }}
```

2.  Parse the JSON response.

Successful example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingSettings",    "data": {}}
```

#### Set current viewport

1.  Request the autotracker to send a list of potential moving objects and visible zones (profiles) in the JSON format.

-   **User level**: Admin, Operator, Viewer

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setViewportConfig",    "params": {        "rotation": 180    }}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setViewPortConfig",    "data": {}}
```

## API specifications
### getSupportedVersions

This API method retrieves a list of supported major API versions along with their highest supported minor version.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`
-   **Content-Type**: `application/json`

JSON input parameters

```bash
{    "context": "abc",    "method": "getSupportedVersions",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<Major2.Minor2>",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameters | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `apiVersions` | Array | The supported API versions presented in the format "Major.Minor". |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "abc",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setAutotrackingSettings

This API method changes the general PTZ Autotracker settings. You will not be able change profile settings with this method and only JSON objects included in the request can be updated. So for example, if you want to remove a color combination, you need to send a JSON object with that id included.

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingSettings",    "params": {        "minObjectSize": {            "width": 7,            "height": 7,            "enabled": true        },        "minObjectLifespan": {            "time": 3,            "enabled": true        }    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `minObjectSize` | Object | The minimum object size that can cause a trigger in a zone. |
| `minObjectLifespan` | Object | The minimum lifespan (in seconds) for an object to cause a trigger in a zone. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingSettings",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains the method specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingSettings",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid profile ID |
| `1102` | Max number of profiles reached |
| `1103` | Invalid number of coordinates in zone (not equal x/y for example) |
| `1104` | Too many coordinates in zone |
| `1105` | Too few coordinates in zone |
| `1106` | Profile name empty |
| `1107` | Invalid preset |
| `1108` | Could not update zone |
| `1109` | No zone included |
| `1110` | Tracker not active |
| `1201` | Invalid color id |
| `1202` | No colours configured |
| `1301` | Invalid min object size width |
| `1302` | Invalid min object size height |
| `1401` | Invalid lifespan time |
| `1801` | Invalid value for timeout to home |
| `1802` | Invalid value for zoom limit |
| `1803` | Invalid value for max profile number |

See [General error codes](#general-error-codes) for a list of potential errors.

### getAutotrackingSettings

This API method lists available autotracker settings.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in thee response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "data": {        "minObjectSize": {            "width": 7,            "height": 7,            "enabled": true        },        "minObjectLifespan": {            "time": 3,            "enabled": true        },        "profiles": \[            {                "id": 1,                "name": "Profile 1",                "preset": -1,                "enabled": false            },            {                "id": 2,                "name": "Profile 2",                "preset": -1,                "enabled": false            },            {                "id": 3,                "name": "Profile 3",                "preset": 5,                "enabled": false            }        \]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used, presented in the format Major.Minor. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains the method specific parameters listed below. |
| `minObjectSize` | Object | The minimum size settings for an object that can be triggered in the zones. |
| `minObjectLifespan` | Object | The minimum lifespan (in seconds) for an object that can be triggered in the zones. |
| `profiles` | Array | A list of available profiles (zones) along with their settings. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingSettings",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setAutotrackingTarget

This API method starts the object tracking.

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingTarget",    "params": {        "targetId": 101    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `targetId` | Integer | The video-scene ID for the object that should be followed. `-1` is used to stop the tracking. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingTarget",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingTarget",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid object ID |

See [General error codes](#general-error-codes) for a list of potential errors.

### getAutotrackingTarget

This API method allows the application to operate in either manual or automatic mode. For example, if the `getAutotrackingState` returns `enabled = true`, it means that the application is in automatic mode.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingTarget",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingTarget",    "data": {        "targetId": 101    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `targetId` | Integer | The video-scene ID for the object that is followed. `-1` is used for not tracking. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingState",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid object ID |

See [General error codes](#general-error-codes) for a list of potential errors.

### setApplicationSettings

Use this method to start or stop PTZ Autotracker service.

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setApplicationSettings",    "params": {        "service": {            "active": true        }    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `service` | Object | Container for active state. |
| `active` | Boolean | `true`: Start the service.  
`false`: Stop the service. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setApplicationSettings",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setApplicationSettings",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getApplicationSettings

Use this method check if the Autotracker service is running.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getApplicationSettings",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getApplicationSettings",    "data": {        "service": {            "active": true        }    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `service` | Object | Container for active state. |
| `active` | Boolean | `true`: The service is running.  
`false`: The service is stopped. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getApplicationSettings",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setViewportConfig

This API method sets the viewport rotation. Supported rotation values are between 0 and 180 degrees.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setViewportConfig",    "params": {        "rotation": 180    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `rotation` | Integer | Rotation value of the camera. Only values between 0 and 180 are supported. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setViewportConfig",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setViewportConfig",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid object ID |

See [General error codes](#general-error-codes) for a list of potential errors.

### getViewportConfig

This API method returns the value set by the `setViewportConfig`, or a negative value if nothing has been set.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getViewportConfig",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getViewportConfig",    "data": {        "rotation": 180    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains response specific parameters. |
| `rotation` | Integer | The camera rotation. `-1` will be used if rotation hasn’t been initialized, otherwise a value of either 0 or 180 will be used.. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getViewportConfig",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid object ID |

See [General error codes](#general-error-codes) for a list of potential errors.

### Object stream description

Once a viewport has been configured, the application will start sending metadata on the camera’s event channel such as this:

```bash
<MESSAGE > ---- Event ------------------------<MESSAGE > Global Declaration Id: 165<MESSAGE > Local Declaration Id: 1<MESSAGE > Producer Id: 38<MESSAGE > Timestamp: 1549289932.405513<MESSAGE > \[jsonframe = '{"objects":\[{"id":11215,"x":0.4176,"y":0.3057,"width":0.01257,"height":0.04077},{"id":11210,"x":0.3989,"y":0.239,"width":0.008301,"height":0.04822},{"id":11205,"x":0.7885,"y":0.03162,"width":0.0459,"height":0.04077}\],"zones":\[{"profileId":1,"zoneType":0,"polygon":\[0.2888,0.3782,0.3907,0.3679,0.4277,0.4849,0.3054,0.5005\]}\]}'\] {onvif-data}<MESSAGE > \[tnsaxis:topic0 = 'CameraApplicationPlatform'\]<MESSAGE > \[tnsaxis:topic2 (streamObjects) = 'streamObjects' (streamObjects)\] {isApplicationData}<MESSAGE > \[tnsaxis:topic1 (PtzAutotracking) = 'PtzAutotracking' (PtzAutotracking)\]
```

This example shows the metadata with three moving objects and one zone (with four corners) visible in the video stream. Zone coordinates may be outside the \[0,1\] range, as they can be outside the visible screen. All x- and y-coordinates range between 0 and 1, where \[0,0\] is the top left corner and \[1,1\] is bottom right.

```bash
{    "object": \[        {            "id": 11215,            "x": 0.4176,            "y": 0.3057,            "width": 0.01257,            "height": 0.04077        },        {            "id": 11210,            "x": 0.3989,            "y": 0.239,            "width": 0.008301,            "height": 0.04822        },        {            "id": 11205,            "x": 0.7885,            "y": 0.3162,            "width": 0.0459,            "height": 0.04077        }    \],    "zones": \[        {            "profileId": 1,            "zoneType": 0,            "polygon": \[0.2888, 0.3782, 0.3907, 0.3679, 0.4277, 0.4849, 0.3054, 0.5005\]        }    \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `objects` | Array | A list of moving objects visible on screen. |
| `id` | Integer | The object ID that will be used when starting manual tracking. |
| `x` | Double | The X coordinate of the top left corner of the object. |
| `y` | Double | The Y coordinate of the top left corner of the object. |
| `width` | Double | The object width. |
| `height` | Double | The object height. |
| `zones` | Array | A list of zones visible on screen. |
| `profileId` | Integer | The zone ID. |
| `zoneType` | Integer | The zone type. |
| `polygon` | Array | A list of \[x,y\] coordinates. Represents the corner of the profile/zone. |

### setAutotrackingState

This API method sets the application to either manual or automatic mode. If the autotracking state is enabled, it will be set to automatic mode and the first object that enters a zone will automatically trigger the tracking. When the autotracking is set to manual there is no automatic triggering active, which means that zones and profiles are turned off.

**Request**

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingState",    "params": {        "enabled": true    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `enabled` | Boolean | The tracking option status. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingState",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains method specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setAutotrackingState",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getAutotrackingState

This API method retrieves the application in either manual or automatic mode. If `getAutotrackingState` returns `enabled = true`, it means that the application is in automatic mode.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingState",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingState",    "data": {        "enabled": true    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains the method specific parameters. |
| `enabled` | Boolean | Determines whether tracking is set to automatic or manual. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getAutotrackingState",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### addProfile

This API method adds a profile to the PTZ Autotracker settings.

**Request**

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "addProfile",    "params": {        "name": "Profile 1",        "preset": -1,        "enabled": false,        "polygon": \[0.426, 0.574, 0.326, 0.774, 0.526, 0.774\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `name` | String | The profile name (optional). |
| `preset` | Integer | The number of connected presets. `-1` if no preset is connected. |
| `enabled` | Boolean | True if a profile/zone is enabled. |
| `polygon` | Array | An array containing the floats, such as a three point polygon (`[x[0], y[0], x[1], y[1], x[2], y[2]]`). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "addProfile",    "data": {        "id": 1,        "name": "Profile 1",        "preset": -1,        "enabled": false    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains method specific parameters. |
| `id` | Integer | The profile ID. |
| `name` | String | The profile name. |
| `preset` | Integer | The number of connected presets. `-1` if no preset is connected. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "addProfile",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1102` | Max number of profiles reached |
| `1103` | Invalid number of coordinates in zone (not equal x/y for example) |
| `1104` | Too many coordinates in zone |
| `1105` | Too few coordinates in zone |
| `1109` | No zone included |

See [General error codes](#general-error-codes) for a list of potential errors.

### getProfile

This API method fetches all settings associated with a profile.

**Request**

-   **User level**: Admin, Operator, Viewer
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getProfile",    "params": {        "id": 1    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `id` | Integer | The ID for the requested profile. |

**Response value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getProfile",    "data": {        "id": 1,        "name": "Profile 1",        "preset": -1,        "enabled": false,        "polygon": \[0.426, 0.574, 0.326, 0.774, 0.526, 0.774\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains method specific parameters. |
| `id` | Integer | The profile ID. |
| `name` | String | The profile name. |
| `preset` | Integer | The number of connected presets. `-1` if no preset is connected. |
| `enabled` | Boolean | Set to true if this profile/zone has been enabled. |
| `polygon` | Array | An array containing floats, such as a three point polygon (`[x[0], y[0], x[1], y[1], x[2], y[2]]`). |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getProfile",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### updateProfile

This API method updates the PTZ Autotracker profile settings. As with other interfaces, the JSON objects sent are the ones that will be updated, for example, if only `id` and `name` are included in the request, only those will be updated, while `polygon` and other settings will remain unchanged.

The `polygon` array is a list of x and y coordinates that corresponds to the corners of the polygon (between 3 and 10 corners) currently shown by the video stream on the camera.

**Request**

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "updateProfile",    "params": {        "id": 1,        "name": "Profile 1",        "preset": -1,        "enabled": false,        "polygon": \[0.426, 0.574, 0.326, 0.774, 0.526, 0.774\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API in the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `id` | Integer | The ID of the requested profile. |
| `name` | String | The profile name. |
| `preset` | Integer | The number of connected presets. `-1` if no preset is connected. |
| `enabled` | Boolean | True if a profile/zone is enabled. |
| `polygon` | Array | An array containing the floats, such as a three point polygon (`[x[0], y[0], x[1], y[1], x[2], y[2]]`). |

**Response value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "updateProfile",    "data": {        "id": 1,        "name": "Profile 1",        "preset": -1,        "enabled": false    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used, presented in the format "Major.Minor". |
| `context` | String | A text string that will be echoed back as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains method specific parameters. |
| `id` | Integer | The profile ID. |
| `name` | String | The profile name. |
| `preset` | Integer | The number of connected presets. `-1` if no preset is connected. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "updateProfile",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1103` | Invalid number of coordinates in zone (not equal x/y for example) |
| `1104` | Too many coordinates in zone |
| `1105` | Too few coordinates in zone |

See [General error codes](#general-error-codes) for a list of potential errors.

### deleteProfile

This API method deletes a PTZ Autotracker profile.

**Request**

-   **User level**: Admin, Operator
-   **Method**: `POST`

JSON input parameters

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "deleteProfile",    "params": {        "id": 1    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version the format "Major.Minor". |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params` | Object | Contains method specific parameters. |
| `id` | Integer | The ID of the requested profile. |

**Response value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "deleteProfile",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The method that was performed. |
| `data` | Object | Contains method specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "deleteProfile",    "error": {        "code": 1003    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used. |
| `context` | String | A text string that will be echoed back as long as it was provided by the user in the corresponding request (optional). |
| `method` | String | The performed method. |
| `code` | Integer | The error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `1101` | Invalid profile ID |

See [General error codes](#general-error-codes) for a list of potential errors.

### General error codes

This table lists the general error codes that can occur for any API method. Method specific errors are listed under the respective descriptions.

| Code | Description |
| --- | --- |
| `1001` | The provided JSON input was invalid. |
| `1002` | No Method name tag found in request. |
| `1003` | Method not supported. |
| `1004` | Parameter tag ("params") required, but missing. |
| `1005` | Required parameter missing. |
| `1006` | Invalid value of parameter. |
| `1007` | Internal error. |