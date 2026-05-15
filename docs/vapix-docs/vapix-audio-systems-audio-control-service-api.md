---
title: Audio control service API
url: "https://developer.axis.com/vapix/audio-systems/audio-control-service-api/"
category: vapix
subcategory: audio-systems
sha256: 99661ebf8e2f6e6bd7373e562d1b50089e888923420003f97e9d983a17fb7efb
scraped_at: "2026-01-09T15:18:18.754Z"
page_height: 7666
---

# Audio control service API

## Description

The Audio Control service provides mechanisms for adjusting the foreground and background volume for a device.

Foreground volume will set the volume for high priority audio, such as audio clips and VoIP (Voice over Internet Protocol).

Background volume is audio at a lower priority, for example ACAP Audio Players playing background music or a line in when available. Foreground audio is always prioritized over background audio.

info

Please note that this API has been deprecated as of AXIS OS version 10.12 and will no longer receive any updates.

### Identification

The Audio Control Service is supported if

-   **Property**: `Properties.API.AudioControl.Version="1.0"`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

**JSON and simplified key-value requests**

In some VAPIX API:s requests can be constructed using JSON or a simplified key-value format.

The simplified key-value format is a flattened structure with `key=value` strings. Levels in the structure are indicated by underscores (`_`).

-   Boolean values are encoded as `true` and `false`.
-   The `NULL` value is encoded as `null`.
-   Strings are URL-encoded and may start and end with quotation marks. Example: `"a+string%0A"`.
-   Array keys are encoded as `_index_` where `index` is an integer starting from 0.

### Simple cURL examples

This example shows how to get the volume via cURL

JSON Request for GetVolume

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/vapix/audiocontrol" \\  --data '{"axac:GetVolume":{}}'
```

```bash
POST /vapix/audiocontrolHost: <servername>Content-Type: application/json{"axac:GetVolume":{}}
```

Response:

```bash
{    "Volume": {        "ForegroundVolume": -20,        "ForegroundVolumeUnit": "dB",        "ForegroundVolumeMute": false,        "BackgroundVolume": -20,        "BackgroundVolumeUnit": "dB",        "BackgroundVolumeMute": false    }}
```

Simple Request for GetVolume

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/vapix/audiocontrol?...format=simple&action=axac:GetVolume"
```

```bash
GET /vapix/audiocontrol?...format=simple&action=axac:GetVolumeHost: <servername>
```

Response:

```bash
Volume\_ForegroundVolume=-20Volume\_ForegroundVolumeUnit="dB"Volume\_ForegroundVolumeMute=falseVolume\_BackgroundVolume=-20Volume\_BackgroundVolumeUnit="dB"Volume\_BackgroundVolumeMute=false
```

### Adjust volume

Use `axac:SetVolume` to adjust the volume of the device. Optional parameters can be left unused if default values are valid. The following example adjusts the foreground volume and sets the background to mute.

Request to set volume JSON format

```bash
{    "axac:SetVolume": {        "Volume": {            "ForegroundVolume": -21,            "BackgroundVolumeMute": true        }    }}
```

Response

```bash
{}
```

Request to set volume using simple format

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/vapix/audiocontrol?...format=simple&action=axac:SetVolume&Volume\_ForegroundVolume=-21&Volume\_BackgroundVolumeMute=true"
```

```bash
GET /vapix/audiocontrol?...format=simple&action=axac:SetVolume&Volume\_ForegroundVolume=-21&Volume\_BackgroundVolumeMute=trueHost: <servername>
```

Response

```bash

```
### Adjust InputConfiguration

Use `axac:SetInputConfiguration` to specify which audio inputs that should be used. Information regarding the valid values available for the `InputId` and `ChannelId` can be requested using the `axac:GetControlCapabilities` call. Please note that not all devices support line input capabilities and as such, it will not always be possible to adjust the feature.

Request to set an input configuration in JSON format

```bash
{    "axac:SetInputConfiguration": {        "InputConfiguration": {            "InputId": "analog\_1",            "ChannelId": "Background",            "Enabled": true        }    }}
```

Response

```bash
{}
```

## Service capabilities

The `GetControlCapabilities` call can be used to retrieve the capabilities of the service, to handle future extensions.

**Range**

Describes a range of valid values and the unit.

| Field | Type | Description |
| --- | --- | --- |
| `Unit` | String | The unit of the value, (e.g. dB). |
| `MaxValue` | int | The maximum value of the range. |
| `MinValue` | int | The minimum value of the range. |

**Control Capabilities**

The structure of `ServiceCapabilities` reflects the optional functionality of a service. The information is static and does not change during device operation.

| Field | Type | Description |
| --- | --- | --- |
| `VolumeRanges` | Range | Master volume ranges as supported by this service. |

**GetControlCapabilities Command**

This operation returns the capabilities of the service.

Request

```bash
{}
```

The request is empty.

Response

```bash
{    "Capabilities": {        <ControlCapabilities>    }}
```

| Parameter | Description |
| --- | --- |
| `Capabilities` | The capability response message contains the capabilities that are present in the device. |

## Audio control volume configuration

**Volume**

The configuration of foreground and background volumes for a device. Valid parameter values may be defined by the service capabilities. The following fields are available, some of which are optional:

| Field | Type | Description |
| --- | --- | --- |
| `ForegroundVolume` | int | The foreground volume. |
| `ForegroundVolumeUnit` | String | The unit of the foreground volume. Optional parameter to use if default unit type is not used. |
| `ForegroundVolumeMute` | Boolean | Mutes the foreground volume. |
| `BackgroundVolume` | int | The background volume. |
| `BackgroundVolumeUnit` | String | The unit of the background volume. Optional parameter to use if default unit type is not used. |
| `BackgroundVolumeMute` | Boolean | Mutes the background volume of the Audio Relay Network. |

**SetVolume Command**

Requests that a `Volume` should be set. All members of the `Volume` are optional, so a `Volume` with all members empty will be accepted, but won’t change anything.

Request

```bash
{    "Volume": {        <Volume>    }}
```

| Parameter | Description |
| --- | --- |
| `Volume` | The volume to set. |

**GetVolume command**

Returns the `Volume` of the Audio Relay network.

Request

```bash
{}
```

The request is empty.

Response

```bash
{  "Volume": {    <Volume>  }}
```

| Parameter | Description |
| --- | --- |
| `Volume` | The returned volume. |