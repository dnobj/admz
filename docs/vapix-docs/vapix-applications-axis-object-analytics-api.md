---
title: AXIS Object analytics API
url: "https://developer.axis.com/vapix/applications/axis-object-analytics-api/"
category: vapix
subcategory: applications
sha256: 9adcda47f340bdb552ce84bb07117726abe20dd3b7d3bfdd58952004974bd206
scraped_at: "2026-01-09T15:01:05.407Z"
page_height: 67089
---

# AXIS Object analytics API

The VAPIX® AXIS Object analytics API (AOA API) contains the information that makes it possible configure a number of different scenarios with object detection. Each scenario or event defines a set of rules that can be applied to detected objects to decide if an alarm should be triggered. AOA can also filter out unwanted objects, such as small animals and moving leafs. All of this can be made visible on the video stream.

AOA supports fixed cameras, PTZ (Pan, Tilt, Zoom) cameras.

The Common Gateway Interface (CGI) API provides the ability to configure and setup different scenarios for object analytics.

## Overview

The API implements `/local/objectanalytics/control.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getConfigurationCapabilities` | Retrieve information about the configuration limits and capabilities of the camera where the application is running. |
| `setConfiguration` | Apply a complete application configuration to the camera. |
| `getConfiguration` | Retrieve a complete application configuration. |
| `getSupportedVersions` | Retrieve a list of supported API versions. |
| `sendAlarm` | Trigger a test alarm. |
| `getAccumulatedCounts` | Retrieve current accumulated counts from a Crossline Counting scenario. |
| `resetAccumulatedCounts` | Reset the accumulated counts from a Crossline Counting scenario. |
| `resetPassthrough` | Reset the passthrough counter for a Crossline Counting scenario. |
| `getOccupancy` | Retrieve the current occupancy for an Occupancy in Area scenario. |

Additional information about the API method, their parameters and how to use them can be found here:

-   [Configuration](#configuration)
-   [Configuration capabilities](#configuration-capabilities)

### JSON syntax

The API implements the Google JSON style guide for its method structure.

Optional JSON parameters may be omitted or sent as `null`, `[]` or `{}`. Please note that the Object analytics application can’t modify or format the parameters in a successful `setConfiguration` request and the client format will instead be kept in a consecutive `getConfiguration` request.

### Identification

Use `/axis-cgi/applications/list.cgi` to check if the application is installed on your Axis device.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Read configuration capabilities

Use this example to retrieve the application capabilities of your device. This is useful when you want to adapt a user interface to implement either limitations or the default values of the application, including support for multiple camera models.

1.  Request configuration capabilities.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfigurationCapabilities"}'
    ```
    
    ```bash
    POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfigurationCapabilities"}
    ```
    
2.  Parse the JSON response.
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "getConfigurationCapabilities",    "data": {        ...    }}
    ```
    
    See [get configuration capabilities](#get-configuration-capabilities) for additional details.
    

### Create a scenario for object detection

Use this example to set up rules that should apply for the object detection on your device. A minimal scenario consists of an ID, name, trigger and a list of connected devices. For additional information see [Scenarios](#scenarios-configuration-capabilities).

1.  Configure the basic scenario parameters. The code below contains the minimal requirements for a scenario and consists of the following parameters:
    
    -   `id`: The identifier
    -   `name`: The human readable name for the scenario.
    -   `type`: Determines what trigger and filter types that should be allowed. For example, the `motion` scenario implements an include area for triggering alarms.
    -   `devices`: Tells the application which device the scenario should be uploaded to.
    -   `triggers`: Defines an include area that will trigger when detecting a moving object.
    
    ```bash
    {    ...    "scenarios": \[        {            "id": 1,            "name": "My Scenario",            "type": "motion",            "devices": \[                {                    "id": 1                }            \],            "triggers": \[                {                    "type": "includeArea",                    "vertices": \[                        \[-0.9, -0.9\],                        \[-0.9, 0.9\],                        \[0.9, 0.9\],                        \[0.9, -0.9\]                    \]                }            \]        }    \],    ...}
    ```
    
2.  Use the `setConfiguration` method to upload the configuration to your device. The scenario will take effect immediately.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        <the complete configuration object defined above>    }}'
    ```
    
    ```bash
    POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        <the complete configuration object defined above>    }}
    ```
    
3.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration"}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "error": {        "code": 2004,        "message": "Invalid parameter"    }}
    ```
    
4.  Verify that objects detected in the include area triggers an alarm.
    

See [Scenarios](#scenarios-configuration) and [set configuration](#set-configuration) for additional details.

### Visualize scenario alarms

Use this example to control an overlay from the object detection scenarios, visible in both live and recorded video.

1.  Enable metadata overlays in the device configuration. The first step is to make sure that there is an entry in the `metadataOverlay` device listing. This will tell the application what resolutions that should be used for each specific device. The following example will assume that the camera has one optical device that put out a metadata overlay in `1280x720`.
    
    ```bash
    "metadataOverlay": \[    {        "id": 1,        "drawnOnAllResolutions": false,        "resolutions": \[            "1280x720"        \]    }\]
    ```
    
    See [Metadata overlay](#metadata-overlay-configuration) for additional information.
    
2.  Enable overlays in the scenario configuration, such as the one created in step 1. This will initiate the overlay, while omitting it will halt the scenario.
    
    ```bash
    "scenarios": \[    ...    {        ...        "name": "my scenario",        "metadataOverlay": 1,        ...    },    ...\]
    ```
    
    See [Scenarios](#scenarios-configuration) for additional information.
    
3.  Use the `setConfiguration` method to upload your new configuration. This will start the metadata overlay in the configured resolutions.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        ...    }}'
    ```
    
    ```bash
    POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        ...    }}
    ```
    
4.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration"}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "error": {        "code": 2004,        "message": "Invalid parameter"    }}
    ```
    
5.  Verify that the detected objects are visible in the video stream.
    

