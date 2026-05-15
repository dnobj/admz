---
title: Radar configuration
url: "https://developer.axis.com/vapix/radar/radar-configuration/"
category: vapix
subcategory: radar
sha256: 7d9a15346ab4f66f0ccbe73417d1256c0010a1e8424cfec022bcaf800def6695
scraped_at: "2026-01-09T15:22:07.078Z"
page_height: 145424
---

# Radar configuration

The VAPIX® Radar configuration API consists of methods compatible with Axis radar motion detectors. The API makes it possible to

-   define a guarded zone by setting up areas in where motion should be detected.
-   set up and configure several motion detection zones per channel.
-   configure area rules. The rules will determine when the device should trigger an event. A client application may listen to the event data stream to initiate new actions when an event is triggered.
-   configure settings that affect the detection and filtering algorithms to adapt the radar detector to different situations.

When radar profiles are set to road monitoring there are additional settings for lanes. These are used to improve detection and separation of vehicles.

## Overview

Radar configuration is split into two separate API:s containing their own methods and parameters:

The Control API uses `/axis-cgi/radar/control.cgi` as its communications interface and consists of methods that can configure the rules for event zones:

| Method | Description |
| --- | --- |
| `getConfiguration` | Query for the complete event configuration. |
| `setConfiguration` | Upload a complete event configuration. |
| `getConfigurationCapabilities` | Query for the configuration capabilities. |
| `getEnabled` | Query if the radar has been enabled. |
| `setEnabled` | Enable or disable the radar. |
| `getSupportedVersions` | Query for a list of supported API versions. |
| `sendAlarmEvent` | Send an alarm event for video management system testing purposes. |

The Analytics API uses `/axis-cgi/radar/radaranalytics.cgi` as its communications interface and consists of methods that handles the configuration of general parameters and application algorithms:

| Method | Description |
| --- | --- |
| `getConfigurationCapabilities` | Query for the configuration capabilities. |
| `setDetectionSensitivity` | Sets the detection sensitivity value suitable for the scene. |
| `getDetectionSensitivity` | Queries for the current sensitivity of the detection algorithm. |
| `setCoexistence` | Sets the radar’s coexistence mode. |
| `getCoexistence` | Queries for the current coexistence mode. |
| `setFrequencyChannel` | Sets the frequency channel to avoid interference between two radar sensors that are mounted close to each other. |
| `getFrequencyChannel` | Queries for the current frequency channel of the radar sensor. |
| `setGlobalFilters` | Sets the radar’s global filter configuration. |
| `getGlobalFilters` | Queries the current global filter configurations. |
| `setMountingHeight` | Sets the mounting height of the security radar. |
| `getMountingHeight` | Queries for the current mounting height. |
| `setMountingTilt` | Sets the mounting tilt of the security radar. |
| `getMountingTilt` | Queries for the current mounting tilt. |
| `getRadarDataStatus` | Queries for the current status of radar data reception. |
| `getSupportedVersions` | Queries for a list of the supported API versions. |
| `getLanes` | Queries for the current lane setup for one or multiple roads. |
| `setLanes` | Set up the lanes for one or multiple roads. |
| `getRadarProfile` | Queries for the currently used radar profile on the radar detector. |
| `setRadarProfile` | Set up a radar profile suitable for the scene. |

### Identification

-   **API Discovery**: `id=radar-analytics2` (radaranalytics.cgi)
-   **API Discovery**: `id=radar-control2` (control.cgi)

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Back up and restore configuration

This example will show you how to back up or restore your event configurations without having to set each individual parameter. It is possible to apply the same configuration to multiple devices as long as they have the same version of the Control API. Please note that this process may not be applied correctly when there is a difference between the major API versions and while it may work when only the minor version differs, some parameters will not.

1.  Request the current radar event configuration:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}
```

2.  Parse the response.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {...}}
```

3.  Restore the configuration settings by modifying the `data` field in the response and post it as `params`.

```bash
POST /axis-cgi/radar/control.cgi
```

Request

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setConfiguration",  "params": {...}}
```

### Configure all settings

This example will show you how to retrieve all parameters with their current configurations to change certain values and upload them back to the API.

1.  Request the current radar event configuration:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}
```

2.  Parse the response.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {...}}
```

3.  Modify the configuration received in the `data` field and upload the modified configuration as `params`. The JSON object will be modified according to [setConfiguration](#setconfiguration)

```bash
POST /axis-cgi/radar/control.cgi
```

Request

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setConfiguration",  "params": {...}}
```

### Test event functionality

This example will show you how to test a setup consisting of multiple radars with events from different radar profiles and check if they return the expected functions.

1.  Send an alarm event for profile 1.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "sendAlarmEvent",    "params": {        "profile": 1    }}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "sendAlarmEvent",    "params": {        "profile": 1    }}
```

1.  Parse the response. A successful response will contain an empty `data` object. A stateful alarm will raise a temporarily stateful alarm on the given profile.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "sendAlarmEvent",    "data": {}}
```

### Determine configuration capabilities

This example will show you how to determine the default values and limits of the configuration parameters that can be read with `getConfiguration` and set with `setConfiguration`. This will be useful when you wish to update the user interface without needing to hard code the values.

1.  Request the configuration capabilities of the API.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {...}}
```

### Enable the minimum speed filter

This example will show you how to detect objects based on their movement speed and track objects, such as fast-moving vehicles, by setting a minimum speed limit that the object must exceed to generate an alarm.

1.  Request the configuration capabilities of the API.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response. This will provide the capabilities in the `data` object.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    ...    "filters": \[      ...      {        "type": "minimumSpeedLimit",        "min": 0.0,        "max": 70.0,        "default": 69.444444444444443,        "defaultActive": true      }      ...    \]    ...  }}
```

3.  Request the current radar event configuration.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}
```

4.  Parse the current radar event configuration. The minimum speed filter will be set to `off` in this example.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {    ...    "profiles": \[      ...      "filters": \[        ...        {          "type": "minimumSpeedLimit",          "data": 0,          "active": false        }        ...      \]    \]    ...  }}
```

5.  Enable the minimum speed filter by setting its properties described by the configuration capabilities. The following example will show you when the configuration is assumed to be unchanged, with the exception for the values in the minimum speed filter.

```bash
POST /axis-cgi/radar/control.cgi
```

Request

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setConfiguration",  "params": {    ...    "profiles": \[      ...      "filters": \[        ...        {          "type": "minimumSpeedLimit",          "data": 5.0,          "active": true        }        ...      \]    \]    ...  }}
```

6.  Parse the response, which will contain an empty `data` response if the request is successful.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

### Set up a cross line

This example will show you how to generate an alarm event whenever an object crosses a pre-defined line in a specified direction.

1.  Request the current configuration capabilities.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response, which will provide the capabilities in the `data` object.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    ...    "profiles": \[      ...      {        "type": "crossLine",        "min": \[-1, -1\],        "max": \[1, 1\],        "minNbrVertices": 2,        "maxNbrVertices": 100000,        "minNbrInstances": 0,        "maxNbrInstances": 100000,        "alarmDirections": \[          "leftToRight",          "rightToLeft"        \],        "detfaultInstance": \[          \[-0.5, 0.0\],          \[0.5, 0.0\]        \],        "defaultAlarmDirection": "leftToRight"      }      ...    \]    ...  }}
```

3.  Request the current event configuration.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

4.  Parse the current radar event configuration.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {    ...    "profiles": \[\]    ...  }}
```

5.  Add a profile containing a cross line to the current configuration with the boundaries described by the configuration capabilities.

```bash
POST /axis-cgi/radar/control.cgi
```

Request

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setConfiguration",  "params": {    ...    "profiles": \[      {        "name": "Zone",        "uid": 1,        "channel": 1,        "filters": \[...\],        "triggers": \[          {            "type": "crossLine",            "alarmDirection": "leftToRight",            "data": \[              \[-1.0, 0.0\],              \[ 1.0, 0.0\]            \]          }        \]      }    \]    ...  }}
```

6.  Parse the response, which will contain an empty `data` object if the request is successful. This example shows what happens when the configuration is successfully set with the added crossline now in place, which will generate an alarm if an object crosses from left to right.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

### Adjust detection sensitivity

This example will show you how to adjust the detection sensitivity of the radar. This is useful in noisy environments as it will decrease the frequency of false alarms and can be used as a complement to zone specific and global filters that are configured by [setConfiguration](#setconfiguration) and [setGlobalFilters](#setglobalfilters).

1.  Request the configuration capabilities of the API.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response, which will contain the allowed detection sensitivity levels.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    ...    "detectionSensitivity": {      "values": \[        "low",        "medium",        "high"      \],      "default": "medium"    },    ...  }}
```

3.  Apply a new valid detection sensitivity value according to the capabilities.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "method": "setDetectionSensitivity",    "params": {        "value": "medium"    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "method": "setDetectionSensitivity",    "params": {        "value": "medium"    }}
```

4.  Parse the response.

Response

```bash
{    "apiVersion": "2.2",    "method": "setDetectionSensitivity",    "data": {}}
```

### Adjust frequency channel

This example will show you how to set up two radar detectors to different frequency channels to avoid interference between them.

1.  Check the current frequency channel for the first radar detector.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "params": {        "channel": 1    }}
```

2.  Parse the response to receive the current frequency channel.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "data": {        "automatic": false,        "value": 1    }}
```

3.  Check the current frequency channel for the second radar detector.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "params": {        "channel": 1    }}
```

4.  Parse the response to retrieve the current frequency channel.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getFrequencyChannel",    "data": {        "automatic": false,        "value": 1    }}
```

