---
title: Optics Control
url: "https://developer.axis.com/vapix/network-video/optics-control/"
category: vapix
subcategory: network-video
sha256: c399fd6a2263747b87e4d4e7d1bd61ff1f0744ca57f2c78c6013ce43d2b7aba7
scraped_at: "2026-01-09T15:20:31.564Z"
page_height: 69659
---

# Optics Control

## Description

The AXIS Optics Control API contains the information that makes it possible to set up the optics in your Axis device, including the zoom, focus and IRCut filter hardware. This includes setting the magnification of the zoom lens, triggering a focus search and setting up a search window, as well as setting focus position manually.

### Model

The API implements `/axis-cgi/opticscontrol.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getOptics` | Retrieves information about all available optics. |
| `getCapabilities` | Retrieves information about the optics capabilities. |
| `setFocus` | Sets a focus position on one or more of the optics. |
| `setRelativeFocus` | Changes the focus relative to the current position on one or more optics. |
| `setMagnification` | Sets a magnification on one or more of the optics. |
| `setRelativeMagnification` | Changes the magnification relative to the current position on one or more optics. |
| `calibrate` | Calibrates the optics. |
| `reset` | Resets the optics back to their default position. |
| `setFocusWindow` | Sets the window in which autofocus will optimize the focus. |
| `performAutoFocus` | Starts an automatic focus search. |
| `setTemperatureCompensation` | Sets the state for the active temperature compensation. |
| `setIrCutFilterState` | Sets the state for the IRCut filter. |
| `setIrCompensation` | Sets the state for the active IR compensation. |
| `getSupportedVersion` | Retrieves a list of API versions supported by your device. |

### Identification

-   **API Discovery**: `id=optics-control`
-   **API version**: 1.2

### Limitations

`/axis-cgi/opticscontrol.cgi` is currently hardware exclusive and don’t have support for PTZ cameras, where `/axis-cgi/com/ptz.cgi` should be used instead.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Retrieve optics information

Use this example to retrieve the status of available optics capabilities.

