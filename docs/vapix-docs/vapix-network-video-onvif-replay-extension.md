---
title: Onvif Replay Extension
url: "https://developer.axis.com/vapix/network-video/onvif-replay-extension/"
category: vapix
subcategory: network-video
sha256: 0feaad4a0afae225e17e44d745efaa514a7c6dae5b15f6ee2b1bbebd12aec057
scraped_at: "2026-01-09T15:20:28.397Z"
page_height: 6923
---

# Onvif Replay Extension

The VAPIX® Onvif Replay Extension API makes it possible to receive a Real-time Transport Protocol (RTP) header extension with a Network Time Protocol (NTP) timestamp for video and/or audio streams on an Axis device. `/axis-cgi/param.cgi` can be used to enable Real-Time Streaming Protocol (RTSP) parameters as a default. Use cases include mapping a metadata object with a timestamp into a video frame within a video stream. The [Onvif Streaming specification](https://www.onvif.org/specs/stream/ONVIF-Streaming-Spec.pdf) specifies the RTP header extension.

## Identification

-   **Property**: `Properties.API.RTP.OnvifReplayExt`
-   **AXIS OS**: 10.11 and later

_Example_

[Check if the feature is supported](#check-if-the-feature-is-supported). On an open terminal, send the following `HTTP GET` request to `/axis-cgi/param.cgi`:

`curl --digest --user root:pass 'http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.API.RTP.OnvifReplayExt'`

A correct response will contain the property `"Properties.API.RTP.OnvifReplayExt=yes"`.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Retrieve video stream

Enable Onvif Replay Extension with the RTSP setup. NTP timestamps will be included in the RTP packets and the client can use them to map frames to metadata objects, synchronize video from different cameras, etc. RTP header extensions are enabled if the RTSP parameter is used.

_Example_

Open a streaming application, such as VLC, and a network URL (Media -> Open Network Stream):

`rtsp://root:pass@<servername>:554/axis-media/media.amp?videocodec=h264&onvifreplayext=1`

Check the network with, for example, a wireshark for an RTP header extension. This can also be used if you want to disable the feature [in case it was enabled by default](#check-if-the-feature-is-enabled-by-default):

`rtsp://root:pass@<servername>:554/axis-media/media.amp?videocodec=h264&onvifreplayext=0`

### Retrieve default values

Check if the RTP header extension is enabled by default. If it is, the feature will be used even if the RTSP setup doesn't contain any extra parameters.

_Example_

[Check if the feature is enabled by default](#check-if-the-feature-is-enabled-by-default). On an open terminal, send the following `HTTP GET` request to `/axis-cgi/param.cgi`:

`curl --digest --user root:pass 'http://<servername>/axis-cgi/param.cgi?action=list&group=Network.RTP.OnvifReplayExt'`

If the feature is supported, the response will contain `Network.RTP.OnvifReplayExt=yes`.

### Enable Onvif Replay Extension

Enable or disable the RTP header extension by default.

_Example_

[Enable or disable the feature by default](#enable-or-disable-the-feature-by-default). On an open terminal, send the following `HTTP GET` request to `/axis-cgi/param.cgi`:

`curl --digest --user root:pass 'http://<servername>/axis-cgi/param.cgi?action=update&Network.RTP.OnvifReplayExt=yes'`

## API specifications
### Check if the feature is supported

Check if RTP with the OnvifReplayExt feature is supported.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.API.RTP.OnvifReplayExt"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.API.RTP.OnvifReplayExtHost: <servername>
```

| Parameter | Available values | Description |
| --- | --- | --- |
| `action=<string>` | `list` | The parameter action. |
| `group=<string>` | `Properties.API.RTP.OnvifReplayExt` | The parameter group name. |

#### Responses

```bash
200 OK
```

_Example value_

```bash
Properties.API.RTP.OnvifReplayExt=yes
```

#### Schema

_Feature is supported_

```bash
{    \[        Properties.API.RTP.OnvifReplayExt=yes    \]}
```

_Feature is not supported_

```bash
{    \[        # Error: Error -1 getting param in group 'Properties.API.RTP.OnvifReplayExt'    \]}
```

### Check if the feature is enabled by default

Check if RTP with the OnvifReplayExt feature is enabled by default.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Network.RTP.OnvifReplayExt"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Network.RTP.OnvifReplayExtHost: <servername>
```

| Parameter | Available values | Description |
| --- | --- | --- |
| `action=<string>` | `list` | The parameter action. |
| `group=<string>` | `Network.RTP.OnvifReplayExt` | The parameter group name. |

#### Responses

```bash
200 OK
```

_Example value_

```bash
Network.RTP.OnvifReplayExt=yes
```

#### Schema

_Feature is enabled_

```bash
{    \[        Network.RTP.OnvifReplayExt=yes    \]}
```

_Feature is disabled_

```bash
{    \[        Network.RTP.OnvifReplayExt=no    \]}
```

_Feature is not supported_

```bash
{    \[        # Error: Error -1 getting param in group 'Network.RTP.OnvifReplayExt'    \]}
```

### Enable or disable the feature by default

Enable RTP with the OnvifReplayExt feature by default.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Network.RTP.OnvifReplayExt=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&Network.RTP.OnvifReplayExt=yesHost: <servername>
```

| Parameter | Available values | Description |
| --- | --- | --- |
| `action=<string>` | `update` | The parameter action. |
| `Network.RTP.OnvifReplayExt=<string>` | `yes`, `no` | The new default value for `Network.RTP.OnvifReplayExt`. |

#### Responses

```bash
200 OK
```

_Example value_

```bash
OK
```

#### Schema

_Value is updated_

```bash
{    \[        OK    \]}
```

_Feature is not supported_

```bash
{    \[        # Error: Error setting 'root.Network.RTP.OnvifReplayExt' to 'yes'!    \]}
```