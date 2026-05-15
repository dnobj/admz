---
title: Trigger data
url: "https://developer.axis.com/vapix/network-video/trigger-data/"
category: vapix
subcategory: network-video
sha256: efc5421998f7124cd8863992c52f1aae7e713710ccd705af855a81c932827145
scraped_at: "2026-01-09T15:21:22.194Z"
page_height: 14505
---

# Trigger data

## Description

info

Deprecated. Trigger data functionality, that is, trigger data in H.264, MPEG-4 and MJPEG headers, is deprecated and will eventually be removed. Trigger data is replaced by event data streaming, see section [Event data streaming](/vapix/network-video/event-data-streaming/).

The JPEG header, the MPEG-4 GOV header and the H.264 SEI message contain Axis specific comment fields. One of the fields in the image header can be enabled to contain trigger data. The trigger data field describes different conditions in the Axis product. Triggers can be enabled according to requirement, for example:

-   Digital input states
-   Motion detection states and levels
-   Video loss status
-   Audio trigger state
-   Camera tampering state

User defined triggers can also be used which means that the triggers of interest are specified. For example specific motion detection windows, triggers connected to another video source in a video encoder etc.

When enabled to include triggers, all these states will be included in the JPEG header, GOV header or H.264 SEI message. This allows the receiving application to lose trigger data blocks without necessarily losing a changed state since the current state is included.

info

In this document, MPEG-4 is short for MPEG-4 Part 2.

## Prerequisites
### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 5.00 and later.

### Dependencies

