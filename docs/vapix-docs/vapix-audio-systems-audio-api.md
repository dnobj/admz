---
title: Audio API
url: "https://developer.axis.com/vapix/audio-systems/audio-api/"
category: vapix
subcategory: audio-systems
sha256: 3587c0b360a3816ea209beb1302787e45d613099265f8f8efc00337f91916cf1
scraped_at: "2026-01-09T15:18:17.308Z"
page_height: 25882
---

# Audio API

## Description

Axis products with audio capabilities usually support two-way audio, that is the Axis product can both transmit and receive audio. Using a built-in or external microphone, the Axis product can capture audio and transmit the audio to the network. Using built-in or external speakers, the Axis product can play audio received from the network. Most products support full duplex and half duplex transmission modes but can also be configured to use simplex modes where the product can only receive or only transmit audio. As audio surveillance is restricted in many countries, audio streaming can always be disabled.

info

For information about audio clips, see [Media clip API](/vapix/audio-systems/media-clip-api/).

Audio from the Axis product can be streamed together with H.264/MJPEG video over RTP/RTSP (including RTP over RTSP over HTTP), together with MJPEG video over HTTP, or on its own. When streaming over RTP/RTSP, audio and video are synchronized. Supported audio compression standards are product-dependent but usually includes G.711, G.726, AAC and Opus. For sample rates and bit rates, see [Audio compression formats](#audio-compression-formats). AAC should be streamed over RTP/RTSP as streaming over HTTP is not part of the standard. AAC and Opus support stereo audio in addition to mono.

Audio settings are defined by parameters in the `Audio` and `AudioSource` groups. Many audio settings are global but the `Audio.A#` groups can be used to set up different audio configurations to be used in different streams. When requesting an HTTP or RTSP stream, argument `audio` determines if audio is streamed or not. If `audio` is omitted, the parameter settings determine if audio is included in the stream.

To enable audio, parameters `Audio.A#.Enabled` and `AudioSource.A#.AudioSupport` must both be set to `yes`.

### Audio modes

Axis network video products can support some or all of the following audio modes:

-   **Full duplex**: Simultaneous two-way audio. Multiple clients can receive audio, but only one client at a time can transmit audio.
-   **Half duplex**: Two-way audio, but only in one direction at a time.
-   **Simplex – Speaker only**: One-way audio where audio is transmitted from the client to the Axis product.
-   **Simplex – Microphone only**: One-way audio where audio is transmitted from the Axis product to the client. Multiple clients can receive audio at the same time.

### Audio compression formats

Axis network video products can support all or some of the following audio compression formats

| Compression | MIME type | Bit rate (kbit/s) | Sample rate (kHz) |
| --- | --- | --- | --- |
| G.711 µ-law | `audio/basic` | 64 | 8 |
| Axis µ-law 128 | `audio/axis-mulaw-128` (Variant of G.711 µ-law with doubled sample rate and bit rate. Can be used for client-to-server communication.) | 128 | 16 |
| G.726 | `audio/G726-32` | 32 | 8 |
|  | `audio/G726-24` | 24 | 8 |
| AAC | `audio/mpeg4-generic` | 8, 12, 16, 24, 32 | 8 |
|  |  | 12, 16, 24, 32, 48, 64 | 16 |
|  |  | 16, 24, 32, 48, 64, 128 | 32 |
|  |  | 32, 48, 64, 128 | 44.1 |
|  |  | 32, 48, 64, 128 | 48 |
| Opus | `audio/opus` | 8, 12, 16, 24, 32 | 8 |
|  |  | 12, 16, 24, 32, 48, 64 | 16 |
|  |  | 32, 48, 64, 128 | 48 |
| LPCM | `audio/L24` | 384, 768, 1058.4, 1152 | 16, 32, 44.1, 48 |

## Prerequisites
### Identification

The Audio API is supported if:

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Audio.Audio=yes`
-   **AXIS OS**: 5.00 and later

The `Properties.Audio` parameters lists supported audio capabilities.

Properties.Audio

| Parameter | Valid values | Description |
| --- | --- | --- |
| `Audio` | `yes` `no` | `yes` = Audio is supported.`no` = Audio is not supported. |
| `Format` | A string | Comma-separated list of supported audio encoding formats.`g711` = G.711 µ-law is supported.`g726` = G.726 is supported.`aac` = AAC is supported.`opus` = Opus is supported.`lpcm` = Lpcm is supported. |
| `DuplexMode` | A string | Comma-separated list of supported duplex modes.`full` = Full duplex mode is supported.`half` = Half duplex mode is supported.`post` = Simplex post mode is supported. The Axis product can transmit simplex audio.`get` = Simplex get mode is supported. The Axis product can receive simplex audio. |
| `InputType` | A string | Comma-separated list of supported input types.`mic` = Microphone input is supported.`line` = Line input is supported. |
| `Decoder.Format` | A string | Comma-separated list of supported audio decoding formats.`g711` = G.711 µ-law is supported.`axis-mulaw-128` = Axis µ-law 128 is supported.`g726` = G.726 is supported.`opus` = Opus is supported. |
| `Source.A#.Input` | `yes` `no` | `yes` = `AudioSource.A#` has audio input.`no` = `AudioSource.A#` does not have audio input. |
| `Source.A#.Output` | `yes` `no` | `yes` = `AudioSource.A#` has audio output.`no` = `AudioSource.A#` does not have audio output. |

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Enable audio in the Axis product. `AudioSource.A0.AudioSupport=yes` enables audio from audio source 0. `Audio.A0.Enabled=yes` enables audio configuration 0.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&AudioSource.A0.AudioSupport=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&AudioSource.A0.AudioSupport=yesHost: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Audio.A0.Enabled=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&Audio.A0.Enabled=yesHost: <servername>
```

Request an RTSP stream with video and audio.

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&audio=1
```

Request an audio stream over HTTP.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/audio/receive.cgi"
```

```bash
GET /axis-cgi/audio/receive.cgiHost: <servername>
```

Limit the maximum number of clients that can receive audio at the same time.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Audio.MaxListeners=5"
```

```bash
GET /axis-cgi/param.cgi?action=update&Audio.MaxListeners=5Host: <servername>
```

Configure the audio source parameters.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&AudioSource.A0.Name=Dynamic%20Microphone&AudioSource.A0.AudioEncoding=g726&AudioSource.A0.InputType=mic&AudioSource.A0.MicrophonePower=no"
```

```bash
GET /axis-cgi/param.cgi?action=update&AudioSource.A0.Name=Dynamic%20Microphone&AudioSource.A0.AudioEncoding=g726&AudioSource.A0.InputType=mic&AudioSource.A0.MicrophonePower=noHost: <servername>
```

## Parameters
### Audio parameters

The `Audio` group contains audio parameters used for all audio configurations.

Audio

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DuplexMode` | Product-dependent | `full` (Product/release-dependent. Check the product’s release notes.) `half` (Product/release-dependent. Check the product’s release notes.) `get` `post` (Product/release-dependent. Check the product’s release notes.) | admin: read, write operator: read, write viewer: read | The audio mode.`full`\= Full duplex. Simultaneous two-way audio.`half`\= Half duplex. Two-way audio, but only in one direction at a time.`get`\= Simplex. Retrieve audio from the Axis product.`post` = Simplex. Send audio to the Axis product. |
| `MaxListeners` | `10` or `20` (Product/release-dependent. Check the product’s release notes.) | `0 … 20` (Product/release-dependent. Check the product’s release notes.) | admin: read, write operator: read, write viewer: read | Maximum number of simultaneous audio clients (does not affect multicast delivery). |
| `ReceiverBuffer` (Product/release-dependent. Check the product’s release notes.) | `120` | `0 … 9999` | admin: read, write operator: read, write viewer: read | The receiving audio buffer size in milliseconds. |
| `ReceiverTimeout` | `1000` | `0 … 9999` | admin: read, write operator: read, write viewer: read | The receiving audio timeout in milliseconds. When the Axis video product is receiving audio data from a client, the session is terminated if no data is received in this time span. |
| `NbrOfConfigs` | Product-dependent | An unsigned integer | admin: read operator: read viewer: read | The number of audio configurations, that is of `Audio.A#` subgroups. |
| `DSCP` | `0` | `0 … 63` | admin: read, write operator: read viewer: read | The Differentiated Services Codepoint for audio Quality of Service (QoS). |

### Audio configuration parameters

The `Audio.A#` groups contain settings for different audio configurations. The audio configurations can be used when requesting audio streams.

info

The # in Audio.A# is replaced by a group number starting from zero, e.g. Audio.A0.

Audio.A#

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable the audio for the specific audio configuration. |
| `HTTPMessageType` | `singlepart` | `singlepart` `multipart` | admin: read, write operator: read, write viewer: read | How audio should be streamed. Some proxies require multipart streaming. |
| `Name` |  | A string | admin: read, write operator: read, write viewer: read | Name of the configuration. |
| `Source` | `0` | An integer (Product/release-dependent) | admin : read, write operator: read, write viewer: read | The audio source a specific audio configuration is connected to. |
| `NbrOfChannels` (Product/release-dependent) | `1` | `1`, `2` | admin : read, write operator: read, write viewer: read | Number of channels in the audio configuration.`1` = mono audio.`2` = stereo audio. |
| `AlarmLevel` (Obsolete) | `50` | `0 ... 100` | admin: read operator: read | Obsolete. Replaced by `AudioSource.A#.AlarmLevel`.Alarm level in percent of the maximum amplitude of the audio samples. The alarm level is used in event setup. Events can be configured to trigger when the sound level rises above or falls below the alarm level. |
| `AlarmResolution` (Obsolete) | `50` | `0 ... 100` | admin: read operator: read | The length of the audio sample used for the audio alarm calculation. The parameter is expressed as percent of a block of 1024 samples, e.g. 50% corresponds to 512 samples. The actual sample time is the number of samples divided by the sample rate, e.g. 512 samples at 8 kHz correspond to 64 ms. An audio alarm is generated when the mean level for a sample exceeds the `AlarmLevel`. A shorter `AlarmResolution` makes the alarm calculation more sensitive. |
| `AlarmLowLimit` (Obsolete) | 50 | `0 ... 10000` | admin: read operator: read | The lowest configurable alarm limit (`AlarmLevel`\=0%) in basis points (`1`/`10000`) of the maximum amplitude value. |
| `AlarmHighLimit` (Obsolete) | 6500 | `0 ... 10000` | admin: read operator: read | The highest configurable alarm limit (`AlarmLevel`\=100%) in basis points (`1`/`10000`) of the maximum amplitude value. |

### Audio source parameters

The `AudioSource` group contains settings for the product’s audio sources.

AudioSource

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `NbrOfSources` | 1 (Product/release-dependent. Check the product’s release notes.) | An unsigned integer | admin: read operator: read viewer: read | The number of audio sources. |
| `AudioSupport` | `yes` | `yes` `no` | admin: read, write operator: read viewer: read | Whether the audio sources should be enabled or not. |

The `AudioSource.A#` groups contain settings for the different audio sources. The `#` is to be replaced by an integer starting from zero, for example `AudioSource.A0`

AudioSource.A#

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Name` | `Audio` | A string | admin: read, write operator: read, write viewer: read | Name of the audio source. |
| `AudioEncoding` | `aac` (Product/release-dependent. Check the product’s release notes.) | (Product-dependent. Check the corresponding Properties parameter.) `g711` `g726` `aac` `opus` `lcpm` | admin: read, write operator: read, write viewer: read | The audio codec. |
| `InputType` | Hardware-dependent | `internal` (Product/release-dependent. Check the product’s release notes.) `mic` `line` (Product/release-dependent. Check the product’s release notes.) `digital` (Product/release-dependent. Check the product’s release notes.) | admin: read, write operator: read, write viewer: read | The source from where the audio is captured. |
| `MicrophonePower` | `yes` (Product/release-dependent. Check the product’s release notes.) | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable power on the audio input connector. |
| `InputGain` | `0` | `mute` Product-dependent numbers (decimals allowed) | admin: read, write operator: read, write viewer: read | Applied gain (in dB) to sound sent from the Axis product. |
| `InputPreGain` (Product/release-dependent. Check the product’s release notes.) | `high` (Product/release-dependent. Check the product’s release notes.) | `low` `high` | admin: read, write operator: read, write viewer: read | Pre-amplifier gain. |
| `OutputGain` (Product/release-dependent. Check the product’s release notes.) | `0` | `mute` Product-dependent numbers (decimals allowed) | admin: read, write operator: read, write viewer: read | Applied gain (in dB) to sound sent to the Axis product. |
| `SampleRate` | Hardware-dependent | (Product/release-dependent. Check the product’s release notes.) `8000` `16000` `32000` `44100` `48000` | admin: read, write operator: read, write viewer: read | Clock rate (in Hz) for the audio sampling. |
| `BitRate` | Encoder-dependent | `g711: 64000` `g726: 24000, 32000` `aac (8 kHz): 8000, 12000, 16000, 24000, 32000` `aac (16 kHz): 12000, 16000, 24000, 32000, 48000, 64000` `aac (32 kHz): 16000, 24000, 32000, 48000, 64000, 128 000` `opus (8 kHz): 8000, 12000, 16000, 24000, 32000` `opus (16 kHz): 12000, 16000, 24000, 32000, 48000, 64000` `opus (48 kHz): 32000, 48000, 64000, 128 000` | admin: read, write operator: read, write viewer: read | The output bit rate (in bits per second). |
| `AudioSupport` | `yes` | `yes` `no` | admin: read, write operator: read viewer: read | Enable/disable audio from this audio source. If the audio source is turned off with this parameter, no audio will be transmitted even if `Audio.A#.Enabled=yes`. |
| `InputPort` (Product/release-dependent. Check the product’s release notes.) | `1` | An integer | admin: read, write operator: read, write viewer: read | Set which audio input port to use if the device got more than one. |
| `MicrophoneBalanced` | `no` (Product/release-dependent. Check the product’s release notes.) | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable balanced audio source. |
| `MicrophonePowerType` | `electret2_5v` (Product/release-dependent. Check the product’s release notes.) | `electret` `electret3_0v` `electret2_5v` `electret2_0v` `p12` `p48` `r12` | admin: read, write operator: read, write viewer: read | The power types to use for the microphone. To set a value it is assumed that `MicrphonePower` is set to `yes`. |
| `SpeakerAmp` (Product/release-dependent. Check the product’s release notes.) | `no` | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable speaker amplifier. |
| `AlarmLevel` | `100` | `0` .. `100` | admin: read, write operator: read, write viewer: read | Alarm level for the `tns1:AudioSource/tnsaxis:TriggerLevel` event. Replaces `Audio.A#.AlarmLevel`.The alarm level is the audio input level expressed in percent. 0% corresponds to the minimum audio level which is -90 dBFS for 16-bit audio. 100% corresponds to the maximum audio level which is 0 dBFS. |
| `LevelIndicator` (Product/release-dependent. Check the product’s release notes.) | `no` | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable audio level indication. |
| `PTZAlarmControl` (Product/release-dependent. Check the product’s release notes.) | `yes` | `yes` `no` | admin: read, write operator: read, write viewer: read | Enable/disable audio level alarm during PTZ movement. Camera movement could create noises that trigger alarms. If set to `yes` no alarms will trigger during PTZ movement. |
| `NbrOfChannels` | Product-dependent | An unsigned integer | admin: read operator: read viewer: read | Number of supported audio channels within the `AudioSource.A#`.1 = Mono audio.2 = Stereo audio.Each channel has its own input and output gain settings. See `AudioSource.A#.Channel.C#` below. |

AudioSource.A#.Channel.C

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `InputGain` | Inherited | `mute` `inherit` Product-dependent numbers (decimals allowed) | admin: read, write operator: read, write viewer: read | Applied gain (in dB) to sound sent from the Axis product.`mute` = Audio is muted.`inherit` = Value is inherited from parameter `AudioSource.A#.InputGain` |
| `OutputGain` | Inherited | `mute` `inherit` Product-dependent numbers (decimals allowed) | admin: read, write operator: read, write viewer: read | Applied gain (in dB) to sound sent to the Axis product.`mute` = Audio is muted.`inherit` = Value is inherited from parameter `AudioSource.A#.OutputGain` |

## HTTP API

The default audio source is `AudioSource.A0.` The default audio device, input and output IDs are `0`.

### Audio data request

Request and configure an audio stream.

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/audio/receive.cgi?\[&<argument>=<value>\]"
```

```bash
GET /axis-cgi/audio/receive.cgi?\[&<argument>=<value>\]Host: <servername>
```

With the following argument and values:

| Argument | Valid values | Description |
| --- | --- | --- |
| `audio=<int>` | `0,1` | Enable (1) or disable (0) audio. |
| `audiobitrate` | `8000..` | The audio bit rate in bps. |
| `audiocodec` | `g711, g726, aac, opus, lpcm` | The audio codec type. |
| `audiosamplerate` | `8000..` | The audio sample rate in Hz. |
| `camera=<int>` | `1...` (The number of audio configurations/audio sources may differ between different cameras and video servers. See the product's specification.) | Select the audio configuration in `Audio.A#`. Note: The argument has a different value than the corresponding parameter. E.g. if the argument `camera=1` then the parameter group is `Audio.A0`. |
| `httptype=<string>` | `singlepart` `multipart` | Choose streaming method. Some proxies require multipart streaming. Default: As defined by the parameter `Audio.A#.HTTPMessageType` |
| `audiochannel=<int>` | `1...` (The number of audio configurations/audio sources may differ between different cameras and video servers. See the product's specification. The arguments `audiochannel` and `audiodeviceid+audioinputid` are mutually exclusive.) | Select the audio source in `AudioSource.A#`. Note: The argument has a different value than the corresponding parameter. E.g. if the argument `audiochannel=2` then the parameter group is `AudioSource.A1`. |
| `audiodeviceid=<string>` | `id` (The number of audio configurations/audio sources may differ between different cameras and video servers. See the product's specification. The arguments `audiochannel` and `audiodeviceid+audioinputid` are mutually exclusive. Support for this argument depends on the status of `audio-device-control` in API discovery. This argument is supported if the status is `official`. `id` is defined in the [Audio Device Control API](/vapix/audio-systems/audio-device-control/).) | The audio device ID. |
| `audioinputid=<string>` | `id` (The number of audio configurations/audio sources may differ between different cameras and video servers. See the product's specification. The arguments `audiochannel` and `audiodeviceid+audioinputid` are mutually exclusive. Support for this argument depends on the status of `audio-device-control` in API discovery. This argument is supported if the status is `official`. `id` is defined in the [Audio Device Control API](/vapix/audio-systems/audio-device-control/).) | The audio device input ID. |
| `audionbrofchannels=<int>` | `1...` | The number of audio channels. |

**Request an audio stream:**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/audio/receive.cgi"
```

```bash
GET /axis-cgi/audio/receive.cgiHost: <servername>
```

### Singlepart audio data response

**Request a singlepart audio stream using HTTP:**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/audio/receive.cgi?httptype=singlepart"
```

```bash
GET /axis-cgi/audio/receive.cgi?httptype=singlepartHost: <servername>
```

**Successful request**

If the request was successful, the server returns a continuous flow of audio packets. The content type is only set at the beginning of the connection. When the connection is up and running audio packets will come one after another without any extra information between the packets.

**Return**  
Successful response to a HTTP request. Here, singlepart audio data with G.711 μ-law compression is returned.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: <Audio MIME>

Syntax:

```bash
<audio data><audio data><audio data>...
```

**Failed request**

If the specified parameter value is invalid, the server returns `400 Bad Request`.

**Return**

-   **HTTP Code**: `400 Bad Request`

Syntax:

```bash
<body>
```

### Multipart audio data response

**Request a multipart audio stream using HTTP:**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/audio/receive.cgi?httptype=multipart"
```

```bash
GET /axis-cgi/audio/receive.cgi?httptype=multipartHost: <servername>
```

**Successful request**

If the request was successful, the server returns a continuous flow of audio packets. The content type is "`multipart/x-mixed-replace`" and each audio packet ends with a boundary string. The message body contains a block of binary data. The content length provides the size of each block of coded audio which varies for different codecs: G.711 has 512 bytes block size, G.726 32 kbit/s has 256 bytes and G.726 24 kbits/s has 192 bytes. AAC is not supported.

**Return**  
Successful response to a HTTP request. Here, multipart audio data with G.726 32 kbit/s compression is returned.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `multipart/x-mixed-replace; boundary=<boundary>`

Syntax:

```bash
--myboundary \\r\\nContent-Type: audio/G726-32\\r\\nContent-Length: <content length>\\r\\n<Audio data>\\r\\n--myboundary\\r\\nContent-Type: audio/G726-32\\r\\nContent-Length: <content length>\\r\\n<Audio data>\\r\\n--myboundary\\r\\nContent-Type: audio/G726-32\\r\\nContent-Length: <content length>\\r\\n<Audio data>\\r\\n--myboundary\\r\\nContent-Type: audio/G726-32\\r\\nContent-Length: <content length>\\r\\n<Audio data>\\r\\n--myboundary\\r\\n
```

**Failed request**

If the specified parameter value is invalid, the server returns `400 Bad Request`.

**Return**

-   **HTTP Code**: `400 Bad Request`

Syntax:

```bash
<body>
```

### Transmit audio data

**Transmit a singlepart audio data stream:**

Check what audio formats your Axis product can transmit. For a complete list of audio formats supported by VAPIX® see [Audio compression formats](#audio-compression-formats).

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Audio.Decoder"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Audio.DecoderHost: <servername>
```

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: <Audio MIME>" \\  "http://<servername>/axis-cgi/audio/transmit.cgi\[&<argument>=<value>\]"
```

```bash
POST /axis-cgi/audio/transmit.cgi\[&<argument>=<value>\]Host: <servername>Content-Type: <Audio MIME>
```

| Argument | Valid values | Description |
| --- | --- | --- |
| `audiodeviceid=<string>` | `id` (Support for this argument depends on the status of `audio-device-control` in API discovery. This argument is supported if the status is `official`. `id` is defined in the [Audio Device Control API](/vapix/audio-systems/audio-device-control/).) | The audio device ID. |
| `audiooutputid=<string>` | `id` (Support for this argument depends on the status of `audio-device-control` in API discovery. This argument is supported if the status is `official`. `id` is defined in the [Audio Device Control API](/vapix/audio-systems/audio-device-control/).) | The audio device output ID. |

Request body:

```bash
<Audio data>
```

There are no arguments and values to `/axis-cgi/audio/transmit.cgi`.

When an audio stream is transmitted, the server receives a continuous flow of audio packets. The content type is only set at the beginning of the connection together with the content length that can have any value. When the connection is up and running the audio packets will come right after another without any extra information between the packets. The message body contains a block of binary data.

The content length must be set to a valid size and will generate a server response for every successful playback. If the playback fails, the connection will be closed without any response.

**Transmit singlepart audio using G.711 µ-law (authorization omitted):**

```bash
POST /axis-cgi/audio/transmit.cgi HTTP/1.0\\r\\nContent-Type: audio/basic\\r\\n\\r\\n<Audio data><Audio data><Audio data>...
```

### Error responses

This section describes the error responses that can occur when using the API.

| Error code | Content-Type | Error message | Description |
| --- | --- | --- | --- |
| `400` | _text/plain_ | Bad request | The request had a bad syntax, or could not be implemented. |
| `405` | _text/plain_ | Method not allowed | The GET/POST is not allowed in the current mode. |
| `415` | _text/plain_ | Unsupported media type | The request is not in an acceptable format and can’t be processed. |
| `503` | _text/plain_ | Service unavailable | The maximum number of clients are already connected. |

## Audio in the RTSP API

Media streams transmitted over RTSP include audio if the request contains `audio=1` or if parameters `Audio.A#.Enabled` and `AudioSource.A#.AudioSupport` are enabled. If `audio=0`, the stream does not include audio even if the parameters are enabled.

When `AudioSource.A#.AudioSupport` is enabled, the `camera` and `audiochannel` arguments from `/axis-cgi/audio/receive.cgi` can be used when requesting RTSP streams. The `camera` argument specifies both the video source and the audio configuration.

## Audio detection event

The Audio Detection event is `true` when the sound level rises above the audio alarm level defined by parameter `AudioSource.A#.AlarmLevel`.

**Topic**

-   **Name**: `tns1:AudioSource/tnsaxis:TriggerLevel`
-   **Type**: Stateful
-   **Nice name**: `Audio detection`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

| Value | Nice name |
| --- | --- |
| `1` | — |
| `2` | — |
| `...` | — |
| `n = number of audio channels` | — |

**Data instance**

-   **Nice name**: `Above alarm leve`l
-   **Type**: boolean
-   **Name**: `triggered`
-   **isPropertyState**: `true`