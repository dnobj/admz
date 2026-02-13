---
title: Power settings
url: "https://developer.axis.com/vapix/network-video/power-settings/"
category: vapix
subcategory: network-video
sha256: f4c3be04f98a3b58c09958b383dc9ca635f2686c54a3c843866d4185922c0dc1
scraped_at: "2026-01-09T15:20:43.338Z"
page_height: 91232
---

# Power settings

The VAPIX® Power settings API provides the methods and parameters that makes it possible to control the power settings on your Axis devices.

## Overview

The API uses the `/axis-cgi/power-settings.cgi` as its communication interface and supports the following methods:

| Method | Description |
| --- | --- |
| [getSupportedVersions](#getsupportedversions) | Retrieves the API versions supported by your Axis device. |
| [getCapabilities](#getcapabilities) | Retrieves supported product capabilities. |
| [getPowerSavingMode](#getpowersavingmode) | Retrieves the current state of the Power saving mode from your Axis device |
| [setPowerSavingMode](#setpowersavingmode) | Applies the requested state of the Power saving mode to your Axis device. |
| [getDelayedPowerDownMode](#getdelayedpowerdownmode) | Retrieves the current state of the delayed power down mode from your Axis device. |
| [setDelayedPowerDownMode](#setdelayedpowerdownmode) | Applies the requested state of the delayed power down mode on your Axis device. |
| [getPowerStatus](#getpowerstatus) | Retrieves power status for your Axis device. |
| [getPowerConsumers](#getpowerconsumers) | Retrieves a list containing available power consumers for your Axis device. |
| [setPowerConsumer](#setpowerconsumer) | Applies the requested properties to a power consumer on your Axis device. |
| [getPowerProfiles](#getpowerprofiles) | Retrieves a list of available power profiles on your Axis device. |
| [setPowerProfile](#setpowerprofile) | Applies the requested power profile to your Axis device. |
| [getPowerConfigurations](#getpowerconfigurations) | Retrieves a list of available power configurations on your Axis device. |
| [getActivePowerConfiguration](#getactivepowerconfiguration) | Retrieves the active power configuration on your Axis device. |
| [setActivePowerConfiguration](#setactivepowerconfiguration) | Applies the requested active power configuration to your Axis device. |
| [getDynamicPowerMode](#getdynamicpowermode) | Retrieves the current state of Dynamic Power Mode. |
| [setDynamicPowerMode](#setdynamicpowermode) | Applies the requested state of Dynamic Power Mode. |
| [getPowerHistory](#getpowerhistory) | Retrieves power history data from your Axis device. |
| [getPowerWarningOverlay](#getpowerwarningoverlay) | Checks if the power warning overlay is enabled. |
| [setPowerWarningOverlay](#setpowerwarningoverlay) | Enable or disable the power warning overlay by setting the parameter to either `true` or `false`. |
| [getIoPortPower](#getioportpower) | Check if IO Port Power is enabled. |
| [setIoPortPower](#setioportpower) | Enable or disable IO port power. |

### General concepts
#### Power-saving mode

The power-saving mode lowers the power consumption of your Axis device while maintaining its overall operational performance. This feature is recommended for larger camera installations, where it can lower the continuous power consumption and reduce the overall energy cost. A user with operator level access and higher can either manually, or by triggering pre-configured conditions, turn off the power saving mode without rebooting the device. This is useful if optimal image quality is necessary.

#### Delayed power down mode

Some Axis devices have an extra pin that can be connected to the ignition of a vehicle. This means that the vehicle can control whether your camera should be active and can be enabled by setting `delayedPowerDown` to `true`. By extension, this also means that the camera will stop recording when you turn off the vehicle. You are also able to set a timer, but only when `delayedPowerDown` is `true`. Doing this will delay the power down of the camera, which is useful when the vehicle is making several short stops, or the driver leaves the vehicle, and you want to continue the recording.

#### Power status

Power status is a selection of information and statistics about the total power consumption of your device and may be used by the products web interface.

#### Power consumers

The maximum power consumption can be changed on either selected parts of a device or allow a functionality to be disabled by the user. This makes it possible to reduce the power consumption, or redirect more of the available power according to meet the current requirements.

Caution

> This feature should only be used with great knowledge of the device since it will affect the product’s sensitivity and limitations regarding temperature and condensation.

#### Power profiles

A power profile is a pre-defined configuration of power consumer settings that allows the user to change the power consumption by using officially tested settings. This includes documented limitations for temperature and condensation.

#### Power configurations

Some devices allow the user to completely change their power configurations. This means that it is possible to set different configurations, or priorities for PoE 3 and PoE 4, in order to limit the total power usage and change power related behaviors of the device.

#### Dynamic power mode

This configuration can be used to lower the performance and power consumption of the system during periods of inactivity when a full performance is not required. The amount of power drawn is product dependant and the functionality is able to increase the latency of the initial video start by up to a fraction of a second, which means that the product performance won’t be noticeable affected.

#### Power history

This configuration is used by devices with the hardware support to measure the momentary power draw. Power history is set up to record the power consumption of the device and allows the user to plot the power consumption over various time intervals. This means that you are able to see how the power consumption varies over the span of a day/night cycle, in a particular climate or over the seasons for the last day, week, year, etc.

#### Disable power warning overlay

Some products support a text overlay warning about insufficient Power over Ethernet. For those products, the system will use the enabled overlay when appropriate unless the overlay is actively turned off by the user.

#### IO Port Power

Some products can turn on/off the 12 volt power of the IO connector. The extra power can then be used by another power consumer in the camera, such as the heater, IR or deep learning.

### Identification

-   **API Discovery**: `id=power-settings`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Power saving mode

This example will show you how to control the power consumption on your Axis device.

1.  Request a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Failed response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

See [getSupportedVersions](#getsupportedversions) for further details.

3.  Request the capabilities that will verify if the device supports the power saving mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getCapabilities",    "params": {}}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getCapabilities",    "params": {}}
```

4.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.5",    "context": "abc",    "method": "getCapabilities",    "data": {        "powerSavingSupport": true,        "delayedPowerDownSupport": false,        "powerProfileSupport": true,        "powerConsumerSupport": true,        "powerStatusSupport": true,        "powerConfigurationSupport": false,        "dynamicPowerModeSupport": true,        "powerHistorySupport": true    }}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getCapabilities",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

See [getCapabilities](#getcapabilities) for further details.

5.  Request information about the power saving mode and verify its present state.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getPowerSavingMode",    "params": {}}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getPowerSavingMode",    "params": {}}
```

6.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPowerSavingMode",    "data": {        "powerSavingMode": true    }}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPowerSavingMode",    "error": {        "code": 300,        "message": "Power saving mode is not supported."    }}
```

See [getPowerSavingMode](#getpowersavingmode) for further details.

7.  Activate the Power saving mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setPowerSavingMode",    "params": {        "powerSavingMode": true    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setPowerSavingMode",    "params": {        "powerSavingMode": true    }}
```

8.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPowerSavingMode",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPowerSavingMode",    "error": {        "code": 301,        "message": "Unable to store Power saving mode."    }}
```

See [setPowerSavingMode](#setpowersavingmode) for further details.

### Delayed power down mode

This example will show you how to configure the camera to power down after a predefined amount of time, for example when the motor of a vehicle in a surveilled zone is shut down.

1.  Verify the current state of the delayed power down mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "getDelayedPowerDownMode",    "params": {}}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "getDelayedPowerDownMode",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getDelayedPowerDownMode",    "data": {        "delayedPowerDownMode": true,        "delayTime": 30    }}
```

Failed response

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getDelayedPowerDownMode",    "error": {        "code": 300,        "message": "Delayed power down mode is not supported."    }}
```

3.  Activate the delayed power down mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.1",    "context": "abc",    "method": "setDelayedPowerDownMode",    "params": {        "delayedPowerDownMode": true,        "delayTime": 30    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.1",    "context": "abc",    "method": "setDelayedPowerDownMode",    "params": {        "delayedPowerDownMode": true,        "delayTime": 30    }}
```

4.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setDelayedPowerDownMode",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "setDelayedPowerDownMode",    "error": {        "code": 301,        "message": "Unable to set delayed power down mode."    }}
```

See [getDelayedPowerDownMode](#getdelayedpowerdownmode) and [setDelayedPowerDownMode](#setdelayedpowerdownmode) for further details.

### Power status information

This example will show you how to verify the power consumption of your device by initiating a health check that will investigate if the power consumption correspond to the device configuration.

1.  Request the current power status of your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerStatus"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerStatus"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerStatus",    "data": {        "usage": {            "currentPower": 60.0,            "averagePower": 60.0,            "maxPower": 60.0        },        "psePoeClass": 4,        "lldpPoeClass": 4,        "powerRequested": 30.0    }}
```

Failed response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerStatus",    "error": {        "code": 300,        "message": "Power status is not supported."    }}
```

See [getPowerStatus](#getpowerstatus) for further details.

### Check power consumer information

This example will show you how to check the power consumption of your device by listing all power consumers and how they can be changed to optimize power requirements.

1.  Request the available power consumers from the product.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerConsumers"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerConsumers"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerConsumers",    "data": {        "consumers": \[            {                "powerConsumer": "WindowHeater",                "type": "Heater",                "maxPower": 5.0,                "adjustablePower": true,                "enabled": true            }        \]    }}
```

Failed response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerConsumers",    "error": {        "code": 300,        "message": "Power consumers is not supported."    }}
```

See [getPowerConsumers](#getpowerconsumers) for further details.

### Configure power consumers

This example will show you how to configure the power consumption of the heater on your device.

1.  Configure a power consumer on your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerConsumer",    "params": {        "powerConsumer": "WindowHeater",        "maxPower": 5.0,        "enabled": true    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerConsumer",    "params": {        "powerConsumer": "WindowHeater",        "maxPower": 5.0,        "enabled": true    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerConsumer",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerConsumer",    "error": {        "code": 301,        "message": "Unable to set power consumer."    }}
```

See [setPowerConsumer](#setpowerconsumer) for further details.

### Retrieve power profile information

This example will show you how to control the power consumption on your device by listing pre-defined configurations of power consumers found on your device.

1.  Request a list containing all available power profiles on your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerProfiles"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerProfiles"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerProfiles",    "data": {        "currentPowerProfile": "Default",        "profiles": \[            {                "powerProfile": "Default",                "powerRank": 10,                "lowerTemperature": -50,                "upperTemperature": 50,                "labels": \["highPerformance", "temperatureRange"\],                "default": true,                "consumers": \[                    {                        "powerConsumer": "WindowHeater",                        "maxPower": 5.0,                        "enabled": true                    }                \]            },            {                "powerProfile": "LimitedTemperatureRange",                "powerRank": 1,                "lowerTemperature": 0,                "upperTemperature": 50,                "labels": \["lowPower", "temperatureRange", "disableHeaters"\],                "default": false,                "consumers": \[                    {                        "powerConsumer": "WindowHeater",                        "maxPower": 5.0,                        "enabled": false                    }                \]            }        \]    }}
```

Failed response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "getPowerProfiles",    "error": {        "code": 300,        "message": "Power profiles is not supported."    }}
```

See [getPowerProfiles](#getpowerprofiles) for further details.

### Set a pre-defined power profile

This example will show you how to control the power consumption of your device by using a pre-defined and tested configuration for the available power consumers.

1.  Configure a power profile on your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerProfile",    "params": {        "powerProfile": "LimitedTemperatureRange"    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerProfile",    "params": {        "powerProfile": "LimitedTemperatureRange"    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerProfile",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.2",    "context": "abc",    "method": "setPowerProfile",    "error": {        "code": 301,        "message": "Unable to set power profile."    }}
```

See [setPowerProfile](#setpowerprofile) for further details.

### Power configurations

This example will show you how to control the power consumption of your device to reduce the operating cost of the installation by listing and applying supported and active power configurations.

**Check available power configurations**

1.  Retrieve a list containing all available power configurations on your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.4",    "context": "abc",    "method": "getPowerConfigurations"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "context": "abc",    "method": "getPowerConfigurations"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "getPowerConfigurations",    "data": {        "powerConfigurations": \[            {                "index": 0,                "name": "PoE 4"            },            {                "index": 1,                "name": "PoE 3"            }        \]    }}
```

Failed response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "getPowerConfigurations",    "error": {        "code": 300,        "message": "Power configurations are not supported."    }}
```

See [getPowerConfigurations](#getpowerconfigurations) for further details.

**Check active power configuration**

1.  Check your device to see the currently active power configuration.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.4",    "context": "abc",    "method": "getActivePowerConfiguration"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "context": "abc",    "method": "getActivePowerConfiguration"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "getActivePowerConfiguration",    "data": {        "index": 0    }}
```

Failed response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "getActivePowerConfiguration",    "error": {        "code": 300,        "message": "Power configurations are not supported."    }}
```

See [getActivePowerConfiguration](#getactivepowerconfiguration) for further details.

**Apply a power configuration**

1.  Change the active power configuration.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.4",    "context": "abc",    "method": "setActivePowerConfiguration",    "params": {        "index": 2    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.4",    "context": "abc",    "method": "setActivePowerConfiguration",    "params": {        "index": 2    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "setActivePowerConfiguration",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.4",    "context": "abc",    "method": "setActivePowerConfiguration",    "error": {        "code": 301,        "message": "Unable to set power configuration."    }}
```

See [setActivePowerConfiguration](#setactivepowerconfiguration) for further details.

### Dynamic power mode

This example will show you how to disable the dynamic power mode when you wish to lower the video latency.

**Check dynamic power mode**

1.  Retrieve the current state of the dynamic power mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.5",    "context": "abc",    "method": "getDynamicPowerMode",    "params": {}}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.5",    "context": "abc",    "method": "getDynamicPowerMode",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.5",    "context": "abc",    "method": "getDynamicPowerMode",    "data": {        "dynamicPowerMode": true    }}
```

Failed response

```bash
{    "apiVersion": "1.5",    "context": "abc",    "method": "getDynamicPowerMode",    "error": {        "code": 300,        "message": "Dynamic power mode is not supported."    }}
```

See [getDynamicPowerMode](#getdynamicpowermode) for further details.

3.  Disable dynamic power mode.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.5",    "context": "abc",    "method": "setDynamicPowerMode",    "params": {        "dynamicPowerMode": false    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.5",    "context": "abc",    "method": "setDynamicPowerMode",    "params": {        "dynamicPowerMode": false    }}
```

4.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.5",    "context": "abc",    "method": "setDynamicPowerMode",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.5",    "context": "abc",    "method": "setDynamicPowerMode",    "error": {        "code": 301,        "message": "Unable to store dynamic power mode."    }}
```

See [setDynamicPowerMode](#setdynamicpowermode) for further details.

### Power history

This example will show you how to collect data on your camera’s power consumption without the need for external tools.

1.  Request a list containing the power consumption over a specific time period.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.6",    "context": "abc",    "method": "getPowerHistory",    "params": {        "requestedTimeSpan": 7200    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.6",    "context": "abc",    "method": "getPowerHistory",    "params": {        "requestedTimeSpan": 7200    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.6",    "context": "abc",    "method": "getPowerHistory",    "data": {        "acquiredTimeSpan": 14400,        "numberOfSamples": 16,        "endTimeStamp": "2023-01-23T14:00:01.549356Z",        "powerMeasurements": \[            49.939, 49.893, 49.933, 49.954, 49.949, 49.936, 49.847, 49.929, 49.923, 49.952, 49.962, 49.858, 49.973,            49.964, 49.882, 49.964        \],        "powerAverage": 49.929    }}
```

Failed response

```bash
{    "apiVersion": "1.6",    "context": "abc",    "method": "getPowerHistory",    "error": {        "code": 300,        "message": "Power history is not supported."    }}
```

See [getPowerHistory](#getpowerhistory) for further details.

### Disable the power warning overlay

This example will show you how to remove the text overlay warning about too low power levels after connecting a camera to a lower PoE class switch than what is normally required for full functionality.

1.  Disable the overlay with the method `setPowerWarningOverlay`.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.7",    "context": "abc",    "method": "setPowerWarningOverlay",    "params": {        "enable": false    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.7",    "context": "abc",    "method": "setPowerWarningOverlay",    "params": {        "enable": false    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.7",    "context": "abc",    "method": "setPowerWarningOverlay",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.7",    "context": "abc",    "method": "setPowerWarningOverlay",    "error": {        "code": 301,        "message": "Unable to disable Power Warning Overlay."    }}
```

See [setPowerWarningOverlay](#setpowerwarningoverlay) for further details.

### Control the IO Port Power

This example will show you how to connect an accessory to the camera that requires 12 volt on the IO port. Note that the 12 volt pin in the IO port needs to be enabled for this method to work.

#### Get the current state of the IO Port Power

1.  Use `IoPortPower` to read the current state of IO Port Power. It can be either enabled or disabled.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.9",    "context": "abc",    "method": "getIoPortPower",    "params": {}}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.9",    "context": "abc",    "method": "getIoPortPower",    "params": {}}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.9",    "context": "abc",    "method": "getIoPortPower",    "data": {        "enabled": true    }}
```

Failed response

```bash
{    "apiVersion": "1.9",    "context": "abc",    "method": "getIoPortPower",    "error": {        "code": 300,        "message": "Get IO Port Power is not supported."    }}
```

See [getIoPortPower](#getioportpower) for further details.

#### Enable IO Port Power

1.  Use `setIoPortPower` to enable or disable IO Port Power.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{    "apiVersion": "1.9",    "context": "abc",    "method": "setIoPortPower",    "params": {        "enable": true    }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.9",    "context": "abc",    "method": "setIoPortPower",    "params": {        "enable": true    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.9",    "context": "abc",    "method": "setIoPortPower",    "data": {}}
```

Failed response

```bash
{    "apiVersion": "1.9",    "context": "abc",    "method": "setIoPortPower",    "error": {        "code": 301,        "message": "Unable to set IO Port Power to its new state."    }}
```

See [setIoPortPower](#setioportpower) for further details.

## API specification
### getSupportedVersions

This method should be used when you want to retrieve a list containing all API versions supported by your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested method. |
| `data.apiVersions[]=<list of versions>` | A list containing all supported major versions along with their highest minor version, e.g. `["1.0", "1.2"]`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes)for a complete list of potential errors.

### getCapabilities

This method should be used when you want to retrieve the different capabilities that can be controlled.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getCapabilities"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion: "<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getCapabilities"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getCapabilities",  "data": {    "powerSavingSupport": <boolean>,    "delayedPowerDownSupport": <boolean>,    "powerProfileSupport": <boolean>,    "powerConsumerSupport": <boolean>,    "powerStatusSupport": <boolean>,    "powerConfigurationSupport": <boolean>,    "dynamicPowerModeSupport": <boolean>,    "powerHistorySupport": <boolean>,    "disablePowerWarningOverlaySupport": <boolean>,    "ioPortPowerSupport": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion: "<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getCapabilities"` | The requested method. |
| `data.powerSavingSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support Power saving mode. `false` if the device doesn’t support Power saving mode. |
| `data.delayedPowerDownSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support Delayed power down mode. `false` if the device doesn’t support Delayed power down mode. |
| `data.powerProfileSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support power profiles. `false` if the device doesn’t support power profiles. |
| `data.powerConsumerSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support power consumers. `false` if the device doesn’t support power consumers. |
| `data.powerStatusSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support power status. `false` if the device doesn’t support power status. Please note that the value will be `-1` if the parameter isn’t available on your device. |
| `data.powerConfigurationSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device support power configurations. `false` if the device doesn’t support power configurations. |
| `data.dynamicPowerModeSupport=<boolean>` | A boolean returning one of the following responses: `true` if the device supports dynamic power mode. `false` if the device doesn’t support dynamic power mode. |
| `data.powerHistorySupport=<boolean>` | A boolean returning one of the following responses: `true` if the device supports power history. `false` if the device doesn’t support power history. |
| `data.disablePowerWarningOverlaySupport=<boolean>` | A boolean returning `true` if the the device can toggle the power warning overlay and `false` if power warning overlay handing is not supported. |
| `data.ioPortPowerSupport=<boolean>` | A boolean returning `true` if the device can toggle IO Port Power on or off and `false` if it is not supported. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "method": "getCapabilities",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getCapabilities"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerSavingMode

This method should be used when you want to retrieve the current state of the power saving mode.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerSavingMode"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerSavingMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerSavingMode"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>"  "context": "<string>",  "method": "getPowerSavingMode",  "data": {    "powerSavingMode": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerSavingMode"` | The requested method. |
| `data.powerSavingMode=<boolean>` | A boolean returning the state of the power saving mode: `true` if power saving mode is active. `false` if power saving mode is not active. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerSavingMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerSavingMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getPowerSavingMode

| Code | Description |
| --- | --- |
| `300` | Power saving mode is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setPowerSavingMode

This method should be used when you want to apply a new state to the Power saving mode.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerSavingMode",  "params": {    "powerSavingMode": <boolean>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerSavingMode",  "params": {    "powerSavingMode": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setPowerSavingMode"` | The method that should be used. |
| `params.powerSavingMode=<boolean>` | A boolean applying the state for the Power saving mode. `true` activates power saving mode. `false` deactivates power saving mode. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>"  "context": "<string>",  "method": "setPowerSavingMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerSavingMode"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerSavingMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerSavingMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setPowerSavingMode

| Code | Description |
| --- | --- |
| `300` | Power saving mode is not supported. |
| `301` | Unable to store Power saving mode. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getDelayedPowerDownMode

This method should be used when you want to retrieve the current state of the delayed power down mode.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDelayedPowerDownMode"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDelayedPowerDownMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getDelayedPowerDownMode"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>"  "context": "<string>",  "method": "getDelayedPowerDownMode",  "data": {    "delayedPowerDownMode": <boolean>,    "delayTime": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerSavingMode"` | The requested method. |
| `data.delayedPowerDownMode=<boolean>` | A boolean returning the state of the delayed power down mode: `true` if delayed power down mode is active. `false` if delayed power down mode is not active. |
| `data.delayTime=<integer>` | An integer returning the delay time in seconds. It is not used if `delayedPowerDownMode` is `false`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDelayedPowerDownMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getDelayedPowerDownMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getDelayedPowerDownMode

| Code | Description |
| --- | --- |
| `300` | Delayed power down mode is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setDelayedPowerDownMode

This method should be used when you want to apply a new state to the delayed power down mode.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDelayedPowerDownMode",  "params": {    "delayedPowerDownMode": <boolean>,    "delayTime": <integer>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDelayedPowerDownMode",  "params": {    "delayedPowerDownMode": <boolean>,    "delayTime": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setDelayedPowerDownMode"` | The method that should be used. |
| `params.delayedPowerDownMode=<boolean>` | A boolean applying the state for the delayed power down mode. `true`: if delayed power down mode should be activated. `false`: if delayed power down mode should be deactivated. |
| `params.delayTime=<integer>` | An integer returning the delay time in seconds. It is not used if `delayedPowerDownMode` is `false`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDelayedPowerDownMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setDelayedPowerDownMode"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDelayedPowerDownMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setDelayedPowerDownMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDelayedPowerDownMode

| Code | Description |
| --- | --- |
| `300` | Delayed power down mode is not supported. |
| `301` | Unable to set delayed power down mode. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerStatus

This method should be used when you want to check the power status of your device. Please note that the values will be `-1` if the parameters aren’t available on your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerStatus"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerStatus"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerStatus"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerStatus",  "data": {    "usage": {      "currentPower": <double>,      "averagePower": <double>,      "maxPower": <double>    },    "psePoeClass": <integer>,    "lldpPoeClass": <integer>,    "powerRequested": <double>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerStatus"` | The requested method. |
| `usage=<object>` | An object containing the power and energy usage statistics of your device. |
| `currentPower=<double>` | Contains the power in watts currently used by your device. |
| `averagePower=<double>` | Contains the average power in watts used by your device. |
| `maxPower=<double>` | Contains the max power in watts used by your device. |
| `psePoeClass=<integer>` | Contains the PoE class according to the hardware power source equipment. |
| `lldpPoeClass=<integer>` | Contains the PoE class according to the LLDP software negotiation. |
| `powerRequested=<double>` | Contains the power in watts requested by your device. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerStatus",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerStatus"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getPowerStatus

| Code | Description |
| --- | --- |
| `300` | Power status is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerConsumers

This method should be used when you want to retrieve a list containing all available power consumers on your device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConsumers"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConsumers"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerConsumers"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConsumers",  "data": {    "consumers": \[      {        "powerConsumer": <string>,        "type": <string>,        "maxPower": <double>,        "adjustablePower": <boolean>,        "enabled": <boolean>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerConsumers"` | The requested method. |
| `consumers=<object>` | Contains all available power consumers. |
| `powerConsumer=<string>` | Contains the name of the power consumer. |
| `type=<string>` | Contains the consumer type. |
| `maxPower=<double>` | The maximum power, in watts, used by the consumer. |
| `adjustablePower=<boolean>` | Indicates if the power for the consumer can be adjusted. |
| `enabled=<boolean>` | Indicates if the consumer is enabled. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConsumers",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerConsumers"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getPowerConsumers

| Code | Description |
| --- | --- |
| `300` | Power consumers is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setPowerConsumer

This method should be used when you want to apply properties to a power consumer.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerConsumer",  "params": {    "powerConsumer": <string>,    "maxPower": <number>,    "enabled": <boolean>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerConsumer",  "params": {    "powerConsumer": <string>,    "maxPower": <number>,    "enabled": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setPowerConsumer"` | The method that should be used. |
| `powerConsumer=<string>` | Contains the name of the power consumer. |
| `maxPower=<double>` | The maximum power, in watts, used by the consumer. |
| `enabled=<boolean>` | Indicates if the consumer is enabled. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerConsumer"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerConsumer"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerConsumer",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerConsumer"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setPowerConsumer

| Code | Description |
| --- | --- |
| `300` | Power consumers is not supported. |
| `301` | Unable to set power consumer. |
| `302` | Invalid parameter value for power consumer. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerProfiles

This method should be used when you want to retrieve a list containing all available power profiles.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerProfiles"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerProfiles"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerProfiles"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerProfiles",  "data": {    "currentPowerProfile": <string>,    "profiles": \[      {        "powerProfile": <string>,        "powerRank": <integer>,        "lowerTemperature": <integer>,        "upperTemperature": <integer>,        "labels": \[          <string>        \],        "default": <boolean>,        "consumers": \[          {            "powerConsumer": <string>,            "maxPower": <double>,            "enabled": <boolean>          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerProfiles"` | The requested method. |
| `currentPowerProfile=<string>` | Contains the name of the active profile. |
| `profiles=<object>` | Lists the power profiles available on your device. |
| `powerProfile=<string>` | Contains the profile name. |
| `powerRank=<integer>` | Contains a value that ranks the power usage of a profile relative to other profiles from lowest to highest. |
| `lowerTemperature=<integer>` | Contains the lowest profile specific temperature limit, which is dependant on if the profile allows heaters or fans to be used. Please note that your device is not guaranteed to have full functionality if the ambient temperature is lower than this value. |
| `upperTemperature=<integer>` | Contains the highest profile specific temperature limit, which is dependant on if the profile allows coolers or fans to be used. Please note that your device is not guaranteed to have full functionality if the ambient temperature is higher than this value. |
| `labels=<object>` | Profile labels. |
| `default=<boolean>` | Boolean indicating if the profile is the default profile. |
| `consumers=<object>` | Power consumers settings for the profile. |
| `powerConsumer=<string>` | Contains the consumer names. |
| `maxPower=<double>` | Contains the maximum power, in watts, for the consumer when a profile is used. |
| `enabled=<boolean>` | Indicator for if the consumer should be active when a profile is used. |

The following table lists the objects supported by `labels=<object>`.

| Property name | Description |
| --- | --- |
| `disableHeaters` | Profile has disabled heaters. |
| `highPerformance` | Profile is optimized for high performance. |
| `lowPower` | Profile is optimized for low power consumption. |
| `temperatureRange` | Profile has a suggested temperature range indicated by lowerTemperature and upperTemperature limits. |
| `enableIo` | Profile has 12V IO enabled (only used if there are other profiles with 12V IO disabled). |
| `enableHdmiAndAudio` | Profile has HDMI and Audio enabled (only used if there are other profiles with HDMI and Audio disabled). |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerProfiles",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerProfiles"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getPowerProfiles

| Code | Description |
| --- | --- |
| `300` | Power profiles is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setPowerProfile

This method should be used when you want to apply a pre-defined power profile.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerProfile",  "params": {    "powerProfile": <string>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerProfile",  "params": {    "powerProfile": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setPowerProfile"` | The method that should be used. |
| `powerProfile=<string>` | Contains the name of the profile that should be applied. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerProfile"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerProfile"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerProfile",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerProfile"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setPowerProfile

| Code | Description |
| --- | --- |
| `300` | Power profiles is not supported. |
| `301` | Unable to set power profile. |
| `302` | Invalid parameter value for power profile. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerConfigurations

This method should be used when you want to retrieve a list containing all available power configurations.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConfigurations"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConfigurations"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerConfigurations"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConfigurations",  "data": {    "powerConfigurations": \[      {        "index": <integer>,        "name": <string>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerConfigurations"` | The requested method. |
| `powerConfigurations=<object>` | Lists the power configurations available for your device. |
| `index=<integer>` | The index number of the power configuration. |
| `name=<string>` | The name of the power configuration. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerConfigurations",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerConfigurations"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getPowerConfigurations

| Code | Description |
| --- | --- |
| `300` | Power configurations are not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getActivePowerConfiguration

This method should be used when you want to retrieve an active power configuration.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getActivePowerConfiguration"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getActivePowerConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getActivePowerConfiguration"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getActivePowerConfiguration",  "data": {    "index": <integer>,  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getActivePowerConfiguration"` | The requested method. |
| `index=<integer>` | The index number of the active power configuration. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getActivePowerConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getActivePowerConfiguration"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getActivePowerConfiguration

| Code | Description |
| --- | --- |
| `300` | Power configurations are not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setActivePowerConfiguration

This method should be used when you want to apply a requested power configuration to be active on your device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setActivePowerConfiguration",  "params": {    "index": <integer>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setActivePowerConfiguration",  "params": {    "index": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setActivePowerConfiguration"` | The method that should be used. |
| `index=<integer>` | The index number of the power configuration that should be set. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setActivePowerConfiguration"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setActivePowerConfiguration"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setActivePowerConfiguration",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setActivePowerConfiguration"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setActivePowerConfiguration

| Code | Description |
| --- | --- |
| `300` | Power configurations are not supported. |
| `301` | Unable to set power configuration, index out of bounds. |
| `302` | Invalid parameter value for power configuration. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getDynamicPowerMode

This method should be used when you want to retrieve the dynamic power mode state.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDynamicPowerMode"}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDynamicPowerMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getDynamicPowerMode"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDynamicPowerMode",  "data": {    "dynamicPowerMode": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getDynamicPowerMode"` | The requested method. |
| `dynamicPowerMode=<boolean>` | `true`: dynamic power mode is active. `false`: dynamic power mode is not active. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getDynamicPowerMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getDynamicPowerMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for getDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | Dynamic power mode is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setDynamicPowerMode

This method should be used when you want to either enable or disable dynamic power mode on your device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDynamicPowerMode",  "params": {    "dynamicPowerMode": <boolean>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDynamicPowerMode",  "params": {    "dynamicPowerMode": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setDynamicPowerMode"` | The method that should be used. |
| `dynamicPowerMode=<boolean>` | `true`: enables dynamic power mode. `false`: disables dynamic power mode. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDynamicPowerMode"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setDynamicPowerMode"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setDynamicPowerMode",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setDynamicPowerMode"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | Dynamic power mode is not supported. |
| `301` | Unable to set dynamic power mode. |
| `302` | Invalid parameter value for dynamic power mode. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerHistory

This method should be used when you want to check the power history of your device. The history is accumulated and stored on the device memory for persistent and long term statistics.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerHistory",  "params": {    "requestedTimeSpan": <integer>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerHistory",  "params": {    "requestedTimeSpan": <integer>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerHistory"` | The method that should be used. |
| `params.requestedTimeSpan=<integer>` | Contains the requested time length in seconds for which to request data. Please note that the acquired time length will likely differ as the algorithm finds the closest matching set of data points with the highest possible resolution. Parameters should be larger than or equal to zero, or the error code `302` will be returned. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerHistory",  "data": {    "acquiredTimeSpan": <integer>,    "numberOfSamples": <integer>,    "endTimeStamp": <string>,    "powerMeasurements": \[<double>, ..., <double>\],    "powerAverage": <double>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerHistory"` | The requested method. |
| `data.acquiredTimeSpan=<integer>` | Contains the length of the requested time span in seconds and is obtained after an algorithm finds the set of data best matching the requested time length, along with the highest resolution of data for the time interval. |
| `data.numberOfSamples=<integer>` | Contains the number of data points in the `powerMeasurements` array. |
| `data.endTimeStamp=<string>` | Contains the time stamp in the ISO8601 format of the last data point in the `powerMeasurements` array. |
| `data.powerMeasurements[]=<list of doubles>` | Contains the data points in watts for the acquired time span. |
| `data.powerAverage=<double>` | Contains the average power consumption, in watts, over the acquired time span. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerHistory",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerHistory"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | Power history is not supported. |
| `301` | Unable to retrieve power history data. |
| `302` | Invalid parameter value for power history. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPowerWarningOverlay

This method should be used when you want to check whether the text overlay warning regarding a lack of power on the PoE is enabled. If enabled, the system will show the overlay when appropriate. Some products support the possibility to change the power configuration with `setActivePowerConfiguration` instead of disabling the overlay with`setPowerWarningOverlay`.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerWarningOverlay",  "params": {  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerWarningOverlay",  "params": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getPowerWarningOverlay"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerWarningOverlay",  "data": {    "enabled": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerWarningOverlay"` | The requested method. |
| `data.enabled=<boolean>` | Returns that state of the power warning overlay functionality. Can be either `true` = enabled or `false` = disabled. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPowerWarningOverlay",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPowerWarningOverlay"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | Disable Power Warning Overlay is not supported. |
| `301` | Unable to disable Power Warning Overlay. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setPowerWarningOverlay

This method should be used when you want to check whether the text overlay warning regarding a lack of power on the PoE is enabled. If enabled, the system will show the overlay when appropriate. Some products support the possibility to change the power configuration with `setActivePowerConfiguration` instead of disabling the overlay with`setPowerWarningOverlay`.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerWarningOverlay",  "params": {    "enable": <boolean>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerWarningOverlay",  "params": {    "enable": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setPowerWarningOverlay"` | The method that should be used. |
| `params.enable=<boolean>` | States if the power warning overlay should be enabled. Can be either `true` = enabled or `false` = disabled. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerWarningOverlay"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerWarningOverlay"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPowerWarningOverlay",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPowerWarningOverlay"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | Disable Power Warning Overlay is not supported. |
| `301` | Unable to disable Power Warning Overlay. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getIoPortPower

This method should be used when you want to check the status of the IO Port Power feature. This API makes it possible to see if the 12V output on the IO connector is enabled or disabled.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIoPortPower",  "params": {  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIoPortPower",  "params": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getIoPortPower"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIoPortPower",  "data": {    "enabled": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getIoPortPower"` | The requested method. |
| `data.enabled=<boolean>` | Returns the IO Port Power state.  
`true` = enabled  
`false` = disabled |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getIoPortPower",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getIoPortPower"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | IO Port Power is not supported. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setIoPortPower

This method should be used when you want to set the state of the power output for the IO connector and turn the 12V IO Port Power on or off.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/power-settings.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIoPortPower",  "params": {    "enable" <boolean>  }}'
```

```bash
POST /axis-cgi/power-settings.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIoPortPower",  "params": {    "enable" <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="setIoPortPower"` | The method that should be used. |
| `params.enable=<boolean>` | States if IO Port Power should be enabled.  
`true` = enabled  
`false` = disabled |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIoPortPower",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setIoPortPower"` | The requested method. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setIoPortPower",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<Major>.<Minor>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setIoPortPower"` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

Error codes for setDynamicPowerMode

| Code | Description |
| --- | --- |
| `300` | IO Port Power is not supported. |
| `301` | Unable to set IO Port Power to its new state. |
| `302` | Invalid parameter value for set IO Port Power. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

The following table lists the general errors that can occur to any CGI method. Errors unique to a method are listed under the API description of that particular method.

| Code | Description |
| --- | --- |
| `100` | The requested API version is not supported. |
| `4001` | Mandatory input parameters was not found in the input. |
| `4002` | The type of a provided JSON parameter was incorrect. |
| `8000` | Internal error. |