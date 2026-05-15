---
title: Radar autotracking
url: "https://developer.axis.com/vapix/radar/radar-autotracking/"
category: vapix
subcategory: radar
sha256: c59329ded6e189b82ef78543eaaf7a0605eed9c492117fb316fd6bf781bf9dd3
scraped_at: "2026-01-09T15:22:04.570Z"
page_height: 75902
---

# Radar autotracking

## Description

The Axis Radar autotracking API makes it possible to configure the behavior of the autotracking software run on a radar unit such as the D2050–VE. The unit itself controls a PTZ camera through the `/axis-cgi/com/ptz.cgi`, which makes it possible to view the objects detected by the radar. The API can configure parameters such as PTZ camera IP address, credentials and mounting height and it can also be queried for information regarding Radar autotracking capabilities.

### Model

The API is built around the `/axis-cgi/radar-autotracking.cgi`, which makes it possible to control camera connections, camera mounting height, adjusting the camera pan/tilt offsets and switching the tracking between on and off.

The CGI consists of the following methods:

| Method | Description |
| --- | --- |
| `setCameraConnection` | Sets the camera’s connection. |
| `getCameraConnection` | Receives the current camera’s connection and connection state. |
| `setCameraMountingHeight` | Sets the camera’s mounting height. |
| `getCameraMountingHeight` | Receives the current camera’s mounting height and its allowed values. |
| `setCameraPanOffset` | Sets the camera’s pan offset. |
| `getCameraPanOffset` | Receives the current camera’s pan offset and its allowed values. |
| `saveCameraPanOffset` | Reads the pan position from a connected camera, which can be saved as a camera pan offset. |
| `setCameraTiltOffset` | Sets the camera’s tilt offset. |
| `getCameraTiltOffset` | Receives the current camera’s tilt offset and its allowed values. |
| `saveCameraTiltOffset` | Reads the tilt position from a connected camera, which can be saved as a camera tilt offset. |
| `setCameraZoomDegree` | Sets the camera’s zoom degree. |
| `getCameraZoomDegree` | Receives the current camera’s zoom degree and its allowed values. |
| `setTrackingEnabled` | Sets the tracking to enabled. |
| `getTrackingEnabled` | Receives the enabled tracking. |
| `setGuardTourEnabled` | Sets the guard tour to enabled. |
| `getGuardTourEnabled` | Receives the enabled guard tour. |
| `setGuardTourTime` | Sets the guard tour time. |
| `getGuardTourTime` | Receives the guard tour and its allowed values. |
| `setReturnToHomeEnabled` | Sets return to home to enabled. |
| `getReturnToHomeEnabled` | Receives the enabled return to home. |
| `setReturnToHomeTimeout` | Sets the return to home timeout. |
| `getReturnToHomeTimeout` | Receives the return to home timeout, including its min and max values. |
| `setObjectTypesToTrack` | Sets the object types to track. |
| `getObjectTypesToTrack` | Receives the tracks for the object types. |
| `getCapabilities` | Receives supported capabilities. |
| `getSupportedVersions` | Receives a list of supported API versions. |

### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Radar.Radar=yes`
-   **AXIS OS**: 7.10 and later
-   **Product category**: Axis product equipped with a security radar
-   **API discovery**: `id=radar-autotracking`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Camera connection

Use this example to configure the connection between the radar and camera. This is done during the setup process by entering the IP address of the camera and its login credentials, all of which can be cross-checked later on. The example also includes the steps required to receive the current IP address and credentials for the camera.

