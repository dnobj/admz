---
title: Rate control
url: "https://developer.axis.com/vapix/network-video/rate-control/"
category: vapix
subcategory: network-video
sha256: 8f85e38a8c587401fd0a51f06db55b4a89b25bc3fd63bc3a204334bed378cfe6
scraped_at: "2026-01-09T15:20:49.714Z"
page_height: 12220
---

# Rate control

## Description

The Rate control API can be used to control the bitrate of one or several video streams on an Axis camera.

### Terminology

| Term | Description |
| --- | --- |
| `ABR` | Average bitrate. |
| `ADA` | AXIS Device Assistant is a web-browser based (web app) GUI for managing the Axis device. This web app is most often hosted on the Axis device itself. |
| `ADM` | AXIS Device Manager, an installation and maintenance tool for Axis devices. |
| `CBR` | Constant bitrate. |
| `MBR` | Maximum bitrate. |
| `VBR` | Variable bitrate. |

### Model

The API is built on the CGI `/axis-cgi/param.cgi`, which lets you query and set the default stream parameters, as well as the URL options for RTSP URLs. If you specify any rate control option in the URL, you must specify `videobitratemode` in the URL as well.

The API supports the following rate control modes:

-   Variable Bitrate (VBR)
-   Maximum Bitrate (MBR)
-   Average Bitrate (ABR)

Please note that any URL options not passed in a request will receive a default value from a `/axis-cgi/param.cgi` parameter, the resulting settings will then be used when starting the stream. The settings not applicable for the specified mode are ignored.

### Identification

The API is identified through `/axis-cgi/param.cgi` and the following properties:

-   **Property**: `Image.IO.RateControl.Mode`
-   **Property**: `Image.IO.RateControl.MaxBitrate`

The presence of the MBR mode in `Image.IO.RateControl.Mode` and the `videobitratemode` URL is identified by `Properties.Image.RateControl.Version` when it is set to 1.1 or higher.

The presence of the ABR (Average bitrate) is identified through the following property:

-   **Property**: `Properties.Image.RateControl.ABR.ABR=yes`

Please note that if `Properties.Image.RateControl.Version=2.0` or higher neither `videobitrate` nor `Image.I#.RateControl.TargetBitrate` are supported.

### Obsoletes

The CBR mode (Constant bitrate) has been deprecated and is no longer supported.

`Image.I#.RateControl.TargetBitrate` and `videobitrate` are no longer supported as of API version 2.0.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Maximum bitrate

The purpose of maximum bitrate is to limit the immediate network bitrate, as it is not built to regulate the expected storage of a stream. This means that if the desired maximum bitrate is set at an unrealistically low level there might be an impact on the video quality in motion heavy scenes, where high quality is important. It is therefore recommended to use variable- or average bitrate instead.

### Average bitrate

The purpose of average bitrate is to provide the best quality on the stream based on available storage.

**Establishment**

The average bitrate algorithm takes about 24 hours to gather data and provide the best quality level, with the bitrate adjusting according to the most recent data. Depending on the monitored scene, the establishing time may vary.

The available storage is defined by the target bitrate that measures the running time of the stream, thus the aim of the average bitrate is to not exceed the target bitrate, as this would surpass the available storage. During the initial 5 minutes of a stream, the average bitrate/second may exceed the requested target bitrate.

**Margin**

The average bitrate algorithm accumulates a margin between 10–30% of the available storage space and uses it during periods when the bitrate is temporarily higher. This means that not all of the storage space available will be used. How much of the margin it uses depends on the scene and when the bitrate gets more unpredictable, in which case a higher margin is used.

**Bitrate histories**

The camera stores the bitrate history of a stream internally. In the case when a stream is restarted, for example when the network goes down, this history is restored when an identical stream is started. The camera has allocated space for up to 10 such stories, meaning that the oldest one will be deleted when the memory gets full.

**History lost due to power outage**

