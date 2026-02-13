---
title: Video motion detection 4 API
url: "https://developer.axis.com/vapix/applications/video-motion-detection-4-api/"
category: vapix
subcategory: applications
sha256: 71266ae65a8f73a7828849c94468c3f2abecef67ce6644b4a197b2466ab91244
scraped_at: "2026-01-09T15:01:32.449Z"
page_height: 42883
---

# Video motion detection 4 API

## Description

AXIS Video Motion Detection 4 is an AXIS Camera Application Platform (ACAP) application that detects moving objects in the camera’s field of view. When a moving object is detected, AXIS Video Motion Detection 4 sends an alarm (event). A client application that listens to events from AXIS Video Motion Detection 4 can use the event to, for example, record video or send a notification.

AXIS Video Motion Detection 4 is preinstalled in products with AXIS OS 6.50 and later but must be started before it can be used. In products with older AXIS OS, the application must first be uploaded and then started. The application can be configured by modifying the include area and, optionally, exclude areas and ignore filters. Include and exclude areas define the parts of the scene in which moving objects should be detected. Ignore filters are used to avoid detecting objects such as shadows of swaying trees, lights from passing cars and small animals regardless of where in the scene the objects appear.

When there are moving objects in the camera’s field of view, the application tests the object’s position, size and movements against the include area, exclude areas and filter conditions to determine if the object should be reported as detected or ignored. If the object is reported as detected, an event is emitted.

When using ignore filters, events will not be emitted until the filter conditions have been fulfilled. For example, when using the `Short-lived Object Filter` parameter, events will be sent if the object is still moving when the set time has passed. That is, all events will be delayed by the set time. If the event is used to start a recording, it is recommended to configure the pre-trigger time in the recording setup so that the recording also includes the time the object moved in the scene before being detected.

When the application is configured using the Axis product web pages, visual confirmation can be used to help understand the effect of the different filters. When visual confirmation is enabled, colored polygons show which objects the application detects and which objects the application ignores.

AXIS Video Motion Detection 4 (VMD4) with dynamic background filter and support for three include areas now replaces the built-in motion detection. It will eventually also replace AXIS Video Motion Detection 3 (VMD3).

### Methods

The API consists of five methods:

-   `getConfiguration` - Get the complete ACAP configuration.
-   `setConfiguration` - Upload a complete ACAP configuration file.
-   `getSupportedVersions` - Get the supported API versions.
-   `sendAlarmEvent` - Send a stateful alarm event for VMS testing purposes.
-   `getConfigurationCapabilities` - Get the boundaries and default values for the ACAP.

### Identification

AXIS Video Motion Detection 4 is preinstalled in Axis network video products with AXIS OS 6.50 and later. Use `/axis-cgi/applications/list.cgi` to list applications, it also lists the url to the configuration page.

AXIS Video Motion Detection 4 can be uploaded to Axis network video products with:

-   **Property**: `Properties.EmbeddedDevelopment.Version=2.12` or later
-   **Software**: AXIS Camera Application Platform (ACAP)
-   **Product category**: Axis network cameras and video encoders. Note that this intended for fixed cameras.

Multiple profiles are supported by the same amount of entries `[i]` as there are channels. For more information, see [Parameter description table](#parameter-description-table).

### Limitations

It is not possible to get the configuration from a stopped application.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

All code listings are examples. See [API documentation](#api-documentation) for a detailed description of each API command.

### Backup and restore configuration

Use this example to back up all of the configurations in a camera, and later restore them without having to set each parameter individually.

1.  Request the current configuration of the application.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}'
    ```
    
    ```bash
    POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
    ```
    
2.  Parse the JSON response.
    
    Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "data": {...}}
    ```
    
    Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "error":    {        "code": XXXX,        "message": "A descriptive error message."    }}
    ```
    
3.  Restore settings
    
    Post the configuration as `params` using the same JSON structure from `data` received from previous call.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}'
    ```
    
    ```bash
    POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}
    ```
    

### Configure all settings

Use this example to retrieve the most current configuration of all parameters, change certain values and upload the updated configuration back to the application.

1.  Request the current configuration of the application.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}'
    ```
    
    ```bash
    POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
    ```
    
2.  Parse the JSON response.
    
    Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "data": {...}}
    ```
    
    Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration",    "error":    {        "code": XXXX,        "message": "A descriptive error message."    }}
    ```
    
3.  Parse the JSON response.
    
    The configuration JSON object is modified according to setConfiguration.
    
4.  Upload new settings
    
    Post the configuration as `params` using the same JSON structure from `data` received from previous call.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}'
    ```
    
    ```bash
    POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "params": {...}}
    ```
    
    Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "data": {...}}
    ```
    
    Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "error":    {        "code": XXXX,        "message": "A descriptive error message."    }}
    ```
    