1.  View the current IP address, credentials and camera connection state.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraConnection",    "params": {}}'
```

```bash
GET /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraConnection",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that presents the current camera connection.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraConnection",    "data": {        "ip": "192.168.0.91",        "user": "operator",        "state": "connected"    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraConnection",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraConnection",    "params": {        "ip": "192.168.0.91",        "user": "operator",        "pass": "secret"    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraConnection",    "params": {        "ip": "192.168.0.91",        "user": "operator",        "pass": "secret"    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraConnection",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setCameraConnection",    "error": {        "code": 300,        "message": "Invalid value '192.168.0.91' for parameter 'ip'"    }}
```

### Adjust camera mounting height

Use this example to cross-check the mounting height of the camera sensor, which was originally entered during the setup process.

1.  View the current configured mounting height.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraMountingHeight",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraMountingHeight",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example presenting the current mounting height and the allowed values (in meters).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraMountingHeight",    "data": {        "value": 5.1,        "minValue": 1.0,        "maxValue": 16.0    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraMountingHeight",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraMountingHeight",    "params": {        "value": 5.1    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraMountingHeight",    "params": {        "value": 5.1    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersions": "1.0",    "context": "context",    "method": "setCameraMountingHeight",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setCameraMountingHeight",    "error": {        "code": 300,        "message": "Invalid value '8.1000' for parameter 'value'"    }}
```

### Adjust camera pan offset

Use this example to adjust the pan offset of the camera. This has to be done during the setup process, as the radar module needs to know what camera pan angle that corresponds to its own angle from the start.

1.  View the current camera pan offset.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraPanOffset",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraPanOffset",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that presents the current camera pan offset and allowed value (in degrees).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraPanOffset",    "data": {        "value": 118.35,        "minValue": -360.0,        "maxValue": 360.0    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraPanOffet",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis.cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraPanOffset",    "params": {        "value": 118.35    }}'
```

```bash
POST /axis.cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraPanOffset",    "params": {        "value": 118.35    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraPanOffset",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setCameraPanOffset",    "error": {        "code": 300,        "message": "Invalid value '375.1200' for parameter 'value'"    }}
```

### Save camera pan offset

Use this example to save the current camera pan position as a camera pan offset value. Once you have established a connection to the camera during the setup process, you will also be able to align the camera to the radar’s straight ahead direction and save this position as the camera’s pan offset.

1.  Save the current camera pan value as a camera pan offset.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraPanOffset",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraPanOffset",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraPanOffset",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "method": "saveCameraPanOffset",    "error": {        "code": 301,        "message": "No camera connected"    }}
```

### Adjust camera tilt offset

Use this example to adjust the tilt offset of the camera. This has to be done during the setup process and makes the tilt offset adjust to the slope of the ground.

1.  View the current camera tilt offset.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraTiltOffset",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraTiltOffset",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that presents the current camera tilt offset and allowed values (in degrees).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraTiltOffset",    "data": {        "value": -2.7,        "minValue": -10.0,        "maxValue": 10.0    }}
```

b. Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraTiltOffset",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraTiltOffset",    "params": {        "value": -1.2    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraTiltOffset",    "params": {        "value": -1.2    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraTiltOffset",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setCameraTiltOffset",    "error": {        "code": 300,        "message": "Invalid value '-10.1000' for parameter 'value'"    }}
```

### Save camera tilt offset

Use this example to save the current camera tilt position as a camera tilt offset value. This can be done once a connection to the camera has been established during the setup process and it becomes possible to aim the camera at the horizon and save the position as the camera tilt offset.

1.  Save the current camera tilt value as a camera tilt offset.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraTiltOffset",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraTiltOffset",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "saveCameraTiltOffset",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "saveCameraTiltOffset",    "error": {        "code": 301,        "message": "No camera connected"    }}
```

### Adjust camera zoom degree

Use this example to adjust the zoom degree of the camera. This is useful when the ground is uneven and less zoom is required to get a tracked object into the field of view of the camera.

1.  View the current camera zoom degree.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraZoomDegree",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraZoomDegree",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that will present the current camera zoom degree and the allowed values (in percent).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraZoomDegree",    "data": {        "value": 50.0,        "minValue": 0.0,        "maxValue": 100.0    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCameraZoomDegree",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraZoomDegree",    "params": {        "value": 50.0    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraZoomDegree",    "params": {        "value": 50.0    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setCameraZoomDegree",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setCameraZoomDegree",    "error": {        "code": 300,        "message": "Invalid value '100.10' for parameter 'value'"    }}
```

### Enable/disable tracking

Use this example to enable or disable the tracking that is performed by the radar PTZ tracking software. When tracking is enabled, the PTZ camera is controlled by the Radar autotracking software whenever an object is detected by the radar.

1.  Enable the current tracking.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getTrackingEnabled",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getTrackingEnabled",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getTrackingEnabled",    "data": {        "value": true    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getTrackingEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setTrackingEnabled",    "params": {        "value": true    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setTrackingEnabled",    "params": {        "value": true    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setTrackingEnabled",    "data": {}}
```

b) Failure response example.

```bash
{    "apiVersion": "1.0",    "method": "setTrackingEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

### Enable/disable guard tour

Use this example to enable or disable a guard tour between objects detected by the radar. When it is enabled, the Radar autotracking software will direct the PTZ at the objects detected in chronological order.

1.  Enable guard tour.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourEnabled",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourEnabled",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourEnabled",    "data": {        "value": true    }}
```

b) Failure response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourEnabled",    "params": {        "value": true    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourEnabled",    "params": {        "value": true    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourEnabled",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setGuardTourEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

### Adjust guard tour time

Use this example to adjust the time that the PTZ remains on each object during the guard tour. When the guard tour is enabled in the Radar autotracking software the PTZ will be directed to each object detected by the radar. The PTZ lingering time on each object depends on the configured guard tour time.

1.  View the current guard tour time.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourTime",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourTime",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that will present the current mounting height and the allowed values (in meters).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourTime",    "data": {        "value": 4.0,        "minValue": 1.0,        "maxValue": 60.0    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getGuardTourTime",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourTime",    "params": {        "value": 1.5    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourTime",    "params": {        "value": 1.5    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setGuardTourTime",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setGuardTourTime",    "error": {        "code": 300,        "message": "Invalid value '0.5000' for parameter 'value'"    }}
```

### Enable/disable return to home

Use this example to enable or disable the return to home-function. When it is enabled, the PTZ will be redirected towards the home position after an adjustable timeout.

1.  View the current return to home values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeEnabled",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeEnabled",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example. The response will give you the currently enabled status.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeEnabled",    "data": {        "value": true    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set new rules.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeEnabled",    "params": {        "value": true    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeEnabled",    "params": {        "value": true    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeEnabled",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setReturnToHomeEnabled",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

[getReturnToHomeEnabled](#getreturntohomeenabled)

[setReturnToHomeEnabled](#setreturntohomeenabled)

### Adjust return to home timeout

Use this example to adjust the timeout of the return to home function and receive information on the min/max limit of the timeout. Once the return to home function is enabled, the PTZ will be redirected towards the home position after the timeout.

1.  View the current return to home values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeTimeout",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeTimeout",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that will present the current timeout value as well as its min/max values for the timeout (in seconds).

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeTimeout",    "data": {        "value": 5,        "minValue": 1,        "maxValue": 300    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getReturnToHomeTimeout",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set new values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeTimeout",    "params": {        "value": 5    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeTimeout",    "params": {        "value": 5    }}
```

4.  Parse the JSON response.

a) Success response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setReturnToHomeTimeout",    "data": {}}
```

b) Failure response example.

```bash
{    "apiVersion": "1.0",    "method": "setReturnToHomeTimeout",    "error": {        "code": 300,        "message": "Invalid value '1000' for parameter 'timeout'"    }}
```

### Adjust object types to track

Use this example to select which type of objects you want to track. The objects are divided into one of the following categories: `small`, `humans`, `vehicles` and `unknown`, and whenever any of them have been selected, the autotracking software will direct the PTZ camera towards that particular object upon detection.

1.  View the current object types to track the values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getObjectTypesToTrack",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getObjectTypesToTrack",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example that will present the currently enabled tracking status for different objects types to track.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getObjectTypesToTrack",    "data": {        "small": false,        "human": true,        "vehicle": true,        "unknown": false    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getObjectTypesToTrack",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

3.  Set new rules.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "setObjectTypesToTrack",    "params": {        "small": false,        "human": true,        "vehicle": true,        "unknown": false    }}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "setObjectTypesToTrack",    "params": {        "small": false,        "human": true,        "vehicle": true,        "unknown": false    }}
```

4.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "setObjectTypesToTrack",    "data": {}}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "method": "setObjectTypesToTrack",    "error": {        "code": 300,        "message": "Invalid value '100' for parameter 'small'"    }}
```

### Supported capabilities

An API might exist in several different versions and supported capabilities may differ depending on what version you are using. This example will show you how to check which capabilities you can access from a particular version of Radar autotracking.

1.  View the current object types to track the values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getCapabilities",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getCapabilities",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCapabilities",    "data": {        "returnToHomeEnabled": {},        "returnToHomeTimeout": {            "minValue": 1,            "maxValue": 300        },        "objectTypesToTrack": {            "types": \["small", "human", "vehicle", "unknown"\]        }    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getCapabilities",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

### Get supported versions

Use this example to implement an application that uses Axis Radar autotracking. As an application might exists in several different versions, this example will show you how to write code that will check if the API version is supported before using the application.

1.  View a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "context",    "method": "getSupportedVersions",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "context",    "method": "getSupportedVersions",    "params": {}}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0"\]    }}
```

b) Failed response example.

```bash
{    "apiVersions": "1.0",    "context": "context",    "method": "getSupportedVersions",    "error": {        "code": 200,        "message": "JSON input error"    }}
```

### Camera connection state event

Use this example to receive information when the Radar module gets connected/disconnected to the PTZ camera or when auto tuning is run.

Start a subscription to the camera connection state event.

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=axis:RadarAutotracking/CameraConnection
```

