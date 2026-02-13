---
title: Radar image
url: "https://developer.axis.com/vapix/radar/radar-image/"
category: vapix
subcategory: radar
sha256: ef596f5cea156f2e685c8a1700c9fc46bada18e65ca4620cc11f116d48434474
scraped_at: "2026-01-09T15:22:09.011Z"
page_height: 64763
---

# Radar image

## Description

Use the radar image API to:

-   configure properties of virtual video streams generated to show information from a radar sensor.
-   setting up a reference map for the video stream and align the radar data.

The virtual video stream consist of the following elements:

-   **Background:** Either a solid color or a reference map added by the user.
-   **Grid:** Marks the radar field of view and give the user a way to determine the distance to the tracked object.
-   **Echoes:** Raw responses from the radar sensor.
-   **Radar tracks:** Echoes grouped together from the same object, filtered to remove uninteresting ones.
-   **Radar track trails:** Tracks history displayed in the image.

Supported CGIs:

| CGI | Usage |
| --- | --- |
| `/axis-cgi/radar/uploadradarimage.cgi` | Upload an image and set it as a reference map in the video stream. |
| `/axis-cgi/radar/replaceradarimage.cgi` | Replace an already calibrated reference map in the video stream. |
| `/axis-cgi/radar/radarimage.cgi` | Control the calibration process and handle parameters for the virtual video stream. |

Supported methods:

| Method | Usage |
| --- | --- |
| `uploadImage` | Response to `/axis-cgi/radar/uploadradarimage`.cgi. |
| `replaceImage` | Response to `/axis-cgi/radar/replaceradarimage`.cgi. |
| `startCalibrationTracking` | Start or restart the reference map calibration using tracking. |
| `setCalibrationPoint` | Set the coordinates in the reference map used by the back-end to calibrate the radar. |
| `stopCalibrationTracking` | Stop tracking and store the result if calibration was successful. |
| `abortCalibration` | Stop tracking and reset all parameters related to the current reference map. |
| `resetCalibration` | Stop tracking, remove the current reference map and reset the parameters related to the reference map. |
| `getCalibrationState` | Return the current state of calibration. |
| `setManualRadarPosition` | Manually set a point in the reference map as the new radar position. |
| `setManualCalibrationPoint` | Manually set a point in the reference map used to calibrate the radar. |
| `setColorScheme` | Set a predefined collection of colors used for the virtual video stream. |
| `getColorScheme` | Get current color scheme and a list of possible color scheme values. |
| `setTrailLifetime` | Set how many seconds a trail should be visible. |
| `getTrailLifetime` | Get the current value for trail lifetime and its minimum and maximum value. |
| `setGridOpaque` | Set opaque value of the grid. |
| `getGridOpaque` | Get opaque value for the grid and minimum and maximum opaque value. |
| `setEchoVisualizationLevel` | Set level for the visualization of echoes. |
| `getEchoVisualizationLevel` | Get current setting for the visualization of echoes. |
| `getImageMetricSize` | Get the metric size of the image to be able to transform between pixels and meters. |
| `getFilename` | Get the filename for the currently used reference map. |
| `getSupportedVersions` | Get a list of supported API versions. |

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Overview
### Model

The API consists of three CGI calls which should be called using the `HTTP POST` method. The calls `/axis-cgi/radar/uploadradarimage.cgi` and `/axis-cgi/radar/replaceradarimage.cgi` use `multipart/form-data` for sending binaries while `/axis-cgi/radar/radarimage.cgi` accept JSON formatted data. All three return JSON formatted data. This all give the user the possibility to:

-   Upload an image and set it as a reference map.
-   Replace a reference map with a new image.
-   Calibrate the radar so it aligns the grid and radar tracks to a reference map.
-   Fetch image parameters like color scheme, opaque level, echo visualization level, filename and trail lifetime.
-   Set how long a trail should be displayed.
-   Set color scheme.
-   Set grid opaque.
-   Set level of echo visualization.
-   Request a list with the supported API versions.

### Identification

-   **Property**: `Properties.Radar.Radar=yes`
-   **Property**: `Properties.AddOnFramework.AddOnFramework=yes`
-   **Property**: `Properties.AddOnFramework.Version=1.0` or higher
-   **AXIS OS**: 7.10 and later
-   **Product category**: Axis cameras with application support

