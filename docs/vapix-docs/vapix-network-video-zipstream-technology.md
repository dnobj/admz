---
title: Zipstream technology
url: "https://developer.axis.com/vapix/network-video/zipstream-technology/"
category: vapix
subcategory: network-video
sha256: 00f23f684e2478ab74535466d511a517576c1174ff00b75aa7d223bfc725ac41
scraped_at: "2026-01-09T15:21:33.417Z"
page_height: 40090
---

# Zipstream technology

## Introduction

Zipstream is a bit rate reduction technology optimized for video surveillance that reduces the average bit rate by removing unnecessary data and makes it possible to allow higher resolutions, reduce storage cost or to keep recordings for a longer time. To reduce the bit rate, Zipstream reduces the number of bits in the areas of the image that are less interesting from a video surveillance perspective, for example the background. Image details that are important for forensic video analysis, for example faces and license plates, are preserved with enough number of bits.

Axis Zipstream technology for H.264 conforms to the H.264 standard and is compatible with third-party clients and VMS solutions that decode H.264 video. To use the Zipstream dynamic GOP mode, some clients might need to adapt their H.264 playback implementation. The fixed GOP mode works with all implementations.

info

For more information about Zipstream, see the Zipstream technology white paper.

If the Axis product supports Axis Zipstream technology, some Zipstream elements are enabled by default and will automatically be used when a client requests an H.264 stream. Zipstream can be used together with variable bit rate control (VBR) or with maximum bit rate control (MBR).

Zipstream is affected by the compression parameter in the RTSP request `axis-media/media.amp?compression=30`. When Zipstream is enabled, this parameter controls the amount of compression applied to the important forensic details. That is, compression only affects the important forensic details. Compression is usually set to 30 and this value is recommended also for Zipstream streams.

Using VAPIX, the Zipstream settings can be controlled through:

-   Zipstream API – Retrieve and configure Zipstream settings such as the strength and GOP mode. These settings will be used for all streams unless overridden in an RTSP stream request. See [Zipstream API](#zipstream-api).
-   RTSP API – Specify Zipstream parameters when requesting a stream. The parameters are used only for the requested stream. See [Zipstream in RTSP requests](#zipstream-in-rtsp-requests).

### Identification

VAPIX® Zipstream API is available if:

-   **Property**: `root.Properties.ZipStream.ZipStream=yes`
-   **AXIS OS**: 5.80 and later
-   **Product category**: Network cameras using ARTPEC-5 and later

info

AXIS OS version 6.30 and later is required for FPS mode if root.Image.I#.MPEG.ZFpsMode exists.

### Zipstream strength

Zipstream strength is a measure of the amount of bit rate savings. Increasing the strength reduces the bit rate but will also affect image quality outside the area of interest and not affect the forensic details.

By default, Axis products with Zipstream technology are configured to use strength 10 and fixed GOP mode. This setting reduces the bit rate significantly without affecting the visual image quality and is compatible with third-party clients and VMS solutions.

Zipstream strength 30 or higher (30 for cameras with AXIS OS before AXIS OS version 6.30) with dynamic GOP is recommended for cameras that are connected to the cloud and for cameras that record to SD cards and need to limit the bit rate in order to keep recordings for a longer time. To further optimize the use of storage, this setting can be combined with motion-triggered recording and/or maximum bit rate control (MBR).

The following table lists supported Zipstream strengths:

| Zipstream strength | Description |
| --- | --- |
| `off` | Zipstream is disabled. |
| `10` `20` `30` `40` `50` | Valid Zipstream strengths. Default value: `10`Increasing the strength reduces the bit rate but will also affect the visual image quality. At the default value `10`, visual image quality is not affected, but as the strength increases, visual image quality is degraded in unprioritized image areas, for example the background. Image details important for forensic video analysis are kept. |
| `60` `70` `80` `90` `100` | Deprecated. |

### Zipstream GOP mode

Zipstream can be used in fixed or dynamic GOP (Group of Picture) mode. Dynamic GOP will reduce bit rate even more and is recommended if the Zipstream strength is 30 or above.

| GOP mode | Description |
| --- | --- |
| `fixed` | The GOP length is fixed and set to the Axis product’s default GOP length. |
| `dynamic` | When possible, unnecessary I-frames are removed in order to further reduce the bit rate. The GOP length varies between the Axis product’s default GOP length and a configurable, maximum GOP length. The maximum GOP length is used for scenes with no or almost no motion; the default GOP length is used for busy scenes.Dynamic GOP mode is recommended when the Zipstream strength is 30 or above. |

The default GOP length is defined by parameter `Image.I#.MPEG.PCount`. In RTSP requests, the default GOP length can be overridden by `videokeyframeinterval`.

info

Using dynamic GOP can result in long key frame intervals. Depending on the H.264 playback implementation, long key frame intervals could cause problems viewing recorded video in some clients and VMS solutions.

For more information, see the Axis Zipstream Technology white paper.

### Zipstream FPS mode

There are two frame rate (fps) modes available.

| Fps mode | Description |
| --- | --- |
| `fixed` | The fps will be the default one set for the stream (it may vary due to rate control limitation). |
| `dynamic` | The dynamic fps mode shall be triggered by the motion in the scene, if using Zipstream strength of 30 or above it is recommended to use dynamic fps mode.Dynamic fps is off when Zipstream strength is set to off. |

It is the user’s choice to activate/deactivate this feature independently from the other Zipstream parameters.

The fps is defined by parameter `Image.I#.MPEG.ZFpsMode`

info

Some VMS might adversely affect the user experience, for example fps may reduce and the user may think the stream has frozen.

For more information, see the Axis Zipstream Technology white paper.

### Zipstream minimum FPS mode

The minimum dynamic frame rate. This parameter is only relevant if Ziptream = `ON` and dynamic FPS = `dynamic`.

| Minimum FPS mode | Description |
| --- | --- |
| `0` | `0` means that the FPS is allowed to go as low as the dynamic frame rate can go. If a value is greater than `0` the dynamic frame rate is not allowed to go below the specified value. |

### Zipstream in RTSP requests

If the Axis product supports Zipstream technology for H.264, Zipstream is enabled by default and used in all RTSP streams. Zipstream settings, such as the strength and GOP mode, are defined by VAPIX® Zipstream API and will be used when a client requests an RTSP stream. Clients can override the Zipstream settings by including Zipstream URL parameters in the RTSP request.

RTSP video stream with Zipstream strength 20 and fixed GOP mode:

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&resolution=1920x1080&videozstrength=20&videozgopmode=fixed
```

RTSP video stream with Zipstream strength 30 and dynamic GOP mode:

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&videozstrength=30&videozgopmode=dynamic
```

RTSP video stream with dynamic Zipstream GOP mode and maximum GOP length 400:

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&videozgopmode=dynamic&videozmaxgoplength=400
```

RTSP video stream with dynamic Zipstream GOP mode, maximum GOP length 400 and minimum GOP length 32:

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&videozgopmode=dynamic&videozmaxgoplength=400&videokeyframeinterval=32
```

RTSP video stream without Zipstream (not recommended):

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&videozstrength=off
```

RTSP video stream with fps mode dynamic:

```bash
rtsp://<servername>/axis-media/media.amp?videozfpsmode=dynamic
```

RTSP video stream with videozminfps, set to 15 in this example (only when videozfpsmode is set to dynamic):

```bash
rtsp://<servername>/axis-media/media.amp?videozminfps=15
```

The RTSP API is described in [Video streaming over RTSP](/vapix/network-video/video-streaming/#video-streaming-over-rtsp). Available URL parameters are listed described in [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Set the Zipstream strength

Use this example to set the Zipstream strength to 30 for channel 1:

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setstrength.cgi?schemaversion=1&strength=30&camera=1"
```

```bash
GET /axis-cgi/zipstream/setstrength.cgi?schemaversion=1&strength=30&camera=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type:text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

### List the available Zipstream strengths

Use this example to list available Zipstream strengths. For a description of the valid values, see [Zipstream strength](#zipstream-strength).

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/liststrengths.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/zipstream/liststrengths.cgi?schemaversion=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>     <ListStrengthsSuccess>      <Strength>off</Strength>      <Strength>10</Strength>      <Strength>20</Strength>      <Strength>30</Strength>      <Strength>40</Strength>      <Strength>50</Strength>      ...    </ListStrengthsSuccess>  </Success></ZipStreamResponse>
```

### Get the current Zipstream settings

Use this example to retrieve the current Zipstream settings for all channels. All channels will be set to default if the camera parameter is omitted.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?schemaversion=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GetStatusSuccess>      <Status>        <Channel>1</Channel>        <Strength>10</Strength>        <GopMode>fixed</GopMode>        <MaxGopLength>300</MaxGopLength>        <FpsMode>fixed</FpsMode>        <MinFps>0</MinFps>      </Status>      <Status>        <Channel>2</Channel>        <Strength>30</Strength>        <GopMode>dynamic</GopMode>        <MaxGopLength>100</MaxGopLength>        <FpsMode>fixed</FpsMode>        <MinFps>0</MinFps>      </Status>      <Status>        <Channel>3</Channel>        <Strength>off</Strength>        <GopMode>fixed</GopMode>        <MaxGopLength>300</MaxGopLength>        <FpsMode>fixed</FpsMode>        <MinFps>0</MinFps>      </Status>      <Status>        <Channel>4</Channel>        <Strength>off</Strength>        <GopMode>fixed</GopMode>        <MaxGopLength>300</MaxGopLength>        <FpsMode>fixed</FpsMode>        <MinFps>0</MinFps>      </Status>    </GetStatusSuccess>  </Success></ZipStreamResponse>
```

### Get the current Zipstream strength

Use this example to receive the current Zipstream strength for channel 2.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=2"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=2Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GetStatusSuccess>      <Status>        <Channel>2</Channel>        <Strength>20</Strength>        <GopMode>dynamic</GopMode>        <MaxGopLength>60</MaxGopLength>        <FpsMode>fixed</FpsMode>        <MinFps>0</MinFps>      </Status>    </GetStatusSuccess>  </Success></ZipStreamResponse>
```

The Zipstream strength is returned in the `<Strength>` XML element.

### Set the GOP data

Use this example to set the Zipstream GOP mode to `dynamic` for all channels. All channels will be set to `default` if the camera parameter is omitted.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setgop.cgi?schemaversion=1&gopmode=dynamic"
```

```bash
GET /axis-cgi/zipstream/setgop.cgi?schemaversion=1&gopmode=dynamicHost: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

Then set the dynamic max GOP length to 300 for channel 1 using the following call:

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setgop.cgi?schemaversion=1&maxgoplength=300&camera=1"
```

```bash
GET /axis-cgi/zipstream/setgop.cgi?schemaversion=1&maxgoplength=300&camera=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

Finally, try setting an invalid max GOP length. For a full list of error codes, see [General error response](#general-error-response).

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setgop.cgi?schemaversion=1&maxgoplength=100000"
```

```bash
GET /axis-cgi/zipstream/setgop.cgi?schemaversion=1&maxgoplength=100000Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Error>    <GeneralError>      <ErrorCode>70</ErrorCode>      <Description>Invalid max GOP length</Description>    </GeneralError>  </Error></ZipStreamResponse>
```

### List the available GOP modes

Use this example to list the available GOP modes. Valid modes are either `fixed` or `dynamic`.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listgopmodes.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/zipstream/listgopmodes.cgi?schemaversion=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <ListGopModesSuccess>      <GopMode>fixed</GopMode>      <GopMode>dynamic</GopMode>    </ListGopModesSuccess>  </Success></ZipStreamResponse>
```

### Get the current GOP data

Use this example to retrieve the GOP data for channel 1.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1Host: <servername>
```

The GOP mode and max GOP length are returned in `<GopMode>` and `<MaxGopLength>` XML elements as seen in [Get the current Zipstream settings](#get-the-current-zipstream-settings) and [Get the current Zipstream strength](#get-the-current-zipstream-strength).

### Get supported and deprecated XML schema versions

Use this example to receive both supported and deprecated XML schema versions for the Zipstream technology API.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getschemaversions.cgi"
```

```bash
GET /axis-cgi/zipstream/getschemaversions.cgiHost: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GetSchemaVersionsSuccess>      <SchemaVersion>        <VersionNumber>1.0</VersionNumber>        <Deprecated>true</Deprecated>      </SchemaVersion>      <SchemaVersion>        <VersionNumber>1.1</VersionNumber>        <Deprecated>true</Deprecated>      </SchemaVersion>      <SchemaVersion>        <VersionNumber>2.0</VersionNumber>        <Deprecated>false</Deprecated>      </SchemaVersion>    </GetSchemaVersionsSuccess>  </Success></ZipStreamResponse>
```

info

In this example version 2.0 is listed as supported while versions 1.0 and 1.1 are deprecated.

### Set the Zipstream FPS mode

Use this example to set the FPS mode to `dynamic` for all channels. All channels will be set to `default` if the camera parameter is omitted.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setfpsmode.cgi?schemaversion=1&fpsmode=dynamic"
```

```bash
GET /axis-cgi/zipstream/setfpsmode.cgi?schemaversion=1&fpsmode=dynamicHost: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

### List the available FPS modes

Use this example to list the available FPS modes, which can be either `fixed` or `dynamic`.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listfpsmodes.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/zipstream/listfpsmodes.cgi?schemaversion=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <ListFpsModesSuccess>      <FpsMode>fixed</FpsMode>      <FpsMode>dynamic</FpsMode>    </ListFpsModesSuccess>  </Success></ZipStreamResponse>
```

### Set the minimum FPS

Use this example to set the minimum FPS to 5 for all channels. All channels will be set to `default` if the camera parameter is omitted.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setminfps.cgi?schemaversion=1&minfps=5"
```

```bash
GET /axis-cgi/zipstream/setminfps.cgi?schemaversion=1&minfps=5Host: <servername>
```

Response

```bash
HTTP/1.0 200 OK<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

### Get the current FPS data

Use this example to receive the current FPS data for channel 1.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1Host: <servername>
```

The FPS mode and minimum FPS are returned in `<FpsMode>` and `<MinFps>` XML elements (see [Get the current Zipstream settings](#get-the-current-zipstream-settings) and [Get the current Zipstream strength](#get-the-current-zipstream-strength).

### Set the Zipstream profile

Use this example to set the Zipstream profile to `classic` for all available channels. Please note that all channels will be set to default if this parameter is omitted.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setprofile.cgi?schemaversion=1&profile=classic&profilelevel=0"
```

```bash
GET /axis-cgi/zipstream/setprofile.cgi?schemaversion=1&profile=classic&profilelevel=0Host: <servername>
```

Response

```bash
HTTP/1.0 200 OK<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.3" xmlns="http://www.axis.com/vapix/http\_cgi/zipstream1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1 http://www.axis.com/vapix/http\_cgi/zipstream1/zipstream1.xsd">  <Success>    <GeneralSuccess/>  </Success></ZipStreamResponse>
```

### List available Zipstream profiles

Use this example to list all available Zipstream profiles.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listprofiles.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/zipstream/listprofiles.cgi?schemaversion=1Host: <servername>
```

Response

```bash
HTTP/1.0 200 OK<?xml version="1.0" encoding="utf-8"?><ZipStreamResponse SchemaVersion="1.3" xmlns="http://www.axis.com/vapix/http\_cgi/zipstream1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1 http://www.axis.com/vapix/http\_cgi/zipstream1/zipstream1.xsd">  <Success>    <ListProfilesSuccess>      <Profile>        <Name>classic</Name>        <MaxLevel>1</MaxLevel>      </Profile>      <Profile>        <Name>storage</Name>        <MaxLevel>2</MaxLevel>      </Profile>      <Profile>        <Name>networkloadbalancing</Name>        <MaxLevel>1</MaxLevel>      </Profile>    </ListProfileSuccess>  </Success></ZipStreamResponse>
```

### Retrieve the current Zipstream profiles

Use this example to retrieve the current Zipstream profile for channel 1.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?schemaversion=1&camera=1Host: <servername>
```

Both the profile and profile level are returned as `<Profile>` and `<ProfileLevel>` XML elements as seen in the examples [Get the current Zipstream settings](#get-the-current-zipstream-settings) and [Get the current Zipstream strength](#get-the-current-zipstream-strength).

## Zipstream API
### Description

VAPIX® Zipstream API is used to configure Zipstream technology. Using the API, the Axis products Zipstream settings such as the strength and GOP mode can be configured. The Zipstream settings are used for all RTSP streams but are overridden if Zipstream URL parameters are included in the RTSP request.

Supported functionality:

-   List the current Zipstream settings.
-   Set the Zipstream strength.
-   Set the Zipstream GOP mode.
-   Set the maximum Zipstream GOP length.
-   Set the Zipstream FPS mode (from AXIS OS 6.30 and later).

Zipstream is enabled by default but can be disabled by setting the strength to `off`.

### Get schema versions

Use `/axis-cgi/zipstream/getschemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getschemaversions.cgi"
```

```bash
GET /axis-cgi/zipstream/getschemaversions.cgiHost: <servername>
```

**Return value - Success**

A successful request returns the supported schema versions.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GetSchemaVersionsSuccess>            <SchemaVersion>                <VersionNumber>\[major.minor\]</VersionNumber>                <Deprecated>\[true/false\]</Deprecated>            </SchemaVersion>        </GetSchemaVersionsSuccess>    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetSchemaVersionsSuccess` | Successful request |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

### Set Zipstream strength

Use `/axis-cgi/zipstream/setstrength.cgi` to set the Zipstream strength. The strength can be set on all video channels or on an individual channel. The new strength will be used for new streams, ongoing streams will not be affected.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setstrength.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/setstrength.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `camera=<string>` | `1, ...` | The video channel. If omitted, the Zipstream strength is set on all channels. |
| `strength=<string>` | See [Zipstream strength](#zipstream-strength) | Required. The Zipstream strength to set. |

**Return value - Success**

If the request is successful, the strength is set and a `GeneralSuccess` is returned. See [General success response](#general-success-response).

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40, 50

### Set Zipstream GOP settings

Use `/axis-cgi/zipstream/setgop.cgi` to set the GOP mode and the maximum GOP length. The GOP settings can be set on all video channels or on an individual video channel. The new settings will be used for new streams, ongoing streams will not be affected.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setgop.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/setgop.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `camera=<string>` | `1, ...` | The video channel. If omitted, the Zipstream GOP settings are set on all channels. |
| `gopmode=<string>` | `dynamic` `fixed` | The Zipstream GOP mode to set. If omitted, the current value will be used. |
| `maxgoplength=<integer>` | `1 ... 1023` | The Zipstream maximum GOP length. If omitted, the current value will be used. |

**Return value - Success**

If the request is successful, the strength is set and a `GeneralSuccess` is returned. See [General success response](#general-success-response).

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40, 60, 70

### Get Zipstream status

Use `/axis-cgi/zipstream/getstatus.cgi` to retrieve the current Zipstream settings.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/getstatus.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/zipstream/getstatus.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `camera=<string>` | `1, ...` | The video channel. If omitted, the request returns Zipstream settings for all channels. |

**Return value - Success**

A successful request returns the current Zipstream settings.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GetStatusSuccess>            <Status>                <Channel>\[channel\]</Channel>                <Strength>\[strength\]</Strength>                <GopMode>\[fixed/dynamic\]</GopMode>                <MaxGopLength>\[maximum GOP length\]</MaxGopLength>            </Status>            ...        </GetStatusSuccess>    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetStatusSuccess` | Successful request. |
| `Status` | Contains status information for one video channel. |
| `Channel` | The video channel. |
| `Strength` | Zipstream strength. See [Zipstream strength](#zipstream-strength). |
| `GopMode` | Zipstream GOP mode. See [Zipstream GOP mode](#zipstream-gop-mode). |
| `MaxGopLength` | Maximum GOP length for Zipstream. |

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

### List Zipstream strengths

Use `/axis-cgi/zipstream/liststrengths.cgi` to retrieve the available Zipstream strengths.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/liststrengths.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/liststrengths.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Return value - Success**

A successful request returns available Zipstream strengths.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <ListStrengthsSuccess>            <Strength>\[value\]</Strength>            <Strength>\[value\]</Strength>            ...        </ListStrengthsSuccess>    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `ListStrengthsSuccess` | Successful request. |
| `Strength` | Contains one available strength value. For available values, see [Zipstream strength](#zipstream-strength). |

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 40

### List Zipstream GOP modes

Use `/axis-cgi/zipstream/listgopmodes.cgi` to list the available Zipstream GOP modes. See [Zipstream GOP mode](#zipstream-gop-mode).

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listgopmodes.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/listgopmodes.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Return value - Success**

A successful request returns available Zipstream GOP modes.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <ListGopModesSuccess>            <GopMode>\[mode\]</GopMode>            <GopMode>\[mode\]</GopMode>            ...        </ListGopModesSuccess>    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `ListGopModesSuccess` | Successful request. |
| `GopMode` | Contains one available GOP mode. For modes, see [Zipstream GOP mode](#zipstream-gop-mode). |

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 40

### Set Zipstream FPS modes

Use `/axis-cgi/zipstream/setfpsmode.cgi` to set the Zipstream FPS mode.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setfpsmode.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/setfpsmode.cgi?<argument>=<value>Host: <servername>
```

Supported arguments and values:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | `1 ...` | The major version of the XML Schema that the response is structured according to. The latest supported minor version is always used. |
| `camera=<string>` | `Channel name` |  |
| `fpsmode=<string>` | `fixed, dynamic` | The FPS mode. |

**Return value - Success**

A successful request sets the Zipstream FPS modes.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GeneralSuccess />    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |

**Return value - Error**

If an error occurred, a `GeneralError` response is returned.

### List Zipstream FPS modes

Use `/axis-cgi/zipstream/listfpsmodes.cgi` to list the available Zipstream FPS modes.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listfpsmodes.cgi"
```

```bash
GET /axis-cgi/zipstream/listfpsmodes.cgiHost: <servername>
```

**Return value - Success**

A successful request returns available Zipstream FPS modes.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <ListFpsModesSuccess>            <FpsMode>\[mode\]</FpsMode>            <FpsMode>\[mode\]</FpsMode>            ...        </ListFpsModesSuccess>    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `ListFpsModesSuccess` | Successful request. |
| `FpsMode` | Fps mode. For modes, see [Zipstream FPS mode](#zipstream-fps-mode). |

**Return value - Error**

If an error occurred, a `GeneralError` response is returned.

### Set minimum FPS

Use `/axis-cgi/zipstream/setminfps.cgi` to set the minimum FPS mode for the Zipstream.

**Request**

-   **Security level**: Administrator, Operator

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setminfps.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/setminfps.cgi?<argument>=<value>Host: <servername>
```

Supported elements attributes and values:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion<integer>` | `Integer` | Required. The major version of the XML Schema to use for the response. See [XML schemas.](/vapix/network-video/#xml-schemas). |
| `camera<string>` | `1, ...` | The video channel. If omitted, the request returns Zipstream settings for all channels. |
| `minfps<string>` | `0, ...` | The minimum FPS mode. Only relevant if FPS mode is set to `dynamic`. |

**Return value - Success**

If the request is successful, a `GeneralSuccess` is returned. See [General success response](#general-success-response).

**Return value - Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 40

### `/axis-cgi/zipstream/setprofile.cgi`

Use `/axis-cgi/zipstream/setprofile.cgi` to set the profile to `classic` on all available Zipstream channels.

**Request**

-   **Security level**: Operator

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/setprofile.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/setprofile.cgi?<argument>=<value>Host: <servername>
```

Supported elements attributes and values:

| Argument | Valid values | Default value | Description |
| --- | --- | --- | --- |
| `schemaversion=<integer>` | Integer | Must be specified | The major version of the XML Schema that the response is structured according to. The latest supported minor version is always used. |
| `camera=<string>` | `1...` `Channel name` |  | The video channel. The GOP values are set for all channels if this argument is omitted. |
| `profile=<string>` | `classic` `storage` `networkloadbalancing` | `classic` | The profile that should be used.  
  
\- `classic`: All controls are manually set.  
\- `storage` Some settings will automatically be optimized for storage use cases to minimize the bitrate while quality is maintained. B-frames can be used on platforms that support it.  
\- `networkloadbalancing`: Some settings will automatically be optimized for loaded network use cases to avoid network spikes. I-frames will be smaller and can be replaced by gradual decode refresh P-frames. |
| `gradualdecoderefresh` | `auto` `low` `balanced` | `auto` | When the Zipstream profile `networkloadbalancing` is in use, the optional parameter `gradualdecoderefresh` can have one of the following values:  
  
\- `auto`: The video framework handles this parameter internally. This is the default value if nothing else is specified.  
\- `off` No gradual decode refresh is used.  
\- `balanced` Gradual decode refresh is used for most refresh cycles, but some I-frames will still be used. |
| `level=<integer>` | `0...` | `0` | The level of features. The `0` will be replaced with the highest available level. Please note that you should only include features included at a particular level, or the levels below it. The maximum level applicable for a specific profile can be obtained from the [`/axis-cgi/zipstream/listprofiles.cgi`](#axis-cgizipstreamlistprofilescgi) response. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GeneralSuccess />    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Success. |

### `/axis-cgi/zipstream/listprofiles.cgi`

Use `/axis-cgi/zipstream/listprofiles.cgi` to list all available Zipstream profiles.

**Request**

-   **Security level**: Operator

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/zipstream/listprofiles.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/zipstream/listprofiles.cgi?<argument>=<value>Host: <servername>
```

Supported elements attributes and values:

| Parameter | Valid values | Default value | Description |
| --- | --- | --- | --- |
| `schemaversion=<integer>` | Integer | Must be specified | The major version of the XML Schema that the response is structured according to. The latest supported minor version is always used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GeneralSuccess />    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Success. |

### General success response

General success response in Zipstream API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Success>        <GeneralSuccess />    </Success></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Success. |

### General error response

General error response in Zipstream API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ZipStreamResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/zipstream1.xsd">    <Error>        <GeneralError>            <ErrorCode>\[error code\]</ErrorCode>            <Description>\[description\]</Description>        </GeneralError>    </Error></ZipStreamResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ZipStreamResponse` | Contains the response to the CGI request. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `Description` | Description of the error. |

| Error code | Description | CGI request |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid channel. | `/axis-cgi/zipstream/setgop.cgi`, `/axis-cgi/zipstream/getstatus.cgi`, `/axis-cgi/zipstream/setstrength.cgi` |
| `40` | Specified version is not supported. | All |
| `50` | Invalid Zipstream strength | `/axis-cgi/zipstream/setstrength.cgi` |
| `60` | Invalid GOP mode. | `/axis-cgi/zipstream/setgop.cgi` |
| `70` | Invalid maximum GOP length. | `/axis-cgi/zipstream/setgop.cgi` |
| `80` | Invalid FPS mode. | `/axis-cgi/zipstream/setfpsmode.cgi` |
| `90` | Invalid minimum FPS. | `setminfps` |