### Read the configuration capabilities

Use this example to retrieve the default values of all of the parameters that are needed to create an intuitive user interface.

1.  Request the configuration capabilities of the application.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
    ```
    
    ```bash
    POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
    ```
    
2.  Parse the JSON response.
    
    Success response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "data": {...}}
    ```
    
    Failure response example.
    
    ```bash
    {    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "error":    {        "code": XXXX,        "message": "A descriptive error message."    }}
    ```
    

The configuration JSON object is modified according to [getConfigurationCapabilities](#getconfigurationcapabilities).

## API documentation

The different API’s all uses the same CGI-call, using the method `property` to decide the operation to perform on the data.

All of the included API’s uses the same error code pattern. Error codes from 1000 to 1999 are reserved for camera application (server) errors, for example: could not read configuration from file. The actual cause can be seen in the server-log, and the problem could in some cases be solved by removing and reinstalling the application. Error codes from 2000 to 2999 are reserved for client errors, for example: wrong format on the configuration file or an invalid parameter. These errors should be possible to solve by changing the input data to the API.

### Changes between apiVersions

**Changes between version 1.0 to 1.1**

`Preset`, an optional parameter for mechanical PTZ cameras was supported from apiVersion 1.1 and forward. For mechanical PTZ cameras, each profile can be connected to one preset. If a preset is added, the profile will only be active when the camera is at the given preset. If this parameter is omitted or the profile is not connected to any preset it will always be active.

In apiVersion 1.1 it is only possible to connect a profile to at most one preset, however, the parameter is set as an array.

The preset parameter is only valid for mechanical PTZ camera.

```bash
"profiles":\[  {    "name": "Profile 1",    "uid": 1,    "camera": 1,    "filters": \[...\],    "triggers": \[...\],    "presets": \[p\]  },\]
```

**Changes between version 1.1 to 1.2**

Adds a method to get the capabilities as well as the default and boundary values for the application.

### getConfiguration

Request the current configuration of the application.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | (optional) Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies the operation that is performed. |

#### Response Success

Returns the current configuration of the ACAP, in a JSON formatted response. In the following examples the values **d, w, h, t, x, y** and **r**are numbers. For a complete description of each field in the configuration see [Parameter description table](#parameter-description-table).

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfiguration",  "data":  {    "cameras":    \[      { "active": true, "id": 1, "rotation": r }    \],    "profiles":    \[      "name": "Profile 1",      "uid": 1,      "camera": 1,      "filters":      \[        { "type": "sizePercentage",  "data": \[w,h\], "active": false },        { "type": "timeShortLivedLimit",  "data": t,  "active": true  },        { "type": "distanceSwayingObject",  "data": d,  "active": true  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  }      \],      "triggers":\[        { "type": "includeArea",  "data": \[ \[x,y\], ..., \[x,y\] \] }      \],      "presets" : \[p\],      },      {...},      {...},      {...}    \],    "configurationStatus": 0  }}
```

The response if the camera supports multiple channels, eg. AXIS F44.

Channel specific properties are set in `data.cameras`. However, each profile has its individual settings, and refers to a camera `id` property with the `data.profiles[j].camera` property.

```bash
{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfiguration",  "data":  {    "cameras":    \[      { "active": true,  "id": 1, "rotation": r },      { "active": true,  "id": 2, "rotation": r },      { "active": true,  "id": 3, "rotation": r },      { "active": true,  "id": 4, "rotation": r }    \],    "profiles":    \[      {        "name": "Profile 1 (Video 1)",        "uid": 1,        "camera": 1,        "filters":        \[          { "type": "sizePercentage",  "data": \[w,h\], "active": false },          { "type": "timeShortLivedLimit",  "data": t,  "active": true  },          { "type": "distanceSwayingObject",  "data": d,  "active": true  },          { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  },          { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  }        \],        "triggers":\[          { "type": "includeArea",  "data": \[ \[x,y\], ..., \[x,y\] \] }        \]      },      {        "name": "Profile 2 (Video 3)",        "uid": 2,        "camera": 3,        "filters": \[...\],        "triggers": \[...\],        "presets": \[p\]      },      {...},      {...},      {...}    \],    "configurationStatus": 0  }}
```

#### Error

See [General error response](#general-error-response).

### setConfiguration

Set the configuration of the application. The application is not restarted and any ongoing events will be set as inactive when the new configuration is applied. This will cause ongoing recordings to stop, and for multichannel products all cameras are affected simultaneously. However, if there is still motion in the include area after the new configuration is set, and no exclusion filter hinders the alarm to be sent, the event will be set to active directly after new configuration is applied.

There is a size limitation on POST transfer request which makes it suitable to send a minified JSON structure without white-spaces and new lines.

**Modify specific properties**

Below are some examples for how to change values in the json file to perform specific actions. In the examples `<i>` is an index in the profile-array, not the uid of the profile.

**Set image rotation**: The image rotation for which the configuration is done should be specified in `params.cameras[i].rotation.` Valid values are (0, 90, 180, 270), which corresponds to the rotation of the camera.

**Modify include area**: To change the include area of a profile consisting of n connected straight lines connecting points `[x0,y0], ..., [xn,yn]` change the property `params.profiles[i].triggers` to:

```bash
"triggers":\[  { "type": "includeArea",  "data": \[ \[x0,y0\], ..., \[xn,yn\] \] }\]
```

**Modify exclude areas**: To add an exclude area for a profile consisting of `n` connected straight lines, connecting points `[x0,y0], ..., [xn,yn]` change the property `params.profiles[i].filters` to

```bash
"filters":\[  { "type": "excludeArea",  "data": \[ \[x0,y0\], ..., \[xn,yn\] \] }  ...\]
```

Note that the exclude area object is removed if the exclude area should not be used.

**Set percentage filter**: To apply a percentage filter with height `h` and width `w` in percent of`image,params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "sizePercentage",  "data": \[w,h\], "active": true  },  ...\]
```

**Set short-lived object filter**: In order to set the short-lived object filter value to `t` seconds `params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "timeShortLivedLimit",  "data": t, "active": true  },  ...\]
```

**Set swaying object filter**: In order to set the swaying object filter value to `d` percent of the image `params.profiles[i].filters` should be modified to

```bash
"filters":\[  { "type": "distanceSwayingObject",  "data": d, "active": true  },  ...\]
```

The filter value `d` determines how far an object has to move from its point of origin before it can trigger an alarm. It is given in percent of the image. Note that this is a global setting and will also delay alarms from all objects in the image with that distance, which could introduce missed alarms if the value is set too high.

**Modify presets:**

info

Only PTZ cameras are supported (PTZ encoders are not supported).

To connect a profile to a PTZ preset, set `params.profiles[i]` to:

```bash
"presets":\[p\]
```

where p is the id-number of the preset (the index value in the VAPIX-parameter `PTZ.Preset.P0.Position.P<index>`). The value can also be -1 for any-preset, or -2 for anywhere.

A profile that is connected to anywhere (-2) is always active, both if the PTZ-camera points at a preset or if it is manually moved away from the preset. Settings for such a general profile should be used with care to handle all different conditions, for example a large include area and a small short-lived filter.

A profile that is connected to any-preset (-1) is active as long as the camera is at **any** preset, but not if it is manually moved away from the preset. This setting should also be used with care. It is useful for connecting a general action rule, where false alarms are acceptable, for example when a light is turned on.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{  "apiVersion": "1.3",  "context": "<client context>",  "method": "setConfiguration",  "params":  {    "cameras":    \[      { "active": true, "id": 1, "rotation": r }    \],    "profiles":    \[      {      "name": "Profile 1",      "uid": 1,      "camera": 1,      "filters":      \[        { "type": "sizePercentage",  "data": \[w,h\], "active": false },        { "type": "timeShortLivedLimit",  "data": t,  "active": true  },        { "type": "distanceSwayingObject",  "data": d,  "active": true  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  }      \],      "triggers":\[        { "type": "includeArea",  "data": \[ \[x,y\], ..., \[x,y\] \] }      \],      "presets": \[p\]      \]    },    { ... },    { ... },    { ... }    \]  }}'
```

