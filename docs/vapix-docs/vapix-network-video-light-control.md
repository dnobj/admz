---
title: Light control
url: "https://developer.axis.com/vapix/network-video/light-control/"
category: vapix
subcategory: network-video
sha256: f5f6522aca47c144cd078cb54bb6a674ac491ed2c7364521e655eef99ebba553
scraped_at: "2026-01-09T15:20:08.802Z"
page_height: 114642
---

# Light control

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Light control API

The VAPIX® Light control API makes it possible to control the behavior and functionality of IR and White light LEDs in the Axis devices. This is done through JSON commands, and the API also have support for the [On-screen controls](/vapix/network-video/on-screen-controls/) API in order to control the lights directly, something that was not possible with the older [Light control service API](#light-control-service-api).

### Overview

The API is built around the `/axis-cgi/lightcontrol.cgi`, which makes it possible to query for one or several light devices and their status, controlling their light intensity and focus, and turning them on/off.

The CGI consists of the following methods:

| Method | Description |
| --- | --- |
| `getSupportedVersions` | Lists the API versions that are supported by the CGI. |
| `getServiceCapabilities` | Lists the capabilities of the light control. |
| `getLightInformation` | Lists the light control information. |
| `activateLight` | Activates the light. |
| `deactivateLight` | Deactivates the light. |
| `enableLight` | Enables the light functionality on the device. |
| `disableLight` | Disables the light functionality on the device. |
| `getLightStatus` | Retrieves the light status from a given Light ID. |
| `setAutomaticIntensityMode` | Enables the automatic light intensity control. |
| `getValidIntensity` | Lists the valid light intensity values. |
| `setManualIntensity` | Manually sets the intensity. |
| `getManualIntensity` | Retrieves the intensity from the `setManualIntensity` request. |
| `setIndividualIntensity` | Manually sets the intensity for an individual LED. |
| `getIndividualIntensity` | Retrieves the intensity from the `setIndividualIntensity` request. |
| `getCurrentIntensity` | Retrieves the current intensity. |
| `setAutomaticAngleOfIlluminationMode` | Automatically controls the angle of illumination. Using this mode means that the angle of illumination is the same as the camera’s angle of view. |
| `getValidAngleOfIllumination` | Lists the valid angle of illumination values. |
| `setManualAngleOfIllumination` | Sets the manual angle of illumination. This is useful when the angle of illumination needs to be different from the camera’s view angle. |
| `getManualAngleOfIllumination` | Retrieves the angle of illumination from the `setManualAngleOfIllumination` request. |
| `getCurrentAngleOfIllumination` | Retrieves the current angle of illumination. |
| `setLightSynchronizeDayNightMode` | Enables automatic synchronization with the day/night mode. |
| `getLightSynchronizeDayNightMode` | Checks if the automatic synchronization is enabled with the day/night mode. |
| `getValidIRWavelengths` | Lists the valid IR wavelengths. |
| `setIRWavelength` | Sets the IR wavelength. |
| `getIRWavelength` | Retrieves the currently set IR wavelength |

#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.LightControl.LightControl2=yes`
-   **AXIS OS**: 7.40 and later
-   **API Discovery**: `id=light-control`

#### Obsoletes

A successful response from the `getServiceCapabilities` method will list supported capabilities of the light controller service. This is followed by an array that contains the supported capabilities for each `LEDgroup`. It is recommended to use this array, as the global capabilities have been deprecated.

### Common examples
#### Get supported versions

Use this example to get a list of API versions that are supported on the device.

1.  Send a request to receive a list of the supported API versions:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "2.1",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "2.1"\]    }}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "2.1",    "context": "my context",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error, could not complete request."    }}
    ```
    

See [getSupportedVersions](#getsupportedversions) for further instructions.

#### Get service capabilities

Use this example to list the capabilities of the light controller that is supported on the device.

Please note that the global capabilities have been deprecated and the `capabilities` array should be used instead.

1.  Send a request to receive a list showing the light service capabilities.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceCapabilities"}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceCapabilities"}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceCapabilities",    "data": {        "automaticIntensitySupport": true,        "manualIntensitySupport": true,        "individualIntensitySupport": false,        "getCurrentIntensitySupport": true,        "manualAngleOfIlluminationSupport": false,        "automaticAngleOfIlluminationSupport": false,        "dayNightSynchronizeSupport": true,        "multiIRWaveLengthSupport": true,        "capabilities": \[            {                "lightID": id,                "automaticIntensitySupport": true,                "manualIntensitySupport": true,                "individualIntensitySupport": false,                "getCurrentIntensitySupport": true,                "manualAngleOfIlluminationSupport": false,                "automaticAngleOfIlluminationSupport": false,                "dayNightSynchronizeSupport": true,                "multiIRWaveLengthSupport": true            },            {                "lightID": id,                "automaticIntensitySupport": true,                "manualIntensitySupport": true,                "individualIntensitySupport": false,                "getCurrentIntensitySupport": true,                "manualAngleOfIlluminationSupport": false,                "automaticAngleOfIlluminationSupport": false,                "dayNightSynchronizeSupport": true,                "multiIRWaveLengthSupport": true            }        \]    }}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getServiceCapabilities",    "error": {        "code": 7000,        "message": "The requested API version is not supported by this implementation."    }}
    ```
    

