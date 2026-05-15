---
title: Fence guard
url: "https://developer.axis.com/vapix/applications/fence-guard/"
category: vapix
subcategory: applications
sha256: ae06163f024540d0ad760b1b053227d39d6727a19c09165068111f61afc92b05
scraped_at: "2026-01-09T15:01:13.441Z"
page_height: 48138
---

# Fence guard

## Description

AXIS Fence Guard is an AXIS Camera Application Platform (ACAP) product for Axis network cameras and encoders.

The ACAP makes it possible for the user to:

-   set up a fence by defining a set of one or more virtual lines in the camera view.
-   configure a set of rules for the lines for when the ACAP should trigger an event.
-   configure so that an event is only triggered if the object adheres to certain dimensional constraints or when it has been visible in the camera view for a set time.

The Fence Guard API is used for configuring the behavior of the ACAP. It is possible to configure where and if a detected object should trigger an alarm.

There is support for ONVIF motion alarm event.

### Methods

The API consists of five methods:

-   `getConfiguration` - Querying the complete ACAP configuration.
-   `setConfiguration` - Upload a complete ACAP configuration file.
-   `getSupportedVersions` - Get supported API versions.
-   `sendAlarmEvent` - Send a stateful alarm event for VMS testing purposes.
-   `getConfigurationCapabilities` - Get the boundaries and default values for the ACAP.

### Identification

-   **Software:** `EmbeddedDevelopment` version 2.13 or higher is required for the ACAP to work.
-   **Property:** `Properties.EmbeddedDevelopment.Version=2.13`

In order to check if the ACAP is installed, use `/axis-cgi/applications/list.cgi`, which shows the status of all installed ACAP’s. It also lists the url to the configuration page and the license state of the ACAP.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Backup and restore configuration

1.  Request the current configuration of the application:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "data": {...}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "error":    {        "code": <error code>,        "message": "A descriptive error message."    }}
    ```
    
3.  Validate current license state of the ACAP.
    
    In order to post configurations to the ACAP, the license key must be valid.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/list.cgi"
    ```
    
    ```bash
    GET /axis-cgi/applications/list.cgiHost: <servername>
    ```
    
4.  Restore settings:
    
    Post the configuration as `params` using the same JSON structure from `data` received from previous call.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}
    ```
    

### Configure all settings

1.  Request the current configuration of the application:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
    ```
    
2.  Parse the JSON response.
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "data": {...}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "error":    {        "code": <error code>,        "message": "A descriptive error message."    }}
    ```
    
3.  Parse the JSON Response:
    
    The configuration JSON object is modified according to [setConfiguration](#setconfiguration).
    
4.  Validate current license state of the ACAP.
    
    In order to post configurations to the ACAP the license key must be valid.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/list.cgi"
    ```
    
    ```bash
    GET /axis-cgi/applications/list.cgiHost: <servername>
    ```
    
5.  Upload new settings:
    
    Post the configuration as `params` using the same JSON structure from `data` received from previous call.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}
    ```
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "data": {...}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "error":    {        "code": <error code>,        "message": "A descriptive error message."    }}
    ```
    

### Visual feedback

**Visualize alarming objects in live view and recorded video**

Use this example to see all alarming objects in order to determine what causes alarms in both live view video, as well as in recorded video.

1.  Configure with `overlayResolution` and `alarmOverlayEnabled`.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3.",    "context": "<client context>",    "method": "setConfiguration",    "params": {        "cameras": \[        {            "active":            "id": 1,            "rotation": r,            "overlayResolution": "1280x720"        }        \],        "profiles": \[        {            "name": "Profile 1",            "alarmOverlayEnabled": true,            ...        }        \]    }}
    ```
    
    Response
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setCOnfiguration",    "data": {...}}
    ```
    
2.  Validate in streams.
    

The video streams use the chosen resolution (e.g. 1280x720) and the specified rotation will have alarming objects with burnt in bounding boxes.

info

It is possible to request a video stream that ignores the alarm overlay despite using the chosen resolution. If the stream parameter overlays is set to either none or dynamic the overlay from the application is not shown.

```bash
rtsp://<servername>/axis-media/media.amp?resolution=1280x720&overlays=off
```

### Read the configuration capabilities

1.  Request the configuration capabilities of the application:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi"
    ```
    
    ```bash
    POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json
    ```
    
    Body:
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
    ```
    
2.  Parse the JSON response
    
    a. Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "data": {...}}
    ```
    
    b. Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "error":    {        "code": <error code>,        "message": "A descriptive error message."    }}
    ```
    