```bash
POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "setConfiguration",  "params":  {    "cameras":    \[      { "active": true, "id": 1, "rotation": r }    \],    "profiles":    \[      {      "name": "Profile 1",      "uid": 1,      "camera": 1,      "filters":      \[        { "type": "sizePercentage",  "data": \[w,h\], "active": false },        { "type": "timeShortLivedLimit",  "data": t,  "active": true  },        { "type": "distanceSwayingObject",  "data": d,  "active": true  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  }      \],      "triggers":\[        { "type": "includeArea",  "data": \[ \[x,y\], ..., \[x,y\] \] }      \],      "presets": \[p\]      \]    },    { ... },    { ... },    { ... }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | (Optional) Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `setConfiguration` operation is performed. |
| `params` | A complete ACAP configuration. To remove a profile, delete that profile object from the array. |

#### Response Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

#### Error

See [General error response](#general-error-response).

### getConfigurationCapabilities

Request the boundaries and default values of the ACAP.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | (Optional). Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `getConfigurationCapabilities` operation is performed. |

#### Response Success

Returns the boundaries and default values of the ACAP, in a JSON formatted response. This CGI will always return the same result for one camera independent of when it is called, i.e. these values cannot be changed through a CGI. However, different cameras might return different result depending on their capabilities. In the following examples the values p, q, r and z are numbers. For a complete description of each field in the configuration see [Configuration capabilities parameter description](#configuration-capabilities-parameter-description).

```bash
200 OKContent-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data":  {    "alarmOverlay": {      "isSupported": false    }    "filters":    \[      {        "type": "sizePercentage",        "min": \[width, height\],        "max": \[width, height\],        "default": \[width, height\],        "defaultActive": true      },      {        "type": "timeShortLivedLimit",        "min": p,        "max": q,        "default": r,        "defaultActive": true      },      {        "type": "distanceSwayingObject",        "min": p,        "max": q,        "default": r,        "defaultActive": true      },      {        "type": "excludeArea",        "min": \[x, y\],        "max": \[x, y\],        "minNbrVertices": p,        "maxNbrVertices": q,        "minNbrInstances": r,        "maxNbrInstances": z,        "defaultInstance": \[\[x, y\], \[x, y\], \[x, y\], \[x, y\]\]      }    \],    "triggers":    \[      {        "type": "includeArea",        "min": \[x, y\],        "max": \[x, y\],        "minNbrVertices": p,        "maxNbrVertices": q,        "minNbrInstances": r,        "maxNbrInstances": z,        "defaultInstance": \[\[x, y\], \[x, y\], \[x, y\], \[x, y\]\]      }    \],    "profiles":    {      "minNbrProfilesPerCamera": p,      "maxNbrProfilesPerCamera": q,      "minLengthName": r,      "maxLengthName": z    },    "presets":    {      "maxNbrPresets": p,      "defaultPreset": q    }  }}
```

#### Error

See [General error response](#general-error-response)

### getSupportedVersions

Get a list of supported api versions for the ACAP (one for each major version).

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getSupportedVersions"}'
```

