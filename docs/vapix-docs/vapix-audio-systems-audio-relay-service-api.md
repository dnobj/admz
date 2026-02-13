---
title: Audio relay service API
url: "https://developer.axis.com/vapix/audio-systems/audio-relay-service-api/"
category: vapix
subcategory: audio-systems
sha256: 1b0b72f8bac94535ec0372023453364a89bbed3a1044ebdee922d0f9fba81ffb
scraped_at: "2026-01-09T15:18:25.262Z"
page_height: 27495
---

# Audio relay service API

## Description

The Audio Relay service provides configuration mechanisms for connecting audio peers to each other. An audio relay network can be altered by adding and removing audio peers. Status monitoring of the audio peers is provided.

An audio relay network is based on one audio peer being a leader, and the rest of the peers being followers. The audio content intended for the audio relay network shall be provided by the leader, which will stream the audio content to its followers.

The Audio Relay service also provides sound configuration, for adjusting the master volume of an audio relay network. The audio peers' output gain is also provided via the audio peer configuration. The master volume applies to all peers in the audio relay network, while output gain is separate for each audio peer.

info

Please note that this API has been deprecated as of AXIS OS version 10.12 and will no longer receive any updates.

### Identification

Audio Relay Service API is available if:

-   **Property**: `Properties.API.AudioRelay.Version="1.2"` or later.

### Terminology and abbreviations

| Term | Description |
| --- | --- |
| Non-normative `Enum` | `Enum` whose values are used as strings to enable future extensions. |

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

This section will show common use cases for this service. General concepts are discussed, and details are provided in the detailed specification.

Most examples use pseudocode to illustrate the intended flow of requests to the Audio Relay service and data will be shown in JavaScript Object Notation (JSON).

API calls can be encoded in either JSON format or in a key-value format referred to as "simple", which flattens out a structure to `key=value` strings, where each level in a structure is separated by underscore `('_')` when encoding the key.

Boolean values are encoded as true or false, and the NULL value is encoded as null.

String values are URL-encoded and may start and end with quotation marks, e.g. `"a+string%0A"`.

Character sets are not converted or validated by the service, but UTF-8 is recommended.

### Simple cURL examples

The below shows examples of how to set and get audio peers via cURL. The set operation shows the possibility of using both IP address and MAC address to identify the peers. The example also illustrates how a list of elements will be represented.

cURL JSON request for SetAudioPeerConfigurations

```bash
$ curl --anyauth -s "http://root:pass@192.168.0.90/vapix/audiorelay" \\   -d '{"axar:SetAudioPeerConfigurations": {"Configuration": \[      {"Id":"1",       "Address": {"IPAddress":"192.168.0.90"},       "Leader":true},      {"Id":"2",       "Address": {"MAC": "00:40:8C:18:00:01"},       "Leader":false} \]}}'> {>   "AudioPeerId":>     \[>       "1",>       "2">     \]> }
```

cURL simple request for SetAudioPeerConfigurations

```bash
$ curl --anyauth -s "http://root:pass@192.168.0.90/vapix/audiorelay? ...  format=simple&action=axar:SetAudioPeerConfigurations& ...  Configuration\_0\_Id=1&Configuration\_0\_Address\_IPAddress=192.168.0.1&Configuration\_0\_Leader=true& ...  Configuration\_1\_Id=2&Configuration\_1\_Address\_MAC=00:40:8C:18:00:00&Configuration\_1\_Leader=false"> AudioPeerId\_0="1"> AudioPeerId\_1="2"
```

cURL JSON request for GetAudioPeers