Application identification

```bash
The getInfo method in \`/axis-cgi/packagemanager.cgi\` lists axis-rmd as active.orThe property Properties.Radar.Radar equals "yes".
```

## Common examples
### Reference map calibration using tracking

Use this example to set up a reference map and align it with the radar data to identify the position of objects detected by the radar.

1.  Upload image and us it as background in stream:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form '<name>=@<filename>;type=image/png' \\  "http://<servername>/axis-cgi/radar/uploadradarimage.cgi"
    ```
    
    ```bash
    POST /axis-cgi/radar/uploadradarimage.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="<name>"; filename="<filename>"Content-Type: image/png<file content>--<boundary>--
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "Echoed if provided by the client in the corresponding request",    "method": "uploadRadarImage",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "Echoed if provided by the client in the corresponding request",    "method": "uploadRadarImage",    "error": {        "code": 5000,        "message": "File type is invalid. Support .png and .jpeg."    }}
    ```
    
3.  Start tracking calibration object:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "starCalibrationTracking",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "starCalibrationTracking",    "params": {}}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "startCalibrationTracking",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "startCalibrationTracking",    "error": {        "code": 6000,        "message": "Invalid calibration state: 'reset'."    }}
    ```
    
5.  Set a calibration point in the image:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "params": {        "x\_pos": -0.2,        "y-pos": 0.9    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "params": {        "x\_pos": -0.2,        "y-pos": 0.9    }}
    ```
    
6.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "error": {        "code": 6000,        "message": "Invalid calibration state: 'image\_uploaded'."    }}
    ```
    
7.  Set another calibration point in image:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "params": {        "x-pos": 0.1,        "y-pos": 0.8    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "params": {        "x-pos": 0.1,        "y-pos": 0.8    }}
    ```
    
8.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setCalibrationPoint",    "error": {        "code": 6001,        "message": "Tracked object moved out of range."    }}
    ```
    
9.  Calibration is successful so stop tracking calibration object:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "stopCalibrationTracking",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "stopCalibrationTracking",    "params": {}}
    ```
    
10.  Parse the JSON response.
     
     a. Success response example.
     
     ```bash
     {    "apiVersion": "1.0",    "context": "123",    "method": "stopCalibrationTracking",    "data": {}}
     ```
     
     b. Failure response example.
     
     ```bash
     {    "apiVersion": "1.0",    "context": "123",    "method": "stopCalibrationTracking",    "error": {        "code": 6002,        "message": "Not enough calibration points set for successful calibration."    }}
     ```
     

### Restart calibration

Use this example to restart the calibration process.

1.  Restart the calibration:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "startCalibration",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "startCalibration",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "startCalibration",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "startCalibration",    "error": {        "code": 6000,        "message": "Invalid calibration state: 'reset'."    }}
    ```
    

### Find calibration state

Use this example to find the state of the calibration in order to present the user with useful options.

1.  Get the state of the calibration process:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getCalibrationState",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getCalibrationState",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getCalibrationState",    "data": {        "value": "tracking"    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getCalibrationState",    "error": {        "code": 8000,        "message": "Internal error."    }}
    ```
    

### Abort calibration

Use this example to abort an ongoing calibration process and re-start it later when there are no objects entering the radars’s field of view.

1.  Abort the calibration:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "abortCalibration",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "abortCalibration",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "abortCalibration",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "abortCalibration",    "error": {        "code": 6000,        "message": "Invalid calibration state: 'reset'."    }}
    ```
    

### Remove reference map

Use this example to remove the reference map and the calibrated parameters in order to move the radar unit to a different location.

1.  Reset calibration parameters and remove the reference map:
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "resetCalibration",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "resetCalibration",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "resetCalibration",    "error": {        "code": 6000,        "message": "Invalid calibration state: 'reset'."    }}
    ```
    

### Replace background image

Use this example to update the reference map without having to redo the entire calibration process.

1.  Replace the reference map with a new:
    
    ```bash
    http://<servername>/axis-cgi/radar/replaceradarimage.cgi
    ```
    
    Input parameters:
    
    ```bash
    HTTP/1.0Content-Type: multipart/form-data;boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="<name>"; filename"<filename>"Content-Type: image/png<file content>--<boundary>
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "Echoed if provided by the client in the corresponding request",    "method": "replaceRadarImage",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "Echoed if provided by the client in the corresponding request",    "method": "replaceRadarImage",    "error": {        "code": 5002,        "message": "Invalid file content."    }}
    ```
    

### Manual calibration

Use this example to calibrate the radar remotely using the API.

1.  Set radar position:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setManualRadarPosition",    "params": {        "x\_pos": -0.5,        "y\_pos": -0.5    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setManualRadarPosition",    "params": {        "x\_pos": -0.5,        "y\_pos": -0.5    }}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setManualRadarPosition",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setManualRadarPosition",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
    ```
    