```bash
POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | (optional) Client sets this value and server echos data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `getSupportedVersions` operation is performed. |

#### Response Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "method": "getSupportedVersions",    "context": "<client context>",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Element | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `apiVersion=<list of versions>` | List of supported versions, i.e. all major versions with the highest supported minor version. |
| `<list of versions>` | List of `<major>.<minor>` versions, e.g. `["1.4", "2.5"]`. |

#### Error

See [General error response](#general-error-response).

### sendAlarmEvent

By using this method, it is possible to send a stateful alarm event, both in Axis and ONVIF format, for a specific profile `<uid>`. The stateful alarm event is active for a few seconds. The response message will be returned immediately. This can be used by VMS installers to check that the VMS configuration is correct (for example: start recording). All events related to the profile will be sent, both in Axis and ONVIF format. A profile connected to a preset will also send an event even if the camera is not on the preset.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/vmd/control.cgi" \\  --data '{  "apiVersion": "1.3",  "context": "<client context>",  "method": "sendAlarmEvent",  "params":  {    "profile": <uid>  }}'
```

```bash
POST /local/vmd/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.3",  "context": "<client context>",  "method": "sendAlarmEvent",  "params":  {    "profile": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that the response should use. |
| `context` | (optional) Client sets this value and server echoes data in the response. It is present regardless of whether the response succeeded or failed. |
| `method` | Specifies that the `sendAlarmEvent` operation is performed. |
| `profile` | The unique id for each profile. There must be a profile with the specified `uid`. |

#### Response Success

```bash
200 OKContent-Type: application/json{    "apiVersion": "1.3",    "context": "<client context>",    "method": "sendAlarmEvent",    "data": {}}
```

#### Error

See [General error response](#general-error-response).

### Parameter description

The structure of a configuration object is the same in both the data object in the response for `getConfiguration` and the `params` object in the request for `setConfiguration`. The structure is the same for single and multichannel products, where the `cameras` objects should mirror the different VAPIX camera properties.

-   **Security level**: Operator
-   **Method**: POST

**Example configuration**

The following example configuration will be described in details in the [Parameter description table](#parameter-description-table).

```bash
{  "cameras":  \[    { "active": bool,   "id": 1, "rotation": r }  \],  "profiles":  \[    {      "name": "<client nice-name>",      "uid": <uid>,      "camera": 1,      "filters":      \[        { "type": "sizePercentage",  "data": \[w,h\], "active": false },        { "type": "timeShortLivedLimit",  "data": t,  "active": true  },        { "type": "distanceSwayingObject",  "data": d,  "active": true  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  },        { "type": "excludeArea",  "data": \[ \[x,y\], ..., \[x,y\] \]  }      \],      "triggers": \[        { "type": "includeArea",  "data": \[ \[x,y\], ..., \[x,y\] \] }      \],      "presets": \[1\]      \]    },    { ... },    { ... },    { ... }  \],  "configurationStatus": 0}
```

#### Parameter description table

All parameters and properties are considered mandatory unless otherwise specified.

The `cameras` object contains general information that is the same for all profiles using that camera.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `cameras[i].active` | `boolean` | `true` | `true,false` | It is possible to have active profiles for the camera if set to `true`. All profiles for that camera are currently inactivated if set to `false`. |
| `cameras[i].id` | `integer` | `1` | `1, ..., #Cameras` | The corresponding camera value used when requesting a video using `media.amp`Note that it starts at`1`. |
| `cameras[i].rotation` | `integer` | `0` | `0, 90, 180 or 270` | The rotation of the camera in the plane of the camera, measured in degrees. Should match the property`Image.I<camera>.Appearance.Rotation` |