The parameters (see [Parameters](#parameters)) are managed through the Parameter Management CGI `/axis-cgi/param.cgi`.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

This examples describes the trigger data block in a network camera. The trigger data block shows that audio, digital input 0 and 3 are not triggered. Digital input 1 and 2 are triggered as well as camera tampering on video source 0. Motion is detected for window 0 and the motion level for window 0 is 35. Video source 0 has video.

```bash
A0:0;IO0:0;IO1:1;IO2:1;IO3:0;V0:1;M0:1;ML0:035;T0:1
```

In this example, we will consider a network camera with two motion detection windows.

Enable user data and include trigger data:

**Request:**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.MPEG.UserDataEnabled=yes&Image.TriggerDataEnabled=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.MPEG.UserDataEnabled=yes&Image.TriggerDataEnabled=yesHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Body:

```bash
OK
```

Restart the network camera for these settings to take effect.

A listing of the default configuration would look like this:

```bash
root.Image.I0.TriggerData.IOEnabled=yesroot.Image.I0.TriggerData.AudioEnabled=yesroot.Image.I0.TriggerData.TamperingEnabled=yesroot.Image.I0.TriggerData.MotionDetectionEnabled=yesroot.Image.I0.TriggerData.MotionLevelEnabled=noroot.Image.I0.TriggerData.UserTriggers=
```

This would result in a trigger data block similar to this:

```bash
A0:0;IO0:0;M0:0;M1:0;T0:0;
```

Continuation of example 2: In this example the `UserTriggers` parameter is used to specify a trigger. The parameter `MotionDetectionEnabled` is set to `no` and the trigger `M0` is set as values for the `UserTriggers` parameter. If the `MotionDetectionEnabled` parameter would have been set to `yes`, both motion detection windows for `Image.I0` (`M0` and `M1`) would have been used. All other triggers from example 2 are included in the trigger request in the example below.

**Request:**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.TriggerData.IOEnabled=yes&Image.I0.TriggerData.AudioEnabled=yes&Image.I0.TriggerData.MotionDetectionEnabled=no&Image.I0.TriggerData.MotionLevelEnabled=yes&&Image.I0.TriggerData.TamperingEnabled=yes&Image.I0.TriggerData.UserTriggers=M0"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.TriggerData.IOEnabled=yes&Image.I0.TriggerData.AudioEnabled=yes&Image.I0.TriggerData.MotionDetectionEnabled=no&Image.I0.TriggerData.MotionLevelEnabled=yes&&Image.I0.TriggerData.TamperingEnabled=yes&Image.I0.TriggerData.UserTriggers=M0Host: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Body:

```bash
OK
```

This will result in a trigger data block in the header. No triggers have been activated in this example.

```bash
A0:0;IO0:0;IO1:0;M0:0;ML0:000;T0:0
```

## Parameters
### Enable trigger data

info

Deprecated. Trigger data functionality, that is, trigger data in H.264, MPEG-4 and MJPEG headers, is deprecated and will eventually be removed. Trigger data is replaced by event data streaming, see section [Event data streaming](/vapix/network-video/event-data-streaming/).

The Axis product must be restarted for this parameter to take effect.

Image

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `TriggerDataEnabled` | `no` | `yes` `no` | admin: read, write operator: read, write | Include trigger data in the video stream. |

### Enable user data in H.264/MPEG-4

The Axis product must be restarted for these parameters to take effect.

Image.I#.MPEG

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `UserDataEnabled`  
_(Needs to be enabled to get trigger data in the H.264/MPEG-4 stream.)_ | `no` | `yes` `no` | admin: read, write operator: read, write | Enable/disable inclusion of user data in the H.264 SEI message and the MPEG-4 GOV header. |
| `ConfigHeaderInterval` | `5` | An integer | admin: read, write operator: read, write | The interval at which configuration headers are inserted into the H.264 or MPEG-4 stream before a SEI or GOV. A configuration header is always inserted at the start of the stream. `n` = Headers inserted before every nth SEI/GOV. `0` = No extra headers inserted. |
| `UserDataInterval` | `1` | An integer | admin: read, write operator: read, write | This parameter controls how often user data should be sent on a 'per frame' basis and not on a 'per I-frame' basis as for the `ConfigHeaderInterval` parameter. |

info

The # in Image.I#.MPEG is replaced by an integer starting from zero, e.g. Image.I0.MPEG.

### Trigger data parameters

For each image configuration `Image.I#`, the `TriggerData` parameters specify the triggers included in the trigger data. The `UserTriggers` parameter can be used to include only a few triggers or triggers from other image configurations.

Image.I#.TriggerData

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `AudioEnabled` | `yes` | `yes` `no` | admin: read, write operator: read, write | Include audio trigger states. `yes` = Include the states of all audio triggers for image configuration `#`. To include just some audio triggers, set to `no` and use `UserTriggers` instead. |
| `IOEnabled` | `yes` | `yes` `no` | admin: read, write operator: read, write | Include digital input triggers. `yes` = Include the states of all digital input triggers for image configuration `#`. To include just some digital input triggers, set to `no` and use `UserTriggers` instead. |
| `MotionDetectionEnabled` | `yes` | `yes` `no` | admin: read, write operator: read, write | Include motion detection triggers. `yes` = Include the motion detection states of all windows that belong to image configuration `#`. To include just some window states or window states belonging to other image configurations, set to `no` and use `UserTriggers` instead. |
| `MotionLevelEnabled` | `no` | `yes` `no` | admin: read, write operator: read, write | Include motion detection level triggers. `yes` = Include the motion detection levels of all windows that belong to image configuration `#`. To include just some window levels or window levels belonging to other image configurations, set to `no` and use `UserTriggers` instead. |
| `TamperingEnabled` | `yes` | `yes` `no` | admin: read, write operator: read, write | Include camera tampering triggers. `yes` = Include the camera tampering state of image configuration `#`. Use `UserTriggers` to include tampering states for other image configurations. |
| `VideoLossEnabled` | `yes` | `yes` `no` | admin: read, write operator: read, write | Include video loss status. `yes` = Include video loss status for image configuration `#`. Use `UserTriggers` to include video loss states for other image configurations. |
| `UserTriggers` |  | A string | admin: read, write operator: read, write | Include user triggers in the trigger data for image configuration `#`. The string should be in the format `<trigger1>;<trigger2>;<trigger3>;...` Valid triggers are listed in the section [Trigger data blocks](#trigger-data-blocks). |

info

The # in Image.I#.TriggerData counts the image configurations and is replaced by an integer starting from zero, e.g. Image.I0.TriggerData. The number of image configurations is given by the Image.NbrOfConfigs parameter.

## Header data

Three different types of data can be included in the comment header, GOV header and H.264 SEI message:

-   product information
-   time stamps
-   trigger data

To include product information and time stamps in the user data for MPEG-4 or H.264, set the `Image.I#.MPEG.UserDataEnabled` parameters (one for each image configuration) to `yes`. To include trigger data for MPEG-4, H.264 and MJPEG, set the `Image.TriggerDataEnabled` parameter to `yes`.

The Axis ID field identifies the type of user data:

| Axis ID | Description |
| --- | --- |
| `0x0A,0x00` | Product information user data |
| `0x0A,0x01` | Time stamp user data |
| `0x0A,0x03` | Trigger data |

### Product information

The product information user data field contains information such as hardware ID, AXIS OS version and serial number.

| **Value**([1](#user-content-fn-1)) | Size (bytes) | Description |
| --- | --- | --- |
| `0x##,0x##` | 2 | Hardware ID (`0…65535`) |
| `0x##.0x##` | 2 | AXIS OS version (`0x##.0x##)` |
| `0x##` | 1 | AXIS OS build number (`0…255`) |
| `0x00,0x40,0x8c,0x##,0x##,0x##` | 6 | Serial number (`00:40:8c:##:##:##`) |

### Time stamp

The time stamp user data field contains information about the user time and unit time. For products with AXIS OS 5.00 and later, the unit and user times are equivalent, but both are kept for backwards compatibility.

| **Value**([2](#user-content-fn-2)) | Size (bytes) | Description |
| --- | --- | --- |
| `0x##, 0x##,0x##,0x##` | 4 | User Time – Seconds since EPOCH (2…2^32-1). |
| `0x##` | 1 | User Time – 1/100 seconds (0..99). |
| `0x##,0x##,0x##,0x##` | 4 | Unit Time. The unit time is equal to the user time. |
| `0x##` | 1 | Unit Time – 1/100 seconds. |
| `0x##` | 1 | Unit Time – invalid (1). |

### Trigger data

info

Deprecated. Trigger data functionality, that is, trigger data in H.264, MPEG-4 and MJPEG headers, is deprecated and will eventually be removed. Trigger data is replaced by event data streaming, see section [Event data streaming](/vapix/network-video/event-data-streaming/).

The trigger data field is an optional field which can be included in the comment header, GOV header and H.264 SEI message. For further information about triggers see [Trigger data blocks](#trigger-data-blocks).

## Trigger data blocks

info

Deprecated. Trigger data functionality, that is, trigger data in H.264, MPEG-4 and MJPEG headers, is deprecated and will eventually be removed. Trigger data is replaced by event data streaming, see section [Event data streaming](/vapix/network-video/event-data-streaming/).

The trigger data block contains the states of all triggers, as opposed to just including a changed state in one block when it occurs. This allows the receiving application to lose trigger data blocks without necessarily losing a changed state.

The trigger data block, same for all supported video formats, is a block of text containing trigger states in this format:

```bash
<trigger>:<state>;<trigger>:<state>;...
```

Where `<trigger>` is a tag for the trigger and `<state>` is a text describing the state. The following table lists defined trigger tags and their possible states.

| Trigger tag | Description | State |
| --- | --- | --- |
| `A0 ... An` | Status for audio trigger for source `0` to `n`, where `n` is an audio sources >"`0`". | `0` `1` |
| `IO0 ... IOn` | Status for digital input `0` to `n`, where `n` is inputs >"`0`". Note that state "`1`" means that the input is in triggered state, which isn't necessarily the same as that the input is high. Each input can be configured when to trigger. | `0` `1` |
| `V0 ... Vn`([3](#user-content-fn-3)) | Video loss status for video source 0 to n, where n is a video sources >"`0`". State "0" means that there is no video for that video source. | `0` `1` |
| `M0 ... Mn` | Motion detection status for window `0` to n, where `n` is a motion detection windows >"`0`". State "`1`" means that motion has been detected for this window, that is the motion level is above the configured threshold. | `0` `1` |
| `ML0 ... MLn` | Motion detection level for window `0` to n, where `n` is a motion detection windows >"`0`". The state specifies the amount of motion in a motion window. | `000 ...` `100` |
| `T0 ... Tn` | Camera tampering status for source `0` to `n`, where `n` is a video sources >"`0`". State `1` means that camera tampering has been detected for that video source. | `0` `1` |

### MJPEG

For MJPEG the trigger data block is included as a comment header for each image. The image may contain several comments in this format:

| Field | Value | Size (bytes) | Description |
| --- | --- | --- | --- |
| `marker` | `0xFF 0xFE` | 2 | JPEG comment marker. |
| `length` | `0x##, 0x##` | 2 | Length of the comment (starting from Axis ID). |

An example of a comment header. The comment section starts with `ff fe`, the length is `00 48` and the trigger data starts with `0a 03` (marked in bold in the example)

```bash
05 14 07 00 40 8c 18 34  76 ff fe 00 48 0a 03 49 ....@..4 v...H..I4f 30 3a 30 3b 41 30 3a  30 3b 4d 30 3a 30 3b 4d O0:0;A0: 0;M0:0;M4c 30 3a 30 30 30 3b 4d  31 3a 30 3b 4d 4c 31 3a L0:000;M 1:0;ML1:30 30 30 3b 4d 32 3a 30  3b 4d 4c 32 3a 30 30 30 000;M2:0 ;ML2:0003b 4d 33 3a 30 3b 4d 4c  33 3a 30 30 33 3b 54 30 ;M3:0;ML 3:003;T03a 30 3b ff db 00 43 00  0a 07 07 08 07 06 0a 08 :0;...C. ........
```

### MPEG-4

For MPEG-4 the trigger data block is included as "user data" in the GOV header. The GOV header may contain several data blocks following each other in this format. The GOV header is inserted into the MPEG-4 stream at regular intervals. A new GOV header can also be forced to be inserted as soon as possible when a trigger changes state. This is done for I/O triggers to reduce the latency.

| Field | Value | Size (bytes) | Description |
| --- | --- | --- | --- |
| `marker` | `0x00, 0x00, 0x01, 0xB2` | 4 | User data start code. |

An example of user data in the GOV header. The user data section starts with `00 00 01 b2` and the trigger data starts with `0a 03` (both marked in bold in the example)

```bash
80 60 55 a3 bb 26 2d e8  16 3f 3e a5 00 00 01 b3 .\`U..&-. .?>.....11 f3 a7 00 00 01 b2 0a  01 4e 73 cd a7 cf 29 ce ........ .Ns...).79 b7 a9 e4 01 00 00 01  b2 0a 03 49 4f 30 3a 30 y....... ...IO0:03b 41 30 3a 30 3b 4d 30  3a 30 3b 4d 4c 30 3a 30 ;A0:0;M0 :0;ML0:030 30 3b 56 30 3a 31 3b  54 30 3a 30 3b 00 00 01 00;V0:1; T0:0;...b2 0a 00 01 3f 04 2f 02  00 40 8c 71 81 ca 00 00 ....?./. .@.q....01 b6 14 d8 2c 33 14 7f  fa 27 1f 6f fc 6f b7 f1 ....,3.. .'.o.o..
```

### H.264

For H.264 the trigger data block is included as "user data" in the SEI NAL units marked as type user data unregistered. The H.264 SEI message is inserted into the H.264 stream at regular intervals. A new H.264 SEI message can also be forced to be inserted as soon as possible when a trigger changes state. This is done for I/O triggers to reduce the latency.

The first field in the H.264 SEI message is an UUID identifier filled with 16 consecutive `0xAA` bytes. The next three fields are the payload data block including the length of the data block, an identifier and the actual user data. Each SEI may contain several payload data blocks.

info

For further information about H.264 SEI message please refer to the standard document _ISO/IEC 14496-10 Supplemental enhancement information_.

| Field | **Value**([4](#user-content-fn-4)) | Size (bytes) | Description |
| --- | --- | --- | --- |
| \`uuid\_iso\_iec\_11578\`\` | `0xAA,0xAA,0xAA,` `0xAA,0xAA,0xAA,` `0xAA,0xAA,0xAA,` `0xAA,0xAA,0xAA,` `0xAA,0xAA,0xAA,` `0xAA` | 16 | Axis UUID identifier. |
| `Length` | `0x##, 0x##` | 2 | Size of user data (starting from Axis ID). |

An example of user data in the SEI NAL units. The user data section starts with `aa aa ... aa`. There are three length values `00 0d`, `00 0d`, `00 46`. The trigger data starts with `0a 03`. Axis UUID identifier, the size of user data and trigger data start are marked in bold in the example.

```bash
80 60 bc 7a 15 8e 0e 8d  dc 84 63 98 06 05 76 aa .\`.z.... ..c...v.aa aa aa aa aa aa aa aa  aa aa aa aa aa aa aa 00 ........ ........0d 0a 00 00 a2 05 14 07  00 40 8c 18 34 76 00 0d ........ .@..4v..0a 01 4e 73 79 0c 01 4e  73 79 0c 01 01 00 46 0a ..Nsy..N sy....F.03 49 4f 30 3a 30 3b 41  30 3a 30 3b 4d 30 3a 30 .IO0:0;A 0:0;M0:03b 4d 4c 30 3a 30 30 30  3b 4d 31 3a 30 3b 4d 4c ;ML0:000 ;M1:0;ML31 3a 30 30 30 3b 4d 32  3a 30 3b 4d 4c 32 3a 30 1:000;M2 :0;ML2:030 30 3b 4d 33 3a 30 3b  4d 4c 33 3a 30 30 30 3b 00;M3:0; ML3:000;54 30 3a 30 3b 80                                                            T0:0;.
```

## Footnotes

1.  The # is replaced by the symbols 0–9 or A-F. [↩](#user-content-fnref-1)
    
2.  The # is replaced by the symbols 0–9 or A-F. [↩](#user-content-fnref-2)
    
3.  This trigger is only available for video encoders. [↩](#user-content-fnref-3)
    
4.  The # is replaced by the symbols 0–9 or A-F. [↩](#user-content-fnref-4)