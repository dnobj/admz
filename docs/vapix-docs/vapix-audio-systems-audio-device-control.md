---
title: Audio Device Control
url: "https://developer.axis.com/vapix/audio-systems/audio-device-control/"
category: vapix
subcategory: audio-systems
sha256: 25db42ade8b978e24c36c67e829f9c959e924a816fc7a3cb286fe4d036cee97f
scraped_at: "2026-01-09T15:18:20.453Z"
page_height: 38024
---

# Audio Device Control

The VAPIX® Audio Device Control API contains the information required to configure and control your audio devices in various ways, including:

-   Retrieving a list of available audio capabilities for the device as well as the external audio devices that can be plugged into it.
-   Retrieving a list of of both configurable and current audio settings on your device, as well as any compatible external audio device.
-   Setting the gain value for selected inputs and outputs.
-   Setting the type value for selected input and outputs.
-   Muting selected inputs and outputs.

The API is based around audio devices with inputs and outputs. For example, a speaker will always have at least one device with one output that is always available and cannot be disconnected.

```bash
+---------+        +--------------+        +----------+| Input 0 | ------ |    Device    | ------ | Output 0 |+---------+        |      0       |        +----------++---------+        |              || Input 1 | ------ |              |+---------+        +--------------++---------+        +--------------+        +----------+| Input 0 | ------ |    Device    | ------ | Output 0 |+---------+        |      1       |        +----------+                   +--------------+
```

## Overview

The API uses `/axis-cgi/audiodevicecontrol.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getDevicesCapabilities` | Retrieves a list of all audio capabilities on your device. |
| `getDevicesSettings` | Retrieves a list of the current audio parameters. |
| `setDevicesSettings` | Sets the audio parameters. |
| `getHazardousSettings` | Retrieves a list of hazardous settings. |
| `getSupportedVersions` | Retrieves a list of supported API versions. |

### Identification

-   **API Discovery**: `id=audio-device-control`

### Obsoletes

This API makes the parameters in the group `AudioSource.A#` obsolete. Although they can still be kept in parallel, it will not receive any updates to match this new API. The parhand parameters replaced are:

-   `InputGain`
-   `InputType`
-   `MicrophoneBalance`
-   `MicrophonePower`
-   `MicrophonePowerType`
-   `OutputGain`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Retrieve audio capabilities

Use this example to retrieve a list containing all available audio capabilities for your device. The list will include the number of accepted gain values as well as accepted power types that can be applied to the audio device.

1.  Start with the following request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesCapabilities"}'
    ```
    
    ```bash
    POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesCapabilities"}
    ```
    
2.  Parse the JSON response. A successful response will return a list containing all available devices along with their capabilities.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesCapabilities",    "data": {        "devices": \[            {                "id": "Q1615-MkIII",                "inputs": \[                    {                        "id": "0",                        "connectionTypes": \[                            {                                "id": "internal",                                "signalTypes": \[                                    {                                        "id": "unbalanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["On", "Off"\]                                    }                                \]                            },                            {                                "id": "mic",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["P48", "Off"\]                                    },                                    {                                        "id": "unbalanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["5V", "Off"\]                                    }                                \]                            },                            {                                "id": "line",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["On", "Off"\]                                    },                                    {                                        "id": "unbalanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["On", "Off"\]                                    }                                \]                            }                        \]                    },                    {                        "id": "1",                        "connectionTypes": \[                            {                                "id": "mic",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["P48", "Off"\]                                    },                                    {                                        "id": "unbalanced",                                        "gainValues": \[1, 2, 4\],                                        "powerTypes": \["5V", "Off"\]                                    }                                \]                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "connectionTypes": \[                            {                                "id": "external",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "gainValues": \[1, 2, 4\]                                    }                                \]                            }                        \]                    }                \]            }        \]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "2.1",    "context": "abc",    "method": "getDevicesCapabilities",    "error": {        "code": 1100,        "message": "Internal error"    }}
    ```
    