The `profiles` object contains information for each individual profile.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `profiles[j].name` | `string` | `"Profile<uid>"` |  | Unicode string that is in the nice name of the event, and is visible to the end user in the action rule list. |
| `profiles[j].camera` | `integer` | `1` | `1, 2, 3, ...,` | Shall match `id` of the corresponding camera in `cameras`. |
| `profiles[j].uid` | `integer` | `1` | `1, 2, 3, ...,` | Shall be an unique id for each profile. |
| `profiles[j].filters` | `array` |  |  | An array of exclusion filters. |
| `profiles[j].triggers` | `array` |  |  | An array of triggers. |
| `profiles[j].presets` | `array` |  |  | The array can only contain one preset. This parameter is optional. If omitted the profile will always be active. It is only valid for mechanical PTZ cameras. The client is responsible for making sure that the preset is valid. There is no automatic detection if a preset is removed. There are two special values: "-2" means that the profile is active anywhere and "-1" means that the profile is active on any profile. |

The exclusion filters of `profiles[j].filters` have similar structure. The exclusion filters are all optional, and a filter is considered disabled if it is not present in the array `profiles[].filters`.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | `string` | See separate table. | Specifies the type of exclusion filter. |
| `profiles[j].filters[k].data` |  |  | The data for the exclusion filter. The type differs for each exclusion filter. |
| `profiles[j].filters[k].active` | `boolean` | `true, false` | If the filter is active. Not applicable for exclude areas. |

The data field for each exclusion filter.

| Parameter | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `"sizePercentage"` | `[int, int]` | `[5,5]` | `[3..100,3..100]` | An array with width and height (`[w, h]`) in percent of image. If the height and width of an objects measured as a percentage of the total camera view is lesser than or equal to the set values, it will not be able to raise an alarm. |
| `"timeShortLivedLimit"` | `integer` | `1` | `1..5` | The value reflects how many seconds the object has to be in the camera view before it can raise an alarm. If the object does something that should trigger an alarm before the set time has passed, the alarm is temporarily suppressed. If the object still is in the camera view after the expiration of the set time, an alarm will be raised then. If the object has disappeared from the camera view the alarm will not be raised. |
| `"distanceSwayingObject"` | `integer` | `5` | `3..20` | Max distance object is allowed to sway without raising an alarm. The swaying distance is given in percent of image. |
| `"excludeArea"` | `[ [float, float], ... [float, float] ]` |  | `[ [-1,..1] ]` | An exclude area is described as an array of points `[ [x0,y0], ..., [xn,yn] ]`, the unit are normalized to the size of the image, so that the visible view spans from -1 to 1 in both horizontal and vertical direction. Each profile can contain up to three exclude areas. |