The camera has two ways of storing bitrate histories: temporarily in the RAM and permanently on the flash memory. For continuously running streams, the bitrate history gets stored on the flash memory once every 24 hours. If a stream is closed, the bitrate history will be stored on the flash memory, but only as long as the stream has been active for more than 8 hours, otherwise it will be stored on the RAM. When the camera is rebooted in a proper way, histories will be stored on the flash memory.

The reason why there is an 8 hour minimum time limit when writing to flash is to avoid unnecessary wear on the flash memory. This does mean that in the case of a power outage, bitrate history could be lost.

**Incompatible recordings**

This feature is currently not compatible with event-triggered recordings, nor with continuous recordings that aren’t active 24/7. If `ABR` is used in conjunction with these recordings, the image quality will suffer a downgrade and all of the available storage might not be used.

**Limitations**

If an unreasonable low target bitrate is provided, quality may be impacted and in some cases the average bitrate/second and thus the used storage may exceed the available storage.

### Variable bitrate

The purpose of variable bitrate is to guarantee that the selected compression will be used. Also, both instantaneous bitrate and storage might be unpredictable, as variable bitrate may be as large as the hardware limit. Depending on the resolution and frame rate it will be limited to what the level of that resolution and frame rate supports, however it should be at least 50 Mbits/s.

## Common examples
### Set rate control parameters

Use this example to set the rate control parameters on the stream RTSP URL to ensure that the bitrate of the stream is able to handle the network bandwidth limitations. This should be done to support a number of cameras on the network and make sure that it is not overloaded.

#### Set the rate control parameters in the RTSP URL

1.  Start playback with the MBR set to 1000 kbit/s and the priority set to quality:

```bash
rtsp://<servername>/axis-media/media.amp?videobitratemode=mbr&videomaxbitrate=1000&videobitratepriority=quality
```

2.  When any rate control option is specified in the URL, a `400 Bad Request` will be returned if `videobitratemode` is not specified in the URL. Examples of error requests:

```bash
rtsp://<servername>/axis-media/media.amp?videomaxbitrate=1000rtsp://<servername>/axis-media/media.amp?videoabrtargetbitrate=1000
```

### Set default Rate Control parameters via `/axis-cgi/param.cgi`

Use this example to set the default rate control settings for an image view of the camera. If you are using just a few cameras, this can be set via the web interface (AXIS Camera Assistant), however, if you are using several cameras, use the Axis Device Manager.

#### Getting and setting the default rate control parameters for image view

1.  Get the current default rate control parameters for image view 0:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Image.I0.RateControl"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Image.I0.RateControlHost: <servername>
```

2.  Set rate control parameters for image view 0 with MBR set to 1000 kbit/s and the priority set to quality:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/admin/param.cgi?action=update&root.Image.I0.RateControl.Mode=mbr&root.Image.I0.RateControl.MaxBitrate=1000&root.Image.I0.RateControl.Priority=quality"
```

```bash
GET /axis-cgi/admin/param.cgi?action=update&root.Image.I0.RateControl.Mode=mbr&root.Image.I0.RateControl.MaxBitrate=1000&root.Image.I0.RateControl.Priority=qualityHost: <servername>
```

### Set average bitrate parameters

Use this example to set the rate control parameters on the RTSP URL stream. This is done to ensure that the stream and network bandwidth doesn't exceed the limitations of the storage space that has been accumulated for a specific retention time.

#### Setting ABR parameters on the RTSP URL

Start a playback where ABR is set to 500 kbit/s for a 30 day period and the max bitrate is 1000 kbit/s:

```bash
rtsp://<servername>/axis-media/media.amp?videobitratemode=abr&videoabrtargetbitrate=500&videoabrretentiontime=30&videoabrmaxbitrate=1000
```

### Set the average bitrate parameters in `/axis-cgi/param.cgi`

Use this example to choose a default ABR setting for the image view of a camera. If you are using just a few cameras, this can be set via the web interface (AXIS Camera Assistant), however, if you are using several cameras, use the Axis Device Manager.

