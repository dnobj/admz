---
title: DayNight API
url: "https://developer.axis.com/vapix/network-video/daynight-api/"
category: vapix
subcategory: network-video
sha256: 53f11c0c3893215b10e7ba754da6df62b9e5a98dd25a28bd83f25098c16e5a12
scraped_at: "2026-01-09T15:19:29.571Z"
page_height: 24306
---

# DayNight API

The VAPIX® DayNight API provides information that makes it possible to manage day and night configurations on an Axis device where the IR-cut filter has been set to Auto, as well as what filter to use when the IR-cut filter is set to Off.

When the IR-cut filter is set to Auto, this activates a day-night algorithm that automatically switches between day and night mode depending on the brightness in the image. The API provides the ability to change how the algorithm behaves.

When the IR-cut filter is set to Off, the camera switches to night mode and the image becomes black and white. In night mode, the light sensitivity increases since the camera removes the IR-cut filter and uses either a clear glass or a an IR-pass filter if supported instead.

-   A clear glass transmits both visible light and IR light.
-   An IR-pass filter transmits only IR light.

If the camera supports an IR-pass filter, you can configure which filter to use when the IR-cut filter is set to Off.

info

When the IR-cut filter is set to Auto, `NightFilter` is automatically set to use clear glass if an IR-pass filter is used on the camera.

## Overview

| Parameter | Description |
| --- | --- |
| `DayNightShiftLevel` | Controls the level for when the switch between day and night shall occur.  
  
\- A higher value means that the switch will occur when the image is darker.  
\- A lower value means that the switch will occur when the image is brighter.  
  
This parameter is equivalent to the `/axis-cgi/param.cgi` parameter `root.ImageSource.IX.DayNight.ShiftLevel`. |
| `DayNightDwellTime` | In day mode, when it gets dark enough for the day to night threshold of `DayNightShiftLevel` to be reached, this parameter defines the number of seconds that should pass until the channel switch into night mode. |
| `NightDayDwellTime` | In night mode, when it gets bright enough for the night to day threshold of `DayNightShiftLevel` to be reached, this parameter defines the number of seconds that should pass until the channel switch into day mode. |
| `NightDayShiftLevel` | Gives the user the ability to change the parameter `NightDayShiftLevel` as long as `NightDayShiftLevelSupport` is `true`. `NightDayShiftLevel` controls the night to day switch.  
  
\- A higher value corresponds to a night to day switch when it’s darker.  
\- A lower value corresponds to a night to day switch when it’s brighter.  
  