See [getServiceCapabilities](#getservicecapabilities) for further instructions.

#### Get light information

Use this example to list the light control information on the device.

1.  Send a request to receive a list of lights and their configuration and status.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightInformation",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightInformation",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getLightInformation",    "data": {        "items": \[            {                "lightID": "led0",                "lightType": "IR",                "enabled": true,                "synchronizeDayNightMode": true,                "lightState": false,                "automaticIntensityMode": false,                "automaticAngleOfIlluminationMode": false,                "nrOfLEDs": 1,                "error": false,                "errorInfo": ""            },            {                "lightID": "led1",                "lightType": "IR",                "enabled": true,                "synchronizeDayNightMode": false,                "lightState": false,                "automaticIntensityMode": false,                "automaticAngleOfIlluminationMode": false,                "nrOfLEDs": 2,                "error": false,                "errorInfo": ""            }        \]    }}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getLightInformation",    "error": {        "code": 2000,        "message": "Failed to allocate memory for request."    }}
    ```
    

See [getLightInformation](#getlightinformation) for further instructions.

#### Activate light

Use this example to turn on the light of a specific Light ID.

1.  Send a request to activate the lights of a given Light ID. Please note that a single Light ID can still contain several LEDs and/or lamps.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "activateLight",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "activateLight",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "activateLight",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "activateLight",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
    ```
    