5.  Check the allowed values for the first radar detector.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

6.  Parse the response to receive the currently supported frequency channels.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    ...    "frequencyChannel": {      "minValue": 1,      "maxValue": 2,      "default": 1    },    ...  }}
```

7.  Set a new value for the first radar detector.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setFrequencyChannel",    "params": {        "value": 2,        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setFrequencyChannel",    "params": {        "value": 2,        "channel": 1    }}
```

8.  Parse the response to apply the chosen frequency channel.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setFrequencyChannel",    "data": {}}
```

### Mounting height and tilt of radar

This example will show you how to, after mounting the radar the radar detector on different heights and tilt angles, inform the radar and update the analytical algorithm to the changes.

1.  Check the currently configured mounting height.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingHeight",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingHeight",    "params": {        "channel": 1    }}
```

2.  Parse the response to receive the current mounting height and allowed values (in meter).

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingHeight",    "data": {        "value": 3.5    }}
```

3.  Set a new value for the mounting height.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingHeight",    "params": {        "value": 5.1,        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingHeight",    "params": {        "value": 5.1,        "channel": 1    }}
```

4.  Parse the response to apply the new mounting height.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingHeight",    "data": {}}
```

5.  Check the currently configured mounting tilt angle.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingTilt",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingTilt",    "params": {        "channel": 1    }}
```

6.  Parse the response to receive the current mounting tilt and if the current value comes from an automatic or manual measurement.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getMountingTilt",    "data": {        "automatic": false,        "value": 0    }}
```

7.  Set a new value for the mounting tilt angle.

```bash
POST /axis-cgi/radar/radaranalytics.cgi
```

The value of the field `automatic` will tell the application whether the measurement comes from an automatic source, such as an inclinometer, or a manual value. This will be defined by the `value` object.

Request

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingTilt",    "params": {        "automatic": false,        "value": 10,        "channel": 1    }}
```

8.  Parse the response to apply the new mounting tilt.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingTilt",    "data": {}}
```

### Get status of radar data

This example will show you how to test if the security radar is working correctly.

1.  Get the current radar data reception status.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus"}
```

2.  Parse the response to receive the current status as a boolean, where `true` signifies normal operation.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus",    "data": {        "value": true    }}
```

### Enable the swaying object filter

This example will show you how to reduce the number of false alarms from swaying objects such as trees or bushes. Unlike zone-specific filters that can be configured with `setConfiguration`, the swaying object filter is a global filter that requires a different setup.

1.  Get the current configuration of the swaying object filter.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters",    "params": {        "channel": 1    }}
```

2.  Parse the response to receive a list containing available global filters and their respective status.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters",    "data": {        "filters": \[            {                "type": "swayingObjectFilter",                "active": false            }        \]    }}
```

3.  Enable the swaying objects filter.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "params": {        "channel": 1,        "filters": \[            {                "type": "swayingObjectFilter",                "active": true            }        \]    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "params": {        "channel": 1,        "filters": \[            {                "type": "swayingObjectFilter",                "active": true            }        \]    }}
```

4.  Parse the response. The returning `data` object will be empty if the request was successful.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "data": {}}
```

### Determine support for automatic mounting tilt measurement

This example will show you how to check if your device supports automatic mounting tilt measurement or if the numbers needs to be added manually.

1.  Request the configuration capabilities of the application

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response. The value of `data.mountingTilt.automatic` will determine if your device supports automatic tilt measurement.

Response

```bash
{    "apiVersion": "2.2",    "method": "getConfigurationCapabilities",    "data": {        "coexistence": {            "maxNeighboringRadars": {                "values": \[1, 5\],                "default": 1            },            "group": {                "values": \[1, 2\],                "default": 1            }        },        "mountingHeight": {            "default": 3.5,            "maxValue": 100,            "minValue": 0.3        },        "mountingTilt": {            "automatic": true,            "default": 0,            "maxValue": 100,            "minValue": -100        }    }}
```

### Determine if the radar has been enabled

This example will show you how to check if the radar is enabled.

1.  Request the current status of the radar.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getEnabled"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getEnabled"}
```

2.  Parse the response, where the object `data.enabled` will specify whether the radar is enabled.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getEnabled",    "data": {        "enabled": true    }}
```

### Disable the radar

This example will show you how to temporarily disable the radar.

1.  Request that the radar is turned off.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setEnabled",    "params": {        "enabled": false    }}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setEnabled",    "params": {        "enabled": false    }}
```

2.  Parse the response, which will contain an empty `data` object if the request was successful.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setEnabled",    "data": {}}
```

### Set coexistence group

This example will show you how to install four to six radar detectors within the range of each other and how to make sure that they don’t interfere with each other.

1.  Find the maximum number of neighboring radars and coexistence groups.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response. This will return the currently supported maximum number of neighbors and coexistence groups. In this example, a number of neighbors will be between 1 and 5, and coexistence groups 1 and 2.

Response

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    ...    "coexistence": {      "maxNeighboringRadars": {        "values": \[          1,          5        \],        "default": 1      },      "group": {        "values": \[          1,          2        \],        "default": 1      }    },    ...  }}
```

3.  Find the current number of neighbors and the coexistence group.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getCoexistence"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getCoexistence"}
```

1.  Parse the response. This will return the current value of the maximum number of neighbors and coexistence group. In this example the numbers will be 2 and 1 by default.

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getCoexistence",    "data": {        "maxNeighboringRadars": {            "value": 2        },        "group": {            "value": 1        }    }}
```

5.  Set the maximum number of neighboring radars to the new value. The current radar should be set to one of the groups if the number of detectors are higher than 3.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setCoexistence",    "params": {        "maxNeighboringRadars": 4,        "group": 2    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setCoexistence",    "params": {        "maxNeighboringRadars": 4,        "group": 2    }}
```

6.  Parse the response, which will contain an empty data response if the request is successful.

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setCoexistence",    "data": {}}
```

### Set up a multiple line crossing

This example will show you how to generate an alarm event whenever an object crosses two pre-defined lines in a specified direction.

1.  Request the current configuration capabilities:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response, which will provide the capabilities in the `data` object:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "data": {        ...        "triggers": \[            ...            {                "type": "multipleLineCrossLine",                "min": \[-1, -1\],                "max": \[1, 1\],                "minNbrVertices": 2,                "maxNbrVertices": 100000,                "minNbrLines": 2,                "maxNbrLines": 2,                "minNbrInstances": 0,                "maxNbrInstances": 100000,                "alarmDirections": \["leftToRight", "rightToLeft"\],                "defaultInstance": \[                    \[-0.5, 0.0\],                    \[0.5, 0.0\]                \],                "defaultAlarmDirection": "leftToRight"            }            ...        \]        ...    }}
```

3.  Request the current event configuration:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

4.  Parse the current radar event configuration. No profiles will be set up in this example.

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration",    "data": {        ...        "profiles": \[\]        ...    }}
```

5.  Add a profile with multiple line crossings to the current configuration according to the boundaries described by the configuration capabilities.

```bash
POST /axis-cgi/radar/control.cgi
```

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setConfiguration",    "params": {        ...        "profiles": \[            {                "name": "Zone",                "uid": 1,                "channel": 1,                "filters": \[ ... \],                "triggers": \[                    {                        "type": "multipleLineCrossLine",                        "alarmDirection": "leftToRight",                        "data": \[                            \[                                \[ -1.0, 0.0 \],                                \[ 1.0, 0.0 \]                            \],                            \[                                \[ -1.0, 0.5 \],                                \[ 1.0, 0.5 \]                            \]                        \],                        "crossingTimeLimit": 10                    }                \]            }        \]        ...    }}
```

6.  Parse the response, which will contain an empty `data` object if the request was successful. In this example, the configuration was successfully set and the added crossline is now in place. This will generate an alarm if an if an object crosses it from left to right and fulfills the other filter criteria.

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

### Set lanes

This example will show you how to draw an outline of the lanes in the road(s) used when the radar is setup for road mode. Each lane can be named, enabled or disabled.

1.  Request the configuration capabilities of the API:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response, which will contain the allowed maximum number of lanes:

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "data": {        ...        "lanes": {            "maxNameLength": <number>,            "maxNodes": <number>        },        ...    }}
```