1.  Retrieve the optics status with the following request:

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getOptics"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getOptics",    "data": {        "numberOfOptics": 2,        "optics": \[            {                "opticsId": "0",                "focusPosition": 0.5,                "focusMoving": false,                "focusWindowUpperLeftX": 0.3,                "focusWindowUpperLeftY": 0.2,                "focusWindowWidth": 0.4,                "focusWindowHeight": 0.5,                "magnification": 1.4,                "zoomMoving": false,                "temperatureCompensation": true,                "irCutFilterState": "auto",                "irCompensation": true            },            {                "opticsId": "1",                "focusPosition": 0.3,                "focusMoving": false,                "focusWindowUpperLeftX": 0.3,                "focusWindowUpperLeftY": 0.2,                "focusWindowWidth": 0.4,                "focusWindowHeight": 0.5,                "magnification": 1.6,                "zoomMoving": false,                "temperatureCompensation": true,                "irCutFilterState": "auto",                "irCompensation": true            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getOptics",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

### Retrieve optics capabilities

Use this example to retrieve information about the optics capabilities on your device.

1.  Retrieve the optics status with the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "getCapabilities"}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "getCapabilities"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getCapabilities",    "data": {        "numberOfOptics": 1,        "optics": \[            {                "opticsId": "0",                "capabilities": \[                    "focus",                    "zoom",                    "irCutFilter",                    "calibrateFocus",                    "calibrateZoom",                    "compensateTemperature",                    "compensateIr"                \],                "maxMagnification": 2.4            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getCapabilities",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

### Configure a newly installed camera

Use these examples to configure the field of view and focus after installing your device.

#### Set magnification

1.  Set the desired magnification with the following request:

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setMagnification",    "params": {        "optics": \[            {                "opticsId": "0",                "magnification": 1.4            },            {                "opticsId": "1",                "magnification": 1.5            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setMagnification",    "data": {}}
```

If a failure is generic, such as a missing parameter, you will receive the following error:

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setMagnification",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

If there is a failure in one of the optics only that error will occur. Meanwhile, the other parameters will be successfully set and you will receive the following error:

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setMagnification",    "error": {        "code": 1100,        "message": "Internal error",        "details": {            "opticsId": "0"        }    }}
```

If there is a failure in multiple optics only that error will occur. Meanwhile, the other parameters are successfully set and you will receive the following error:

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setMagnification",    "error": {        "code": 1200,        "message": "Temperature out of range",        "details": {            "opticsId": "optics01"        },        "errors": \[            {                "code": 1100,                "message": "Internal error",                "details": {                    "opticsId": "0"                }            },            {                "code": 2104,                "message": "Invalid parameter value specified",                "details": {                    "opticsId": "1"                }            }        \]    }}
```

#### Set focus window

1.  Create a window for the autofocus algorithm to search. Please note that the optimal focus position might change after setting up a focus window. It is therefore recommended to make a new search after using the following request:

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocusWindow",    "params": {        "optics": \[            {                "opticsId": "0",                "upperLeftX": 0.25,                "upperLeftY": 0.3,                "width": 0.5,                "height": 0.4            },            {                "opticsId": "1",                "upperLeftx": 0.3,                "upperLeftY": 0.25,                "width": 0.4,                "height": 0.5            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocusWindow",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocusWindow",    "error": {        "code": 1200,        "message": "Internal error"    }}
```

#### Set focus

1.  Specify a focus position with a value between 0 and 1 with the following request:

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocus",    "params": {        "optics": \[            {                "opticsId": "0",                "position": 0.2            },            {                "opticsId": "1",                "position": 0.3            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocus",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setFocus",    "error": {        "code": 1200,        "message": "Internal error"    }}
```

#### Perform autofocus

1.  Initiate an autofocus search, after first setting the magnification, with the following request:

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "performAutofocus",    "params": {        "optics": \[            {                "opticsId": "0"            },            {                "opticsId": "1"            }        \]    }}
```

Please note that the requested search may take some time to perform and will fail if another request is initiated before completion.

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "performAutofocus",    "data": {}}
```

If the focus cannot be found:

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "performAutofocus",    "error": {        "code": 1300,        "message": "Focus not found",        "details": {            "opticsId": "0"        }    }}
```

Generic failure:

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "performAutofocus",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

### Reset optics to the default position

Use this example to reset the optics back to the default position following a lens switch. Please note that a new focus search is required once this request has been completed.

