---
title: Pan/tilt/zoom API
url: "https://developer.axis.com/vapix/network-video/pantiltzoom-api/"
category: vapix
subcategory: network-video
sha256: 9065dc8a8acb70ef649cd2998ab9461ed35a61c548fbcaca5267d5e276d988fd
scraped_at: "2026-01-09T15:20:36.660Z"
page_height: 105880
---

# Pan/tilt/zoom API

## Description

The PTZ API is used to configure and control the pan, tilt and zoom (PTZ) functionality in Axis network cameras and video encoders. PTZ functionality is available in most camera models. Cameras categorized as PTZ cameras have mechanical PTZ functionality while other cameras can have view areas with digital PTZ. Cameras and video encoders with serial ports can be connected to external devices, for example pan-tilt motors, that provide PTZ functionality. To control the external PTZ device, a PTZ driver must be uploaded.

For cameras with view areas and video encoders with multiple video channels, the PTZ functionality is configured and controlled for each view area or video channel (referred to as a camera in the API) separately.

The PTZ API consists of:

-   **PTZ control API**: Configure and control the PTZ functionality. See [PTZ control API](#ptz-control-api).
-   **PTZ driver management API**: Upload, remove, list, activate and deactivate PTZ drivers. See [PTZ driver management API](#ptz-driver-management-api).
-   **Queueing API**: Configure and control the PTZ control queue. See [Queuing API](#queuing-api).

See also [PTZ events and actions](#ptz-events-and-actions).

In addition to PTZ functionality, the API also includes parameters for IR cut filter (day and night functionality), backlight compensation, focus, brightness and iris.

### PTZ parameter and CGI functionality

Each functionality (for example pan) uses `Support` parameters (see [PTZ.Support](#ptzsupport)) to check if the functionality is supported, uses `Various` parameters (see [PTZ.Various](#ptzvarious)) to check if functionality is enabled and to disable functionality, and use CGIs (see [PTZ control](#ptz-control)) to control the functionality.

### Definitions

| Term | Definition |
| --- | --- |
| Digital PTZ | PTZ without moving parts. PTZ "movements" are done by dynamically changing crop section on the image sensor. |
| Mechanical PTZ | Mechanical PTZ is driven by motors. The motors could either be integrated in the Axis product or the Axis product could be mounted on a external mechanical PT (PanTilt) device. It could also be an external PTZ camera connected to an encoder. |
| Panopsis technology | Panopsis technology is used by mechanical PTZ domes that in addition to the standard zoom lens have a Panopsis (fisheye) lens attached to the dome cover.A product with Panopsis technology can be used in two modes. In Overview mode, the zoom lens is fully zoomed out and points straight down (-90 degrees tilt) looking through the Panopsis lens. This gives a 360-degree overview image. In Normal mode, the zoom lens avoids the Panopsis lens and the product works as a standard mechanical PTZ dome. Note that some PTZ commands cannot be used or do not have any effect in Overview mode. |
| Absolute movement | Move to a specific coordinate position, for example "move to -45°". |
| Relative movement | Move a specific distance from the current position, for example "move left 15°". |
| Continuous movement | Move in a specific direction (until stopped), for example "move down". |
| Auto-flip | The auto-flip functionality allows the camera to simulate a continuous pan beyond the mechanical stop, thereby enabling an operator to continuously follow an object. |
| Static PTZ driver | A PTZ driver is built into the AXIS OS and is always running. Typically used on domes and digital PTZ. |
| Uploadable PTZ driver | A PTZ driver that can be uploaded and installed to a running Axis product. |

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Check if PTZ is available.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.PTZ.PTZ"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.PTZ.PTZHost: <servername>
```

Verify that PTZ is enabled on channel 1:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?info=1&camera=1"
```

```bash
GET /axis-cgi/com/ptz.cgi?info=1&camera=1Host: <servername>
```

A successful response should look similar or the same to the response in [Success for info=1](#success-for-info1).

Request information about which PTZ commands that are available for `camera=1`. For the response see example in section [PTZ control](#ptz-control).

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?info=1&camera=1"
```

```bash
GET /axis-cgi/com/ptz.cgi?info=1&camera=1Host: <servername>
```

Pan `camera=3` to the right, 10 degrees.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?rpan=10&camera=3"
```

```bash
GET /axis-cgi/com/ptz.cgi?rpan=10&camera=3Host: <servername>
```

Set a home position named "MyPreset" at the current location for the Axis product.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptzconfig.cgi?setserverpresetname=MyPreset&home=yes"
```

```bash
GET /axis-cgi/com/ptzconfig.cgi?setserverpresetname=MyPreset&home=yesHost: <servername>
```

Enable PTZ on video channel number 3 on an Axis product with digital PTZ. For digital PTZ, `PTZ.ImageSource.I0.PTZEnabled` is controlling all video channel. Each video channel has a `PTZ.Various.V#.Locked` parameter.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?PTZ.ImageSource.I0.PTZEnabled=yes&PTZ.Various.V3.Locked=false"
```

```bash
GET /axis-cgi/param.cgi?PTZ.ImageSource.I0.PTZEnabled=yes&PTZ.Various.V3.Locked=falseHost: <servername>
```

Check if a product supports upload and installation of drivers.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.PTZ.DriverManagement"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.PTZ.DriverManagementHost: <servername>
```

Upload a driver with the driver file contents as HTTP POST data (see for details).

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzuploader.cgi"
```

```bash
GET /axis-cgi/ptz/ptzuploader.cgiHost: <servername>
```

A driver ID is returned in the HTTP response, for example `7`.

```bash
<?xml version=1"1.0"?><root>  <id>7</id></root>
```

Install the uploaded driver with ID 7 on video channel 3.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverid=7&channel=3"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverid=7&channel=3Host: <servername>
```

## PTZ control API
### Description

There are two types of PTZ, mechanical PTZ and digital PTZ. Mechanical PTZ is driven by motors. The motors could either be integrated in the Axis product or the Axis product could be mounted on a external mechanical PT (PanTilt) device. It could also be an external PTZ camera connected to an encoder. For Axis products with digital PTZ it is possible to select only a part of the image by zooming in. The zoomed area can then be moved around using pan/tilt commands. Digital PTZ uses the same HTTP API as Axis products with mechanical PTZ, with some limitations.

The PTZ Control API consists of the following CGIs:

| Name | Description |
| --- | --- |
| `/axis-cgi/com/ptz.cgi` | Control the PTZ movement. |
| `/axis-cgi/com/ptzconfig.cgi` | Configure the PTZ functionality. |
| `/axis-cgi/com/ptzqueue.cgi` | Control the PTZ control queuing mechanism. |

### Prerequisites
#### Identification

-   **API Discovery**: `id=ptz-control`
-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.API.PTZ.Presets.Version=2.00` (The index for the `preset` that is the device's home position at start-up or when calling `/axis-cgi/com/ptz.cgi?move=home`)
-   **Property**: `Properties.PTZ.PTZ=yes`
-   **Property**: `Properties.PTZ.DigitalPTZ=yes` (Products with digital PTZ)
-   **Property**: `Properties.Overview.Overview=yes` (Products with Panopsis technology)
-   **Property**: `Properties.Overview.MechanicalHybrid=yes` (Products with Panopsis technology)
-   **Property**: `Properties.PTZ.EmbeddedDrivers=yes`(For when all previously uploadable ptz drivers are embedded in the cameran AXIS OS instead of externally published. This also means that it is not possible to upload any ptz drivers.)
-   **AXIS OS**: 5.20 and later.

### Parameters
#### PTZ

Various Pan tilt zoom parameters. All writable parameters may be directly modified.

PTZ

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `BoaProtPTZOperator` | `password` | `password` `anonymous` | admin: read, write operator: read viewer: read | `password` = Password is required to control PTZ units and to use control queue. `anonymous` = Anybody on the network have access to PTZ units without having to log in. |
| `CameraDefault` | `1` | `1 ... n` n = Number of video channels. | admin: read, write operator: read viewer: read | The video channel used if the `camera` parameter is omitted in HTTP requests. |
| `ResponseEncoding` | iso-8859–1 | iso-8859–1 utf-8 | admin: read, write operator: read viewer: read | The character encoding that should be used for the plain-text responses of the preset queries. If the parameter is set to ISO-8859-1, but the text contains unsupported characters, the response will default to utf-8. |
| `NbrOfCameras` | Product specific | `1 ...` | admin: read operator: read viewer: read | Number of video channels. |
| `NbrOfSerPorts` | Product specific | `0 ...` | admin: read operator: read viewer: read | Number of serial ports. |

#### PTZ.ImageSource

This group contains a parameter for turning on/off PTZ functionality.

Toggling this parameter does not install/uninstall any driver.

PTZ.ImageSource.I#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `PTZEnabled` | **Mechanical PTZ**: `true` **Digital PTZ**: `false` | `true` `false` | admin: read, write operator: read, write viewer: read | **Mechanical PTZ** = Enable/disable the PTZ functionality of the video channel. `true` = Enable the PTZ functionality of the video channel. `false` = Disable the PTZ functionality of the video channel. **Digital PTZ** = Enable/disable the PTZ functionality on the Axis product. `true` = Enable the PTZ functionality on the Axis product. `false` = Disable the PTZ functionality on the Axis product. When this parameter is changed to `false`, the product returns to a default PTZ position (in contrast to the parameter `PTZ.Various.V#.Locked`, for which the position is locked when the parameter is set to `true`). |

info

For mechanical PTZ, the index # in PTZ.ImageSource.I# is the index of the video channel, starting on 0 for video channel 1. For digital PTZ, there is one group PTZ.ImageSource.I0, and the parameter PTZ.ImageSource.I0.PTZEnabled is used for enabling/disabling PTZ on all channels.

#### PTZ.PTZDriverStatuses

This group contains a parameter that informs about the current status of the drivers installed on the Axis product.

PTZ.PTZDriverStatuses

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Driver#Status` |  | `0 ... 3` | admin: read operator: read viewer: read | The status of the driver installed on `camera #` , where `#` starts on `1` for video channel 1. The value should be interpreted as: 0 = No driver installed. 1 = Installation file invalid or incompatible. 2 = Driver malfunction. 3 = Driver installed. |

#### PTZ.Support

The dynamic parameter group `PTZ.Support.S#` is updated when a driver is installed on a video channel. A parameter in the group has the value `true` if the corresponding capability is supported by the driver. The index `#` is the video channel number which starts from 1.

An absolute operation means moving to a certain position, a relative operation means moving relative to the current position. Arguments referred to apply to [PTZ control](#ptz-control).

PTZ.Support.S#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `AbsolutePan` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute pan is supported by the driver. `false` = Absolute pan is disabled/not supported. |
| `RelativePan` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative pan is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Relative pan is disabled/not supported. |
| `AbsoluteTilt` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute tilt is supported by the driver. `false` = Absolute tilt is disabled/not supported. |
| `RelativeTilt` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative tilt is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Relative tilt is disabled/not supported. |
| `AbsoluteZoom` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute zoom is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Absolute zoom is disabled/not supported. |
| `RelativeZoom` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative zoom is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Relative zoom is disabled/not supported. |
| `DigitalZoom` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Digital zoom is supported (increases the upper limit of `PTZ.Limit.L#.MaxZoom` to `19999`) by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Digital zoom is disabled/not supported. |
| `AreaZoom` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Area zoom is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Area zoom is disabled/not supported. |
| `AbsoluteFocus` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute focus is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Absolute focus is disabled/not supported. |
| `RelativeFocus` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative focus is supported by the driver. _Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._ `false` = Relative focus is disabled/not supported. |
| `AutoFocus` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Autofocus is supported by the driver. `false` = Autofocus is disabled/not supported. |
| `AbsoluteIris` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute iris is supported by the driver. `false` = Absolute iris is disabled/not supported. |
| `RelativeIris` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative iris is supported by the driver. `false` = Relative iris is disabled/not supported. |
| `AutoIris` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Auto iris is supported by the driver. `false` = Auto iris is disabled/not supported. |
| `AbsoluteBrightness` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Absolute brightness is supported by the driver. `false` = Absolute brightness is disabled/not supported. |
| `RelativeBrightness` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Relative brightness is supported by the driver. `false` = Relative brightness is disabled/not supported. |
| `ContinuousPan` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous pan is supported by the driver. `false` = Continuous pan is disabled/not supported. |
| `ContinuousTilt` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous tilt is supported by the driver. `false` = Continuous tilt is disabled/not supported. |
| `ContinuousZoom` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous zoom is supported by the driver.  
_Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._  
`false` = Continuous zoom is disabled/not supported. |
| `ContinuousFocus` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous focus is supported by the driver.  
_Products with Panopsis technology: Even if supported, functionality cannot be used in Overview mode._  
`false` = Continuous focus is disabled/not supported. |
| `ContinuousIris` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous iris is supported by the driver. `false` = Continuous iris is disabled/not supported. |
| `ContinuousBrightness` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Continuous brightness is supported by the driver. `false` = Continuous brightness is disabled/not supported. |
| `Auxiliary` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = CGI argument `auxiliary` (`/axis-cgi/com/ptz.cgi?auxiliary=<string>`)is supported by the driver. `false` = CGI argument `auxiliary` is disabled/not supported. |
| `ServerPreset` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Server presets are supported by the driver. `false` = Server presets are disabled/not supported. |
| `DevicePreset` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Device presets are supported by the driver. `false` = Device preset are disabled/not supported. |
| `SpeedCtl` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Speed control is supported by the driver. `false` = Speed control is disabled/not supported. |
| `IrCutFilter` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = IR cut filter is supported by the driver. `false` = IR cut filter is disabled/not supported. |
| `AutoIrCutFilter` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = The IR cut filter can be controlled automatically. `false` = Automatic IR cut filter is disabled/not supported. |
| `Backlight` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Backlight compensation is supported by the driver. `false` = Backlight compensation is disabled/not supported. |
| `OSDMenu` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = OSD menu is supported by the driver. `false` = OSD menu is disabled/not supported. |
| `ActionNotification` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | Value is `true` if the PTZ driver can send messages to other internal applications when it starts or stops movements. Makes it possible to trigger events on arrival to a preset position. `true` = Action notification is supported. `false` = Action notification is disabled/not supported. |
| `ProportionalSpeed` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | Value is `true` if the product supports proportional speed when using the command `continuouspantiltmove`, for example adjusting the movement speed in the image proportional to the zoom level used. _Proportional speed has the option to be disabled for individual continuous move commands For more information, see [PTZ control](#ptz-control)._ `true` = Proportional speed is supported. `false` = Proportional speed is disabled/not supported. |
| `LensOffset` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Lens offset is supported by the driver. `false` = Lens offset is disabled/not supported. |

#### PTZ.Limit

This dynamic group is updated when a driver is installed on a video channel. Index `#` is the video channel number, starting on `1`. When it is possible to obtain the current position from the driver, for example the current pan position, it is possible to apply limit restrictions to the requested operation. For instance, if an absolute pan to position `150` is requested, but the upper limit is set to `140`, the new pan position will be `140`. This is the purpose of all but `MinFieldAngle` and `MaxFieldAngle` in this group. The purpose of those two parameters is to calibrate image centering.

PTZ.Limit.L#

| Parameter | Default values | Valid values _(May be overridden by configuration file for driver. Maximal value must be ≥ minimal value.)_ | Access control | Description |
| --- | --- | --- | --- | --- |
| `MinPan` | Product/driver dependent | `-180 ... 180` | admin: read, write operator: read viewer: read | Lower limit for pan position. |
| `MaxPan` | Product/driver dependent | `-180 ... 180` | admin: read, write operator: read viewer: read | Upper limit for pan position. |
| `MinTilt` | Product/driver dependent | `-180 ... 180` | admin: read, write operator: read viewer: read | Lower limit for tilt position. |
| `MaxTilt` | Product/driver dependent | `-180 ... 180` | admin: read, write operator: read viewer: read | Upper limit for tilt position. |
| `MinZoom` | Product/driver dependent | `1 ... 9999` _If digital zoom is supported (see PTZ.Support.S#.DigitalZoom in section [PTZ.Support](#ptzsupport)), MaxZoom can have values up to 19999._ | admin: read, write operator: read viewer: read | Lower limit for zoom position. |
| `MaxZoom` | Product/driver dependent | `1 ... 9999` _If digital zoom is supported (see PTZ.Support.S#.DigitalZoom in section [PTZ.Support](#ptzsupport)), MaxZoom can have values up to 19999._ | admin: read, write operator: read viewer: read | Upper limit for zoom position. |
| `MinFocus` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Lower limit for focus position. |
| `MaxFocus` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Upper limit for focus position. |
| `MinIris` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Lower limit for iris position. |
| `MaxIris` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Upper limit for iris position. |
| `MinBrightness` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Lower limit for brightness position. |
| `MaxBrightness` | Product/driver dependent | `1 ... 9999` | admin: read, write operator: read viewer: read | Upper limit for brightness position. |
| `MinFieldAngle` | Product/driver dependent | `1 ... 1000` | admin: read, write operator: read viewer: read | Minimum field angle for the (zoom) lens, used to calibrate image centering. |
| `MaxFieldAngle` | Product/driver dependent | `1 ... 1000` | admin: read, write operator: read viewer: read | Maximum field angle for the (zoom) lens, used to calibrate image centering. |

#### PTZ.Various

The dynamic parameter group `PTZ.Various.V#` is updated when a driver is installed on a video channel. The index `#` is the video channel number which starts from `1`.

The group consists of several different types of parameters for the video channel. To distinguish the parameter types, the group is presented as three different categories below.

The `Enabled` parameters determine if a specific feature can be controlled using `/axis-cgi/com/ptz.cgi` (see section [PTZ control](#ptz-control)).

PTZ.Various.V#

| Parameter | Default values | Valid values _(Integer ranges may be overridden by configuration file for driver)_ | Access control | Description |
| --- | --- | --- | --- | --- |
| `PanEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Pan is allowed. `false` = Pan is not allowed. |
| `TiltEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Tilt is allowed. `false` = Tilt is not allowed. |
| `ZoomEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Zoom is allowed. _Products with Panopsis technology: Cannot be used in Overview mode._ `false` = Zoom is not allowed. |
| `FocusEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Focus is allowed. _Products with Panopsis technology: Cannot be used in Overview mode._ `false` = Focus is not allowed. |
| `IrisEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Iris is allowed. `false` = Iris is not allowed. |
| `BrightnessEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Brightness is allowed. `false` = Brightness is not allowed. |
| `IrCutFilterEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = IR cut filter is allowed. `false` = IR cut filter is not allowed. |
| `BackLightEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Backlight compensation is allowed. `false` = Backlight compensation is not allowed. |
| `SpeedCtlEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Pan/tilt speed adjustment is allowed. `false` = Pan/tilt speed adjustment is not allowed. |
| `ProportionalSpeedEnabled` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Proportional speed is allowed. This function is adjusting the movement speed in the image proportional to the zoom level used. `false` = Proportional speed is not allowed. |

The default parameters set the default value for a specific function in the driver.

PTZ.Various.V#

| Parameter | Default values | Valid values _(Integer ranges may be overridden by configuration file for driver)_ | Access control | Description |
| --- | --- | --- | --- | --- |
| `AutoFocus` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Autofocus is on by default. `false` = Autofocus is off by default. |
| `AutoIris` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Autoiris is on by default. `false` = Autoiris is off default. |
| `IrCutFilter` | Product/driver dependent | `on` `off` `auto` _Only valid if PTZ.Support.S#.AutoIrCutFilter is true._ | admin: read, write operator: read viewer: read | `on` = Default value for IR cut filter is `on`, that is, the filter will block IR light (daytime use). `off` = Default value for IR cut filter is `off`, that is, the filter allows IR light (nighttime use). `auto` = Default value for IR cut filter is `auto`, that is, the filter automatically switches between `on` and `off` depending on the lighting conditions. |
| `BackLight` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = Backlight compensation is on by default. `false` = Backlight compensation is off by default. |

The various parameters have different types of functions.

PTZ.Various.V#

| Parameter | Default values | Valid values _(Integer ranges may be overridden by configuration file for driver)_ | Access control | Description |
| --- | --- | --- | --- | --- |
| `CamId` | Product/driver dependent | An integer | admin: read, write operator: read viewer: read | Identifies an external PTZ device on a serial port, often set by a dip switch on the external device. |
| `DeviceType` | Product/driver dependent | A string | admin: read, write operator: read viewer: read | A driver for an external device may support several variants of the device. Select the matching device type for best compatibility. |
| `Locked` | Product/driver dependent | `true` `false` | admin: read, write operator: read viewer: read | `true` = The PTZ position is locked, that is, the position cannot be changed using PTZ commands. `false` = The PTZ position is unlocked. |
| `LensOffsetX` | Product/driver dependent | `-9999 ... 9999` | admin: read, write operator: read viewer: read | X coordinate of sensor center to lens center vector. Unit is 1/10000 of the sensor width. Used by the `areazoom` argument. Only applicable if the driver supports lens offset. |
| `LensOffsetY` | Product/driver dependent | `-9999 ... 9999` | admin: read, write operator: read viewer: read | Y coordinate of sensor center to lens center vector. Unit is 1/10000 of the sensor height. Used by the `areazoom` argument. Only applicable if the driver supports lens offset. |
| `ReturnToOverview` | Product/driver dependent | `0 ... 300` | admin: read, write operator: read viewer: read | Idle timeout; if there is no PTZ activity for this number of seconds, the video channel returns to its home position. The value `0` means that the idle timeout functionality is turned off. |
| `MaxProportionalSpeed` | Product/driver dependent | `1 ... 1000` | admin: read, write operator: read viewer: read | Set the maximum continuous movement speed in 1/100 of fields of view per second. Example: `200` = Max 2.00 fields of view per second. |

#### PTZ.UserBasic

This dynamic group is updated when a driver is installed on a video channel. Index `#` is the video channel number, starting on `1`. The parameters in these groups are driver dependent and are hence not known in advance. They are described on the help pages that come with the driver installation.

| Parameter | Default values | Valid values | Description |
| --- | --- | --- | --- |
| `FlipPan` | `false` | `true` `false` | Controls if the relative pan operations are inverted. `true`: The relative pan movements are inverted. `false`: The relative pan movements are not inverted. |
| `FlipTilt` | `false` | `true` `false` | Controls if the relative tilt operations are inverted. `true`: The relative tilt movements are inverted. `false`: The relative tilt movements are not inverted. |

#### PTZ.UserAdv

This dynamic group is updated when a driver is installed on a video channel. Index `#` is the video channel number, starting on `1`. The parameters in these groups are driver dependent and are hence not known in advance. Some of the parameters (described below) are supported by most drivers. For the rest of the parameters not described in this section please refer to the help pages that come with the driver installation.

The following parameter is supported by all products where `PTZ.Support.SpeedCtl=true`.

PTZ.UserAdv

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `MoveSpeed` | `100` | `1` ... `100` | admin: read, write operator: read viewer: read | Set the default move speed for absolute and relative pan/tilt movements. Can be overridden with the `speed` argument in the PTZ control HTTP API, see section [PTZ control](#ptz-control). |

The following parameters are supported by most PTZ domes, however please note that some of the parameters are product specific.

PTZ.UserAdv

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `ImageFreeze` | `off` | `off` `on` `auto` | admin: read, write operator: read viewer: read | Freeze the image while the Axis product is moving during a pan, tilt or zoom operation `off` = Image freeze is turned off. `on` = Freeze on all movements. `auto` = Freeze only when going to presets. |
| `AutoFlip` | `true` | `true` `false` | admin: read, write operator: read viewer: read | Simulate continuous pan movement in the same direction. See [Definitions](#definitions) for further information. `true` = Auto flip is enabled. `false` = Auto flip is disabled. |
| `MovePrediction` | `false` | `true` `false` | admin: read, write operator: read viewer: read | The Axis product attempts to predict the new position in the pan movement, after compensating for the slight delay while the Axis product changes direction after an auto flip. `true` = Move prediction is enabled. `false` = Move prediction is disabled. |
| `AutoCalibration` | `true` | `true` `false` | admin: read, write operator: read viewer: read | Enable auto calibration which automatically resets the components of the camera, pan and tilt if a hardware error occurs. `true` = Auto calibration is enabled. `false` = Auto calibration is disabled. |
| `DeviceStatus` | `cam=ok,pan=ok,tilt=ok` | `component=status` `[,component=status...]` | admin: read, write operator: read viewer: read | Shows the status of the camera, pan and tilt hardware components. _Camera = Camera optics. For example zoom, focus and iris._ The values are shown as a comma separated list of `component=status` where `status`can be `ok` or `error[code]` where \[code\] is a 4 digit hexadecimal value. `cam` = Status for the camera. `pan` = Status for pan. `tilt` = Status for tilt. |
| `LastTestDate` | A string | A string \[date time year\] | admin: read, write operator: read viewer: read | Get the date and time for the most recent reset, manually or by `AutoCalibration`. |
| `DeviceModVer` | Product dependent | `model:[model_id], version:[version_nbr]` | admin: read, write operator: read viewer: read | Auto detected identifications of internal hardware component model and version. The values are presented as 4 digit hexadecimal values. `model` = Internal hardware component for model. `version` = Internal hardware component for version. |
| `AutoFocusType` | `assisted` | `assisted` `normal` | admin: read, write operator: read viewer: read | Controls the auto focus behavior on Laser focus cameras. `assisted` = Laser focus is used. `normal` = Contrast based auto focus is used. |
| `QuickZoom` | `true` | `true` `false` | admin: read, write operator: read viewer: read | Controls if quick zoom should be turned on or off. `true`: The camera zoom is using quick zoom. `false`: The camera zoom at normal speed using focus tracing. |
| `TiltIllumination` | `true` | `true` `false` | admin: read, write operator: read viewer: read | Controls if the tilt angle may be used to dim the IR illumination if there is a risk of the IR light being reflected back into the camera. `true`: The tilt angle may dim the IR illumination to avoid reflections. `false`: The IR illumination is independent of the tilt angle. |
| `OneShotAF` | `false` | `true` `false` | admin: read, write operator: read viewer: read | Controls if a new AutoFocus (AF) should be a one shot and only triggered after a PTZ movement. `true`: A new AF search is only triggered when a pan/tilt/zoom movement has finished. `false`: A new AF search is triggered whenever the scene changes, even when there is no PTZ movement. |
| `CameraHousingConfiguration` | `default` | `default` `inverted` | admin: read, write operator: read viewer: read | Stores information on how the camera housing is mounted on your PT unit. Please note that changing this parameter will automatically switch and invert the sign of the `up` and `down` parameters and change the valid tilt limit range for `default`: -90 to +45 and `inverted`: -45 to +90. `default`: The camera housing is mounted upright on the PT unit. `inverted`: The camera housing is mounted in reverse on the PT unit. |
| `IlluminatorType[IL1 | IL2]` | `none` | `none` `ir` `white` | admin: read, write operator: read viewer: read | Gets set when any illuminator gets mounted on your PT unit which makes it controllable from the system. `none`: No light has been mounted. `ir`: An IR illuminator has been mounted. The IR lights can be turned on with the auxiliary command `tt:LightIR | On` and off with `tt:LightIR | Off`. `white`: A white light illuminator has been mounted. The white lights can be turned on with the auxiliary command `tt:LightWL | On` and off with `tt:LightWL | Off`. |
| `IRSynchCameraDayNightSwitch` | `false` | `true` `false` | admin: read, write operator: read viewer: read | Controls the on/off switch of any attached IR illuminators based on the day/night mode. `true`: The IR illuminator will be turned on if the camera has gone into night mode and turned off in day mode. `false`: The IR illuminator is independent of day/night mode |
| `NozzlePosition` | `false` | `true` `false` | admin: read, write operator: read viewer: read | Stores the current PT position as the washing position in `NozzlePresetData` and enables the washer button on the live view page. The washer can also be triggered with the auxiliary command `tt:WashingProcedure` if the washer button is not available on your camera. `true`: The current PT position is stored as the washing position in `NozzlePresetData`. `false`: `NozzlePresetData` has not stored the washing position. |
| `NozzlePresetData` | `pan=0.0:tilt=0.0` | `pan=-180.0 ... 180.0:tilt=-90.0 ... 45.0` | admin: read, write operator: read viewer: read | Stores a string that holds the PT position of the washer nozzle. |
| `WasherPumpPin` | 1 | 1–4 | admin: read, write operator: read viewer: read | Selects the pin that the washer pump is connected to. |
| `WasherPumpTime` | 10 | 10–60 | admin: read, write operator: read viewer: read | Specifies the duration of time in seconds that the pump should run during a washing procedure. |
| `WasherWiperTime` | 10 | 7–60 | admin: read, write operator: read viewer: read | Specifies the duration of time in seconds that the wiper should run during a washing procedure. |
| `SpotFocus` | `false` | `true` `false` | admin: read, write operator: read viewer: read | Enables spot focus mode for auto focus, causing it to adjust focus based only on the center of the scene. |

#### PTZ.Preset

The preset PTZ position configuration, that should be set using `/axis-cgi/com/ptzconfig.cgi`.

PTZ.Preset.P#

| Parameter name | Default value | Valid values | Security level (get/set) | Description |
| --- | --- | --- | --- | --- |
| `Name` | Hardware dependent | A string | admin: read, write operator: read viewer: read | **Note:** This parameter has been **deprecated**. The name of the preset configuration. |
| `ImageSource` | Hardware dependent | 0 (in products with 1 ImageSource, 0 ... 4 (in products with 4 ImageSource (4 inputs + Quad)). | admin: read operator: read viewer: read | **Note:** This parameter has been **deprecated**. The `ImageSource.I#` this `Preset.P#` configuration is connected to. |
| `HomePosition` | 1 | An unsigned integer. | admin: read, write operator: read viewer: read | The `Position.P#` group number of the home position. |

info

The **#** is replaced with a group number starting from zero, e.g. **PTZ.Preset.P0**.

#### PTZ.Preset.P.Position

This group contains the parameters that describes the individual preset positions.

info

This parameter group has been deprecated. Use `/axis-cgi/com/ptzconfig.cgi` and `/axis-cgi/com/ptz.cgi?` query to manage the list of preset positions instead. As of version 2.00 of the PTZ preset API **Properties.API.PTZ.Presets.Version=2.00** adding, updating and removing presets using `/axis-cgi/param.cgi` is no longer supported.

#### PTZ.Sync

Parameter for configuration of zoom sync functionality. This parameter only exists on bispectral products where the visual and thermal channels have synchronized pan/tilt.

info

The `areazoom` command will zoom relative to the current field of view of the respective channels when zoom sync is enabled.

PTZ.Sync.S#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `ZoomSync` | `disabled` | `disabled` and `vapix` | admin: read, write  
operator: read  
viewer: read | Configure zoom synchronization between visual and thermal channel on bispectral products.  
`disabled` = Zoom sync is disabled.  
`vapix` = Zoom sync is enabled. Synchronize the zoom VAPIX position when zoom changes. |

### PTZ control

Control the pan, tilt and zoom behavior of a PTZ unit.

The PTZ control is device-dependent. For information about supported parameters and actual parameter values, check the specification of the Axis PTZ driver used. The following table is only an overview.

-   **Security level**: Viewer with access to PTZ controls.
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?<argument>=<value>\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/com/ptz.cgi?<argument>=<value>\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `camera=<string>` | `1` (default) `...` _Product/release dependent. Check the product's release notes._ | Selects the video channel. If omitted the default value `camera=1` is used. This argument is only valid for Axis products with more than one video channel. That is cameras with multiple view areas and video encoders with multiple video channels. Please note that `camera=all` is only valid for `query=presetposcam`, `query=presetposcamdata` and `query=attributes`. |
| `whoami=<string>` | `1` | Returns the name of the system-configured device driver. |
| `center=<int>,<int>` | `<x>,<y>` | Center the camera on positions x,y where x,y are pixel coordinates in the client video stream. |
| `areazoom=<int>,<int>,<int>` | `<x>,<y>,<z=>1>` | Centers on positions `x`,`y` (like the `center` command) and zooms by a factor of z/100. If z is more than 100 the image is zoomed in (for example; z=300 zooms in to 1/3 of the current field of view). If z is less than 100 the image is zoomed out (for example; z=50 zooms out to twice the current field of view).Note: In some Axis products, the precision of `areazoom` can be strongly improved by calibrating the lens offset parameters. |
| `imagewidth=<int>` | `1, ...` _Product/release dependent. Check the product's release notes._ | Required in conjunction with `center` or `areazoom` if the image width displayed is different from the default size of the image, which is product-specific. |
| `imageheight=<int>` | `1, ...` _Product/release dependent. Check the product's release notes._ | Required in conjunction with `center` or `areazoom` if the image height is different from the default size of the image, which is product-specific. |
| `move=<string>` | `home` `up` `down` `left` `right` `upleft` `upright` `downleft` `downright` `stop` | **Absolute**:Moves the image 25 % of the image field width in the specified direction. **Relative**: Moves the device approx. 50-90 degrees in the specified direction (driver-specific). `home` = Moves the image to the home position. `up` = Moves the image up. `down` = Moves the image down. `left` = Moves the image to the left. `right` = Moves the image to the right. `upleft` = Moves the image up diagonal to the left. `upright` = Moves the image up diagonal to the right. `downleft` = Moves the image down diagonal to the left. `downright` = Moves the image down diagonal to the right. `stop` = Stops the pan/tilt movement. |
| `pan=<float>` | `-180.0 ... 180.0` | Pans the device to the specified absolute coordinates. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ |
| `tilt=<float>` | `-180.0 ... 180.0` | Tilts the device to the specified absolute coordinates. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ |
| `zoom=<int>` _Float input will be handled as int. No assumptions can be made on the correct rounding._ | `1 ... 9999` If Support.S#.DigitalZoom is true, zoom ranges are `1` ... `19999` for `zoom` and `-19999` ... `19999` for `rzoom`. | Zooms the device `n` steps to the specified absolute position. A high value means zoom in, a low value means zoom out. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ |
| `focus=<int>` (driver specific) _Float input will be handled as int. No assumptions can be made on the correct rounding._ | `1 ... 9999` | Moves focus `n` steps to the specified absolute position. A high value means focus far, a low value means focus near. |
| `iris=<int>` _Float input will be handled as int. No assumptions can be made on the correct rounding._ | `1 ... 9999` | Moves iris `n` steps to the specified absolute position. A high value means open iris, a low value means close iris. |
| `brightness=<int>` _Float input will be handled as int. No assumptions can be made on the correct rounding._ | `1 ... 9999` | Moves brightness `n` steps to the specified absolute position. A high value means brighter image, a low value means darker image. |
| `rpan=<float>` _Products with Panopsis technology: Does not have any effect in Overview mode._ | `-360.0 ... 360.0` | Pans the device `n` degrees relative to the current position. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ |
| `rtilt=<float>` _Products with Panopsis technology: Does not have any effect in Overview mode._ | `-360.0 ... 360.0` | Tilts the device `n` degrees relative to the current position. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ |
| `rzoom=<int>` _Products with Panopsis technology: Does not have any effect in Overview mode._ | `-9999 ... 9999` If Support.S#.DigitalZoom is true, zoom ranges are `1` ... `19999` for `zoom` and `-19999` ... `19999` for `rzoom`. | Zooms the device n steps relative to the current position. Positive values mean zoom in, negative values mean zoom out. |
| `rfocus=<int>` | `-9999 ... 9999` | Moves focus `n` steps relative to the current position. Positive values mean focus far, negative values mean focus near. |
| `riris=<int>` | `-9999 ... 9999` | Moves iris `n` steps relative to the current position. Positive values mean open iris, negative values mean close iris. |
| `rbrightness=<int>` | `-9999 ... 9999` | Moves brightness `n` steps relative to the current position. Positive values mean brighter image, negative values mean darker image. |
| `autofocus=<string>` | `on` `off` | Enable/disable auto focus. `on` = Enables auto focus. `off` = Disables auto focus. |
| `autoiris=<string>` | `on` `off` | Enable/disable auto iris. `on` = Enable auto iris. `off` = Disable auto iris. |
| `continuouspantiltmove=<int>,<int>` | `-100 ... 100,-100 ... 100` | Continuous pan/tilt motion. Positive values mean right (pan) and up (tilt), negative values mean left (pan) and down (tilt). `0,0` means stop. _Products with Panopsis technology: If the product moves to a position where the Panopsis (fisheye) lens is visible, the product will go to Overview mode._ Values as `<pan speed>`,`<tilt speed>`. Optional arguments are: `proportionalspeed=<string>`, valid values: disabled. This option only affects proportional speed for individual commands and is only supported on mechanical PTZ domes when both `Properties.PTZ.DigitalPTZ=no` and `Properties.PTZ.DriverManagement=no` have been chosen ( API-version 1.1). |
| `continuouszoommove=<int>` _Products with Panopsis technology: Does not have any effect in Overview mode._ | `-100 ... 100` | Continuous zoom motion. Positive values mean zoom in and negative values mean zoom out. `0` means stop. |
| `continuousfocusmove=<int>` | `-100 ... 100` | Continuous focus motion. Positive values mean focus far and negative values mean focus near. `0` means stop. |
| `continuousirismove=<int>` | `-100 ... 100` | Continuous iris motion. Positive values mean iris open and negative values mean iris close. `0` means stop. |
| `continuousbrightnessmove=<int>` | `-100 ... 100` | Continuous brightness motion. Positive values mean brighter image and negative values mean darker image. `0` means stop. |
| `auxiliary=<string>` | `<function name>` | Activates/deactivates auxiliary functions of the device where `<function name>` is the name of the device specific function. Check in driver's documentation or in response to `info=1` for information about `<function name>`. |
| `gotoserverpresetname=<string>` | `<preset name>` Preset positions are configured using `/axis-cgi/com/ptzconfig.cgi`, see [PTZ configuration](#ptz-configuration). | Move to the position associated with the `<preset name>`. |
| `gotoserverpresetno=<int>` | `1, ...` Preset positions are configured using `/axis-cgi/com/ptzconfig.cgi`, see [PTZ configuration](#ptz-configuration) | Move to the position associated with the specified preset position number. |
| `gotodevicepreset=<int>` | `<preset pos>` Preset positions are configured using `/axis-cgi/com/ptzconfig.cgi`, see [PTZ configuration](#ptz-configuration) | Bypasses the presetpos interface and tells the device to go directly to the preset position number `<preset pos>` stored in the device, where the `<preset pos>` is a device-specific preset position number. This may also be a device-specific special function. |
| `speed=<int>` | `1 ... 100` | Sets the move speed of pan and tilt. |
| `imagerotation=<int>` _Product/release dependent. Check the product's release notes._ | `0` `90` `180` `270` | If PTZ command refers to an image stream that is rotated differently than the current image setup, then the image stream rotation must be added to each command with this argument to allow the Axis product to compensate. `0` = Rotate the image 0 degrees. `90` = Rotate the image 90 degrees. `180` = Rotate the image 180 degrees. `270` = Rotate the image 270 degrees. |
| `ircutfilter=<string>` _Product/release dependent. Check the product's release notes._ | `auto` _Product/release dependent. Check the product's release notes._ `on` `off` | Control the IR cut filter. `auto` = Automatically switch between `on` and `off` depending on the lighting conditions. `on` = Apply the filter, that is block IR light. `off` = Remove the filter, that is allow IR light to reach the image sensor. |
| `backlight=<string>` | `on` `off` | Control the backlight compensation. `on` = Bright mode. `off` = Normal mode. |
| `query=<string>` | `limits` `mode` `position` (driver specific) `presetposall` _Character encoding for plain-text responses defined by the PTZ.ResponseEncoding parameter._ `presetposcam` _Character encoding for plain-text responses defined by the PTZ.ResponseEncoding parameter._ `presetposcamdata` _Character encoding for plain-text responses defined by the PTZ.ResponseEncoding parameter._ `speed` `auxiliary` _Product/release dependent. Check the product's release notes._ `attributes` _Product/release dependent. Check the product's release notes._ | Returns the current status. `limits` = PTZ limits for the Axis product. `mode` = Products with Panopsis technology: The current mode (overview or normal). `position` = Values for current position. `presetposall` = Current preset positions for all video channels. Optional arguments are:  
\- `format=<string>`, valid values: json`presetposcam` = Current preset positions for a video channel. Optional arguments are:  
\- `format=<string>`, valid values: json`presetposcamdata` = Returns the configured preset positions with position data measured in degrees. Optional arguments are:  
\- `format=<string>`, valid values: json`speed` = Values for pan/tilt speed. `auxiliary` = Returns supported auxiliary commands. Optional arguments are:  
\- `format=<string>`, valid values: json`attributes` = Returns various PTZ attributes such as zoom, focus and speed-steps. Optional arguments are:  
\- `format=<string>`, valid values: json  
\- `group=<string>`, valid values: zoom, focus, speed, speeddry. All attributes will be returned if no group argument is given. |
| `info=<int>` | `1` | Returns a description of available PTZ commands. |

**Example: Request information about available PTZ commands on video channel 3**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?info=1&camera=3"
```

```bash
GET /axis-cgi/com/ptz.cgi?info=1&camera=3Host: <servername>
```

If PTZ is available the response may look like this:

```bash
Available commands:{camera=\[n\]}whoami=yescenter=\[x\],\[y\]  imagewidth=\[n\]  imageheight=\[n\]areazoom=\[x\],\[y\],\[z\]  imagewidth=\[n\]  imageheight=\[n\]move={ home | up | down | left | right | upleft | upright | downleft | downright | stop }pan=\[abspos\]tilt=\[abspos\]zoom=\[n\]rpan=\[offset\]rtilt=\[offset\]rzoom=\[offset\]continuouspantiltmove=\[x-speed\],\[y-speed\]  proportionalspeed={ disabled }continuouszoommove=\[speed\]setserverpresetname=\[name\]setserverpresetno=\[n\]removeserverpresetname=\[name\]removeserverpresetno=\[n\]gotoserverpresetname=\[name\]gotoserverpresetno=\[n\]query={ position | limits | presetposcam | presetposall | status }  format={ json }
```

#### Query=attributes response

The response is sectioned for each camera/channel number, with each section containing a list of attribute/data pairs. The data can be either a single value or an entire array of entries each containing one or more key/value pairs. Please note that supported attributes are product dependent. Also, the order of cameras/channels sections in the response may not be in the number order.

| Group | Attribute | Data type | Valid values | Description |
| --- | --- | --- | --- | --- |
| speed | `speeds` | An array of entries containing the keys "value" and "speed". | Value: integer 1–100 Speed: integer ≥ 1 or float > 0.0. | Mapping between VAPIX pan/tilt speed values and the actual speed (degrees/sec). |
| focus | `minFocus` | An array of entries containing the keys "value" and "distance". | Value: integer 1–100 Distance: integer ≥ 0. | Mapping between VAPIX focus limit values and the actual distance (centimeters). |
| zoom | `maxOpticalZoomMag` | Single value. | Integer ≥ 1 or float ≥ 1.0. | The maximum optical magnification at tele zoom. |
| zoom | `maxDigitalZoomMag` | Single value. | Integer ≥ 1 or float ≥ 1.0. | The maximum digital magnification at tele zoom. |
| zoom | `zoomSteps` | An array of entries containing the keys "value", "zoom" and the optional "visible". | Value: integer 1–19999 Zoom: integer ≥ 1 or float ≥ 1.0 Visible: boolean "true" or "false" | Mapping between VAPIX zoom positions and magnification. The optional "visible" key helps the GUI determine if the entry as an option for the zoom limit configuration should be shown or not. Default value is "true". |
| zoom | `isOverview` | Single value. | Boolean "true" or "false" | If "true", the camera on this channel is stationary and does not perform movements itself, instead acting as a proxy to control another channel to which movement commands are forwarded. |

**Query attribute response format - plain text**

```bash
Attributes for camera \[n\]<attribute a>=<array entry1>, <array entry2>,...<attribute b>=<array entry1>, <array entry2>,...<attribute c>=<single value>Attributes for camera \[m\]...
```

The attribute array entries are comma separated while the key/value pairs are separated by a | as shown below:

```bash
<key 1>=<value 1> |<key 2>=<value 2> |... |<key N>=<value N>
```

**Example**

```bash
Attributes for camera 1speeds=value=1 | speed=0.05,value=9 | speed=0.16,value=14 | speed=2,value=24 | speed=2.1,value=40 | speed=9,value=58 | speed=28,value=80 | speed=74,value=100 | speed=150maxOpticalZoomMag=30
```

**Query attribute response format - json**

```bash
{  "Camera <n>": {    "<attribute a>": \[<arrary entry 1>, <array entry 2>\],    "<attribute b>": \[<arrary entry 1>, <array entry 2>\],    "<attribute c>": "<single value>"  },  "Camera <m>": {    ...  }}
```

The attribute array entries are json objects with one or more key/value pairs:

```bash
{  "<key 1>": "<value 1>",  "<key 2>": "<value 2>",  ...,  "<key N>": "<value N>"}
```

**Example**

```bash
{    "Camera 1": {        "maxOpticalZoomMag": "30",        "zoomSteps": \[            {                "value": "1",                "zoom": "1"            },            {                "value": "3868",                "zoom": "2"            },            {                "value": "7736",                "zoom": "3"            },            {                "value": "9999",                "zoom": "3.584961"            }        \]    }}
```

### PTZ configuration

Set and configure PTZ preset positions and On screen display (OSD) control.

A server preset saved with name will also get a number and vice versa. You can use both `setserverpresetname`/`removeserverpresetname` and `setserverpresetno`/`removeserverpresetno` commands on the same preset.

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptzconfig.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/com/ptzconfig.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `camera=<int>` | `1 ...` | The video channel. If omitted, the default video channel is used. You must specify `all` to select all video channels. Please note that `camera=all` is only valid for `removeallserverpresets`. |
| `osdmenu=<string>` | `open` `close` `up` `down` `left` `right` `select` `back` | Commands to control the OSD menu in the external device. Note that support for different commands, and the behavior of the commands, are driver dependent. `open` = Open. `close` = Close. `up` = Move up. `down` = Move down. `left` = Move to the left. `right` = Move to the right. `select` = Select. `back` = Go back. |
| `setserverpresetname=<string>` | `<preset name>` _<preset name> is a string with a maximum of 31 characters. The following five characters are not allowed: "<>~:_ | Associates the current position to `<preset name>` as a preset position in the Axis product. |
| `setserverpresetno=<int>` | `1, ...` | Saves the current position as a preset position number in the Axis product. |
| `renameserverpresetno=<int>&newname=<string>` | `1, ..., <preset name>` _<preset name> is a string with a maximum of 31 characters. The following five characters are not allowed: "<>~:_ | Set a new name for the specified preset position. |
| `home=<string>` | `yes` | Makes the current position the home position for the Axis product. Used with `setserverpresetname` or `setserverpresetno`. |
| `removeserverpresetname=<string>` _When a home preset is removed a new default home preset will be created before the request can be answered._ | `<preset name>` _<preset name> is a string with a maximum of 31 characters. The following five characters are not allowed: "<>~:_ | Removes the specified preset position associated with `<preset name>`. |
| `removeserverpresetno=<int>` _When a home preset is removed a new default home preset will be created before the request can be answered._ | `1 ...` | Removes the specified preset position. |
| `removeallserverpresets=<string>` | `yes` | Removes all presets for a specified camera. Please note that the presets will be removed from all active PTZ channels when `camera=all` is used. |
| `setdevicepreset=<int>` | `<preset pos>` | Bypasses the presetpos interface and tells the device to save its current position as preset position `<preset pos>` directly in the device, where `<preset pos>` is a device-specific preset position number. This may also be a device-specific special function |

### Responses
#### Success for `/axis-cgi/com/ptz.cgi`

A successful response for `/axis-cgi/com/ptz.cgi`.

-   **HTTP code**: `204 No content`
-   **Content-Type**: `text/plain`

#### Error for `/axis-cgi/com/ptz.cgi`

An error response for `/axis-cgi/com/ptz.cgi`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Error:\[message\]
```

#### Success for info=1

If PTZ is available a successful response for `info=1`. The generated response values for this argument depends on what functions the Axis product supports and what functions that are enabled.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Available commands:{camera=\[n\]}whoami=yescenter=\[x\],\[y\]  imagewidth=\[n\]  imageheight=\[n\]areazoom=\[x\],\[y\],\[z\]  imagewidth=\[n\]  imageheight=\[n\]move={ home | up | down | left | right | upleft | upright | downleft |downright | stop }pan=\[abspos\]tilt=\[abspos\]zoom=\[n\]focus=\[n\]iris=\[n\]brightness=\[offset\]rpan=\[offset\]rtilt=\[offset\]rzoom=\[offset\]rfocus=\[offset\]riris=\[offset\]rbrightness=\[offset\]autofocus={ on | off }autoiris={ on | off }ircutfilter={ on | off | auto }backlight={ on | off }continuouspantiltmove=\[x-speed\],\[y-speed\]continuouszoommove=\[speed\]continuousfocusmove=\[speed\]continuousirismove=\[speed\]continuousbrightnessmove=\[speed\]auxiliary=\[function\]setserverpresetname=\[name\]setserverpresetno=\[n\]removeserverpresetname=\[name\]removeserverpresetno=\[n\]gotoserverpresetname=\[name\]gotoserverpresetno=\[n\]gotodevicepreset=\[n\]speed=\[n\]osdmenu=\[cmd\]query={ speed | position | limits | presetposcam | presetposall }
```

#### Success for query=speed

If PTZ is available a successful response for `query=speed`. The generated response values for this argument depends on what functions the Axis product supports and what functions that are enabled.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
speed=\[speed\]
```

#### Success for query=position

If PTZ is available a successful response for `query=position`. The generated response values for this argument depends on what functions the Axis product supports and what functions that are enabled.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
pan=\[abspos\]tilt=\[abspos\]zoom=\[n\]autofocus={ on | off }autoiris={ on | off }
```

#### Success for query=limits

If PTZ is available a successful response for `query=limits`. The generated response values for this argument depends on what functions the Axis product supports and what functions that are enabled.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
MinPan=\[abspos\]MaxPan=\[abspos\]MinTilt=\[abspos\]MaxTilt=\[abspos\]MinZoom=\[n\]MaxZoom=\[n\]MinIris=\[n\]MaxIris=\[n\]MinFocus=\[n\]MaxFocus=\[n\]MinFieldAngle=\[n\]MaxFieldAngle=\[n\]MinBrightness=\[offset\]MaxBrightness=\[offset\]
```

#### Success for query=presetposcam

If PTZ is available a successful response for `query=presetposcam`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Preset Positions for camera \[n\]presetposno\[n\]=p\[n\]presetposno1=Home
```

#### Success for query=presetposall

If PTZ is available on a multichannel product several cameras can be listed. A successful response for `query=presetposall` .

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Preset Positions for camera 1presetposno\[n\]=p\[n\]presetposno1=HomePreset Positions for camera 2presetposno\[n\]=p\[n\]presetposno1=Home...
```

#### Error for query=\[invalid value\]

An error response for an invalid value, `query=[invalid value]`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Error:query: unknown value: \[invalid value\]
```

#### Success for whoami=1

If PTZ is available a successful response for `whoami=1`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
\[Driver name\]
```

#### Success for `/axis-cgi/com/ptzconfig.cgi`

A successful response for `/axis-cgi/com/ptzconfig.cgi`.

-   **HTTP code**: `204 No content`
-   **Content-Type**: `text/plain`

#### Error for `/axis-cgi/com/ptzconfig.cgi`

An error response for `/axis-cgi/com/ptzconfig.cgi`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Error:\[message\]
```

## PTZ driver management API

Axis products with serial ports can be connected to an external PTZ device, for example a pan-tilt motor, that provides PTZ functionality. To control the external PTZ device, a driver matching the external device must first be activated on the physical channels where the functionality is wanted.

### Overview

Only one external PTZ device driver can be active at any given time. In addition, there can be zero or more _static_ drivers active. The static drivers are always active and controls the internal hardware. Static drivers also operate in parallel with the external PTZ device driver and cannot be listed or manipulated using any Driver Management CGI.

All compatible external PTZ device drivers are included on the Axis product’s software as of API version 1.1. Please note that when using device software of earlier API versions that some drivers may be included in the Axis product's software, but most drivers must be retrieved from Axis support and uploaded to the camera by the user before they can be activated.

The PTZ driver management API consists of the following CGIs:

| Name | Description |
| --- | --- |
| `/axis-cgi/ptz/ptzuploader.cgi` | List uploaded drivers.Please note that uploading and removing drivers are no longer necessary and will have no effect as of API version 1.1, as all compatible PTZ drivers will be embedded part of device software. Because of this, the options to upload and remove drivers have been deprecated. This feature is no longer supported as of API version 2.0. |
| `/axis-cgi/ptz/ptzupgrader.cgi` | Activate or deactivate a driver for a video channel, detailed in [Install and unistall PTZ driver](#install-and-unistall-ptz-driver). |

For information about serial ports, see [Serial port API](/vapix/network-video/serial-port-api/).

#### Identification

**API version 1.0**

-   **API Discovery**: `id=ptz-driver-management version=1.0`
-   **Property**: `Properties.PTZ.DriverManagement=yes`
-   **AXIS OS**: 5.20 and later
-   **Product category**: Axis video products with serial ports.

**API version 1.1**

-   **API Discovery**: `id=ptz-driver-management version=1.1`
-   **Property**: `Properties.PTZ.DriverManagement=yes`
-   **Property**: `Properties.PTZ.EmbeddedDrivers=yes`
-   **AXIS OS**: 10.12 and later
-   **Product category**: Axis video products with serial ports.

#### Obsoletes

-   `ptzupdate.cgi` - Removed, since drivers are now associated with video channels and not directly with ports.
-   `ptzadmin.cgi`\- Removed, `/axis-cgi/ptz/ptzupgrader.cgi` should be used instead.
-   `ptzuploader.cgi` to upload and remove PTZ drivers - Deprecated since API version 1.1. Support has been removed completely since API version 2.0.
-   The port argument used in `/axis-cgi/ptz/ptzupgrader.cgi` - Deprecated since API version 1.1. The port will always be set to the one required by the driver.
-   `root.PTZ.PTZDrivers` - Removed since API version 2.0. Use `/axis-cgi/ptz/ptzupgrader.cgi` to list active drivers.
-   `root.PTZ.PTZDriverVersions`\- Deprecated since API version 1.1, since the PTZ drivers are embedded in the software from that version. Removed completely since API version 2.0.
-   `root.PTZ.SerDriverStatuses` - Removed since API version 2.0 Use `PTZ.PTZDriverStatuses` instead.

### Use cases
#### List all PTZ drivers

This example will show you how to list all PTZ drivers available for activation and see which drivers are currently active. Available PTZ drivers have an ID that can be used to either activate or deactivate them.

1.  List all PTZ drivers.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzuploader.cgi?list=yes"
```

```bash
GET /axis-cgi/ptz/ptzuploader.cgi?list=yesHost: <servername>
```

2.  Parse the HTTP response. A response where a Pelco driver is active on channels 3 and 4 will look like this:

Successful response example

```bash
<?xml version="1.0"?>  <driverentry>    <id>1</id>    <driver>Pelco</driver>    <driverversion>4.17</driverversion>    <installed>      <ch>3</ch>      <ch>4</ch>    </installed>    <deviceTypes>      <deviceType>Generic</deviceType>      <deviceType>DD5-C</deviceType>      <deviceType>Esprit ES30C/ES31C</deviceType>      <deviceType>LRD41C21</deviceType>      <deviceType>LRD41C22</deviceType>      <deviceType>Spectra III</deviceType>      <deviceType>Spectra IV</deviceType>      <deviceType>Spectra Mini</deviceType>      <deviceType>Videotec DTRX3/PTH310P</deviceType>      <deviceType>Videotec ULISSE</deviceType>      <deviceType>PTK AMB</deviceType>      <deviceType>YP3040</deviceType>      <deviceType>XP40</deviceType>    </deviceTypes>    <deviceIdRange>      <min>1</min>      <max>255</max>    </deviceIdRange>  </driverentry>  <driverentry>    <id>2</id>    <driver>Visca/EVI</driver>    <driverversion>4.11</driverversion>    <installed></installed>    <deviceTypes>      <deviceType>EVI-G20/G21</deviceType>      <deviceType>EVI-D30/D31</deviceType>      <deviceType>EVI-D100/D100P</deviceType>      <deviceType>EVI-D70/D70P</deviceType>      <deviceType>EVI-D70F/D70PF</deviceType>      <deviceType>DCP-27</deviceType>    </deviceTypes>    <deviceIdRange>      <min>1</min>      <max>7</max>    </deviceIdRange>  </driverentry>  <driverentry>    <id>3</id>    <driver>ARTP</driver>    <driverversion>1.1.0</driverversion>    <installed></installed>  </driverentry>  ...</root>
```

3.  List all PTZ drivers and the driver status for all channels.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzuploader.cgi?list=yes&status=yes"
```

```bash
GET /axis-cgi/ptz/ptzuploader.cgi?list=yes&status=yesHost: <servername>
```

4.  Parse the HTTP response. A response where a Pelco driver is active with the device type `Generic` and device id=1 on channel 1 will look like this:

Successful response example

```bash
<?xml version="1.0"?>  <driverentry>    <id>1</id>    <driver>Pelco</driver>    <driverversion>4.17</driverversion>    <installed>      <ch>1</ch>    </installed>    <deviceTypes>      <deviceType>Generic</deviceType>      <deviceType>DD5-C</deviceType>      <deviceType>Esprit ES30C/ES31C</deviceType>      <deviceType>LRD41C21</deviceType>      <deviceType>LRD41C22</deviceType>      <deviceType>Spectra III</deviceType>      <deviceType>Spectra IV</deviceType>      <deviceType>Spectra Mini</deviceType>      <deviceType>Videotec DTRX3/PTH310P</deviceType>      <deviceType>Videotec ULISSE</deviceType>      <deviceType>PTK AMB</deviceType>      <deviceType>YP3040</deviceType>      <deviceType>XP40</deviceType>    </deviceTypes>    <deviceIdRange>      <min>1</min>      <max>255</max>    </deviceIdRange>  </driverentry>  ...  <status>    <channel id="1">      <activeDriver>        <driverStatus>2</driverStatus>        <driverId>1</driverId>        <driverDeviceType>Generic</driverDeviceType>        <driverDeviceId>1</driverDeviceId>      </activeDriver>    </channel>    <channel id="2"></channel>    <channel id="3"></channel>    <channel id="4"></channel>  <status></root>
```

Successful response example

```bash
200 OK
```

Error response example when the product can not use uploadable PTZ driver mode

```bash
HTTP/1.1 409
```

Error response example when the list driver fails

```bash
HTTP/1.1 400
```

#### Install a PTZ driver

This example will show you how to install a PTZ driver and perform PTZ movements on your camera. Individual addresses can be set for connected devices that are daisy chained.

1.  Install a PTZ driver.

Install a PTZ driver with ID 2 on the default video channel.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverid=2"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverid=2Host: <servername>
```

Install a PTZ driver with ID 2 on video channel 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverid=2&channel=1"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverid=2&channel=1Host: <servername>
```

Install a driver with ID 2 on video channel 1 using device type `Generic` and giving it the device ID address 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverid=2&channel=1&deviceType=Generic&deviceId=1"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverid=2&channel=1&deviceType=Generic&deviceId=1Host: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
200 OK
```

This error response will appear if the driver installation fails due to an invalid request.

Error response example

```bash
HTTP/1.1 400
```

This error response will appear if the driver installation fails due to the product not being configured to use uploadable PTZ driver mode.

Error response example

```bash
HTTP/1.1 409
```

This error response will appear if the driver installation fails due to misconfiguration or hardware errors.

Error response example

```bash
HTTP/1.1 500
```

This error response will appear if the driver installation fails due to an already installed driver on the channel.

Error response example

```bash
HTTP/1.1 501
```

#### Change device type or device ID settings

This example will show you how to change the device type or device ID settings of an already active driver or video channel.

1.  Change device ID settings to 2 for the driver with ID 1 that was previously activated on channel 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverId=1&channel=1&deviceId=2"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverId=1&channel=1&deviceId=2Host: <servername>
```

2.  Change device type settings to "Spectra IV" for the Pelco driver with ID 1 previously active on channel 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverId=1&channel=1&deviceType=Spectra%20IV"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverId=1&channel=1&deviceType=Spectra%20IVHost: <servername>
```

#### Uninstall a PTZ driver

This example will show you how to uninstall a PTZ driver from a video channel.

1.  Uninstall a PTZ driver from video channel 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?driverid=0&channel=1"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?driverid=0&channel=1Host: <servername>
```

2.  Parse the HTTP response.

Successful response example

```bash
200 OK
```

This error response will appear if the driver uninstall fails due to misconfiguration or hardware errors.

Error response example

```bash
HTTP/1.1 500
```

This error response will appear if the driver uninstall fails due to the product not being configured to use uploadable PTZ driver mode.

Error response example

```bash
HTTP/1.1 409
```

This error response will appear if the driver uninstall fails due to the request being invalid.

Error response example

```bash
HTTP/1.1 400
```

#### Check if a PTZ driver is active

This example will show you how to check whether a PTZ driver is active on a channel.

The channel status is included in the response from any CGI request as long as the argument `status=yes` is provided. It is also possible to retrieve the status in a separate `/axis-cgi/ptz/ptzuploader.cgi` request. The status contains information related to active drivers on each channel, such as the driver status, ID and optionally also the device type and ID when this is supported.

1.  Check if the driver is active on channel 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzuploader.cgi?status=yes"
```

```bash
GET /axis-cgi/ptz/ptzuploader.cgi?status=yesHost: <servername>
```

2.  The following response will return for a 4–channel device if a Pelco driver with ID 1 is active on channel 1 with device type `Generic` and `device id=1`.

```bash
<?xml version="1.0" ?><root>    <status>        <channel id="1">            <activeDriver>                <driverStatus>2</driverStatus>                <driverId>1</driverId>                <driverDeviceType>Generic</driverDeviceType>                <driverDeviceId>1</driverDeviceId>            </activeDriver>        </channel>        <channel id="2" />        <channel id="3" />        <channel id="4" />    </status></root>
```

Successful response example

```bash
200 OK
```

This error response will appear if the `GET` status fails due to the product not being configured to use uploadable PTZ driver mode.

Error response example

```bash
HTTP/1.1 409
```

This error response will appear if the `GET` status fails.

Error response example

```bash
HTTP/1.1 400
```

### API Specifications
#### List PTZ drivers

This method should be used when you want to list available PTZ drivers.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzuploader.cgi?<argument>=<value>\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/ptz/ptzuploader.cgi?<argument>=<value>\[<argument>=<value>\]Host: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `list=<string>` | `yes` | `yes`: The Axis product lists the uploaded drivers in an XML listing. |
| `status=<string>` | `yes` `no` (default value) | `yes`: Appends the driver status for all channels in the response. |

**Return value - Success**

Using `list` will return the driver listing in the following format:

```bash
<?xml version=1.0"?><root>  <driverentry>    <id>driverid</id>    <driver>drivername</driver>    <driverversion>driverversion</driverversion>    <installed>      <ch>1</ch>      <ch>2</ch>      ...      <ch>n</ch>    </installed>    <deviceTypes>      <deviceType>deviceType\_1</deviceType>      ...      <deviceType>deviceType\_N</deviceType>    </deviceTypes>    <deviceId>      <min>min\_device\_id</min>      <max>max\_device\_id</max>    </deviceId>  </driverentry>  ...</root>
```

Please note that there is one `driverentry` element for each available driver.

| Parameter | Description |
| --- | --- |
| `driverid` | The driver ID. |
| `drivername` | The driver name. |
| `driverversion` | The driver version. |
| `installed` | Contains the number of a video channel where the driver is active. No `<ch>` on a video channel means that the channel has no active driver. Optional attributes are device type and device ID configured for the active driver. These attributes will be left out if the driver can not support them. |
| `deviceTypes` | Contains one or more `<deviceType>` elements with the name of a supported device type for the driver. This argument is only included if the driver supports selecting device types. |
| `deviceIdRange` | Contains the `<min>` and `<max>` elements that represents the range of integer values that can be assigned as the address identifier to a device managed by the driver. |

#### Install and unistall PTZ driver

This method should be used when you want to install or uninstall a driver on a video channel. Drivers may have been previously uploaded, or may be included in the device software.

After activating a driver, the external device can be controlled using the [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/) and, if the driver supports it, [Serial port API](/vapix/network-video/serial-port-api/).

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ptz/ptzupgrader.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/ptz/ptzupgrader.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `driverid=<int>` | `0` (default) `...` | The driver ID parsed from the XML and returned from `/axis-cgi/ptz/ptzuploader.cgi?list=yes`. The value `0` deactivates the currently active driver without installing another driver. |
| `channel=<integer>` | `1` (default) `...` | The video channel where the driver should be installed. An external PTZ device driver active on the channel will be deactivated when a new driver is activated. |
| `deviceType=<string>` |  | The type of device the video channel should be configured to communicate with in cases where the driver can be used with different hardware variants. Valid device types can be parsed from the XML returned with `/axis-cgi/ptz/ptzuploader.cgi?list=yes` when this argument is supported. It will default to the first entry on the list of device types identified with `<driverid>`, but without any guarantees of successful communication with the connected device. |
| `deviceId=<integer>` |  | The address of the device the video channel should be configured to communicate with when several devices are connected in a daisy chain. Defaults to the channel number when it is not supplied. The range of allowed addresses can be parsed from the XML returned by `/axis-cgi/ptz/ptzuploader.cgi?list=yes`. |
| `status=<string>` | `yes` `no` (default value) | Appends the driver status for all channels in the response. |

**Response**

```bash
<?xml version="1.0"?><root>  <status>    <channel id="1">      <activeDriver>        <driverStatus>driverstatus</driverStatus>        <driverId>driverid</driverId>        <driverDeviceType>devicetype</driverDeviceType>        <driverDeviceId>deviceid<driverDeviceId>      </activeDriver>    </channel>    ...    <channel id="n"></channel>  </status></root>
```

| Parameter | Valid values | Parameter |
| --- | --- | --- |
| `channel` |  | Contains channel specific statuses. Limited to one channel element for each channel and uses the channel number as its attribute. |
| `activeDriver` |  | Data related to the active driver. |
| `driverStatus` | `2 = active` `1 = malfunction` `0 = not installed` | The current status of the driver. |
| `driverId` |  | The ID number of the active driver defined in the response from `/axis-cgi/ptz/ptzuploader.cgi?list=yes`. |
| `driverDeviceType` |  | The device type of the active driver. |
| `driverDeviceId` |  | The device ID of the active driver. |

#### Driver management parameters

The [Parameter management](/vapix/network-video/parameter-management/) API should be used to implement the following parameters. Valid values for `[video_channel]` ranges from `1` to `root.PTZ.NbrOfCameras`.

**root.PTZ.PTZDriverStatuses.Driver#Status**

The parameters in this group are used when you want to find out the statuses for PTZ drivers associated with the (serial) ports.

-   **List security level**: viewer

Syntax

```bash
PTZ.PTZDriverStatuses.Driver\[video\_channel\]Status
```

| Parameter | Description |
| --- | --- |
| `Driver[video_channel]Status=<integer>` | Holds the status of the driver active on `[video_channel]` and can be interpreted as: `0`: No driver is active or the driver is being activated/configured. `1`: The installation file is invalid or incompatible. `2`: The driver is malfunctioning. `3`: The driver is active. |

An active driver with state 3 may briefly change to state 0 while it is reconfigured, such as when the device type is changed.

## Queuing API
### Description

The control queue is used to administrate the PTZ control in an environment where several users have PTZ control. A control blocking function lets one user at the time have PTZ control. The other users are put in the control queue. Once a user gained PTZ control PTZ requests can be sent as usual. The rules of the queue are based on what type of access control the user has. For example a user with admin access control will be prioritized over a user with viewer access control. To distinguish individuals using the same user account a cookie is sent the first time the user sends a PTZ request.

### Prerequisites
#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 5.20 and later.

Products with mechanical PTZ require:

-   **Property**: `Properties.PTZ.PTZ=yes`

Products with digital PTZ require:

-   **Property**: `Properties.PTZ.DigitalPTZ=yes`

### Parameters

**PTZ.Various**

PTZ.Various.V#

| Parameter | Default values | Valid values _(Integer ranges may be overridden by configuration file for driver)_ | Access control | Description |
| --- | --- | --- | --- | --- |
| `CtlQueueing` | Product/driver dependent | `true` `false` | admin: read, write operator: read, write viewer: read | The parameter is `true` if control queuing is supported by the driver. If enabled, access to controlling the PTZ unit is limited to the client currently possessing the control. `true` = Control queuing is allowed. `false` = Control queuing is not allowed. |
| `CtlQueueLimit` | Product/driver dependent | `1 ... 100` | admin: read, write operator: read, write viewer: read | Set the maximal number of clients in a control queue. |
| `CtlQueuePollTime` | Product/driver dependent | `5 ... 3600` | admin: read, write operator: read, write viewer: read | Set the maximum time in seconds between poll-requests, which an existing client in the control queue must send, to stay active in the queue. |

**PTZ.UserCtlQueue.U#**

Parameters for the different users in the control queue. These parameters only have effect if the control queue is enabled (`PTZ.Various.V#.CtlQueuing=true`). In that case, cookies will be required for all calls to `/axis-cgi/com/ptz.cgi`.

The `#` is replaced with a group number starting from `0`, for example `PTZ.UserCtlQueue.U5.UserGroup`.

PTZ.UserCtlQueue.U#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `UserGroup` | User group dependent | `Administrator` `Operator` `Viewer` `Event` `Autotracking` `Guardtour` `Recordedtour` `Usergroup` `...` | admin: read operator: read | Name of the user group.`Guardtour` = preset tour (guard tour)`Recordedtour` = recorded tour (guard tour)`Autotracking` = mechanical autotracking |
| `UseCookie` | User group dependent | `yes` `no` | admin: read, write operator: read | If users from a user group shall be separated by using a cookie. `yes` = Cookies are used. `no` = Cookies are not used. |
| `Priority` | User group dependent | `1 ... 100` | admin: read, write operator: read | The priority value. `1` is the highest value. |
| `TimeoutType` | User group dependent | `timespan` `activity` `infinity` | admin: read, write operator: read | Set the timeout type to use. `timespan` = The user possesses the PTZ control during the time defined by `TimeoutTime`. `activity` = The user possesses the PTZ control during the time defined by `TimeoutTime` parameter. The `TimeoutTime` parameter is reset after every PTZ movement. `infinity` = The user has infinite PTZ control. |
| `TimeoutTime` | User group dependent | `1 ... 3600` | admin: read, write operator: read | The time used for each `TimeoutType`. The value is ignored when `TimeoutType` is `infinity`. |

### PTZ control queue

This CGI handles requests concerning the control queue. If the PTZ control queuing mechanism is enabled (`PTZ.Various.V1.CtlQueueing=true`) for a video channel, control of PTZ units is limited to the client currently possessing it.

info

Cookies are enabled by default when enabling PTZ control queue.

-   **Security level**: Viewer with access to PTZ controls
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptzqueue.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/com/ptzqueue.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `control=<string>` | `request` `drop` `query` | `request` = Requests PTZ control. `drop` = Drops the PTZ control or leaves the queue. `query` = Reports the current status for the client. For possessing clients with no peers existing in the queue, `request` will reset the control timer. For all other clients, `request` will have the same effect as `query`. |
| `camera=<int>` | `1 ...` _Product-dependent. Check the product's Release notes._ | The video channel number. If omitted, the default channel is used. |

Request PTZ control for video channel 2.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptzqueue.cgi?control=request&camera=2"
```

```bash
GET /axis-cgi/com/ptzqueue.cgi?control=request&camera=2Host: <servername>
```

### Response

**PTZ control queue response**

The `200 OK` response on success for `request` and `query` has a format that enables simple JavaScript parsing.

**Success**

-   **HTTP Code**: `200 OK`

Body:

```bash
<a name="<pos>"</a><a name="<seconds>"</a><a name="<period>"></a>
```

-   `<pos>` can have a value from `0` to the maximum value of how many clients are allowed in the queue. This value is the given position in the queue. `0` means that the client is not in the queue, `1` means control is possessed. If the value is `0` the other values are undefined.
-   `<seconds>` is the estimated number of seconds remaining, that is for position `1` the remaining control time and for other positions, the time until position `1` is reached. If the value is `-1` the time remaining to get control cannot be estimated. This means that a client in the queue has the `TimeoutType` set to `infinity`.
-   `<period>` is the recommended time in seconds when the client should send a new `control=query` requests. To stay active in the queue the client must regularly send the request `control=query` to the Axis product. An inactive client will automatically be removed from the queue.

Control requested.

-   **HTTP Code**: `200 OK`

```bash
<a name="3"></a><a name="410"></a><a name="5"></a>
```

This means the client was assigned queue position 3. The expected number of seconds until control is possessed is 410 and the recommended time until the next request is 5 seconds.

**Failure**

On failure no anchor elements are provided, instead the error message in plain text.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Error:<error information>
```

## Focus recall API
### Description

The VAPIX® Focus recall API gives instant focus even in challenging light conditions when used for management of camera settings in PTZ zones. Focus recall uses memory zones which consist of a pan, tilt and/or zoom range where the specified camera settings should be applied. Zones can be added, listed and removed. Each zone is identified by a unique index. The settings in a zone is applied when the center coordinate of the camera is inside the PTZ area that is defined by the zone.

#### Identification

VAPIX® Focus recall is available if:

-   **Property**: `Properties.MemoryZones.MemoryZones=yes`

Additional read-only properties available through `/axis-cgi/param.cgi`:

-   **Property**: `Properties.MemoryZones.MaxNbrOfMemoryZones=X`
-   **Property**: `Properties.MemoryZones.Version=0.1`
-   **API Discovery**: `id=ptz-focus-recall`

**AXIS OS**: 6.25 and later.

**Product category**: PTZ or Zoom cameras.

### Common examples

Check if Focus recall is supported.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.MemoryZones.MemoryZones"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.MemoryZones.MemoryZonesHost: <servername>
```

**Response if memoryzones are supported:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Properties.MemoryZones.MemoryZones=yes
```

Save current focus position as a memoryzone.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/add.cgi?focus=current"
```

```bash
GET /axis-cgi/memoryzones/add.cgi?focus=currentHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "name": "memory\_zone\_1",    "index": 1}
```

Using a certain zoom range.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/add.cgi?focus=current&zoomrange=1111:3333"
```

```bash
GET /axis-cgi/memoryzones/add.cgi?focus=current&zoomrange=1111:3333Host: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "name": "memory\_zone\_1",    "index": 1}
```

Remove the current memory zone.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/remove.cgi"
```

```bash
GET /axis-cgi/memoryzones/remove.cgiHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{    "name": "memory\_zone\_1",    "index": 1}
```

Remove the memory zone having index 4

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/remove.cgi?index=4"
```

```bash
GET /axis-cgi/memoryzones/remove.cgi?index=4Host: <servername>
```

Response:

```bash
None
```

### Add memory zone

Use `/axis-cgi/memoryzones/add.cgi` to add a memory zone.

**Request**

-   **Security level**: Administrator, Operator, Viewer with PTZ control
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/add.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/memoryzones/add.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `name=<string>` | string | Name of the memory zone (UTF-8 encoded). Maximum length 32 characters. Optional |
| `polygon=<string>` | string | Image related coordinates of the corners of the memory zone stored as float values in a string of coordinate pairs, <x1>,<y1>:<x2>,<y2>:<x3>,<y3>:<x4>,<y4>.Origo (0.0, 0.0) is in the middle of the image. X-coordinates have positive direction to the right. Y-coordinates have positive direction up.The coordinates of the image have coordinates (-1.0, -1.0), (1.0, -1.0), (1.0, 1.0) and (-1.0, 1.0).Coordinates less than -1.0 and greater than 1.0 are accepted to indicate points outside the image.All coordinates relate to the currently configured default rotation and mirroring settings for the channel. Optional. |
| `zoomrange=<string>` | string | Zoom coordinates in VAPIX scale in format, <zoom\_min>:<zoom\_max>, defines the zoomrange where the memoryzone is valid. Valid range 1 - 19999. Default value "1:19999". Optional. |
| `camera=<integer>` | integer | The index of the camera source to apply the request. Default is 1. This argument is not required when there is only one camera source in the product. Optional. |
| `focus=<string>` | string | The focus configuration to be saved in the memory zone. Valid values are: 1 - 9999 | current VAPIX scale, 1 - 9999 for focus position, current to save the current focus position of the camera. Mandatory. |

**Response**

Responses from `/axis-cgi/memoryzones/add.cgi`

**Success**

If the request is successful:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
{"name" : "name",  "index" : index}
```

HTTP Code: `GeneralSuccess` response is returned. See [General success response](#general-success-response-focus-recall-api).

**Error**

If an error occurred:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
{"error": { "id":<error code>, "message":"<optional error message in English>" }}
```

HTTP Code: `GeneralError` response is returned. See [General error response](#general-error-response-focus-recall-api).

### Remove memory zone

Use `/axis-cgi/memoryzones/remove.cgi` to delete a memory zone.

**Request**

-   **Security level**: Administrator, Operator, Viewer with PTZ control
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/remove.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/memoryzones/remove.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `index=<integer>` | integer | The index of the memoryzone to apply the request. This argument is not required when removing all saved memoryzones. Optional |
| `camera=<integer>` | integer | The index of the camera source to apply the request. Default is 1. This argument is not required when there is only one camera source in the product. Optional. |
| `removeall=<integer>` | integer | _removeall=1_ will remove all configured zones. Optional. |

**Response**

Responses from `/axis-cgi/memoryzones/remove.cgi`

**Success**

If the request is successful:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
Empty
```

HTTP code: `GeneralSuccess` response is returned. See [General success response](#general-success-response-focus-recall-api).

**Error**

If an error occurred:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
{"error": { "id":<error code>, "message":"<optional error message in English>"}}
```

HTTP code: `GeneralError`response is returned. See [General error response](#general-error-response-focus-recall-api).

### List memory zones

Use `/axis-cgi/memoryzones/list.cgi` to list the memory zones.

**Request**

-   **Security level**: Administrator, Operator, Viewer with PTZ control
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/list.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/memoryzones/list.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `camera=<integer>` | integer | The index of the camera source to apply the request. Default is 1. This argument is not required when there is only one camera source in the product. Optional. |
| `query=list | current | view` | listcurrentview | List all memory zones in the camera.Query for the memory zone located at the current coordinate.Query details about memoryzones located inside the current view. |

**Response**

Responses from `/axis-cgi/memoryzones/list.cgi`

**Success**

If the request is successful:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Response for **query=list** if at least one zone has been added:

Body:

```bash
\[{ "name" : "name", "index" : index, "ptpolygon" : "0.0,0.0:0.0,0.0:0.0,0.0:0.0,0.0", "zoomrange" : "0:0", "focus" : position},...\]
```

Response for **query=list** if there are no zones:

Body:

```bash
\[\]
```

Response for **query=current** if there is a zone at the current coordinates:

Body:

```bash
{ "name" : "name", "index" : index }
```

Response for **query=current** if there is no zone at the current coordinates:

Body:

```bash
{    "name": "",    "index": -1}
```

Response for **query=view** if there is one or more zone within the current view:

Body:

```bash
\[{ "name" : "name", "index" : index, "polygon" : "0,0:0,0:0,0:0,0", "ptpolygon" : "0.0,0.0:0.0,0.0:0.0,0.0:0.0,0.0", "zoomrange" : "0:0", "focus" : position}, ...\]
```

Response for **query=view** if there are no zones in the current view:

Body:

```bash
\[\]
```

HTTP code: `GeneralSuccess` response is returned. See [General success response](#general-success-response-focus-recall-api).

**Error**

If an error occurred:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
{ "error": { "id":<error code>, "message":"<optional error message in English>" }}
```

HTTP code: `GeneralError` response is returned. See [General error response](#general-error-response-focus-recall-api).

### Goto memory zone

Use `/axis-cgi/memoryzones/goto.cgi` to go to and focus on memory zone coordinates.

**Request**

-   **Security level**: Administrator, Operator, Viewer with PTZ control
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/memoryzones/goto.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/memoryzones/goto.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `camera=<integer>` | integer | The index of the camera source to apply the request. Default is 1. This argument is not required when there is only one camera source in the product. Optional. |
| `index=<integer>` | integer | Index of the memory zone. Mandatory. |

**Response**

Responses from `/axis-cgi/memoryzones/goto.cgi`

**Success**

If the request is successful:

```bash
HTTP code: 204 OKContent-Type: application/json
```

Body:

```bash
Empty
```

HTTP code: `GeneralSuccess` response is returned. See [General success response](#general-success-response-focus-recall-api).

**Error**

If an error occurred:

```bash
HTTP code: 200 OKContent-Type: application/json
```

Body:

```bash
{ "error": { "id":<error code>, "message":"<optional error message in English>" }}
```

HTTP code: `GeneralError` response is returned. See [General error response](#general-error-response-focus-recall-api).

### General success response

General success response from Focus recall API.

-   **HTTP code**: : `200 OK`
-   **Content-Type**: `application/json`

Body:

```bash
{  "name" : "name",  "index" : index}
```

### General error response

General error response from Focus recall API.

-   **HTTP code**: : `200 OK`
-   **Content-Type**: `application/json`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><memoryzonesResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/memoryzones.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></memoryzonesResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `memoryzonesResponse` | Contains the response. |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `501` | Other error | All |
| `502` | Unknown memory zone command | All |
| `503` | Unknown index | `/axis-cgi/memoryzones/remove.cgi`, `/axis-cgi/memoryzones/list.cgi` |
| `504` | List full | `/axis-cgi/memoryzones/add.cgi`, `/axis-cgi/memoryzones/goto.cgi` |
| `505` | Name already defined | `/axis-cgi/memoryzones/add.cgi` |
| `506` | Name too long | `/axis-cgi/memoryzones/add.cgi` |

## PTZ events and actions
### PTZ preset reached event

The PTZ preset reached event is `true` when the camera stops at a preset position. Preset positions are defined for each video channel or view area. There is one event for each preset position. The `Any` event is `true` if the camera stops at any of the preset positions defined on that channel or view area.

Note that `Nice name` can be changed.

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:PTZPresets/tnsaxis:Channel_X`
-   **Type**: Stateful
-   **Nice name**: `PTZ preset reached on channel X`

**Source instance**

-   **Nice name**: `Preset token`
-   **Type**: integer
-   **Name**: `PresetToken`

| Value | Nice name |
| --- | --- |
| `-1` | `Any` |
| `1` | `Home`Note that `Home`is the default and this can be changed. |
| `2` | User-defined name |
| `...` | `...` |
| `number of presets defined` | User-defined name |

**Data instance**

-   **Nice name**: Preset reached
-   **Type**: boolean
-   **Name**: `on_preset`
-   **isPropertyState**: `true`

### PTZ moving event

The PTZ movement event is `true` when the camera is moving due to a PTZ operation.

The event can for example be used to prevent motion detection from being triggered while the camera moves due to a PTZ operation.

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:Move/tnsaxis:Channel_X`
-   **Type**: Stateful
-   **Nice name**: `PTZ movement on channel X`

**Source instance**

-   **Nice name**: `PTZ channel`
-   **Type**: integer
-   **Name**: `PTZConfigurationToken`

| Value | Nice name |
| --- | --- |
| `X` | `Channel X` |

**Data instance**

-   **Nice name**: Moving
-   **Type**: boolean
-   **Name**: `is_moving`
-   **isPropertyState**: `true`

### PTZ ready event

The PTZ ready event is `true` when the PTZ functionality is ready to be used. The event can for example be used to detect that PTZ is ready to use after restart or after a PTZ driver has been installed.

For products with multiple view areas or multiple video channels, there is one event for each view area or video channel. The `channel` element in `SourceInstance` specifies the view area or video channel.

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:PTZReady`
-   **Type**: Stateful
-   **Nice name**: `PTZ ready`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

**Data instance**

-   **Nice name**: Ready
-   **Type**: boolean
-   **Name**: `ready`
-   **isPropertyState**: `true`

### PTZ control queue event

The PTZ control queue event shows the user who is controlling the PTZ functionality.

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:ControlQueue`
-   **Type**: Stateful
-   **Nice name**: `PTZ control queue`

**Source instance**

-   **Nice name**: `PTZ channel`
-   **Type**: integer
-   **Name**: `PTZConfigurationToken`

| Value | Nice name |
| --- | --- |
| `1` | `Channel 1` |
| `2` | `Channel 2` |
| `...` | `...` |
| `number of channels` | `Channel n` |

**Data instance**

-   **Nice name**: Queue owner
-   **Type**: string
-   **Name**: `queue_owner`
-   **isPropertyState**: `true`

### Autotracking event

info

These events have been deprecated as of AXIS OS version 10.12 and will no longer receive updates. The methods found in [PTZ Autotracker API](/vapix/network-video/ptz-autotracker-api/) should be used instead.

The Autotracking event is `true` when autotracking is active.

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:AutoTracking`
-   **Type**: Stateful
-   **Nice name**: `Autotracking`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

The table below is valid for multichannel products. For single channel products, the channel is always 0.

| Value | Nice name |
| --- | --- |
| `1` | — |
| `2` | — |
| `...` | — |
| `n = number of video channels` | — |

**Data instance**

-   **Nice name**: Tracking motion
-   **Type**: boolean
-   **Name**: `tracking`
-   **isPropertyState**: `true`

### PTZ error event

A PTZ error event `tns1:PTZController/tnsaxis:PTZError` is emitted if the PTZ functionality is malfunctioning.

To retrieve the event declaration, use `aev:GetEventInstances`.

Event declaration:

```bash
<tns1:PTZController aev:NiceName="PTZController">    <tnsaxis:PTZError wstop:topic="true" aev:NiceName="PTZ error">        <aev:MessageInstance>            <aev:SourceInstance>                <aev:SimpleItemInstance aev:NiceName="Channel" Type="xsd:int" Name="channel" />            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance Type="xsd:string" Name="ptz\_error" />            </aev:DataInstance>        </aev:MessageInstance>    </tnsaxis:PTZError></tns1:PTZController>
```

**Topic**

-   **Name**: `tns1:PTZController/tnsaxis:PTZError`
-   **Type**: Stateless
-   **Nice name**: `PTZ error`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

| Value | Nice name |
| --- | --- |
| `1` | `Channel 1` |
| `2` | `Channel 2` |
| `...` | `...` |
| `number of channels` | `Channel n` |

**Data instance**

-   **Nice name**: `PTZ error`
-   **Type**: string
-   **Name**: `ptz_error`
-   **isPropertyState**: `false`

### Go to PTZ preset action

Use the Go to PTZ preset action to steer the camera view to a PTZ preset position. When the action is completed, the camera view will return to the home position.

This action can be run as:

-   **fixed action** — stay at the preset position for a predefined time (defined by parameter `home_timeout`)
-   **unlimited action** — stay at the preset position as long as all event conditions are fulfilled.  
    \- **Action ID**: `com.axis.action.fixed.goto.preset`  
    \- **Action ID**: `com.axis.action.unlimited.goto.preset`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `channel` | Unsigned integer | Video channel |
| `preset_name` | String | Name of the PTZ preset to go to. Preset names can be retrieved from `/axis-cgi/com/ptz.cgi?query=presetposall` |
| `home_timeout` | Unsigned integer or `-1` | Number of seconds to wait before returning to the home position. Use `-1` if the camera view should not return to the home position. |

### Autotracking action

info

These actions have been deprecated as of AXIS OS version 10.12 and will no longer receive updates. The methods found in [PTZ Autotracker API](/vapix/network-video/ptz-autotracker-api/) should be used instead.

Use the autotracking action to start autotracking from a preset position. When the action is triggered, the camera moves to the preset position `preset_name` and starts autotracking from that position.

The action can be run as

-   **The action can be run as**: **fixed action** — continue autotracking until there are no moving objects
-   **unlimited action** — continue autotracking as long as all conditions are fulfilled

The action can for example be used in an action rule triggered by a signal from an I/O port. Consider a PTZ camera monitoring a number of doors with door sensors connected to the camera’s I/O ports. When one of the doors is opened, the action rule is triggered and the camera moves to a preset position facing that door and starts follow a person or vehicle coming out of the door.

-   **Action ID**: `com.axis.action.fixed.motiontracking`
-   **Action ID**: `com.axis.action.unlimited.motiontracking`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `channel` | Unsigned integer | The video channel. |
| `goto_home_timeout` | Unsigned integer | Fixed action: Number of seconds to wait before returning to the home position when tracking stops. |
| `preset_name` | String | The PTZ preset position from which tracking should start. |

## Speed dry API
### Description

The VAPIX® Speed dry API function enables the camera to shake so that water moves over the dome enabling the water to dry faster, thus clearing the camera’s view faster. Water drops from rain or washing equipment may prevent a clear camera view.

#### Identification

VAPIX® Speed dry is available if:

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.SpeedDry.SpeedDry=yes`

**AXIS OS**: 5.65 and later.

**Product category**: PTZ cameras.

### Common examples

Get speed dry capabilites

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/speeddry/getcapabilities.cgi"
```

```bash
GET /axis-cgi/speeddry/getcapabilities.cgiHost: <servername>
```

Response:

```bash
operations/oneshot/@method xs:enumoperations/oneshot/@runtime xs:integeroperations/oneshot/@idletime sx:integer
```

Initiate speed dry operation

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/speeddry/oneshot.cgi"
```

```bash
GET /axis-cgi/speeddry/oneshot.cgiHost: <servername>
```

Response:

```bash
HTTP code:  200 OKContent-Type: text/plain
```

### Get speed dry

Use `/axis-cgi/com/ptz.cgi?auxiliary=speeddry` executes a one-shot speed dry operation. After the operation has finished the server has an idle time of ~20 seconds, during which other speed dry requests are discarded.

**Request**

-   **Security level**: Administrator, Operator, Viewer with PTZ control
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/ptz.cgi?auxiliary=speeddry"
```

```bash
GET /axis-cgi/com/ptz.cgi?auxiliary=speeddryHost: <servername>
```

**Response**

Responses from `/axis-cgi/com/ptz.cgi?auxiliary=speeddry`

The response is always the same, there is no success or failure information.

```bash

```
### General success response

General success response from the Speed dry API.

-   **HTTP code**: : `200 OK`
    
-   **Content-Type**: `application/json`
    
-   **HTTP code**: `204 No content`
    
-   **Content-Type**: `N/A`
    

### General error response

General error response from the Speed dry API.

-   **HTTP code**: : `200 OK`
    
-   **Content-Type**: `application/json`
    
-   **HTTP code**: `204 No content`
    
-   **Content-Type**: `N/A`
    

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><speeddryResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/speeddry.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></speeddryResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `speeddryResponse` | Contains the response. |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `204` | No content |  |