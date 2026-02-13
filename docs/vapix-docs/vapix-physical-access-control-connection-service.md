---
title: Connection service
url: "https://developer.axis.com/vapix/physical-access-control/connection-service/"
category: vapix
subcategory: physical-access-control
sha256: 0e38297d7e8ff49abb261a01e64eba74c4032ed36caad809c0f5f5db5e03307f
scraped_at: "2026-01-09T15:21:39.353Z"
page_height: 17951
---

# Connection service

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

info

The AXIS A1601 network door controller is not supported by this API.

## Connection service guide

Door controllers can be interconnected to create door controller networks. The connection service is used to add and remove door controllers to and from the network and to list all door controllers in the network.

The door controllers in a network share the same configuration. A client can connect to any door controller in the network in order to read and update the configuration for all door controllers in the network.

### Door controller network basics

A door controller network can consist of up to 33 door controllers. Door controllers that are part of the same network are.called peers.

In a door controller network, the configurations in the different door controller services are shared among the door controllers in the network. If a configuration is updated at one door controller, the change will be sent to all other door controllers in the network so that all door controllers have the same configuration. For example, if calling `axtdc:SetDoor` at one door controller, the `Door` will be distributed to all door controllers. The `Door` can then be used or retrieved by`axtdc:GetDoorList` at any door controller

To maintain configuration consistency across the network, a majority rule applies: A configuration update will only be applied if a majority of the door controllers in the network are connected and accept the request. As an example, consider a network with three door controllers. If two of the door controllers are offline and one is online, it is not possible to make a configuration update at the online door controller. The request will fail because of the majority rule. If, instead, two door controllers are online and one is offline, the configuration update will be accepted and will be distributed to the two online door controllers. The offline door controller will receive the update from the other door controllers when it comes online.