The configuration JSON object is modified according to [getConfigurationCapabilities](#getconfigurationcapabilities).

**Changes between apiVersion 1.2 and 1.3**

Adds support for alarm overlays, which includes two new optional fields in the configuration of the application.

## API specification

All APIs uses the same CGI-call, using `method` property to decide the operation to perform on the data.

The different APIs uses the same error code pattern.

Error codes from 1000 to 1999 are reserved for camera application (server) errors, e.g. could not read configuration from file. The actual cause can be seen in the server-log, and the problem could in some cases be solved by restarting the camera.

Error codes from 2000 to 2999 are reserved for client errors, e.g. wrong format of configuration file or invalid parameter. These errors should be possible to solve by changing the input data to the API.

Error code 8000 indicates that the camera is not supported by this version of the application. This should be possible to solve by downloading the version of the application designed for the camera type.

Error codes 9000 to 9999 are reserved for license related errors e.g. the current license is invalid or missing. These errors should be possible to solve by uploading a new license file for the ACAP.

### getConfiguration

Request the current configuration of the ACAP.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | **Optional** Client sets this value and server echoes data in the response . It is present regardless of whether the response was successful or an error. |
| `method` | Specifies that the `getConfiguration` operation is performed. |

#### Return value - Success

Returns the current configuration of the ACAP, in a JSON formatted response. In the following examples, the values **w, h, t, x, y, p** and **r** are numbers, the variable **direction** is a string with value "**leftToRight**", "**rightToLeft**" or "**both**". The directions left and right are defined from the perspective of a viewer that stands at the starting point of the segment, looking towards the end point of the same segment. The variable `resolution` is a string, e.g. "1280x720" or "640x360". For a complete description of each field in the configuration, see [Configuration parameter description](#configuration-parameter-description).

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfiguration",  "data":  {    "cameras":    \[      { "active": true, "id": 1, "rotation": r, "overlayResolution": resolution}    \],    "profiles":    \[      {        "name": "Profile 1",        "uid": 1,        "camera": 1,        "alarmOverlayEnabled": true,        "filters":        \[          { "type": "sizePerspective", "data": \[w,h\], "active": true },          { "type": "sizePercentage", "data": \[w,h\], "active": false },          { "type": "timeShortLivedLimit", "data": t, "active": true }        \],        "triggers":\[          { "type": "fence", "data": \[ \[x,y\], ..., \[x,y\] \] "alarmDirection": direction }        \],        "presets": \[p\],        "perspective":        \[          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h},          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h},          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h}        \]      },      { ... },      { ... },      { ... }    \],    "configurationStatus": 0  }}
```

**The response if the camera supports multiple channels:**

info

Channel specific properties are set in data.cameras. However, each profile has its individual settings, and refers to a camera id property with the `data.profiles[j].camera property`. The parameter **"presets"** is not present because it is only supported for mechanical PTZ-cameras.

```bash
{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfiguration",  "data":  {    "cameras":    \[      { "active": true, "id": 1, "rotation": r, "overlayResolution": resolution1},      { "active": false, "id": 2, "rotation": r, "overlayResolution": resolution2},      { "active": false, "id": 3, "rotation": r, "overlayResolution": resolution3},      { "active": false, "id": 4, "rotation": r, "overlayResolution": resolution4}    \],    "profiles":    \[      {        "name": "Profile 1",        "uid": 1,        "camera": 1,        "alarmOverlayEnabled": true,        "filters":        \[          { "type": "sizePerspective", "data": \[w,h\], "active": true },          { "type": "sizePercentage", "data": \[w,h\], "active": false },          { "type": "timeShortLivedLimit", "data": t, "active": true }        \],        "triggers": \[          { "type": "fence", "data": \[ \[x,y\], ..., \[x,y\] \] "alarmDirection": direction }        \],        "perspective":        \[          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h},          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h},          { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h}        \]      },      {        "name": "Profile 2",        "uid": 2,        "camera": 3,        "alarmOverlayEnabled": false,        "filters": {...},        "triggers": {...},        "perspective": {...}      },      { ... },      { ... },      { ... }    \],    "configurationStatus": 0  }}
```

#### Return value - Error

Return value `<error code>` is a number.

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfiguration",  "error":  {    "code": <error code>,    "message": "A descriptive error message"  }}
```

| Error | Code | Description |
| --- | --- | --- |
| `Application Error` | 1000 | The application failed to return a configuration |
| `Unsupported Version` | 2000 | The major version number isn’t supported |
| `Invalid Format` | 2001 | The request was not formatted correctly, i.e. does not follow the JSON-schema |
| `Unsupported Product` | 8000 | The product is not supported by this application |

### setConfiguration

Set the configuration of the ACAP. If the ACAP is not restarted beforehand, any ongoing events will be set as inactive when the new configuration is applied. This will cause ongoing recordings to stop. For multichannel products, all cameras are affected simultaneously.

There is a size limitation on POST transfer request which makes it suitable to send a minified JSON structure without white-spaces and new lines.

**Modify specific properties**

Below are some examples for how to change values, in the JSON file to perform specific actions. In the examples `i` is an index in the profile-array, not the `uid` of the profile.

**Enable alarm overlay**

In order to enable Alarm overlay for a profile, the resolution has to be specified for the camera in `params.cameras[i].overlayResolution`. Supported resolutions are listed by the `getConfigurationCapabilities` method. These resolutions will change if the capture mode in the camera is changed.

Each profile that is connected to that camera can then be specified to visualize its alarming objects in the video by activating the parameter `params.profiles[i].alarmOverlayEnabled`.

```bash
"cameras": \[{  "active": true,  "id": 1,  "rotation": r,  "overlayResolution": "1280x720"}\],"profiles": \[{  "name": "Profile 1",  "camera": 1,  "alarmOverlayEnabled": true  ...  }\]
```

**Set image rotation**

The image rotation for which the configuration is done should be specified in `params.cameras[i].rotation`. Valid values are (0, 90, 180, 270), which corresponds to the rotation of the camera.

**Modify fence**

To change the fence of a profile consisting of `n` connected straight lines connecting points `[x0,y0], ..., [xn,yn]` with alarm direction **direction** change the property `params.profiles[i].triggers` to

```bash
"triggers":\[  { "type": "fence", "data": \[ \[x0,y0\], ..., \[xn,yn\] \], "alarmDirection": direction}\]
```

**Modify size perspective filter**

In order to apply a size perspective filter with two perspective bars with height and width defined as h1 `[x11, y11], [x12,y12]` and h2 `[x21, y21], [x22,y22]`. The first set of numbers are the start position, the second set of numbers are the end position. Both `params.profiles[i].perspective` and the size filter must be modified.

The perspective bars are added by changing `params.profiles[i].perspective` to

```bash
"perspective":\[  { "type": "bar", "data": \[ \[x11,y11\], \[x12,y12\] \], "height": h1},  { "type": "bar", "data": \[ \[x21,y21\], \[x22,y22\] \], "height": h2},\]
```

The size filter in `params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "sizePerspective", "data": \[w,h\], "active": true },  ...\]
```

The filter values width `w` and height `h`, and the heights of the perspective bars should be given in cm. Only one size filter can be active at any time, so `sizePercentage` must be disabled if `sizePerspective` is used. It is also crucial that the camera rotation is the same as the rotation specified in the configuration.

**Set percentage filter**

To apply a percentage filter with height `h` and width `w` in percent of image, `params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "sizePercentage", "data": \[w,h\], "active": true },\]
```

Note that only one size filter can be active at any time, so `sizePerspective` must be disabled if `sizePercentage` is used. The width and height of an object follows the camera rotation, and the direction used will change if the rotation parameter is changed. That is, for a camera with a 640x360 resolution and a filter with width 10% and height 20%, then the corresponding box will have a size of 64x72 pixels if the camera rotation is 0 or 180 degrees. However, if the rotation is changed to 90 or 270 degrees, the same filter setting (width 10% and height 20%), corresponds to a box of 36x128 pixels.

**Set short-lived object filter**

In order to set the short-lived object filter value to `t` seconds `params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "timeShortLivedLimit", "data": t, "active": true },  ...\]
```

**Modify presets**

**Note: Only for PTZ cameras. PTZ encoders are not supported.**

To change the presets of a profile change the property `params.profiles[i].presets` to

```bash
"presets": \[p\]
```

where **p** is the id-number of the preset, the index value in the VAPIX-parameter `PTZ.Preset.P0.Position.P<index>`. The value can also be –1 for `any-preset` or –2 for `anywhere`.

**Modify specific properties**

Below are some examples for how to change values, in the JSON file to perform specific actions. In the examples `i` is an index in the profile-array, not the `uid` of the profile.

#### Request

-   **Security level:** Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi" \\  --data '{  "apiVersion": "1.3",  "context": "<client context>",  "method": "setConfiguration",  "params":  {    "cameras":    \[      {"active": true, "id": 1, "rotation": r, "overlayResolution": resolution}    \],    "profiles":    \[      {        "name": "Profile 1",        "uid": 1,        "camera": 1,        "alarmOverlayEnabled": true,        "filters":        \[          { "type": "sizePerspective", "data": \[w,h\], "active": true },          { "type": "sizePercentage", "data": \[w,h\], "active": false },          { "type": "timeShortLivedLimit", "data": t, "active": true }        \],        "triggers": \[          { "type": "fence", "data": \[ \[x,y\], ..., \[x,y\] \], "alarmDirection": direction }        \],        "presets": \[p\],        "perspective":        \[          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h},          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h},          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h}        \]      },      { ... },      { ... },      { ... }    \]  }}'
```

```bash
POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "setConfiguration",  "params":  {    "cameras":    \[      {"active": true, "id": 1, "rotation": r, "overlayResolution": resolution}    \],    "profiles":    \[      {        "name": "Profile 1",        "uid": 1,        "camera": 1,        "alarmOverlayEnabled": true,        "filters":        \[          { "type": "sizePerspective", "data": \[w,h\], "active": true },          { "type": "sizePercentage", "data": \[w,h\], "active": false },          { "type": "timeShortLivedLimit", "data": t, "active": true }        \],        "triggers": \[          { "type": "fence", "data": \[ \[x,y\], ..., \[x,y\] \], "alarmDirection": direction }        \],        "presets": \[p\],        "perspective":        \[          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h},          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h},          { "type": "bar", "data": \[ \[x,y\], ..., \[x,y\] \],"height": h}        \]      },      { ... },      { ... },      { ... }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `method` | Specifies that the `setConfiguration` operation is performed. |
| `context` | **Optional** Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `params` | A complete ACAP configuration. **Note:** To remove a profile, remove that profile object from the `params.profiles` array. For a complete description of each field in the configuration see [Configuration parameter description](#configuration-parameter-description). |

#### Return value - Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

Note that successful calls contains en empty `data` object.

#### Return value - Failure

Return value `<error code>` is a number.

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context":  "<client context>",  "method": "setConfiguration",  "error":  {    "code": <error code>,    "message": "A descriptive error message"  }}
```

| Error | Code | Description |
| --- | --- | --- |
| `Application Error` | 1000 | The application failed to set the configuration. |
| `Unsupported Version` | 2000 | The major version number isn’t supported. |
| `Invalid Format` | 2001 | The configuration was not formatted correctly, i.e. does not follow the JSON-schema. |
| `Incoherent Format` | 2002 | Parts of the configuration contradict each other, e.g. several profiles have the same `uid`. |
| `Missing Parameter` | 2003 | The request has a missing mandatory parameter. |
| `Invalid Parameter` | 2004 | The request has parameters that has an invalid value. |
| `Unsupported Product` | 8000 | The product is not supported. |
| `Invalid License` | 9000 | The license file is invalid or missing. |

### getConfigurationCapabilities

Request the boundaries and default values of the ACAP.

#### Request

-   **Security level:** Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | **Optional** Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `getConfigurationCapabilities` operation is performed. |

#### Return value - Success

Return the boundaries and default values of the ACAP, in a JSON formatted response. This cgi will always return the same result for one camera independent of when it is called, i.e. these values cannot be changed through a cgi. However different cameras might return different result depending on their capabilities. In the following examples the values **p, q, r** and **z** are numbers. For a complete description of each field in the configuration see [Configuration capabilities parameter description](#configuration-capabilities-parameter-description).

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data":  {    "alarmOverlay":{      "isSupported": true,      "cameras": \[        {"id": 1, "availableResolutions": \["1280x720", "640x360", ...\]},        {"id": 2, "availableResolutions": \["640x360", ...\]}      \]      "maxNbrActiveCameras": 1    },    "filters":    \[      {        "type": "sizePercentage",        "min": \[width, height\],        "max": \[width, height\],        "default": \[width, height\],        "defaultActive": true      },      {        "type": "timeShortLivedLimit",        "min": p,        "max": q,        "default": r,        "defaultActive": true      }    \],    "triggers":    \[      {        "type": "fence",        "min": \[x,y\],        "max": \[x,y\],        "minNbrVertices": p,        "maxNbrVertices": q,        "minNbrInstances": r,        "maxNbrInstances": z,        "validAlarmDirection": \["leftToRight", "rightToLeft", "both"\],        "defaultInstance": \[ \[x,y\], \[x,y\], \[x,y\], \[x,y\] \],        "defaultAlarmDirection": direction      }    \],    "profiles":    {      "minNbrProfilesPerCamera": p,      "maxNbrProfilesPerCamera": q,      "minLengthName": r,      "maxLengthName": z    }    "presets":    {      "maxNbrPresets": p,      "defaultPreset": q    }  }}
```

#### Return value - Error

Return value `<error code>` is a number.

```bash
Content-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "error":  {    "code": <error code>,    "message": "A descriptive error message"  }}
```

| Error | Code | Description |
| --- | --- | --- |
| `Application Error` | 1000 | The application failed to return a configuration. |
| `Unsupported Version` | 2000 | The major version number isn’t supported. |
| `Invalid Format` | 2001 | The request was not formatted correctly, i.e. does not follow the JSON-schema. |
| `Unsupported Product` | 8000 | The product is not supported by this application. |

### getSupportedVersions

Get a list of supported API versions for the ACAP (one for each major version).

#### Request

-   **Security level:** Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fenceguard/control.cgi" \\  --data '{    "apiVersion": "1.3",    "method": "getSupportedVersions",    "context": "<client context>"}'
```

```bash
POST /local/fenceguard/control.cgiHost: <servername>{    "apiVersion": "1.3",    "method": "getSupportedVersions",    "context": "<client context>"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `method` | Specifies that the `getSupportedVersions` operation is performed. |
| `context` | **Optional** Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |

#### Return value - Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "method": "getSupportedVersions",    "context": "<client context>",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `apiVersions=<list of versions>` | List of supported versions, all major versions with highest supported minor version. |
| `<list of versions>` | List of `<major>.<minor>` versions e.g. `["1.4","2.5"]`. |

#### Return value - Failure

Return value `<error code>` is a number.

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "method": "getSupportedVersions",  "context": "<client context>",  "error":  {    "code": <error code>,    "message": "A descriptive error message"  }}
```

| Error | Code | Description |
| --- | --- | --- |
| `Application Error` | 1000 | The application failed to return the supported versions. |
| `Unsupported Version` | 2000 | The major version number isn’t supported |
| `Invalid Format` | 2001 | The request was not formatted correctly, i.e. does not follow the JSON-schema. |
| `Unsupported Product` | 8000 | The product is not supported by this application. |

### sendAlarmEvent

By using this method, it is possible to send a stateful alarm event for the specific profile `<uid>`. The stateful alarm event is active for a few seconds. The response message will be returned immediately. This can be used by VMS installers to check that the VMS configuration is correct (e.g. start recording). All events related to the profile will be sent.

**Note:** The profile will send events independent of its current state, i.e. in PTZ products, profiles that are connected to other than the current preset will also send events if triggered by the `sendAlarmEvent` method.

#### Request

-   **Security level:** Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fenceguard/control.cgi" \\  --data '{  "apiVersion": "1.3",  "method": "sendAlarmEvent",  "context": "<client context>",  "params":  {    "profile": <uid>  }}'
```

```bash
POST /local/fenceguard/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.3",  "method": "sendAlarmEvent",  "context": "<client context>",  "params":  {    "profile": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context` | **Optional** Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `sendAlarmEvent` operation is performed. |
| `profile=<uid>` | Defines which profile that will send the motion alarm event. |
| `<uid>` | The unique id that each profile has. There must be a profile with the specified `uid`. |

#### Return value - Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "method": "sendAlarmEvent",    "context": "<client context>",    "data": {}}
```

#### Return value - Failure

Return value `<error code>` is a number.

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "method": "sendAlarmEvent",  "context": "<client context>",  "error":  {    "code": <error code>,    "message": "A descriptive error message"  }}
```

| Error | Code | Description |
| --- | --- | --- |
| `Application Error` | 1000 | The application failed to handle the request. |
| `Unsupported Version` | 2000 | The major version isn’t supported. |
| `Invalid Format` | 2001 | The request was not formatted correctly, i.e. invalid JSON-schema. |
| `Incoherent Format` | 2002 | The request cannot be handled, e.g. profile-id does not exist or is on an inactive camera. |
| `Missing Parameter` | 2003 | The request has a missing mandatory parameter. |
| `Invalid Parameter` | 2004 | The request has a parameter that has an invalid value. |
| `Unsupported Product` | 8000 | The product is not supported by this application. |
| `Invalid License` | 9000 | The license file is invalid or missing. |

### Configuration parameter description

The structure of a configuration object is the same in both the `data` object in the response for `getConfiguration` and the `params` object in the request for `setConfiguration`. The structure is the same for single and multichannel products, where the `cameras` objects should mirror the different VAPIX camera properties. The only difference appears when PTZ cameras are used, in which case the parameter **preset** can be optionally included.

**Example configuration**

The following example configuration will be described in details in table [Parameter description table](#parameter-description-table).

```bash
{  "cameras":  \[    { "active": bool, "id": 1, "rotation": r, "overlayResolution": resolution}  \],  "profiles":  \[    {      "name": "<client nice-name>",      "uid": <uid>,      "alarmOverlayEnabled": true,      "camera": 1,      "filters":      \[        { "type": "sizePerspective", "data": \[w,h\], "active": true },        { "type": "sizePercentage", "data": \[w,h\], "active": false },        { "type": "timeShortLivedLimit", "data": t, "active": true }      \],      "triggers": \[        { "type": "fence", "data": \[ \[x,y\], ..., \[x,y\] \], "alarmDirection": direction }      \],      "presets": \[1\],      "perspective":      \[        { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h},        { "type": "bar", "data": \[ \[x,y\], \[x,y\] \], "height": h}      \]    },    { ... },    { ... },    { ... }  \],  "configurationStatus": 0}
```

#### Parameter description table

All parameters and properties are considered mandatory unless otherwise specified. The default values for the filters and triggers are recommended values, to get the values used by the application use the [getConfigurationCapabilities](#getconfigurationcapabilities).

The `cameras` object contains general information that is the same for all profiles using that camera.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `cameras[i].active` | boolean | true | true, false | It is possible to have active profiles for the camera if set to `true`. All profiles for that camera are currently inactivated if set to `false.` |
| `cameras[i].id` | integer | 1 | 1, ..., #Cameras | The corresponding camera value used when requesting a video using `media.amp`. Note that it starts at 1. |
| `cameras[i].rotation` | integer | 0 | 0, 90, 180 or 270 | The rotation of the camera in the plane of the camera, measured in degrees. Should match the property `Image.I<camera>.Appearance.Rotation`. |
| `cameras[i].overlayResolution` | string |  | `<width>x<height>` | The resolution of the video streams that will have the alarming objects burnt in as an alarm overlay. The parameter is optional if `profiles[j].alarmOverlayEnabled` is not active. |

The `profiles` object information for each individual profile.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `profiles[j].name` | string | `Profile <uid>` |  | A unicode string up to 15 characters long. It is part of the nice name of the event, and is visible to the end user in the action rule list. Invalid character combinations are: \[`&&`, `<`, `>`\]. |
| `profiles[j].camera` | int | 1 | 1, 2, 3, ..., | Shall match `id` of the corresponding camera in `cameras`. |
| `profiles[j].uid` | int | 1 | 1, 2, 3, ..., | Shall be an unique id for each profile. |
| `profiles[j].alarmOverlayEnabled` | int | false | true, false | `true` if the alarming objects of the profile are shown in an alarm overlay video stream. The parameter is optional, and defaults to `false` if it is not present. |
| `profiles[j].filters` | array |  |  | An array of exclusion filters. |
| `profiles[j].triggers` | array |  |  | An array of triggers. |
| `profiles[j].presets` | array |  |  | An array with a single preset index number (optional). See [Parameter presets description](#parameter-presets-description). |
| `profiles[j].perspective` | array | `[]` |  | An array of perspective objects. |

The exclusion filters of `profiles[j].filters` have similar structure. The exclusion filters are all optional, and a filter is considered disabled if it is not present in the array `profiles[].filters`.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | string | See separate table. | Specifies the type of exclusion filter. |
| `profiles[j].filters[k].data` |  |  | The data for the the exclusion filter. The type differs for each exclusion filter. |
| `profiles[j].filters[k].active` | boolean | true, false | If the filter is active. Not applicable for exclude areas. |

The data field for each exclusion filter.

| Exclusion filter type | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `"sizePercentage"` | `[int, int]` | `[5, 5]` | `[3..100, 3..100]` | An array with width and height (`[w, h]`) in percent of the image. If the height and width of an object is measured as a percentage of the total camera view and it is less than or equal to the set values, it will not be able to raise an alarm. |
| `"sizePerspective"` | `[int, int]` |  |  | An array with width and height (`[w, h]`) in real-world size for an object in the scene. If the object’s width and height is below this value, it will not raise an alarm. The real-world height of the object is computed by comparing the pixel height of the object with the pixel height of the perspective bars. Since the perspective bars each have a real-world height assigned to them by the user, the corresponding height of the object can be computed using a linear equation. Two objects with the same height in pixel at different horizontal positions will have different real-world heights. |
| `"timeShortLivedLimit"` | int | 1 | 1..5 | The value reflects how many seconds the object has to be in the camera view before it can raise an alarm. If the object does something that should trigger an alarm before the set time has passed, the alarm is temporarily suppressed. If the object is still in the camera view after the expiration of the set time, an alarm will be raised. If the object has disappeared from the camera view the alarm will not be raised. |

The only type of trigger in Fence Guard is `fence`. The array `profiles[j].triggers` should contain exactly one fence. But this can change in the future.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].triggers[0].type` | string | "`fence`" | Specifies that it is a fence. |
| `profiles[j].triggers[0].data` | `[ [float, float], ..., [float, float] ]` | \- 1, ..., 1 | A fence is described as an array of points `[ [x0,y0], ..., [xn,yn] ]`, where the unit are normalized to the size of the image, so that the visible view spans from -1 to 1 in both horizontal and vertical direction. |
| `profiles[j].triggers[0].alarmDirection` | string | "`leftToRight`", "`rightToLeft`", "`both`" | `leftToRight`: fence should raise alarm when an object crosses the line segment from left to right. `rightToLeft`: fence should raise alarm when on object crosses the line segment from right to left. `both`: fence should raise alarm when an object crosses the line segment in either directions. The directions left and right are defined from the perspective of a viewer that stands at the starting point of the segment, looking towards the end point of the same segment. |

It is only possible to have the exclusion filter "`sizePerspective`" if there is a perspective. It is described by an array of perspective objects, that calibrates the view of the camera. The only type of perspective objects are `bar`.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `configurationStatus` | int | 0, ..., MAX\_INT | This property is read-only and therefore ignored by `setConfiguration`. The initial value, 0, indicates a default configuration i.e. that no configuration has yet been set. Each time a configuration is set, the value is increased by one. Note that the value is reset to 1 after `MAX_INT` has been reached. |
| `profiles[j].perspective[k].type` | string | `bar` | Specifies that it is a perspective bar. Which is a vertical line in the rotation of the camera. |
| `profiles[j].perspective[k].data` | `[ [float,float], ..., [float,float] ]` | \-1, ..., 1 | Start and end points for a perspective bar. The start position should be the point that touches the ground-plane. The unit are normalized to the size of the image, so that the visible view spans from -1 to 1 in both horizontal and vertical direction. |
| `profiles[j].perspective[k].height` | int |  | Real-world height of an object appearing at the same location and with the same perceived height in the camera view as the perspective bar. |

#### Parameter presets description

In `apiVersion` 1.1 the parameter `profiles[j].presets` was introduced. It must be an array which can contain at most one preset. But this may change in the future. The profile will not be connected to any presets if the presets array is empty, and will always be active, i.e. it is connected to "anywhere". The client is responsible for connecting a profile to an existing preset. Note that if the connected preset is deleted, there is no automatic handling for updating the configuration. The parameter will cause an error in non PTZ-cameras.

The parameter is optional in PTZ-cameras, and if the parameter is omitted it is equivalent to an empty array, i.e. the profile is always active.

A parameter value for `any-preset` is -1 and for `anywhere` it is -2.

`anywhere` **(value: -2):** A profile that is connected to `anywhere` is always active, both if the PTZ-camera points at a preset or if it is manually moved away from a preset. Settings for such a general profile should be used with care to handle all different conditions.

`any-preset` **(value: -1):** A profile that is connected to `any-preset` is active as long as the camera is at ANY preset, but not if it is manually moved away from the preset. This setting should also be used with care. It is useful for connecting a general action rule, where false alarms are OK, e.g. turn on lights.

**Note:** If all presets have a profile connected to them, one can use the event `CameraXProfileANY` to also capture triggers from all presets. This also means that it is possible to adapt the settings for each preset.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `profiles[j].presets` | array of int | `[]` | `[-2]`, `[-1]`, `[]`, `[1]`, `[2]`, `[3]`, ... | The index number of the preset, e.g. 1 for parameter `PTZ.Preset. P0.Position.P1`. The value can be -1 for `any-preset` or -2 for `anywhere`. |

#### Different apiVersion values for alarmOverlay parameters

In `apiVersion` 1.3 the parameters `profiles[j].alarmOverlayEnabled` and `cameras[i].overlayResolution` are introduced. They control if the alarms from a profile should be burnt into the video.

The application is able to support clients using `apiVersion` 1.2 or older. Because of this, some special handling of these parameters have been introduced.

If the values are activated from a configuration using at least `apiVersion` 1.3, the feature is enabled. Later, if a client with `apiVersion` 1.2 or lower configures the application the values for `profiles[j].alarmOverlayEnabled` and `cameras[i].overlayResolution` are ignored if present and the values from the existing configuration is used instead.

### Configuration capabilities parameter description

The table below describe the parameters in the [getConfigurationCapabilities](#getconfigurationcapabilities).

**AlarmOverlay**

alarmOverlay

| Property | Type | Description |
| --- | --- | --- |
| `isSupported` | boolean | True, if the camera is supporting the burnt in overlay feature. |
| `maxNbrActiveCameras` | int | The number of different cameras in a multichannel device that simultaneously can use the feature. The value is 0 if the feature is not supported. |
| `cameras` | `[object, object]` | A list of camera objects that describe the alarm overlay capabilities for each camera. |

alarmOverlay.cameras`[]`

| Property | Type | Description |
| --- | --- | --- |
| `id` | int | Same as the parameter `cameras[i].id` in the configuration and the corresponding camera value (value starts at 1) used when requesting a video using `media.amp`. |
| `availableResolutions` | `[string, string, ...]` | A list of resolutions of the form `<width>x<height>` for which it is possible to use alarm overlay for the specific camera. |

**Filters**

sizePercentage

| Property | Type | Description |
| --- | --- | --- |
| `min` | `[int,int]` | An array containing the minimum allowed width and height (`[w, h]`) in percent of the image. |
| `max` | `[int,int]` | An array containing the maximum allowed width and height (`[w, h]`) in percent of the image. |
| `default` | `[int,int]` | An array containing the default values of width and height (`[w, h]`) in percent of the image. |
| `defaultActive` | boolean | If the filter is active by default. |

timeShortLivedLimit

| Property | Type | Description |
| --- | --- | --- |
| `min` | int | The minimum allowed time in seconds. |
| `max` | int | The maximum allowed time in seconds. |
| `default` | int | The default time in seconds. |
| `defautActive` | boolean | If the filter is active by default. |

**Triggers**

fence

| Property | Type | Description |
| --- | --- | --- |
| `min` | `[int, int]` | An array `[xPos, yPos]` with the minimum allowed values in the x- and y-directions for the fence. |
| `max` | `[int, int]` | An array `[xPos, yPos]` with the maximum allowed values in the x- and y-directions for the fence. |
| `minNbrVertices` | int | The minimum number of vertices the fence may contain. |
| `maxNbrVertices` | int | The maximum number of vertices the fence may contain. |
| `minNbrInstances` | int | The minimum allowed number of fences. |
| `maxNbrInstances` | int | The maximum allowed number of fences. |
| `validAlarmDirections` | list of strings | The possible directions that the fence can have. |
| `defaultInstance` | `[ [x, y], [x, y], [x, y], [x, y] ]` | The default fence, an array of arrays containing the default vertices. |
| `defaultAlarmDirection` | string | The default alarm direction for a fence. |

Profiles

| Property | Type | Description |
| --- | --- | --- |
| `minNbrProfilesPerCamera` | int | The minimum number of profiles a configuration may contain. |
| `maxNbrProfilesPerCamera` | int | The maximum number of profiles a configuration may contain. |
| `minLengthName` | int | The minimum number of characters for a profile name. |
| `maxLengthName` | int | The maximum number of characters for a profile name. |

Presets

| Property | Type | Description |
| --- | --- | --- |
| `maxNbrPresetsPerProfile` | int | The maximum number of presets a profile can be connected to. |
| `defaultPreset` | int | The preset that the profile is connected to by default. |

**Note:** This section is only included in the configuration for mechanical PTZ cameras.

## Events
### Fence guard event

**Note:** No events are declared and the ACAP does not run if the license for the ACAP id invalid or missing.

**Declaration of the Fence guard event**

The declaration of the Fence guard event can be accessed through VAPIX and ONVIF event web service API:s.

The declaration of the Fence guard event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform aev:NiceName="Applications">  <FenceGuard aev:NiceName="Fence Guard">    <CameraXProfileY wstop:topic="true" aev:NiceName="Fence Guard: <profile.name>">      <aev:MessageInstance aev:isProperty="true">        <aev:DataInstance>          <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true"/>        </aev:DataInstance>      </aev:MessageInstance>    </CameraXProfileY>  </FenceGuard></tnsaxis:CameraApplicationPlatform>
```

The event in this example is named CameraXProfileY, it is sent every time an object has crossed a specific fence In the alarm direction. It is based on a profile with `camera=X` and `uid=Y`. If it is a multichannel product the nicename attribute is changed to:

```bash
aev:NiceName="Fence Guard: <profile.name> (Image.I<profile.camera>.Name>)"
```

The name of the camera is taken from the parhand using the `Image.I<index>.Name` parameter. Value `<index>` is the same as the camera source value `camera=X` minus one.

The properties can be used for matching the criteria for triggering an action rule:

`Property=<active>` - Required. When an object crosses a fence direction the event is activated. It is inactivated after a short period of time.

`<active>` - A stateful event. An active event has the value "1", and an inactive event has the value "0".

**Declaration of the Fence guard events for multichannel products**

The following example shows how an event declaration will look for a scenario with a multichannel product with two cameras, and each camera has two profiles. The Namespaces and unnecessary tags has been removed for readability.

```bash
<TopicSet>    <CameraApplicationPlatform>        <FenceGuard NiceName="Fence Guard">            <Camera1Profile1 topic="true" NiceName="Fence Guard: Garden Left (Camera 1)">                <MessageInstance isProperty="true">                    <DataInstance>                        <SimpleItemInstance Type="xsd:boolean" />                    </DataInstance>                </MessageInstance>            </Camera1Profile1>            <Camera1Profile2 topic="true" NiceName="Fence Guard: Garden Right (Camera 1)">...</Camera1Profile2>            <Camera2Profile3 topic="true" NiceName="Fence Guard: Parking Day (Camera2)">...</Camera2Profile3>            <Camera2Profile4 topic="true" NiceName="Fence Guard: Parking Night (Camera 2)">...</Camera2Profile4>        </FenceGuard>    </CameraApplicationPlatform>    ...</TopicSet>
```

**CameraXProfileANY event**

When the ACAP detects an object crossing a fence, it will be sent as an ANY event element for a specific camera.

The declaration of an ANY event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform>    <FenceGuard aev:NiceName="Fence Guard">        <CameraXProfileANY wstop:topic="true" aev:NiceName="Fence Guard: Any Profile">            .    .    .        </CameraXProfileANY>    </FenceGuard></tnsaxis:CameraApplicationPlatform>
```

The event in this example is named CameraXProfileANY and is sent every time an object has crossed a specific fence. It is based on a profile with `camera=X`. If it is a multichannel product the nicename attribute is changed to:

```bash
aev:NiceName="Fence Guard: Any Profile (<Image.I<profile.camera>.Name>)"
```

The name of the camera is taken from the parhand using the `Image.I<index>.Name` parameter. Value `<index>` is same as camera source value `camera=X` minus one.

**CameraANY event**

When the ACAP detects an object crossing a fence, it will be sent as a global ANY event element. A global ANY event is an ANY event for ANY camera, which means an alarm on any of the channels will also trigger this event.

The declaration of such ANY event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform>    <FenceGuard aev:NiceName="Fence Guard">        <CameraANY wstop:topic="true" aev:NiceName="Fence Guard: Any Camera">            .    .    .        </CameraANY>    </FenceGuard></tnsaxis:CameraApplicationPlatform>
```

**The event stream**

A client may subscribe to events from the VAPIX/ONVIF event stream. The format of the stream and its element are described in [http://www.onvif.org/onvif/ver10/schema/onvif.xsd](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [http://www.onvif.org/onvif/ver10/topics/topicns.xml](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

Using VAPIX, this stream can be retrieved over RTSP using the url:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=axis:CameraApplicationPlatform/fenceguard/.
```

It is also possible to listen for a specific profile as below.

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=axis:CameraApplicationPlatform/FenceGuard/CameraXProfileY/.
```

**CameraXProfileY**

When the ACAP detects an object crossing a fence, it will be sent as an event element. An example of such an event is described below.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics">            <wsnt:ProducerReference>                <wsa5:Address>uri://2a513b80-8211-4034-82e7-e8d48792c845/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2016-05-23T06:21:10.290542Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

The UtcTime of the message refers to the time of the event, i.e. this should be in sync with time stamps in an image stream with images of the actual physical event that took place.

**Synchronize metadata with video stream**

Axis cameras uses the Real Time Streaming Protocol (RTSP) for controlling the media streaming between the camera and its clients. RTSP uses the Realtime Transport Protocol (RTP) for the packet format for the streaming of the meta/video data, and the RTP Control Protocol (RTCP) for the synchronization of the metadata and video data stream. The synchronization conversion from the absolute time (UTC timestamp) at the motion detection to the relative time (RTP timestamp) for the video stream, can be found in the RTCP packets.

### ONVIF MotionAlarm event

**Declaration of the MotionAlarm event**

The declaration of the ONVIF Motion Alarm event can be accessed through the VAPIX and ONVIF event we service API:s. ONVIF event corresponds to CameraXProfileANY event. An ONVIF event will be sent if there is an ANY event being sent for a specific camera.

The declaration of the ONVIF Motion Alarm event as received from the VAPIX API:

```bash
<tns1:VideoSource>    <MotionAlarm wstop:topic="true">        <tt:MessageDescription IsProperty="true">            <tt:Source>                <tt:SimpleItemDescription Name="Source" Type="tt:ReferenceToken" />            </tt:Source>            <tt:Data>                <tt:SimpleItemDescription Name="State" Type="xs:boolean" />            </tt:Data>        </tt:MessageDescription>    </MotionAlarm></tns1:VideoSource>
```

| Parameter | Description |
| --- | --- |
| `Property=<Source>` | Required. The video source for ONVIF, which starts counting from 0. |
| `<Source>` | Reference counter starts at 0. |
| `Property=<Data>` | Required. The value for Motion Alarm State. |
| `<State>` | An active event has the value "1", and an inactive event has the value "0". |

**The event stream**

A client may subscribe to events from the VAPIX/ONVIF event stream. The format of the stream and its elements are described in [http://www.onvif.org/onvif/ver10/schema/onvif.xsd](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [http://www.onvif.org/onvif/ver10/topics/topicns.xml](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

Using VAPIX, this stream can be retrieved over RTSP using:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=onvif:VideoSource/MotionAlarm/.
```