```bash
$ curl --anyauth -s "http://root:pass@192.168.0.90/vapix/audiorelay" -d '{"axar:GetAudioPeers":{}}'> {>   "Peer":>     \[>       {>         "Configuration": {>           "Id": "1",>           "Address": {>             "IPAddress": "192.168.0.90",>             "MAC": "00:40:8C:18:00:00">           },>           "Leader": true,>           "Credentials": {>             "User": "root",>             "Password": null>           },>           "OutputGain":>             \[>               {>                 "Name": "AudioSource.A0.OutputGain",>                 "Value": "0">               }>             \]>         },>         "MetaData": {>           "Type": "C2005">         },>         "ConnectionStatus": "Online",>         "OutputGainDefinitions":>           \[>             {>               "Name": "AudioSource.A0.OutputGain",>               "Range":>                 \[>                   "Mute",>                   "-57",>                   ... ,>                   "6">                 \]>             }>           \]>       },>       {>         "Configuration": {>           "Id": "2",>           "Address": {>             "IPAddress": "192.168.0.91",>             "MAC": "00:40:8C:18:00:01">           },>           "Leader": false,>           "Credentials": {>             "User": "root",>             "Password": null>           },>           "OutputGain":>             \[>               {>                 "Name": "AudioSource.A0.OutputGain",>                 "Value": "0">               }>             \]>         },>         "MetaData": {>           "Type": "C1004-E">         },>         "ConnectionStatus": "Online",>         "OutputGainDefinitions":>           \[>             {>               "Name": "AudioSource.A0.OutputGain",>               "Range":>                 \[>                   "Mute",>                   "-57",>                   ... ,>                   "6">                 \]>             }>           \]>       }>     \]> }
```

cURL simple Request for GetAudioPeers

```bash
$ curl --anyauth -s "http://root:pass@192.168.0.90/vapix/audiorelay? ...  format=simple&action=axar:GetAudioPeers"> Peer\_0\_Configuration\_Id="2"> Peer\_0\_Configuration\_Address\_IPAddress="192.168.0.91"> Peer\_0\_Configuration\_Address\_MAC="00:40:8C:18:00:01"> Peer\_0\_Configuration\_Leader=false> Peer\_0\_Configuration\_Credentials\_User="root"> Peer\_0\_Configuration\_Credentials\_Password=null> Peer\_0\_Configuration\_OutputGain\_0\_Name="AudioSource.A0.OutputGain"> Peer\_0\_Configuration\_OutputGain\_0\_Value="0"> Peer\_0\_MetaData\_Type="C1004-E"> Peer\_0\_ConnectionStatus="Online"> Peer\_0\_OutputGainDefinitions\_0\_Name="AudioSource.A0.OutputGain"> Peer\_0\_OutputGainDefinitions\_0\_Range\_0="Mute"> Peer\_0\_OutputGainDefinitions\_0\_Range\_1="-57"> ...> Peer\_0\_OutputGainDefinitions\_0\_Range\_64="6"> Peer\_1\_Configuration\_Id="1"> Peer\_1\_Configuration\_Address\_IPAddress="192.168.0.90"> Peer\_1\_Configuration\_Address\_MAC="00:40:8C:18:00:00"> Peer\_1\_Configuration\_Leader=true> Peer\_1\_Configuration\_Credentials\_User="root"> Peer\_1\_Configuration\_Credentials\_Password=null> Peer\_1\_Configuration\_OutputGain\_0\_Name="AudioSource.A0.OutputGain"> Peer\_1\_Configuration\_OutputGain\_0\_Value="0"> Peer\_1\_MetaData\_Type="C2005"> Peer\_1\_ConnectionStatus="Online"> Peer\_1\_OutputGainDefinitions\_0\_Name="AudioSource.A0.OutputGain"> Peer\_1\_OutputGainDefinitions\_0\_Range\_0="Mute"> Peer\_1\_OutputGainDefinitions\_0\_Range\_1="-57"> ...> Peer\_1\_OutputGainDefinitions\_0\_Range\_64="6"
```

### Add audio peer

Use `axar:SetAudioPeerConfiguration` to add a new audio peer to the existing audio relay network. The example shows how to add a new follower called "lobby speaker left" with IP. The audio peer may be retrieved by `axar:GetDiscoveredPeers` prior to adding it.

Request to add audio peer using JSON format

```bash
{    "axar:SetAudioPeerConfiguration": {        "Configuration": {            "Name": "lobby speaker left",            "Address": {                "IPAddress": "192.168.0.92"            }        }    }}
```

Response

```bash
{    "AudioPeerId": "AudioPeer\_03"}
```

Request to add audio peer using simple format

```bash
format=simple&action=axar:SetAudioPeerConfiguration& ...Configuration\_Name=lobby%20speaker%20left&Configuration\_Address\_IPAddress=192.168.0.92
```

Response

```bash
AudioPeerId="AudioPeer\_03"
```

The `AudioPeerId` in the response is generated in this example. It may be set by the client by providing it in the request. The difference between `axar:SetAudioPeerConfiguration` and `axar:SetAudioPeers` is that the latter would reset the current audio relay network and set the configuration as provided in the parameters.