The only type of trigger in VMD is `includeArea`. The array `profiles[j].triggers` should contain exactly one include area.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].triggers[0].type` | `string` | `"includeArea"` | Specifies that it is an include area. |
| `profiles[j].triggers[0].data` | `[ [float, float], ... [float, float] ]` | `[[-1..1,-1..1],...[-1..1,-1..1]]` | An include area is described as an array of points `[ [x0,y0], ..., [xn,yn] ]`, the unit are normalized to the size of the image, so that the visible view spans from -1 to 1 in both horizontal and vertical direction. |

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `configurationStatus` | `integer` | `INT_MAX` | This property is read only and therefore ignored by `setConfiguration`. The initial value, 0, indicates a default configuration for example: that no configuration has yet been set. Each time a configuration is set, the value is increased by one. Note that the value is reset to 1 after `INT_MAX` has been reached. |

#### Parameter presets description

In `apiVersion` 1.1 the parameter `profiles[j]. presets` was introduced. It comes in the form of an array which can contain at most one preset. The profile will not be connected to any presets if the presets array is empty however, and will always be active, i.e. it is connected to "anywhere". The user is responsible for connecting a profile to an existing preset. If the connected preset is deleted, there is no automatic handling for updating the configuration. The parameter will cause an error in non PTZ-cameras.

The parameter is optional in PTZ-cameras, and if the parameter is omitted, it is equivalent to an empty array, i.e. the profile is always active.

A parameter value for `any-preset` is -1 and for `anywhere` it is -2.

`anywhere` (value: -2):

A profile that is connected to `anywhere` is always active, both if the PTZ-camera points at a preset of if it is manually moved away from a preset. Settings for such a general profile should be used with care to handle all different conditions, e.g. a large include area and a small short-lived filter.

`any-preset` (value: -1):

A profile that is connected to `any-preset` is active as long as the camera is at ANY preset, but not if it is manually moved away from the preset. This setting should also be used with care. It is useful for connecting a general action rule, where false alarms are OK, e.g. turn on the lights.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `profiles[j].presets` | array of int | `[]` | `[-2]`, `[-1]`, `[]`, `[1]`, `[2]`, `[3]`, ... | The index-number of the preset, e.g. 1 for parameter `PTZ.Preset.P0.Position.P1`. The value can be -1 for `any-preset` or -2 for `anywhere`. |

### Configuration capabilities parameter description

The tables below describe the parameters found in [getConfigurationCapabilities](#getconfigurationcapabilities)

**AlarmOverlay**

Introduced with `apiVersion` 1.3.

alarmOverlay

| Property | Type | Description |
| --- | --- | --- |
| `isSupported` | boolean | True, if the camera supports the burnt in alarm overlay feature. |
| `maxNbrActiveCameras` | int | The number of different cameras in a multichannel device that can use the feature simultaneously. The value is 0 if the feature is not supported. |
| `cameras` | `[object, object]` | A list of camera objects that describe the alarm overlay capabilities for each camera. |

| Property | Type | Description |
| --- | --- | --- |
| `id` | int | Same as the parameter `cameras[i].id` in the configuration and the corresponding camera value (value starts at 1) used when requesting a video using `media.amp`. |
| `availableResolutions` | `[string, string, ...]` | A list of resolutions of the form `<width>x<height>` for which it is possible to use alarm overlay for the specific camera. |

**Filters**

sizePercentage

| Property | Type | Description |
| --- | --- | --- |
| `min` | `[int, int]` | An array containing the minimum allowed width and height (`[w, h]`) in percent of the image. |
| `max` | `[int, int]` | An array containing the maximum allowed width and height (`[w, h]`) in percent of the image. |
| `default` | `[int, int]` | An array containing the default values of width and height (`[w, h]`) in percent of the image. |
| `defaultActive` | boolean | If the filter is active by default. |

timeShortLivedLimit

| Property | Type | Description |
| --- | --- | --- |
| `min` | int | The minimum allowed time in seconds. |
| `max` | int | The maximum allowed time in seconds. |
| `default` | int | The default time in seconds. |
| `defaultActive` | boolean | If the filter is active by default. |

distanceSwayingObject

| Property | Type | Description |
| --- | --- | --- |
| `min` | int | The minimum allowed distance to sway. |
| `max` | int | The maximum allowed distance to sway. |
| `default` | int | The distance to sway. |
| `defaultActive` | boolean | If the filter is active by default. |

excludeArea

| Property | Type | Description |
| --- | --- | --- |
| `min` | `[int, int]` | An array `[xPos, yPos]` with the minimum allowed values in the x- and y-direction to place the window. |
| `max` | `[int, int]` | An array `[xPos, yPos]` with the maximum allowed values in the x- and y-direction to place the window. |
| `minNbrVertices` | int | The minimum number of vertices the area may contain. |
| `maxNbrVertices` | int | The maximum number of vertices the area may contain. |
| `minNbrInstances` | int | The minimum allowed number of exclude areas. |
| `maxNbrInstances` | int | The maximum allowed number of exclude areas. |
| `defaultInstance` | `[[x, y], [x, y], [x, y], [x, y]]` | The default area, an array of arrays containing the default vertices. |

**Triggers**

includeArea

| Property | Type | Description |
| --- | --- | --- |
| `min` | `[int, int]` | An array `[xPos, yPos]` with the minimum allowed values in the x- and y-direction to place the window. |
| `max` | `[int, int]` | An array `[xPos, yPos]` with the maximum allowed values in the x- and y-direction to place the window. |
| `minNbrVertices` | int | The minimum number of vertices the area may contain. |
| `maxNbrVertices` | int | The maximum number of vertices the area may contain. |
| `minNbrInstances` | int | The minimum allowed number of include areas. |
| `maxNbrInstances` | int | The maximum allowed number of include areas. |
| `defaultInstance` | `[[x, y], [x, y], [x, y], [x, y]]` | The default area, an array of arrays containing the default vertices. |

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

### General error response

General error response from VMD 4 API.

-   **HTTP Code**: 200 OK
-   **Content-Type**: `application/json`

Return value XXXX is a number.

```bash
{  "apiVersion": "1.3",  "context": "<client context>",  "method": "<request>",  "error":  {    "code": XXXX,    "message": "A descriptive error message."  }}
```

Supported elements, attributes and values:

| Error | Error code | Description | Request |
| --- | --- | --- | --- |
| `Application Error` | 1000 | The application failed to return a configuration. | getConfiguration, setConfiguration, getConfigurationCapabilities, getSupportedVersions, sendAlarmEvent |
| `Unsupported Version` | 2000 | The major version number isn’t supported. | getConfiguration, setConfiguration, getConfigurationCapabilities, getSupportedVersions, sendAlarmEvent |
| `Invalid Format` | 2001 | The request was not formatted correctly, for example: does not follow json-schema. | getConfiguration, setConfiguration, getConfigurationCapabilities, getSupportedVersions, sendAlarmEvent |
| `Incoherent Format` | 2002 | Parts of the configuration contradict each other, for example: several profiles have the same `uid`. | setConfiguration, sendAlarmEvent |
| `Missing Parameter` | 2003 | The request has a missing mandatory parameter. | setConfiguration, sendAlarmEvent |
| `Invalid Parameter` | 2004 | The request has a parameter that has an invalid value. | setConfiguration, sendAlarmEvent |
| `Unsupported Product` | 8000 | The product is not supported by this application. | getConfigurationCapabilities |

## Events
### VMD event

**Declaration of the VMD event**

The declaration of the VMD event can be accessed through VAPIX and ONVIF event web service APIs.

The declaration of the VMD event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform>  <VMD aev:NiceName="Video Motion Detection">    <CameraXProfileY wstop:topic="true" aev:NiceName="VMD 4: <profile.name>">      <aev:MessageInstance aev:isProperty="true">        <aev:DataInstance>          <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />        </aev:DataInstance>      </aev:MessageInstance>    </CameraXProfileY>  </VMD></tnsaxis:CameraApplicationPlatform>
```

