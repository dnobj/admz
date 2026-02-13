---
title: Temperature control
url: "https://developer.axis.com/vapix/network-video/temperature-control/"
category: vapix
subcategory: network-video
sha256: 191478a76e064dd021b46b65b2e8d0505d5f7aff5b4e0644e6e5bfdf6b6a015d
scraped_at: "2026-01-09T15:21:15.580Z"
page_height: 16870
---

# Temperature control

## Description

The Temperature control API provides the information that makes it possible for applications and users to monitor and control the temperature of an Axis product. This includes monitoring the temperature sensors and controlling the heaters as well as the fans. Since the availability of these components are product specific this API also includes how to retrieve this information.

### Model

The API implements the following CGI:s as its communications interface that allows you to do the following:

| Function | Description |
| --- | --- |
| `/axis-cgi/temperaturecontrol.cgi` | Retrieves all information about available temperature sensors, heaters and fans. This CGI can also be used to directly control the heaters and fans. |
| `/axis-cgi/param.cgi` | Specifies the trigger levels for user configured events. |

### Identification

-   **API Discovery**: `id=temperaturecontrol`
-   **Property**: `Properties.TemperatureSensor.TemperatureControl=yes`
-   **Property**: `Properties.TemperatureSensor.Fan=yes | no`
-   **Property**: `Properties.TemperatureSensor.Heater=yes | no`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Remove fog on camera window

Use these examples to get rid of fog on the front window of the camera that may have built up due to changing weather conditions. Depending on your product, this can either be done by running a heater or a fan.

**Initiate the heater manually**

1.  Turn on the heater, which in this example has the id 0.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=0&action=start"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=0&action=startHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Stop the fan**

1.  Stop the fan, which in this example has the id 1, from running.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=fan&id=1&action=stop"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=fan&id=1&action=stopHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Set duration for a manual heater control**

1.  Set the manual activation time for a heater, which in this example has the id 0.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&TemperatureControl.Heater.H0.ManualControlDuration=120"
```

```bash
GET /axis-cgi/param.cgi?action=update&TemperatureControl.Heater.H0.ManualControlDuration=120Host: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Activate user control mode**

1.  Enable the user control for a heater, which in this example has the id 1, and set the heater intensity to 50%.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=1&usercontrolmode=true&intensity=50"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=1&usercontrolmode=true&intensity=50Host: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Fail to start heater**

1.  Request a non-existing heater with id 1 to turn on.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=start"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=startHost: <servername>
```

2.  Parse the HTTP response.

Error response example

```bash
Unknown device type or bad id.
```

**Unsupported action for fan**

1.  Request a non-existing action for a fan, which in this example has the id 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=fan&id=1&action=badaction"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=fan&id=1&action=badactionHost: <servername>
```

2.  Parse the HTTP response.

Error response example

```bash
Unsupported action.
```

**User control mode not supported**

1.  Request to enable user control of a heater, which in this example has the id 0, when this is not supported.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=0&usercontrolmode=true"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=0&usercontrolmode=trueHost: <servername>
```

2.  Parse the HTTP response.

Error response example

```bash
Could not set the requested mode for the device.
```

### Retrieve temperature information

Use these examples when you want to retrieve information about the temperature sensors, heaters and fans. This is useful when you want to understand the camera status.

**Get all temperature information**

1.  Retrieve all status information for the temperature sensors, heaters and fans.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?action=statusall"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?action=statusallHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
Sensor.S0.Name=MainSensor.S0.Celsius=43.50Sensor.S0.Fahrenheit=110.30Sensor.S1.Name=CPUSensor.S1.Celsius=50.44Sensor.S1.Fahrenheit=122.79Sensor.S2.Name=Image SensorSensor.S2.Celsius=46.67Sensor.S2.Fahrenheit=116.00Sensor.S3.Name=OpticsSensor.S3.Celsius=38.66Sensor.S3.Fahrenheit=101.58Heater.H0.Status=StoppedHeater.H0.TimeUntilStop=0Heater.H1.Status=StoppedHeater.H1.TimeUntilStop=0Fan.F0.Status=StoppedFan.F0.TimeUntilStop=0
```

Possible entries for the statusall response

