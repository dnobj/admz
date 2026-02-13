---
title: AXIS Audio Manager Pro API
url: "https://developer.axis.com/vapix/audio-systems/axis-audio-manager-pro-api/"
category: vapix
subcategory: audio-systems
sha256: 4ec4af0bb95fb9ecf953c3a1c0b9cd7cee86d90618799582dda36c37e7e16a15
scraped_at: "2026-01-09T15:18:30.507Z"
page_height: 68740
---

# AXIS Audio Manager Pro API

The VAPIX® AXIS Audio Manager Pro API can be used together with the AXIS Audio Manager Pro software to manage larger and more advanced audio installations. Supported features includes central control, zone management, scheduling, system health monitoring and real time configuration. Using this API makes it possible to make programmatic interactions with an existing Audio Manager Pro installation, including:

-   Start/Stop the playback of an audio file.
-   Silence either the whole or parts of a site.

Access to the API is enabled in the System settings in the Audio Manager Pro interface. Clients are then able to authenticate using the Digest Authentication method and the username and password specified in the System settings.

Further information on how to use the API is available in the document **How To AXIS Audio Manager Pro API**, available from [AXIS Audio Manager Pro](https://www.axis.com/products/axis-audio-manager-pro/support#support-resources).

## Overview

The API is divided into the following sections containing their own operations and methods:

-   [Audio sessions](#audio-sessions) — Plays a live or pre-recorded announcement to either the entire or parts of a site. The session contains a list of designated targets and a priority setting. An audio session can be used one time or saved for future use.
-   [Targets](#targets) — Endpoints used to interact with available targets such as physical zones and destinations. Targets can be enabled/disabled or be used to define where audio sessions should be played.
-   [Audio files](#audio-files) — Announcements or music available on the AXIS Audio Manager Pro server. These endpoints can be used to retrieve and list information about them.
-   [Volume controllers](#volume-controllers) — Offsets the volume of content classes in whole or parts of the audio site. The volume controllers are typically created during installation and setup, where the endpoints are used to interact with already created volume controllers.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Audio sessions
### List audio sessions

This method should be used when you want to retrieve a list of available audio sessions.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioSessions"
```

```bash
GET /api/v1.1/audioSessionsHost: <servername>
```

_AudioSessionHTTP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "holdup": 200,    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "HTTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `holdup=<integer>` _Optional_ | 200 (default value) |  | The holdup time, measured in ms (milliseconds) of the pre-buffered audio. Defines the latency of the audio session. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `HTTP` | The type of the audio session. |

_AudioSessionRTP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "codecs": \[        {            "audioProfile": "g711aMono8kHz",            "payloadType": 127        }    \],    "encryption": {        "cryptosuite": "AES\_CM\_128\_HMAC\_SHA1\_80",        "encrypted": false,        "srtpKey": "d0RmdmcmVCspeEc3QGZiNWpVLFJhQX1cfHAwJSoj"    },    "id": "156",    "multicastGroup": "string",    "port": 0,    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "RTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `codecs` |  |  | The codecs for the RTP session. |
| _AudioSessionRTPCodec parameters_ |  |  |  |
| `audioProfile=<string>` |  | `[g711aMono8kHz, g711uMono8kHz, g722Mono16kHz, l16Stereo48kHz, l16Mono48kHz, l16Stereo44kHz, l16Mono44kHz, l16Stereo32kHz, l16Mono32kHz, l16Stereo16kHz, l16Mono16kHz, mp2Stereo48kHz, opusStereo48kHz, opusMono48kHz]` | The audio profile. |
| `payloadType=<integer>` |  | Maximum: 127 Minimum: 0 | The payload type. This is only for codecs supporting the dynamic payload type. |
| `encryption` |  |  | The encryption for the RTP session. |
| _AudioSessionRTPEncryption parameters_ |  |  |  |
| `cryptosuite=<string>` |  | `[AES_CM_128_HMAC_SHA1_80, AES_CM_128_HMAC_SHA1_32, AES_192_CM_HMAC_SHA1_80, AES_192_CM_HMAC_SHA1_32, AES_256_CM_HMAC_SHA1_80, AES_256_CM_HMAC_SHA1_32, F8_128_HMAC_SHA1_80, SEED_CTR_128_HMAC_SHA1_80, SEED_128_CCM_80, SEED_128_GCM_96, AEAD_AES_128_GCM, AEAD_AES_256_GCM]` | The crypto suit algorithm. Required when `encrypted` is `true`. |
| `encrypted=<boolean>` |  | `true` `false` (default value) | Set to `true` if the stream is encrypted with SRTP. Please note that SRTP only works for new streams and not when it has to connect to an existing SRTP stream. |
| `srtpKey=<string>` | `d0RmdmcmVCspeEc3QGZ iNWpVLFJhQX1cfHAwJSoj` |  | The SRTP encryption key encoded by Base64. Required when `encrypted` is `true`. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `multicastgroup=<string>` |  |  | The IPv4 or IPv6 address of a multicast group. Used in cases where the sender is streaming via multicast. |
| `port=<integer>` |  |  |  |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `RTP` | The type of the audio session. |

_AudioSessionSIP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "duplexDevice": {        "id": "dev\_15",        "sourceId": "dsc\_15"    },    "extention": "3256",    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "SIP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `duplexdevice` |  |  | The device with the audio input that will send the audio back. Devices with multiple inputs need a specified `sourceId`. This parameters can be skipped on devices with only one input. The device must also be in the targets list, which means that it is included in a zone, otherwise no audio will be returned. |
| _DeviceWithSource_ |  |  |  |
| `id` | `dev_15` |  | A unique device ID. |
| `sourceId` | `dsc_15` |  | A unique device source id. |
| `extension=<string>` | `3256` |  | An extension for dialing. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `SIP` | The type of the audio session. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [500 Internal server error](#500-internal-server-error)

### Create an audio session

This method should be used when you want to create a new audio session. Available types are HTTP, RTP and SIP.

_AudioSessionHTTP_

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions" \\  --data '{    "holdup": 200,    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "HTTP"}'
```

```bash
POST /api/v1.1/audioSessionsHost: <servername>Content-Type: application/json{    "holdup": 200,    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "HTTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `holdup=<integer>` _Optional_ | 200 (default value) |  | The holdup time, measured in ms (milliseconds) of the pre-buffered audio. Defines the latency of the audio session. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `HTTP` | The type of the audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "holdup": 200,    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "HTTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `holdup=<integer>` _Optional_ | 200 (default value) |  | The holdup time, measured in ms (milliseconds) of the pre-buffered audio. Defines the latency of the audio session. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `HTTP` | The type of the audio session. |

_AudioSessionRTP_

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions" \\  --data '{    "codecs": \[        {            "audioProfile": "g711aMono8kHz",            "payloadType": 127        }    \],    "encryption": {        "cryptosuite": "AES\_CM\_128\_HMAC\_SHA1\_80",        "encrypted": false,        "srtpKey": "d0RmdmcmVCspeEc3QGZiNWpVLFJhQX1cfHAwJSoj"    },    "id": "156",    "multicastGroup": "string",    "port": 0,    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "RTP"}'
```

```bash
POST /api/v1.1/audioSessionsHost: <servername>Content-Type: application/json{    "codecs": \[        {            "audioProfile": "g711aMono8kHz",            "payloadType": 127        }    \],    "encryption": {        "cryptosuite": "AES\_CM\_128\_HMAC\_SHA1\_80",        "encrypted": false,        "srtpKey": "d0RmdmcmVCspeEc3QGZiNWpVLFJhQX1cfHAwJSoj"    },    "id": "156",    "multicastGroup": "string",    "port": 0,    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "RTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `codecs` |  |  | The codecs for the RTP session. |
| _AudioSessionRTPCodec parameters_ |  |  |  |
| `audioProfile=<string>` |  | `[g711aMono8kHz, g711uMono8kHz, g722Mono16kHz, l16Stereo48kHz, l16Mono48kHz, l16Stereo44kHz, l16Mono44kHz, l16Stereo32kHz, l16Mono32kHz, l16Stereo16kHz, l16Mono16kHz, mp2Stereo48kHz, opusStereo48kHz, opusMono48kHz]` | The audio profile. |
| `payloadType=<integer>` |  | Maximum: 127 Minimum: 0 | The payload type. This is only for codecs supporting the dynamic payload type. |
| `encryption` |  |  | The encryption for the RTP session. |
| _AudioSessionRTPEncryption parameters_ |  |  |  |
| `cryptosuite=<string>` |  | `[AES_CM_128_HMAC_SHA1_80, AES_CM_128_HMAC_SHA1_32, AES_192_CM_HMAC_SHA1_80, AES_192_CM_HMAC_SHA1_32, AES_256_CM_HMAC_SHA1_80, AES_256_CM_HMAC_SHA1_32, F8_128_HMAC_SHA1_80, SEED_CTR_128_HMAC_SHA1_80, SEED_128_CCM_80, SEED_128_GCM_96, AEAD_AES_128_GCM, AEAD_AES_256_GCM]` | The crypto suit algorithm. Required when `encrypted` is `true`. |
| `encrypted=<boolean>` |  | `true` `false` (default value) | Set to `true` if the stream is encrypted with SRTP. Please note that SRTP only works for new streams and not when it has to connect to an existing SRTP stream. |
| `srtpKey=<string>` | `d0RmdmcmVCspeEc3QGZ iNWpVLFJhQX1cfHAwJSoj` |  | The SRTP encryption key encoded by Base64. Required when `encrypted` is `true`. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `multicastgroup=<string>` |  |  | The IPv4 or IPv6 address of a multicast group. Used in cases where the sender is streaming via multicast. |
| `port=<integer>` |  |  |  |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `RTP` | The type of the audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "codecs": \[        {            "audioProfile": "g711aMono8kHz",            "payloadType": 127        }    \],    "encryption": {        "cryptosuite": "AES\_CM\_128\_HMAC\_SHA1\_80",        "encrypted": false,        "srtpKey": "d0RmdmcmVCspeEc3QGZiNWpVLFJhQX1cfHAwJSoj"    },    "id": "156",    "multicastGroup": "string",    "port": 0,    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "RTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `codecs` |  |  | The codecs for the RTP session. |
| _AudioSessionRTPCodec parameters_ |  |  |  |
| `audioProfile=<string>` |  | `[g711aMono8kHz, g711uMono8kHz, g722Mono16kHz, l16Stereo48kHz, l16Mono48kHz, l16Stereo44kHz, l16Mono44kHz, l16Stereo32kHz, l16Mono32kHz, l16Stereo16kHz, l16Mono16kHz, mp2Stereo48kHz, opusStereo48kHz, opusMono48kHz]` | The audio profile. |
| `payloadType=<integer>` |  | Maximum: 127 Minimum: 0 | The payload type. This is only for codecs supporting the dynamic payload type. |
| `encryption` |  |  | The encryption for the RTP session. |
| _AudioSessionRTPEncryption parameters_ |  |  |  |
| `cryptosuite=<string>` |  | `[AES_CM_128_HMAC_SHA1_80, AES_CM_128_HMAC_SHA1_32, AES_192_CM_HMAC_SHA1_80, AES_192_CM_HMAC_SHA1_32, AES_256_CM_HMAC_SHA1_80, AES_256_CM_HMAC_SHA1_32, F8_128_HMAC_SHA1_80, SEED_CTR_128_HMAC_SHA1_80, SEED_128_CCM_80, SEED_128_GCM_96, AEAD_AES_128_GCM, AEAD_AES_256_GCM]` | The crypto suit algorithm. Required when `encrypted` is `true`. |
| `encrypted=<boolean>` |  | `true` `false` (default value) | Set to `true` if the stream is encrypted with SRTP. Please note that SRTP only works for new streams and not when it has to connect to an existing SRTP stream. |
| `srtpKey=<string>` | `d0RmdmcmVCspeEc3QGZ iNWpVLFJhQX1cfHAwJSoj` |  | The SRTP encryption key encoded by Base64. Required when `encrypted` is `true`. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `multicastgroup=<string>` |  |  | The IPv4 or IPv6 address of a multicast group. Used in cases where the sender is streaming via multicast. |
| `port=<integer>` |  |  |  |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `RTP` | The type of the audio session. |

_AudioSessionSIP_

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions" \\  --data '{    "duplexDevice": {        "id": "dev\_15",        "sourceId": "dsc\_15"    },    "extention": "3256",    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "SIP"}'
```

```bash
POST /api/v1.1/audioSessionsHost: <servername>Content-Type: application/json{    "duplexDevice": {        "id": "dev\_15",        "sourceId": "dsc\_15"    },    "extention": "3256",    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "SIP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `duplexdevice` |  |  | The device with the audio input that will send the audio back. Devices with multiple inputs need a specified `sourceId`. This parameters can be skipped on devices with only one input. The device must also be in the targets list, which means that it is included in a zone, otherwise no audio will be returned. |
| _DeviceWithSource_ |  |  |  |
| `id` | `dev_15` |  | A unique device ID. |
| `sourceId` | `dsc_15` |  | A unique device source id. |
| `extension=<string>` | `3256` |  | An extension for dialing. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `SIP` | The type of the audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "duplexDevice": {        "id": "dev\_15",        "sourceId": "dsc\_15"    },    "extention": "3256",    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "SIP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `duplexdevice` |  |  | The device with the audio input that will send the audio back. Devices with multiple inputs need a specified `sourceId`. This parameters can be skipped on devices with only one input. The device must also be in the targets list, which means that it is included in a zone, otherwise no audio will be returned. |
| _DeviceWithSource_ |  |  |  |
| `id` | `dev_15` |  | A unique device ID. |
| `sourceId` | `dsc_15` |  | A unique device source id. |
| `extension=<string>` | `3256` |  | An extension for dialing. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `SIP` | The type of the audio session. |

**Error responses**

-   [400 Invalid parameters](#400-invalid-parameters)
-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Play one shot audio files

This method should be used when you want to create a temporary audio session and trigger playback for an array of audio files. The audio session is deleted after playback, but can be also be stopped by deleting the audio session returned by the request.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions/oneshotPlayAudioFiles" \\  --data '{    "fileIds": \["15", "19"\],    "prio": "HIGH",    "repeat": 1,    "targets": \["zon\_1", "dev\_15"\]}'
```

```bash
POST /api/v1.1/audioSessions/oneshotPlayAudioFilesHost: <servername>Content-Type: application/json{    "fileIds": \["15", "19"\],    "prio": "HIGH",    "repeat": 1,    "targets": \["zon\_1", "dev\_15"\]}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `fileIds=<array>` | `[ "15", "19" ]` |  | The IDs of the audio files that will be played. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `repeat=<integer>` |  | `1` (default value) | Indicates the number of times the audio files will be played. |
| `targets=<string>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "holdup": 200,        "id": "156",        "prio": "HIGH",        "targets": \["zon\_1", "dev\_15"\],        "type": "HTTP"    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `holdup=<integer>` _Optional_ | 200 (default value) |  | The holdup time, measured in ms (milliseconds) of the pre-buffered audio. Defines the latency of the audio session. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `HTTP` | The type of the audio session. |

**Error responses**

-   [400 Invalid parameters](#400-invalid-parameters)
-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Delete a specific audio session

This method should be used when you want to delete an existing audio session. Deleting the audio session will also cancel any ongoing audio playback.

**Request**

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioSessions/<audio session id>"
```

```bash
DELETE /api/v1.1/audioSessions/<audio session id>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `<audio session id>` | The ID of the audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Retrieve a specific audio session

This method should be used when you want to retrieve an existing audio session.

**Request**

-   **Method**: `GET`
-   **Content-Type**: `application/json`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioSessions/<audioSessionId>"
```

```bash
GET /api/v1.1/audioSessions/<audioSessionId>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `audioSessionId` | The ID of the audio session. |

_AudioSessionHTTP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "holdup": 200,    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "HTTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `holdup=<integer>` _Optional_ | 200 (default value) |  | The holdup time, measured in ms (milliseconds) of the pre-buffered audio. Defines the latency of the audio session. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `HTTP` | The type of the audio session. |

_AudioSessionRTP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "codecs": \[        {            "audioProfile": "g711aMono8kHz",            "payloadType": 127        }    \],    "encryption": {        "cryptosuite": "AES\_CM\_128\_HMAC\_SHA1\_80",        "encrypted": false,        "srtpKey": "d0RmdmcmVCspeEc3QGZiNWpVLFJhQX1cfHAwJSoj"    },    "id": "156",    "multicastGroup": "string",    "port": 0,    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "RTP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `codecs` |  |  | The codecs for the RTP session. |
| _AudioSessionRTPCodec parameters_ |  |  |  |
| `audioProfile=<string>` |  | `[g711aMono8kHz, g711uMono8kHz, g722Mono16kHz, l16Stereo48kHz, l16Mono48kHz, l16Stereo44kHz, l16Mono44kHz, l16Stereo32kHz, l16Mono32kHz, l16Stereo16kHz, l16Mono16kHz, mp2Stereo48kHz, opusStereo48kHz, opusMono48kHz]` | The audio profile. |
| `payloadType=<integer>` |  | Maximum: 127 Minimum: 0 | The payload type. This is only for codecs supporting the dynamic payload type. |
| `encryption` |  |  | The encryption for the RTP session. |
| _AudioSessionRTPEncryption parameters_ |  |  |  |
| `cryptosuite=<string>` |  | `[AES_CM_128_HMAC_SHA1_80, AES_CM_128_HMAC_SHA1_32, AES_192_CM_HMAC_SHA1_80, AES_192_CM_HMAC_SHA1_32, AES_256_CM_HMAC_SHA1_80, AES_256_CM_HMAC_SHA1_32, F8_128_HMAC_SHA1_80, SEED_CTR_128_HMAC_SHA1_80, SEED_128_CCM_80, SEED_128_GCM_96, AEAD_AES_128_GCM, AEAD_AES_256_GCM]` | The crypto suit algorithm. Required when `encrypted` is `true`. |
| `encrypted=<boolean>` |  | `true` `false` (default value) | Set to `true` if the stream is encrypted with SRTP. Please note that SRTP only works for new streams and not when it has to connect to an existing SRTP stream. |
| `srtpKey=<string>` | `d0RmdmcmVCspeEc3QGZ iNWpVLFJhQX1cfHAwJSoj` |  | The SRTP encryption key encoded by Base64. Required when `encrypted` is `true`. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `multicastgroup=<string>` |  |  | The IPv4 or IPv6 address of a multicast group. Used in cases where the sender is streaming via multicast. |
| `port=<integer>` |  |  |  |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `RTP` | The type of the audio session. |

_AudioSessionSIP_

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "duplexDevice": {        "id": "dev\_15",        "sourceId": "dsc\_15"    },    "extention": "3256",    "id": "156",    "prio": "HIGH",    "targets": \["zon\_1", "dev\_15"\],    "type": "SIP"}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `duplexdevice` |  |  | The device with the audio input that will send the audio back. Devices with multiple inputs need a specified `sourceId`. This parameters can be skipped on devices with only one input. The device must also be in the targets list, which means that it is included in a zone, otherwise no audio will be returned. |
| _DeviceWithSource_ |  |  |  |
| `id` | `dev_15` |  | A unique device ID. |
| `sourceId` | `dsc_15` |  | A unique device source id. |
| `extension=<string>` | `3256` |  | An extension for dialing. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `prio=<string>` _Optional_ | `"HIGH"` | `"HIGH"` `"MEDIUM"` `"LOW"` (default value) | The priority parameter indicates the relative priority of an audio session compared to other playing audio. Sessions with a higher priority will automatically silence audio sessions with a lower priority in the same targets. The first audio session will have higher priority if multiple API audio sessions with the same priority and to the same targets are simultaneously active. The audio session priority levels (high, medium, low) correspond to the paging priority groups in the web interface in _Scheduling & Destinations > Content Priorities > Paging_. New audio sessions will be placed at the lowest priority in the priority group. |
| `targets=<array>` | `[ "zon_1", "dev_15" ]` |  | The targets of the audio session. Accepted types are `"physicalZone"` and `"device"`. |
| `type=<string>` |  | `SIP` | The type of the audio session. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Play audio files

This method should be used when you want to trigger a playback for an array of audio files from the content library. Files listed in the audio session will be played in succession. The current playback will be replaced if this method is used while an audio file is played in the audio session.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions/<audioSessionId>/playAudioFiles" \\  --data '{    "fileIds": \["15", "19"\],    "repeat": 1}'
```

```bash
POST /api/v1.1/audioSessions/<audioSessionId>/playAudioFilesHost: <servername>Content-Type: application/json{    "fileIds": \["15", "19"\],    "repeat": 1}
```

| Parameter | Description |
| --- | --- |
| `audioSessionId=<string>` | The ID of the HTTP audio session. |

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `fileIds=<array>` | `[ "15", "19" ]` |  | The IDs of the audio files that will be played. |
| `repeat=<integer>` |  | `1` (default value) | Indicates the number of times the audio files will be played. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [400 Invalid parameters](#400-invalid-parameters)
-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Check audio session status

This method should be used when you want to check the status of an existing audio session, including playback and availability of devices in the sessions.

info

This method was introduced in API version 1.1 and can not be used by devices with API version 1.0.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioSessions/<audioSessionId>/status"
```

```bash
GET /api/v1.1/audioSessions/<audioSessionId>/statusHost: <servername>
```

| Parameter | Description |
| --- | --- |
| `audioSessionId` | The ID of the audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
{    "availableDevices": \["dev\_1", "dev\_15"\],    "id": "156",    "playbackStarted": "2023-01-12 12:53:32+0100",    "status": "notPlaying",    "unavailableDevices": \["dev\_2", "dev\_13"\]}
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `availableDevices=<string>` | `[ "dev_1", "dev_15" ]` |  | A list of devices that successfully received and played the entire announcement. |
| `id=<string>` | 156 |  | A unique audio session ID. |
| `playbackStarted=<string>` | `2023-01-12 12:53:32+0100` |  | The time when the `audioSession` started. |
| `status=<string>` |  | `notPlaying` `playing` | The status of the `audioSession`. |
| `unavailableDevices=<string>` | `[ "dev_2", "dev_13" ]` |  | A list of devices where the announcement is partially or fully out prioritized by a higher priority announcement. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Stop audio files

This method should be used when you want to stop playing audio files in the session.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/audioSessions/<audioSessionId>/stopAudioFiles"
```

```bash
POST /api/v1.1/audioSessions/<audioSessionId>/stopAudioFilesHost: <servername>Content-Type: application/json
```

| Parameter | Description |
| --- | --- |
| `audioSessionId=<string>` | The ID of the HTTP audio session. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Upload audio data

This method should be used when you want to upload audio data to a specific audio session.

info

This method was introduced in API version 1.1 and can not be used by devices with API version 1.0.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: audio/mpeg; codecs="opus"" \\  "http://<servername>/api/v1.1/audioSessions/<audioSessionId>/upload"
```

```bash
POST /api/v1.1/audioSessions/<audioSessionId>/uploadHost: <servername>Content-Type: audio/mpeg; codecs="opus"
```

| Parameter | Description |
| --- | --- |
| `audioSessionId=<string>` | The ID of the HTTP audio session. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

## Targets
### List targets

This method should be used when you want to list all available targets, including physical zones and destinations. Targets can be enabled/disabled or be used to define where the audio session should be played.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/targets"
```

```bash
GET /api/v1.1/targetsHost: <servername>
```

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "children": \["zon\_1256", "zon\_1257"\],        "enabled": true,        "id": "zon\_1258",        "niceName": "Zone for first floor",        "sources": \[            {                "id": "dev\_src\_15",                "name": "Line-In"            }        \],        "status": "unmanaged",        "type": "physicalZone"    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `children=<string>` | `["zon_1256","zon_1257"` |  | The immediate children of the target. Physical zones: A zone one level deeper in the hierarchy of physical zones. Destinations: A physical zone set as the target for the destination. |
| `enabled=<boolean>` |  | `true` `false` | Indicates if a target should play audio. All mapped sources will be stopped for a destination, but other audio can still play in the destination’s targets. |
| `id=<string>` | `zon_1258` |  | A unique target id. For device targets it is the ID of the sink. |
| `niceName=<string>` | _Zone for the first floor_ |  | The target nice name. |
| `sources=<string>` |  |  | The device list for sources available on a device such as Line-in. This part is only applicable for targets of the device type. |
| _TargetSource_ |  |  |  |
| `id=<string>` | `dev_src_15` |  | A unique device source ID. |
| `name=<string>` | _Line-in_ |  | The name of the source ID. |
| `status=<string>` | `unmanaged` | `unmanaged` `online` `offline` `playing` `error: NO_LICENCE` `error: FACTORY_DEFAULTS` `error: UNAUTHORIZED` `error: UNSUPPORTED_HOST_FW` `error: UNSUPPORTED_TRANSPORT` | The status attribute is available only for end devices. Child objects on devices will be empty. |
| `type=<string>` | `physicalZone` | `physicalZone` `site` `device` `destination` | The target type. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [500 Internal server error](#500-internal-server-error)

### Retrieve a specific target

This method should be used when you want to retrieve a specific target.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/targets/<target id>"
```

```bash
GET /api/v1.1/targets/<target id>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `<target id>` | A unique target ID. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "children": \["zon\_1256", "zon\_1257"\],        "enabled": true,        "id": "zon\_1258",        "niceName": "Zone for first floor",        "sources": \[            {                "id": "dev\_src\_15",                "name": "Line-In"            }        \],        "status": "unmanaged",        "type": "physicalZone"    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `children=<string>` | `["zon_1256", "zon_1257"` |  | The immediate children of the target. Physical zones: A zone one level deeper in the hierarchy of physical zones. Destinations: A physical zone set as the target for the destination. |
| `enabled=<boolean>` |  | `true` `false` | Indicates if a target should play audio. All mapped sources will be stopped for a destination, but other audio can still play in the destination’s targets. |
| `id=<string>` | `zon_1258` |  | A unique target id. For device targets it is the ID of the sink. |
| `niceName=<string>` | _Zone for the first floor_ |  | The target nice name. |
| `sources=<string>` |  |  | The device list for sources available on a device such as Line-in. This part is only applicable for targets of the device type. |
| _TargetSource_ |  |  |  |
| `id=<string>` | `dev_src_15` |  | A unique device source ID. |
| `name=<string>` | _Line-in_ |  | The name of the source ID. |
| `status=<string>` | `unmanaged` | `unmanaged` `online` `offline` `playing` `error: NO_LICENCE` `error: FACTORY_DEFAULTS` `error: UNAUTHORIZED` `error: UNSUPPORTED_HOST_FW` `error: UNSUPPORTED_TRANSPORT` | The status attribute is available only for end devices. Child objects on devices will be empty. |
| `type=<string>` | `physicalZone` | `physicalZone` `site` `device` `destination` | The target type. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Modify a specific target

This method should be used when you want to modify the settings or properties of a specific target.

**Request**

-   **Method**: `PATCH`
-   **Content-Type**: `application/json`

-   curl
-   HTTP

```bash
curl --request PUT \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/targets/<targetId>" \\  --data '{    "enabled": true}'
```

```bash
PUT /api/v1.1/targets/<targetId>Host: <servername>Content-Type: application/json{    "enabled": true}
```

| Parameter | Description |
| --- | --- |
| `targetId=<string>` | A unique target ID. |

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `enabled=<boolean>` | `true` | `true` `false` | Indicates if the target should play audio. All mapped sources will be stopped for a destination, but other audio clips can still be played in the destination’s target. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

## Audio files
### List audio files

This method should be used when you want to list all audio files available on the site. These files are found in the announcement and music library.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioFiles"
```

```bash
GET /api/v1.1/audioFilesHost: <servername>
```

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "id": 156,        "length": 35.613,        "library": "Announcement",        "name": "Closing announcement.mp3",        "path": "/Closing/"    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `id=<string>` | 156 |  | A unique audio file ID. |
| `length=<number>` | 35.613 |  | The length of the audio file (in seconds). |
| `library=<string>` | Announcement |  | The library containing the audio file. |
| `name=<string>` | Closing announcement.mp3 |  | A file name or nicename of the audio file. |
| `path=<string>` _Optional_ | /Closing/ |  | Folder information of the audio file. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [500 Internal server error](#500-internal-server-error)

### Retrieve a specific audio file

This method should be used when you want to retrieve a specific audio file available on the site.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/audioFiles/<audio file id>"
```

```bash
GET /api/v1.1/audioFiles/<audio file id>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `<audio file id>=<string>` | The ID of the audio file that will be retrieved. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "id": 156,        "length": 35.613,        "library": "Announcement",        "name": "Closing announcement.mp3",        "path": "/Closing/"    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `id=<string>` | 156 |  | A unique audio file ID. |
| `length=<number>` | 35.613 |  | The length of the audio file (in seconds). |
| `library=<string>` | Announcement |  | The library containing the audio file. |
| `name=<string>` | Closing announcement.mp3 |  | A file name or nicename of the audio file. |
| `path=<string>` _Optional_ | /Closing/ |  | Folder information of the audio file. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

## Volume controllers
### Get all volume controllers

This method should be used when you want to retrieve all available volume controllers. A volume controller can then be used to mute or adjust the audio volume.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/volumeControllers"
```

```bash
GET /api/v1.1/volumeControllersHost: <servername>
```

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "allowMute": true,        "contentClasses": \[            {                "id": "156",                "niceName": "Music"            }        \],        "id": "157",        "maxNegativeVolumeOffset": -80,        "maxPositiveVolumeOffset": 80,        "muted": true,        "niceName": "Music in kitchen",        "targets": \["zon\_1", "dev\_15"\],        "volumeOffset": -5.33    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `allowMute=<boolean>` |  |  | Controls whether the volume controller can be muted. |
| `contentClasses=<array>` |  |  | Contains the target content classes. |
| _VolumeControllerContentClass_ |  |  |  |
| `id=<string>` | 156 |  | A unique content class ID. |
| `niceName=<string>` | Music |  | Name of the content class. |
| `id=<string>` | 157 |  | A unique volume controller ID. |
| `maxNegativeVolumeOffset=<integer>` | \-80 | maximum: 100 minimum: -100 | The minimum allowed value of the volume controller. |
| `maxPositiveVolumeOffset=<integer>` | 80 | maximum: 100 minimum: -100 | The maximum allowed value of the volume controller. |
| `muted=<boolean>` |  |  | Controls if the volume controller is muted. |
| `niceName=<string>` | _Music in kitchen_ |  | The name of the volume controller. |
| `targets=<string>` | `["zon_1", "dev_15"` |  | The targets of the volume controller. |
| `volumeOffset=<number>` | \-5.33 | maximum: 100 minimum: -100 | The current volume offset, with ranges between \[-100, +100\]. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [500 Internal server error](#500-internal-server-error)

### Get a specific volume controller

This method should be used when you want to retrieve a specific volume controller.

**Request**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/api/v1.1/volumeControllers/<volume controller id>"
```

```bash
GET /api/v1.1/volumeControllers/<volume controller id>Host: <servername>
```

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

Response body example

```bash
\[    {        "allowMute": true,        "contentClasses": \[            {                "id": "156",                "niceName": "Music"            }        \],        "id": "157",        "maxNegativeVolumeOffset": -80,        "maxPositiveVolumeOffset": 80,        "muted": true,        "niceName": "Music in kitchen",        "targets": \["zon\_1", "dev\_15"\],        "volumeOffset": -5.33    }\]
```

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `allowMute=<boolean>` |  |  | Controls whether the volume controller can be muted. |
| `contentClasses=<array>` |  |  | Contains the target content classes. |
| _VolumeControllerContentClass_ |  |  |  |
| `id=<string>` | 156 |  | A unique content class ID. |
| `niceName=<string>` | Music |  | Name of the content class. |
| `id=<string>` | 157 |  | A unique volume controller ID. |
| `maxNegativeVolumeOffset=<integer>` | \-80 | maximum: 100 minimum: -100 | The minimum allowed value of the volume controller. |
| `maxPositiveVolumeOffset=<integer>` | 80 | maximum: 100 minimum: -100 | The maximum allowed value of the volume controller. |
| `muted=<boolean>` |  |  | Controls if the volume controller is muted. |
| `niceName=<string>` | _Music in kitchen_ |  | The name of the volume controller. |
| `targets=<string>` | `["zon_1", "dev_15"` |  | The targets of the volume controller. |
| `volumeOffset=<number>` | \-5.33 | maximum: 100 minimum: -100 | The current volume offset, with ranges between \[-100, +100\]. |

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [500 Internal server error](#500-internal-server-error)

### Modify a specific volume controller

This method should be used when you want to modify a volume controller.

**Request**

-   **Method**: `PATCH`
-   **Content-Type**: `application/json`

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/volumeControllers/<volume controller id>" \\  --data '{    "muted": false,    "volumeOffset": -5.33}'
```

```bash
PATCH /api/v1.1/volumeControllers/<volume controller id>Host: <servername>Content-Type: application/json{    "muted": false,    "volumeOffset": -5.33}
```

| Parameter | Description |
| --- | --- |
| `<volume controller id>=<string>` | A unique target ID. |

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `muted=<boolean>` | `true` | `true` `false` (default) | Mutes all audio of the content types and targets that the volume controller controls. |
| `volumeOffset=<number>` | \-5.33 | maximum: 100 minimum: -100 | The current volume offset, with ranges between \[-100, +100\]. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [500 Internal server error](#500-internal-server-error)

### Modify offset volume of a volume controller

This method should be used when you want to make a volume change relative to the current volume.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/volumeControllers/<volumeControllerId>/offsetVolume" \\  --data '{    "volumeOffset": 10}'
```

```bash
POST /api/v1.1/volumeControllers/<volumeControllerId>/offsetVolumeHost: <servername>Content-Type: application/json{    "volumeOffset": 10}
```

| Parameter | Description |
| --- | --- |
| `volumeControllerId=<string>` | A unique target ID. |

| Parameter | Example value | Valid values | Description |
| --- | --- | --- | --- |
| `volumeOffset=<number>` | \-5.33 | maximum: 100 minimum: -100 | The requested volume change in relation to the previous value. A negative value will lower the volume. The resulting value will be in the range `[-100, +100]` or the configured max/min offset of the volume controller. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [422 Change not allowed](#422-change-not-allowed)
-   [500 Internal server error](#500-internal-server-error)

### Modify the mute state of a volume controller

This method should be used when you want to switch between mute/unmute states of a target.

**Request**

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/api/v1.1/volumeControllers/<volumeControllerId>/toggleMute"
```

```bash
POST /api/v1.1/volumeControllers/<volumeControllerId>/toggleMuteHost: <servername>Content-Type: application/json
```

| Parameter | Description |
| --- | --- |
| `volumeControllerId=<string>` | A unique target ID. |

**Successful response**

-   **HTTP Code**: 200 Operation successful
-   **Content-Type**: `application/json`

**Error responses**

-   [401 Unauthorized](#401-unauthorized)
-   [404 Not found](#404-not-found)
-   [422 Change not allowed](#422-change-not-allowed)
-   [500 Internal server error](#500-internal-server-error)

## General error responses

The following error responses can occur for any request independent of their type.

### 400 Invalid parameters

-   **HTTP Code**: 400 Invalid parameters
-   **Content-Type**: `application/json`

Response body example

```bash
{    "error": {        "code": 400,        "errors": \[            {                "location": "string",                "locationType": "DATA\_FIELD",                "message": "string",                "reason": "string"            }        \],        "id": "f1a02d76-9b83-437e-8cb4-21016465ea43",        "message": "Unknown priority 'HIGHER'",        "messageKey": "string",        "messageParams": \["string"\]    }}
```

| Parameter | Valid Values | Description |
| --- | --- | --- |
| `error` |  | Container for the error data. |
| _Error data_ |  |  |
| `code=<integer>` |  | The error code. |
| `errors=<object>` |  | Container for detailed error information. Each element in the array represents a different error and several errors can be returned with a single request. |
| _DetailedErrorData_ |  |  |
| `location=<string>` |  | The location of the error (interpretation of its value depends on `locationType`). |
| `locationType=<string>` | `"DATA_FIELD"` `"HEADER"` `"PARAMETER"` | Indicates how the location property should be interpreted. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `reason=<string>` |  | Unique identifier for this error. |
| `id=<string>` |  | A unique identifier for the request. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `messageKey` |  | The key of the error message. Defined by a properties list. |
| `messageParams` |  | Error related parameters sent in request. |

### 401 Unauthorized

-   **HTTP Code**: 401 Unauthorized
-   **Content-Type**: `application/json`

Response body example

```bash
{    "error": {        "code": 401,        "errors": \[            {                "location": "string",                "locationType": "DATA\_FIELD",                "message": "string",                "reason": "string"            }        \],        "id": "f1a02d76-9b83-437e-8cb4-21016465ea43",        "message": "Unknown priority 'HIGHER'",        "messageKey": "string",        "messageParams": \["string"\]    }}
```

| Parameter | Valid Values | Description |
| --- | --- | --- |
| `error` |  | Container for the error data. |
| _Error data_ |  |  |
| `code=<integer>` |  | The error code. |
| `errors=<object>` |  | Container for detailed error information. Each element in the array represents a different error and several errors can be returned with a single request. |
| _DetailedErrorData_ |  |  |
| `location=<string>` |  | The location of the error (interpretation of its value depends on `locationType`). |
| `locationType=<string>` | `"DATA_FIELD"` `"HEADER"` `"PARAMETER"` | Indicates how the location property should be interpreted. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `reason=<string>` |  | Unique identifier for this error. |
| `id=<string>` |  | A unique identifier for the request. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `messageKey` |  | The key of the error message. Defined by a properties list. |
| `messageParams` |  | Error related parameters sent in request. |

### 404 Not found

-   **HTTP Code**: 404 Not found
-   **Content-Type**: `application/json`

Response body example

```bash
{    "error": {        "code": 404,        "errors": \[            {                "location": "string",                "locationType": "DATA\_FIELD",                "message": "string",                "reason": "string"            }        \],        "id": "f1a02d76-9b83-437e-8cb4-21016465ea43",        "message": "Unknown priority 'HIGHER'",        "messageKey": "string",        "messageParams": \["string"\]    }}
```

| Parameter | Valid Values | Description |
| --- | --- | --- |
| `error` |  | Container for the error data. |
| _Error data_ |  |  |
| `code=<integer>` |  | The error code. |
| `errors=<object>` |  | Container for detailed error information. Each element in the array represents a different error and several errors can be returned with a single request. |
| _DetailedErrorData_ |  |  |
| `location=<string>` |  | The location of the error (interpretation of its value depends on `locationType`). |
| `locationType=<string>` | `"DATA_FIELD"` `"HEADER"` `"PARAMETER"` | Indicates how the location property should be interpreted. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `reason=<string>` |  | Unique identifier for this error. |
| `id=<string>` |  | A unique identifier for the request. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `messageKey` |  | The key of the error message. Defined by a properties list. |
| `messageParams` |  | Error related parameters sent in request. |

### 422 Change not allowed

-   **HTTP Code**: 422 Change not allowed
-   **Content-Type**: `application/json`

Response body example

```bash
{    "error": {        "code": 422,        "errors": \[            {                "location": "string",                "locationType": "DATA\_FIELD",                "message": "string",                "reason": "string"            }        \],        "id": "f1a02d76-9b83-437e-8cb4-21016465ea43",        "message": "Unknown priority 'HIGHER'",        "messageKey": "string",        "messageParams": \["string"\]    }}
```

| Parameter | Valid Values | Description |
| --- | --- | --- |
| `error` |  | Container for the error data. |
| _Error data_ |  |  |
| `code=<integer>` |  | The error code. |
| `errors=<object>` |  | Container for detailed error information. Each element in the array represents a different error and several errors can be returned with a single request. |
| _DetailedErrorData_ |  |  |
| `location=<string>` |  | The location of the error (interpretation of its value depends on `locationType`). |
| `locationType=<string>` | `"DATA_FIELD"` `"HEADER"` `"PARAMETER"` | Indicates how the location property should be interpreted. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `reason=<string>` |  | Unique identifier for this error. |
| `id=<string>` |  | A unique identifier for the request. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `messageKey` |  | The key of the error message. Defined by a properties list. |
| `messageParams` |  | Error related parameters sent in request. |

### 500 Internal server error

-   **HTTP Code**: 500 Internal server error
-   **Content-Type**: `application/json`

Response body example

```bash
{    "error": {        "code": 500,        "errors": \[            {                "location": "string",                "locationType": "DATA\_FIELD",                "message": "string",                "reason": "string"            }        \],        "id": "f1a02d76-9b83-437e-8cb4-21016465ea43",        "message": "Unknown priority 'HIGHER'",        "messageKey": "string",        "messageParams": \["string"\]    }}
```

| Parameter | Valid Values | Description |
| --- | --- | --- |
| `error` |  | Container for the error data. |
| _Error data_ |  |  |
| `code=<integer>` |  | The error code. |
| `errors=<object>` |  | Container for detailed error information. Each element in the array represents a different error and several errors can be returned with a single request. |
| _DetailedErrorData_ |  |  |
| `location=<string>` |  | The location of the error (interpretation of its value depends on `locationType`). |
| `locationType=<string>` | `"DATA_FIELD"` `"HEADER"` `"PARAMETER"` | Indicates how the location property should be interpreted. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `reason=<string>` |  | Unique identifier for this error. |
| `id=<string>` |  | A unique identifier for the request. |
| `message=<string>` |  | A human readable text providing more details about the error. |
| `messageKey` |  | The key of the error message. Defined by a properties list. |
| `messageParams` |  | Error related parameters sent in request. |

## Websockets

Websockets will ensure that clients are promptly informed about server-side changes in AXIS Audio Manager Pro. For example, a client will be notified if the volume is changed or when a device starts to play. For detailed integration guidance, refer to STOMP protocol specifications (v 1.0, 1.1 or 1.2 are supported).

Endpoints

```bash
wss://<servername>/api/v1.1/notifications
```

Topics

```bash
/topic/audiofiles/topic/audioSessions/topic/targets/topic/volumeControllers
```