This parameter should be handled with care as a day night oscillations could occur when the value is too high. |
| `Autotune` | Give the user the ability to change the parameter `Autotune` as long as `AutotuneSupport` is `true`. An algorithm will take control of the `NightDayShiftLevel` parameter to obtain an optimal night to day performance if `Autotune` is `true`. The user will be prevented from changing the NighDayShiftLevel parameter at this stage. The user is able to change NighDayShiftLevel to a fixed value if `Autotune` is `false`. |
| `NightFilter` | Only usable if `IrPassSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `irpass`: The camera uses an IR-pass filter when the IR-cut filter is set to Off.  
\- `clear`: The camera uses a clear glass when the IR-cut filter is set to Off. |

### Identification

-   **API Discovery**: `id=daynight`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Request day night configurations

List all capabilities and check the day and night configurations on a device.

**Example**

1.  Use [getCapabilities](#getcapabilities) to check the current day night capabilities for a channel.
    
2.  Use [getConfiguration](#getconfiguration) to check the current day night configuration for a channel.
    

### Shift level configurations

Change the day to night and/or night to day shift level configuration.

-   Increasing the value of `DayNightShiftLevel` will make the channel switch from day to night when it is darker.
-   If the night to day switch is unsatisfactory it is possible to set `Autotune` to `true`. This will let an algorithm take control of the `NightDayShiftLevel` parameter to obtain optimal night to day performance.
-   If the `Autotune` algorithm is unsatisfactory it is possible to set it to `false` and modify the value of `NightDayShiftLevel`.
-   Increasing the value of `NightDayShiftLevel` will make the channel switch from night to day when it is darker. Please note that increasing the value of `NightDayShiftLevel` too much might lead to day night oscillations and should be carefully handled.

**Example**

1.  Use [setConfiguration](#setconfiguration) to set the `DayNightShiftLevel` for a channel.
    
2.  Use [setConfiguration](#setconfiguration) to set the boolean value of the parameter `Autotune` for a channel. This is only possible if AutotuneSupport is `true` (see [getCapabilities](#getcapabilities)).
    
3.  Use [setConfiguration](#setconfiguration) to set the `NightDayShiftLevel` for a channel. Please note that this is only possible if Autotune is false and `NightDayShiftLevelSupport` is true (see [getCapabilities](#getcapabilities)).
    

### Shift dwell time configurations

Change the day to night and/or night to day dwell time configuration. A dwell time will always occur when a camera and a corresponding channel switch from day to night or night to day. Dwell time are the number of seconds that should pass until the day night algorithm make the switch, which by default is between 3–5 seconds and can be changed depending on use case:

-   If a channel is observing a highway where there is temporary light sources passing by in the night for a short period of time. This can make the day night algorithm believe that it is bright and switch from night to day just because the headlights shine into the channel longer time than the night to day dwell time. The channel will switch back to night-mode once the car has left the scene. This means that it would be wise to change the `NightDayDwellTime` to be more than 20 seconds in order to avoid switches every time a car pass.
-   If, on the other hand, the camera and a corresponding channel is located next to a motion triggered light source with visible light it would be wise to switch to day-mode as fast as possible when that light source turns on. In this case `NightDayDwellTime` should be set to 1–3 seconds.

**Example**

1.  Use [setConfiguration](#setconfiguration) to set the `DayNightDwellTime` for a channel.
    
2.  Use [setConfiguration](#setconfiguration) to set the `NightDayDwellTime` for a channel.
    

### Night filter configuration

This example shows how to change the filter from the standard clear glass to IR-pass filter.

**Example**

1.  Use [setConfiguration](#setconfiguration) to set `NightFilter` for a channel.

## API specifications
### getCapabilities

This method should be used when you want to request a list of all day and night capabilities for a specific channel on your device.

**Request**

-   **Security level**: Admin, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/daynight.cgi#getCapabilities" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getCapabilities",    "params": {        "channel": 0    }}'
```

```bash
POST /axis-cgi/daynight.cgi#getCapabilitiesHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getCapabilities",    "params": {        "channel": 0    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method=<method>` | The method that should be used. |
| `channel=<integer>` | The channel that should be used for the operation. |

**Return value – Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getCapabilities",    "data": \[        {            "channel": 0,            "AutotuneSupport": true,            "IrPassSupport": true,            "NightDayShiftLevelSupport": true        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `channel=<integer>` | The channel used in the operation. |
| `AutotuneSupport=<boolean>` | True if the channel supports autotune, otherwise false. |
| `IrPassSupport=<boolean>` | True if the channel supports IR-pass filter, otherwise false. |
| `NightDayShiftLevelSupport=<boolean>` | True if the channel supports night to day shift levels, otherwise false. |

**Return value – Failure**

