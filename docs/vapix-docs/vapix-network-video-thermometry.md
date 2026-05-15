---
title: Thermometry
url: "https://developer.axis.com/vapix/network-video/thermometry/"
category: vapix
subcategory: network-video
sha256: c3d33a03671a6ef68f73e65ad0c7d34f1524d0448d7ae97d8fdb267f7003d5bb
scraped_at: "2026-01-09T15:21:19.221Z"
page_height: 121108
---

# Thermometry

The VAPIX® Thermometry API provides the information that makes it possible to configure the temperature monitoring functions on a temperature calibrated thermal camera:

-   **Isothermal palettes**: Pixels colored differently depending on their temperature for an overview of the temperatures across the scene. You can choose between a number of palettes that can be either isothermal or non-isothermal. The chosen palette is stored in the parameter `Image.I0.Appearance.Palette`, which is used by the majority of thermal cameras, including those without thermometric capabilities. However, only thermometric cameras have isothermal palettes as an option, further detailed in `getIsothermLevels` and `setIsothermLevels`. Three temperature levels must be provided if an isothermal palette is chosen. These temperatures will be tied to three distinct colors in the palette. Temperatures between and outside of these levels will be linearly mapped to the colors of the palette. An image of the palette and the three levels can also be included in the video stream as an overlay.
-   **Temperature detection areas**: Defined numbers of polygon-shaped areas in which the temperature can be monitored. You are able to set a number of conditions that must be met before the alarm will trigger. For example, you are able to set a temperature limit that will trigger the alarm whenever the temperature goes above or below it. An alternative to the fixed threshold is setting a limit on how fast the temperature is allowed to increase or decrease. This means that you need to set a delay time (in seconds) before the alarm will trigger and if it will trigger on the highest, lowest or at an average temperature in the area. It is possible to include the areas as overlays in the video. The areas can also be tied to a preset on a mounted pan/tilt-device.
-   **Spot temperature measurement**: A single spot in the image chosen to measure the temperature. There can only be one spot temperature, which will then be included in the video stream as an overlay.
-   **Image source**: The channel where the thermal image originated from. It can have different numbers depending on the product and show the overlays without the need to first enable them. Channels can be every possible stream, while overlay channels are streams with overlays. Examples of the latter can be an area overlay or spotmeter overlay that can appear on that channel and will be different than the image source. An image source can't be an overlay channel and can vary between products. Lastly, it should be noted that area overlays default to the image source they were created on.

## Overview

The API implements `/axis-cgi/thermometry.cgi` as its communications interface and supports the following methods:

| Method | Description | Supported from API version |
| --- | --- | --- |
| [getSupportedVersions](#getsupportedversions) | List supported API versions. | 1.0 |
| [getConfigurationCapabilities](#getconfigurationcapabilities) | Retrieve values to configure the functionality. | 1.0 |
| [setTemperatureScale](#settemperaturescale) | Set temperature scale. | 1.0 |
| [getIsothermLevels](#getisothermlevels) | Retrieve current isotherm levels. | 1.0 |
| [setIsothermLevels](#setisothermlevels) | Set isotherm levels. | 1.0 |
| [addArea](#addarea) | Add a new alarm area. | 1.0 |
| [updateArea](#updatearea) | Update alarm area. | 1.0 |
| [removeAreas](#removeareas) | Delete one or several areas. | 1.0 |
| [listAreas](#listareas) | List temperature areas. | 1.0 |
| [getAreaStatus](#getareastatus) | Retrieve the current status of active areas. | 1.0 |
| [addSpotTemperature](#addspottemperature) | Adds the spot meter to new coordinates. | 1.0 |
| [getSpotTemperature](#getspottemperature) | Retrieve a spot temperature. | 1.0 |
| [removeSpotTemperature](#removespottemperature) | Remove the spot meter. | 1.0 |
| [getTgtConfiguration](#gettgtconfiguration) | Retrieve the thermometric guard tour configuration. | 1.1 |
| [setTgtConfiguration](#settgtconfiguration) | Set the thermometric guard tour configuration. | 1.1 |
| [addGroup](#addgroup) | Add a new group. | 1.2 |
| [updateGroup](#updategroup) | Update a group. | 1.2 |
| [removeGroup](#removegroup) | Delete one or all groups. | 1.2 |
| [listGroups](#listgroups) | List groups. | 1.2 |
| [getGroupStatus](#getgroupstatus) | Retrieve the current status of active groups. | 1.2 |
| [addOverlayChannel](#addoverlaychannel) | Add a channel to the area overlay display. | 1.3 |
| [removeOverlayChannel](#removeoverlaychannel) | Remove the overlay channel. | 1.3 |
| [listOverlayChannels](#listoverlaychannels) | List overlay channels. | 1.3 |
| [listSpotMeters](#listspotmeters) | List all the spot meters, along with their state. | 1.3 |

### Identification

-   **API Discovery**: `id=thermometry`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### List supported API versions

This example will show you how to list the API versions that are supported by your device.

1.  List supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0"\]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [getSupportedVersions](#getsupportedversions) for additional details.

### List thermometry configuration capabilities

This example will show you how to list the thermometric capabilities featured on your camera. It is useful when you want to set up the user interface without hard coded information or legacy parameters. The parameter `maxNumberOfAreas` is used per each individual preset on PTZ cameras.

1.  List thermometric capabilities.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getConfigurationCapabilities",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getConfigurationCapabilities",    "params": {}}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getConfigurationCapabilities",    "data": {        "currentTemperatureScale": "celsius",        "minTemperature": -40,        "maxTemperature": 350,        "maxNumberOfAreas": 10,        "maxNumberOfVertices": 10,        "maxDelayTime": 300,        "defaultDelayTime": 5,        "maxNameLength": 60    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getConfigurationCapabilities",    "error": {        "code": 3000,        "message": "The requested API version is not supported."    }}
```

See [getConfigurationCapabilities](#getconfigurationcapabilities) for additional details.

### Set temperature scale

This example will show you how to set the temperature scale to be either Celsius or Fahrenheit.

1.  Set the temperature scale.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setTemperatureScale",    "params": {        "unit": "fahrenheit"    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setTemperatureScale",    "params": {        "unit": "fahrenheit"    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setTemperatureScale",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setTemperatureScale",    "error": {        "code": 2104,        "message": "Invalid parameter value."    }}
```

See [setTemperatureScale](#settemperaturescale) for additional details.

### List isotherm levels

This example will show you how to list the current isotherm levels.

1.  Retrieve the current isotherm levels.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getIsothermLevels",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getIsothermLevels",    "params": {}}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getIsothermLevels",    "data": {        "high": 100,        "middle": 50,        "low": 10,        "renderOverlay": true    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getIsothermLevels",    "error": {        "code": 2102,        "message": "Method not supported."    }}
```

See [getIsothermLevels](#getisothermlevels) for additional details.

### Set isotherm levels

This example will show you how to colorize the image with an isothermal palette. The palette consists of the three temperature levels that were obtained in the previous example. The palette is chosen with the parameter `Image.IO.Appearance.Palette`.

1.  Set the active palette.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setIsothermLevels",    "params": {        "high": 100,        "middle": 50,        "low": 10,        "renderOverlay": true    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setIsothermLevels",    "params": {        "high": 100,        "middle": 50,        "low": 10,        "renderOverlay": true    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setIsothermLevels",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setIsothermLevels",    "error": {        "code": 2104,        "message": "Invalid parameter: Levels not in correct order."    }}
```

See [setIsothermLevels](#setisothermlevels) for additional details.

### Add a temperature detection area

This example will show you how to monitor the temperature of a selected area or object and set a temperature threshold. An alarm will be raised if the temperature goes outside of the limits defined by the threshold.

1.  Add a new temperature area.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "addArea",    "params": {        "imagesource": 0,        "enabled": true,        "name": "Area 1",        "detectionType": "above",        "measurement": "average",        "threshold": 100,        "delay": 5,        "vertices": \[            \[-0.5, -0.5\],            \[0.5, -0.5\],            \[0.5, 0.5\],            \[-0.5, 0.5\]        \],        "areaOverlay": "always",        "temperatureOverlay": true,        "presetNbr": 1    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "addArea",    "params": {        "imagesource": 0,        "enabled": true,        "name": "Area 1",        "detectionType": "above",        "measurement": "average",        "threshold": 100,        "delay": 5,        "vertices": \[            \[-0.5, -0.5\],            \[0.5, -0.5\],            \[0.5, 0.5\],            \[-0.5, 0.5\]        \],        "areaOverlay": "always",        "temperatureOverlay": true,        "presetNbr": 1    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "addArea",    "data": {        "id": 0    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "addArea",    "error": {        "code": 2103,        "message": "Required parameter missing."    }}
```

See [addArea](#addarea) for additional details.

### Modify a temperature detection area

This example will show you how to modify the settings of a detection area.

1.  Update an existing temperature area.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "updateArea",    "params": {        "id": 0,        "imagesource": 0,        "enabled": true,        "name": "Area 1",        "detectionType": "below",        "measurement": "minimum",        "threshold": 100,        "delay": 5,        "vertices": \[            \[-0.5, -0.5\],            \[0.5, -0.5\],            \[0.5, 0.5\],            \[-0.5, 0.5\]        \],        "areaOverlay": "if\_triggered",        "temperatureOverlay": true,        "presetNbr": 2    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "updateArea",    "params": {        "id": 0,        "imagesource": 0,        "enabled": true,        "name": "Area 1",        "detectionType": "below",        "measurement": "minimum",        "threshold": 100,        "delay": 5,        "vertices": \[            \[-0.5, -0.5\],            \[0.5, -0.5\],            \[0.5, 0.5\],            \[-0.5, 0.5\]        \],        "areaOverlay": "if\_triggered",        "temperatureOverlay": true,        "presetNbr": 2    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "updateArea",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "updateArea",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
```

See [updateArea](#updatearea) for additional details.

### Remove temperature detection areas

This example will show you how to remove one or more temperature areas.

1.  Delete 3 temperature areas.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "removeAreas",    "params": {        "areas": \[0, 1, 3\]    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "removeAreas",    "params": {        "areas": \[0, 1, 3\]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "removeAreas",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "removeAreas",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [removeAreas](#removeareas) for additional details.

### List temperature detection areas

This example will show you how to list existing temperature areas and their individual settings.

1.  Create a list.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "listAreas",    "params": {        "presetNbr": 0    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "listAreas",    "params": {        "presetNbr": 0    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "listAreas",    "data": {        "areaList": \[            {                "id": 0,                "imageSource": 0,                "enabled": true,                "name": "Area 1",                "detectionType": "below",                "measurement": "minimum",                "threshold": 100,                "delay": 5,                "position": \[                    \[-0.5, -0.5\],                    \[0.5, -0.5\],                    \[0.5, 0.5\],                    \[-0.5, 0.5\]                \],                "areaOverlay": "if triggered",                "temperatureOverlay": true,                "presetNbr": 1            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "listAreas",    "error": {        "code": 2110,        "message": "User is not authorized to this request, permission denied."    }}
```

See [listAreas](#listareas) for additional details.

### Check area status

This example will show you how to investigate the current status of the alarm areas.

1.  Retrieve current status of the active areas.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getAreaStatus",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getAreaStatus",    "params": {}}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getAreaStatus",    "data": {        "areaList": \[            {                "id": 0,                "avg": 5,                "min": 0,                "max": 10,                "maxPos": \[0.91, 0.12\],                "minPos": \[-0.63, -0.31\],                "triggered": true            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getAreaStatus",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [getAreaStatus](#getareastatus) for additional information.

### Add a spot temperature

This example will show you how to activate the spot temperature for the given coordinates and render it as an overlay in the image.

1.  Add a spot temperature.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "addSpotTemperature",    "params": {        "spotCoordinates": \[0.37, -0.95\],        "coordinateSystem": "coord\_neg1\_1"    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "addSpotTemperature",    "params": {        "spotCoordinates": \[0.37, -0.95\],        "coordinateSystem": "coord\_neg1\_1"    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "addSpotTemperature",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "addSpotTemperature",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [addSpotTemperature](#addspottemperature) for additional information.

### Check spot temperature

This example will show you how to check the temperature in the spot chosen with the `addSpotTemperature` method.

1.  Take the temperature for a spot-sized area.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSpotTemperature",    "params": {        "coordinateSystem": "coord\_neg1\_1"    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSpotTemperature",    "params": {        "coordinateSystem": "coord\_neg1\_1"    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSpotTemperature",    "data": {        "spotTemperature": 7,        "spotCoordinates": \[-0.53, 0.45\],        "renderOverlay": true    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSpotTemperature",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [getSpotTemperature](#getspottemperature) for additional details.

### Remove a spot temperature

This example will show you how to remove the spot temperature and disable the overlay.

1.  Remove the spot temperature.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "removeSpotTemperature",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "removeSpotTemperature",    "params": {}}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "removeSpotTemperature",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "removeSpotTemperature",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [removeSpotTemperature](#removespottemperature) for additional details.

### Get TGT configuration

This example will show you how to check the current thermometric guard tour settings.

1.  Get TGT configuration:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "my context",    "method": "getTgtConfiguration",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "my context",    "method": "getTgtConfiguration",    "params": {}}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "my context",    "method": "getTgtConfiguration",    "data": {        "pauseOnAlarm": true,        "autoResume": true    }}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "my context",    "method": "getTgtConfiguration",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [getTgtConfiguration](#gettgtconfiguration) for additional details.

### Set TGT configuration

This example will show you how to change the thermometric guard tour settings.

1.  Set TGT configuration:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "my context",    "method": "setTgtConfiguration",    "params": {        "pauseOnAlarm": true,        "autoResume": true    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "my context",    "method": "setTgtConfiguration",    "params": {        "pauseOnAlarm": true,        "autoResume": true    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.1",    "context": "my context",    "method": "setTgtConfiguration",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.1",    "context": "my context",    "method": "setTgtConfiguration",    "error": {        "code": 1100,        "message": "Internal error."    }}
```

See [setTgtConfiguration](#settgtconfiguration) for additional details.

### Add a group

This example will show you how to create a group of temperature areas and monitor them in search for deviations. If the difference between the highest and lowest area temperatures exceed the defined threshold and time limit, the alarm will be raised.

1.  Add a new group

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "addGroup",    "params": {        "enabled": true,        "name": "Group 1",        "measurement": "average",        "threshold": 5,        "delay": 5,        "areaIds": \[0, 1, 2\],        "groupOverlay": true,        "presetNbr": 1    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "addGroup",    "params": {        "enabled": true,        "name": "Group 1",        "measurement": "average",        "threshold": 5,        "delay": 5,        "areaIds": \[0, 1, 2\],        "groupOverlay": true,        "presetNbr": 1    }}
```

2.  Parse the JSON response

Successful response example, in which the `addGroup` method returns an ID for the group

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "addGroup",    "data": {        "id": 1,        "enabled": true    }}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "addGroup",    "error": {        "code": 2103,        "message": "Missing parameter: 'param'"    }}
```

See [addGroup](#addgroup) for additional details.

### Modify a group

This example will show you how to modify the settings of an existing group.

1.  Modify a group:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "updateGroup",    "params": {        "id": 2,        "enabled": true,        "name": "Group 1",        "measurement": "minimum",        "threshold": 10,        "delay": 5,        "areaIds": \[3, 4\],        "groupOverlay": true    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "updateGroup",    "params": {        "id": 2,        "enabled": true,        "name": "Group 1",        "measurement": "minimum",        "threshold": 10,        "delay": 5,        "areaIds": \[3, 4\],        "groupOverlay": true    }}
```

2.  Parse the JSON response

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "updateGroup",    "data": {        "enabled": true    }}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "updateGroup",    "error": {        "code": 2104,        "message": "Invalid parameter for: 'param'"    }}
```

See [updateGroup](#updategroup) for additional details.

### Remove a group

This example will show you how to remove one or all groups.

1.  Delete group:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "removeGroup",    "params": {        "id": 1    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "removeGroup",    "params": {        "id": 1    }}
```

2.  Parse the JSON response

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "removeGroup",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "removeGroup",    "error": {        "code": 1200,        "message": "Cannot remove group: Group does not exist"    }}
```

See [removeGroup](#removegroup) for additional details.

### List all groups

This example will show you how to review existing groups and their settings.

1.  List all temperature areas and their settings:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "listGroups",    "params": {        "presetNbr": 0    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "listGroups",    "params": {        "presetNbr": 0    }}
```

2.  Parse the JSON response

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "listGroups",    "data": {        "grouplist": \[            {                "id": 2,                "enabled": true,                "name": "Group 2",                "measurement": "minimum",                "threshold": 10,                "delay": 5,                "areaIds": \[2, 3\],                "groupOverlay": true,                "presetNbr": 0            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "listGroups",    "error": {        "code": 2110,        "message": "User is not authorized to this request, permission denied"    }}
```

See [listGroups](#listgroups) for additional details.

### Retrieve the group status

This example will show you how to check the status of the group alarms in the current preset.

1.  Check the current status of the active groups:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "my context",    "method": "getGroupStatus",    "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "my context",    "method": "getGroupStatus",    "params": {}}
```

2.  Parse the JSON response

Successful response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getGroupStatus",    "data": {        "grouplist": \[            {                "id": 2,                "triggered": true,                "details": {                    "name": "Group1",                    "currentDeviation": 10.0,                    "memberAreas": \[                        { "areaId": 1, "areaName": "Area1" },                        { "areaId": 2, "areaName": "Area2" },                        { "areaId": 3, "areaName": "Area3" }                    \],                    "maxDeviationAreas": \[                        { "maxAreaId": 1, "maxAreaTemp": 25.3 },                        { "minAreaId": 3, "minAreaTemp": 15.3 }                    \]                }            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.2",    "context": "my context",    "method": "getGroupStatus",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

See [getGroupStatus](#getgroupstatus) for additional details.

### Add an overlay channel

This example will show you how to add an overlay channel.

1.  Get the current status of the active groups:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "method": "addOverlayChannel",    "context": "ClientContext",    "apiVersion": "1.3",    "params": {        "imagesource": 1,        "overlayChannel": 2    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "method": "addOverlayChannel",    "context": "ClientContext",    "apiVersion": "1.3",    "params": {        "imagesource": 1,        "overlayChannel": 2    }}
```

2.  Parse the JSON response.

Successful response example:

```bash
{    "apiVersion": "1.3",    "context": "ClientContext",    "method": "addOverlayChannel",    "data": {}}
```

Error response example:

```bash
{    "apiVersion": "1.3",    "context": "ClientContext",    "method": "addOverlayChannel",    "error": {        "code": 2104,        "message": "Invalid parameter value specified"    }}
```

See [addOverlayChannel](#addoverlaychannel) for additional details.

### Remove overlay channel

This example will show you how to remove one of the overlay channels with an active area overlay.

1.  Delete the overlay channel:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "method": "removeOverlayChannel",    "context": "ClientContext",    "apiVersion": "1.3",    "params": {        "imagesource": 1,        "overlayChannel": 2    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "method": "removeOverlayChannel",    "context": "ClientContext",    "apiVersion": "1.3",    "params": {        "imagesource": 1,        "overlayChannel": 2    }}
```

2.  Parse the JSON response.

Successful response example:

```bash
{    "apiVersion": "1.3",    "context": "ClientContext",    "method": "removeOverlayChannel",    "data": {}}
```

Error response example:

```bash
{    "apiVersion": "1.3",    "context": "ClientContext",    "method": "removeOverlayChannel",    "error": {        "code": 2104,        "message": "Invalid parameter value specified"    }}
```

See [removeOverlayChannel](#removeoverlaychannel) for additional details.

### List overlay channels

This example will show you how to review active overlay channels and their image sources.

1.  List all active overlay channels and their related image sources:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "my context",    "method": "listOverlayChannels"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "my context",    "method": "listOverlayChannels"}
```

2.  Parse the JSON response.

Successful response example:

```bash
{    "apiVersion": "1.3",    "context": "my context",    "method": "listOverlayChannels",    "data": {        "overlayList": \[            {                "imagesource": 1,                "overlayChannels": \[0, 2\]            }        \]    }}
```

Error response example:

```bash
{    "apiVersion": "1.3",    "context": "my context",    "method": "listOverlayChannels",    "error": {        "code": 2110,        "message": "User is not authorized to this request, permission denied."    }}
```

See [listOverlayChannels](#listoverlaychannels) for additional details.

### List spot meter

This example will show you how to check if the spot meter is active on a specific channel.

1.  List all spot meter channels and their active state:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "1.3",    "context": "my context",    "method": "listSpotMeters"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.3",    "context": "my context",    "method": "listSpotMeters"}
```

2.  Parse the JSON response.

Successful response example:

```bash
{    "apiVersion": "1.3",    "context": "my context",    "method": "listSpotMeters",    "data": {        "spotmeters": \[            {                "imagesource": 0,                "active": false            }        \]    }}
```

Error response example:

```bash
{    "apiVersion": "1.3",    "context": "my context",    "method": "listSpotMeters",    "error": {        "code": 2110,        "message": "User is not authorized to this request, permission denied."    }}
```

See [listSpotMeters](#listspotmeters) for additional details.

## API specifications
### getSupportedVersions

This method should be used when you want to list all API versions supported by your device. The list will consist of all supported major versions along with their highest supported minor version.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[ "<Major1>.<Minor1>", "<Major2>.<Minor2>", ... \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `apiVersions[]=<list of versions>` | A list containing all supported API versions along with their highest supported minor version. |

**Return value - Failure**

-   **HTTP code**: `400 Bad Request`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getConfigurationCapabilities

This method should be used when you want to list the thermometric limits and values for the configuration values on your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getConfigurationCapabilities"` | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities",  "data": {    "currentTemperatureScale": <string>,    "minTemperature": <int>,    "maxTemperature": <int>,    "maxNumberOfAreas": <int>,    "maxNumberOfVertices": <int>,    "maxDelayTime": <int>,    "defaultDelayTime": <int>,    "maxNameLength": <int>,    "maxGroups": <int>,    "imagesources": \[<int>, <int>, ...\],    "overlayChannels": \[<int>, <int>, ...\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfigurationCapabilities"` | The requested method. |
| `currentTemperatureScale="celsius" | "fahrenheit"` | The current temperature scale. Can be either Celsius or Fahrenheit. |
| `minTemperature=<int>` | The minimum temperature possible to measure with the current temperature scale. |
| `maxTemperature=<int>` | The maximum temperature possible to measure with the current temperature scale. |
| `maxNumberOfAreas=<int>` | The maximum number of areas that can be defined. |
| `maxNumberOfVertices=<int>` | The maximum number of vertices that an alarm area can have. |
| `maxDelayTime=<int>` | The maximum delay time, measured in seconds. |
| `defaultDelayTime=<int>` | The default delay time, measured in seconds. |
| `maxNameLength=<int>` | The maximum number of characters you can use for an area name. |
| `maxGroups=<int>` | The maximum number of area groups that can be defined in a preset. Added in API version 1.2. |
| `imagesources=<int>` | The list of valid image sources active as thermal input channels. Added in API version 1.3. |
| `overlayChannels=<int>` | The list of channels that can have area overlays enabled. Added in API version 1.3. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getConfigurationCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getConfigurationCapabilities"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setTemperatureScale

This method should be used when you want to set the temperature scale on your device to measure in either Celsius (default) or Fahrenheit. Please note that the current temperature scale is called by the method `getConfigurationCapabilities`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureScale"  "params": {    "unit": "celsius" | "fahrenheit"  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureScale"  "params": {    "unit": "celsius" | "fahrenheit"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setTemperatureScale"` | The method that should be used. |
| `unit="celsius" | "fahrenheit"` | The temperature scale that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureScale",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setTemperatureScale"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTemperatureScale",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setTemperatureScale"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getIsothermLevels

This method should only be used together with isothermal palettes, which always have names that begins with "Iso-". Available palettes and their current value are given by the parameter `Image.IO.Appearance.Palette`, and fetched with the `/axis-cgi/param.cgi`. More information is available in [Parameter management](/vapix/network-video/parameter-management/).

This method returns the three temperature levels that have been set as fixed on the color scale as well as if the palette overlay is active or not.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIsothermLevels"}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIsothermLevels"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getIsothermLevels"` | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIsothermLevels",  "data": {    "high": <int>,    "middle": <int>,    "low": <int>,    "min": <int>    "renderOverlay": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getIsothermLevels"` | The requested method. |
| `high=<int>` | The highest temperature level on the temperature color scale. |
| `middle=<int>` | The middle temperature level on the temperature color scale. |
| `low=<int>` | The low temperature level on the temperature color scale and the lowest temperature colored by the chosen palette. Temperatures between low and minimum appear in grayscale. |
| `min=<int>` | Available in API version 1.2 and onwards. The minimum temperature on the temperature color scale. It is the lowest temperature that can be shown in the image. |
| `renderOverlay=<boolean>` | `true` if the chosen color palette is included in the video stream. The three isotherm levels will be marked on the palette. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIsothermLevels",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getIsothermLevels"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setIsothermLevels

This method should only be used when you want to set the isothermal levels for the three isothermal palettes. The request `action=update&root.Image.IO.Appearance.Palette=<name>` should be used by `/axis-cgi/param.cgi` to set the palette that should be used. All isothermal palettes have names that start with "Iso-". More information is available in [Parameter management](/vapix/network-video/parameter-management/).

The three temperature levels tied to three colors on the temperature color scale must be set before the isotherm functions can be used. These levels must be unique and set in rising order from lowest to highest. `getConfigurationCapabilities` is used to check the current temperature scale. The palette can be included in the video stream as an overlay.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIsothermLevels"  "params": {    "high": <int>,    "middle": <int>,    "low": <int>,    "min": <int>,    "renderOverlay": <boolean>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIsothermLevels"  "params": {    "high": <int>,    "middle": <int>,    "low": <int>,    "min": <int>,    "renderOverlay": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setIsothermLevels"` | The method that should be used. |
| `high=<int>` | The highest temperature level on the temperature color scale. The temperature scale itself is given by `getConfigurationCapabilities`. Range \[`getConfigurationCapabilities:minTemperature` +3, `getConfigurationCapabilities:maxTemperature`\]. |
| `middle=<int>` | The middle temperature level on the temperature color scale. The temperature scale itself is given by `getConfigurationCapabilities`. Range \[`getConfigurationCapabilities:minTemperature` +2, `getConfigurationCapabilities:maxTemperature -1`\]. |
| `low=<int>` | The lowest temperature level on the temperature color scale. The temperature scale itself is given by `getConfigurationCapabilities`. Range \[`getConfigurationCapabilities:minTemperature` +1, `getConfigurationCapabilities:maxTemperature` -2\]. |
| `min=<int>` | Optional in API version 1.2 onwards. The minimum temperature level on the temperature color scale. The temperature scale itself is given by `getConfigurationCapabilities`. If the parameter is omitted it will automatically be set to the lowest possible temperature given by `getConfigurationCapabilities`. Range \[`getConfigurationCapabilities:minTemperature`, `getConfigurationCapabilities:maxTemperature` -3\]. |
| `renderOverlay=<boolean>` | The color palette chosen to be included in the video stream. The three isotherm levels are marked on the palette. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIsothermLevels",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setIsothermLevels"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIsothermLevels",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setIsothermLevels"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### addArea

This method should be used when you want to add a new temperature detection area. The area is a polygon given as a set of coordinates in consecutive order where no edges may cross each other. Additionally, a number of conditions must be provided for when an alarm should be triggered. The maximum number of areas per preset is given by the method `getConfigurationCapabilities`.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addArea"  "params": {    "imagesource": <int>,    "enabled": <boolean>,    "name": <string>,    "detectionType": <string>,    "measurement": <string>,    "threshold": <int>,    "delay": <int>,    "vertices": \[\[<float>, <float>\],...\],    "areaOverlay": <string>,    "temperatureOverlay": <boolean>,    "presetNbr": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addArea"  "params": {    "imagesource": <int>,    "enabled": <boolean>,    "name": <string>,    "detectionType": <string>,    "measurement": <string>,    "threshold": <int>,    "delay": <int>,    "vertices": \[\[<float>, <float>\],...\],    "areaOverlay": <string>,    "temperatureOverlay": <boolean>,    "presetNbr": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="addArea"` | The method that should be used. |
| `imagesource=<int>` | The image source for the area. |
| `enabled=<boolean>` | Enables the area monitoring if `true`. |
| `name=<string>` | The area name. The maximum length is given by `getConfigurationCapabilities`. The name must be unique. |
| `detectionType="above" | "below" | "increase" | "decrease"` | The detection type  
  
\- `above` and `below`: The alarm will trigger if the value goes above or below the threshold value.  
\- `increase` and `decrease`: Monitors the change rate of the temperature. The alarm will trigger if the temperature increases or decreases faster than the threshold value divided by the delay time. |
| `measurement="maximum" | "minimum" | "average"` | The area value. The alarm will trigger depending on the maximum, minimum or average temperature in the area. |
| `threshold=<int>` | The temperature value that activates the trigger. This is the temperature change during the delay time and must be positive for the increase and decrease detection types. The allowed range is given by the method `getConfigurationCapabilities`. |
| `delay=<int>` | The number of seconds the trigger condition must be true before an alarm is triggered. If the delay time is zero the alarm will activate immediately when the trigger conditions are met. This is the time during which the temperature must have changed with the threshold value to trigger the alarm for the increase and decrease detection types. Both the maximum and default delay time is given in the method `getConfigurationCapabilities`. |
| `vertices=Array of coordinates` | The vertices of the polygon, given as an array of its x and y coordinates \[x, y\]. All vertices must be unique and the edges of the polygon can not cross each other. The coordinates are normalized to the size of the image and spans from -1 to 1 in both the horizontal and vertical direction. This means that the upper right corner has the coordinates \[1, 1\], while the lower left corner has the coordinates \[-1, -1\]. The coordinates must always be given for an image that is neither rotated or mirrored. The minimum number of vertices in a polygon is 3, the maximum is given by the method `getConfigurationCapabilities`. |
| `areaOverlay="none" | "always" | "if_triggered"` | Tells if and when the area should be included in the video stream and visible on recordings. The overlay color will change from green to red if the alarm is triggered. |
| `temperatureOverlay=<boolean>` | Indicates if the temperature of the area should be shown, but only when the area overlay is visible. The chosen measurement value is shown. |
| `presetNbr=<int>` | The preset number for the area. Will be ignored on non PTZ cameras and must be an existing preset number for PTZ cameras. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addArea",  "data": {    "id": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addArea"` | The requested method. |
| `id=<int>` | The area id. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addArea",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addArea"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Maximum amount of areas in preset reached. |
| `1200` | Preset does not exist. |
| `2104` | The specified name is already in use. |

### updateArea

This method should be used when you want to update an existing area.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "updateArea"  "params": {    "id": <int>,    "imagesource": <int>,    "enabled": <boolean>,    "name": <string>,    "detectionType": <string>,    "measurement": <string>,    "threshold": <int>,    "delay": <int>,    "vertices": \[\[<float>, <float>\],...\],    "areaOverlay": <string>,    "temperatureOverlay": <boolean>,    "presetNbr": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "updateArea"  "params": {    "id": <int>,    "imagesource": <int>,    "enabled": <boolean>,    "name": <string>,    "detectionType": <string>,    "measurement": <string>,    "threshold": <int>,    "delay": <int>,    "vertices": \[\[<float>, <float>\],...\],    "areaOverlay": <string>,    "temperatureOverlay": <boolean>,    "presetNbr": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="updateArea"` | The method that should be used. |
| `id=<int>` | The area ID. |
| `imagesource=<int>` | The image source for the area. |
| `enabled=<boolean>` | Enables the area monitoring if `true`. |
| `name=<string>` | The area name. The maximum length is given by `getConfigurationCapabilities`. The name must be unique. |
| `detectionType="above" | "below" | "increase" | "decrease"` | The detection type  
  
\- `above` and `below`: The alarm will trigger if the value goes above or below the threshold value.  
\- `increase` and `decrease`: Monitors the change rate of the temperature. The alarm will trigger if the temperature increases or decreases faster than the threshold value divided by the delay time. |
| `measurement="maximum" | "minimum" | "average"` | The area value. The alarm will trigger depending on the maximum, minimum or average temperature in the area. |
| `threshold=<int>` | The temperature value that activates the trigger. This is the temperature change during the delay time and must be positive for the increase and decrease detection types. The allowed range is given by the method `getConfigurationCapabilities`. |
| `delay=<int>` | The number of seconds the trigger condition must be true before an alarm is triggered. If the delay time is zero the alarm will activate immediately when the trigger conditions are met. This is the time during which the temperature must have changed with the threshold value to trigger the alarm for the increase and decrease detection types. Both the maximum and default delay time is given in the method `getConfigurationCapabilities`. |
| `vertices=Array of coordinates` | The vertices of the polygon, given as an array of it x and y coordinates \[x, y\]. All vertices must be unique and the edges of the polygon can not cross each other. The coordinates are normalized to the size of the image and spans from -1 to 1 in both the horizontal and vertical direction. This means that the upper right corner has the coordinates \[1, 1\], while the lower left corner has the coordinates \[-1, -1\]. The coordinates must always be given for an image that is neither rotated or mirrored. The minimum number of vertices in a polygon is 3, the maximum is given by the method `getConfigurationCapabilities`. |
| `areaOverlay="none" | "always" | "if_triggered"` | Tells if and when the area should be included in the video stream and visible on recordings. The overlay color will change from green to red if the alarm is triggered. |
| `temperatureOverlay=<boolean>` | Indicates if the temperature of the area should be shown, but only when the area overlay is visible. The chosen measurement value is shown. |
| `presetNbr=<int>` | The preset number for the area. Will be ignored on non PTZ cameras and must be an existing preset number for PTZ cameras. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "updateArea",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="updateArea"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "updateArea",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="updateArea"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Maximum amount of areas in preset reached. |
| `1200` | Preset does not exist. |
| `2104` | The specified name is already in use. |

### removeAreas

This method should be used when you want to remove specified areas.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeAreas"  "params": {    "areas": \[<int>, <int>, ...\]  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeAreas"  "params": {    "areas": \[<int>, <int>, ...\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="removeAreas"` | The method that should be used. |
| `params.areas=[<int>, <int>, ...]` | ID:s of the areas that should be removed. The maximum number of areas per request is given by `getConfigurationCapabilities`. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeAreas",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeAreas"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeAreas",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeAreas"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Area \[x\] could not be found |

### listAreas

This method should be used when you want to list all temperature detection areas for a provided preset number. All areas will be returned for all presets if the preset number is set to 0.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAreas"  "params": {    "presetNbr": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAreas"  "params": {    "presetNbr": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="listAreas"` | The method that should be used. |
| `params.presetNbr=<integer>` | The preset number for which the temperature areas will be returned. All areas for all presets are returned if the number is 0. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAreas",  "data": {    "areaList": \[      {        "id": <int>,        "imagesource": <int>,        "enabled": <boolean>,        "name": <string>,        "detectionType": <string>,        "measurement": <string>,        "threshold": <int>,        "delay": <int>,        "position": \[\[<float>, <float>\],...\],        "areaOverlay": <string>,        "temperatureOverlay": <boolean>,        "presetNbr": <int>      }, ...    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listAreas"` | The requested method. |
| `id=<int>` | The area ID. |
| `imagesource=<int>` | The image source for the area. |
| `enabled=<boolean>` | Enables the area monitoring if `true`. |
| `name=<string>` | The area name. The maximum length is given by `getConfigurationCapabilities`. |
| `detectionType="above" | "below" | "increase" | "decrease"` | The detection type  
  
\- `above` and `below`: The alarm will trigger if the value goes above or below the threshold value.  
\- `increase` and `decrease`: Monitors the change rate of the temperature. The alarm will trigger if the temperature increases or decreases faster than the threshold value divided by the delay time. |
| `measurement="maximum" | "minimum" | "average"` | The area value. The alarm will trigger depending on the maximum, minimum or average temperature in the area. |
| `threshold=<int>` | The temperature value that activates the trigger. This is the temperature change during the delay time and must be positive for the increase and decrease detection types. The allowed range is given by the method `getConfigurationCapabilities`. |
| `delay=<int>` | The number of seconds the trigger condition must be true before an alarm is triggered. If the delay time is zero the alarm will activate immediately when the trigger conditions are met. This is the time during which the temperature must have changed with the threshold value to trigger the alarm for the increase and decrease detection types. The maximum delay time is given in the method `getConfigurationCapabilities`. |
| `vertices=Array of vertices` | The vertices of the polygon, given as an array of it x and y coordinates \[x, y\]. All vertices must be unique and the edges of the polygon can not cross each other. The coordinates are normalized to the size of the image and spans from -1 to 1 in both the horizontal and vertical direction. This means that the upper right corner has the coordinates \[1, 1\], while the lower left corner has the coordinates \[-1, -1\]. The coordinates must always be given for an image that is neither rotated or mirrored. The minimum number of vertices in a polygon is 3, the maximum is given by the method `getConfigurationCapabilities`. |
| `areaOverlay="none" | "always" | "if_triggered"` | Tells if and when the area should be included in the video stream and visible on recordings. The overlay color will change from green to red if the alarm is triggered. |
| `temperatureOverlay=<boolean>` | Indicates if the temperature of the area should be shown, but only when the area overlay is visible. The chosen measurement value is shown. |
| `presetNbr=<int>` | The preset number for the area. Will be ignored on non PTZ cameras and must be an existing preset number for PTZ cameras. |

**Return value - Failure**

-   **HTTP code**: `400 Bad request`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAreas",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listAreas"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getAreaStatus

This method should be used when you want to return the current temperature and trigger status of the active areas.

PTZ cameras will return either the status for the active areas on the current preset, or an empty status if not on preset positions

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAreaStatus"  "params": {  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAreaStatus"  "params": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getAreaStatus"` | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAreaStatus",  "data": {    "areaList": \[      {        "id": <int>,        "avg": <int>,        "min": <int>,        "max": <int>,        "minCoordinates": \[<float, float>\],        "maxCoordinates": \[<float, float>\],        "triggered": <boolean>,      }, ...    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getAreaStatus"` | The requested method. |
| `id=<int>` | The area ID. |
| `avg=<int>` | The average temperature of the area. |
| `min=<int>` | The minimum temperature of the area. |
| `max=<int>` | The maximum temperature of the area. |
| `minCoordinates=[<float, float>]` | The coordinates for the minimum temperature. Only the first found pixel with this temperature is returned. |
| `maxCoordinates=[<float, float>]` | The coordinates for the maximum temperature. Only the first found pixel with this temperature is returned. |
| `triggered=<boolean>` | Tells if the area alarm has been triggered. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAreaStatus",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getAreaStatus"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Could not get status for areas |

### addSpotTemperature

This method should be used when you want to activate the spot meter for the coordinates in the given coordinate system. Only one `spotTemperature` will be replaced will be replaced when a new one is called for. If the spot meter is activated on a specific image source, an overlay will be enabled on that channel.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addSpotTemperature",  "params": {    "spotCoordinates": \[<float, float>\],    "coordinateSystem": <string>,    "imagesource": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addSpotTemperature",  "params": {    "spotCoordinates": \[<float, float>\],    "coordinateSystem": <string>,    "imagesource": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="addSpotTemperature"` | The method that should be used. |
| `params.spotCoordinates=Array of coordinates` | The coordinates of the pixel of interest. |
| `params.coordinateSystem=<"coord_neg1_1" | "coord_0_1">` | The coordinate system for the given coordinates. Possible values are:  
  
\- `coord_neg1_1`: The point of origin is placed in the middle of the image, with coordinates going from -1 to 1 and increases from left to right or bottom to top of the image.:  
\- `coord_0_1`: The point of origin is located in the upper left corner of the image, with coordinates going from 0 to 1. |
| `params.imagesource=<int>` | The image source channel that shows the spot meter. Added in API version 1.3. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addSpotTemperature",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addSpotTemperature"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx/5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addSpotTemperature",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addSpotTemperature"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| 2104 | Invalid channel number specified. |

### getSpotTemperature

This method should be used when you want to check the temperature in the spot set by the method `addSpotTemperature`. If the spot meter is activated on a specific image source, an overlay will be enabled on that channel.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSpotTemperature",  "params": {    "coordinateSystem": <string>,    "imagesource": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSpotTemperature",  "params": {    "coordinateSystem": <string>,    "imagesource": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSpotTemperature"` | The method that should be used. |
| `params.coordinateSystem=<"coord_neg1_1" | "coord_0_1">` | The coordinate system for the spot meter. Possible values are:  
  
\- `coord_neg1_1`: The point of origin is placed in the middle of the image, with coordinates going from -1 to 1 and increases from left to right or bottom to top of the image.:  
\- `coord_0_1`: The point of origin is located in the upper left corner of the image, with coordinates going from 0 to 1. The chosen coordinate system does not need to be the same as the one used in `addSpotTemperature`. |
| `params.imagesource=<int>` | The image source channel that shows the current spot meter information. Added in API version 1.3. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSpotTemperature",  "data": {    "spotTemperature": <float>,    "spotCoordinates": \[<float>, <float>\],    "renderOverlay": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSpotTemperature"` | The requested method. |
| `data.spotTemperature=<float>` | The current temperature in the given coordinates. |
| `data.spotCoordinates=Array of coordinates` | The x and y coordinates of the spot temperature. |
| `data.renderOverlay=<boolean>` | If the spot meter overlay has been activated or not. |

**Return value - Failure**

-   **HTTP code**: \`\`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method":  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSpotTemperature"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| 2104 | Invalid channel number specified. |

### removeSpotTemperature

This method should be used when you want to remove the rendering of the spot meter. If the spot meter is activated on a specific image source, an overlay will be enabled on that channel and disabled when removed.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeSpotTemperature",  "params": {    "imagesource": <int>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeSpotTemperature",  "params": {    "imagesource": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="removeSpotTemperature"` | The method that should be used. |
| `params.imagesource=<int>` | The image source channel from which to remove the spot meter. Added in API version 1.3. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeSpotTemperature",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeSpotTemperature"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `400 Bad request`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeSpotTemperature",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeSpotTemperature"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| 2104 | Invalid channel number specified. |

### getTgtConfiguration

This method should be used when you want to retrieve the current configuration of the thermometric guard tour.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getTgtConfiguration"  "params": {}}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getTgtConfiguration"  "params": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getTgtConfiguration"` | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getTgtConfiguration",  "data": {    "pauseOnAlarm": <boolean>,    "autoResume": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getTgtConfiguration"` | The requested method. |
| `pauseOnAlarm=<boolean>` | The guard tour is paused on the preset when an event is active. |
| `autoResume=<boolean>` | Only valid if `pauseOnAlarm` is true. The guard tour will resume automatically after the event becomes inactive. It must be restarted manually otherwise. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getTgtConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getTgtConfiguration"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1202` | Method not supported: No guard tour settings available since camera is fixed. |

### setTgtConfiguration

This method should be used when you want to set the thermometric guard tour configuration.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTgtConfiguration"  "params": {    "pauseOnAlarm": <boolean>,    "autoResume": <boolean>  }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTgtConfiguration"  "params": {    "pauseOnAlarm": <boolean>,    "autoResume": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setTgtConfiguration"` | The method that should be used. |
| `pauseOnAlarm=<boolean>` | The guard tour is paused on the preset when an event is active. |
| `autoResume=<boolean>` | Only valid if `pauseOnAlarm` is true. The guard tour will resume automatically after the event becomes inactive. It must be restarted manually otherwise. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTgtConfiguration",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setTgtConfiguration"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setTgtConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setTgtConfiguration"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1202` | Method not supported: No guard tour settings available since camera is fixed. |

### addGroup

This method should be used when you want to add a new area group. A group is used to monitor and compare temperature conditions across multiple areas. The maximum number of groups per preset is given by the method `getConfigurationCapabilities`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "addGroup",    "params": {        "enabled": <boolean>,        "name": <string>,        "measurement": <string>,        "threshold": <int>,        "delay": <int>,        "areaIds": \[<int>, <int>, ...\],        "groupOverlay": <boolean>,        "presetNbr": <int>    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "addGroup",    "params": {        "enabled": <boolean>,        "name": <string>,        "measurement": <string>,        "threshold": <int>,        "delay": <int>,        "areaIds": \[<int>, <int>, ...\],        "groupOverlay": <boolean>,        "presetNbr": <int>    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="addGroup"` |  | The method that should be used. |
| `enabled=boolean` |  | Enables the group monitoring if `true`. The real value is returned in the response. |
| `name=<string>` |  | The group name. The maximum length is given by `getConfigurationCapabilities`. Supplying a name that is to long will result in an error (2104), or a name that is not unique (1200). |
| `measurement=<string>` | `maximum`, `minimum`, `average`, `inherit` | The value for each area in the group used for analysis. The alarm detection will use either `maximum`, `minimum` or `average` temperature for the respective areas in the group, while the `inherit` option will let the area´s own setting decide the value. |
| `threshold=<int>` |  | The allowed temperature difference from the resulting group analysis of the group area before an alarm is triggered. It is a positive value equal to or larger than 1. The allowed range is indirectly given by `getConfigurationCapabilities`. |
| `delay=<int>` |  | The number of seconds the trigger condition must be true before an alarm is triggered. If the delay time is zero the alarm will activate immediately when the trigger conditions are met. The maximum delay time is given by the `getConfigurationCapabilities`. |
| `areaIds=Array of <int>` |  | The area ID numbers of the areas in the group. In order to start analysis the number of areas must be at least 2. It is possible to set this parameter to fewer (or 0) areas, but doing so will lock `enabled` to `false` until there are enough areas. Changing areas are done with the method`updateGroup`. The upper area limit in the group is given by`getConfigurationCapabilities`. |
| `groupOverlay=<boolean>` |  | Whether or not to display an area overlay when a group is triggered. |
| `presetNbr=<int>` |  | The preset number associated with this group. It will be ignored for non PTZ cameras, where it must be an existing preset number. |

**Return value - Success**

If a group is successfully created, the method will return a unique ID for the group, starting with 1 (0 is never used as an ID) and if the group is enabled.

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "addGroup",    "data": {        "id": <int>,        "enabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 | The context set by the user in the request. |
| `method="addGroup"` | The requested method. |
| `id=<int>` | The new group ID. |
| `enabled=<boolean>` | The status of the new group. If the group's configuration is complete this will have the same value as in the request. Otherwise, it will be `false`. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "addGroup",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addGroup"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Group name is not unique. |
| `1200` | Maximum number of groups for this preset already reached. |
| `1200` | Preset does not exist. |
| `1200` | Group area configuration is invalid (area(s) disabled, not existing, not in valid preset, or area limit reached). |

### updateGroup

This method should be used when you want to update an existing group without changing its ID. The parameter `presetNbr` can not be changed once the group has been created by `addGroup`.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "updateGroup",    "params": {        "id": <int>,        "enabled": <boolean>,        "name": <string>,        "measurement": <string>,        "threshold": <int>,        "delay": <int>,        "areaIds": \[<int>, <int>, ...\],        "groupOverlay": <boolean>    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "updateGroup",    "params": {        "id": <int>,        "enabled": <boolean>,        "name": <string>,        "measurement": <string>,        "threshold": <int>,        "delay": <int>,        "areaIds": \[<int>, <int>, ...\],        "groupOverlay": <boolean>    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="updateGroup"` |  | The method that should be used. |
| `id=<int>` |  | The ID of the group that should be updated. |
| `enabled=boolean` |  | The requested enabled state. The actual value will be returned in the response since, depending on the rest of the group configuration, a group may not be enabled if this value is set to `true`. |
| `name=<string>` |  | The updated name of the group. |
| `measurement=<string>` | `maximum`, `minimum`, `average`, `inherit` | Changes the measurement type. See [addGroup](#addgroup) for details. |
| `threshold=<int>` |  | The updated threshold value. See See [addGroup](#addgroup) for details. |
| `delay=<int>` |  | The updated delay value. See [addGroup](#addgroup) for details. |
| `areaIds=Array of <int>` |  | Fully replace the current area IDs in the group with new ones. The array can be empty. The same rules for enabling the group as for [addGroup](#addgroup) applies. |
| `groupOverlay=<boolean>` |  | Change if the trigger overlay should be displayed. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "updateGroup",    "data": {        "enabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 | The context set by the user in the request. |
| `method="updateGroup"` | The requested method. |
| `enabled=<boolean>` | The status of the updated group. Depending on what was updated, the group may shift from enabled to disabled without a specific user request. See [addGroup](#addgroup) for details. Updating a group to be enabled does not guarantee it is actually enabled (depending on the rest of the group configuration), which means that this value is needed for confirmation. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "updateGroup",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="updateGroup"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Group ID is invalid. |
| `1200` | Group name is not unique. |
| `1200` | Group area configuration is invalid (area(s) disabled, not existing, not in valid preset, or area limit reached). |

### removeGroup

This method should be used when you want to remove one or all groups.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "removeGroup",    "params": {        "id": <int>    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "removeGroup",    "params": {        "id": <int>    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="removeGroup"` |  | The method that should be used. |
| `id=<int>` |  | The ID of the group that should be removed. Must be a positive number. Using the special ID `0` will remove all existing groups for all presets. Specifying a group that does not exist will result in an error. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "removeGroup",    "data": {    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 | The context set by the user in the request. |
| `method="removeGroup"` | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "removeGroup",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeGroup"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Group ID is invalid. |

### listGroups

This method should be used when you want to retrieve a list of groups for a provided preset number. If the preset number is `0`, all areas will be returned for all presets.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listGroups",    "params": {        "presetNbr": <int>    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listGroups",    "params": {        "presetNbr": <int>    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method=listGroups"` |  | The method that should be used. |
| `presetNbr=<int>`  
_Optional_  
 |  | The preset number for which the groups will be returned. If it is set to `0` or omitted, all groups for all presets will be returned. Specifying a preset that doesn't exist will result in an error. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listGroups",    "data": {        "grouplist": \[            {                "id":<int>,                "enabled": <boolean>,                "name": <string>,                "measurement": <string>,                "threshold": <int>,                "delay": <int>,                "areaIds": \[<int>, int, ...\],                "groupOverlay": <boolean>,                "presetNbr": <int>            }, ...        \]    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="listGroups"` |  | The requested method. |
| `id=<int>` |  | The ID of the group. |
| `enabled=boolean` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `name=<string>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `measurement=<string>` | `maximum`, `minimum`, `average`, `inherit` | The measurement type. See [addGroup](#addgroup) for details. |
| `threshold=<int>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `delay=<int>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `areaIds=Array of <int>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `groupOverlay=<boolean>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |
| `presetNbr=<int>` |  | See [addGroup](#addgroup) for an explanation of this parameter. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listGroups",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listGroups"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1200` | Preset does not exist. |

### getGroupStatus

This method should be used when you want to return the current trigger status of active groups. PTZ cameras will return the status of active groups on the current preset, or an empty status if not standing on a preset.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getGroupStatus",    "params": {    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getGroupStatus",    "params": {    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="getGroupStatus"` |  | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getGroupStatus",    "data": {        "grouplist": \[            {                "id":<int>,                "triggered": <boolean>,                "details": {                    "name": <string>,                    "currentDeviation": <float>,                    "memberAreas": \[                        {"areaId": <int>, "areaName": <string>},                        {"areaId": <int>, "areaName": <string>},                        ...                    \],                    "maxDeviationAreas": \[                        {"maxAreaId": <int>, "maxAreaTemp": <float>},                        {"minAreaId": <int>, "minAreaTemp": <float>}                    \]                }            }        \]    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="getGroupStatus"` |  | The requested method. |
| `id=<int>` |  | The ID of the group. |
| `triggered=<boolean>` |  | Tells if the alarm has been triggered for a group. |
| `details=<{}>` |  | Contains specific data about the group's current status. To accomodate future extension, the contents of this parameter is dynamic to change, including being empty. The currently supported format include the following parameters: |

**`details=<{}>` parameters**

| Parameter | Sub-parameters | Description |
| --- | --- | --- |
| `name=<string>` |  | The name of the group. |
| `currentDeviation=<float>` |  | The current maximum deviation within the group. |
| `memberAreas=<[{}]>` | `areaId`, `areaName` | The group's areas. |
| `areaId=<int>` |  | The ID of an area in a group. |
| `areaName=<string>` |  | The name of an area in a group. |
| `maxDeviationAreas=<[{}]>` | `maxAreaId`, `maxAreaTemp`, `minAreaId`, `minAreaTemp` | The currently most and least deviating area in the group. |
| `maxAreaId=<int>` |  | The area ID of the most deviating area. |
| `maxAreaTemp=<float>` |  | The temperature of the most deviating area. |
| `minAreaId=<int>` |  | The area ID of the least deviating area. |
| `minAreaTemp=<float>` |  | The temperature of the least deviating area. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getGroupStatus",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getGroupStatus"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### addOverlayChannel

This method should be used when you want to add an overlay channel with visible area overlays. This means that overlay channels added with this API can show area overlays created by a specific image source. Image sources and overlay channels are listed by [getConfigurationCapabilities](#getconfigurationcapabilities).

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "addOverlayChannel",    "params": {      "imagesource": "<int>",      "overlayChannel": "<int>"    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "addOverlayChannel",    "params": {      "imagesource": "<int>",      "overlayChannel": "<int>"    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="addOverlayChannel"` |  | The method that should be used. |
| `imagesource=<int>` |  | The image source for the specified area. |
| `overlayChannel=<int>` |  | The channel that displays/enables area overlays. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<Major>.<Minor>",    "context": "<string>",    "method": "addOverlayChannel",    "data": {}}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="addOverlayChannel"` |  | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "addOverlayChannel",    "error": {        "code": "<integer error code>",        "message": "<string>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="addOverlayChannel"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### removeOverlayChannel

This method should be used when you want to remove an overlay channel with visible area overlays. This means that overlay channels removed with this API can't show area overlays created by a specific image source. Image sources and overlay channels are listed by [getConfigurationCapabilities](#getconfigurationcapabilities).

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "removeOverlayChannel",    "params": {      "imagesource": "<int>",      "overlayChannel": "<int>"    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "removeOverlayChannel",    "params": {      "imagesource": "<int>",      "overlayChannel": "<int>"    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="removeOverlayChannel"` |  | The method that should be used. |
| `imagesource=<int>` |  | The image source for the specified area. |
| `overlayChannel=<int>` |  | The channel that disables area overlays. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<Major>.<Minor>",    "context": "<string>",    "method": "removeOverlayChannel",    "data": {}}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="removeOverlayChannel"` |  | The requested method. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "removeOverlayChannel",    "error": {        "code": "<integer error code>",        "message": "<string>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="removeOverlayChannel"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### listOverlayChannels

This method should be used when you want to list all active overlay channels and their image sources.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "listOverlayChannels",    "params": {    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "listOverlayChannels",    "params": {    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="listOverlayChannels"` |  | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<Major>.<Minor>",    "context": "<string>",    "method": "listOverlayChannels",    "data": {        "overlayList": \[            {                "imagesource": "<int>",                "overlayChannels": \["<int>, <int>, .."\]            }        \]    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="listOverlayChannels"` |  | The requested method. |
| `imagesource=<int>` |  | A channel where a thermal image can originate from. Product dependant. |
| `overlayChannels=<int>` |  | A channel where overlays, such as area and spot meter overlays, can appear. Different than the image source. |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listOverlayChannels",    "error": {        "code": "<integer error code>",        "message": "<string>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listOverlayChannels"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### listSpotMeters

This method should be used when you want to check a list and the state of channels with a spot meter.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/thermometry.cgi" \\  --data '{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "listSpotMeters",    "params": {    }}'
```

```bash
POST /axis-cgi/thermometry.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major.minor>",    "context": "<string>",    "method": "listSpotMeters",    "params": {    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>`  
_Optional_  
 |  | The user sets this value and the application echoes it back in the response . |
| `method="listSpotMeters"` |  | The method that should be used. |

**Return value - Success**

-   **HTTP code**: 200 OK
-   **Content-Type**: `application-json`

Response body syntax

```bash
{    "apiVersion": "<Major>.<Minor>",    "context": "<string>",    "method": "listSpotMeters",    "data": {        "spotmeters": \[            {                "imagesource": "<int>",                "active": "<boolean>"            }        \]    }}
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>`  
_Optional_  
 |  | The context set by the user in the request. |
| `method="listSpotMeters"` |  | The requested method. |
| `imagesource=<int>` |  | A channel number where the spot meter can be enabled. |
| `active=<boolean>` |  | Indicates whether the spot meter is enabled (`true`) or disabled (`false`). |

**Return value - Failure**

-   **HTTP code**: `4xx / 5xx`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listSpotMeters",    "error": {        "code": "<integer error code>",        "message": "<string>"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listSpotMeters"` | The requested method. |
| `code=<integer>` | The error code. |
| `message=<string>` | The message corresponding to the error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### Temperature area event

This event will be `true` if all conditions for an area is fulfilled.

-   **Topic**: `tns1:VideoSource/tns1:RadiometryAlarm/tnsaxis:TemperatureDetection`
-   **Type**: Stateful
-   **Nice name**: `Temperature Area Alarm`

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| `AreaID` | Integer | Area ID | The temperature alarm area. | `0..maxAreas-1` |
| `AlarmActive` (STATE) | Boolean | Alarm Activated | True when active. | `true/false` |
| `AreaName` | String | Area Name | Name of the area. | `Max 60 characters` |
| `PresetNbr` | Integer | Preset Token | The preset number that the area belongs to. Only present for PTZ-enabled cameras. | `1..maxPresetNbr` |
| `AverageTemp` | Float | Average Temperature | The average area temperature. | `-40..700` |
| `MaximumTemp` | Float | Maximum Temperature | The maximum area temperature. | `-40..700` |
| `MinimumTemp` | Float | Minimum Temperature | The minimum area temperature. | `-40..700` |
| `TemperatureUnit` | String | Temperature Unit | The used temperature unit. | `Celsius or Fahrenheit` |
| `MaxTempPositionX` | Float | Maximum Temperature X Position | The X coordinate for maximum temperature. | `-1..1` |
| `MaxTempPositionY` | Float | Maximum Temperature Y Position | The Y coordinate for maximum temperature. | `-1..1` |
| `MinTempPositionX` | Float | Minimum Temperature X Position | The X coordinate for minimum temperature. | `-1..1` |
| `MinTempPositionY` | Float | Minimum Temperature Y Position | The Y coordinate for minimum temperature. | `-1..1` |

### Temperature Any Area Event

The Temperature Any Area Event is true if the conditions for any area is fulfilled.

-   **Topic:** `tns1:VideoSource/tns1:RadiometryAlarm/tnsaxis:TemperatureDetectionAnyArea`
-   **Type:** Stateful
-   **Nice name:** `Temperature Any Area Alarm`

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| `AreaName` | String | Area Name | AnyArea | `Max 60 characters` |
| `AlarmActive` (STATE) | Boolean | AlarmActivated | True when active, otherwise false | true/false |

### Temperature Any Area On Preset Event

The Temperature Any Area On Preset Event is assigned to a unique preset position. The event is true if the conditions for any area on the selected preset is fulfilled.

-   **Topic:** `tns1:VideoSource/tns1:RadiometryAlarm/tnsaxis:TemperatureDetectionAnyAreaOnPreset`
-   **Type:** Stateful
-   **Nice name:** `Temperature Any Area On Preset Alarm`

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| `PresetNbr` | Integer | Preset Token | The preset number that the area belongs to. Only present on PTZ-enabled cameras. | `1..maxPresetNbr` |
| `AlarmActive` (STATE) | Boolean | Alarm Activated | True when active, otherwise false. | true/false |
| `AreaName` | String | Area Name | AnyAreaOnPreset | `Max 60 characters` |

### Temperature information event

This event is uniquely assigned to an area. An update event is sent to each existing area every 30 seconds.

-   **Topic**: `tns1:VideoSource/tns1:Thermometry/tnsaxis:TemperatureDetection`
-   **Type**: Stateless
-   **Nice name**: `Temperature Detection`

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| `AreaID` | Integer | Area ID | The temperature alarm area. | `0..maxAreas-1` |
| `AreaName` | String | Area Name | Name of the area. | `Max 60 characters` |
| `PresetNbr` | Integer | Preset Token | The preset number that the area belongs to. Only present for PTZ-enabled cameras. | `1..maxPresetNbr` |
| `AverageTemp` | Float | Average Temperature | The average area temperature. | `-40..700` |
| `MaximumTemp` | Float | Maximum Temperature | The maximum area temperature. | `-40..700` |
| `MinimumTemp` | Float | Minimum Temperature | The minimum area temperature. | `-40..700` |
| `TemperatureUnit` | String | Temperature Unit | The used temperature unit. | `Celsius or Fahrenheit` |
| `MaxTempPositionX` | Float | Maximum Temperature X Position | The X coordinate for maximum temperature. | `-1..1` |
| `MaxTempPositionY` | Float | Maximum Temperature Y Position | The Y coordinate for maximum temperature. | `-1..1` |
| `MinTempPositionX` | Float | Minimum Temperature X Position | The X coordinate for minimum temperature. | `-1..1` |
| `MinTempPositionY` | Float | Minimum Temperature Y Position | The Y coordinate for minimum temperature. | `-1..1` |

### Temperature deviation detection event

This event is used for enabled area groups that will emit an event when its configured criteria is met.

-   **Topic**: `tns1:VideoSource/tns1:RadiometryAlarm/tnsaxis:DeviationDetection`
-   **Type**: Stateful
-   **Nice name**: `Temperature Deviation Alarm`

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| `GroupID` | Integer | GroupID | The ID of the triggered groups. | 1 .. `maxGroups` |
| `AlarmActive` (STATE) | Boolean | Alarm Activated | `true` if active, otherwise `false` | `true` / `false` |
| `GroupName` | String | Group Name | The name of the triggered group. | Max 60 characters |
| `DeltaTemp` | Float | Delta Temp for Deviation Alarm | The maximum delta between area temperatures in the group. | 0 .. 700 |
| `ThresholdTemp` | Float | Threshold Temp for Deviation Alarm | The temperature threshold that should be exceeded for the event to trigger. | 1 .. 700 |
| `PresetNbr` | Integer | Preset Token | The preset number that the group belongs to. Only present on PTZ-enabled cameras. | 1 .. `maxPresetNbr` |
| `PresetName` | String | Preset Name | The name of the preset that the group belongs to. Only present on PTZ-enabled cameras. | Max 60 characters |

### General error codes

The following table consist of errors that may occur for any method. Errors specific to a method are listed under their separate API description. The error codes exist in the following ranges.

-   1100–1199
    
    Generic error codes common for many APIs and reserved for server errors such as "Maximum number of configurations reached". The actual cause can be seen in the server log and can sometimes be solved by restarting the device.
    
-   1200–1999
    
    API-specific server errors that may collide between different APIs.
    
-   2100–2199
    
    Generic error codes common to many APIs and reserved for client errors such as "Invalid parameter". These errors should be possible to solve by changing the input data to the API.
    
-   2200–2999
    
    API-specific client errors that may collide between different APIs.
    

info

The 4–digit error codes are returned in the JSON body when the service is executed, which means that the client must be prepared to handle transport-level errors codes with non-JSON responses. Specifically, HTTP error 401/403 will be emitted if either authentication or authorization fails.

| JSON code | HTTP code | Description |
| --- | --- | --- |
| `1100` | `500` | Internal error.([1](#user-content-fn-1)) |
| `2100` | `400` | API version not supported. |
| `2101` | `400` | Invalid JSON format. |
| `2102` | `400` | Method not supported. |
| `2103` | `400` | Required parameter missing. |
| `2104` | `400` | Invalid parameter value specified. |
| `2105` | `400` | Invalid arguments |
| `2106` | `400` | Invalid request method |
| `2107` | `400` | Invalid content length |
| `2108` | `400` | Invalid content type |
| `2109` | `403` | Authorization failed |
| `2110` | `401` | Authentication failed |

## Footnotes

1.  Out-of-memory errors will also be reported as 1100 Internal error. [↩](#user-content-fnref-1)