To check if a request will be accepted, check if the majority of the door controllers in the network are connected. First use `aconn:GetPeerList` to list all peers (see section [List peers](#list-peers)). The total number of door controllers in the network is the number of door controllers with `TrustState` equal to `InPeerNetwork`. The number of connected door controllers is the number of door controllers with `TrustState` equal to `InPeerNetwork` and with `ConnectionState` equal to `Connected`. If the number of connected door controllers divided by the total number of door controllers is larger than 50%, then there is a majority and the request will be accepted.

### API functions

The table lists the API functions supported by the connection service.

API functions in the Connection Service

| API function | Description |
| --- | --- |
| aconn:AddPeers | This operation is used to have a door controller invite one or more door controllers to join its door controller network. The inviting door controller may or may not already be part of a door controller network. |
| aconn:RemovePeers | This operation is used to have a door controller remove one or more peers from a door controller network. |
| aconn:LeaveNetwork | Leave network means that the door controller will remove itself from the door controller network, without communication with the other peers. Leaving network should only be used as last-exit-option, when `aconn:RemovePeers`is not possible. |
| aconn:GetPeerList | This operation is used to get a list of all peers from a door controller. |
| aconn:SetStandAloneMode | Setting Stand Alone Mode to True means that the door controller will not accept requests from peers to become part of their network. Setting this parameter to False means that the door controller will accept request from peers to become part of their network. Already established connected peers are not affected by this parameter. |
| aconn:GetStandAloneMode | Returns current Stand Alone Mode state. If the device is paired with any other device, this call will always return `True`. See `SetStandAloneMode` for more information. |

### Two sample door controllers

The API documentation uses a sample configuration with two door controllers called A and B. See table below.

Sample door controllers

| Name | Id | Address |
| --- | --- | --- |
| A | 00408C184C1E | 192.168.0.90 |
| B | 00408C184C1F | 192.168.0.91 |

### Connect door controllers

A remote door controller can be added to a door controller network using `aconn:AddPeers`. In the request `ExpectedAddress` or ID should be specified. `ExpectedAddress` is the IPv4 address and `ID` is the Media Access Control (MAC) address of the remote door controller. If `ExpectedAddress` and `ID` are both specified, both values must be true for the door controller to be connected.

The `aconn:AddPeers` operation starts an asynchronous process of inviting and adding the specified door controllers. A successful response from `aconn:AddPeers` indicates that the process has started, not that the door controllers are added to the network. When the door controllers have been added, an event will be emitted. The event is described below

When adding door controllers to a network, the majority rule applies, see section [Door controller network basics](#door-controller-network-basics). Door controllers can only be added if a majority of the door controllers in the network are connected.

When a door controller is added to the network, the door controller’s configuration is modified. All hardware-related configuration will remain, but configurations related to access management will be deleted and replaced by the configuration used by the door controller network. The table lists configurations that remain and configurations that are deleted.

Example of door controller configurations that are deleted and configurations that remain when the door controller joins a network.

| Deleted configurations | `IdDataConfiguration` |
| --- | --- |
|  | `DoorScheduleConfiguration` |
|  | `Credential` |
|  | `User` |
|  | `AccessProfile` |
|  | `AuthenticationProfile` |
|  | `User-defined schedules` |
|  | `Default schedules` |
| Remaining configurations | `Door` |
|  | `DoorConfiguration` |
|  | `IdPoint` |
|  | `IdPointConfiguration` |
|  | `AccessPoint` |

The `aconn:AddPeers` request in the following example is sent to door controller A (see section [Two sample door controllers](#two-sample-door-controllers)) in order to add door controller B to the network.

Request

```bash
{    "aconn:AddPeers": {        "Peer": \[            {                "ID": "00408C184C1F",                "ExpectedAddress": "192.168.0.91"            }        \]    }}
```

Request

```bash
<aconn:AddPeers>    <aconn:Peer>        <aconn:ExpectedAddress>192.168.0.91</aconn:ExpectedAddress>        <aconn:ID>00408C184C1F</aconn:ID>    </aconn:Peer></aconn:AddPeers>
```

The response to a successful `aconn:AddPeers` request is empty.

The following example shows the event that is emitted when a connection is established and door controller B is added to the network. The peer (door controller B) is identified by its `ID` which here is marked in bold.

```bash
{    "rowid": 162,    "token": "Axis-00408c184bdb:1383295902.202490000",    "UUID": "5581ad80-95b0-11e0-b883-00408c184bdb",    "UtcTime": "2013-11-01T08:51:42.181973Z",    "KeyValues": \[        { "Key": "Peer", "Value": "00408C184C1F", "Tags": \["onvif-data"\] },        { "Key": "topic1", "Value": "PeerConnection", "Tags": \[\] },        { "Key": "topic0", "Value": "Device", "Tags": \[\] },        {            "Key": "Status",            "Value": "ConnectionEstablished",            "Tags": \["onvif-source"\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>162</axlog:rowid>    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c184bdb</axlog:UUID>    <axlog:UtcTime>2013-11-01T08:51:42Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>Peer</axlog:Key>        <axlog:Value>00408C184C1F</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        <axlog:Value>PeerConnection</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>Device</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>Status</axlog:Key>        <axlog:Value>ConnectionEstablished</axlog:Value>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues></axlog:Event>
```

### Disconnect door controllers

A door controller can be removed from the door controller network using `aconn:RemovePeers` or using `aconn:LeaveNetwork`.

`aconn:RemovePeers`, see section [Remove peers](#remove-peers), is the preferred method and can be sent to any door controller in the network.

`aconn:LeaveNetwork`, see section [Leave network](#leave-network), is intended for situations where `aconn:RemovePeers` cannot be used, for example because of the majority rule. The request should be sent to the door controller to remove.

#### Remove peers

`aconn:RemovePeers` is similar to `aconn:AddPeers` and can be sent to any door controller in the network. A peer with an `ExpectedAddress` or `ID` matching the values specified in the request will be removed from the door controller network. The `ExpectedAddress` is not matched with the `LastKnownAddress`.

The response from `aconn:RemovePeers` indicates that the remove process has started, not that the doors controllers are removed. When the door controllers have been removed, an event will be emitted.

The majority rule, see section [Door controller network basics](#door-controller-network-basics), applies when removing door controllers from a network. `aconn:RemovePeers` is only successful if a majority of the door controllers in the network are connected.

When a door controller is removed using `aconn:RemovePeers`, the door controller’s configuration is modified similar to what happens when a door controller is added. Hardware-related configuration remain unchanged but other configurations will be deleted.

After removing a door controller, the door controller’s hardware configuration should be reset. If not, the doors connected to the door controller will remain in the system and cannot be removed.

The removed door controller will be in stand alone mode, as described in section [Prevent door controller from joining door controller network](#prevent-door-controller-from-joining-door-controller-network).

If the door controller network consists of only two door controllers, both will be in stand alone mode if one of them is removed from the network.

The `aconn:RemovePeers` request in the following example is sent to the sample door controller A in order to remove door controller B from the network.

Request

```bash
{    "aconn:RemovePeers": {        "Peer": \[            {                "ID": "00408C184C1F",                "ExpectedAddress": "192.168.0.91"            }        \]    }}
```

Request

```bash
<aconn:RemovePeers>    <aconn:Peer>        <aconn:ExpectedAddress>192.168.0.91</aconn:ExpectedAddress>        <aconn:ID>00408C184C1F</aconn:ID>    </aconn:Peer></aconn:RemovePeers>
```

The response to a successful `aconn:RemovePeers` operation is empty.

#### Leave network

The `aconn:LeaveNetwork` is intended for situations where `aconn:RemovePeers` cannot be used, typically because of the majority rule. `aconn:LeaveNetwork` should be sent to the door controller to remove and forces the door controller to abruptly leave the network without trying to communicate with the other door controllers in the network.

When a door controller leaves the network using `aconn:LeaveNetwork`, all hardware-related configuration as well as all global configuration related to access management are kept. The only information removed is the list of known remote door controllers.

`aconn:LeaveNetwork` is an emergency exit to be used if it is not possible to fulfill the majority condition by bringing offline door controllers back online. The global configuration used by the network is kept in the door controller and can be used when setting up a new door controller network.

The following example shows the `aconn:LeaveNetwork` request. The request takes no parameters and must be sent to the door controller that should be removed from the network.

Request

```bash
{    "aconn:LeaveNetwork": {}}
```

Request

```bash
<aconn:LeaveNetwork />
```

The response to a successful `aconn:LeaveNetwork` operation is empty.

### List peers

Each door controller maintains a list of known remote door controllers. The list contains peers connected in the same door controller network as well as discovered but not connected door controllers. Each door controller broadcasts its presence in order to make it possible for other door controllers to discover it.

In following example, `aconn:GetPeerList` operation below is sent to door controller A. The successful completion of this operation results in door controller A reporting back a list of its peers. In this example the door controller network consists of only door controller A and B. The sample door controller is from section [Two sample door controllers](#two-sample-door-controllers).

Request

```bash
{    "aconn:GetPeerList": {}}
```

Response

```bash
{    "Self": {        "ID": "00408C184BDB",        "ExpectedAddress": "",        "LastKnownAddress": "",        "DeviceUUID": "5581ad80-95b0-11e0-b883-00408c184bdb",        "TrustState": "InPeerNetwork",        "ConnectionState": "Connected"    },    "Peer": \[        {            "ID": "00408C184C1F",            "ExpectedAddress": "192.168.0.91",            "LastKnownAddress": "192.168.0.91",            "DeviceUUID": "5581ad80-95b0-11e0-b883-00408c184c1f",            "TrustState": "InPeerNetwork",            "ConnectionState": "Connected"        }    \]}
```

`Self` represents the door controller where the API call was done. `Peer` is the list of all connected peers and discovered but disconnected peers.

In `Peer,LastKnownAddress` is the discovered address and will be empty if not found during the discovery process. `ExpectedAddress` is only set if the peer was added using it, and may also differ from `LastKnownAddress` if the peer is discovered at another address than used when it was added.

#### Trust state

The `TrustState` describes if a peer is part of the trusted network. The available states are `NotInPeerNetwork, AddingToPeerNetwork, InitialSyncWithPeerNetwork, InPeerNetwork`and `RemovingFromPeerNetwork`. The possible transitions are shown by the state diagram.

![Possible transitions of TrustState](/assets/images/connection-service.t10068093-0a722dc5e6743c9dc75e8f0f0317682e.png)

An added door controller (by `aconn:AddPeers`) will go from `NotInPeerNetwork` to `InPeerNetwork` via `AddingToPeerNetwork` and `InitialSyncWithPeerNetwork`. The `AddingToPeerNetwork` state means that the remote peer is currently in the process of joining the network. The `InitialSyncWithPeerNetwork` state is when the peer is accepted into the network but not yet fully initialized (that is, catching up on the network’s specific data).

A peer being removed from the network (using `aconn:RemovePeers`) will go from `InPeerNetwork` to `NotInPeerNetwork` via `RemovingFromPeerNetwork`. The `RemovingFromPeerNetwork` state is where the peer will be until all other peers in the current network are updated of that the peer is leaving.

The other state transitions illustrated are special cases when a peer is removed when not in `InPeerNetwork` state.

#### ConnectionState

The ConnectionState describes if there is a network link established to the remote peer. The available states are `Disconnected`, `Connected` and `PairingFailed`.

`PairingFailed` indicates that an error occurred while trying to pair the door controllers during the `AddingToPeerNetwork` state, for example, the `ID` of the remote peer is not the `ID`as specified when calling `aconn:AddPeers`.

An event is dispatched whenever a remote peer changes `ConnectionState`. The event structure is described in section 10.4, and the `Status`\-field will indicate the state change.

### Prevent door controller from joining door controller network

By default, door controllers are open to become part of a door controller network. Stand-alone mode exists to set whether or not the door controller should join a door controller network upon invitation requests. Stand-alone mode is not applicable for door controllers that are already in a door controller network.

Setting `StandAloneMode` to True means that the door controller will not accept requests from other peers, and `False` means that it will accept requests.

The sample `aconn:SetStandAloneMode` below is sent to door controller A to toggle `StandAloneMode`, and it affects door controller A only.

Request

```bash
{    "aconn:SetStandAloneMode": {        "StandAlone": true    }}
```

Request

```bash
<aconn:SetStandAloneMode>    <aconn:StandAlone>true</aconn:StandAlone></aconn:SetStandAloneMode>
```

The response to a successful `aconn:SetStandAloneMode` operation is empty.

The sample `aconn:GetStandAloneMode` below is sent to door controller A to read its stand-alone mode setting.

Request

```bash
{    "aconn:GetStandAloneMode": {}}
```

Request

```bash
<aconn:GetStandAloneMode />
```

Response

```bash
{    "StandAlone": true}
```

Response

```bash
<aconn:GetStandAloneModeResponse>    <aconn:StandAlone>true</aconn:StandAlone></aconn:GetStandAloneModeResponse>
```

## Connection service API specification

The connection service are used to create door controller network by interconnecting door controllers to each other. A door controller network can be altered by adding and removing door controllers to/from the door controller network. Current status of the door controllers can also be retrieved.

### Peer

aconn = [http://www.axis.com/vapix/ws/connection](http://www.axis.com/vapix/ws/connection)

#### Peer data structure

The configuration of a peer.

The following fields are available:

-   I`D`
    
    MAC in form 000000000000 or 00:00:00:00:00:00. May be empty for pending peers.
    
-   `ExpectedAddress`
    
    IPv4 address. May be empty for pending peers.
    
-   `LastKnownAddress`
    
    IPv4 address. May be empty for pending peers.
    
-   `DeviceUUID`
    
    Device UUID of peer. May be empty for pending peers. - - `TrustState` - `ConnectionState`
    

#### PeerTrustState data structure

The trust state of a peer.

The following values are available:

-   `NotInPeerNetwork`
    
    Peer discovered on the network
    
-   `AddingToPeerNetwork`
    
    Peer added by `AddPeers` but not yet reached
    
-   `InitialSyncWithPeerNetwork`
    
    Peer trusted, but not yet initially synced with other peers
    
-   `InPeerNetwork`
    
    Trusted peer
    
-   `RemovingFromPeerNetwork`
    
    Trusted peer that is in the process of being removed
    

#### PeerConnectionState data structure

The connection state of a peer.

The following values are available:

-   `Disconnected`
    
    No connection open to peer
    
-   `PairingFailed`
    
    Failed to pair with pending peer
    
-   `Connected`
    
    Connection open to peer
    

#### PeerInfo data structure

A subset of the configuration of a peer.

The following fields are available:

-   `ID`
    
    MAC in form 000000000000 or 00:00:00:00:00:00.
    
-   `ExpectedAddress`
    
    IPv4 address.
    

#### GetPeerList command

List of peers.

GetPeerList command

-   Name: `GetPeerList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetPeerListRequest` | This message shall be empty. |
| `GetPeerListResponse` | This message contains:  
  
\- `Self`: The peer this function was called on.  
\- `Peer`: All other peers.  
  
`aconn:Peer Self [1][1]`  
`aconn:Peer Peer [0][unbounded]` |

#### AddPeers command

Requests that a set of peers be added to the trusted network. Note that the success of this function does not mean that the peer has been added yet.

AddPeers command

-   Name: `AddPeers`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `AddPeersRequest` | This message contains:  
  
\- `Peer`: Peers to add.  
  
`aconn:Peer Peer [0][unbounded]` |
| `AddPeersResponse` | This message shall be empty. |

#### RemovePeers command

Requests that a set of peers be removed from the trusted network. Note that the success of this function does not mean that the peer has been removed yet.

RemovePeers command

-   Name: `RemovePeers`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemovePeersRequest` | This message contains:  
  
\- `Peer`: Peers to remove.  
  
`aconn:PeerInfo Peer [1][unbounded]` |
| `RemovePeersResponse` | This message shall be empty. |

#### SetStandAloneMode command

Setting this parameter to true means that the door controller does not accept requests from peers to become part of their network. Setting this parameter to false means that the door controller device accepts requests from peers to become part of their network. Already established connected peers are not affected by this parameter.

SetStandAloneMode command

-   Name: `SetStandAloneMode`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetStandAloneModeRequest` | This message contains:  
  
\- `StandAlone`:`xs:boolean StandAlone [1][1]` |
| `SetStandAloneModeResponse` | This message shall be empty. |

#### GetStandAloneMode command

Returns current stand-alone–mode state. If the device is paired with any other device, this call will always return true. See [SetStandAloneMode command](#setstandalonemode-command) for more information.

GetStandAloneMode command

-   Name: `GetStandAloneMode`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetStandAloneModeRequest` | This message shall be empty. |
| `GetStandAloneModeResponse` | This message contains:  
  
\- `StandAlone`:`xs:boolean StandAlone [1][1]` |

#### LeaveNetwork command

Ejects the peer from its existing network, forgetting all trusted, pending and pending\_remove peers but keeping device-specific data.

LeaveNetwork command

-   Name: `LeaveNetwork`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `LeaveNetworkRequest` | This message shall be empty. |
| `LeaveNetworkResponse` | This message shall be empty. |