3.  Set the lane(s) name, enabled and nodes.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.4",    "context": "<client context>",    "method": "setLanes",    "params": {        "lanes": \[            {                "name": "Left lane",                "enabled": "true",                "nodes": \[                    \[-0.8, 0.8\],                    \[-0.8, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[-0.8, 0.8\]                \]            },            {                "name": "Middle lane",                "enabled": "false",                "nodes": \[                    \[0, 0.8\],                    \[0, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[0, 0.8\]                \]            }        \]    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.4",    "context": "<client context>",    "method": "setLanes",    "params": {        "lanes": \[            {                "name": "Left lane",                "enabled": "true",                "nodes": \[                    \[-0.8, 0.8\],                    \[-0.8, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[-0.8, 0.8\]                \]            },            {                "name": "Middle lane",                "enabled": "false",                "nodes": \[                    \[0, 0.8\],                    \[0, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[0, 0.8\]                \]            }        \]    }}
```

4.  Parse the response, which will contain an empty `data` object is the request was successful. In this example, the chosen lanes where all stored.

Response

```bash
{    "apiVersion": "2.4",    "context": "<client context>",    "method": "setLanes",    "data": {}}
```

### Get lanes

This example will show you how to check an outline of the lanes in the road(s) used when the radar is set up for road mode.

1.  Request the configuration capabilities of the API:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

2.  Parse the response, which will contain the allowed maximum lanes:

Response

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities",    "data": {        ...        "lanes": {            "maxNameLength": <number>,            "maxNodes": <number>        },        ...    }}
```

3.  Set the lane(s) name, status and nodes.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.4",    "context": "<client context>",    "method": "getLanes"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.4",    "context": "<client context>",    "method": "getLanes"}
```

4.  Parse the response, which will contain an empty `data` object if the request was successful. In this example, the chosen lanes will be stored.

Response

```bash
{    "apiVersion": "2.4",    "context": "<client context>",    "method": "getLanes",    "data": {        "lanes": \[            {                "name": "Lane-name 1",                "enabled": "true",                "nodes": \[                    \[-0.8, 0.8\],                    \[-0.8, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[-0.8, 0.8\]                \]            },            {                "name": "Lane-name 2",                "enabled": "false",                "nodes": \[                    \[0, 0.8\],                    \[0, 0.2\],                    \[-0.3, 0.2\],                    \[-0.3, 0.8\],                    \[0, 0.8\]                \]            }        \]    }}
```

### Adjust radar profile

This example will show you how to adjust a radar profile to suit a scene.

1.  Check allowed values for the radar profile.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "1.4",    "method": "getRadarProfile",    "params": {        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "method": "getRadarProfile",    "params": {        "channel": 1    }}
```

2.  Parse the response.

Successful response example

```bash
{    "apiVersion": "1.4",    "method": "getRadarProfile",    "data": {        "value": "area",        "allowedValues": \["area", "road"\]    }}
```

Error response example

```bash
{    "apiVersion": "1.4",    "method": "getRadarProfile",    "error": {        "errorCode": 8000,        "errorMsg": "Internal error"    }}
```

3.  Set a new value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "1.4",    "method": "setRadarProfile",    "params": {        "value": "area",        "channel": 1    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "method": "setRadarProfile",    "params": {        "value": "area",        "channel": 1    }}
```

4.  Parse the response.

Successful response example

```bash
{    "apiVersion": "1.4",    "method": "setRadarProfile",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.4",    "method": "setRadarProfile",    "error": {        "errorCode": 1000,        "errorMsg": "Invalid value 'test' for parameter 'value'"    }}
```

## Control API
### getConfiguration

This method should be used when you want request the current radar event configuration.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getConfiguration"` | The method that should be used. |

**Return value - Success**

Returns the current event configuration as a JSON response. The values **t**, **x** and **y** represents numbers.

For a complete description of each field in the configuration, see [Parameter description](#parameter-description).

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {    "channels": \[      {        "active": true,        "id": 1      }    \],    "profiles": \[      {        "name": "Zone 1",        "uid": 1,        "channel": 1,        "filters": \[          {            "type": "objectType",            "small": false,            "human": true,            "vehicle": true,            "unknown": true,            "active": false          },          {            "type": "timeShortLivedLimit",            "data": 2,            "active": true          },          {            "type": "excludeArea",            "data": \[\[x,y\], ..., \[x,y\]\],            "trackingPassingObjects": true          },          {            "type": "excludeArea",            "data": \[\[x,y\], ..., \[x,y\]\],            "trackingPassingObjects": false          }        \],        "triggers": \[          {            "type": "includeArea",            "data": \[\[x,y\], ..., \[x,y\]\]          }        \]      },      {...},      {...},      {...}    \],    "configurationStatus": 0  }}
```

**Response if the radar supports multiple channels:**

info

Channel specific properties are set with `data.channels`. Please note that each profile has its own individual settings and refers to a channel id with the`data.profiles[j].channel` property.

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfiguration",  "data": {    "channels": \[      {"active": true, "id": 1},      {"active": false, "id": 2},      {"active": false, "id": 3},      {"active": false, "id": 4}    \],    "profiles": \[      {        "name": "Zone 1",        "uid": 1,        "channel": 1,        "filters": \[          {            "type": "objectType",            "small": false,            "human": true,            "vehicle": true,            "unknownType": true,            "active": false          },          {            "type": "timeShortLivedLimit",            "data": 2,            "active": true          },          {            "type": "excludeArea",            "data": \[\[x,y\], ..., \[x,y\]\],            "trackingPassingObjects": true          },          {            "type": "excludeArea",            "data": \[\[x,y\], ..., \[x,y\]\],            "trackingPassingObjects": false          }        \],        "triggers": \[          {            "type": "includeArea",            "data": \[\[x,y\], ..., \[x,y\]\]          }        \]      },      {        "name": "Zone 2",        "uid": 2,        "channel": 3,        "filters": \[...\],        "triggers": \[...\]      },      {...},      {...},      {...}    \],    "configurationStatus": 0  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfiguration"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "<string>",  "method": "getConfiguration",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfiguration"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### setConfiguration

This method should be used when you want to apply a new event configuration.

**Modify specific properties**

The following examples will change the values of a JSON event configuration to make it perform a specific action. In these examples, `i` represents an index in the profile array.

**Modify include area:**

The profile’s include area consists of `n` connected straight lines that connects the points `[[x0,y0], ..., xn,yn]]`, and can be modified by changing the property `params.profiles[i].triggers` to:

```bash
"triggers": \[  ...  {    "type": "includeArea",    "data": \[\[x0,y0\], ..., \[xn,yn\]\]  },  ...\]
```

**Modify exclude areas:**

The profile’s exclude area consists of `n` connected straight lines that connects the points `[[x0,y0], ..., xn,yn]]`, and can be modified by changing the property `params.profiles[i].filters` to:

```bash
"filters": \[  ...  {    "type": "excludeArea",    "data": \[\[x0,y0\], ..., \[xn,yn\]\],    "trackPassingObjects": false  }  ...\]
```

Please note that the exclude area object should be removed when the exclude area is not in use.

**Set short-lived object filter:**

To change the short-lived object filter value to `t` seconds you should start by modifying the property `params.profiles[i].filters` to:

```bash
"filters": \[  ...  {    "type": "timeShortLivedLimit",    "data": t,    "active": true  },  ...\]
```

**Set object type object filter:**

In order to change the object type filter values to include only humans you should start by modifying `params.profiles[i].filters` to:

```bash
"filters": \[  ...  {    "type": "objectType",    "small": false,    "human": true,    "vehicle": false,    "unknown": false,    "active": true  },  ...\]
```

**Request**

-   **Security level**: Administrator

```bash
POST /axis-cgi/radar/control.cgi
```

Request body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setConfiguration",  "params": {    "channels": \[      {        "active": true,        "id": 1      }    \],    "profiles": \[      {        "name": "Profile 1",        "uid": 1,        "channel": 1,        "filters":        \[          {"type": "objectType", "small": false, "human": true, "vehicle": true, "unknownType": true, "active": false},          {"type": "timeShortLivedLimit", "data": t, "active": true},          {"type": "excludeArea", "data": \[\[x,y\], ..., \[x,y\]\], "trackPassingObjects": true},          {"type": "excludeArea", "data": \[\[x,y\], ..., \[x,y\]\], "trackPassingObjects": false}        \],        "triggers": \[          {"type": "includeArea", "data": \[\[x,y\], ..., \[x,y\]\]}        \],      },      {...},      {...},      {...}    \]  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context=<string>` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method="setConfiguration"` | String | The method that should be used. |
| `params` | JSON object | Container for a complete event configuration. To remove a profile, remove that profile object from the `params.profiles` array. For a complete description of each field in the configuration, see [Parameter description](#parameter-description). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setConfiguration",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that was used in the request. |
| `context=<string>` | String | The context set by the user in the request (optional). |
| `method="setConfiguration"` | String | The requested method. |
| `data` | JSON object | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "<string>",  "method": "setConfiguration",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setConfiguration"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### getConfigurationCapabilities

This method should be used when you want to request the boundaries and default API values.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getConfigurationCapabilities"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data":{    "filters": \[      {        "type": "excludeArea",        "min": \[-1.0, -1.0\],        "max": \[1.0, 1.0\],        "minNbrVertices": 3,        "maxNbrVertices": ...,        "defaultInstance": \[...\],        "defaultTrackPassingObjects": ...      },      {        "type": "timeShortLivedLimit", ...        "min": ...,        "max": ...,        "default": ...,        "defaultActive": ...      },      {        "type": "minimumSpeedLimit", ...        "min": ...,        "max": ...,        "default": ...,        "defaultActive": ...      },      {        "type": "maximumSpeedLimit", ...        "min": ...,        "max": ...,        "default": ...,        "defaultActive": ...      },    \],    "triggers": \[      {        "type": "crossLine",        "min": \[-1.0, -1.0\],        "max": \[1.0, 1.0\],        "minNbrVertices": 2,        "maxNbrVertices": ...,        "minNbrInstances": ...,        "maxNbrInstances": ...,        "validAlarmDirection": \[...\],        "defaultAlarmDirection": ...      }    \],    "profiles": {      "minNbrProfilesPerChannel": ...,      "maxNbrProfilesPerChannel": ...,      "minLengthName": ...,      "maxLengthName": ...    },    "radarProfile": {        "values": \[            "area",            "road"        \],        "default": "area"    }  }}
```