### Remove audio peer

Use `axar:RemoveAudioPeer` to remove an audio peer from the audio relay network.

Request to remove audio peer using JSON format

```bash
{    "axar:RemoveAudioPeer": {        "AudioPeerId": "AudioPeer\_03"    }}
```

Response

```bash
{}
```

Request to remove audio peer using simple format

```bash
format=simple&action=axar:RemoveAudioPeer&AudioPeerId=AudioPeer03
```

Response

```bash

```
### Rename audio peer and change its output gain

Use `axar:SetAudioPeerConfiguration` to modify an audio peer. This example shows how two values are changed at the same time.

Current audio peer configuration

```bash
{    "Configuration": {        "Id": "AudioPeer\_01",        "Name": "SpeakerX",        "Address": {            "IPAddress": "192.168.0.90",            "MAC": "00:40:8C:18:00:00"        },        "Leader": true,        "Credentials": {            "User": "root",            "Password": null        },        "OutputGain": \[            {                "Name": "AudioSource.A0.OutputGain",                "Value": "0"            }        \]    }}
```

Request to modify audio peer using JSON format

```bash
{    "axar:SetAudioPeerConfiguration": {        "Configuration": {            "Id": "AudioPeer\_01",            "Name": "lobby speaker left",            "OutputGain": \[                {                    "Name": "AudioSource.A0.OutputGain",                    "Value": "-6"                }            \],            "Address": {}        }    }}
```

Response

```bash
{    "AudioPeerId": "AudioPeer\_01"}
```

Request to modify audio peer using simple format

```bash
format=simple&action=axar:SetAudioPeerConfiguration& ...Configuration\_Id=AudioPeer\_01&Configuration\_Name=lobby%20speaker%20left& ...Configuration\_OutputGain\_0\_Name=AudioSource.A0.OutputGain& ...Configuration\_OutputGain\_0\_Value=-6
```

Response

```bash
AudioPeerId="AudioPeer\_01"
```

### Setup audio relay network using multicast

Use `axar:SetAudioPeers` to setup a new audio relay network. This also gives the opportunity to configure usage of multicast stream instead of unicast between the peers. This example show how to set up multicast with two peers and the device to generate the multicast group.

Request to set audio peers using JSON format

```bash
{    "axar:SetAudioPeerConfigurations": {        "Configuration": \[            {                "Id": "1",                "Address": {                    "IPAddress": "192.168.0.90"                },                "Leader": true            },            {                "Id": "2",                "Address": {                    "IPAddress": "192.168.0.91"                }            }        \],        "AudioNetworkConfiguration": {            "MulticastEnabled": true        }    }}
```

Response

```bash
{    "AudioPeerId": \["1", "2"\]}
```

Request to set audio peers using simple format

```bash
format=simple&action=axar:SetAudioPeerConfigurations& ...  Configuration\_0\_Id=1&Configuration\_0\_Address\_IPAddress=192.168.0.90&Configuration\_0\_Leader=true& ...  Configuration\_1\_Id=2&Configuration\_0\_Address\_IPAddress=192.168.0.91& ...  AudioNetworkConfiguration\_MulticastEnabled=true"
```

Response

```bash
AudioPeerId\_0="1"AudioPeerId\_1="2"
```

The generated multicast group can be retrieved via `axar:GetAudioPeers`.

### Change multicast settings in existing audio relay network

Use `axar:SetAudioNetworkConfiguration` to setup a uni- or multicast stream in the audio relay network. The call to the leader comes with the ability to change the setting without the need of re-transmitting all existing peers.

If the multicast group isn’t specified, the one that is generated will be returned upon a successful request.

Request to enable multicast using the JSON format

```bash
{    "axar:SetAudioNetworkConfiguration": {        "AudioNetworkConfiguration": {            "MulticastEnabled": true        }    }}
```

Response

```bash
{    "MulticastGroup": "239.168.0.90"}
```

Request to enable multicast using a simple format

```bash
format=simple&action=axar:"SetAudioNetworkConfiguration&AudioNetworkConfiguration\_MulticastEnabled=true"
```

Response

```bash
"MulticastGroup": "239.168.0.90"
```

### Adjust the master volume