See [getDevicesCapabilities](#getdevicescapabilities) for additional details.

### Retrieve current device settings

Use this example to retrieve a list containing all available as well as currently applied settings on your audio device.

1.  Start with the following request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesSettings"}'
    ```
    
    ```bash
    POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesSettings"}
    ```
    
2.  Parse the JSON response. A successful response will return a list containing all available devices along with their current settings.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "getDevicesSettings",    "data": {        "devices": \[            {                "id": "Q1615-MkIII",                "name": "Q1655-MkIII Audio Device",                "inputs": \[                    {                        "id": "0",                        "name": "Conference Room 42",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "internal",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 3,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "line",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    },                    {                        "id": "1",                        "name": "Dining Room",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "5V",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "name": "Loudspeaker 2",                        "connectionTypeSelected": "external",                        "connectionTypes": \[                            {                                "id": "external",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 0,                                                "gain": 4,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \]            }        \]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "2.1",    "context": "abc",    "method": "getDevicesSettings",    "error": {        "code": 1100,        "message": "Internal error"    }}
    ```
    

See [getDevicesSettings](#getdevicessettings) for additional details.

### Change device settings

Use this example to change the audio settings for one or multiple audio devices.

1.  Start with the following request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setDevicesSettings",    "params": {        "devices": \[            {                "id": "Q1615-MkIII",                "name": "Q1615-MkIII Audio Device",                "inputs": \[                    {                        "id": "0",                        "name": "Conference Room 42",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "internal",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 3,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "line",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    },                    {                        "id": "1",                        "name": "Dining Room",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "5V",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "name": "Loudspeaker 2",                        "connectionTypeSelected": "external",                        "connectionTypes": \[                            {                                "id": "external",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 0,                                                "gain": 4,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \]            }        \]    }}'
    ```
    
    ```bash
    POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setDevicesSettings",    "params": {        "devices": \[            {                "id": "Q1615-MkIII",                "name": "Q1615-MkIII Audio Device",                "inputs": \[                    {                        "id": "0",                        "name": "Conference Room 42",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "internal",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 3,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            },                            {                                "id": "line",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "Off",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    },                    {                        "id": "1",                        "name": "Dining Room",                        "connectionTypeSelected": "internal",                        "connectionTypes": \[                            {                                "id": "mic",                                "signalingTypeSelected": "balanced",                                "signalingTypes": \[                                    {                                        "id": "balanced",                                        "powerType": "P48",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    },                                    {                                        "id": "unbalanced",                                        "powerType": "5V",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "name": "Loudspeaker 2",                        "connectionTypeSelected": "external",                        "connectionTypes": \[                            {                                "id": "external",                                "signalingTypeSelected": "unbalanced",                                "signalingTypes": \[                                    {                                        "id": "unbalanced",                                        "channels": \[                                            {                                                "id": 1,                                                "gain": 0,                                                "mute": false                                            },                                            {                                                "id": 0,                                                "gain": 4,                                                "mute": false                                            }                                        \]                                    }                                \]                            }                        \]                    }                \]            }        \]    }}
    ```
    
2.  Parse the JSON response.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "setDevicesSettings",    "data": {}}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "setDevicesSettings",    "error": {        "code": 2101,        "message": "The provided JSON input was invalid."    }}
    ```
    

See [setDevicesSettings](#setdevicessettings) for additional details.

### Retrieve hazardous settings

Use this example to retrieve a list containing all potentially harmful settings. This is useful for when you need additional information displayed due to the risk of one or several of them being harmful to the hardware if used incorrectly.

1.  Start with the following request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getHazardousSettings"}'
    ```
    
    ```bash
    POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getHazardousSettings"}
    ```
    
2.  Parse the JSON response. A successful response will return a list containing all hazardous settings.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "getHazardousSettings",    "data": {        "powerTypes": \["R12"\]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "abc",    "method": "getHazardousSettings",    "error": {        "code": 1100,        "message": "Internal error"    }}
    ```
    

See [getHazardousSettings](#gethazardoussettings) for additional details.

### Get supported versions

Use this example retrieve a list of API versions that is supported by your device.

1.  Start with the following request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
    ```
    
    ```bash
    POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
    ```
    
2.  Parse the JSON response.
    
    Successful response example
    
    ```bash
    {    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
    ```
    
    Error response example
    
    ```bash
    {    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 1100,        "message": "Internal error"    }}
    ```
    

See [getSupportedVersions](#getsupportedversions) for additional details.

## API specification
### getDevicesCapabilities

This method lists all audio capabilities on your current device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesCapabilities"}'
```

```bash
POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getDevicesCapabilities"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesCapabilities",  "data": {    "devices": \[      {        "id": <string>,        "inputs": \[          {            "id": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "gainValues": \[<integer>\],                    "powerTypes": \[<string>\]                  }                \]              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "gainValues": \[<integer>\]                  }                \]              }            \]          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getDevicesCapabilities"` | The API method used in the request. |
| `data.devices[]=<list of audio devices>` | Lists available audio devices. |
| `<audio device>.id` | The audio device ID. |
| `<audio device>.inputs[]=<list of inputs>` | Lists the inputs on a device. |
| `inputs.id` | The input ID. |
| `inputs.connectionTypes[]=<list of input connection types>` | Lists the input types. |
| `connectionTypes.id` | The input type ID. |
| `connectionTypes.signalingTypes[]=<list of signal configuration>` | Lists the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please not that this can not be changed. |
| `signalingTypes.gainValues[]=<list of supported gain values>` | The gain capabilities for the signaling type. |
| `signalingTypes.powerTypes[]=<list of supported power types>` | The power types available for the signal. |
| `<audio device>.outputs[]=<list of outputs>` | Lists the outputs on a device. |
| `outputs.id` | The output ID. |
| `outputs.connectionTypes[]=<list of output connection types>` | Lists the output types. |
| `connectionTypes.id` | The output type ID. |
| `connectionTypes.signalingTypes[]=<list of signal configurations>` | Lists the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please not that this can not be changed. |
| `signalingTypes.gainValues[]=<list of supported gain values>` | The gain capabilities for the signaling types. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getDevicesCapabilities"` | The API method used in the request. |
| `error=<object>` | The error object with an integer error code and a message string. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### getDevicesSettings

This method lists all audio settings currently installed on your device.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesSettings"}'
```

```bash
POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getDevicesSettings"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesSettings",  "data": {    "devices": \[      {        "id": <string>,        "name": <string>,        "inputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypeSelected": <string>                "signalingTypes": \[                  {                    "id": <string>,                    "powerType": <string>                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypesSelected": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getDevicesSettings"` | The API method used in the request. |
| `data.devices[]=<list of audio devices>` | Lists available audio devices. |
| `<audio device>.id` | The audio device ID. |
| `<audio device>.name` | The audio device name. |
| `<audio device>.inputs[]=<list of inputs>` | Lists the inputs on a device. |
| `inputs.id` | The input ID. |
| `inputs.name` | The input name. |
| `inputs.connectionTypeSelected` | The selected input type. |
| `inputs.connectionTypes[]=<list of input connection types>` | Lists the input types. |
| `connectionTypes.id` | The input type ID. |
| `connectionTypes.signalingTypeSelected` | The selected signal. |
| `connectionTypes.signalingTypes[]=<list of signal configuration>` | Lists the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please not that this is not changeable. |
| `signalingTypes.powerType` | The selected power type for a signal. |
| `signalingTypes.channels[]=<list of channels>` | Lists the channels for an input type. |
| `channels.id` | The channel ID. |
| `channels.gain` | The channel gain. |
| `channels.mute` | The channel mute. |
| `<audio device>.outputs[]=<list of outputs>` | Lists the outputs on a device. |
| `outputs.id` | The output ID. |
| `outputs.name` | The output name. |
| `outputs.connectionTypeSelected` | The selected output type. |
| `outputs.connectionTypes[]=<list of output connection types>` | Lists the output types. |
| `connectionTypes.id` | The output type ID. |
| `connectionTypes.signalingTypeSelected` | The selected signal. |
| `connectionTypes.signalingTypes[]=<list of signal configurations>` | Lists the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please not that this is not changeable. |
| `signalingTypes.channels[]=<list of channels>` | Lists the channels for an output type. |
| `channels.id` | The channel ID. |
| `channels.gain` | The channel gain. |
| `channels.mute` | The channel mute. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDevicesSettings",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getDevicesSettings"` | The API method used in the request. |
| `error=<object>` | The error object with an integer error code and a message string. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### setDevicesSettings

This method changes the audio settings currently active on your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDevicesSettings",  "params": {    "devices": \[      {        "id": <string>,        "name": <string>,        "inputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypeSelected": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "powerType": <string>,                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypeSelected": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \]      }    \]  }}'
```

```bash
POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDevicesSettings",  "params": {    "devices": \[      {        "id": <string>,        "name": <string>,        "inputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypeSelected": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "powerType": <string>,                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "name": <string>,            "connectionTypeSelected": <string>,            "connectionTypes": \[              {                "id": <string>,                "signalingTypeSelected": <string>,                "signalingTypes": \[                  {                    "id": <string>,                    "channels": \[                      {                        "id": <integer>,                        "gain": <integer>,                        "mute": <boolean>                      }                    \]                  }                \]              }            \]          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setDevicesSettings"` | The API method used in the request. |
| `params=<object>` | Container for method specific parameters listed below. |
| `params.devices[]=<list of audio devices>` | A list containing the available audio devices. |
| `<audio device>.id` | The audio device ID. |
| `<audio device>.name` | The audio device name. |
| `<audio device>.inputs[]=<list of inputs>` | A list containing the device inputs. |
| `inputs.id` | The input ID. |
| `inputs.name` | The input name. |
| `inputs.connectionTypeSelected` | The selected input type. |
| `inputs.connectionTypes[]=<list of input connection types>` | A list containing the input types. |
| `connectionTypes.id` | The input type ID. |
| `connectionTypes.signalingTypeSelected` | The selected signal. |
| `connectionTypes.signalingTypes[]=<list of signal configurations>` | A list containing the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please note that this is not changeable. |
| `signalingTypes.powerType` | The power type selected for the signal. |
| `signalingTypes.channels[]=<list of channels>` | A list of input type channels. |
| `channels.id` | The channel ID. |
| `channels.gain` | The channel gain. |
| `channels.mute` | The channel mute. |
| `<audio device>.outputs[]=<list of outputs>` | A list containing the device outputs. |
| `outputs.id` | The channel ID. |
| `outputs.name` | The channel gain. |
| `outputs.connectionTypeSelected` | The channel mute. |
| `outputs.connectionTypes[]=<list of output connection types>` | A list containing the output types. |
| `connectionTypes.id` | The output type ID. |
| `connectionTypes.signalingTypeSelected` | The selected signal. |
| `connectionTypes.signalingTypes[]=<list of signal configuration>` | A list containing the signal configuration settings. |
| `signalingTypes.id` | The signal ID. Please note that this can not be changed. |
| `signalTypes.channels[]=<list of channels>` | A list containing the output type channels. |
| `channels.id` | The channel ID. |
| `channels.gain` | The channel gain. |
| `channels.mute` | The channel mute. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDevicesSettings",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getDevicesSettings"` | The API method used in the request. |
| `data=<object>` | An empty data object |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDevicesSettings",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setDevicesSettings"` | The API method used in the request. |
| `error=<object>` | The error object with an integer error code and a message string. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### getHazardousSettings

This method retrieves a list of strings containing information about settings that may harm your device if used incorrectly. Please note that the settings are global, which means that they don’t depend on a selected device, nor input or output.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getHazardousSettings"}'
```

```bash
POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getHazardousSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getHazardousSettings"` | The API method used in the request. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getHazardousSettings",  "data": {    "powerTypes": \[      <string>    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getHazardousSettings"` | The API method used in the request. |
| `data.powerTypes[]=<list of hazardous powerTypes>` | A list containing the hazardous powerTypes. |
| `<list of hazardous powerTypes>` | The hazardous powerTypes, e.g. \["R12"\]. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getHazardousSettings",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getHazardousSettings"` | The API method used in the request. |
| `error=<object>` | The error object with an integer error code and a message string. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### getSupportedVersions

This method retrieves a list of API versions supported by your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiodevicecontrol.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/audiodevicecontrol.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getSupportedVersions"` | The API method used in the request. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[      "<Major1>.<Minor1>",      "<Major2>.<Minor2>"    \]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getSupportedVersions"` | The API method used in the request. |
| `data.apiVersions[]=<list of versions>` | A list containing the supported major API versions along with their highest minor version. |
| `<list of versions>` | List of <Major>.<Minor> versions, e.g. \["1.2", "3.4"\] |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getHazardousSettings"` | The API method used in the request. |
| `error=<object>` | The error object with an integer error code and a message string. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### General error codes

| Code | Definition | Description |
| --- | --- | --- |
| `1100` | INTERNAL\_ERROR | Internal error. |
| `2100` | UNSUPPORTED\_API\_VERSION | The requested API version is not supported. |
| `2101` | JSON\_INVALID\_ERROR | The provided JSON input was invalid. |
| `2102` | METHOD\_NOT\_SUPPORTED | Method not supported. |
| `2103` | JSON\_KEY\_NOT\_FOUND | A mandatory input parameter was not found in the input. |
| `2104` | PARAM\_INVALID\_VALUE\_ERROR | Invalid parameter value specified. |
| `2105` | AUTHORIZATION\_ERROR | Authorization failed. |
| `2106` | AUTHENTICATION\_ERROR | Authentication failed. |
| `2107` | TRANSPORT\_LEVEL\_ERROR | Transport level error. |