See [Parameter description](#parameter-description) for a complete description of all parameters in the response.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "<string>",  "method": "getConfigurationCapabilities",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfigurationCapabilities"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### getEnabled

This method should be used when you want to determine if the radar is currently enabled or disabled.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getEnabled"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getEnabled"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context=<string>` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method="getEnabled"` | String | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getEnabled",  "data": {    "enabled": <true | false>  }}
```

See [Parameter description](#parameter-description) for a complete description of all parameters in the response.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "<string>",  "method": "getEnabled",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getEnabled"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### setEnabled

This method should be used when you want to enable or disable the radar.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setEnabled",  "params": {    "enabled": <true | false>  }}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setEnabled",  "params": {    "enabled": <true | false>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method` | String | The method that should be used. |
| `params.enabled=<true | false>` | Boolean | Container for the method specific parameters that specifies if the radar should be enabled (`true`) or disabled (`false`). |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setEnabled",    "data": {}}
```

See [Parameter description](#parameter-description) for a complete description of all parameters in the response.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": <client context>,  "method": "setEnabled",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setEnabled"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### getSupportedVersions

This method should be used when you want to create a list containing all supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "context": "<client context>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "context": "<client context>",    "method": "getSupportedVersions"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `context=<string>` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | String | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

See [Parameter description](#parameter-description) for a complete description of all parameters in the response.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": <client context>,  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### sendAlarmEvent

This method should be used when you want to send a stateful alarm event for a specific `uid` profile. Stateful alarm events are active for a few seconds, and the response message will be returned immediately. This is useful when you want to check if a configuration has been correctly set (e.g. it starts the recording) as all profile-related events will be sent.

info

Profile events will be sent regardless of their current state.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "sendAlarmEvent",  "params": {    "profile": <uid>  }}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "sendAlarmEvent",  "params": {    "profile": <uid>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context=<string>` | String | The user sets this value and the application echoes it back in the response (optional). |
| `method=<sendAlarmEvent>` | String | The method that should be used. |
| `data.profile=<uid>` | JSON object | Specifies the profile that should raise an alarm. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "sendAlarmEvent",    "data": {}}
```

See [Parameter description](#parameter-description) for a complete description of all parameters in the response.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "<string>",  "method": "sendAlarmEvent",  "error": {    "code": <integer error code>,    "message": <error message>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="sendAlarmEvent"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-control-api) for a complete list of potential errors.

### Parameter description

The structure of a configuration object is the same for both the `data` object in the response for `getConfiguration` and the `params` object requested when using `setConfiguration`. This is true for both single and multichannel products, where the `channels` objects will mirror the different VAPIX channel properties.

#### Example configuration

The following example configuration will be further described in [Parameter description table](#parameter-description-table-control-api)

```bash
{  "channels": \[    {      "active": true,      "id": 1    }  \],  "profiles": \[    {      "name": "<client nice-name>",      "uid": <uid>,      "channel": 1,      "filters": \[        {"type": "objectType", "small": false, "human": true, "vehicle": true, "unknown": true, "active": false},        {"type": "timeShortLivedLimit", "data": 2, "active": true},        {"type": "excludeArea", "data": \[\[x,y\], ..., \[x,y\]\], "trackPassingObjects": false},        {"type": "excludeArea", "data": \[\[x,y\], ..., \[x,y\]\], "trackPassingObjects": false}      \],      "triggers": \[        {"type": "includeArea", "data": \[\[x,y\], ..., \[x,y\]\]}      \]    },    {...},    {...},    {...}  \],  "configurationStatus": 0}
```

#### Parameter description table

All parameters and properties are mandatory unless otherwise specified. Please note that exclusion filters are optional.

The `channels` object contains general information for all profiles using that channel.

| Property | Type | Default value | Valid values | Description |
| --- | --- | --- | --- | --- |
| `channels[i].active` | Boolean | true | true, false | Active profiles for the channel are set to `true`. Inactive profiles are set to `false`. |
| `channels[i].id` | Integer | 1 | 1, ..., #channels | The channel value applied when requesting a video by using `media.amp`. Note that it starts at 1. |

The `profiles` object contains information for each individual profile.

| Property | Type | Default value | Valid value | Description |
| --- | --- | --- | --- | --- |
| `profiles[j].name` | String | "Profile <uid>" | <string> | A unicode string found in the nice name of the event, and visible to the end user in the action rule list. |
| `profiles[j].channel` | Integer | 1 | 1, 2, 3, ..., | Should match the `id` of the corresponding channel in `channels`. |
| `profiles[j].uid` | Integer | 1 | 1, 2, 3, ..., | A unique profile id. |
| `profiles[j].filters` | Array |  |  | An array of exclusion filters. |
| `profiles[j].triggers` | Array |  |  | An array of triggers. |
| `profiles[j].minimumTriggerDuration` | Float |  | 0, ... | Optional. The minimum time that the profile should remain active after t has been triggered. |

All exclusion filters from `profiles[j].filters` have a similar structure and are all optional. A filter not present in the `profiles[].filters` array during the configuration will be created with the default values specified in [getConfigurationCapabilities](#get-configuration-capabilities-control-api).

The properties of the `objectType` filter each represent a certain type of object. For example, setting `vehicle` to `false` will let vehicles enter the alarm area without triggering an event. The object type `small` include small animals such as rodents, small dogs and birds, while `unknown` includes everything not applicable by the other types.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | String | `objectType` | Specifies the exclusion filter type. |
| `profiles[j].filters[k].active` | Boolean | true, false | Specifies if the filter is active. |
| `profiles[j].filters[k].small` | Boolean | true, false | Specifies if small objects should generate events. Default value is `true`. |
| `profiles[j].filters[k].human` | Boolean | true, false | Specifies if humans should generate events. Default value is `true`. |
| `profiles[j].filters[k].vehicle` | Boolean | true, false | Specifies if vehicles should generate events. Default value is `true`. |
| `profiles[j].filters[k].unknown` | Boolean | true, false | Specifies if unknown objects should generate events. Default value is `true`. |

The `timeShortLivedLimit` filter reflects the number of seconds an object is tracked before raising an alarm. The alarm will be temporarily suppressed If the object does something that could trigger an alarm before the set time has passed, but if the object is still tracked after the set time has expired, the alarm will be raised. Should the object disappear from the radar view before the set time expires, the alarm will not be raised.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | String | `timeShortLivedLimit` | Specifies the type of exclusion filter. |
| `profiles[j].filters[k].active` | Boolean | true, false | Specifies if the filter is active. |
| `profiles[j].filters[k].data` | Integer | 1, ..., | Seconds alive before generating an event. |

The `excludeArea` filter specifies an exclude area where objects doesn’t generate any events. An exclude area is made out of an array of points `[[x0,y0], ..., [xn,yn]]`, and the coordinates are normalized to the size of the image so that the visible view spans from -1 to 1 in both the horizontal and vertical direction.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | String | `excludeArea` | Specifies the type of exclusion filter. |
| `profiles[j].triggers[k].data` | `[[x0,y0], ..., [xn,yn]]` | \- 1, ..., 1 | The exclude area polygon. |
| `profiles[j].filters[k].trackPassingObjects` | boolean | true, false | Enable passing objects tracking. |

The `minimumSpeedLimit` filter specifies the minimum speed that an object must travel at to generate an event.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | String | `minimumSpeedLimit` | Specifies the exclusion filter type. |
| `profiles[j].filters[k].active` | Boolean | true, false | Specifies if the filter is active. |
| `profiles[j].filters[k].data` | Float | 0, ..., (Maximum valid value can be obtained from `getConfigurationCapabilities`) | The minimum speed in meters per second. |

The `maximumSpeedLimit` filter specifies the maximum speed that an object must travel at to generate an event.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].filters[k].type` | String | `maximumSpeedLimit` | Specifies the exclusion filter type. |
| `profiles[j].filters[k].active` | Boolean | true, false | Specifies if the filter is active. |
| `profiles[j].filters[k].data` | Float | 0, ..., (Maximum valid value can be obtained from `getConfigurationCapabilities`) | The maximum speed in meters per seconds. |

The only trigger types are `crossLine` and `includeArea`, which means that the array `profiles[j].triggers` should contain no more than one cross line or one include area.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].triggers[0].type` | String | `crossLine` | Specifies that the trigger is a cross line. |
| `profiles[j].triggers[0].alarmDirection` | String | `leftToRight` `rightToLeft` | Specifies the direction in which an object must cross the cross line to generate an event. |
| `profiles[j].triggers[0].data` | `[[x0,y0], ..., [xn,yn]]` | \-1, ..., 1 | A cross line is described as an array of points `[[x0, y0], ..., [xn, yn]]` and the unit are normalized to the size of the image so that the visible view spans from -1 to 1 in both the horizontal and vertical direction. |

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].triggers[0].type` | String | `multipleLineCrossLine` | Specifies that the trigger is multiple line crossing. |
| `profiles[j].triggers[0].alarmDirection` | String | `leftToRight`, `rightToLeft` | Specifies the direction in which an object must cross the lines to generate an event. |
| `profiles[j].triggers[0].data` | `[ [ [x, y], . . . , [x, y] ], [ [x, y], . . . , [x, y] ], . . . ]` | \-1, .., 1 | A multiple line crossing is described as an array of lines, where each line has the format \[\[x0,y0\], ..., \[xn,yn\]\]. The coordinates are normalized to the size of the image, so that the visible view spans from -1 to 1 in both the horizontal and vertical direction. |
| `profiles[j].triggers[0].crossingTimeLimit` | float | 0 | The maximum time in seconds that an object can take to cross the two lines before it raises an alarm. A value of zero will disable to the time limit. |

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `profiles[j].triggers[0].type` | String | `includeArea` | Specifies that it is an include area. |
| `profiles[j].triggers[0].data` | `[[x0, y0], ..., [xn, yn]]` | \-1, ..., 1 | An include area is described as an array of points `[[x0, y0], ..., [xn, yn]]` and the unit are normalized to the size of the image, so that the visible view spans from -1 to 1 in both the horizontal and vertical direction. |