See [Error responses](#error-responses) for a complete list of potential errors.

### getConfiguration

This method should be used when you want to request configuration information for a channel.

**Request**

-   **Security level**: Admin, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/daynight.cgi#getConfiguration" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration",    "params": {        "channel": 0    }}'
```

```bash
POST /axis-cgi/daynight.cgi#getConfigurationHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration",    "params": {        "channel": 0    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method=<method>` | The method that should be used. |
| `channel=<integer>` | The channel that should be used for the operation. |

**Return value – Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration",    "data": \[        {            "channel": 0,            "DayNightDwellTime": 3,            "DayNightShiftLevel": 50,            "NightDayDwellTime": 3,            "NightDayShiftLevel": 50,            "Autotune": true,            "NightFilter": "clear"        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `channel=<integer>` | The channel used in the operation. |
| `DayNightDwellTime=<float>` | The dwell time before switching from day to night-mode. This event occur when it gets dark enough for the day to night threshold `DayNightShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `DayNightShiftLevel=<integer>` | Controls the day to night switch threshold with a range between 0–100. A higher value corresponds to a night to day switch when it is darker. Equivalent to the `/axis-cgi/param.cgi` parameter `root.ImageSource.IX.DayNight.ShiftLevel`. |
| `NightDayDwellTime=<float>` | The dwell time before switching from night to day-mode. This event occur when it gets bright enough for the night to day threshold `NightDayShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `NightDayShiftLevel=<integer>` | Only possible to use if `NightDayShiftLevelSupport` is `true` (see [getCapabilities](#getcapabilities)). Controls the night to day threshold.  
  
\- A lower value corresponds to a night to day switch when it is brighter.  
\- A higher value corresponds to a day to night switch when it is darker.  
  
By manually setting `NightDayShiftLevel` too high can lead to oscillations between day- and night-mode. It is recommended to optimize this parameter automatically by setting `Autotune` to `true`, in which case it is not possible to `NighDayShiftLevel` in `setConfiguration`. |
| `Autotune=<boolean>` | Only usable if `AutotuneSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `true`: An algorithm takes control over the parameter `NightDayShiftLevel` to obtain optimal night to day performance.  
\- `false`: The operator can change `NightDayShiftLevel` to a fixed value. |
| `NightFilter=<string>` | Only usable if `IrPassSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `irpass`: The camera uses an IR-pass filter when the IR-cut filter is set to Off.  
\- `clear`: The camera uses a clear glass when the IR-cut filter is set to Off. |

**Return value – Failure**

See [Error responses](#error-responses) for a complete list of potential errors.

### setConfiguration

This method should be used when you want to apply configurations to a channel.

**Request**

-   **Security level**: Admin, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/daynight.cgi#setConfiguration" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        "channel": 0,        "DayNightDwellTime": 3,        "DayNightShiftLevel": 50,        "NightDayDwellTime": 3,        "NightDayShiftLevel": 50,        "Autotune": true,        "NightFilter": "clear"    }}'
```

```bash
POST /axis-cgi/daynight.cgi#setConfigurationHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        "channel": 0,        "DayNightDwellTime": 3,        "DayNightShiftLevel": 50,        "NightDayDwellTime": 3,        "NightDayShiftLevel": 50,        "Autotune": true,        "NightFilter": "clear"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method=<method>` | The method that should be used. |
| `channel=<integer>` | The channel that should be used for the operation. |
| `DayNightDwellTime=<float>` | The dwell time before switching from day to night-mode. This event occur when it gets dark enough for the day to night threshold `DayNightShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `DayNightShiftLevel=<integer>` | Controls the day to night switch threshold with a range between 0–100. A higher value corresponds to a night to day switch when it is darker. Equivalent to the `/axis-cgi/param.cgi` parameter `root.ImageSource.IX.DayNight.ShiftLevel`. |
| `NightDayDwellTime=<float>` | The dwell time before switching from night to day-mode. This event occur when it gets bright enough for the night to day threshold `NightDayShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `NightDayShiftLevel=<integer>` | Only possible to use if `NightDayShiftLevelSupport` is `true` (see [getCapabilities](#getcapabilities)). Controls the night to day threshold.  
  
\- A lower value corresponds to a night to day switch when it is brighter.  
\- A higher value corresponds to a day to night switch when it is darker.  
  
By manually setting `NightDayShiftLevel` too high can lead to oscillations between day- and night-mode. It is recommended to optimize this parameter automatically by setting `Autotune` to `true`, in which case it is not possible to `NighDayShiftLevel` in `setConfiguration`. |
| `Autotune=<boolean>` | Only usable if `AutotuneSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `true`: An algorithm takes control over the parameter `NightDayShiftLevel` to obtain optimal night to day performance.  
\- `false`: The operator can change `NightDayShiftLevel` to a fixed value. |
| `NightFilter=<string>` | Only usable if `IrPassSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `irpass`: The camera uses an IR-pass filter when the IR-cut filter is set to Off.  
\- `clear`: The camera uses a clear glass when the IR-cut filter is set to Off. |

**Return value – Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "data": \[        {            "channel": 0,            "DayNightDwellTime": 3,            "DayNightShiftLevel": 50,            "NightDayDwellTime": 3,            "NightDayShiftLevel": 50,            "Autotune": true,            "NightFilter": "clear"        }    \]}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `channel=<integer>` | The channel used in the operation. |
| `DayNightDwellTime=<float>` | The dwell time before switching from day to night-mode. This event occur when it gets dark enough for the day to night threshold `DayNightShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `DayNightShiftLevel=<integer>` | Controls the day to night switch threshold with a range between 0–100. A higher value corresponds to a night to day switch when it is darker. Equivalent to the `/axis-cgi/param.cgi` parameter `root.ImageSource.IX.DayNight.ShiftLevel`. |
| `NightDayDwellTime=<float>` | The dwell time before switching from night to day-mode. This event occur when it gets bright enough for the night to day threshold `NightDayShiftLevel` to be reached. The dwell time is measured between 1 and 600 seconds. |
| `NightDayShiftLevel=<integer>` | Only possible to use if `NightDayShiftLevelSupport` is `true` (see [getCapabilities](#getcapabilities)). Controls the night to day threshold.  
  
\- A lower value corresponds to a night to day switch when it is brighter.  
\- A higher value corresponds to a day to night switch when it is darker.  
  
By manually setting `NightDayShiftLevel` too high can lead to oscillations between day- and night-mode. It is recommended to optimize this parameter automatically by setting `Autotune` to `true`, in which case it is not possible to `NighDayShiftLevel` in `setConfiguration`. |
| `Autotune=<boolean>` | Only usable if `AutotuneSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `true`: An algorithm takes control over the parameter `NightDayShiftLevel` to obtain optimal night to day performance.  
\- `false`: The operator can change `NightDayShiftLevel` to a fixed value. |
| `NightFilter=<string>` | Only usable if `IrPassSupport` is `true` (see [getCapabilities](#getcapabilities)).  
  
\- `irpass`: The camera uses an IR-pass filter when the IR-cut filter is set to Off.  
\- `clear`: The camera uses a clear glass when the IR-cut filter is set to Off. |

**Return value – Failure**

See [Error responses](#error-responses) for a complete list of potential errors.

### getSupportedVersions

This method should be used when you want to check which major and minor API versions that are supported on your device.

**Request**

-   **Security level**: Admin, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/daynight.cgi#getSupportedVersions" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/daynight.cgi#getSupportedVersionsHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method=<method>` | The method that should be used. |

**Return value – Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "1.2"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `apiVersions` | A list containing all supported major versions along with their highest minor version, e.g. `["1.0", "1.2"]`. |

**Return value – Failure**

See [Error responses](#error-responses) for a complete list of potential errors.

### Error responses

**200 API version not supported**

-   **HTTP Code**: `200`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2100,        "message": "API version not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**400 Bad request**

-   **HTTP Code**: `400`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2101,        "message": "Invalid JSON."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**200 Method not supported**

-   **HTTP Code**: `200`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2102,        "message": "Method not supported."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**500 Missing parameter**

-   **HTTP Code**: `500`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2103,        "message": "Required parameter missing."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**500 Invalid parameter**

-   **HTTP Code**: `500`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2104,        "message": "Invalid parameter value specified."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**403 Authorization failed**

-   **HTTP Code**: `403`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2105,        "message": "Authorization failed."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**401 Authentication failed**

-   **HTTP Code**: `401`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2106,        "message": "Authentication failed."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**405 Method not allowed**

-   **HTTP Code**: `405`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 2107,        "message": "Transport level error."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |

**500 Internal error**

-   **HTTP Code**: `500`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 1100,        "message": "Internal error",        "details": \[            {                "Autotune": "Can't set Autotune, Autotune is not supported.",                "channel": 0            }        \]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |
| `NightDayShiftLevel=<string>` | Can't set NightDayShiftLevel while Autotune is true. |
| `Autotune=<string>` | Can't set Autotune, Autotune is not supported. |
| `NightFilter=<string>` | IrPassSupport is false, unable to set NightFilter |
| `channel=<integer>` | The channel used in the operation. |

**500 Internal error, autotune set to true**

-   **HTTP Code**: `500`
-   **Content-Type**: `application/json`

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "method",    "error": {        "code": 1100,        "message": "Internal error, autotune set to true."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<method>` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The error message for the corresponding error code. |