See [activateLight](#activatelight) for further instructions.

#### Deactivate light

Use this example to turn off the lights of a specific Light ID.

1.  Send a request to deactivate the lights of a given Light ID.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "deactivateLight",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "deactivateLight",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "deactivateLight",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "deactivateLight",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
    ```
    

See [deactivateLight](#deactivatelight) for further instructions.

#### Enable light

Use this example to enable the lights of a specific Light ID. Note that a disabled light can not be turned on.

1.  Send a request to enable the lights of a given Light ID.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "enableLight",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "enableLight",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "enableLight",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "enableLight",    "error": {        "code": 1005,        "message": "Hardware failure, could not complete request."    }}
    ```
    

See [enableLight](#enablelight) for further instructions.

#### Disable light

Use this example to disable the light of a specific Light ID. Note that a disabled light can not be turned on.

1.  Send a request to disable the lights of a given Light ID.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "disableLight",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "disableLight",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "disableLight",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "disableLight",    "error": {        "code": 1005,        "message": "Hardware failure, could not complete request."    }}
    ```
    

See [disableLight](#disablelight) for further instructions.

#### Get light status

Use this example to get the status of a specified Light ID.

1.  Send a request to receive the status of the lights of a given Light ID.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightStatus",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightStatus",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getLightStatus",    "data": {        "status": true    }}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getLightStatus",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
    ```
    

See [getLightStatus](#getlightstatus) for further instructions.

#### Set automatic intensity mode

Use this example to enable the automatic light intensity controller.

1.  Send a request to change the setting of the automatic intensity mode.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticIntensityMode",    "params": {        "lightID": "led0",        "enabled": true    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticIntensityMode",    "params": {        "lightID": "led0",        "enabled": true    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticIntensityMode",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticIntensityMode",    "error": {        "code": 1005,        "message": "Hardware failure, could not complete request."    }}
    ```
    

See [setAutomaticIntensityMode](#setautomaticintensitymode) for further instructions.

#### Get valid intensity

Use this example to get a list of valid light intensity ranges. Values within this range can be used to change the intensity of the light when using the `setManualIntensity` method.

1.  Send a request to receive a list of supported intensity ranges.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidIntensity",    "params": {        "lightID": "led0"    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidIntensity",    "params": {        "lightID": "led0"    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getValidIntensity",    "data": {        "ranges": \[            {                "low": 0,                "high": 50            }        \]    }}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getValidIntensity",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
    ```
    

See [getValidIntensity](#getvalidintensity) for further instructions.

#### Set manual intensity

Use this example to set the manual intensity of a light.

1.  Send a request to receive the manual intensity level of a light.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualIntensity",    "params": {        "lightID": "led0",        "intensity": 50    }}'
    ```
    
    ```bash
    POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualIntensity",    "params": {        "lightID": "led0",        "intensity": 50    }}
    ```
    
2.  Parse the JSON response.
    
    a) Successful response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setManualIntensity",    "data": {}}
    ```
    
    b) Failed response example:
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setManualIntensity",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
    ```
    

See [setManualIntensity](#setmanualintensity) for further instructions.

#### Get manual intensity

Use this example to get the manually configured intensity from the previous example.

1.  Send a request to receive a response with the currently configured manual intensity level of a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualIntensity",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualIntensity",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualIntensity",    "data": {        "intensity": 50    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualIntensity",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [getManualIntensity](#getmanualintensity) for further instructions.

#### Set individual intensity

Use this example to manually change the intensity of an individual LED light.

1.  Send a request to receive a manual intensity level for either a single or group of LED lights.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setIndividualIntensity",    "params": {        "lightID": "led0",        "LEDID": 1,        "intensity": 100    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setIndividualIntensity",    "params": {        "lightID": "led0",        "LEDID": 1,        "intensity": 100    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setIndividualIntensity",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setIndividualIntensity",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [setIndividualIntensity](#setindividualintensity) for further instructions.

#### Get individual intensity

Use this example to get the manually configured intensity of an individual LED light.

1.  Send a request to receive the current intensity level for either a single or a group of LED lights.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getIndividualIntensity",    "params": {        "lightID": "led0",        "LEDID": 2    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getIndividualIntensity",    "params": {        "lightID": "led0",        "LEDID": 2    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getIndividualIntensity",    "data": {        "intensity": 100    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getIndividualIntensity",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [getIndividualIntensity](#getindividualintensity) for further instructions.

#### Get current intensity

Use this example to get the current intensity of a light.

1.  Send a request to receive the current intensity of a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentIntensity",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentIntensity",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentIntensity",    "data": {        "intesity": 100    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentIntensity",    "error": {        "code": 1005,        "message": "Hardware failure, could not complete request."    }}
```

See [getCurrentIntensity](#getcurrentintensity) for further instructions.

#### Set automatic angle of illumination mode

Use this example to automatically control the angle of illumination.

1.  Send a request to receive a change of the automatic angle of illumination mode for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticAngleOfIlluminationMode",    "params": {        "lightID": "led0",        "enabled": true    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticAngleOfIlluminationMode",    "params": {        "lightID": "led0",        "enabled": true    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticAngleOfIlluminationMode",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setAutomaticAngleOfIlluminationMode",    "error": {        "code": 1001,        "message": "Method call not supported by the device."    }}
```

See [setAutomaticAngleOfIlluminationMode](#setautomaticangleofilluminationmode) for further instructions.

#### Get valid angle of illumination

Use this example to get a list of supported angle of illumination ranges for a light.

1.  Send a request to receive a list of valid ranges for angle of illumination for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidAngleOfIllumination",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidAngleOfIllumination",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidAngleOfIllumination",    "data": {        "ranges": \[            {                "low": 10,                "high": 30            },            {                "low": 20,                "high": 50            }        \]    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getValidAngleOfIllumination",    "error": {        "code": 1001,        "message": "Method call not supported by the device."    }}
```

See [getValidAngleOfIllumination](#getvalidangleofillumination) for further instructions.

#### Set manual angle of illumination

Use this example to manually control the angle of illumination.

1.  Send a request to make a change of the manual angle of illumination for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualAngleOfIllumination",    "params": {        "lightID": "led0",        "angleOfIllumination": 30    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualAngleOfIllumination",    "params": {        "lightID": "led0",        "angleOfIllumination": 30    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualAngleOfIllumination",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setManualAngleOfIllumination",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [setManualAngleOfIllumination](#setmanualangleofillumination) for further instructions.

#### Get manual angle of illumination

Use this example to get the current configured manual angle of illumination.

1.  Send a request to receive the current configured manual angle of illumination mode for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualAngleOfIllumination",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualAngleOfIllumination",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualAngleOfIllumination",    "data": {        "angleOfIllumination": 30    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getManualAngleOfIllumination",    "error": {        "code": 1005,        "message": "Hardware failure, could not complete request."    }}
```

See [getManualAngleOfIllumination](#getmanualangleofillumination) for further instructions.

#### Get current angle of illumination

Use this example to get the current angle of illumination.

1.  Send a request to receive the current angle of illumination for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentAngleOfIllumination",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentAngleOfIllumination",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentAngleOfIllumination",    "data": {        "angleOfIllumination": 20    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getCurrentAngleOfIllumination",    "error": {        "code": 1001,        "message": "Method call not supported by the device."    }}
```

See [getCurrentAngleOfIllumination](#getcurrentangleofillumination) for further instructions.

#### Set light synchronize day night mode

Use this example to turn on automatic day/night synchronization mode.

1.  Send a request to make a change to the automatic synchronization and day/night mode for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setLightSynchronizationDayNightMode",    "params": {        "lightID": "led0",        "enabled": false    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setLightSynchronizationDayNightMode",    "params": {        "lightID": "led0",        "enabled": false    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setLightSynchronizeDayNightMode",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setLightSynchronizeDayNightMode",    "error": {        "code": 1001,        "message": "Method call not supported by the device."    }}
```

See [setLightSynchronizeDayNightMode](#setlightsynchronizedaynightmode) for further instructions.

#### Get light synchronize day night mode

Use this example to check if the automatic synchronization for the day/night mode is enabled.

1.  Send a request to make a change to the automatic synchronization and day/night mode for a light.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightSynchronizeDayNightMode",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightSynchronizeDayNightMode",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightSynchronizeDayNightMode",    "data": {        "enabled": false    }}
```

b) Failed response exampled:

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getLightSynchronizeDayNightMode",    "error": {        "code": 1001,        "message": "Method call not supported by the device."    }}
```

See [getLightSynchronizeDayNightMode](#getlightsynchronizedaynightmode) for further instructions.

#### Get valid infrared wavelengths

Use this example to retrieve a list of valid infrared wavelengths. The wavelengths themselves can be changed with the `setIRWavelength` method.

1.  Request a list of supported infrared wavelengths.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getValidIRWavelengths",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getValidIRWavelengths",    "params": {        "lightID": "led0"    }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getValidIRWavelengths",    "data": {        "wavelength": \["850nm", "940nm"\]    }}
```

b) Failed response example:

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getValidIRWavelengths",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [getValidIRWavelengths](#getvalidirwavelengths) for further instructions.

#### Set infrared wavelength

Use this example to set the infrared wavelength. Changing the wavelength of the will give the light different properties such as different illumination ranges and red glow emissions from the light source.

1.  Request a change of the infrared wavelength.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": "1.2",  "context": "my context",  "method": "setIRWavelength",  "params": {    "lightID": "led0"    "IRWavelength": wavelength  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.2",  "context": "my context",  "method": "setIRWavelength",  "params": {    "lightID": "led0"    "IRWavelength": wavelength  }}
```

2.  Parse the JSON response.

a) Successful response example:

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "setIRWavelength",    "data": {}}
```

b) Failed response example:

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "setIRWavelength",    "error": {        "code": 1002,        "message": "Provided lightID parameter is not valid for the device."    }}
```

See [setIRWavelength](#setirwavelength) for further instructions.

#### Get infrared wavelength

Use this example to retrieve the currently configured infrared wavelength.

1.  Request a response with the currently configured infrared wavelength.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getIRWavelength",    "params": {        "lightID": "led0"    }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getIRWavelength",    "params": {        "lightID": "led0"    }}
```

a) Successful response example:

```bash
{  "apiVersion": "1.2",  "context": "my context",  "method": "getIRWavelength",  "data": {    "IRWavelength": wavelength  }}
```

b) Failed response example:

```bash
{  "apiVersion": "Major.Minor",  "context": "my context",  "method": getIRWavelength",  "error": {    "code": 1002,    "message": "Provided lightID parameter is not valid for the device."  }}
```

See [getIRWavelength](#getirwavelength) for further instructions.

### API specification
#### getSupportedVersions

A CGI method used to retrieve supported API versions. The returning list consists of the supported major versions as well as the highest supported minor versions. Please note that the version is for the API as a whole, i.e. for all methods in the CGI.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSupportedVersions",  "params": {}}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getSupportedVersions",  "params": {}}
```

getSupportedVersions request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |

**Return value - Success**

Returns an array containing the supported API versions.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

getSupportedVersions response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `apiVersions` | Array | Shows the supported API versions. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

#### getServiceCapabilities

A CGI method that lists the light service capabilities.

Please note that the global capabilities have been deprecated and the `capabilities` array should be used instead.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getServiceCapabilities",  "params": {}}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getServiceCapabilities",  "params": {}}
```

getServiceCapabilities request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getServiceCapabilities",  "data": {    "automaticIntensitySupport": true | false,    "manualIntensitySupport": true | false,    "individualIntensitySupport": true | false,    "getCurrentIntensitySupport": true | false,    "manualAngleOfIlluminationSupport": true | false,    "automaticAngleOfIlluminationSupport": true | false,    "dayNightSynchronizeSupport": true | false,    "multiIRWaveLengthSupport": true | false,    "capabilities": \[      {        "lightID": id,        "automaticIntensitySupport": true | false,        "manualIntensitySupport": true | false,        "individualIntensitySupport": true | false,        "getCurrentIntensitySupport": true | false,        "manualAngleOfIlluminationSupport": true | false,        "automaticAngleOfIlluminationSupport": true | false,        "dayNightSynchronizeSupport": true | false,        "multiIRWaveLengthSupport": true | false      },      {        "lightID": id,        "automaticIntensitySupport": true | false,        "manualIntensitySupport": true | false,        "individualIntensitySupport": true | false,        "getCurrentIntensitySupport": true | false,        "manualAngleOfIlluminationSupport": true | false,        "automaticAngleOfIlluminationSupport": true | false,        "dayNightSynchronizeSupport": true | false,        "multiIRWaveLengthSupport": true | false      }    \]  }}
```

getServiceCapabilities response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `automaticIntensitySupport` | Boolean | Indicates that `setAutomaticIntensityMode` is supported. |
| `manualIntensitySupport` | Boolean | Indicates that `getManualIntensity` and `setManualIntensity` are supported. |
| `individualIntensitySupport` | Boolean | Indicates that `getIndividualIntensity` and `setIndividualIntensity` are supported. |
| `getCurrentIntensitySupport` | Boolean | Indicates that `getCurrentIntensity` is supported. |
| `manualAngleOfIlluminationsupport` | Boolean | Indicates that `setManualAngleOfIllumination` is supported. |
| `automaticAngleOfIlluminationSupport` | Boolean | Indicates that `setAutomaticAngleOfIlluminationMode` is supported. |
| `dayNightSynchronizeSupport` | Boolean | Indicates that `setLightSynchronizeDayNightMode` is supported. |
| `multiIRWaveLengthSupport` | Boolean | Indicates that `getValidIRWavelengths`, `setIRWavelength` and `getIRWavelength` are supported. |
| `capabilities` | JSON object | Container for supported capabilities for each LEDgroup. |
| `lightID` | String | The ID of the LEDgroup. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

There are no specific error codes for this method. General errors are listed in [General error codes](#general-error-codes).

#### getLightInformation

A CGI method that lists the light control information.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getLightInformation",  "params": {}}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getLightInformation",  "params": {}}
```

getLightInformation request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |

**Return value - Success**

Returns an array of lights in the device and their configurations.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getLightInformation",  "data": {    "items": \[      {        "lightID": "id",        "lightType": "type",        "enabled": true | false,        "synchronizeDayNightMode": true | false,        "lightState": true | false,        "automaticIntensityMode": true | false,        "automaticAngleOfIlluminationMode": true | false,        "nrOfLEDs": "numberOfLEDs",        "error": true | false,        "errorInfo": "Error message"      }    \]  }}
```

getLightInformation response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `lightID` | String | Unique ID of the light. |
| `lightType` | String | Type identifier of the light. |
| `enabled` | Boolean | Indicates if the light is enabled. |
| `synchronizeDayNightMode` | Boolean | Indicates if the light is synchronized with day/night. |
| `lightState` | Boolean | Indicates if the light is ON or OFF. |
| `automaticIntensityMode` | Boolean | Indicates if the mode for automatic intensity is active. |
| `automaticAngleOfIlluminationMode` | Boolean | Indicates if the mode for automatic angle of illumination is active. |
| `nrOfLEDs` | Integer | Number of configurable LEDs in a light group. The light groups are identified by their Light ID. |
| `error` | Boolean | An error has occurred. |
| `errorInfo` | String | Error description. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### activateLight

A CGI method that activates the light.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "activateLight",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "activateLight",  "params": {    "lightID": <string>  }}
```