Use `axar:SetSoundConfiguration` to adjust the master volume of the audio relay network, i.e the common volume level for all audio peers. Prior to setting the master volume, its boundaries should be retrieved by calling `axar:GetServiceCapabilities`.

Request to modify sound configuration using JSON format

```bash
{    "axar:SetSoundConfiguration": {        "Configuration": {            "MasterVolume": 0,            "MasterVolumeUnit": "dB"        }    }}
```

Response

```bash
{}
```

Request to modify sound configuration using simple format

```bash
format=simple&action=axar:SetSoundConfiguration& ...Configuration\_MasterVolume=0&Configuration\_MasterVolumeUnit="dB"
```

Response

```bash

```
### Monitor audio relay peers status

Use `axar:GetAudioPeerStatus` to monitor the audio relay network. This example will show the status of each follower and their connection status to the leader, where the leader is `AudioPeer_01`.

Request to retrieve audio peer status using JSON format

```bash
{    "axar:GetAudioPeerStatus": {}}
```

Response

```bash
{    "PeerStatus": \[        {            "Id": "AudioPeer\_02",            "ConnectionStatus": "Offline"        },        {            "Id": "AudioPeer\_01",            "ConnectionStatus": "Online"        }    \]}
```

Request to retrieve audio peer status using simple format

```bash
format=simple&action=axar:GetAudioPeerStatus
```

Response

```bash
PeerStatus\_0\_Id="AudioPeer\_02"PeerStatus\_0\_ConnectionStatus="Offline"PeerStatus\_1\_Id="AudioPeer\_01"PeerStatus\_1\_ConnectionStatus="Online"
```

## API specification
### Common data types
#### AudioPeerId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `AudioPeerId` | String | minLength=0 maxLength=64 | Identifier of an Audio peer. |

#### Enumeration: AudioPeerConnectionStatus

Non-normative enum of connection status. This may be extended in the future.

The following values are available:

| Common Data Types | Description |
| --- | --- |
| `Initiating` | Initial state. |
| `Offline` | Cannot establish a connection to Audio Peer. |
| `Online` | Connection established to Audio Peer. |
| `AuthenticationFailed` | Cannot connect due to invalid credentials. |
| `InOtherPeerNetwork` | Audio Peer already allocated to other Audio Peer Network. |

## Service capabilities

The `GetServices` call can be used to retrieve the capabilities of the service, to handle future extensions.

**Range**

Describes a range of valid values and the unit. The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Unit` | String | The unit of the value (e.g. dB). |
| `MaxValue` | int | The maximum value of the range. |
| `MinValue` | int | The minimum value of the range. |

**ServiceCapabilities**

The structure of ServiceCapabilities reflects the optional functionality of a service. The information is static and does not change during device operation. The following capabilities are available:

| Field | Type | Description |
| --- | --- | --- |
| `MasterVolumeRanges` | Range | Master volume ranges as supported by this service. |

**GetServiceCapabilities command**

This operation returns the capabilities of the service.

Request

```bash
{}
```

The request is empty.

Response

```bash
{  "Capabilities": {    <ServiceCapabilities>  }}
```

| Parameter | Description |
| --- | --- |
| `Capabilities` | The capability response message contains the requested AudioRelay service capabilities. |

## Audio relay network configuration

**AudioPeerCredentials**

The credentials for accessing an audio peer at the time of setup. The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `User` | String | The user account name. |
| `Password` | String | The un-encrypted password. |

**AudioPeerAddress**

The address of an audio peer. The following fields are available and each is optional:

| Field | Type | Description |
| --- | --- | --- |
| `IPAddress` | String | The IP address. |
| `MAC` | String | The MAC address in the form 00:00:00:00:00:00. |

**Gain definition**

A definition for the gain controls of a device.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The name of the gain to set e.g. `AudioSource.A0.OutputGain` |
| `Range` | String | The valid gain values, as retrieved from `/axis-cgi/param.cgi` with `action=listdefinitions`. |

**AudioPeerMetaData**

Metadata information for an audio peer.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Type` | String | The product type. |

**Gain**

A gain control for a device.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The name of the gain to set e.g. `AudioSource.A0.OutputGain` |
| `Value` | String | The gain value. Must be valid according to the gain definition range. |

**AudioPeerConfiguration**

The configuration of a peer in the audio relay network.