| Parameter name | Description |
| --- | --- |
| `Sensor.S#` | A temperature sensor with the index #. |
| `Sensor.S#.Name` | The name of the temperature sensor #. |
| `Sensor.S#.Celsius` | The degrees (in Celsius) reading from the temperature sensor #. |
| `Sensor.S#.Fahrenheit` | The degrees (in Fahrenheit) reading from the temperature sensor #. |
| `Heater.H#` | A heater with the index #. |
| `Heater.H#.Status` | The status of heater #. See the table **Possible status of heater** below for possible values. |
| `Heater.H#.TimeUntilStop` | The number of seconds left until heater # stops following manual activation. |
| `Fan.F#` | A fan with the index #. |
| `Fan.F#.Status` | The status of fan #. See the table **Possible status of fan** below for possible values. |
| `Fan.F#.TimeUntilStop` | The number of seconds left until fan # stops following manual activation. |

Possible status of heater

| Value | Description |
| --- | --- |
| `Heater Failure` | Heater has failed for some reason. |
| `Running` | Heater is active. |
| `Running[XX]` | Heater is active at certain XX intensity. Can be both a percentage or some other product specific representation. |
| `Stopped` | The heater is stopped. |

Possible status of fan

| Value | Description |
| --- | --- |
| `Fan Failure` | Fan has failed for some reason. |
| `Running` | Fan is active. |
| `Running[XX]` | Fan is active at certain XX intensity. Can be both a percentage or some other product specific representation. |
| `Stopped` | The fan is stopped. |

**Time until heater stops**

1.  Retrieve time left until heater number 1 stops following a manual start.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=timeuntilstop"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=timeuntilstopHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
95
```

**Read temperature sensor in Celsius**

1.  Retrieve the current temperature value in Celsius as measured by temperature sensor number 2.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=query"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=queryHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
46.71
```

**Read temperature sensor in Fahrenheit**

1.  Retrieve the current temperature value in Fahrenheit as measured by temperature sensor number 2.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=query&temperatureunit=fahrenheit"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=query&temperatureunit=fahrenheitHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
116.07
```

**Read current heater status**

Retrieve the current status of a heater with id 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=query"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=heater&id=1&action=queryHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
Running\[100%\]
```

**Read temperature sensor on an invalid unit**

1.  Retrieve the current temperature value from a malformed unit measured by temperature sensor number 2.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=query&temperatureunit=badunit"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?device=sensor&id=2&action=query&temperatureunit=badunitHost: <servername>
```

2.  Parse the HTTP response.

Error response example

```bash
Invalid temperature unit.
```

### Configure temperature triggers

Use these examples to change the configured temperature limit for when an event is sent out, which is useful when you want to catch an event and react to it.

**Set low trigger for sensor 2 in Celsius**

1.  Set the low temperature trigger for temperature sensor 2 to -10 degrees Celsius.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S2.TriggerLow=-10"
```

```bash
GET /axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S2.TriggerLow=-10Host: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Set high trigger for sensor 3 in Fahrenheit**

1.  Set the high temperature trigger for temperature sensor 3 to 30 degrees Fahrenheit.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S3.TriggerHigh=30F"
```

```bash
GET /axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S3.TriggerHigh=30FHost: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
OK
```

**Set low trigger for a sensor with bad id**