3.  Set calibration point position:
    
    ```bash
    http://<servername>/axis-cgi/radar/radarimage.cgi{    "apiVersion": "1.0",    "context": "123",    "method": "setManualCalibrationPoint",    "params": {        "x\_pos": -0.5,        "y\_pos": -0.5,        "range": 20,        "angle": 0    }}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setManualCalibrationPoint",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setManualCalibrationPoint",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
    ```
    

### Set color scheme

Use this example to identify tracks in the video stream through the use of color coding.

1.  List color schemes available and current color scheme:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getColorScheme",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getColorScheme",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getColorScheme",    "data": {        "value": "green",        "allowedValues": \["black", "green", "blue"\]    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getColorScheme",    "error": {        "code": 8001,        "message": "Unexpected error."    }}
    ```
    
3.  Set color scheme:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setColorScheme",    "params": {        "value": "blue"    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setColorScheme",    "params": {        "value": "blue"    }}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setColorScheme",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setColorScheme",    "error": {        "code": 1000,        "message": "Invalid radarimage configuration value orange for 'value'."    }}
    ```
    

### Set trail lifetime

Use this example to increase the time the tracked objects history should be shown on a screen to make it easier to identify from where the objects came before entering the alarm area.

1.  Get trail lifetime and boundaries:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getTrailLifetime",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getTrailLifetime",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getTrailLifetime",    "data": {        "value": 17,        "minValue": 0,        "maxValue": 600    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getTrailLifetime",    "error": {        "code": 8001,        "message": "Unexpected error."    }}
    ```
    
3.  Set trail lifetime:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setTrailLifetime",    "params": {        "value": 30    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setTrailLifetime",    "params": {        "value": 30    }}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setTrailLifetime",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setTrailLifetime",    "error": {        "code": 1000,        "message": "Invalid radarimage configuration value -1 for 'value'."    }}
    ```
    

### Set grid opaque

Use this example to make the video stream less cluttered and easier to follow separate objects.

1.  Get grid opaque:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getGridOpaque",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getGridOpaque",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getGridOpaque",    "data": {        "value": 55,        "minValue": 0,        "maxValue": 100    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getGridOpaque",    "error": {        "code": 8001,        "message": "Unexpected error."    }}
    ```
    
3.  Set grid opaque:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setGridOpaque",    "params": {        "value": 50    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setGridOpaque",    "params": {        "value": 50    }}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setGridOpaque",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setGridOpaque",    "error": {        "code": 1000,        "message": "Invalid radarimage configuration value 123 for 'value'."    }}
    ```
    

### Set echo visualization level

Use this example to lower the amount of information visualized to make the video stream look less cluttered.

1.  Get the current echo visualization level:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getEchoVisualizationLevel",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getEchoVisualizationLevel",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getEchoVisualizationLevel",    "data": {        "value": "associated",        "allowedValues": \["disable", "associated", "all"\]    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getEchoVisualizationLevel",    "error": {        "code": 4003,        "message": "Could not find implementation for method getEchoVisualizationLevel"    }}
    ```
    
3.  Set echo visualization level:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setEchoVisualizationLevel",    "params": {        "value": "disable"    }}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setEchoVisualizationLevel",    "params": {        "value": "disable"    }}
    ```
    
4.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setEchoVisualizationLevel",    "data": {}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "setEchoVisualizationLevel",    "error": {        "code": 4001,        "message": "Failed to find key 'value' in JSON input"    }}
    ```
    

### Get metric size

Use this example to enter parameters related to the reference map in meters instead of pixels.

1.  Get image metric size:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getImageMetricSize",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getImageMetricSize",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getImageMetricSize",    "data": {        "value": "57"    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getImageMetricSize",    "error": {        "code": 4004,        "message": "Failed to load JSON from HTTP POST data"    }}
    ```
    