the IP address or the MAC address is used to identify a peer. If the MAC address is given, it will be matched against discovered peers. The IP Address will be ignored if the MAC address is found via discovery, and a discovered IP address takes precedence over any current IP address.

If only the IP address is given (MAC is left empty), then a connection to this specific IP address will be used. Once a connection is established, the MAC address will be known and used in the configuration.

Credentials must be supplied when setting the audio peer configurations, if the devices are not accessible using default credentials. The supplied credential password will never be returned to a client upon a `GetAudioPeers-call`.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Address` | AudioPeerAddress | The audio peer network address. |
| `OutPutGain` | Gain | Optional output gain for the audio peer as described via its parameters retrieved by `/axis-cgi/param.cgi`. |

The following fields are optional:

| Field | Type | Description |
| --- | --- | --- |
| `Id` | AudioPeerId | The audio peer id is a unique identifier for an audio peer within an audio peer network. It is generated by the device if empty or missing. |
| `Name` | String | A descriptive name for the audio peer. |
| `Leader` | Boolean | Set if this peer is the leader. Recognized as false if not provided at creation, and as unchanged when modifying an existing configuration. |
| `Credentials` | AudioPeerCredentials | Optional credential information. If not available, default credentials will be assumed. |

**AudioPeer**

The Audio peer information of a peer in the audio relay network.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Configuration` | AudioPeerConfiguration | The audio peer configuration. |
| `MetaData` | AudioPeerMetaData | The audio peer metadata information. |
| `ConnectionStatus` | String | The status as described by axar:AudioPeerConnectionStatus. |
| `OutputGainDefinitions` | GainDefinition | The gain definitions. |

**DiscoveredAudioPeer**

The audio peer information as discovered on the current network.