1.  Set the low temperature trigger for a temperature sensor with bad or nonexistent id.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S20.TriggerLow=-10"
```

```bash
GET /axis-cgi/param.cgi?action=update&TemperatureControl.Sensor.S20.TriggerLow=-10Host: <servername>
```

2.  Parse the HTTP response.

Error response example

```bash
# Error: Error setting 'root.TemperatureControl.Sensor.S20.TriggerLow' to '-10'!
```

## API specifications
### `/axis-cgi/temperaturecontrol.cgi`

Use this API to manage and retrieve information about temperature sensors, heaters and fans. Please note that the availability of all functionality except `action=statusall` depends on what kind of hardware your product has as well as the capabilities of the hardware.

**Request**

-   **Security level**: Operator
-   **Method**: `GET`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperaturecontrol.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/temperaturecontrol.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `action=start | stop | query | timeuntilstop | statusall` | Optional parameter that defines what should happen. Valid values are:  
  
\- `start`: Manually starts the `heater/fan` for the duration set in `ManualControlDuration` parameter.  
\- `stop`: Manually stops the `heater/fan`. Any duration left in `timeuntilstop` will be reset.  
\- `query`: Retrieve information about `heater/fan`.  
\- `timeuntiltimestop`: Retrieve information left on `heater/fan`.  
\- `statusall`: Retrieve information on all `heater/fans/sensors`. |
| `device=heater | fan | sensor` | Optional parameter that defines the type of temperature device  
  
\- `heater`: The device is a heater.  
\- `fan`: The device is a fan.  
\- `sensor`: The device is a temperature sensor. |
| `id=<id>` | Optional parameter that defines the index number of the temperature device as an integer value. |
| `usercontrolmode=true | false`([1](#user-content-fn-1)) | Optional parameter that is used to enable/disable manual control of a `heater/fan`. The control is reset to `false` whenever the device is rebooted  
  
\- `true`: Enable user control mode.  
\- `false`: Disable user control mode. |
| `temperatureunit=celsius | fahrenheit` | Optional parameter that defines the temperature unit  
  
\- `celsius`: Use Celsius  
\- `fahrenheit`: Use Fahrenheit |
| `intensity=<0-100>` | Optional parameter that defines the intensity of the `heater/fan` as an integer in the range between 0–100 percent. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

Response body syntax

```bash
OK
```

**Return value - Error**

| HTTP code | Description |
| --- | --- |
| `400` | Malformed request. Return body specifies one of the following reasons. |
| `400` | The request had bad syntax or was inherently impossible to satisfy. |
| `400` | Unsupported action. |
| `400` | Unknown device type or bad id. |
| `400` | Invalid temperature unit. |
| `400` | Could not set the requested mode for the device. |
| `500` | Internal server error. |

### TemperatureControl.Heater

Use the parameters in this group to configure the temperature control heater.

-   **List security level**: Viewer
-   **Update security level**: Operator or N/A

```bash
TemperatureControl.Heater.H#.<parameter>
```

Valid values of `#` ranges from 0 to the number of heaters specified for the product -1. Please note that if `UserControlSupport=no` then all parameters have Update Security level N/A.

| Parameter | Description |
| --- | --- |
| `UserControlSupport=yes | no` | Update security level: N/A. A read-only parameter specifying whether the user is allowed to control the heater or not. This parameter is static and will not be changed during the runtime. Default value is product and heater/fan specific. |
| `ManualControlDuration=<integer>` | Specifies the time duration in seconds of a start action for the heater performed via `/axis-cgi/temperaturecontrol.cgi`. Valid ranges as well as the default value is product and heater/fan specific. |
| `ControlPolicyLimit=<integer>` | Specifies the temperature limit around which temperature based, automatic control of the heater shall start. Together with `ControlPolicyDelta` a temperature range for the heater is created. |
| `ControlPolicyDelta=<integer>` | Specifies the size of the range used for creating the temperature based, automatic control of the heater. |

### TemperatureControl.Fan

Use the parameters in this group to configure the temperature control fan.

-   **List security level**: Viewer
-   **Update security level**: Operator or N/A

```bash
TemperatureControl.Fan.F#.<parameter>
```

Valid values of `#` ranges from 0 to the number of heaters specified for the product -1. Please note that if `UserControlSupport=no` then all parameters have Update Security level N/A.

| Parameter | Description |
| --- | --- |
| `UserControlSupport=yes | no` | Update security level: N/A. A read-only parameter specifying whether the user is allowed to control the fan or not. This parameter is static and will not be changed during the runtime. Default value is product and heater/fan specific. |
| `ManualControlDuration=<integer>` | Specifies the time duration in seconds of a start action for the fan performed via `/axis-cgi/temperaturecontrol.cgi`. Valid ranges as well as the default value is product and heater/fan specific. |
| `ControlPolicyLimit=<integer>` | Specifies the temperature limit around which temperature based, automatic control of the heater shall start. Together with `ControlPolicyDelta` a temperature range for the fan is created. |
| `ControlPolicyDelta=<integer>` | Specifies the size of the range used for creating the temperature based, automatic control of the fan. |

### TemperatureControl.Sensor

Use the parameters in this group to configure the temperature control sensor.

-   **List security level**: Viewer
-   **Update security level**: Operator or N/A

```bash
TemperatureControl.Sensor.S#.<parameter>
```

Valid values of `#` ranges from 0 to the number of heaters specified for the product -1.

| Parameter | Description |
| --- | --- |
| `Name=<string>` | Specifies the name of the temperature sensor. |
| `TriggerHigh=<integer>` | Specifies the temperature limit for which the `Temperature` above event is triggered. |
| `TriggerLow=<integer>` | Specifies the temperature limit for which the `Temperature` below event is triggered. |

## Footnotes

1.  Dependant on device and their heater/fan capabilities. See product documentation for more information. [↩](#user-content-fnref-1)