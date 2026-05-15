---
title: Dewarped views
url: "https://developer.axis.com/vapix/network-video/dewarped-views/"
category: vapix
subcategory: network-video
sha256: d2c45fa91b4de8a3d590ed814d296790a9e8664cd50bca35c91930cf12e9fd7f
scraped_at: "2026-01-09T15:19:34.567Z"
page_height: 11522
---

# Dewarped views

Axis 360°/180° cameras, such as AXIS M3007–PV network camera, have multiple view modes. In addition to the 360° overview, the cameras have several dewarped views: 180° panoramic views, quad views and view areas with PTZ functionality.

The view modes are similar to view areas which are available in other Axis products, but there are some differences. Each view mode has its own set of valid resolutions and rotations. When requesting a video stream from one of the dewarped views, a valid resolution must be included in the request. It is not possible to use the same resolution for all dewarped views.

Before using dewarped views, the camera orientation should be configured. Available view modes differ depending on if the camera is mounted on a wall, in the ceiling or on a desk.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## View modes

The view modes are defined by parameters in the dynamic group `Image.I<#>` where `#` is the view mode number starting from `0`. The table below lists the available view modes.

| `#` | Name | **Access**([1](#user-content-fn-1)) | Description |
| --- | --- | --- | --- |
| `0` | `Overview` | read/write | A non-dewarped 360° view. |
| `1` | `Panorama` | read/write | One dewarped 180° panoramic view. |
| `2` | `Double Panorama` | read/write | Two dewarped 180° panoramic views. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |
| `3` | `Quad View` | read/write | Four dewarped 90° views, one for each direction. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |
| `4` | `View Area 1` | read/write | A dewarped 90° view with PTZ (pan/tilt/zoom) functionality. |
| `5` | `View Area 2` | read/write | A dewarped 90° view with PTZ (pan/tilt/zoom) functionality. |
| `6` | `View Area 3` | read/write | A dewarped 90° view with PTZ (pan/tilt/zoom) functionality. |
| `7` | `View Area 4` | read/write | A dewarped 90° view with PTZ (pan/tilt/zoom) functionality. |
| `8` | `Panorama Corner Left` | read/write | Zoomed in, 180° wide angle view of the outermost left corner. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |
| `9` | `Panorama Corner Right` | read/write | Zoomed in, 180° wide angle view of the outermost right corner. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |
| `10` | `Double Panorama Corner` | read/write | A split 180° panoramic view of the outermost corners of the camera view. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |
| `11` | `Corridor` | read/write | Side-by-side view of two different preset view areas. Note that this option isn’t available if the mounting position ‘Wall’ has been selected (`ImageSource.I0.CameraTiltOrientation=0`). |

## Setup

This section describes how to set up the camera to use view modes and dewarped views.

1.  Check if the Axis product supports dewarping. See [Identification](#identification).
    
2.  Set camera orientation. See [Set camera orientation](#set-camera-orientation).
    
3.  Enable and configure views. See [Enable and configure views](#enable-and-configure-views).
    

### Identification

To check if the Axis product supports dewarping, use the `Property.Image.Dewarp` parameter.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.Dewarp"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.DewarpHost: <servername>
```

Response example:

```bash
Properties.Image.Dewarp=yes
```

The parameter has the following values:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Properties.Image.Dewarp` | `yes` `no` | `yes` = Dewarping is supported. `no` = Dewarping is not supported. |

If the parameter does not exist, dewarping is not supported.

### Set camera orientation

When using dewarped views, the camera orientation should be configured. The camera orientation setting affects how view modes and the pan/tilt/zoom functionality are working.

To set the camera orientation, use:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=ImageSource.I0.CameraTiltOrientation"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=ImageSource.I0.CameraTiltOrientationHost: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `ImageSource.I0.CameraTiltOrientation` | `-90` `0` `90` | `-90` = Select this option if the camera is mounted in the ceiling. `0` = Select this option if the camera is mounted on a wall. `90` = Select this option if the camera is mounted on a desk or similar. |

info

Some dewarped views are not available if ImageSource.I0.CameraTiltOrientation=0, that is, if the camera is mounted on a wall. See table in section [View modes](#view-modes).

### Enable and configure views

View modes are handled similar to view areas in other Axis products and are defined by parameters in the dynamic group `Image.I<#>` where `#` is the view mode number starting from `0`.

To retrieve the total number of available views, use parameter `Properties.Image.NbrOfViews`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.NbrOfViews"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.NbrOfViewsHost: <servername>
```

Response:

```bash
<int>
```

To check if a view is available and enabled use `Image.I<#>.Enabled`.

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Image.I<#>.Enabled` | `yes` `no` | `yes` = The view is enabled `no` = The view is disabled. |

An enabled view can be configured in the same way as view areas in other Axis products. Use PTZ commands to move and change direction of the view modes that support PTZ. PTZ can be disabled if users should not be able to modify views after initial setup.

## Using dewarped views

This section describes how to use dewarped views. Since each view mode has its own set of resolutions and rotations, the valid resolutions and rotations should be retrieved before requesting a video stream. It is not possible to use the same resolution for all view modes.

If the request contains an invalid resolution or if the view is disabled, the response is: `HTTP Error: 400 Bad Request`.

### Check valid resolutions and rotations

To check resolutions and rotations supported by the Axis product, use the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Properties.Image.Resolutions` | `<int>x<int>[,<int>x<int>[,...]]` | A list of resolutions supported by the Axis product. |
| `Properties.Image.Rotation` | `<int>[,<int>[,...]]` | A list of rotations supported by the Axis product. Unit: degrees |

To check the resolutions and rotations available for view mode `#`, use the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Properties.Image.I<#>.Resolution` | `<int>x<int>[,<int>x<int>[,...]]` | A list of resolutions supported by view mode `<#>`. |
| `Properties.Image.I<#>.Rotation` | `<int>[,<int>[,...]]` | A list of rotations supported by view mode `<#>`. Unit: degrees |

To check the name of view mode `<#>`, use the following parameter:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Image.I<#>.Name` | `string` | The name of view mode `#`. |

For a list of view mode names, see [View modes](#view-modes).

To retrieve supported resolutions for view mode `Overview` (that is, view mode `0`), use:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.I0"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.I0Host: <servername>
```

Response:

```bash
root.Properties.Image.I0.Rotation=0,180root.Properties.Image.I0.Resolution=2592x1944,2048x1536,1600x1200,1280x960,1024x768,800x600,640x480,480x360,320x240,240x180,160x120
```

### Request a stream

Video streams and images (snapshots) from the dewarped views can be requested using the HTTP API or the RTSP API. To request a stream or image from a particular view mode, the `camera` argument must be specified. Set `camera` to the view mode group number plus `1`. A valid resolution must be included in the request.

For more information about video requests, see the Video streaming API available at [www.axis.com/vapix](http://www.axis.com/vapix)

### Request a motion JPEG stream

The example outlined in this section shows how to request a Motion JPEG stream from view mode `Panorama` using the HTTP API.

Start by checking the group number:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Image.\*.Name"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Image.\*.NameHost: <servername>
```

Response example:

```bash
root.Image.I0.Name=Overviewroot.Image.I1.Name=Panoramaroot.Image.I2.Name=Double Panoramaroot.Image.I3.Name=Quad Viewroot.Image.I4.Name=View Area 1root.Image.I5.Name=View Area 2root.Image.I6.Name=View Area 3root.Image.I7.Name=View Area 4root.Image.I8.Name=Panorama Corner Leftroot.Image.I9.Name=Panorama Corner Rightroot.Image.I10.Name=Double Panorama Cornerroot.Image.I11.Name=Corridor
```

The response shows that the group number is `1`.

Check that the view is enabled:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Image.I1.Enabled"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Image.I1.EnabledHost: <servername>
```

Retrieve the available resolutions:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.I1.Resolution"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.I1.ResolutionHost: <servername>
```

Response

```bash
Properties.Image.I1.Resolution=1600x600,1280x480,960x360,640x240,480x180,320x120
```

Request a Motion JPEG stream using one of the valid resolutions from the response above. Since the group number is `1`, the `camera` argument should be set to `2`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/mjpg/video.cgi?camera=2&resolution=1600x600"
```

```bash
GET /axis-cgi/mjpg/video.cgi?camera=2&resolution=1600x600Host: <servername>
```

### Request an H.264 stream

The example outlined in this section shows how to request an H.264 stream from view mode `Quad View` using the RTSP API.

Start by checking the group number:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Image.\*.Name"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Image.\*.NameHost: <servername>
```

Response example:

```bash
root.Image.I0.Name=Overviewroot.Image.I1.Name=Panoramaroot.Image.I2.Name=Double Panoramaroot.Image.I3.Name=Quad Viewroot.Image.I4.Name=View Area 1root.Image.I5.Name=View Area 2root.Image.I6.Name=View Area 3root.Image.I7.Name=View Area 4root.Image.I8.Name=Panorama Corner Leftroot.Image.I9.Name=Panorama Corner Rightroot.Image.I10.Name=Double Panorama Cornerroot.Image.I11.Name=Corridor
```

The response shows that the group number is `3`.

Check that the view is enabled:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Image.I3.Enabled"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Image.I3.EnabledHost: <servername>
```

Retrieve the available resolutions:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.I3.Resolution"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.I3.ResolutionHost: <servername>
```

Response:

```bash
Properties.Image.I3.Resolution=1600x1200,1280x960,1024x768,800x600,640x480,480x360,320x240,240x180,160x120
```

Request an H.264 stream using one of the valid resolutions from the response above. Since the group number is `3`, the `camera` argument should be set to `4`.

Request:

```bash
PLAY rtsp://<servername>/axis-media/media.amp?videocodec=h264&camera=4&resolution=800x600 RTSP/1.0CSeq: 4User-Agent: Axis AMCSession: 12345678
```

## Footnotes

1.  User access rights for parameter `Image.I<#>.Name`. [↩](#user-content-fnref-1)