The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Address` | AudioPeerAddress | The audio peer network address. |
| `MetaData` | AudioPeetMetaData | Metadata information of the audio peer. |

**AudioNetworkConfiguration**

The configuration of parameters affecting the audio relay network as an entity.

The following fields are available but optional:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | A descriptive name for the audio relay network. |
| `Description` | String | A description of the audio relay network. |
| `MulticastEnabled` | Boolean | Specifies if unicast or multicast shall be used. |
| `MulticastGroup` | String | Multicast group address. |

**SetAudioPeerConfigurations command**

Requests that a list of audio peers shall be set as the Audio Relay network.

The list of audio peer configurations must not contain more than one peer set as leader. The list must also always contain the address of the device that receives this request. The request will fail if these rules are violated.

This call replaces all of the existing AudioPeerConfigurations on the receiving device with the content of the Configuration parameter.

The optional parameter AudioNetworkConfiguration contain two members. MulticastEnabled may be set to true or false in order to enable/disable multicast support for the audio network. If this parameter is not set, unicast will be used. MulticastGroup may be set to a desired multicast group. If the parameter is not set, a default multicast group will be used.

Request

```bash
{  "Configuration": \[{    "AudioPeerConfiguration"  },  ...  \]}
```

| Parameter | Description |
| --- | --- |
| `Configuration` | AudioPeerConfiguration(s) to set. |

Response

```bash
{    "AudioPeerId": "<AudioPeerId>"}
```

| Parameter | Description |
| --- | --- |
| `AudioPeerId` | The IDs of the items provided. |

**SetAudioPeerConfiguration command**

Requests that an audio peer be added or modified in the Audio Relay network.

The new AudioPeerConfiguration must not modify the Audio Relay network so that it would have more or less than one peer set as the leader.

The new AudioPeerConfiguration may have the ID field set or empty. If not set, or set to a non-existing ID, the call will be considered an 'add operation' of a new AudioPeerConfiguration. If set to an existing ID, the call will be considered to be a modify operation for an existing AudioPeerConfiguration.

Request

```bash
{  "Configuration": {    <AudioPeerConfiguration>  }}
```

| Parameter | Description |
| --- | --- |
| `Configuration` | AudioPeerConfiguration(s) to set. |

Response

```bash
{    "AudioPeerId": "<AudioPeerId>"}
```

| Parameter | Description |
| --- | --- |
| `AudioPeerId` | The IDs of the items provided. |

**GetAudioPeers command**

Returns the current Audio Relay network configuration of the device that receives this request.

AudioPeerIds that cannot be resolved will be ignored and an empty set may be returned if there are no audio peers matching specified IDs.

If no `AudioPeerId` is supplied, a list of all audio peers will be returned.

Request

```bash
{  "AudioPeerId": \[    "<AudioPeerId>",  ...  \]}
```

| Parameter | Description |
| --- | --- |
| `AudioPeerId` | IDs of the audio peers to get. |

Response

```bash
{  "Peer": \[    {      "AudioPeer"    },    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `Peer` | The peers of the Audio Relay network. |

**GetDiscoveredAudioPeers command**

Returns the Audio Relay peers discovered by the device that receives this request. The returned list is a snapshot and Audio Relay peers may both be added and removed in subsequent requests.

Request

```bash
{}
```

The request is empty.

Response

```bash
{  "Peer": \[    {      "DiscoveredAudioPeer"    },    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `Peer` | The discovered Audio Relay peers. |

**RemoveAudioPeer command**

Removes an audio peer from the audio relay network. The ID must be for an audio peer other than the recipient of this request.

Request

```bash
{    "AudioPeerId": "<AudioPeerId>"}
```

| Parameter | Description |
| --- | --- |
| `AudioPeerId` | Id of audio peer to remove. |

Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | Supplied ID is invalid (invalid values). |

**SetAudioNetworkConfiguration command**

Modifies the audio network configuration for the Audio Relay Network.

The configuration for multicasting two parameters. MulticastEnabled may be set to "true" or "false" in order to enable/disable multicast support for the audio network, and if not set, unicast will be used. MulticastGroup may be set to a desired multicast group and if not set, a default multicast group will be generated.

Request

```bash
{  "AudioNetworkConfiguration": {    <AudioNetworkConfiguration>  }}
```

| Parameter | Description |
| --- | --- |
| `AudioNetworkConfiguration` | AudioNetworkConfiguration is set. |

Response

```bash
{  "MulticastGroup": "<string>" (optional)}
```

| Parameter | Description |
| --- | --- |
| `MulticastGroup` | Multicast group address if enabled. |

## Audio relay network monitoring

**AudioPeerStatus**

The Audio Peer status. The following fields are available:

| Field | Type | Description |
| --- | --- | --- |
| `Id` | AudioPeerId | The Audio Peer Id. |
| `ConnectionStatus` | String | The status as described by `axar:AudioPeerConnectionStatus`. |

**GetAudioPeerStatus command**

Returns the current status of the link between the leader and its followers in the configured Audio Peer network. It is the leader that tracks the status.

AudioPeerIds that cannot be resolved will be ignored and an empty set may be returned if there are no audio peers matching specified IDs.

If no AudioPeerIds are supplied, a list of all audio peers will be returned.

Request

```bash
{  "AudioPeerId": \[    "<AudioPeerId>",    ...  \]}
```

| Parameter | Description |
| --- | --- |
| `AudioPeerId` | IDs of audio peers to get. |

Response

```bash
{  "PeerStatus": \[{    "AudioPeerStatus"  },  ...  \]}
```

| Parameter | Description |
| --- | --- |
| `PeerStatus` | The status of the Audio Relay peers. |

## Audio relay network sound configuration

**SoundConfiguration**

The configuration of parameters affecting the sound in the audio relay network.

Valid parameter values may be defined by the service capabilities.

The following fields are available, and all are optional:

| Field | Type | Description |
| --- | --- | --- |
| `MasterVolume` | int | The master volume of the Audio Relay network. |
| `MasterVolumeUnit` | String | The unit of the master volume. Optional parameter to use if not default unit type is used. |
| `MasterVolumeMute` | Boolean | Mutes the master volume of the Audio Relay Network. |

**SetSoundConfiguration command**

Requests that a SoundConfiguration should be set on all the peers in the AudioPeerConfiguration.

All members of the SoundConfiguration are optional, thus a SoundConfiguration with all members empty will be accepted, but will change nothing.

Request

```bash
{  "Configuration": {    <SoundConfiguration>  }}
```

| Parameter | Description |
| --- | --- |
| `Configuration` | The SoundConfiguration to set. |

Response

```bash
{}
```

The response is empty.

**GetSoundConfiguration command**

Returns the SoundConfiguration of an Audio Relay network.

Request

```bash
{}
```

The request is empty.

Response

```bash
{  "Configuration": {    <SoundConfiguration>  }}
```

| Parameter | Description |
| --- | --- |
| `Configuration` | The returned SoundConfiguration. |