See [set configuration](#set-configuration) for additional details.

### Backup and restore configuration

Use this example to create a back-up configuration on your cameras that can then be restored at a later time.

**Retrieve the current configuration from the application**

1.  Request the current configuration using the `getConfiguration` method.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration"}'
    ```
    
    ```bash
    POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration"}
    ```
    
2.  Parse the JSON response. The `data` object contains the entire configuration.
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "getConfiguration",    "data": {        ...    }}
    ```
    
3.  Store the configuration data for backup purposes.
    

See [get configuration](#get-configuration) for additional details.

**Upload a backup configuration to the application**

1.  Upload the stored configuration using the `setConfiguration` method. The `params` object should be the contents of the `data` object from the previous request.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        <the backed up <data> object from getConfiguration>    }}'
    ```
    
    ```bash
    POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "params": {        <the backed up <data> object from getConfiguration>    }}
    ```
    
2.  Parse the JSON response.
    
    Successful response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration"}
    ```
    
    Error response
    
    ```bash
    {    "apiVersion": "1.2",    "context": "my context",    "method": "setConfiguration",    "error": {        "code": 2004,        "message": "Invalid parameter"    }}
    ```
    

See [set configuration](#set-configuration) for additional details.

## API specification
### Get configuration capabilities

This method is used when you want to request a JSON object that describes the min, max and default/reference values of all configurable parameters.

#### Request

-   **Access control**: admin

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities"}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getConfigurationCapabilities"` | Specifies the API method. |

#### Successful response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities",  "data": {    "devices": \[      ...    \],    "filters": \[      ...    \],    "metadataOverlay": {      ...    },    "objectClassifications": {      ...    },    "perspective": {      ...    },    "scenarios": {      ...    },    "triggers": \[      ...    \],    "presets": {      ...    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="getConfigurationCapabilities"` | The API method used in the request. |
| `data` | The data object. |
| `devices` | Container for the supported video devices. |
| `filters` | Container for the supported filters. |
| `metadataOverlay` | Container for the metadata overlay options. |
| `objectClassifications` | Container for the classification types as well as their subtypes. |
| `perspective` | Container for the perspective data. |
| `scenarios` | Container for the scenario data. |
| `triggers` | Container for the supported trigger types. |
| `presets` | Container for the PTZ presets. |

For additional information about the `data` field, it’s supported parameters and respective value, see [Configuration capabilities](#configuration-capabilities).

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `1000` | An error occurred inside the application. |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |
| `2005` | The requested CGI method is not supported. |

### Get configuration

This method is used when you want to request a JSON object describing the current application configuration.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getConfiguration"}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getConfiguration"` | Specifies the API method. |

#### Successful response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfiguration",  "data": {    "devices": \[      ...    \],    "filters": \[      ...    \],    "metadataOverlay": {      ...    },    "objectClassifications": {      ...    },    "perspective": {      ...    },    "scenarios": {      ...    },    "triggers": \[      ...    \],    "presets": {      ...    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="getConfiguration"` | The API method used in the request. |
| `data` | The data object. |
| `devices` | Container for the supported video devices. |
| `filters` | Container for the supported filters. |
| `metadataOverlay` | Container for the metadata overlay options. |
| `objectClassifications` | Container for the classification types as well as their subtypes. |
| `perspective` | Container for the perspective data. |
| `scenarios` | Container for the scenario data. |
| `triggers` | Container for the supported trigger types. |
| `presets` | Container for the PTZ presets. |

For additional information about the `data` field, it’s supported parameters and respective value, see [Configuration capabilities](#configuration-capabilities).

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `1000` | An error occurred inside the application. |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |
| `2005` | The requested CGI method is not supported. |

### Set configuration

This method is used when you want to set a configuration of the application immediately. Any ongoing event will be set as inactive when a new configuration is applied, which will cause ongoing recordings to stop. This is also true for multichannel cameras, which will all be affected simultaneously. Exception is made if there is movement in the include area even after the configuration has been set and no exclusion filter hinders the alarm to be sent. This will instead cause the event to be set to active directly after the new configuration is applied.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setConfiguration"  "params": {    ...  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setConfiguration"  "params": {    ...  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="setConfiguration"` | Specifies the API method. |
| `params` | The parameter objects. |

#### Successful response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setConfiguration",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="setConfiguration"` | The API method used in the request. |
| `data` | The data object. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `1000` | An error occurred inside the application. |
| `2000` | The requested version of the application is not supported. |
| `2002` | Incoherent configuration (such as mismatched ID). |
| `2003` | A mandatory parameter is missing. |
| `2004` | Invalid parameter. |
| `2005` | The requested CGI method is not supported. |

### Get supported versions

This method is used when you want to retrieve a list of API versions supported by your device.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getSupportedVersions"` | Specifies the API method. |

#### Successful response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[<Major>.<Minor>, ...\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="getSupportedVersions"` | The API method used in the request. |
| `data` | The data object. |
| `apiVersions` | A list of API versions supported by the application. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `1000` | An error occurred inside the application. |
| `2005` | The requested CGI method is not supported. |

### Send alarm event

This method is used when you want to force a scenario to enter its alarm state for a 3 second duration. This will trigger the scenario to emit events in both Axis and ONVIF formats while the alarm is on high.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "sendAlarmEvent"  "params": {    "scenario": <uid>  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "sendAlarmEvent"  "params": {    "scenario": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="sendAlarmEvent"` | Specifies the API method. |
| `scenario=<uid>` | Defines which scenario that will send the alarm event. `<uid>` represents the unique scenario ID. |

#### Successful response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "sendAlarmEvent",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="sendAlarmEvent"` | The API method used in the request. |
| `data` | The data object. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "sendAlarmEvent",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `1000` | An error occurred inside the application. |
| `2000` | The requested version of the application is not supported. |
| `2005` | The requested CGI method is not supported. |

### Get accumulated counts

This method is used when you want to retrieve the accumulated counts for a Crossline Counting scenario. The response will include the total number of objects for each configured class that have passed the counting line.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAccumulatedCounts",  "params": {    "scenario": <uid>  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAccumulatedCounts",  "params": {    "scenario": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getAccumulatedCounts"` | Specifies the API method. |
| `scenario=<uid>` | Defines the scenario from which the accumulated counts should be obtained. `<uid>` represents the unique scenario ID. |

#### Successful response

```bash
200 OKContent-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getAccumulatedCounts",    "data": {        "resetTime": "<time when counting started or was last reset>",        "timeStamp": "<time when count was read>",        "total": "<number of counted objects of any category>",        "<category>": "<number of counted objects of a specific category>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="getAccumulatedCounts"` | The API method used in the request. |
| `data` | The data object. |
| `resettime` | Time when counting started or was last reset in the ISO 8601 format (a string `YYYY-MM-DDTHH:MM:SSZ` where `Y, M, D, H, M` and `S` are numbers expressing year, month, day, hour (`00-23`), minutes and seconds.) |
| `timestamp` | Time when count was read in the ISO 8601 format (a string `YYYY-MM-DDTHH:MM:SSZ`, where `Y, M, D, H, M` and `S` are numbers expressing year, month, day, hour (`00-23`), minutes and seconds). |
| `total` | The total number of counted objects of any category. |
| `<category>` | The number of counted objects of a specific `<category>` which, depending on the configuration, can be `car`, `bus`, `bike`, `human`, `truck` or `otherVehicle`. Each category included in the configuration corresponds to one entry in the `data` collection in the return value. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAccumulatedCounts",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |
| `2004` | The configuration contain an invalid parameter. |

### Reset accumulated counts

This method is used when you want to reset the object counts for a Crossline Counting scenario.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetAccumulatedCounts",  "params": {    "scenario": <uid>  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetAccumulatedCounts",  "params": {    "scenario": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="resetAccumulatedCounts"` | Specifies the API method. |
| `scenario=<uid>` | Defines the scenario from which the accumulated counts should be obtained. `<uid>` represents the unique scenario ID. |

#### Successful response

```bash
200 OKContent-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "resetAccumulatedCounts",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="resetAccumulatedCounts"` | The API method used in the request. |
| `data` | The data object. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetAccumulatedCounts",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |

### Reset passthrough

This method is used when you want to reset the counter used for passthrough for a Crossline Counting scenario. The passthrough threshold is represented by the `N` integer and will, when active, generate a new event for every `N` count by a separate passthrough counter.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetPassthrough",  "params": {    "scenario": <uid>  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetPassthrough",  "params": {    "scenario": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="resetPassthrough"` | Specifies the API method. |
| `scenario=<uid>` | Defines the scenario from which the accumulated counts should be obtained. `<uid>` represents the unique scenario ID. |

#### Successful response

```bash
200 OKContent-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "resetPassthrough",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="resetPassthrough"` | The API method used in the request. |
| `data` | The data object. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetPassthrough",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |

### Get occupancy

This method is used when you want to retrieve the current object counts for an Occupancy in Area scenario.

#### Request

-   **Access control**: operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/objectanalytics/control.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getOccupancy",  "params": {    "scenario": <uid>  }}'
```

```bash
POST /local/objectanalytics/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getOccupancy",  "params": {    "scenario": <uid>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getOccupancy"` | Specifies the API method. |
| `scenario=<uid>` | Defines the scenario from which the accumulated counts should be obtained. `<uid>` represents the unique scenario ID. |

#### Successful response

```bash
200 OKContent-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getOccupancy",    "data": {        "timeStamp": "<time when count was read>",        "total": "<number of counted objects of any category>",        "<category>": "<number of counted objects of a specific category>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version used in the request. |
| `context` | The context string provided in the request. |
| `method="getOccupancy"` | The API method used in the request. |
| `data` | The data object. |
| `timestamp` | Time when count was read in the ISO 8601 format (a string `YYYY-MM-DDTHH:MM:SSZ`, where `Y, M, D, H, M` and `S` are numbers expressing year, month, day, hour (`00-23`), minutes and seconds). |
| `total` | The total number of counted objects of any category. |
| `<category>` | The number of counted objects of a specific `<category>` which, depending on the configuration, can be `car`, `bus`, `bike`, `human`, `truck` or `otherVehicle`. Each category included in the configuration corresponds to one entry in the `data` collection in the return value. |

#### Error response

```bash
200 OKContent-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getOccupancy",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

| Error code | Description |
| --- | --- |
| `2000` | The requested version of the application is not supported. |
| `2003` | A mandatory parameter is missing. |
| `2004` | The configuration contains an invalid parameter. |

## Configuration

The purpose of this section is to describe the contents of the `setConfiguration` parameter objects and `getConfiguration` data objects. All listed coordinates are in the ONVIF format unless otherwise specified.

### Overview

The field in the general configuration structure seen below are all described in their separate sections. You will find that the structure is the same for both single and multichannel products, where the `devices` array lists the available channels in the camera.

All parameters and properties are considered mandatory unless otherwise specified.

```bash
"data": {  "devices": \[    ...  \],  "metadataOverlay": \[    ...  \],  "perspectives": \[    ...  \],  "scenarios": \[    ...  \]}
```

### Devices

To use a device in a scenario it first needs to be configured. This can be done by providing an entry for the device in the `devices` array. Throughout this chapter, the term _device_ refers to a physical or virtual device within the camera, capable of providing input to object analytics. Currently, only video streams originating from a physical hardware channel are supported.

```bash
"devices": \[  {    "id": <int>,    "type": <string>,    "rotation": <degrees>,    "isActive": <boolean>  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `id` | The device id that should correspond to the `id` in `data.devices` in `getConfigurationCapabilities`. |
| `type` | The device type (can only be camera). |
| `rotation` | The camera rotation, measured in degrees. Valid values are 0, 90, 180 or 270. |
| `isActive` _Optional_ | True if omitted. Excludes the device from being used if set to false. Any scenarios, perspectives or metadata overlays referring to this device will also be ignored. |

### Metadata overlay

An array of metadata overlay configurations. The size of this array is limited by `getConfigurationCapabilities.data.metadataOverlay.minNbrActiveCameras` and `getConfigurationCapabilities.data.metadataOverlay.maxNbrActiveCameras`.

Each device that puts out metadata overlays in a video stream requires a corresponding overlay configuration. In this case, the `metadataOverlay.id` field should match the array ID under `data.metadataOverlay.cameras` field of a device in the `data.devices` array. See [Devices](#devices-configuration) for additional information.

To enable metadata overlays in a scenario, you first need to specify which metadata configuration to use. This can be done by using the `metadataOverlay` parameter in the scenario. See [Scenarios](#scenarios-configuration) for additional information.

```bash
"metadataOverlay": \[  {    "id": <int>,    "drawOnAllResolutions": <boolean>    "resolutions": \["<width>x<height>", "<width>x<height>", ...\]  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `id` | The metadata overlay ID in the range `[1 ... n]`. Corresponds to the device ID. |
| `drawOnAllResolutions` | A boolean that determines whether the metadata overlay should be drawn on all available resolutions. This parameter is not mandatory if `resolutions` is specified. |
| `resolutions` | The supported resolutions array in the format `<width>x<height>`. This parameter should be empty nor not specified if `drawOnAllResolutions` is true. |

### Perspectives

By adding an entry to the `perspectives` list, you are able to define and use perspective filters in a scenario.

A perspective is composed of a number of bars and an algorithm that approximates the perspective of the entire image using the bars as a guide.

-   The number of perspectives are limited by `getConfigurationCapabilities`.
-   A perspective can only be applied to one device, meaning separate perspective configuration must be used in setups that include multiple devices.

```bash
"perspectives": \[  {    "id": <int>,    "bars": \[      "height": <int>,      "points": \[        \[<x1>, <y1>\],        \[<x2>, <y2>\]      \],      ...    \]  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `id` | A unique ID identifying the perspective. |
| `bars` | A list of bars contributing to the perspective calculation, limited by `getConfigurationCapabilities`. |
| `bars.height` | The virtual height (in centimeters) of an object appearing at the same location and perceived height in the camera view as the perspective bar. |
| `bars.points` | Start `pos 0` and end `pos 1` points for a perspective bar in ONVIF coordinates. The start position should be the point that touches the ground-plane. |

### Scenarios

The majority of the AOA application configurations are done within a scenario, including filters, triggers, object classifications and PTZ presets.

-   Scenarios act as user modes that create distinction between different triggers.
-   Scenarios lets you create individual setups that can run in parallel.
-   The number of simultaneously allowed scenarios are defined in `getConfigurationCapabilities`.

```bash
"scenarios": \[  {    "id": <int>,    "name": <string>,    "type": <string>,    "metadataOverlay": <id>,    "alarmRate": <string>,    "devices": \[      ...    \],    "triggers": \[      ...    \],    "filters": \[      ...    \],    "objectClassifications": \[      ...    \],    "perspectives": \[      ...    \],    "presets": \[      ...    \],  }\]
```

| Parameter | Description |
| --- | --- |
| `id` | A unique scenario ID. |
| `name` | A user friendly scenario name. |
| `type` | See table below for possible scenario types. |
| `metadataOverlay` _Optional_ | Enables and disables metadata overlays for a scenario, however it must point to a valid `id` in the `metadataOverlay` array. |
| `alarmRate` _Optional_ | Sets the alarm rate for the scenario. Valid rates are listed in `getConfigurationCapabilities.data.scenarios.alarmRates`. |
| `devices` | Mandatory, see [Scenario devices](#scenario-devices). |
| `triggers` | Mandatory, see [Scenario triggers](#scenario-triggers). |
| `filters` _Optional_ | See [Scenario filters](#scenario-filters). |
| `objectClassifications` _Optional_ | See [Scenario object classifications](#scenario-object-classifications). |
| `perspectives` _Optional_ | See [Scenario perspectives](#scenario-perspectives). |
| `presets` _Optional_ | See [Scenario PTZ presets](#scenario-ptz-presets). |

In terms of API functionality, different scenarios will either enable or disable some configurable settings such as triggers, shown in the table **Scenario feature matrix** below.

Scenario types

| Type | Description |
| --- | --- |
| `motion` | This scenario makes it possible to define an include area which acts as a trigger zone for moving objects. Additionally, filters can be configured to exclude objects based on other criteria, such as size. |
| `fence` | This scenario makes it possible to define a special fence trigger with a polyline shape activated by objects passing the line in a certain direction. See [Scenario triggers](#scenario-triggers) for additional information. |
| `crosslinecounting` | Crossline Counting scenario count objects crossing a defined counting line. The line has a polyline shape and is triggered by objects passing the line in a specified direction. See [Scenario triggers](#scenario-triggers) for additional information. |
| `occupancyInArea` | Occupancy in Area scenario allows defining an include area which are able to count objects. This include stationary objects. |

The triggers and filters supported by a scenario varies with scenario type, which means that you will receive an error message if a configuration with unsupported triggers or filters are uploaded.

Scenario feature matrix

| Feature | `motion` | `fence` | `crosslinecounting` | `occupancyinArea` | `occupancyinArea` |
| --- | --- | --- | --- | --- | --- |
| Filters | Exclude Area | Yes | No | No | Yes |
|  | Size Percentage | Yes | Yes | No | No |
|  | Size Perspective | Yes | Yes | Yes | Yes |
|  | Short-lived objects | Yes | Yes | No | No |
|  | Swaying objects | Yes | No | No | No |
|  | Speed | Yes | Yes | No | No |
| Triggers | Include Area | Yes | No | No | Yes |
|  | Fence | No | Yes | No | No |
|  | Counting Line | No | No | Yes | No |

#### Scenario devices

Lists the devices that the scenario should be applied to.

```bash
"devices": \[  {    "id": <int>  }  ...\]
```

| Parameter | Description |
| --- | --- |
| `id` | Points towards the device ID defined in the root `devices` list. See [Devices](#devices-configuration) for additional information. |

#### Scenario triggers

The triggers are what makes the application raise an alarm in a given scenario.

-   At least one trigger needs to be defined in a scenario for it to be valid.
-   The type of triggers available to a scenario depends on the scenario type.

```bash
"triggers": \[  {    "type": <string>,    ...  },  ...\]
```

**Include area**

This trigger is a polygon that activates an alarm whenever an object intersects an area defined by the polygon.

```bash
{  "type": "includeArea",  "vertices": \[    \[<x1>, <y1>\],    \[<x2>, <y2>\]    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `vertices` | A list of vertices that forms the include area. |

**Fence**

This trigger is a polyline that activates an alarm when an object crosses a line.

```bash
{  "type": "fence",  "alarmDirection": <string>,  "vertices": \[    \[<x1>, <y1>\],    \[<x2>, <y2>\]    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `alarmDirection` | The direction in which the trigger will activate the alarm for a crossing object, defined by `getConfigurationCapabilities.` |

| alarmDirection | Description |
| --- | --- |
| `"leftToRight"` | The fence trigger raises a alarm when an object passes the start of the reference line beginning at the left and going to the right side. |
| `"rightToLeft"` | The fence trigger raises a alarm when an object passes the start of the reference line beginning at the right and going to the left side. |

**Counting line**

A counting line trigger is a polyline that counts when an object crosses this line.

```bash
{  "type": "countingLine",  "countingDirection": <string>,  "vertices": \[    \[<x1>, <y1>\],    \[<x2>, <y2>\]    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `CountingDirection` | The direction in which the trigger will count a crossing object, defined by `getConfigurationCapabilities`. |

| countingDirection | Description |
| --- | --- |
| `"leftToRight"` | Triggers when an object passes the reference line from the left side of the line to the right side. |
| `"rightToLeft"` | Triggers when an object passes the reference line from the right side of the line to the left side. |

#### Scenario filters

The filters makes it possible to set up optional rules that excludes objects from detection and raising the alarm.

```bash
"filters": \[  {    "type": <string>,    ...  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `type` | See sections below. |

**Size percentage**

This high-pass filter excludes small objects based on their size in the view port. The size is defined as a fraction of the width and height of the total view area, measured in percent. Any object smaller than that will be filtered out and not raise an alarm.

-   Only one size filter is allowed, i.e. `sizePerspective` and `sizePercentage` can’t be enabled simultaneously.

```bash
{  "type": "sizePercentage",  "width": <int>,  "height": <int>}
```

| Parameter | Description |
| --- | --- |
| `width` | The horizontal upper limit of the filter size (in ONVIF coordinates). |
| `height` | The vertical upper limit of the filter size (in ONVIF coordinates). |

**Size perspective**

This high-pass filter excludes small objects based on their real-world size. The dimensions of these objects are defined in a virtual coordinate system calculated by using the perspective. For example, if the object’s calculated width and height is below this value, no alarm will be raised. The real-world height of the object if computed by applying the scenario perspective.

-   Only one size filter is allowed, i.e. `sizePerspective` and `sizePercentage` can’t be enabled simultaneously.
-   To configure a perspective filter, the scenario must point to a valid perspective. See [Scenario perspectives](#scenario-perspectives) for additional information.

```bash
{  "type": "sizePerspective",  "width": <int>,  "height": <int>}
```

| Parameter | Description |
| --- | --- |
| `width` | The horizontal upper limit of the filter size (in centimeters). |
| `height` | The vertical upper limit of the filter size (in centimeters). |

**Short-lived objects**

An object must be seen for a number of seconds before an alarm can be triggered, meaning if an object has been in the image longer than the filter time and then moves into the include area the scenario will immediately trigger the alarm. This allows brief objects and noise to be filtered out.

```bash
{  "type": "timeShortLivedLimit",  "time": <sec>}
```

| Parameter | Description |
| --- | --- |
| `time` | The waiting time, measured in seconds, until a detected object rase an alarm. |

**Swaying objects**

This filter sets the distance by which an object can move before raising an alarm. This setting is measured in percent of the image width and height. If configured correctly, swaying objects like leafs and trees can be filtered out.

```bash
{  "type": "distanceSwayingObject",  "distance": <int>}
```

| Parameter | Description |
| --- | --- |
| `distance` | The distance a detected object is allowed to travel before raising an alarm, measured in percent of the image. |

**Speed**

Speed filters are used to define speed ranges, in meters per seconds, for objects where the alarms are not triggered. Several speed filter instances can be created.

These filters can only be used when the scenario is configured with a secondary radar device.

```bash
{  "type": "speed",  "minSpeed": <float>,  "maxSpeed": <float>}
```

| Parameter | Description |
| --- | --- |
| `minSpeed/maxSpeed` | The ground speed between `minSpeed/maxSpeed` where the moving object won’t raise an alarm. |

**Exclude area**

This filter makes it possible to define areas of the image where alarms can’t be triggered. In contrast to other filters, it can create several exclude areas.

```bash
{  "type": "excludeArea",  "vertices": \[    \[<x1>, <y1>\],    \[<x2>, <y2>\]    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `vertices` | A list of vertices forming the exclude area polygon. |

#### Scenario perspectives

Lists the perspectives used by the scenario. Please note that this list does not define any perspectives in itself, but instead refers to the list of perspectives found in `data.perspectives`.

-   This scenario option is optional, but becomes mandatory if a perspective filter has been configured.

```bash
"perspectives": \[  <id>,  ...\]
```

| Parameter | Description |
| --- | --- |
| `perspectives` | A list of perspective IDs used in the scenario. |

#### Scenario object classifications

Configures the kind of objects that should raise an alarm. The `objectClassifications` structure is recursive since `subTypes` points to a new `type/subType` pair, allowing a tree structure to describe objects. A two-level depth is currently supported.

-   The `subType` parameter is only used if the camera supports classification subtypes. See [get configuration capabilities](#get-configuration-capabilities) for additional information.
-   The graphical SVG representation will draw the configured classes for detected objects.

info

An empty objectClassifications array implies that an alarm can be triggered on any detected motion. Filters can still be used to limit unwanted detections.

```bash
"objectClassifications": \[  {    "type": <string>,    "subTypes": \[      {        "type": <string>,        "subTypes": ...      }      ...    \]  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `type` | Identifies the object type. |
| `subTypes` | A list of sub classifiers for a `type` (optional). |

**Object classifications example**

The following example illustrates the recursive use of the `subTypes` parameters.

```bash
{    "type": "vehicle",    "subTypes": \[        {            "type": "bus"        },        {            "type": "car",            "subTypes": \[                {                    "type": "sedan"                },                {                    "type": "van"                }            \]        }    \]}
```

#### Scenario PTZ presets

It is possible to configure the scenarios on PTZ devices to track specific preset positions.

-   The following presets are optional. If no presets are defined and you are using a PTZ device, it will continue tracking objects as long as the camera itself isn’t moving.
-   These presets are not valid on a non-PTZ device.

```bash
"presets": \[  <id>,  ...\]
```

| Parameter | Description |
| --- | --- |
| `presets` | A list of PTZ preset positions that the scenario is tracking. See table below for valid values. |

| Preset | Description |
| --- | --- |
| `-2` | Tracking is always enabled, except when camera is moving. |
| `-1` | Tracking is done on all preset positions. No tracking is done if the PTZ device is not set to a preset. |
| `1` | Tracking on the `home` position of the PTZ device. |
| `2...` | Tracking on specific presets only. |

#### Crossline Counting specific configurations

Crossline Counting scenarios allow additional configurations to reset accumulated counts at midnight, or trigger an event at every N count.

```bash
{  "accumulatedCounts": {    ...  },  "passthroughConfiguration": {    ...  }}
```

Accumulated Counts

```bash
{  "timedResetEnabled": <boolean>}
```

| Parameter | Description |
| --- | --- |
| `timedResetEnabled` | Used if the timed reset for accumulated counts is enabled. |

Passthrough Configuration

```bash
{  "enabled": <boolean>,  "period": <int>}
```

| Parameter | Description |
| --- | --- |
| `enabled` | Indicates if the passthrough event is enabled. |
| `period` | Trigger an event for every `<period>` count. |

#### Occupancy In Area specific configurations

Occupancy In Area scenarios allow additional configurations to trigger an alarm when a specified number of objects are in the area for a specific amount of time.

```bash
{  "thresholdConfiguration": {    "enabled": <boolean>,    "triggerDelay": <int>,    "thresholds": \[      {        "level": <int>,        "type": <string>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `enabled` | Indicates if the threshold events are enabled. |
| `triggerDelay` | The number of seconds to wait after the configured threshold has been reached before the alarm is triggered. |
| `thresholds` | A list o thresholds that need to be reached before the alarm can be triggered. |
| `level` | The number of threshold objects. |
| `type` | Can be either `moreThan` or `lessThan` and triggers if the number of objects in the area are either more or less than the configured level. |

## Configuration capabilities

The parameter values in a configuration is limited by the capabilities of the camera on which the Object analytics application is running. These capabilities are read using the [get configuration capabilities](#get-configuration-capabilities) method. This means that a configuration sent by the `setConfiguration` will be validated by the application and any values outside the capabilities of the camera will result in an error.

All coordinates are in the ONVIF format if not otherwise specified.

### Overview

```bash
"data": {  "devices": \[    ...  \],  "filters": \[    ...  \],  "metadataOverlay": {    ...  },  "objectClassifications": {    ...  },  "perspective": {    ...  },  "scenarios": {    ...  },  "triggers": \[    ...  \],  "presets": {    ...  }}
```

The content of these fields is described in their own separate chapters:

-   [Devices](#devices-configuration-capabilities)
-   [Filters](#filters)
-   [Metadata overlay](#metadata-overlay-configuration-capabilities)
-   [Object classification](#object-classification)
-   [Perspective](#perspective)
-   [Scenarios](#scenarios-configuration-capabilities)
-   [Triggers](#triggers)
-   [Presets](#presets)

### Devices

A list of supported video devices in the camera on which the application is running.

```bash
"devices": \[  {    "id": <int>,    "type": <string>,    "imageIndex": <int>,    "name": <string>,    "rotation": <degree>,    "resolutions": \[      "<int>x<int>",      ...    \],    "tags": \[      <string>,      ...    \]  },  ...\]
```

| Parameter | Descriptions |
| --- | --- |
| `id` | The device ID. |
| `type` | A string describing the device type. |
| `imageIndex` | The image source index. |
| `name` | The device name. |
| `rotation` | The device rotation in the camera plane, measured in degrees. Valid values are 0, 90, 180 or 270. |
| `resolutions` | A list of supported camera resolutions in the format "`<width>x<height>`". |
| `tags` | A list of tags that indicates certain properties of the device. |

Device tags

| Tag | Description |
| --- | --- |
| `primary` | The primary device that should be used when a secondary device exists. |
| `secondary` | A secondary device that can only be used together with a primary device. |
| `fisheye` | A device equipped with a fisheye lens. |

### Filters

An array containing supported filters. The contents of a filter object depends on the `type` parameter.

```bash
"filters": \[  {    "type": <string>,    ...  },  ...\]
```

**Size percentage**

```bash
{  "type": "sizePercentage",  "minWidth": <int>,  "maxWidth": <int>,  "minHeight": <int>,  "maxHeight": <int>,  "defaultWidth": <int>,  "defaultHeight": <int>}
```

| Parameter | Description |
| --- | --- |
| `minWidth/maxWidth` | The min/max allowed width as a percentage of the image. |
| `minHeight/maxHeight` | The min/max allowed height as a percentage of the image. |
| `defaultWidth` | The default width as a percentage of the image. |
| `defaultHeight` | The default height as a percentage of the image. |

**Size perspective**

```bash
{  "type": "sizePerspective",  "minWidth": <int>,  "maxWidth": <int>,  "minHeight": <int>,  "maxHeight": <int>,  "defaultWidth": <int>,  "defaultHeight": <int>}
```

| Parameter | Description |
| --- | --- |
| `minWidth/maxWidth` | The min/max allowed virtual width, measured in centimeters. |
| `minHeight/maxHeight` | The min/max allowed virtual height, measured in centimeters. |
| `defaultWidth` | The default virtual width, measured in centimeters. |
| `defaultHeight` | The default virtual height, measured in centimeters. |

**Short-lived objects**

```bash
{  "type": "timeShortLivedLimit",  "minDistance": <int>,  "maxDistance": <int>,  "defaultDistance": <int>}
```

| Parameter | Description |
| --- | --- |
| `minTime/maxTime` | The min/max allowed time limit, measured in seconds. |
| `defaultTime` | The default time limit, measured in seconds. |

**Swaying objects**

```bash
{  "type": "distanceSwayingObject",  "minDistance": <int>,  "maxDistance": <int>,  "defaultDistance": <int>}
```

| Parameter | Description |
| --- | --- |
| `minDistance/maxDistance` | The min/max allowed value for the swaying distance as a percentage of the image. |
| `defaultDistance` | The default value for the swaying distance as a percentage of time image. |

**Speed**

```bash
{  "type": "speed",  "minSpeed": <float>,  "maxSpeed": <float>,  "defaultMinSpeed": <float>,  "defaultMaxSpeed": <float>}
```

| Parameter | Description |
| --- | --- |
| `minSpeed/maxSpeed` | The min/max allowed values for the speed filter, in m/s. |
| `defaultMinSpeed/defaultMaxSpeed` | The default ground speed filter range in m/s. |

**Exclude area**

```bash
{  "type": "excludeArea",  "minPosX": <real>,  "maxPosX": <real>,  "minPosY": <real>,  "maxPosY": <real>,  "minNbrVertices": <int>,  "maxNbrVertices": <int>,  "minNbrInstances": <int>,  "maxNbrInstances": <int>,  "defaultInstance": \[    \[<real>, <real>\],    \[<real>, <real>\],    \[<real>, <real>\],    \[<real>, <real>\]  \]}
```

| Parameter | Description |
| --- | --- |
| `minPosX, maxPosX, minPosY, maxPosY` | Any exclude area vertices must be located within the rectangle formed by these coordinates. |
| `minNbrVertices, maxNbrVertices` | The min/max number of vertices allowed in an exclude area polygon. |
| `minNbrAreas, maxNbrAreas` | The min/max number of exclude areas allowed by the filter. |
| `defaultInstance` | A reference exclude area in the shape of a rectangle. |

### Metadata overlay

```bash
"metadataOverlay": {  "minNbrActiveCameras": <int>,  "maxNbrActiveCameras": <int>,  "cameras": \[    {      "id": <int>,      "canDrawInSpecifiedResolutions": <boolean>,      "resolutions": \["<int>x<int>", "<int>x<int>", ...\]    },    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `minNbrActiveCameras` | The minimum number of cameras in a multichannel device that can be referenced in a metadata overlay. Please note that if the number of referenced cameras is 0, the overlay will be disabled. |
| `maxNbrActiveCameras` | The maximum number of cameras in a multichannel device that can use the feature. Please note that if the value is 0, the feature is not supported. |
| `cameras` | A list of camera objects describing the alarm overlay capabilities for each camera. |
| `id` | Same as the `cameras[i].id` parameter in the configuration. The corresponding camera value used when requesting a video using `media.amp`, starting at 1. |
| `canDrawInSpecifiedResolutions` | Determines if the camera has the capability to draw an alarm overly on a specified resolution. False means that the camera only supports drawing on all resolutions at once. |
| `resolutions` | A list of resolutions of the form `<width>x<height>` for which it is possible to use alarm overlay on a specific camera. |

### Object classification

This tree contains the supported classification types and their subtypes. The structure of this parameter matches the one in the configuration object. See [Scenario object classifications](#scenario-object-classifications) for additional information.

```bash
"objectClassifications": \[  {    "type": <string>,    "subTypes": \[      {        "type": <string>,        "subTypes": ...      }      ...    \]  },  ...\]
```

| Parameter | Description |
| --- | --- |
| `type` | A string identifying the object type. |
| `subTypes` | A list of sub classifiers for a defined type. |

### Perspective

```bash
"perspective": {  "minNbrBars": <int>,  "maxNbrBars": <int>,  "minNbrPerspectivesPerScenario": <int>,  "maxNbrPerspectivesPerScenario": <int>,  "minHeight": <int>,  "maxHeight": <int>,  "defaultHeight": <int>,  "minNbrPerspectives": <int>,  "maxNbrPerspectives": <int>}
```

| Parameter | Description |
| --- | --- |
| `minNbrBars/maxNbrBars` | The min/max number of allowed perspective bars. |
| `minNbrPerspectivesPerScenario/maxNbrPerspectivesPerScenario` | The min/max number of allowed perspectives per scenario. |
| `minHeight/maxHeight` | The min/max height of a perspective bar. |
| `defaultHeight` | The default height of a perspective bar. |
| `minNbrPerspectives/maxNbrPerspectives` | The min/max number of allowed perspectives in a configuration. |

### Scenarios

```bash
"scenarios": {  "minNbrScenariosPerCamera": <int>,  "maxNbrScenariosPerCamera": <int>,  "minNbrActiveDevices": <int>,  "maxNbrActiveDevices": <int>,  "minNbrDevices": <int>,  "maxNbrDevices": <int>,  "minLengthName": <int>,  "maxLengthName": <int>,  "defaultScenario": <string>,  "defaultDeviceId": <string>,  "supportedScenarios": \[<string>, <string>, ...\]  "alarmRates": \[<string>, <string>, ...\],  "defaultAlarmRate": <string>,  "accumulatedCounts": {    ...  },  "passthroughConfiguration": {    ...  },  "thresholdConfiguration": {    ...  }}
```

| Parameter | Description |
| --- | --- |
| `minNbrScenariosPerCamera/maxNbrScenariosPerCamera` | The min/max number of supported scenarios for each device or camera. |
| `minNbrActiveDevices/maxNbrActiveDevices` | The min/max total number of devices all devices are able to collectively use. |
| `minNbrDevices/maxNbrDevices` | The min/max number of devices one single scenario can use. |
| `minLengthName/maxLengthName` | The min/max length of the scenario name string. |
| `defaultScenario` | The default scenario type. |
| `defaultDeviceId` | A list device ID when a creating a default scenario. |
| `supportedScenarios` | A list of supported scenarios as strings. |
| `alarmRates` | A list of supported alarm rates as strings. |
| `defaultAlarmRate` | The default alarm rate. |

**Accumulated counts**

```bash
{  "defaultTimedResetEnabled": <boolean>}
```

| Parameter | Description |
| --- | --- |
| `defaultTimedResetEnabled` | Indicates if the timed reset for accumulated counts is active per default. |

**Passthrough configuration**

```bash
{  "defaultEnabled": <boolean>,  "minPeriod": <int>,  "maxPeriod": <int>}
```

| Parameter | Description |
| --- | --- |
| `defaultEnabled` | Indicates if the passthrough event is active per default. |
| `minPeriod/maxPeriod` | The min/max period that passthrough events can be triggered for. |

**Threshold configuration**

```bash
{  "defaultEnabled": <boolean>,  "minLevelWithMoreThanType": <int>,  "minTriggerDelay": <int>,  "defaultLevel": <int>,  "defaultType": <string>,  "minLevelWithLessThanType": <int>,  "defaultTriggerDelay": <int>,  "maxLevel": <int>,  "maxTriggerDelay": <int>}
```

| Parameter | Description |
| --- | --- |
| `defaultEnabled` | Indicates if the occupancy threshold events are active per default. |
| `minLevelWithMoreThanType/minLevelWithLessThanType` | The minimum threshold level when using either `MoreThan` or `LessThan` threshold type. |
| `minTriggerDelay/maxTriggerDelay` | The minimum/maximum configured delay for when events are triggered after reaching the threshold. |
| `defaultLevel` | The default threshold level. |
| `defaultType` | The default threshold type. |
| `defaultTriggerDelay` | The default trigger delay. |

### Triggers

This array contains the supported trigger types, while the contents of a trigger object depends on the `type` parameter.

```bash
"triggers": \[  {    "type": <string>,    ...  },  ...\]
```

#### Include area

```bash
{  "type": "includeArea",  "minPosX": <real>,  "maxPosX": <real>,  "minPosY": <real>,  "maxPosY": <real>,  "minNbrVertices": <int>,  "maxNbrVertices": <int>,  "minNbrInstances": <int>,  "maxNbrInstances": <int>,  "defaultInstance": \[    \[<real>, <real>\],    \[<real>, <real>\],    \[<real>, <real>\],    \[<real>, <real>\]  \]}
```

| Parameter | Description |
| --- | --- |
| `minPosX/maxPosX/minPosY/maxPosY` | Four values that defines the area in which creating an include area is valid. |
| `minNbrVertices/maxNbrVertices` | The min/max number of vertices that area can contain. |
| `minNbrInstances/maxNbrInstances` | The min/max allowed number of include areas in a scenario. |
| `defaultInstance` | An array of vertices defining a reference include area `[x1, y1], [x2, y2], ...` etc. |

#### Fence

```bash
{  "type": "fence",  "minPosX": <real>,  "maxPosX": <real>,  "minPosY": <real>,  "maxPosY": <real>,  "minNbrVertices": <int>,  "maxNbrVertices": <int>,  "minNbrInstances": <int>,  "maxNbrInstances": <int>,  "validAlarmDirections": \[<string>, ...\],  "defaultAlarmDirection": <string>,  "defaultInstance": \[    \[<real>, <real>\],    \[<real>, <real>\]  \]}
```

| Parameter | Description |
| --- | --- |
| `minPosX/maxPosX/minPosY/maxPosY` | Four values that defines the area in which creating a fence area is valid. |
| `minNbrVertices/maxNbrVertices` | The min/max number of vertices that fence polyline can contain. |
| `minNbrInstances/maxNbrInstances` | The min/max allowed number of fences in a scenario. |
| `validAlarmDirections` | A list of strings containing valid alarm directions. See [Scenario triggers](#scenario-triggers) for additional information. |
| `defaultAlarmDirection` | See [Scenario triggers](#scenario-triggers) for additional information. |
| `defaultInstance` | An array of vertices defining a reference fence polyline`[x1, y1], [x2, y2], ...` etc. |

#### Counting line

```bash
{  "type": "countingLine",  "minPosX": <real>,  "maxPosX": <real>,  "minPosY": <real>,  "maxPosY": <real>,  "minNbrVertices": <int>,  "maxNbrVertices": <int>,  "minNbrInstances": <int>,  "maxNbrInstances": <int>,  "validCountingDirections": \[<string>, ...\],  "defaultCountingDirection": <string>,  "defaultInstance": \[    \[<real>, <real>\],    \[<real>, <real>\]  \]}
```

| Parameter | Description |
| --- | --- |
| `minPosX/maxPosX/minPosY/maxPosY` | Four values that defines the area in which creating a counting line is valid. |
| `minNbrVertices/maxNbrVertices` | The min/max number of vertices the polyline can contain. |
| `minNbrInstances/maxNbrInstances` | The min/max allowed number of counting lines in a Crossline Counting Scenario. |
| `validAlarmDirections` | A list of strings containing valid counting directions. See [Scenario triggers](#scenario-triggers) for additional information. |
| `defaultAlarmDirection` | See [Scenario triggers](#scenario-triggers) for additional information. |
| `defaultInstance` | An array of vertices defining a reference polyline `[x1, y1], [x2, y2], ...` etc. |

#### Presets

This property is only included if the camera supports PTZ presets.

```bash
{  "minNbrPresetsPerScenario": <int>,  "maxNbrPresetsPerScenario": <int>,  "defaultPreset": <int>}
```

| Parameter | Description |
| --- | --- |
| `minNbrPresetsPerScenario/maxNbrPresetsPerScenario` | The min/max number of presets allowed in the scenario `presets` array. |
| `defaultPreset` | The default preset for the camera on which the application is running. See [Scenario PTZ presets](#scenario-ptz-presets) for additional information. |