1.  Reset the optics with the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "reset",    "params": {        "optics": \[            {                "opticsId": "0",                "focus": true,                "zoom": false            },            {                "opticsId": "1",                "focus": true,                "zoom": false            }        \]    }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "reset",    "params": {        "optics": \[            {                "opticsId": "0",                "focus": true,                "zoom": false            },            {                "opticsId": "1",                "focus": true,                "zoom": false            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "reset",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "reset",    "error": {        "code": 1200,        "message": "Internal error"    }}
```

### Calibrate optics

Use this example to re-calibrate the optics to regain the zoom and focus.

1.  Calibrate the optics mechanics with the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "calibrate",    "params": {        "optics": \[            {                "opticsId": "0",                "zoom": true,                "focus": true            },            {                "opticsId": "1",                "zoom": true,                "focus": true            }        \]    }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "calibrate",    "params": {        "optics": \[            {                "opticsId": "0",                "zoom": true,                "focus": true            },            {                "opticsId": "1",                "zoom": true,                "focus": true            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "calibrate",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "calibrate",    "error": {        "code": 1200,        "message": "Internal error"    }}
```

### Turn off the IRCut filter

Use this example to manually turn off the IRCut filter to see better in difficult lighting condition.

1.  Turn off the IRCut filter with the following request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "setIrCutFilterState",    "params": {        "optics": \[            {                "opticsId": "0",                "irCutFilterState": "off"            }        \]    }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "setIrCutFilterState",    "params": {        "optics": \[            {                "opticsId": "0",                "irCutFilterState": "off"            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setIrCutFilterState",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setIrCutFilterState",    "error": {        "code": 1200,        "message": "Internal error"    }}
```

### Change the focus relative to the current position

1.  Move the focus with a relative focus change.

```bash
{    "apiVersion": "1",    "context": "abc",    "method": "setRelativeFocus",    "params": {        "optics": \[            {                "opticsId": "0",                "type": "+bigStep"            },            {                "opticsId": "1",                "type": "numerical",                "value": -0.1            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setRelativeFocus",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setRelativeFocus",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

### Change the magnification relative to the current position

1.  Move the magnification with a relative magnification change.

```bash
{    "apiVersion": "1",    "context": "abc",    "method": "setRelativeMagnification",    "params": {        "optics": \[            {                "opticsId": "0",                "type": "+bigStep"            },            {                "opticsId": "1",                "type": "numerical",                "value": -0.1            }        \]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setRelativeMagnification",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setRelativeMagnification",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

## API specification
### getOptics

This method retrieves all optics along with their status and abilities.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "getOptics"}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "getOptics"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getOptics"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getOptics",  "data": {    "numberOfOptics": <0-255>,    "optics": \[      {        "opticsId": <string>,        "focusPosition": <number>,        "focusMoving": <boolean>,        "focusWindowUpperLeftX": <number>,        "focusWindowUpperLeftY": <number>,        "focusWindowWidth": <number>,        "focusWindowHeight": <number>,        "magnification": <number>,        "zoomMoving": <boolean>,        "temperatureCompensation": <boolean>,        "irCutFilterState": <string>,        "irCompensation": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getOptics"` | The API method used in the request. |
| `data.numberOfOptics` | The number of optics available on the device. |
| `data.optics[]` | Omitted if `numberOfOptics` is zero. |
| `data.optics[].opticsID=<string>` | The optics ID. |
| `data.optics[].focusPosition=<double>` | The current position of the focus shown as a value between 0 and 1. |
| `data.optics[].focusMoving=<boolean>` | Shows if the focus is moving. |
| `data.optics[].focusWindowUpperLeftX=<number>` | The distance from the upper left corner of the image to the upper left corner of the focus window on the X-plane. Has a value between 0 and 1, with 0 being the top edge of the image and 1 being the bottom. |
| `data.optics[].focusWindowUpperLeftY=<number>` | The distance from the upper left corner of the image to the upper left corner of the focus window on the Y-plane. Has a value between 0 and 1, with 0 being the top edge of the image and 1 being the bottom. |
| `data.optics[].focusWindowWidth=<number>` | The width of the focus window in a value between 0 and 1. represents the window having 100% width of the image. Please note that `focusWindowUpperLeftX+focusWindowWidth` can not exceed 1. |
| `data.optics[].focusWindowHeight=<number>` | The height of the focus window in a value between 0 and 1. 1 represents the window having 100% height of the image. Please not that `focusWindowUpperLeftY+focusWindowHeight` can not exceed 1. |
| `data.optics[].magnification=<double>` | The current magnification of the zoom lens. This is omitted if the optics doesn’t support zoom. |
| `data.optics[].zoomMoving=<boolean>` | Shows if the zoom lens is moving. This is omitted if the optics doesn’t support zoom. |
| `data.optics[].temperatureCompensation=<boolean>` | Shows if the temperature compensation is enabled. |
| `data.optics[].irCutFilterState=<string enum>` | Shows the current IRCut Filter setting. Possible vaues are: `on`: Filter is forced on. `off`: Filter is forced off. `auto`: Filter state is set by software algorithms. |
| `data.optics[].irCompensation=<boolean>` | Shows if the IR compensation is enabled. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getOptics",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getOptics"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getCapabilities

This method retrieves the capabilities of all available optics.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "getCapabilities"}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "getCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getCapabilities"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getCapabilities",  "data": {    "numberOfOptics": <0-255>,    "optics": \[      {        "opticsId": <string>,        "capabilities": \[          <string>        \],        "maxMagnification": <number>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getCapabilities"` | The API method used in the request. |
| `data.numberOfOptics` | The number of optics available on the device. |
| `data.optics[]` | Omitted if `numberOfOptics` is zero. |
| `data.optics[].opticsID=<string>` | The optics ID. |
| `data.optics[].capabilities[]` | List the optics capabilities listed in the tablebelow. |
| `data.optics[].maxMagnification=<number>` | The maximum possible magnification that can be set. Only available for devices where zoom is available. |

Possible capabilities for the capabilities object

| Property | Description |
| --- | --- |
| `focus` | Focus control is supported. |
| `zoom` | Zoom control is supported. |
| `irCutFilter` | IR Cut Filter control is supported. |
| `calibrateFocus` | Focus calibration is supported. |
| `calibrateZoom` | Zoom calibration is supported. Please note that this is only present on products where zoom is available. |
| `compensateTemperature` | Temperature compensation for focus is supported. |
| `compensateIr` | IR Compensation for focus is supported. |

Property names of the optics objects

| Property | Description |
| --- | --- |
| `opticsId` | The optics ID. |
| `capabilities` | An array containing supported capabilities. |
| `maxMagnification` | The largest value that can be set in `magnification`. note that this is only present on products where zoom is available. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getCapabilities"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setFocus

This method sets a focus position for one or more optics.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setFocus"  "params": {    "optics": \[      {        "opticsId": <string>,        "position": <number>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setFocus"  "params": {    "optics": \[      {        "opticsId": <string>,        "position": <number>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setFocus"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set the focus on. |
| `params.optics[].position` | The new focus position. Can be a value between 0 and 1. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setFocus",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setFocus"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setFocus",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setFocus"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setRelativeFocus

This method changes the current focus with relative focus movement. Please note that this is only available on products with the capability focus. See [getCapabilities](#getcapabilities) to find out if your product supports specific capabilities.

This method doesn’t return an error if any optics reaches its maximum or minimum focus. The current focus offset is clamped to make sure it is always within the valid range.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setRelativeFocus",  "params": {    "optics": \[      {        "opticsId": <string>,        "type": <string>,        "value": <double>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setRelativeFocus",  "params": {    "optics": \[      {        "opticsId": <string>,        "type": <string>,        "value": <double>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setRelativeFocus"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to change the relative focus on. |
| `params.optics[].type` | Possible values: `+bigStep`, `-bigStep`, `+smallStep`, `-smallStep`, `numerical`. |
| `params.optics[].value` | The desired focus offset. Use it when `params.optics[].type` is set to `numerical`(optional). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setRelativeFocus",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setRelativeFocus"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setRelativeFocus",  "error": {    "code": <integer error code>,    "message": <string>,    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setRelativeFocus"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setMagnification

This method sets the magnification for one or more optics. Please note that this is only available on products with the capability zoom. See [getCapabilities](#getcapabilities) to find out if your product supports specific capabilities.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setMagnification"  "params": {    "optics": \[      {        "opticsId": <string>,        "magnification": <number>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setMagnification"  "params": {    "optics": \[      {        "opticsId": <string>,        "magnification": <number>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setMagnification"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set magnification on. |
| `params.optics[].magnification` | The new magnification value. Can be a value between 1 and `maxMagnification` in the `getOptics` call. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setMagnification",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setMagnification"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setMagnification",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setMagnification"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setRelativeMagnification

This method changes the current magnification with relative magnification movement. Please note that this is only available on products with the capability zoom. See [getCapabilities](#getcapabilities) to find out if your product supports specific capabilities.

This method doesn’t return an error if any optics reaches its maximum or minimum magnification. The current magnification offset is clamped to make sure it is always within the valid range.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setRelativeMagnification",  "params": {    "optics": \[      {        "opticsId": <string>,        "type": <string>,        "value": <double>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setRelativeMagnification",  "params": {    "optics": \[      {        "opticsId": <string>,        "type": <string>,        "value": <double>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setRelativeMagnification"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to change the relative magnification on. |
| `params.optics[].type` | Possible values: `+bigStep`, `-bigStep`, `+smallStep`, `-smallStep`, `numerical`. |
| `params.optics[].value` | The desired magnification offset. Use it when `params.optics[].type` is set to `numerical`(optional). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setRelativeMagnification",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setRelativeMagnification"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setRelativeMagnification",  "error": {    "code": <integer error code>,    "message": <string>,    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setRelativeMagnification"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### calibrate

This method calibrates the optics for both zoom and focus, which is useful for optics that ended up in an undefined state and needs a re-calibration. This is only available on devices where either `calibrateFocus` or `calibrateZoom` is present.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "calibrate"  "params": {    "optics": \[      {        "opticsId": <string>,        "zoom": <boolean>,        "focus": <boolean>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "calibrate"  "params": {    "optics": \[      {        "opticsId": <string>,        "zoom": <boolean>,        "focus": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="calibrate"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to calibrate. |
| `params.optics[].focus` | Whether to calibrate focus in optics `opticsID` (optional). Default value is false if this parameter does not get set. |
| `params.optics[].zoom` | Whether to calibrate zoom in optics `opticsID` (optional). Default value is false if this parameter does not get set and ignored if no zoom is available on the device. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "calibrate",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="calibrate"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "calibrate",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="calibrate"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### performAutofocus

This method performs auto focus on one or more of your optics.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "performAutofocus"  "params": {    "optics": \[      {        "opticsId": <string>,      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "performAutofocus"  "params": {    "optics": \[      {        "opticsId": <string>,      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="performAutofocus"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to perform autofocus on. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "performAutofocus",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="performAutofocus"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "performAutofocus",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="performAutofocus"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### reset

This method resets the optics back to their default position.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "reset"  "params": {    "optics": \[      {        "opticsId": <string>,        "zoom": <boolean>,        "focus": <boolean>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "reset"  "params": {    "optics": \[      {        "opticsId": <string>,        "zoom": <boolean>,        "focus": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="reset"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to reset. |
| `params.optics[].focus` | Whether to calibrate focus in optics `opticsID` (optional). Default value is false if this parameter does not get set. |
| `params.optics[].zoom` | Whether to calibrate zoom in optics `opticsID` (optional). Default value is false if this parameter does not get set and ignored if no zoom is available on the device. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "reset",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="reset"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "reset",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="reset"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setFocusWindow

This method sets the window where the automatic focus search should optimize the focus.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setFocusWindow"  "params": {    "optics": \[      {        "opticsId": <string>,        "upperLeftX": <number>,        "upperLeftY": <number>,        "width": <number>,        "height": <number>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setFocusWindow"  "params": {    "optics": \[      {        "opticsId": <string>,        "upperLeftX": <number>,        "upperLeftY": <number>,        "width": <number>,        "height": <number>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setFocusWindow"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set the focus window on. |
| `params.optics[].upperLeftX` | Specifies the upper windows upper left corner distance from the full image upper left corner along the X-plane and given as a number between 0 to 1, representing the percentage of the whole image. |
| `params.optics[].upperLeftY` | Specifies the upper windows upper left corner distance from the full image upper left corner along the Y-plane and given as a number between 0 to 1, representing the percentage of the whole image. |
| `params.optics[].width` | Specifies the upper windows width and is given as a number between 0 and 1, representing the percentage of the whole image width. This means that `upperLeftX+width` can’t be more than 1 or it will be truncated. |
| `params.optics[].height` | Specifies the upper windows height and is given as a number between 0 and 1, representing the percentage of the whole image height. This means that `upperLeftY+height` can’t be more than 1 or it will be truncated. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setFocusWindow",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setFocusWindow"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setFocusWindow",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setFocusWindow"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setTemperatureCompensation

This method sets the active temperature compensation that should be used. This method is only available if `compensateTemperature` is true. Please note that the active focus compensation might not work as well if your device has a non-standard lens.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setTemperatureCompensation"  "params": {    "optics": \[      {        "opticsId": <string>,        "enable": <boolean>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setTemperatureCompensation"  "params": {    "optics": \[      {        "opticsId": <string>,        "enable": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setTemperatureCompensation"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set temperature compensation on. |
| `params.optics[].enable` | Specifies if active temperature compensation should be enabled or disabled. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureCompensation",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setFocusWindow"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureCompensation",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setTemperatureCompensation"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setIrCutFilterState

This method sets the desired state of the IRCut filter to either `on/off/auto`. The settings `on` and `off` reflect the manual state while `auto` leaves the decision of the IRCut filter state to the software algorithms.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setIrCutFilterState"  "params": {    "optics": \[      {        "opticsId": <string>,        "irCutFilterState": <string>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setIrCutFilterState"  "params": {    "optics": \[      {        "opticsId": <string>,        "irCutFilterState": <string>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setIrCutFilterState"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set the IRCut filter on. |
| `params.optics[].irCutFilterState` | Specifies that state for the IRCut filter. Valid values are: `on`: Filter is forced on. `off`: Filter is forced off. `auto`: The decision is made by the software algorithm. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIrCutFilterState",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setIrCutFilterState"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIrCutFilterState",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setIrCutFilterState"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setIrCompensation

This method decides if IR compensation should be used.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setIrCompensation"  "params": {    "optics": \[      {        "opticsId": <string>,        "enable": <boolean>      }    \]  }}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<Major>",  "context": "<string>",  "method": "setIrCompensation"  "params": {    "optics": \[      {        "opticsId": <string>,        "enable": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<Major>"` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setIrCompensation"` | Specifies the API method. |
| `params.optics[].opticsID` | The optics ID to set the IR compensation on. |
| `params.optics[].enable` | Specifies if active temperature compensation should be enabled or disabled. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIrCompensation",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setIrCompensation"` | The API method used in the request. |
| `data` | Empty for successful calls. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIrCompensation",  "error": {    "code": <integer error code>,    "message": <string>    "details": {      "opticsId": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "opticsId": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setIrCompensation"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |
| `error.details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.details.propertyName=<string>` | The property name corresponding to the error code (optional). |
| `error.errors[]` | Available if there is more than one error. |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the error code. |
| `error.errors[].details.opticsId=<string>` | The optics ID corresponding to the error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name corresponding to the error code (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSupportedVersions

This method retrieves a list of supported API versions.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/opticscontrol.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/opticscontrol.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getSupportedVersions"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[      "<Major1>.<Minor1>", "<Major2>.<Minor2>"    \]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getSupportedVersions"` | The API method used in the request. |
| `data.apiVersions[]=<list of versions>` | Lists all supported major versions along with their highest supported minor version. |
| `<list of versions>` | Lists of "<Major>.<Minor>" versions e.g. \["1.4", "2.5"\] |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getSupportedVersions"` | The API version used in the request. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

| Code | Description |
| --- | --- |
| `1100` | Internal error |
| `1200` | Temperature out of range |
| `1300` | Focus not found |
| `2100` | API version not supported |
| `2101` | Invalid JSON |
| `2102` | Method not supported |
| `2103` | Required parameter missing |
| `2104` | Invalid parameter value specified |
| `2105` | Authorization failed |
| `2106` | Authentication failed |