## API specification
### getCameraConnection

This CGI method can be used to retrieve the current camera connection.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getCameraConnection data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraConnection",  "data": {    "ip": ip address to the PTZ camera,    "user": user name to login to the PTZ camera,    "state": state of the connection, possible values: disconnected, connecting, autotune, connected or connect\_failed  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraConnection",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setCameraConnection

This CGI method can be used to set the camera connection of the radar. Once the new connection parameters are set an attempt to establish a connection will be made. Using an empty IP address will cause a disconnect. Information on connection state can be found in [getCameraConnection](#getcameraconnection).

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

setCameraConnection data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `ip` | String | The camera’s IP address. |
| `user` | String | The username to log in to the camera. |
| `pass` | String | The password to log in to the camera. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCameraConnection",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setCameraConnection",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed [General error codes](#general-error-codes).

### getCameraMountingHeight

This CGI method can be used to retrieve the current mounting height and its allowed values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided be the client in the corresponding request",  "method":"getCameraMountingHeight",  "data": {    "value": mounting height in meters,    "minValue": minimum height in meters,    "maxValue": maximum height in meters  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setCameraMountingHeight

This CGI method can be used to set the mounting height of the radar. Information on allowed values can be found in [getCameraMountingHeight](#getcameramountingheight).

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

setCameraMountingHeight data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | The vertical mounting height of the camera, measured in meters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setMountingHeight",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setMountingHeight";  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getCameraPanOffset

This CGI method can be used to retrieve the current camera pan offset and its allowed values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraPanOffset",  "data": {    "value": camera pan offset in degrees,    "minValue": minimum camera pan offset in degrees,    "maxValue": maximum camera pan offset in degrees  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setCameraPanOffset

This CGI method can be used to set the camera pan offset of the radar. Information on allowed values can be found in [getCameraPanOffset](#getcamerapanoffset).

**Request**

-   **Security level**: Operator

```bash
POST /axi-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | The camera pan offset, measured in degrees. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCameraPanOffset",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setCameraPanOffset",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### saveCameraPanOffset

This CGI method can be used to read the current pan position from a connected camera and save it as a camera pan offset.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

saveCameraPanOffset data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "saveCameraPanOffset",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "saveCameraPanOffset",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

Specific error codes for saveCameraPanOffset

| Code | Definition | Description |
| --- | --- | --- |
| `301` | `INVALID_CONNECTION_ERROR` | Invalid connection to the camera |

General errors are listed in [General error codes](#general-error-codes).

### getCameraTiltOffset

This CGI method can be used to retrieve the current camera tilt offset and its allowed values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraTiltOffset",  "data": {    "value": camera tilt offset in degrees,    "minValue": minimum camera tilt offset in degrees,    "maxValue": maximum camera tilt offset in degrees  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraTiltOffset",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setCameraTiltOffset

This CGI method can be used to set the camera tilt offset of the radar. Information on allowed values can be found in [getCameraTiltOffset](#getcameratiltoffset).

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

setCameraTiltOffset data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | The camera tilt offset, measured in the degrees. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCameraTiltOffset",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setCameraTiltOffset",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### saveCameraTiltOffset

This CGI method can be used to read the current tilt position from a connected camera and save it as a camera tilt offset.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

saveCameraTiltOffset data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this values and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "saveCameraTiltOffset",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

Error codes for saveCameraTiltOffset

| Code | Definition | Description |
| --- | --- | --- |
| `301` | `INVALID_CONNECTION_ERROR` | Invalid connection to the camera |

General errors are listed in [General error codes](#general-error-codes).

### getCameraZoomDegree

This CGI method can be used to retrieve the current zoom degree and its allowed values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getCameraZoomDegree data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCameraZoomDegree",  "data": {    "value": zoom degree in percent,    "minValue": zoom degree in percent,    "maxValue": zoom degree in percent  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setCameraZoomDegree

This CGI method can be used to set the zoom degree (in percent) of the camera. Information on allowed values can be found in [getCameraZoomDegree](#getcamerazoomdegree).

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The clients sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | The camera zoom degree, measured in percent. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCameraZoomDegree",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getTrackingEnabled

This CGI method can be used to retrieve the current status of the enabled tracking.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getTrackingEnabled",  "data": {    "value": boolean value of tracking enabled  }}
```

**Return value- Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setTrackingEnabled

This CGI method can be used to either enable or disable the radar tracking.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Boolean | Must be set to either true or false to enable/disable tracking. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setTrackingEnabled",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setTrackingEnabled",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getGuardTourEnabled

This CGI method can be used to retrieve the current status of the enabled guard tour.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getGuardTourEnabled",  "data": {    "value": boolean value of tracking enabled  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setGuardTourEnabled

This CGI method can be used to either enable or disable the guard tour.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Boolean | Must be set to either true or false to enable/disable guard tour. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setGuardTourEnabled",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getGuardTourTime

This CGI method can be used to retrieve the current guard tour time and its allowed values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getGuardTourTime data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getGuardTourTime",  "data": {    "value": guard tour time in seconds,    "minValue": minimum guard tour time in seconds,    "maxValue": maximum guard tour time in seconds  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getGuardTourTime",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setGuardTourTime

This CGI method can be used to set the guard tour time. Information on allowed values can be found in [getGuardTourTime](#getguardtourtime).

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

setGuardTourTime data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | The guard tour time, measured in seconds. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setGuardTourTime",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setGuardTourTime",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getReturnToHomeEnabled

This CGI method can be used to retrieve the current status of return to home enabled.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getReturnToHomeEnabled data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getReturnToHomeEnabled",    "data": {    "value": boolean value of return to home enabled  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getReturnToHomeEnabled",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setReturnToHomeEnabled

This CGI method can be used to set return to home to enabled.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this values and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Boolean | Must be set to either true or false to enable/disable the return to home function. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setReturnToHomeEnabled",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setReturnToHomeEnabled",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getReturnToHomeTimeout

This CGI method can be used to retrieve the current return to home timeout as well as its min/max values.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getReturnToHomeTimeout",  "data": {    "value": timeout in seconds,    "minTimeout": minimum timeout in seconds,    "maxTimeout": maximum timeout in seconds  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setReturnToHomeTimeout

This CGI method can be used to set the return to home timeout.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `value` | Number | Sets the timeout in seconds. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setReturnToHomeTimeout",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setReturnToHomeTimeout",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getObjectTypesToTrack

This CGI method can be used to retrieve the currently enabled tracking status for different object types.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getObjectTypesToTrack data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented I the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getObjectTypesToTrack",  "data": {    "small": enabled tracking status for small objects,    "human": enabled tracking status for humans,    "vehicle": enabled tracking status for vehicles,    "unknown": enabled tracking status for unidentified objects  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getObjectTypesToTrack",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### setObjectTypesToTrack

This CGI method can be used to set the enabled tracking status for different object types.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

setObjectTypesToTrack data parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Contains the method specific parameters listed below. |
| `small` | Boolean | Must be set to either true or false to enable/disable tracking small objects. |
| `human` | Boolean | Must be set to either true or false to enable/disable tracking humans. |
| `vehicle` | Boolean | Must be set to either true or false to enable/disable tracking vehicles. |
| `unknown` | Boolean | Must be set to either true or false to enable/disable tracking unidentified objects. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setObjectTypesToTrack",    "data": {}}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setObjectTypesToTrack",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getCapabilities

This CGI method can be used to check which capabilities you can access from a particular version of the API. An API might exist in several different versions and the supported capabilities may differ depending on what version you are using.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar-autotracking.cgi
```

getCapabilities

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this value and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCapabilities",  "data": {    "returnToHomeEnabled": {},    "returnToHomeTimeOut": {      "minValue": ...,      "maxValue": ...    },    "objectTypesToTrack": {      "types": \[...\]    }  }}
```

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCapabilities",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

### getSupportedVersions

This CGI method can be used to retrieve supported API versions. The response consists of a list with the supported major versions and the highest supported minor versions. Please note that the version number is for the API as a whole and not for individual methods in the CGI.

**Request**

-   **Security level**: Operator
-   **Mehtod**: `POST`

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar-autotracking.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "context-id",    "method": "getSupportedVersions",    "params": {}}'
```

```bash
POST /axis-cgi/radar-autotracking.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "context-id",    "method": "getSupportedVersions",    "params": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version, presented in the format Major.Minor. |
| `context` | String | The client sets this values and the application echoes it back in the response (optional). |
| `method` | String | The performed operation. |

**Return value**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

### General error codes

The following table lists the general errors that can occur for any of the CGI methods. Method specific errors are listed in the API description for that method.

General error codes

| Code | Definition | Description |
| --- | --- | --- |
| `100` | UNSUPPORTED\_API\_VERSION | The requested API version is not supported by this implementation. |
| `102` | JSON\_KEY\_NOT\_FOUND\_ERROR | A mandatory input parameter was not found in the input. |
| `103` | JSON\_INVALID\_TYPE | The type of a provided JSON parameter was incorrect. |
| `200` | JSON\_INVALID\_ERROR | The provided JSON input was invalid. |
| `300` | PARAM\_INVALID\_VALUE\_ERROR | Invalid parameter value. |