The event in this example is named `CameraXProfileY`, it is sent every time an object has entered a specific include area. It is based on a profile with `camera=X` and `uid=Y`. If it is a multichannel product the nicename attribute is changed to:

```bash
aev:NiceName="VMD 4: <profile.name> (<Image.I<profile.camera>.Name>)"
```

The name of the camera is taken from the parhand using the `Image.I<index>.Name` parameter. Value `<index>`.is same as camera source value `camera=X` minus one.

The properties can be used for matching the criteria for triggering an action rule:

`Property=<active>`: Required. When movement is detected in the area the event is activated. When the movement disappears the event is inactivated.

`<active>`: A stateful event. An active event has the value "1", and an inactive event has the value "0".

**Declaration of the VMD event for multichannel products**

The following example shows how a event declaration will look for a scenario with a multichannel product with two cameras, and each camera has two profiles. The Namespaces and unnecessary tags has been removed for readability

```bash
<TopicSet>  <CameraApplicationPlatform>    <VMD NiceName="Video Motion Detection">      <Camera1Profile1 topic="true" NiceName="VMD 4: Garden Left (Camera 1)">        <MessageInstance isProperty="true">        <DataInstance>        <SimpleItemInstance Type="xsd:boolean"        </DataInstance>        </MessageInstance>      </Camera1Profile1>      <Camera1Profile2 topic="true" NiceName="VMD 4: Garden Right (Camera 1)">        ...      </Camera1Profile2>      <Camera2Profile3 topic="true" NiceName="VMD 4: Parking Day (Camera 2)">        ...      </Camera2Profile3>      <Camera2Profile4 topic="true" NiceName="VMD 4: Parking Night (Camera 2)">        ...      </Camera2Profile4>    </VMD>  </CameraApplicationPlatform>  ...</TopicSet>
```

**CameraXProfileANY event**

When the ACAP detects an object entering an include area, it will be sent as an ANY event element for a specific camera.

