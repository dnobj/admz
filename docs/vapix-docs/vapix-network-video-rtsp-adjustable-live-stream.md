---
title: RTSP Adjustable Live Stream
url: "https://developer.axis.com/vapix/network-video/rtsp-adjustable-live-stream/"
category: vapix
subcategory: network-video
sha256: fa00b38ea14ebe15e57b8f3f36f6c617e87e92cdaa621a0c7a79d0309b3e6f7d
scraped_at: "2026-01-09T15:20:56.066Z"
page_height: 6119
---

# RTSP Adjustable Live Stream

## Description

The RTSP Adjustable Live Stream API provides the information that makes it possible to change a subset of the settings of a stream without having to restart it. Please note that `videozprofile=storage` is incompatible with this API and a `400 Bad Request` will be returned if it is used.

### Model

The API consists of two RTSP methods that should be used with the URL option `adjustablelivestream=1`, detailed in the table below:

| Method | Description |
| --- | --- |
| `GET_PARAMETER` Adjustable-Stream-Settings | Retrieves a list of supported settings that can be changed. |
| `SET_PARAMETER` Adjustable-Stream-Configuration | Applies updated settings to an ongoing stream. |

Please note that it is not recommended to increase the values above what was used when starting the stream as some video players cannot handle values above the initial SDP data.

### Identification

To identify the presence of this API on your device you should use one of the two methods detailed below:

**RTSP**

Use the method `GET_PARAMETER` with the request parameter Adjustable-Stream-Settings. The request has to be made on a live stream with the URL option `adjustablelivestream=1` set. The feature is supported if the response is `200 OK` and one or more of the settings are listed. If, however, the response is `451 Parameter not understood`, the feature is not supported.

**Parameter CGI**

If the property below exists and has one or more settings listed the Adjustable Stream Settings feature is supported.

-   **Property**: `Properties.API.RTSP.AdjustableStreamSettings=<one or more settings>`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Adjust the stream quality

This example could be used to retrieve supported, adjustable live stream settings. This can then be used to change the quality of an ongoing live stream.

1.  Request a video stream with the default settings and enable the adjustable live stream.

```bash
rtsp://<camera-ip>/axis-media/media.amp?adjustablelivestream=1
```

2.  Retrieves the supported adjustable live settings for the stream.

```bash
GET\_PARAMETER rtsp://<camera-ip>/axis-media/media.amp?adjustablelivestream=1 RTSP/1.0CSeq: 9Content-Type: text/parametersSession: W1CzY9GU2dz8QMfEDate: Fri, 19 Nov 2021 15:54:48 GMTContent-Length: <content length>Adjustable-Stream-Settings:
```

```bash
RTSP/1.0 200 OKCSeq: 9Content-Type: text/parametersServer: GStreamer RTSP serverSession: W1CzY9GU2dz8QMfE;timeout=5Date: Fri, 19 Nov 2021 15:54:48 GMTContent-Length: <content length>Adjustable-Stream-Settings: compression,fps,videokeyframeinterval,videomaxbitrate,videozstrength
```

3.  Change the settings of the ongoing stream.

```bash
SET\_PARAMETER rtsp://<camera-ip>/axis-media/media.amp?adjustablelivestream=1 RTSP/1.0CSeq: 10Content-Type: text/parametersSession: W1CzY9GU2dz8QMfEDate: Fri, 19 Nov 2021 15:54:48 GMTContent-Length: <content length>Adjustable-Stream-Configuration: fps=30,compression=30,videomaxbitrate=100000
```

```bash
RTSP/1.0 200 OKCSeq: 10Server: GStreamer RTSP serverSession: W1CzY9GU2dz8QMfE;timeout=5Date: Fri, 19 Nov 2021 15:54:48 GMT
```

## API specifications
### RTSP Adjustable-Stream-Settings

This method should be used when you wish to retrieve the settings that can be applied with [RTSP Adjustable-Stream-Configuration](#rtsp-adjustable-stream-configuration).

**Request**

-   **Security level**: Viewer
-   **Method**: `GET_PARAMETER`

Request body syntax

```bash
GET\_PARAMETER rtsp://<camera-ip>/axis-media/media.amp?adjustablelivestream=1 RTSP/1.0Content-Type: text/parametersAdjustable-Stream-Settings
```

**Return value - Success**

Returns a comma separated list of supported adjustable stream settings.

-   **RTSP Code**: `200 OK`
-   **Content-Type**: `text/parameters`

Response body syntax

```bash
RTSP/1.0 200 OKContent-Type: text/parametersAdjustable-Stream-Settings: compression,fps,videokeyframeinterval,videomaxbitrate,videozstrength
```

### RTSP Adjustable-Stream-Configuration

This method should be used when you wish to configure the settings of an ongoing stream. This will apply to either all settings or none if the request fails. Supported settings are:

-   compression
-   fps
-   videokeyframeinterval
-   videomaxbitrate
-   videozstrength

Please note that the settings above will behave the same as the URL options found in the [Video streaming](/vapix/network-video/video-streaming/) API.

**Request**

-   **Security level**: Viewer
-   **Method**: `SET_PARAMETER`

Request body syntax

```bash
SET\_PARAMETER rtsp://<camera-ip>/axis-media/media.amp?adjustablelivestream=1 RTSP/1.0Content-Type: text/parametersAdjustable-Stream-Configuration: fps=30,compression=30,videomaxbitrate=100000
```

**Return value - Success**

Returns `200 OK` if all settings were successfully applied.

-   **RTSP Code**: `200 OK`

Response body

```bash
RTSP/1.0 200 OK
```

**Return value - Failure**

Returns `400 Bad Request` if the requested settings were invalid or failed to apply.

-   **RTSP Code**: `400 Bad Request`

Response body

```bash
RTSP/1.0 400 Bad Request
```

### Properties.API.RTSP.AdjustableStreamSettings

This method should be used when you wish to retrieve the supported settings that can be applied with [RTSP Adjustable-Stream-Configuration](#rtsp-adjustable-stream-configuration).

**Request**

-   **Security level**: Viewer

Request body syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=root.Properties.API.RTSP.AdjustableStreamSettings"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=root.Properties.API.RTSP.AdjustableStreamSettingsHost: <servername>
```

**Return value - Success**

Returns a comma separated list of supported, adjustable stream settings.

-   **HTTP Code**: `200 OK`

Response body syntax

```bash
root.Properties.API.RTSP.AdjustableStreamSettings="compression,fps,videokeyframeinterval,videomaxbitrate,videozstrength"
```