#### Setting the default ABR parameters for image view

Set the rate control parameters for image view 0 with an average bitrate set to 500 kbit/s over a 30 day period and an instant limit at 1000 kbit/s:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/admin/param.cgi?action=update&root.Image.I0.RateControl.Mode=abr&root.Image.I0.RateControl.ABR.TargetBitrate=500&root.Image.I0.RateControl.ABR.MaxBitrate=1000&root.Image.I0.RateControl.ABR.RetentionTime=30"
```

```bash
GET /axis-cgi/admin/param.cgi?action=update&root.Image.I0.RateControl.Mode=abr&root.Image.I0.RateControl.ABR.TargetBitrate=500&root.Image.I0.RateControl.ABR.MaxBitrate=1000&root.Image.I0.RateControl.ABR.RetentionTime=30Host: <servername>
```

### Receive ABR stream status as events

Use this example to add an alarm for whenever an ABR stream has an abnormal status.

A stateful event is declared and sent per image source and contains information about a stream by using ABR, which is set in an error state. If at least one ABR stream is in an error state on an image source, `abr_error` will be set to 1. In those cases, the other properties of the event will contain the information about the stream in the worst state. Some of these properties will identify the parameters, such as resolution or state of the stream. The states are, in order of severity:

-   `low_bitrate`: When set to 1, the stream’s average bitrate is significantly lower than the average bitrate. The storage, defined by the target ABR multiplied by the retention time will not be filled up, however either the target average bitrate or some of the parameters can be adjusted to allow the available storage to be filled up.
-   `low_quality`: When set to 1, the quality of the stream has been significantly lowered to keep the average bitrate below the target ABR.
-   `very_low_quality`: When set to 1, the quality of the stream has been lowered even more to keep the average bitrate below the target ABR. Used in tandem with `low_quality` when both are set to 1.
-   `high_bitrate`: When set to 1, the stream’s average bitrate is higher than the target ABR, which means that more storage than originally defined by the target ABR multiplied by the retention time will be used, alternatively the retention time will be reduced, depending on how the video is stored. Implies that both `low_quality` and `very_low_quality` are set to 1.

Several different properties can help you identifying the stream, including:

-   `scale_width` and `scale_height`: The resolution of the stream.
-   `dynamic_gop`: 1 if dynamic GOP is turned on.
-   `dynamic_fps`: 1 if dynamic GOP is turned on.
-   `fps`: The fps (frames per second) of the stream.
-   `default_gop_length`: The GOP length of the stream.
-   `frame_skip_mode`: 1 with empty frames, 0 with dropped frames.
-   `zipstream_mode`: The zipstream strength. 0 if turned off.
-   `max_gop_length`: The maximum GOP length when dynamic GOP is turned on.
-   `stream_profile`: The combination of codec and profile: `h264_baseline`, `h264_main`, `h264_high` and `h265_main`.
-   `dynamic_fps_min_num`: The minimum FPS when dynamic FPS is turned on.

Status event definition example for an ABR stream

```bash
<wstop:TopicSet>    <tns1:VideoSource aev:NiceName="Video source">        <tnsaxis:ABR wstop:topic="true" aev:NiceName="Average bitrate degradation">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance                        aev:NiceName="Video source configuration token"                        Type="xsd:int"                        Name="VideoSourceConfigurationToken">                        <aev:Value>1</aev:Value>                        <aev:Value>2</aev:Value>                        <aev:Value>3</aev:Value>                        <aev:Value>4</aev:Value>                        <aev:Value>5</aev:Value>                        <aev:Value>6</aev:Value>                        <aev:Value>7</aev:Value>                        <aev:Value>8</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance                        isPropertyState="true"                        aev:NiceName="abr error"                        Type="xsd:boolean"                        Name="abr error" />                </aev:DataInstance>            </aev:MessageInstance>        </tnsaxis:ABR>    </tns1:VideoSource></wstop:TopicSet>
```

Please note that the possible values of `VideoSourceConfigurationToken` will vary between products due to the different number of image sources.

## API specification
### `/axis-cgi/param.cgi`

Parameters set with `/axis-cgi/param.cgi` enable default parameters to be set for each image view. # is 0–N, where N is `Properties.Image.NbrOfViews`.

Parameters in Image.I#.RateControl

| Parameter | Default values | Valid values | Applicable modes | Description |
| --- | --- | --- | --- | --- |
| `Mode` | `vbr` | `vbr`  
`mbr`  
`abr` |  | Specifies whether the rate controller should operate in VBR, MBR or ABR. `MaxBitrate` and `Priority` are ignored if the ABR mode is used and `ABR.TargetBitrate` and `ABR.MaxBitrate` will be used instead. There are currently no bitrate priority settings for ABR. |
| `Priority` | `framerate` | `none`  
`quality`  
`framerate`  
`fullframerate` | `MBR` | This method is used to prioritize either frame rate or quality. Not selecting a priority means that the frame rate and image quality will still both be affected.  
\- **framerate**: Prioritizing frame rate will not prevent the controller to skip frames, however, it will make it less likely to do so.  
\- **quality**: Prioritizing quality will not prevent the picture quality from being impacted, however, it will make it less likely to do so.  
\- **none**: Used if `Mode` is either `ABR` or `VBR`  
\- **fullframerate**: Tries to prevent frame drops in the rate controller, but cannot guarantee that other camera functions can cause frame drops. |
| `MaxBitrate` | 0 | 0...50000+ | `MBR` | The maximum bitrate allowed for the stream, measured in kbit/s. If the value is 0, at least 50000 will be used depending of product, resolution or frame rate. |
| `ABR.TargetBitrate` | 0 | 0...50000+ | `ABR` | The maximum average bitrate allowed for the stream, measured in kbit/s over the specified number of days (`ABR.RetentionTime`). It will be less than/equal to this value and If the value is 0, at least 50000 will be used depending of product, resolution or frame rate. Note> Please note that not all values are realistic and might not give you the desired result. |
| `ABR.MaxBitrate` | 0 | 0...50000+ | `ABR` | The maximum instantaneous bitrate allowed for the stream, measured in kbit/s. If the value is 0, at least 50000 will be used depending of product, resolution or frame rate. |
| `ABR.RetentionTime` | 7 | 1...3652 | `ABR` | The desired retention, measured in days. |

### RTSP URL parameters

For the RTSP URL, default values from `/axis-cgi/param.cgi` can be overridden.

RTSP URL parameters

| Parameter | Valid values | Applicable modes | Description |
| --- | --- | --- | --- |
| `videobitratemode` | `vbr`  
`mbr`  
`abr` | N/A | This value overrides `Image.I#.RateControl.Mode`. You must specify this parameter if any rate control option is specified in the URL. The settings not applicable for the specified mode are ignored. |
| `videobitratepriority` | `none`  
`quality`  
`framerate`  
`fullframerate` | `MBR` | This value overrides `Image.I#.RateControl.Priority`. |
| `videomaxbitrate` | 0...50000+ | `MBR` | This value overrides `Image.I#.RateControl.MaxBitrate` and is applied in MBR mode, specified by `videobitratemode`. |
| `videoabrtargetbitrate` | 0...50000+ | `ABR` | This value overrides `Image.I#.RateControl.ABR.TargetBitrate`. |
| `videoabrmaxbitrate` | 0...50000+ | `ABR` | This value overrides `Image.I#.RateControl.ABR.MaxBitrate`. Note> If both `videoabrmaxbitrate` and `videoabrtargetbitrate` are specified in the URL, `videoabrmaxbitrate` must not be smaller than `videoabrtargetbitrate`. |
| `videoabrretentiontime` | 1...3652 | `ABR` | This value overrides `Image.I#.RateControl.ABR.RetentionTime`. |