### Get file name

Use this example to receive and verify the names of the files uploaded from the computer to the radar unit.

1.  Get file name:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getFilename",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getFilename",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getFilename",    "data": {        "value": "west\_entrance.png"    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getFilename",    "error": {        "code": 4004,        "message": "Failed to load JSON from HTTP POST data"    }}
    ```
    

### Get supported versions

Use this example to check if a feature is supported before an application try to use them.

1.  Get supported API:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radarimage.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/radar/radarimage.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions",    "data": {        "value": \["1.0", "2.0"\]    }}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions",    "error": {        "code": 8001,        "message": "Unexpected error."    }}
    ```
    

## API specification
### uploadRadarImage

Upload an image to be used as a reference map to make it easier to relate a radar track to a position.

Supported image file formats are `png` and `jpeg`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form '<name>=@<filename>;type=image/png' \\  "http://<servername>/axis-cgi/radar/uploadradarimage.cgi"
```

```bash
POST /axis-cgi/radar/uploadradarimage.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="<name>"; filename="<filename>"Content-Type: image/png<file content>--<boundary>--
```

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "uploadRadarImage",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "uploadRadarImage",  "error": {    "code": <error code>    "message": "Error message"  }}
```

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under section [General error codes](#general-error-codes).

| Code | Definition | Description |
| --- | --- | --- |
| 2001 | RESOURCE\_NO\_FREE\_SPACE\_ERROR | No free space for the file on the radar unit. |
| 5000 | FILE\_TYPE\_INVALID\_ERROR | File type is invalid. |
| 5001 | FILE\_HEADER\_INVALID\_ERROR | File header is invalid. |
| 5002 | FILE\_CONTENT\_INVALID\_ERROR | File content is invalid. |
| 5003 | FILE\_WRITE\_TO\_SYSTEM\_ERROR | Error writing to file system. |

### replaceRadarImage

Upload an image and replace the existing calibrated image on the security radar, while still keeping all of the related parameters.

Supported image file formats are `png` and `jpeg`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form '<name>=@<filename>;type=image/png' \\  "http://<servername>/axis-cgi/radar/replaceradarimage.cgi"
```

```bash
POST /axis-cgi/radar/replaceradarimage.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="<name>"; filename="<filename>"Content-Type: image/png<file content>--<boundary>--
```

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "replaceRadarImage",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "replaceRadarImage",  "error": {    "code": <error code>    "message": "Error message"  }}
```

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under section [General error codes](#general-error-codes).

| Code | Definition | Description |
| --- | --- | --- |
| 2001 | RESOURCE\_NO\_FREE\_SPACE\_ERROR | No free space for the file on the radar unit. |
| 5000 | FILE\_TYPE\_INVALID\_ERROR | File type is invalid. |
| 5001 | FILE\_HEADER\_INVALID\_ERROR | File header is invalid. |
| 5002 | FILE\_CONTENT\_INVALID\_ERROR | File content is invalid. |
| 5003 | FILE\_WRITE\_TO\_SYSTEM\_ERROR | Error writing to file system. |

### startCalibrationTracking

Track the installer (user) moving away from the radar within the radar’s field of view to set calibration points.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | startCalibrationTracking |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "startCalibrationTracking",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body type:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "startCalibrationTracking",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setCalibrationPoint

Tells the package to use the supplied coordinates and current position of the tracked object.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setCalibrationPoint |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `x_pos` | Number | The x coordinate for the calibration point normalized between -1 and 1. |
| `y_pos` | Number | The y coordinate for the calibration point normalized between -1 and 1. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setCalibrationPoint",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setCalibrationPoint",  "error": {    "code": <error code>    "message": "Error message"  }}
```

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under section [General error codes](#general-error-codes).

| Code | Definition | Description |
| --- | --- | --- |
| 6001 | CALIB\_OUT\_OF\_RANGE\_ERROR | The tracked object walked out of range so tracking is lost and calibration need to be restarted. |
| 6003 | CALIB\_NOT\_DETECTED\_ERROR | Placed first calibration point before tracking detected any object close to the radar unit. |
| 6004 | CALIB\_TOO\_CLOSE\_TO\_RADAR\_ERROR | The tracked object is too close to radar. |
| 6005 | CALIB\_TOO\_CLOSE\_TO\_POINT\_ERROR | The tracked object is too close to last point. |
| 6006 | CALIB\_INVALID\_SCALE\_ERROR | Calibration resulted in invalid scale. |
| 6007 | CALIB\_INVALID\_POSITION\_ERROR | The calculated radar direction (x, y) is too far outside of the image. |
| 6008 | CALIB\_GENERAL\_CALC\_ERROR | The calibration calculation result is invalid so calibration should be done again. |
| 6009 | CALIB\_POINT\_INVALID | The calibration point is out of range -1 to 1. |
| 6010 | CALIB\_OBJ\_MOVING | The tracked object was moving when setting calibration point. May indicate that the wrong object is being tracked. |

### stopCalibrationTracking

Stop tracking the calibration object and store the result if the calibration was successful.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | stopCalibrationTracking |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "stopCalibrationTracking",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "stopCalibrationTracking",  "error": {    "code": <error code>    "message": "Error message"  }}
```

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under section [General error codes](#general-error-codes).

| Code | Definition | Description |
| --- | --- | --- |
| 6002 | CALIB\_NOT\_ENOUGH\_POINTS\_ERROR | Need at least two calibration points to stop calibration successfully. |

### abortCalibration

Stop tracking the calibration object and reset all parameters related to the current reference map.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | abortCalibration |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "abortCalibration",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "abortCalibration",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### resetCalibration

Reset the calibration by removing the reference map and its parameters.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | resetCalibration |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "resetCalibration",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "resetCalibration",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getCalibrationState

Return the current state of the calibration.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getCalibrationState |

The following table lists the possible calibration states.

| State | Description |
| --- | --- |
| `reset` | The calibration is reset back to displaying the default background and grid. |
| `image_uploaded` | A reference map is uploaded for calibration. |
| `tracking` | User have started tracking of calibration object. |
| `successful` | Calibration is successful but user have not stopped it yet. |
| `calibrated` | The reference map is calibrated successfully. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getCalibrationState",    "data": {        "value": "tracking"    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCalibrationState",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setManualRadarPosition

Calibrate the radar manually without the need to track an object.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setManualRadarPosition |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `x_pos` | Number | The x coordinate for the calibration point normalized between -1 and 1. |
| `y_pos` | Number | The y coordinate for the calibration point normalized between -1 and 1. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setManualRadarPosition",    "data": {        "x\_pos": -0.5,        "y\_pos": 0.5    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setManualRadarPosition",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setManualCalibrationPoint

Calibrate the radar manually without the need to track an object.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the add-on echoes it back in the response. |
| `method` | String | setManualCalibrationPoint |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `x_pos` | Number | The x coordinate for the calibration point normalized between -1 and 1. |
| `y_pos` | Number | The y coordinate for the calibration point normalized between -1 and 1. |
| `range` | Number | Actual distance of the calibration point from the radar in meters. |
| `angle` | Number | Actual angle from the radar to the calibration point in degrees. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setManualCalibrationPoint",    "data": {        "x\_pos": -0.5,        "y\_pos": 0.5,        "range": 15.5,        "angle": -21.3    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setManualCalibrationPoint",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getTrailLifetime

Return current lifetime of the trails as well as the minimum and maximum value for trail lifetime.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getTrailLifetime |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request.",    "method": "getTrailLifetime",    "data": {        "value": 17,        "minValue": 0,        "maxValue": 60    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getTrailLifetime",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setTrailLifetime

Sets how long time the trail of a tracked object should be visible in the video stream.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setTrailLifetime |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `value` | Integer | Value for how long the trails should be in seconds. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setTrailLifetime",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setTrailLifetime",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getColorScheme

Return the current color scheme used in the video stream and a list of possible color schemes to choose between.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getColorScheme |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getColorScheme",    "data": {        "value": "green",        "allowedValues": \["black", "green", "blue"\]    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getColorScheme",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setColorScheme

Set the colorScheme to be used when generating the video stream. ColorScheme will affect the grid, the echoes and the radar trail. The getColorScheme method list the available color schemes in its JSON response.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setColorScheme |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `value` | String | Color scheme used in the video stream. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setColorScheme",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setColorScheme",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getGridOpaque

Return current opaque level of the grid as well as minimum and maximum grid opaque level.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getGridOpaque |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getGridOpaque",    "data": {        "value": 70,        "minValue": 0,        "maxValue": 100    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getGridOpaque",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setGridOpaque

Set the opaque level of the grid. Level of zero mean that the grid is fully transparent and level 100 mean that the grid is fully opaque.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setGridOpaque |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `value` | Integer | Opaque level used for the grid in the video stream. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setGridOpaque",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setGridOpaque",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getEchoVisualizationLevel

Return current level of echo visualization and a list of possible levels.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getEchoVisualizationLevel |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getEchoVisualizationLevel",    "data": {        "value": true,        "allowedValues": \["disable", "associated", "all"\]    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getEchoVisualizationLevel",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### setEchoVisualizationLevel

Set the level of visualization of the radar echoes, i.e. the raw responses of the electromagnetic waves the radar sensor sends out.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | setEchoVisualizationLevel |
| `params` | JSON object | Container for the method specific parameters listed below. |
| `value` | String | Value for visualization level. |

The following table lists the echo visualization levels.

| Name | Description |
| --- | --- |
| `disable` | No echoes visualized. |
| `associated` | Echoes associated with a track is visualized. |
| `all` | All echoes are visualized. |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setEchoVisualizationLevel",    "data": {}}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "setEchoVisualizationLevel",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getImageMetricSize

Returns the height of the video stream in meters, i.e. can be used to transform the requested video stream resolution between meters and pixels and set parameter values in meters. The API only support an aspect ratio of 16:9.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getImageMetricSize |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getImageMetricSize",    "data": {        "value": 72    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getImageMetricSize",  "error": {    "code": <error code>    "message": "Error message"  }}
```

### getFilename

Return the name of the reference map currently displayed in the video stream.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for his CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getFilename |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getFilename",    "data": {        "value": "east\_courtyard.png"    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getFilename",  "error": {    "code": <error code>    "message": "Error message"  }}
```

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under section [General error codes](#general-error-codes).

| Code | Definition | Description |
| --- | --- | --- |
| 5002 | FILE\_NOT\_UPLOADED\_ERROR | No image file uploaded to radar. |

### getSupportedVersions

A CGI method for retrieving the supported API versions. The returned list consists of the supported major versions, with the highest supported minor versions.

**Request**

-   **Security level**: Operator

```bash
POST /axis-cgi/radar/radarimage.cgi
```

The following table lists the JSON parameters for this CGI method.

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The requested API version in the format Major.Minor. |
| `context` | String | Optional context string. Client sets this value and the package echoes it back in the response. |
| `method` | String | getSupportedVersions |

**Return value: Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getSupportedVersions",    "data": {        "value": \["1.0", "2.0"\]    }}
```

**Return value: Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getSupportedVersions",  "error": {    "code": <error code>    "message": "Error message"  }}
```

## General error codes

The following table lists general errors that can occur for any CGI method. Errors that are specific for a method are listed under the API description for that method.

| Code | Definition | Description |
| --- | --- | --- |
| 1000 | PARAM\_INVALID\_VALUE\_ERROR | Invalid parameter value. |
| 2000 | RESOURCE\_MEM\_ERROR | Failed to allocate memory. |
| 3000 | UNSUPPORTED\_API\_VERSION | The requested API version is not supported. |
| 3001 | CGI\_INVALID\_PARAM\_ERROR | A CGI parameter is missing or invalid. |
| 3002 | CGI\_NOT\_FOUND | The cgi name was not found. |
| 4000 | JSON\_INVALID\_ERROR | The provided JSON input was invalid. |
| 4001 | JSON\_KEY\_NOT\_FOUND\_ERROR | A mandatory input parameter was not found in the input. |
| 4002 | JSON\_INVALID\_TYPE | The type of a provided JSON parameter was incorrect. |
| 4003 | JSON\_METHOD\_NOT\_FOUND\_ERROR | The JSON method was not found. |
| 4004 | JSON\_FAIL\_TO\_LOAD\_ERROR | Failed to load JSON from HTTP POST data. |
| 6000 | CALIB\_INVALID\_STATE\_ERROR | Can not perform command in current calibration state. |
| 8000 | INTERNAL\_ERROR | Internal error. |
| 8001 | UNEXPECTED\_ERROR | Unexpected error. |
| 8002 | GENERIC\_ERROR | Generic error. |