activateLight request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "activateLight",    "data": {}}
```

activateLight response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

activateLight error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |
| `1008` | `UPDATE_IRCUTFILTER_FAULT` | Could not update IR cut filter. |
| `1009` | `LIGHT_DISABLED_FAULT` | The light group is turned off and can’t be activated. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### deactivateLight

A CGI method that deactivates the light.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "deactivateLight",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "deactivateLight",  "params": {    "lightID": <string>  }}
```

deactivateLight request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "deactivateLight",    "data": {}}
```

deactivateLight response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

deactivateLight error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### enableLight

A CGI method that enables the light functionality.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "enableLight",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "enableLight",  "params": {    "lightID": <string>  }}
```

enableLight request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "enableLight",    "data": {}}
```

enableLight response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

enableLight error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### disableLight

A CGI method that disables the light functionality.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "disableLight",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "disableLight",  "params": {    "lightID": <string>  }}
```

disableLight request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "disableLight",    "data": {}}
```

disableLight response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

disableLight error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### getLightStatus

A CGI method that showcases the light status of a given Light ID.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>  "context": "<string>",  "method": "getLightStatus",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>  "context": "<string>",  "method": "getLightStatus",  "params": {    "lightID": <string>  }}
```

getLightStatus request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getLightStatus",  "data": {    "status": true | false  }}
```

getLightStatus response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `status` | Boolean | Indicates if the light is ON or OFF. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

getLightStatus error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### setAutomaticIntensityMode

A CGI method that enables the automatic light intensity control.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setAutomaticIntensityMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setAutomaticIntensityMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}
```

setAutomaticIntensityMode request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `enabled` | Boolean | Enables automatic light intensity control. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setAutomaticIntensityMode",    "data": {}}
```

setAutomaticIntensityMode response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

setAutomaticIntensityMode error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### getValidIntensity

A CGI method that lists the valid light intensity values.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidIntensity",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidIntensity",  "params": {    "lightID": <string>  }}
```

getValidIntensity request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getValidIntensity",  "data": {    "ranges": \[      {        "low": lowerLimit,        "high": upperLimit      }    \]  }}
```

getValidIntensity response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `ranges` | Array | Array of the range objects. |
| `low` | Integer | The lower intensity limit for the range. |
| `high` | Integer | The upper intensity limit for the range. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

getValidIntensity error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### setManualIntensity

A CGI method that sets the intensity manually.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setManualIntensity",  "params": {    "lightID": <string>,    "intensity": <integer>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setManualIntensity",  "params": {    "lightID": <string>,    "intensity": <integer>  }}
```

setManualIntensity request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `intensity` | Integer | The intensity level of the light. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setManualIntensity",    "data": {}}
```

setManualIntensity response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

setManualIntensity error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1003` | `INVALID_INTENSITY_FAULT` | Provided intensity level is out of the supported range. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### getManualIntensity

A CGI method that gets the intensity that was sent in the `setManualIntensity` request.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getManualIntensity",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getManualIntensity",  "params": {    "lightID": <string>  }}
```

getManualIntensity request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getManualIntensity",  "data": {    "intensity": manualIntensity  }}
```

getManualIntensity response parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `intensity` | Intensity | The currently configured manual intensity. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

getManualIntensity error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