| Property | Type | Description |
| --- | --- | --- |
| `configurationStatus` | Integer | This property is read-only and ignored by `setConfiguration`. The initial value is 0, which indicates a default configuration where no configuration has been set. Each time a configuration is set, the value is increased by 1 up to the maximum number of 2 147 483 647, after which the value will be reset to 1. |

#### Configuration capabilities parameter description

The following tables will describe the parameters found in [getConfigurationCapabilities](#get-configuration-capabilities-control-api).

**Filters**

excludeArea

| Property | Type | Description |
| --- | --- | --- |
| `min` | \[int, int\] | An array \[xPos, yPos\] specifying the minimum allowed values in the x- and y-direction for the area. |
| `max` | \[int, int\] | An array \[xPos, yPos\] specifying the maximum allowed values in the x- and y- direction for the area. |
| `minNbrVertices` | Integer | The minimum number of vertices the area may contain. |
| `maxNbrVertices` | Integer | The maximum number of vertices the area may contain. |
| `defaultInstance` | \[ \[ x,y\], ..., \[x,y \] \] | The default exclude area contains an array of arrays that specifies the default vertices. |
| `defaultTrackPassingObjects` | boolean | The default value of `trackPassingObjects`. |

objectType

| Property | Type | Description |
| --- | --- | --- |
| `default` | List of strings | The default object types that will generate an alarm when the filter is active. The strings in this array correspond to the keys of the `objectType` filter configuration object found in [Parameter description table](#parameter-description-table-control-api). |
| `defaultActive` | Boolean | Specifies if the filter is active by default. |

timeShortLivedLimit

| Property | Type | Description |
| --- | --- | --- |
| `min` | int | The minimum allowed time in seconds. |
| `max` | int | The maximum allowed time in seconds. |
| `default` | int | The default time in seconds. |
| `defaultActive` | Boolean | Specifies if the filter is active by default. |

minimumSpeedLimit

| Property | Type | Description |
| --- | --- | --- |
| `min` | Float | The minimum allowed speed in meters per second. |
| `max` | Float | The maximum allowed speed in meters per second. |
| `default` | Float | The default speed in meters per second. |
| `defaultActive` | Boolean | Specifies if the filter is active by default. |

maximumSpeedLimit

| Property | Type | Description |
| --- | --- | --- |
| `min` | Float | The minimum allowed speed in meters per second. |
| `max` | Float | The maximum allowed speed in meters per second. |
| `default` | Float | The default speed in meters per second. |
| `defaultActive` | Boolean | Specifies if the filter is active by default. |

**Triggers**

_crossLine_

| Property | Type | Description |
| --- | --- | --- |
| `min` | \[int, int\] | An array \[xPos, yPos\] with the minimum allowed values in the x- and y-direction for the cross line. |
| `max` | \[int, int\] | An array \[xPos, yPos\] with the maximum allowed values in the x- and y-direction for the cross line. |
| `minNbrVertices` | int | The minimum number of vertices the cross line may contain. |
| `maxNbrVertices` | int | The maximum number of vertices the cross line may contain. |
| `minNbrInstances` | int | The minimum allowed number of cross lines. |
| `maxNbrInstances` | int | The maximum allowed number of cross lines. |
| `validAlarmDirections` | List of strings | The possible directions that the cross line can have. |
| `defaultInstance` | `[[x, y], ..., [x, y]]` | The default cross line containing an array of arrays specifying the default vertices. |
| `defaultAlarmDirection` | String | The default alarm direction for a cross line. |

_multipleLineCrossLine_

| Property | Type | Description |
| --- | --- | --- |
| `min` | \[int, int\] | An array \[xPos, yPos\] with the minimum allowed values in the x- and y-direction for each cross line. |
| `max` | \[int, int\] | An array \[xPos, yPos\] with the maximum allowed values in the x- and y-direction for each cross line. |
| `minNbrVertices` | int | The minimum number of vertices the cross line can contain. |
| `maxNbrVertices` | int | The maximum number of vertices the cross line can contain. |
| `minNbrLines` | int | The minimum number of cross lines the trigger can contain. |
| `maxNbrLines` | int | The maximum number of cross lines the trigger can contain. |
| `minNbrInstances` | int | The minimum allowed number of multiple-line cross lines. |
| `maxNbrInstances` | int | The maximum allowed number of multiple-line cross lines. |
| `defaultCrossingTimeLimit` | float | The default value for the crossing time limit. |
| `minCrossingTimeLimit` | float | The minimum allowed value for the crossing time limit. |
| `maxCrossingTimeLimit` | float | The maximum allowed value for the crossing time limit. |
| `validAlarmDirections` | list of strings | The possible directions that the cross line can have. |
| `defaultInstance` | `[ [ [x,y], . . . , [x,y] ] ]` | The default double cross line, consisting of an array of lines. |
| `defaultAlarmDirections` | string | The default alarm direction for a multiple-line cross line. |

_includeArea_

| Property | Type | Description |
| --- | --- | --- |
| `min` | \[int, int\] | An array. \[xPos, yPos\] with the minimum allowed values in the x- and y-direction for the area. |
| `max` | \[int, int\] | An array. \[xPos, yPos\] with the maximum allowed values in the x- and y-direction for the area. |
| `minNbrVertices` | int | The minimum number of angles the area may contain. |
| `maxNbrVertices` | int | The maximum number of angles the area may contain. |
| `minNbrInstances` | int | The minimum allowed number of areas. |
| `maxNbrInstances` | int | The maximum allowed number of areas. |
| `defaultInstance` | `[[x, y], ..., [x, y]]` | The default include area containing an array of arrays specifying the default angles. |

**Profiles**

| Property | Type | Description |
| --- | --- | --- |
| `minNbrProfilesPerChannel` | int | The minimum number of profiles a configuration may contain. |
| `maxNbrProfilesPerChannel` | int | The maximum number of profiles a configuration may contain. |
| `minLengthName` | int | The minimum number of characters for a profile name. |
| `maxLengthName` | int | The maximum number of characters for a profile name. |
| `minMinimumTriggerDuration` | float | The minimum value for `minimumTriggerDuration`. |
| `maxMinimumTriggerDuration` | float | The maximum value for `minimumTriggerDuration`. |
| `defaultMinimumTriggerDuration` | float | The default value for `minimumTriggerDuration` if it is omitted. |

### General error codes

This table lists the general errors that can occur for any method in the Control API.

| Code | Description |
| --- | --- |
| `1000` | Internal error. |
| `2000` | The requested API version is not supported by this implementation. |
| `2001` | The format of a provided JSON parameter was incorrect. |
| `2002` | Conflicting input parameters, e.g. two profiles with the same uid. |
| `2003` | A mandatory input parameter was not found in the input. |
| `2004` | An input parameter has an incorrect type. |
| `2005` | An unexpected parameter was passed. |
| `8000` | The requested method is not supported by this implementation. |
| `8003` | The provided input was not well-formed JSON. |

## Analytics API
### getConfigurationCapabilities

This method should be used when you want to request capabilities information from the Analytics API.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getConfigurationCapabilities"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "data": {    "coexistence": {      "maxNeighboringRadars": {        "values": \[<integer>, ...\],        "default": <integer>      },      "group": {        "values": \[<integer>, ...\],        "default": <integer>      }    },    "frequencyChannel": {      "automatic": <true | false>,      "values": \[<integer | string>, ...\],      "default": <integer | string>    },    "mountingHeight": {      "minValue": <number>,      "maxValue": <number>,      "default": <number>    },    "mountingTilt": {      "minValue": <number>,      "maxValue": <number>,      "automatic": <true | false>,      "default": <number>    },    "lanes": {        "maxNameLength": <number>,        "maxNodes": <number>    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfigurationCapabilities"` | The requested method. |
| `data.coexistence.maxNeighboringRadars.default=<integer>` | _Present only if the device supports coexistence._ The default value of the coexistence mode. |
| `data.coexistence.maxNeighboringRadars.values=<integer>` | _Present only if the device supports coexistence._ The allowed values of the coexistence mode. |
| `data.coexistence.group.default=<integer>` | _Present only if the device supports coexistence._ The default value of the coexistence group. |
| `data.coexistence.group.values=<integer>` | _Present only if the device supports coexistence._ The allowed values of the coexistence group. |
| `data.frequencyChannel.automatic=<true | false>` | _Present only if the device supports multiple frequency channels._ Indicates whether the device supports automatic frequency channel selection. Can be either `true` or `false`. |
| `data.frequencyChannel.default=<integer>` | The default value of the frequency channel. |
| `data.frequencyChannel.values=<integer | string>` | The allowed values for the frequency channel. |
| `data.mountingHeight.default=<number>` | The default value of the mounting height. |
| `data.mountingHeight.minValue=<number>` | The smallest allowed mounting height value. |
| `data.mountingHeight.maxValue=<number>` | The largest allowed mounting height value. |
| `data.mountingTilt.automatic=<boolean>` | Indicates whether the device supports automatic mounting tilt measurement. Can be either `true` or `false`. |
| `data.mountingTilt.default=<number>` | The default value of the mounting tilt angle. |
| `data.mountingTilt.minValue=<number>` | The smallest allowed mounting tilt angle value. |
| `data.mountingTilt.maxValue=<number>` | The largest allowed mounting tilt angle value. |
| `data.lanes.maxNameLength=<number>`  
_Only present if the device supports lanes_ | The maximum length of the name string for a lane that can be set with the [setLanes](#set-lanes) method. |
| `data.lanes.maxNodes=<number>`  
_Only present if the device supports lanes_ | The maximum number of nodes allowed to describe a lane polygon that can be set with the [setLanes](#set-lanes) method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "context": "<client context>",  "method": "getConfigurationCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfigurationCapabilities"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setDetectionSensitivity

This method should be used when you want to set the detection sensitivity of the radar. A higher detection sensitivity increases the detection probability, but could also lead to more false alarms.

Radar detectors with several radar channels need to use the channel parameter to specify which channel to set the detection sensitivity for. If no channel parameter is specified all radar channels will use their default detection sensitivity.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setDetectionSensitivity",  "params": {    "value": <string>,    "channel": <integer>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setDetectionSensitivity",  "params": {    "value": <string>,    "channel": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setDetectionSensitivity"` | The method that should be used. |
| `params.value=<string>` | The detection sensitivity that should be used. Allowed values are provided by [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api). |
| `params.channel=<integer>` | Specify the radar channel that should have its detection sensitivity set. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setDetectionSensitivity",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setDetectionSensitivity"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setDetectionSensitivity",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setDetectionSensitivity"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getDetectionSensitivity

This method should be used when you want to check the current detection sensitivity of the radar.

Radar detectors with several radar channels need to use the channel parameter to specify which channel it should operate on. If no channel parameter is specified the radar will return its detection sensitivity.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getDetectionSensitivity",  "params": {    "value": "high",    "allowedValues": \["low", "medium", "high"\],    "channel": <integer>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getDetectionSensitivity",  "params": {    "value": "high",    "allowedValues": \["low", "medium", "high"\],    "channel": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getDetectionSensitivity"` | The method that should be used. |
| `param.channel=<integer>` | Specify the radar channel that should have its detection sensitivity returned. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getDetectionSensitivity",    "data": {        "value": "high"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getDetectionSensitivity"` | The requested method. |
| `data.value=<string>` | The current detection sensitivity. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getDetectionSensitivity",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getDetectionSensitivity"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setCoexistence

This method should be used when you want to set the coexistence mode of the radar. In cases where multiple radar detectors are within each others’ active area, you need to set an appropriate coexistence mode that will reduce the risk of the radar detectors interfering with each other.

info

This method is only available if the coexistence key is present in the response retrieved from getConfigurationCapabilities.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setCoexistence",  "params": {    "maxNeighboringRadars": <maximum number of neighboring radars>,    "channel": <radar channel>,    "group": <coexistence group>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setCoexistence",  "params": {    "maxNeighboringRadars": <maximum number of neighboring radars>,    "channel": <radar channel>,    "group": <coexistence group>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setCoexistence"` | The method that should be used. |
| `params.maxNeighboringRadars=<integer>` | The maximum number of neighboring radars. |
| `params.channel=<integer>` | Specifies on which radar channel the coexistence mode should be set (optional). All radar channels will have their frequency channel set to `params.value` if this parameter is omitted. |
| `params.group=<integer>` | Specifies the group a radar belong to (optional). This parameter is optional if the maximum number of neighboring radars are 2 or fewer. The radar will belong to group 1 if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setCoexistence",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setCoexistence"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setCoexistence",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setCoexistence"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getCoexistence

This method should be used when you want to check the current coexistence mode of the radar sensor.

info

This method is only available if the coexistence key is present in the response retrieved from getConfigurationCapabilities.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getCoexistence",  "params": {    "channel": <radar channel>,  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getCoexistence",  "params": {    "channel": <radar channel>,  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getCoexistence"` | The method that should be used. |
| `params.channel=<integer>` | Specifies the radar channel whose coexistence mode should be returned in the response. The coexistence mode for radar channel 1 will be returned if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getCoexistence",    "data": {        "maxNeighboringRadars": {            "value": 1        }    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getCoexistence"` | The requested method. |
| `data.maxNeighboringRadars` | The maximum number of neighboring radars. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getCoexistence",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getCoexistence"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setFrequencyChannel

This method should be used when you want to set the frequency channel used by the radar sensor. Setting two radar detectors that are within each others’ active area to different frequency channels will remove the risk of interference.

info

This method is only available if a frequencyChannel key is present in the response retrieved from getConfigurationCapabilities.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setFrequencyChannel",  "params": {    "automatic": <true | false>,    "value": <frequency channel>,    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setFrequencyChannel",  "params": {    "automatic": <true | false>,    "value": <frequency channel>,    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setFrequencyChannel"` | The method that should be used. |
| `params.automatic=<true | false>` | Indicates if the automatic frequency channel selection should be used (optional). This can only be `true` if the device supports this functionality, otherwise an error will be returned. Whether your device supports this functionality can be queried by checking the field `frequencyChannel.automatic` in the response from [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api). |
| `params.value=<integer | string>` | Specifies the frequency channel that should be used. Allowed values are provided by [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api) |
| `params.channel=<integer>` | Specifies which radar channel whose frequency channel should be set (optional). All radar channels will have their frequency channel st to `params.value` if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setFrequencyChannel",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setFrequencyChannel"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setFrequencyChannel",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setFrequencyChannel"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getFrequencyChannel

This method should be used when you want to check the current frequency channel on the radar sensor.

info

This method is only available if the frequencyChannel key is present in the response retrieved from getConfigurationCapabilities.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getFrequencyChannel",  "params": {    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getFrequencyChannel",  "params": {    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getFrequencyChannel"` | The method that should be used. |
| `params.channel=<integer>` | Specifies the radar channel whose frequency channel should be returned in the response (optional). The frequency channel for radar channel 1 will be returned if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getFrequencyChannel",  "data": {    "automatic": <true | false>,    "value": 1,  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getFrequencyChannel"` | The requested method. |
| `data.automatic=<true | false>` | Indicates if the device is configured to select frequency channels automatically. |
| `data.value=<integer | string>` | The current frequency channel for the requested radar channel. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": "<client context>",  "method": "getFrequencyChannel",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getFrequencyChannel"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setGlobalFilters

This method should be used when you want to apply the global filter configurations on the radar.

**Enable a global filter:**

In order to enable a global filter, the `params.filters` should first be modified:

```bash
"filters": \[  ...  {    "type": "<FilterName>",    "active": true  },  ...\]
```

`<FilterName>` should be replaced with the name of one of the supported filters obtained by using the method [getGlobalFilters](#getglobalfilters).

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "params": {        "filters": \[            {                "type": "swayingObjectFilter",                "active": true            }        \]    }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "params": {        "filters": \[            {                "type": "swayingObjectFilter",                "active": true            }        \]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setGlobalFilters"` | The method that should be used. |
| `params.filters=<list of objects>` | Specifies the configuration for the `filter.name` and status of `filter.active`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setGlobalFilters",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setGlobalFilters"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setGlobalFilters",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setGlobalFilters"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getGlobalFilters

This method be used when you want to check the current configuration of the global filters.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getGlobalFilters"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getGlobalFilters",    "data": {        "filters": \[            {                "type": "FilterOne",                "active": true            },            {                "type": "FilterTwo",                "active": false            }        \]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getGlobalFilters"` | The requested method. |
| `filters` | An array of objects describing a global filter. Please note that the names `FilterOne` and `FilterTwo` used above are examples. There are no filters with those names. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "Major.Minor",  "context": <client context>,  "method": "getGlobalFilters",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getGlobalFilters"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setMountingHeight

This method should be used when you want to set the mounting height of the radar detector.

The mounting height affects the radar analytics algorithm, which means that it is important to set this parameter if the mounting height differs from the default 3.5 meters.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingHeight",  "params": {    "value": <mounting height>,    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingHeight",  "params": {    "value": <mounting height>,    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setMountingHeight"` | The method that should be used. |
| `params.value=<number>` | The vertical mounting height of the radar detector, measured in meters. The range of permissible values are given by [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api). |
| `params.channel=<integer>` | Specifies the radar channel whose mounting height should be set (optional). All radar channels will have their mounting height set to `params.value` if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingHeight",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setMountingHeight"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingHeight",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setMountingHeight"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getMountingHeight

This method should be used when you want to check the current mounting height of the radar detector.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getMountingHeight",  "params": {    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getMountingHeight",  "params": {    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getMountingHeight"` | The method that should be used. |
| `params.channel` | Specifies the radar channel whose mounting height will be returned in the response (optional). The mounting height for radar channel 1 will be returned if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getMountingHeight",  "data": {    "value": <mounting height in meters>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getMountingHeight"` | The requested method. |
| `data.value` | The current mounting height for the requested radar channel. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getMountingHeight",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getMountingHeight"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setMountingTilt

This method should be used when you wish to set the mounting tilt of the radar detector. Some products may have an automatic source for the tilt measurement, which can be overridden by using this API.

The mounting tilt affects the radar analytics algorithm, which means that it is important to set this parameter if the mounting height differs from the default 0 degrees and should be set relative to the surface that the radar is "seeing". For a radar mounted on a wall, zero degrees means that the backplane of the device is parallel to the wall and vertical to the ground. If the radar is tilted downwards by 10 degrees, the value 10 should be entered, while if the radar is tilted upwards by 10 degrees, the value -10 should be entered.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingTilt",  "params": {    "automatic": <true | false>,    "value": <mounting tilt>,    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingTilt",  "params": {    "automatic": <true | false>,    "value": <mounting tilt>,    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setMountingTilt"` | The method that should be used. |
| `params.automatic=<boolean>` | Indicates whether automatic tilt angle measurement should be used. This can only be `true` if the device supports this functionality, otherwise an error will be returned. Whether your device supports this functionality can be queried by checking the field `mountingTilt.automatic` in the response from [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api). |
| `params.value=<number>` | The mounting tilt of the radar detector, measured in degrees. Positive values correspond to a radar tilted downwards, while a value of zero means that the radar is level with the surface. Allowed values are provided by [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api). This field is ignored if `params.automatic` is set to `true`. |
| `params.channel=<integer>` | Specifies the radar channel that should have its mounting tilt set (optional). All radar channels will have their mounting tilt set to `params.value` if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "setMountingTilt",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setMountingTilt"` | The requested method. |
| `data` | Empty when the request is successful. |

**Return value- Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setMountingTilt",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setMountingTilt"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getMountingTilt

This method should be used when you want to check the current mounting tilt of the radar detector and whether the radar is configured to use an automatic source for the tilt measurement.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "2.2,"  "context": "<client context>",  "method": "getMountingTilt",  "params": {    "channel": <radar channel>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2,"  "context": "<client context>",  "method": "getMountingTilt",  "params": {    "channel": <radar channel>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getMountingTilt"` | The method that should be used. |
| `params.channel` | Specifies the radar channel whose mounting tilt should be returned in the response (optional). The frequency channel for radar channel 1 will be returned if this parameter is omitted. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "2.2,"  "context": "<client context>",  "method": "getMountingTilt",  "data": {    "automatic": <true | false>,    "value": <mounting tilt in degrees>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getMountingTilt"` | The requested method. |
| `data.automatic=<true | false>` | Indicates if the device is configured to use automatic mounting tilt measurement. |
| `data.value` | The currently configured mounting tilt angle. This value is automatically updated for each request to this method if the physical mounting tilt angle of the device changes when `data.automatic` is `true`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "2.2,"  "context": "<client context>",  "method": "getMountingTilt",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getMountingTilt"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getRadarDataStatus

This method should be used when you want to check the data reception status from the radar sensor.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus"}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getRadarDataStatus"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getRadarDataStatus",    "data": {        "value": false    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getRadarDataStatus"` | The requested method. |
| `data.value` | `true` = Data is received from the radar sensor. `false` = No data is received from the radar sensor. Sensor may be malfunctioning. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getRadarDataStatus",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getRadarDataStatus"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getSupportedVersions

This method should be used when you want to retrieve a list of supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.2",    "context": "<client context>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `data.apiVersions=<array of strings>` | List of supported major API versions along with their highest minor version (`"1.3", "2.1"`). |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setLanes

This method should be used when you want to set a lane array configuration with name, status and nodes for the lane.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setLanes",  "params": {    "lanes": \[        {            "name": "name of lane",            "enabled": true,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        },        {            "name": "name of lane n",            "enabled": false,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        }    \]  }}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setLanes",  "params": {    "lanes": \[        {            "name": "name of lane",            "enabled": true,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        },        {            "name": "name of lane n",            "enabled": false,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setLanes"` | The method that should be used. |
| `params` | The lane configuration parameters. Allowed values are provided by the [getConfigurationCapabilities](#get-configuration-capabilities-analytics-api) method. |

The structure of a `lanes` object is the same in both the `data` object in the response for `getLanes` and the `params` object in the request for `setLanes`. The example configurations will be described in the parameter description table below.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "2.4",    "context": "<client context>",    "method": "setLanes",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setLanes"` | The requested method. |
| `data` | Will be empty if the request is successful. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setLanes",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setLanes"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getLanes

This method should be used when you want to check the current lane setup for the radar while it is in road mode.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/control.cgi" \\  --data '{    "apiVersion": "2.4",    "context": "<client context>",    "method": "getLanes"}'
```

```bash
POST /axis-cgi/radar/control.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "2.4",    "context": "<client context>",    "method": "getLanes"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getLanes"` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.4",  "context": "<client context>",  "method": "getLanes",  "params": {    "lanes": \[        {            "name": "name of lane",            "enabled": true,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        },        {            "name": "name of lane n",            "enabled": false,            "nodes": \[                \[x,y\], ... \[x,y\]            \]        }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getLanes"` | The method that should be used. |
| `data.value=<string>` | The current detection sensitivity. |

The structure of a `lanes` object is the same in both the `data` object in the response for `getLanes` and the `params` object in the request for `setLanes`. The example configurations will be described in the parameter description table below.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getLanes",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getLanes"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### setRadarProfile

This method should be used when you want to specify a profile for a radar channel. If no channel is used, the radar will keep its default channel number.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{  "apiVersion": "1.4",  "context": "<client context>",  "method": "setRadarProfile",  "params": {    "value": <radar profile>,    "channel": <integer>  }}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.4",  "context": "<client context>",  "method": "setRadarProfile",  "params": {    "value": <radar profile>,    "channel": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setRadarProfile"` | The requested method. |
| `value=<string>` | The radar channel that should be used. Allowed values are provided by the [getRadarProfile](#getradarprofile) method. |
| `channel=<integer>` | Specify the radar channel that should have its profile set. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "1.4",    "context": "<client context>",    "method": "setRadarProfile",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setRadarProfile"` | The method that should be used. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "setRadarProfile",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setRadarProfile"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

### getRadarProfile

This method should be used when you want to check which profile is in use.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/radar/radaranalytics.cgi" \\  --data '{    "apiVersion": "1.4",    "context": "<client context>",    "method": "getRadarProfile",    "params": {}}'
```

```bash
POST /axis-cgi/radar/radaranalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "context": "<client context>",    "method": "getRadarProfile",    "params": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getRadarProfile"` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{    "apiVersion": "1.4",    "context": "<client context>",    "method": "getRadarProfile",    "data": {        "value": "area",        "allowedValues": \["area", "road"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getRadarProfile"` | The method that should be used. |
| `data.value=<string>` | The current profile value. |
| `data.allowedValues` | Available profile values. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax:

```bash
{  "apiVersion": "2.2",  "context": "<client context>",  "method": "getRadarProfile",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getRadarProfile"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes-analytics-api) for a complete list of potential errors.

#### Parameter description table

All parameters and properties are considered mandatory unless otherwise specified.

| Property | Type | Valid values | Description |
| --- | --- | --- | --- |
| `lanes[j].name` | string | <string> | The lane name. |
| `lanes[j].enabled` | boolean | true  
false | Enable/disable lane. |
| `lanes[j].nodes` | \[\[x,y\], ... \[x,y\]\] | \-1, ... 1 | Polygon that describes lane outline. |

### General error codes

The following table will list all potential errors that may occur for `/axis-cgi/radar/radaranalytics.cgi`.

| Code | Description |
| --- | --- |
| `1000` | Invalid parameter value. |
| `4000` | The provided input was not well-formed JSON. |
| `4001` | A mandatory input parameter was not found in the input. |
| `4002` | The type of value of a provided JSON parameter was incorrect. |
| `4004` | The format of a provided JSON parameter was incorrect. |
| `7000` | The requested API version is not supported by this implementation. |
| `8000` | Internal error. |

## Events
### RMD event
#### Declaration of the RMD event

Declarations for the RMD (radar motion detection) events can be accessed through either VAPIX or ONVIF event web service API:s.

RMD event received using VAPIX

```bash
<tnsaxis:RadarSource>  <MotionAlarm wstop:topic="true">    <ChannelXProfileY wstop:topic="true" aev:NiceName="RMD: <profile.name>">      <aev:MessageInstance aev:isProperty="true">        <aev:DataInstance>          <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true"/>        </aev:DataInstance>      </aev:MessageInstance>    </ChannelXProfileY>  </MotionAlarm></tnsaxis:RadarSource>
```

The event in this example is called `ChannelXProfileY` and is sent every time an object has entered a specific include area. It is based on a profile with `channel=X` and `uid=Y`.

The following properties can be used to match the criteria and trigger an action rule:

| Parameter | Description |
| --- | --- |
| `Property=<active>` | Activates the event when movement is detected in the area and deactivates when the movement disappears. |
| `<active>` | A stateful event. An active event has the value `1`, an inactive `0`. |

#### RMD events for multichannel products

This example will show you how an event declaration will look in a scenario where a multichannel product consisting of two channels with two profiles each is used.

```bash
<tnsaxis:RadarSource>    <MotionAlarm wstop:topic="true">        <Channel1Profile1 wstop:topic="true" aev:NiceName="RMD: Garden Left">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </Channel1Profile1>        <Channel1Profile2 wstop:topic="true" aev:NiceName="RMD: Garden Right">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </Channel1Profile2>        <Channel2Profile3 wstop:topic="true" aev:NiceName="RMD: Parking Day">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </Channel2Profile3>        <Channel2Profile4 wstop:topic="true" aev:NiceName="RMD: Parking Night">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </Channel2Profile4>    </MotionAlarm></tnsaxis:RadarSource>
```

#### ChannelXProfileANY event

When the radar detects an object entering an include area an `ANY` event element will be sent for a specific channel.

ANY event using the VAPIX API

```bash
<tnsaxis:RadarSource>    <MotionAlarm wstop:topic="true">        <ChannelXProfileANY wstop:topic="true" aev:NiceName="RMD: Any Profile">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </ChannelXProfileANY>    </MotionAlarm></tnsaxis:RadarSource>
```

The event in this example is named `ChannelXProfileANY` and it is sent every time an object enters a specific include area. It is based on a profile with `channel=X`.

#### ChannelANY event

When the radar detects an object entering an include area a global `ANY` event element will be sent. This means that alarms appearing on one of the channels will trigger the global `ANY` event on all channels.

Global ANY event using the VAPIX API:

```bash
<tnsaxis:RadarSource>    <MotionAlarm wstop:topic="true">        <ChannelANY wstop:topic="true" aev:NiceName="RMD: Any Channel">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="active" aev:isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </ChannelANY>    </MotionAlarm></tnsaxis:RadarSource>
```

#### The event stream

A user may subscribe to events from the VAPIX/ONVIF event stream and receive information about the format of both the stream and its elements in [http://www.onvif.org/onvif/ver10/schema/onvif.xsd](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [http://www.onvif.org/onvif/ver10/topics/topicns.xml](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

Using VAPIX, this stream can be retrieved over RTSP using the following URL:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=tnsaxis:RadarSource/MotionAlarm//
```

It is also possible to listen for a specific profile:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=tnsaxis:RadarSource/MotionAlarm/ChannelXProfileY/
```

#### Synchronize metadata with video stream

Axis radar sensors uses the Real Time Streaming Protocol (RTSP) to control the media stream between radar and clients. RTSP implements the Realtime Transport Protocol (RTP) for the packet format when streaming the meta/video data, and the RTP Control Protocol (RTCP) for the synchronization of the metadata and video data stream. The synchronized conversation, from the absolute time (UTC timestamp) at the motion detection, to the relative time (RTP timestamp) for the video stream, can be found in the RTCP packet.

### ONVIF MotionAlarm event
#### Declaration of the MotionAlarm event

The declaration of the ONVIF Motion Alarm event can be accessed through either the VAPIX or ONVIF event web service API. ONVIF events corresponds to the `ChannelXProfileANY` event and will be sent if there is an `ANY` event sent to a specific channel.

ONVIF Motion Alarm event received from the VAPIX API

```bash
<tns1:VideoSource>    <MotionAlarm wstop:topic="true">        <tt:MessageDescription IsProperty="true">            <tt:Source>                <tt:SimpleItemDescription Name="Source" Type="tt:ReferenceToken" />            </tt:Source>            <tt:Data>                <tt:SimpleItemDescription Name="State" Type="xs:boolean" />            </tt:Data>        </tt:MessageDescription>    </MotionAlarm></tns1:VideoSource>
```

| Parameter | Description |
| --- | --- |
| `Property=<Source>` | The ONVIF Video source starting at `0`. |
| `<Source>` | Reference counter starts at `0`. |
| `Property=<Data>` | The value for the motion alarm state. |
| `<State>` | An active event has the value `1`, an inactive `0`. |

#### The event stream

A user may subscribe to events from the VAPIX/ONVIF event stream. The format of both the stream and its elements are described in [http://www.onvif.org/onvif/ver10/schema/onvif.xsd](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [http://www.onvif.org/onvif/ver10/topics/topicns.xml](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

Using VAPIX, this stream can be retrieved over RTSP with the following URL:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=tns1:VideoSource/MotionAlarm//
```

It is also possible to listen for a specific profile with the following URL:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&eventtopic=tnsaxis:RadarSource/MotionAlarm/ChannelXProfileY/
```

### System event
#### Radar data disruption event

Radar data errors uses the tag `format_modifier_user_string` in notifications for radar data disruption events to return a user friendly explanation on what went wrong. The channel with the value `-1` and the nicename `Any` will be used as the combined status for all channels.

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:HardwareFailure aev:NiceName="Hardware failure">        <RadarFailure wstop:topic="true" aev:NiceName="Radar data failure">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance aev:NiceName="Channel Identifier" Type="xsd:int" Name="channel" />                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance aev:NiceName="Reason Code" Type="xsd:int" Name="reason" />                    <aev:SimpleItemInstance aev:NiceName="Reason Description" Type="xsd:string" Name="reasonstr" />                    <aev:SimpleItemInstance                        aev:NiceName="Radar Data Disruption"                        Type="xsd:boolean"                        Name="disruption"                        isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </RadarFailure>    </tnsaxis:HardwareFailure></tns1:Device>
```

| Reason code | Reason description |
| --- | --- |
| `0` | No radar data. |
| `1` | Radar interference. |
| `3` | Radar tampering. |

### Event actions
#### Activate radar action

This action should be used when you want to turn the radar detection either on or off by using one of the following options:

-   **fixed action**: keeps the radar either on or off for a predefined time set by parameters .
-   **unlimited action**: keeps the radar either on or off as long as all event conditions are fulfilled.

**Action id**

-   `com.axis.action.fixed.radar`
-   `com.axis.action.unlimited.radar`

| Parameters | Valid values | Description |
| --- | --- | --- |
| `state` | 0, 1 | 0 = Radar detection is off. 1 = Radar detection is on. |
| `duration` | Unsigned integer | Fixed actions: The number of seconds that keeps the radar either on or off. |

## Metadata
### The metadata stream

All users are able to subscribe to a metadata stream from the VAPIX and ONVIF analytics web service detailed in [https://www.onvif.org/specs/srv/analytics/ONVIF-Analytics-Service-Spec-v241.pdf](https://www.onvif.org/specs/srv/analytics/ONVIF-Analytics-Service-Spec-v241.pdf).

Using VAPIX, this stream can be retrieved over RTSP with the following URL:

```bash
rtsp://<servername>/axis-media/media.amp?video=0&audio=0&event=off&analytics=polygon
```

An XML frame may contain several `object` elements corresponding to a tracked object. Frames with no detected objects are sent as empty frames.

### Radar extension description

info

This extension has been deprecated and will no longer receive any updates. We recommend that you use the following ONVIF fields instead:

-   Use the standardized GeoLocation field instead of the GeoLocation extension.
-   Use the SphericalCoordinate field instead of the PolarCoordinate extension.
-   Use the Speed and Direction fields located under Behaviour instead of the Velocity extenstion.

This metadata stream contains an extension for radar-specific data where `<tt:Appearance>` contains a radar extension for the radar object info:

```bash
<tt:Extension>    <axrt:RadarObjectInfo>        <axrt:PolarCoordinate angle="0.0" range="0.0" />        <axrt:Velocity m-s="0.0" angle="0.0" />        <axrt:Size m="0.0" />    </axrt:RadarObjectInfo></tt:Extension>
```

| Parameter | Description |
| --- | --- |
| `PolarCoordinate` | The angle and range where the object is located according to the position of the radar sensor. Range is given in meters and angle in degrees where `0°` is straight ahead of the sensor. |
| `Velocity` | The speed and direction of the object, where direction is the bearing relative to the radar sensor measured in degrees. |
| `Size` | The size of the detected object, measured in meters. |

`<tt:Class>` includes an extension when the type under `<tt:ClassCandidate>` is `Other`.

```bash
<tt:Extension>    <tt:OtherTypes>        <tt:Type>Unknown</tt:Type>        <tt:Likelihood>1.0</tt:Likelihood>    </tt:OtherTypes></tt:Extension>
```

In this case, type can be:

-   `Unknown`
-   `SmallObject`

### Declaration of the metadata stream

The following example will show you how a metadata frame may look for a scenario when multiple objects are tracked.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:VideoAnalytics>        <tt:Frame UtcTime="2017-07-14T08:45:20.284189Z">            <tt:Object ObjectId="88">                <tt:Appearance>                    <tt:Shape>                        <tt:BoundingBox bottom="-0.438904" top="-0.458923" right="0.130005" left="0.109985" />                        <tt:CenterOfGravity x="0.109985" y="-0.458923" />                        <tt:Polygon>                            <tt:Point x="0.099976" y="-0.468933" />                            <tt:Point x="0.119995" y="-0.468933" />                            <tt:Point x="0.119995" y="-0.448914" />                            <tt:Point x="0.099976" y="-0.448914" />                        </tt:Polygon>                    </tt:Shape>                    <tt:Class>                        <tt:ClassCandidate>                            <tt:Type>Other</tt:Type>                            <tt:Likelihood>0.80</tt:Likelihood>                        </tt:ClassCandidate>                        <tt:Extension>                            <tt:OtherTypes>                                <tt:Type>Unknown</tt:Type>                                <tt:Likelihood>1.0</tt:Likelihood>                            </tt:OtherTypes>                        </tt:Extension>                        <tt:Type Likelihood="0.75">Vehicle</tt:Type>                    </tt:Class>                    <tt:Extension>                        <axrt:RadarObjectInfo xmlns:axrt="http://www.axis.com/2017/radar/axrt">                            <axrt:PolarCoordinate angle="23.91" range="14.49" />                            <axrt:Velocity m-s="1.05" angle="343.60" />                            <axrt:Size m="0.00" />                        </axrt:RadarObjectInfo>                        <tt:GeoLocation lon="0.0000528" lat="0.0001196" elevation="0" />                    </tt:Extension>                    <tt:GeoLocation lon="0.0000528" lat="0.0001196" elevation="0" />                    <tt:SphericalCoordinate Distance="14.49" ElevationAngle="0.0" AzimuthAngle="66.09" />                    <tt:Behaviour>                        <tt:Speed>1.05</tt:Speed>                        <tt:Direction yaw="106.4" pitch="0" />                    </tt:Behaviour>                </tt:Appearance>            </tt:Object>            <tt:Object ObjectId="84">...</tt:Object>        </tt:Frame>    </tt:VideoAnalytics></tt:MetadataStream>
```