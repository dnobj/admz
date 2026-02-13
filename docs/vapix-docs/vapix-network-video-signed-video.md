---
title: Signed Video
url: "https://developer.axis.com/vapix/network-video/signed-video/"
category: vapix
subcategory: network-video
sha256: 234b83dc369c2a4a746859565579fd75d1090d06eee05927db5995a6e600fd25
scraped_at: "2026-01-09T15:21:01.036Z"
page_height: 3582
---

# Signed Video

## Description

The Signed Video API contains the settings that makes it possible for applications and users to retrieve signed video content from a channel. Utilizing the parameter group `Image.I#.MPEG.SignedVideo`, where `I#` is the name of the video channel, makes it possible to validate whether the video has been manipulated or tampered with after it was exported from the camera. Supported parameters are:

| Parameter | Type | Description |
| --- | --- | --- |
| `Enabled=<yes/no>` | Boolean | Available values are `yes` or `no`. |

### Model

Signing a video can be done in two different ways:

**Default**

This method enables/disables video signing for a video channel with the regular Signed Video API parameter group `Image.I#.MPEG.SignedVideo` and the parameter `Enabled`.

**Per stream**

Signing can also be enabled/disabled directly in a stream with the Signed Video URL option, i.e. using the boolean `videosigned` that can have the values `1` or `0` and may look like this:

```bash
gst-launch-1.0 -v rtspsrc location="rtsp://<user:password>@<ip addr>/axis-media/media.amp?videosigned=1" ! fakesink silent=false
```

### Identification

-   **API Discovery**: `id=signed-video`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Setup signed video

Use these examples to sign a video and ensure its origin and authenticity. The video can then be validated to prove that it has not been manipulated with after being transferred from the camera.

**Setup signed video on a channel**

To enable video signing by default on a channel you should use the `Enabled` parameter like this:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.MPEG.SignedVideo.Enabled=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.MPEG.SignedVideo.Enabled=yesHost: <servername>
```

**Setup signed video for a stream**

To enable video signing for a stream you should use the `videosigned` URL-option like this:

```bash
gst-launch-1.0 -v rtspsrc location="rtsp://<user:password>@<ip addr>/axis-media/media.amp?videosigned=1" ! fakesink silent=false
```

## API specification
### SignedVideo.Enabled

The `Enabled` parameter is used when you wish to enable/disable video signing with the parameter handling API.

-   **List security level**: Operator, Viewer
-   **Update security level**: Admin

```bash
Image.I#.MPEG.SignedVideo.Enabled
```

Valid values for `#` ranges from 0 and up to the maximum number of channels specified by the product -1. This means that the valid values for a product with 100 channels has a range between 0–99.

| Parameter | Description |
| --- | --- |
| `Enabled=yes | no` | Enables and disables signed video for a channel. The default value is `no`. |

### RTSP URL Options

```bash
gst-launch-1.0 -v rtspsrc location="rtsp://<user:password>@<ip addr>/axis-media/media.amp?videosigned=1" ! fakesink silent=false
```

| Parameter | Description |
| --- | --- |
| `videosigned=1 | 0` | Enables and disables signed video for a stream. |

### General error codes

The following RTSP errors can be returned for all methods.

| Error code | Description |
| --- | --- |
| `400 Bad Request` | An error in the request, e.g. an invalid URL option. |
| `503 Service Unavailable` | An error in the service while handling the request. |