This list contains the error codes for this particular method. For general errors, see [General error codes](#general-error-codes).

#### setIndividualIntensity

A CGI method that manually sets the intensity of an individual LED light.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setIndividualIntensity",  "params": {    "lightID": <string>,    "LEDID": <integer>,    "intensity": <integer>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setIndividualIntensity",  "params": {    "lightID": <string>,    "LEDID": <integer>,    "intensity": <integer>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `LEDID` | Integer | The ID of the LED. |
| `intensity` | Integer | The intensity level of the light. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setIndividualIntensity",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1003` | `INVALID_INTENSITY_FAULT` | Provided intensity level is out of the supported range. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getIndividualIntensity

A CGI method that sends the intensity in the `setIndividualIntensity` request.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getIndividualIntensity",  "params": {    "lightID": <string>,    "LEDID": <integer>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getIndividualIntensity",  "params": {    "lightID": <string>,    "LEDID": <integer>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `LEDID` | Integer | The ID of the LED. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getIndividualIntensity",  "data": {    "intensity": individualIntensity  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `intensity` | Integer | The currently configured individual intensity. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getCurrentIntensity

A CGI method that gets the current intensity.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getCurrentIntensity",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getCurrentIntensity",  "params": {    "lightID": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCurrentIntensity",  "data": {    "intensity": currentIntensity  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `intensity` | Integer | The current intensity of the light. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### setAutomaticAngleOfIlluminationMode

A CGI method that controls the automatic angle of illumination.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setAutomaticAngleOfIlluminationMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setAutomaticAngleOfIlluminationMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `enabled` | Boolean | Activate or deactivate automatic angle of illumination mode for a selected light. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setAutomaticAngleOfIlluminationMode",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getValidAngleOfIllumination

A CGI method that lists the valid angle of the illumination values.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidAngleOfIllumination",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidAngleOfIllumination",  "params": {    "lightID": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getValidAngleOfIllumination",  "data": {    "ranges": \[      {        "low": lowerLimit,        "high": upperLimit      }    \]  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `ranges` | Array | Array of range objects. |
| `low` | Integer | Lower angle limit for the range. |
| `high` | Integer | Upper angle limit for the range. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### setManualAngleOfIllumination

A CGI method that sets the manual angle of illumination.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setManualAngleOfIllumination",  "params": {    "lightID": <string>,    "angleOfIllumination": <integer>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setManualAngleOfIllumination",  "params": {    "lightID": <string>,    "angleOfIllumination": <integer>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `angleOfIllumination` | Integer | The angle of illumination. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setAutomaticAngleOfIlluminationMode",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1004` | `INVALID_ANGLE_OF_ILLUMINATION_FAULT` | Provided angle of illumination is out of the supported range. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getManualAngleOfIllumination

A CGI method that gets the angle of illumination sent by the `setManualAngleOfIllumination` request.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getManualAngleOfIllumination",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getManualAngleOfIllumination",  "params": {    "lightID": <string>  }}
```

getManualAngleOfIllumination request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getManualAngleOfIllumination",  "data": {    "angleOfIllumination": angle  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `angleOfIllumination` | Integer | The current manual angle of illumination. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getCurrentAngleOfIllumination

A CGI method that gets the current angle of illumination.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getCurrentAngleOfIllumination",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getCurrentAngleOfIllumination",  "params": {    "lightID": <string>  }}
```

getCurrentAngleOfIllumination request parameters

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getCurrentAngleOfIllumination",  "data": {    "angleOfIllumination": angle  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `angleOfIllumination` | Integer | The currently active angle of illumination. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### setLightSynchronizeDayNightMode

A CGI method that let you enable or disable the automatic day/night synchronization mode.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setLightSynchronizeDayNightMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setLightSynchronizeDayNightMode",  "params": {    "lightID": <string>,    "enabled": <boolean>  }}
```

setLightSynchronizeDayNightMode

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `enabled` | Boolean | Activate or deactivate automatic angle of illumination mode for a selected light. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setLightSynchronizeDayNightMode",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getLightSynchronizeDayNightMode

A CGI method that checks if the automatic synchronization with the day/night mode is enabled.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getLightSynchronizeDayNightMode",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getLightSynchronizeDayNightMode",  "params": {    "lightID": <string>  }}
```

getLightSynchronizeDayNightMode

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getLightSynchronizeDayNightMode",  "data": {    "synchronize": true | false  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `enabled` | Boolean | If the day/night cut filter synchronization of the light is active. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### getValidIRWavelengths

A CGI method that returns a list containing the infrared wavelengths.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidIRWavelengths",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "getValidIRWavelengths",  "params": {    "lightID": <string>  }}
```

getValidIRWavelength

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getValidIRWavelengths",  "data": {    "settings": \[      wavelength,      ...    \]  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `wavelengths` | Array | An array containing the wavelengths settings. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### setIRWavelength

A CGI method that sets the infrared wavelength.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setIRWavelength",  "params": {    "lightID": <string>,    "IRWavelength": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <major>.<minor>,  "context": "<string>",  "method": "setIRWavelength",  "params": {    "lightID": <string>,    "IRWavelength": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for the method specific parameters. |
| `lightID` | String | The light ID. |
| `IRWavelength` | String | The infrared wavelength. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "Major.Minor",    "context": "Echoed if provided by the client in the corresponding request",    "method": "setIRWavelength",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context` |  | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` |  | Container for the response specific parameters. |
| `data` |  | The current intensity of the light. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |
| `1007` | `INVALID_IR_WAVELENGTH_FAULT` | Provided infrared wavelength is not valid. |

General errors are listed in [General error codes](#general-error-codes).

#### getIRWavelength

A CGI method that returns the current wavelength setting.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/lightcontrol.cgi" \\  --data '{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getIRWavelength",  "params": {    "lightID": <string>  }}'
```

```bash
POST /axis-cgi/lightcontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getIRWavelength",  "params": {    "lightID": <string>  }}
```

getIRWavelength

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `params` | JSON object | Container for method specific parameters. |
| `lightID` | String | The light ID. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "getIRWavelength",  "data": {    "IRWavelength": wavelength  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The client sets this value and the CGI will echo this context string back in the response (optional). |
| `method` | String | The performed operation. |
| `data` | JSON object | Container for the response specific parameters. |
| `IRWavelength` | String | An array containing the wavelength settings. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "Echoed if provided by the client in the corresponding request",  "method": "The called method",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

**Error codes**

| Code | Definition | Description |
| --- | --- | --- |
| `1001` | `NOT_SUPPORTED_FAULT` | Method call not supported by the device. |
| `1002` | `INVALID_LIGHT_ID_FAULT` | Provided lightID parameter is not valid for the device. |
| `1005` | `CARD_MALFUNCTIONING_FAULT` | Could not find light hardware, could not complete request. |
| `1006` | `WRONG_POE_CLASS_FAULT` | Wrong POE class, could not complete request. |

General errors are listed in [General error codes](#general-error-codes).

#### General error codes

The following table lists the general errors that can occur for any CGI method, while errors that are specific for a method are listed under their specific API descriptions.

| Code | Definition | Description |
| --- | --- | --- |
| `1000` | PARAM\_INVALID\_VALUE\_ERROR | Invalid parameter value. |
| `2000` | RESOURCE\_MEM\_ERROR | Failed to allocate memory. |
| `2001` | ACCESS\_FORBIDDEN | Access forbidden |
| `2002` | HTTP\_METHOD\_NOT\_SUPPORTED | HTTP request type not supported. Only POST supported. |
| `2003` | API\_VERSION\_NOT\_SUPPORTED | The requested API version is not supported. |
| `2004` | METHOD\_NOT\_SUPPORTED | Method not supported. |
| `3000` | UNSUPPORTED\_API\_VERSION | The requested API version is not supported. |
| `4000` | JSON\_INVALID\_ERROR | The provided JSON input was invalid. |
| `4001` | JSON\_KEY\_NOT\_FOUND\_ERROR | A mandatory input parameter was not found in the input. |
| `4002` | JSON\_INVALID\_TYPE | The provided JSON parameter type was incorrect. |
| `7000` | UNSUPPORTED\_API\_VERSION | The requested API version is not supported by this implementation. |
| `8000` | INTERNAL\_ERROR | Internal error. |
| `8001` | UNEXPECTED\_ERROR | Unexpected error. |
| `8002` | GENERIC\_ERROR | Generic error. |

## Light control service API

info

For a newer version on how to use light control, see [Light control API](#light-control-api).

VAPIX® Light control service API enables applications and users to control built-in lights. Lights can be activated and inactivated using this API or using action rules. The API is a web services API.

A built-in light is an illuminator which is integrated in the Axis product. The illuminator improves the camera’s short-range visibility, in particular in low-light conditions, and can for example be an infrared LED (light emitting diode) or a white LED. In the API, a "light" is a single illuminator or a group of illuminators. Each light is identified by a unique Light ID.

Supported functionality:

-   Retrieve information about the light
-   Enable and activate light. Enabling allows clients and users to control the light. Activating turns the light on.
-   Synchronize with day/night mode. When synchronized, the light is automatically activated in night mode.
-   Control light intensity
-   Control angle of illumination. The angle of illumination (the width of the light beam) can be set to be adjusted automatically according to the camera’s angle of view.

### Prerequisites
#### Identification

Use VAPIX® Entry service API to check if the API is supported.

-   **Namespace**: `http://www.axis.com/vapix/ws/light`
-   **AXIS OS**: 5.40
-   **Product category**: Products with built-in illuminators, for example infrared LEDs or white LEDs.

#### API specification

The API specification is available as an WSDL file at [http://www.axis.com/vapix/ws/LightService.wsdl](http://www.axis.com/vapix/ws/LightService.wsdl)

### Using the light control service
#### Identification

The example outlined in this section shows how to check if the light control service is supported and how to create a light service client.

To check if the Axis product supports the Light control service API, we use `GetServices` from VAPIX® Entry service API.

We start by defining the IP address, user name and password for the Axis product and the namespace of the light control service. Then, we use `CreateEntryServiceClient` to create an entry service client.

info

The function CreateEntryServiceClient is defined in the sample code and is not part of the API. For more information about the entry service, see the VAPIX® Entry service API documentation.

```bash
/\* Define the address, user name and password for the Axis product. <servername> is an IP address or host name.\*/string address="<servername>";string username="<user name>";string password="<password>";/\* Define the namespace of the light control service.\*/string lightTargetNamespace = "http://www.axis.com/vapix/ws/light";/\* Create an Entry Service client.\*/EntryClient myEntryService = CreateEntryServiceClient(address, username, password);
```

Next, we use the entry service client and `GetServices` to get a list of all services in the Axis product. We search the list to check if the light control service is included.

If the service is found, we use `CreateLightServiceClient()` to create a light client. This function is not part of the API and is created in the same way as `CreateEntryServiceClient`.

```bash
/\* Get a list of all services.\*/Service\[\] serviceList = myEntryService.GetServices(false);/\* Check if light control service is supported.\*/for (i = 0; i < serviceList.count; i++){  if (serviceList\[i\].Namespace == lightTargetNamespace)  {    /\* Get the service address.\*/    string lightXaddr = serviceList\[i\].Xaddr;    /\* Create a light client.\*/     LightClient myLightService = CreateLightServiceClient(lightXaddr, username, password);    break;  }}
```

#### Light information

The following functions can be used to retrieve information about the light:

-   The following functions can be used to retrieve information about the light:
    
    `GetServiceCapabilities` — list the supported light control service capabilities.
    
-   `GetLightInformation` — list light information such as the Light ID, type of light, if the light is enabled and error information
    
-   `GetLightStatus` — check if the light is active or inactive
    

This example shows how to list the capabilities provided by the light control service.

To list the service capabilities, we use the light service client `myLightService` created in section [Identification](#identification-using-light-control-service) and `GetServiceCapabilities`.

```bash
/\* Get the service capabilities.\*/Capabilities LightCapabilities = myLightService.GetServiceCapabilities();
```

This example shows how to list information about the light and how to retrieve the Light ID. We use the light service client `myLightService` and the `GetLightInformation` request.

`GetLightInformation` returns a list of light information for all lights. From the list, we can retrieve information about a particular light. Here, we will retrieve the Light ID of the first light.

```bash
/\* Get a list of light information for all lights.\*/LightInformationList\[\] lightInformationList = myLightService.GetLightInformation();/\* Get the Light ID for the first light.\*/LightInformation lightInformation = lightInformationList\[0\];string lightID = lightInformation.LightID;
```

In this example, we use the light service client `myLightService`, the `lightID` and the `GetLightStatus` request to check if the light is lit.

```bash
/\* Check if the light is lit.\*/if (myLightService.GetLightStatus(lightID)){  Console.WriteLine("The light is lit");}else{  Console.WriteLine("The light is not lit");}
```

#### Enable and activate the light

To allow users and clients to control the light, the light must first be enabled. Activating turns the light on.

For products with an IR cut filter, an IR light cannot be activated if the IR cut filter is in "On" mode (that is, when the IR cut filter is blocking IR light).

Supported operations:

-   Supported operations:
    
    `ActivateLight` — turn on the light
    
-   `DeactivateLight` — turn off the light
    
-   `EnableLight` — enable the light control functionality
    
-   `DisableLight` — disable the light control functionality. This prevents users and clients from turning on the light.
    

This example shows to how check if the light is enabled, enable the light and turn it on.

In the example, we use the light service client `myLightService` created in section [Identification](#identification-using-light-control-service) and `lightInformationList` with information about all lights from section [Light information](#light-information).

```bash
/\* Get the Light ID.\*/LightInformation lightInformation = lightInformationList\[0\];string lightID = lightInformation.LightID;/\* Check if the light is enabled.\*/if (!lightInformation.Enabled){  /\* Enable the light.\*/  myLightService.EnableLight(lightID);  /\* Turn on the light.\*/  myLightService.ActivateLight(lightID);}/\* Inform user that light is lit.\*/if (myLightService.GetLightStatus(lightID)){  Console.WriteLine("The light is lit");}
```

#### Light intensity

The light intensity can be controlled automatically or set manually. Due to power and heat constraints, the actual light intensity might be lower than the set value.

info

Support for automatic mode is product dependent. Functionality may differ depending on product model.

Supported operations:

-   Supported operations:
    
    `SetAutomaticIntensityMode` — enable automatic light intensity control
    
-   `SetManualIntensity` — set the intensity manually
    
-   `GetManualIntensity` — get the intensity sent in the `SetManualIntensity` request
    
-   `GetCurrentIntensity` — get the current light intensity
    
-   `GetValidIntensity` — list valid light intensity values
    

This example shows how to list valid light intensity values.

In the example, we use the light service client `myLightService` created in section [Identification](#identification-using-light-control-service) and `lightInformationList` with information about all lights from section [Light information](#light-information).

```bash
/\* Get the Light ID.\*/LightInformation lightInformation = lightInformationList\[0\];string lightID = lightInformation.LightID;/\* Get valid light intensities.\*/IntRangeList\[\] validIntensityList = myLightService.GetValidIntensity(lightID);/\* Print the valid intensity range.\*/for (i = 0; i < validIntensityList.Count; i++){  IntRange validRange = validIntensityList\[i\];  Console.WriteLine("Valid Intensities are {0} - {1}", validRange.Low, validRange.High);}
```

#### Angle of illumination

The angle of illumination defines the width of the light beam. A small angle of illumination gives a narrow beam, a large angle of illumination gives a wide beam.

The angle of illumination can be controlled automatically or set manually. Automatic mode can be used if the product supports absolute zoom (parameter `PTZ.Support.S#.AbsoluteZoom=true`). In automatic mode, the angle of illumination is set according to the camera’s angle of view and will be adjusted when the angle of view changes.

Supported operations:

-   Supported operations:
    
    `SetAutomaticAngleOfIlluminationMode` — control the angle of illumination automatically
    
-   `SetManualAngleOfIllumination` — set the angle of illumination manually
    
-   `GetManualAngleOfIllumination` — get the angle of illumination sent in the `SetManualAngleOfIllumination` request
    
-   `GetCurrentAngleOfIllumination` — get the current angle of illumination
    
-   `GetValidAngleOfIllumination` — list valid angle of illumination values
    

This example shows how to get the current angle of illumination.

In the example, we use the light service client `myLightService` created in section [Identification](#identification-using-light-control-service) and `lightInformationList` with information about all lights from section [Light information](#light-information).

```bash
/\* Get the Light ID.\*/LightInformation lightInformation = lightInformationList\[0\];string lightID = lightInformation.LightID;/\* Get and print the current angle of illumination.\*/int angleOfIllumination = myLightService.GetCurrentAngleOfIllumination(lightID);Console.WriteLine("Current angle of illumination: {0} ", angleOfIllumination);
```

This example shows how to turn off the automatic mode and set the angle to 50.

```bash
/\* Turn off automatic angle of illumination.\*/myLightService.SetAutomaticAngleOfIlluminationMode(lightID, false);/\* Set the angle of illumination to 50.\*/myLightService.SetManualAngleOfIllumination(lightID, 50);/\* Get and print the current angle of illumination.\*/int angleOfIllumination = myLightService.GetCurrentAngleOfIllumination(lightID);Console.WriteLine("Current angle of illumination: {0} ", angleOfIllumination);
```

#### Synchronize with day/night mode

For products with day/night mode capabilities, the light can be synchronized with day/night mode so that the light is automatically activated in night mode. For products with an IR cut filter, an IR light can be synchronized with day/night mode if the IR cut filter is in "Auto" or "Off" mode.

Supported operations:

-   Supported operations:
    
    `GetLightSynchronizeDayNightMode` — check if synchronization with day/night mode is enabled.
    
-   `SetLightSynchronizeDayNightMode` — enable or disable automatic synchronization with day/night mode