The declaration of an ANY event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform>    <VMD aev:NiceName="Video Motion Detection">        <CameraXProfileANY wstop:topic="true" aev:NiceName="VMD 4: Any Profile">        ...        ...        ...        </CameraXProfileANY>    </VMD></tnsaxis:CameraApplicationPlatform>
```

The event in this example is named CameraXProfileANY, it is sent every time an object has entered a specific include area. It is based on a profile with `camera=X`. If it is a multichannel product the nicename attribute is changed to:

```bash
aev:NiceName="VMD 4: Any Profile (<Image.I<profile.camera>.Name>)"
```

The name of the camera is taken from the parhand using the `Image.I<index>.Name` parameter. Value `<index>` is same as camera source value `camera=X` minus one.

**CameraANY event**

When the ACAP detects an object entering an include area, it will be sent as a global ANY event element. A global ANY event is an ANY event for ANY camera, which means an alarm on any of the channels will also trigger this event.

The declaration of such a global ANY event event as received from the VAPIX API:

```bash
<tnsaxis:CameraApplicationPlatform>    <VMD aev:NiceName="Video Motion Detection">        <CameraANY wstop:topic="true" aev:NiceName="VMD 4: Any Profile">        ...        ...        ...        </CameraANY>    </VMD></tnsaxis:CameraApplicationPlatform>
```

**Legacy VMD 3 event**

Legacy Video Motion Detection 3 (VMD 3) event corresponds to `CameraXProfileANY` event. A VMD 3 event will be sent if there is an ANY event being sent for a specific camera. This is used for VMS without dynamic event integration, where VMD 3 events are hardcoded. An example of such a VMD 3 event is described below.

```bash
<tns1:RuleEngine aev:NiceName="Application">    <tnsaxis:VMD3 aev:NiceName="Video Motion Detection 3">        <VMD3\_video\_1 wstop:topic="true" aev:NiceName="VMD 3">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance aev:NiceName="Area ID" Type="xsd:string" Name="areaid">                        <aev:Value>0</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance                        aev:NiceName="Active"                        Type="xsd:boolean"                        Name="active"                        isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </VMD3\_video\_1>    </tnsaxis:VMD3></tns1:RuleEngine>
```

**The event stream**

A client may subscribe to events from the event stream.

Using VAPIX, this stream can be retrieved over RTSP using the url:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=axis:CameraApplicationPlatform/VMD/.
```

It is also possible to listen for a specific profile:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=axis:CameraApplicationPlatform/VMD/CameraXProfileY/.
```

**CameraXProfileY**

When the ACAP detects an object entering an include area, it will be sent as an event element. An example of such an event is described below.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage xmlns:tns1="http://www.onvif.org/ver10/topics">            <wsnt:ProducerReference>                <wsa5:Address>uri://2a513b80-8211-4034-82e7-e8d48792c845/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2016-05-23T06:21:10.290542Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

The UycTime of the message refers to the time of the event, i.e. this should be In sync with time stamps in an image stream with images of the actual physical event that took place.

**Synchronize metadata with video stream**

Axis cameras uses the Real Time Streaming Protocol (RTSP) for controlling the media streaming between the camera and its clients. RTSP uses the Real­time Transport Protocol (RTP) for the packet format for the streaming of the meta/video data, and the RTP Control Protocol (RTCP) for the synchronization of the metadata and video data stream. The synchronized conversion from the absolute time (UTC timestamp) at the motion detection to the relative time (RTP timestamp) for the video stream, can be found in the RTCP packets.

### ONVIF MotionAlarm event

**Declaration of the MotionAlarm event**

The declaration of the ONVIF Motion Alarm event can be accessed through the VAPIX and ONVIF event web service API:s. ONVIF event corresponds to CameraXProfileANY event. An ONVIF event will be sent if there is an ANY event being sent for a specific camera.

The declaration of the ONVIF Motion Alarm event as received from the VAPIX API:

```bash
<tns1:VideoSource>    <MotionAlarm wstop:topic="true">        <tt:MessageDescription IsProperty="true">            <tt:Source>                <tt:SimpleItemDescription Name="Source" Type="tt:ReferenceToken" />            </tt:Source>            <tt:Data>                <tt:SimpleItemDescription Name="State" Type="xs:boolean" />            </tt:Data>        </tt:MessageDescription>    </MotionAlarm></tns1:VideoSource>
```

| Parameter | Description |
| --- | --- |
| `Property=<Source>` | Required. The Video source for ONVIF, which starts counting from 0. |
| `<Source>` | Reference counter starts from 0. |
| `Property=<Source>` | Required. The value for Motion Alarm State. |
| `<State>` | An active event has the value "1", and an inactive event has the value "0". |

**The event stream**

A client may subscribe to events from the VAPIX/ONVIF event stream. The format of the stream and its elements are described in [http://www.onvif.org/onvif/ver10/schema/onvif.xsd](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [http://www.onvif.org/onvif/ver10/topics/topicns.xml](http://www.onvif.org/onvif/ver10/topics/topicns.xml)

Using VAPIX, this stream can be retrieved over RTSP using the url:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=onvif:VideoSource/MotionAlarm/.
```