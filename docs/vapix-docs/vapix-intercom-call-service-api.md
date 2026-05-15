---
title: Call service API
url: "https://developer.axis.com/vapix/intercom/call-service-api/"
category: vapix
subcategory: intercom
sha256: 62db45840bc92bd1c6b988dbb8b891d71c9894d7f4ff58580dd768e842931597
scraped_at: "2026-01-09T15:19:12.119Z"
page_height: 101584
---

# Call service API

## Description

The Call service API enables Axis products to be integrated in a Voice over IP (VoIP) system. The service uses the Session Initiation Protocol (SIP).

Axis products that support the Call service API can make calls to and receive calls from SIP URIs, for example through a SIP provider or through a Public Branch Exchange (PBX) system. It is also possible to make peer-to-peer calls and to simulate calls. Axis products can respond to Dual-Tone Multi-Frequency (DTMF) sequences, for example to unlock a door when the correct DTMF sequence is received.

To allow VoIP functionality to be integrated in video management systems without implementing SIP, the Call Service supports simulated calls. A simulated call, known as a VMS call, is simulated using the Axis product’s event system and uses the RTSP and HTTP APIs for video and audio streaming.

Events emitted by the Call service inform clients about the call status. The events can be used together with the Axis product’s event and action functionality to instruct the Axis product to perform actions when a call is in progress, is active or is ended. For example, the Axis product can flash a light LED and play a tone when the product makes or receives a call.

Supported functionality:

-   Configure SIP settings.
-   Set up SIP accounts.
-   Retrieve information about calls and call statuses.
-   Initiate and terminate calls.
-   Configure DTMF sequences and DTMF events.
-   Configure the audio codec priority list.

The service defines the following events:

-   Call state events, see [Call state event](#call-state-event).
-   Call state change events, see [Call state change event](#call-state-change-event).
-   DTMF events, see [DTMF events](#dtmf-events).

API requests can be constructed using JSON or using a simplified key-value format. Section [JSON and simplified key-value requests](#json-and-simplified-key-value-requests) describes the request syntax.

### Identification

The Call service API is supported if:

-   **Property**: `Properties.API.SIP.SIP=yes`
-   **Property**: `Properties.API.SIP.Version=2.0` and later.

Use `axcall:GetServiceCapabilities` to list the service capabilities. See [GetServiceCapabilities command](#getservicecapabilities-command).

### Terminology and abbreviations

-   **AOR**: Address of record
    
-   **DFMF**: Dual-Tone Multi-Frequency
    
-   **ICE**: Interactive Connectivity Establishment
    
-   **MWI**: Message Waiting Indication
    
-   **NAT**: Network Address Translation
    
-   Non-normative enum
    
    Enum whose values are used as strings.
    
-   **PBX**: Private Branch Exchange
    
-   **SIP**: Session Initiation Protocol
    
-   **STUN**: Session Traversal Utilities for NAT
    
-   **TURN**: Traversal Using Relays around NAT
    

### Limitations

All types defined by the Call service have an upper limit of maximum 100 entities per type. This policy is not enforced by the service, exceeding the limit is however not recommended as it may cause unexpected behavior.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## SIP configuration and SIP calls

The Session Initiation Protocol (SIP) is an application layer protocol for managing interactive multimedia communication sessions, for example voice and video calls. SIP is a client-server protocol with a syntax similar to HTTP and SMTP and is used to establish, update and terminate communication sessions between two or more devices.

Before the Axis product can be used to make and receive calls, SIP must be enabled and a SIP account must be set up. The SIP account can be a peer-to-peer account or it can be an account registered at a SIP registrar.

Calls can be initiated in different ways:

-   Using `axcall:Call` in the Call service. See [Call command](#call-command)
-   Using action rules in the Action service. For example, an action rule in the Axis product can listen to events from the product’s input ports. When the event `tns1:Device/tnsaxis:IO/Port` is emitted, the call is initiated as an action of type `com.axis.action.fixed.sip`.

If the Axis product is installed behind a NAT device, for example a network router, and needs to be able to make and receive calls from devices on the other side of the NAT device, SIP-specific port forwarding must be configured. See [NAT traversal](#nat-traversal).

For examples on how to enable and configure SIP, see section [Common examples](#common-examples).

### DTMF signaling

Dual-Tone Multi-Frequency (DTMF), also known as touch-tone, is a signaling system used by telecommunication devices such as telephone handsets, switch centers, door stations, and other communication devices.

DTMF can be used to send commands to a remote device in order to instruct the remote device to perform certain actions. To send a command, the user presses the keys on a keypad in a certain sequence, for example `#1234#`. A DTMF packet is then created and sent to the other device. The receiving device decodes the packet and if the key sequence matches one of the allowed DTMF sequences in the receiving device, the device performs a user-defined action.

Axis products that support DTMF can receive, decode and identify DTMF sequences and can be configured to perform actions when a DTMF sequence is received. The Axis product can receive DTMF sequences sent over RTP (RFC 2833) and over SIP INFO (RFC 2976).

info

To check if the Axis product supports DTMF, use axcall:GetServiceCapabilities. See [Service capabilities](#service-capabilities).

To configure an Axis product to allow an operator to unlock a door using a DTMF sequence, the following steps are required:

1.  Connect the door lock to one of the Axis product’s output ports and use VAPIX® I/O port API to configure the port.
    
2.  Enable SIP in the Axis product and configure the SIP settings.
    
3.  Set up a DTMF event. Add the event to a DTMF configuration and add the DTMF configuration to a SIP account. See [Set up a DTMF event](#set-up-a-dtmf-event).
    
4.  Set up an action rule that listens to the DTMF event and activates the door lock output port when the event is received.
    

When the Axis product receives the correct DTMF sequence, the DTMF event is emitted and the door is unlocked.

### NAT traversal

If the Axis product is installed behind a NAT device, for example a network router, and needs to be able to make and receive calls from devices on the other side of the NAT device, SIP-specific port forwarding must be configured.

The following NAT traversal methods can be used with SIP:

-   Interactive Connectivity Establishment (ICE)
-   Session Traversal Utilities for NAT (STUN)
-   Traversal Using Relays around NAT (TURN)

The NAT traversal method to use is specified in the `SIPConfiguration`. See [SIPConfiguration](#sipconfiguration).

## VMS calls

A VMS call is a simulated call from an Axis product to a video management system (VMS). The call is simulated using the Axis product’s event system and is intended for clients that use the Video streaming API:s instead of SIP.

VMS calls are similar to SIP calls and are set up using the same call service request, but the call receiver is `VMS_CALL` instead of a SIP URI, see [Call command](#call-command). VMS calls do not require a SIP account and can be made also if SIP is disabled. A VMS call produces the same events as a SIP call and, therefore, the Axis product acts as if a SIP call was made.

If required, VMS calls can be disabled by configuring the `VMSCallConfiguration` data structure. It is also possible to control when a call is considered active. See [VMS call configuration](#vms-call-configuration).

The following example shows how VMS calls from AXIS A8004-VE Video door station can be integrated with a video management system (VMS).

AXIS A8004-VE has a built-in call button which is available from the door station’s front panel. The button is connected to one of the door station’s I/O ports. To make a call from the door station to the VMS, the caller presses the call button. When the button is pressed, the digital input event `tns1:Device/tnsaxis:IO/Port` with `Source: port=0` and `Data: state=1` is emitted.

info

The port number and state may differ depending on the Axis product configuration. The event syntax is described in VAPIX® Event and action services.

The digital input event is used to initiate the simulated call in the Axis product. AXIS A8004-VE is pre-configured with an action rule that listens to the event from the call button and has `com.axis.action.fixed.sip` with call recipient `VMS_CALL` as its action. When the event is emitted, the VMS call is initiated. The call state becomes `Calling` and a call state event `tnsaxis:Call/State` is emitted as described in [Outgoing VMS call](#outgoing-vms-call).

The same digital input event, or the call state event `tnsaxis:Call/State`, can be used to initiate the call in the VMS. When the VMS receives the event, the VMS can, for example, alert an operator by displaying a question to answer or to reject the call. If the operator decides to answer the call, the VMS should start retrieving an audio stream, or a combined video and audio stream, from the Axis product and should also start transmitting audio to the Axis product.

When the Axis product detects that audio is sent to the product, the call is considered answered. The call state changes to `Active` and the caller at the door station and the VMS operator can talk to each other. The call is considered ended when the VMS stops the audio stream.

info

This behavior can be configured using the VMSCallConfiguration data structure. See [VMS call configuration](#vms-call-configuration).

For Axis products without a built-in call button and pre-configured action rule, the same functionality can be achieved by connecting an external button to an input port and by setting up a corresponding action rule. Configuration and management of input ports is described in VAPIX® I/O port API. Action rules are described in VAPIX® Event and action services.

Call state events can be used to indicate that a call is being made. AXIS A8004-VE has a number of pre-configured action rules that, for example, flash the call button LED and play a tone (using the audio clip action) while the call status is `Calling`.

## JSON and simplified key-value requests

In some VAPIX API:s, for example the Call service API, requests can be constructed using JSON or using a simplified key-value format.

The simplified key-value format is a flattened structure with `key=value` strings. Levels in the structure are indicated by underscores (`_`).

-   Boolean values are encoded as `true` and `false`.
-   The `NULL` value is encoded as `null`.
-   Strings are URL-encoded and may start and end with quotation marks. Example: `"a+string%0A"`.
-   Array keys are encoded as `_index_` where `index` is an integer starting from 0.

Character sets are not converted or validated. UTF-8 is recommended.

This example from the Call service API shows how to request the current SIP configuration using cURL. The first example shows the JSON syntax, the second example shows the corresponding simplified syntax.

**NOTE**

When using cURL on Windows, you might need to escape the quote characters for the commands to work, i.e:

```bash
-d '{"axcall:GetSIPConfiguration":{}}'
```

should instead be written as:

```bash
-d "{\\"axcall:GetSIPConfiguration\\":{}}"
```

JSON request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call" -s -d '{"axcall:GetSIPConfiguration":{}}'> {>   "SIPConfiguration": {>     "SIPEnabled": false,>     "TURNServers": \[\],>     "STUNServers": \[\],>     "ICEEnabled": false,>     "AllowIncomingCalls": false,>     "TURNEnabled": false,>     "STUNEnabled": false,>     "ApplyUserAuthentication": false,>     "AllowedUsers": \[\],>     "SIPPort": 5060,>     "SIPTLSPort": 5061,>     "ApplyAllowedURIs": false,>     "AllowedURIs": \[\]>   }> }
```

Simplified request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call?format=simple&action=axcall:GetSIPConfiguration"'> SIPConfiguration\_SIPEnabled=false> SIPConfiguration\_SIPPort=5060> SIPConfiguration\_SIPTLSPort=5061> SIPConfiguration\_STUNEnabled=false> SIPConfiguration\_TURNEnabled=false> SIPConfiguration\_ICEEnabled=false> SIPConfiguration\_AllowIncomingCalls=false> SIPConfiguration\_ApplyUserAuthentication=false> SIPConfiguration\_ApplyAllowedURIs=false
```

This example shows how to retrieve a list of structures in simplified format. The example shows a list of three `SIPAccounts`. Each key is prefixed with `_index_` where `index` is the index of the element in the list. All keys that share the same prefix correspond to the same element.

Simplified request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call?format=simple&action=axcall:GetSIPAccounts"'> SIPAccount\_0\_Id="sip\_account\_0"> SIPAccount\_0\_Username="local\_account\_ipv4\_udp"> SIPAccount\_0\_Password=null> SIPAccount\_0\_Registrar=null> SIPAccount\_0\_PublicDomain=null> SIPAccount\_0\_IsDefault=false> SIPAccount\_0\_Transport="udp"> SIPAccount\_0\_CallerId="local\_account\_ipv4\_udp"> SIPAccount\_1\_Id="sip\_account\_1"> SIPAccount\_1\_Username="1234"> SIPAccount\_1\_Password="password"> SIPAccount\_1\_Registrar="192.168.0.91"> SIPAccount\_1\_PublicDomain="exampledomain.com"> SIPAccount\_1\_IsDefault=true> SIPAccount\_1\_Transport="udp"> SIPAccount\_1\_CallerId="Entrance Door"> SIPAccount\_1\_DTMFConfigurationId="internal\_config"> SIPAccount\_2\_Id="sip\_account\_2"> SIPAccount\_2\_Username="987654"> SIPAccount\_2\_Password="password2"> SIPAccount\_2\_Registrar=null> SIPAccount\_2\_PublicDomain="examplesecurity.se"> SIPAccount\_2\_IsDefault=false> SIPAccount\_2\_Transport="udp"> SIPAccount\_2\_CallerId="Entrance Door (Axis)"> SIPAccount\_2\_DTMFConfigurationId="remote\_config"> SIPAccount\_3\_Id="sip\_account\_3"> SIPAccount\_3\_Username="12309"> SIPAccount\_3\_Password="password3"> SIPAccount\_3\_Registrar=null> SIPAccount\_3\_PublicDomain="\[fd12:3456:789a:1::90\]"> SIPAccount\_3\_PrioritizeIPv6=true> SIPAccount\_3\_IsDefault=false> SIPAccount\_3\_Transport="udp"> SIPAccount\_3\_CallerId="Entrance Door (Axis)"> SIPAccount\_3\_DTMFConfigurationId="remote\_config"> SIPAccount\_4\_Id="sip\_account\_4"> SIPAccount\_4\_Username="local\_account\_ipv6\_tcp"> SIPAccount\_4\_Password=null> SIPAccount\_4\_Registrar=null> SIPAccount\_4\_PublicDomain=null> SIPAccount\_4\_PrioritizeIPv6=true> SIPAccount\_4\_IsDefault=false> SIPAccount\_4\_Transport="tcp"> SIPAccount\_4\_CallerId="local\_account\_ipv6\_tcp"
```

Corresponding request and response in JSON:

JSON request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call" -s -d '{"axcall:GetSIPAccounts":{}}'> {>   "SIPAccount": \[>     {>       "Username": "local\_account\_ipv4\_udp",>       "PublicDomain": null,>       "CallerId": "local\_account\_ipv4\_udp",>       "Registrar": null,>       "Transport": "udp",>       "Password": null,>       "Id": "sip\_account\_0",>       "IsDefault": false>     },>     {>       "Username": "1234",>       "PublicDomain": "exampledomain.com",>       "CallerId": "Entrance Door",>       "DTMFConfigurationId": "internal\_config",>       "Registrar": "192.168.0.91",>       "Transport": "udp",>       "Password": "password",>       "Id": "sip\_account\_1",>       "IsDefault": true>     },>     {>       "Username": "987654",>       "PublicDomain": "examplesecurity.se",>       "CallerId": "Entrance Door (Axis)",>       "DTMFConfigurationId": "remote\_config",>       "Registrar": null,>       "Transport": "udp",>       "Password": "password2",>       "Id": "sip\_account\_2",>       "IsDefault": false>     },>     {>       "Username": "12309",>       "Registrar": null,>       "PublicDomain": "\[fd12:3456:789a:1::90\]",>       "SecondaryRegistrar": "",>       "SecondaryPublicDomain": "",>       "CallerId": "Entrance Door (Axis)",>       "DTMFConfigurationId": "internal\_config",>       "Transport": "udp",>       "Password": "password3",>       "Id": "sip\_account\_3",>       "IsDefault": false>     },>     {>       "Username": "local\_account\_ipv6\_tcp",>       "PublicDomain": null,>       "CallerId": "local\_account\_ipv6\_tcp",>       "Registrar": null,>       "Transport": "tcp",>       "PrioritizeIPv6": true,>       "Password": null,>       "Id": "sip\_account\_4",>       "IsDefault": false>     }>   \]> }
```

This example shows a response with fault codes.

JSON request:

```bash
curl --anyauth "http://root:pass@192.168.0.90/vapix/axast" -s -d '{"axast:PerformSpeakerTest":{}}'
```

**JSON response:**

-   **HTTP code**: `400 Bad Request`

```bash
{    "Fault": "env:Receiver",    "FaultCode": "ter:Action",    "FaultSubCode": "axast:DeviceNotCalibrated",    "FaultReason": "The Auto Speaker Test cannot be done without prior calibration.",    "FaultMsg": null}
```

Simplified request:

```bash
curl --anyauth "http://root:pass@192.168.0.90/vapix/axast?format=simple&action=axast:PerformSpeakerTest"
```

**Simplified response:**

-   **HTTP code**: `400 Bad Request`

```bash
Fault="env:Receiver"FaultCode="ter:Action"FaultSubCode="axast:DeviceNotCalibrated"FaultReason="The Auto Speaker Test cannot be done without prior calibration."FaultMsg=null
```

## Common examples

This section contains examples how to set up the Axis product to make calls using SIP.

1.  Enable SIP in the Axis product. See [Enable SIP](#enable-sip).
    
2.  Set up a SIP account in the Axis product.
    
3.  1.  See [Add a peer-to-peer account](#add-a-peer-to-peer-account).
        
    2.  See [Add a registered SIP account](#add-a-registered-sip-account).
        
    3.  See [Add a registered SIP account with stream parameters](#add-a-registered-sip-account-with-stream-parameters).
        
    4.  See [Add a registered SIP account with SIP proxies](#add-a-registered-sip-account-with-sip-proxies).
        
4.  Make a SIP call. See [Make a SIP call](#make-a-sip-call).
    
5.  Terminate the call. See [Terminate a call](#terminate-a-call).
    
6.  Set up a DTMF sequence. See [Set up a DTMF event](#set-up-a-dtmf-event).
    
7.  Make a VMS call. See [Make a VMS call](#make-a-vms-call).
    
8.  Configure the audio codec priority list. See [Configure the audio codec priority list](#configure-the-audio-codec-priority-list).
    
9.  Working with call status events. See [Event examples](#event-examples).
    

Most examples use pseudocode to illustrate the intended workflow. Data is shown in JavaScript Object Notifiction (JSON) format. The API syntax is described in [JSON and simplified key-value requests](#json-and-simplified-key-value-requests).

### Enable SIP

Before the Axis product can be used to make SIP calls, the SIP protocol must be enabled in the product. For security reasons, SIP is disabled by default. For the Axis product to be able to receive incoming SIP calls, SIP and the `AllowIncomingCalls` functionality must both be enabled.

info

VMS calls can be made also if SIP is disabled.

The following pseudocode shows how to enable the SIP protocol. First, `axcall:GetSIPConfiguration` is used to retrieve the current SIP configuration. Then, `axcall:SetSIPConfiguration` is used to updated the SIP configuration.

```bash
{  get\_response = axcall.GetSIPConfiguration()  config = get\_response\['SIPConfiguration'\]  config\['SIPEnabled'\] = true  axcall.SetSIPConfiguration(SIPConfiguration=config)}
```

JSON request to enable SIP:

```bash
{    "axcall:SetSIPConfiguration": {        "SIPConfiguration": {            "SIPEnabled": true,            "TURNServers": \[\],            "STUNServers": \[\],            "ICEEnabled": false,            "AllowIncomingCalls": false,            "TURNEnabled": false,            "STUNEnabled": false,            "ApplyUserAuthentication": false,            "AllowedUsers": \[\],            "SIPPort": 5060,            "SIPTLSPort": 5061,            "ApplyAllowedURIs": false,            "AllowedURIs": \[\]        }    }}
```

The request is described in [SetSIPConfiguration command](#setsipconfiguration-command). The SIP configuration data structure is described in [SIPConfiguration](#sipconfiguration). See also [NAT traversal](#nat-traversal).

### Add a peer-to-peer account

A peer-to-peer account is a SIP account that is not registered at a SIP registrar. The account can be used to make peer-to-peer calls. Because the account is not registered, any `UserId` can be set. To make a call through a PBX or SIP provider, the account must be registered. See [Add a registered SIP account](#add-a-registered-sip-account).

The following pseudocode shows how to add a peer-to-peer account and how to check its status. The account is created using `axcall:SetSIPAccount`. The response returns the SIP account identifier `SIPAccountId` which should be used in subsequent requests. The account’s status is retrieved using `axcall:GetSIPAccountStatus`.

```bash
{  account\['UserId'\] = "peer-to-peer"  set\_response = axcall.SetSIPAccount(SIPAccount=account)  my\_accountid = set\_response\['SIPAccountId'\]  status\_response = axcall.GetSIPAccountStatus(SIPAccountId=myaccountid)  account\_status = status\_response\['SIPAccountStatus'\]}
```

JSON request to add a peer-to-peer SIP account:

```bash
{    "axcall:SetSIPAccount": {        "SIPAccount": {            "UserId": "peer-to-peer"        }    }}
```

JSON response:

```bash
{    "SIPAccountId": "sip\_account\_0"}
```

The request is described in [SetSIPAccount command](#setsipaccount-command). The SIP account data structure is described in [SIPAccount](#sipaccount).

In simplified format, the corresponding request and response are:

Simplified request to add a peer-to-peer account:

```bash
format=simple&action=axcall:SetSIPAccount&SIPAccount\_UserId=peer-to-peer
```

Simplified response:

```bash
SIPAccountId="sip\_account\_0"
```

Using the returned `SIPAccountId`, the account’s status can be retrieved using `axcall:GetSIPAccountStatus`.

JSON request to retrieve SIP account status:

```bash
{    "axcall:GetSIPAccountStatus": {        "SIPAccountId": "sip\_account\_0"    }}
```

JSON response:

```bash
{    "SIPAccountStatus": {        "SIPAccountId": "sip\_account\_0",        "SIPURI": "sip:192.168.0.90:5060",        "IsDefault": true,        "RegURI": "",        "Status": 0,        "StatusText": "Does not register"    }}
```

The SIP URI for a peer-to-peer account is `sip:<LOCAL IP>` where `<LOCAL IP>` is the Axis product’s IP address or DNS name. The `IsDefault` field indicates that the account is the default account, that is, the account that will be used when making a call if no other account is specified. For peer-to-peer accounts, the `StatusText` field is "Does not register", `Status` is `0` and `RegURI` is empty. The request is described in [GetSIPAccountStatus command](#getsipaccountstatus-command). The SIP account status data structure is described in [SIPAccountStatus](#sipaccountstatus).

In simplified format, the corresponding request and response are:

Simplified request to retrieve SIP account status:

```bash
format=simple&action=axcall:GetSIPAccountStatus&SIPAccountId=sip\_account\_0
```

Simplified response:

```bash
SIPAccountStatus\_SIPAccountId="sip\_account\_0"SIPAccountStatus\_SIPURI="sip:192.168.0.90:5060"SIPAccountStatus\_RegURI=nullSIPAccountStatus\_Status=0SIPAccountStatus\_StatusText="Does+not+register"
```

### Add a registered SIP account

Accounts that have been set up at a SIP registrar can be added to the Axis product using `axcall:SetSIPAccount`.

In this example, an account with user id `6001` and password `secure` has been set up at the registrar with IP address `192.168.0.1`. The public domain is `example.axis.com` and the SIP URI becomes `sip:6001@example.axis.com`

The account’s status can be requested using `axcall:GetSIPAccountStatus`.

JSON request:

```bash
{    "axcall:SetSIPAccount": {        "SIPAccount": {            "UserId": "6001",            "Password": "secure",            "Registrar": "192.168.0.1",            "PublicDomain": "example.axis.com"        }    }}
```

The response returns the `SIPAccountId` which is used as an identifier for the account. The identifier is used, for example, when making a call using `axcall:Call` and when verifying the account’s registration status using `axcall:GetSIPAccountStatus`.

JSON response

```bash
{    "SIPAccountId": "sip\_account\_0"}
```

To check the SIP account’s registration status, use `axcall:GetSIPAccountStatus`. In the response, `Status` and `StatusText` are standard SIP response codes and response phrases.

JSON request:

```bash
{    "axcall:GetSIPAccountStatus": {        "SIPAccountId": "sip\_account\_0"    }}
```

JSON response:

```bash
{    "SIPAccountStatus": {        "SIPAccountId": "sip\_account\_0",        "SIPURI": "sip:6001@example.axis.com",        "IsDefault": true,        "RegURI": "192.168.0.1",        "Status": 200,        "StatusText": "OK"    }}
```

### Add a registered SIP account with stream parameters

In the SIP account, the `StreamParameters` field specifies the resolution and frame rate to use. If no stream parameters are specified, the account uses the Axis product’s default settings.

This example shows how to add a registered SIP account with resolution 640x480 and frame rate 25 fps.

JSON request:

```bash
{    "axcall:SetSIPAccount": {        "SIPAccount": {            "UserId": "6001",            "Password": "secure",            "Registrar": "192.168.0.1",            "PublicDomain": "example.axis.com"        },        "StreamParameters": "resolution=640x480&fps=25"    }}
```

JSON response

```bash
{    "SIPAccountId": "sip\_account\_0"}
```

### Add a registered SIP account with SIP proxies

This example shows how to add a registered SIP account with two SIP proxies that route communication to the registrar at `272.25.25.3`. The SIP proxies will route traffic from top to down in the specified order, that is, `192.168.0.1` is contacted as the first node, then `10.23.23.2` and finally the registrar at `272.25.25.3` is contacted.

JSON request:

```bash
{    "axcall:SetSIPAccount": {        "SIPAccount": {            "UserId": "6001",            "Password": "secure",            "Registrar": "272.25.25.3",            "SIPAccount": \[                {                    "Server": "192.168.0.1",                    "Username": "username\_proxy1",                    "Password": "password\_proxy1"                },                {                    "Server": "10.23.23.2",                    "Username": "username\_proxy2",                    "Password": "password\_proxy2"                }            \]        }    }}
```

The response returns the `SIPAccountId` which is used as an identifier for the account. The identifier is used, for example, when making a call using `axcall:Call` and when verifying the account’s registration status using `axcall:GetSIPAccountStatus`.

JSON response

```bash
{    "SIPAccountId": "sip\_account\_0"}
```

### Make a SIP call

When SIP has been enabled and an account is set up, it is possible to call a remote SIP URI using `axcall:Call`. The request returns the call identifier `CallId`. Using `CallId`, the status of the call can be requested using `axcall:GetCallStatus`.

The following pseudocode shows how to make a call from the Axis product to `sip:6002@example.axis.com`. The call is made using `axcall:Call`. The response returns the call identifier `CallId` which is used in subsequent requests. The call’s status is requested using `axcall:GetCallStatus`. When the call is answered, the call status changes from `Calling` to `Active`.

```bash
{  call\_response = axcall.Call(To="sip:6002@example.axis.com")  status\_response = axcall.GetCallStatus(CallId=call\_response\['CallId'\])  while (status\_response.CallState == "Calling") {    sleep(1);    status\_response = axcall.GetCallStatus(CallId=call\_response\['CallId'\])  }  if (status\_response.CallState == "Active") {    // Call ok  } else {    // No answer  }}
```

JSON request to make a call:

```bash
{    "axcall:Call": {        "To": "sip:6002@example.axis.com"    }}
```

JSON response:

```bash
{    "CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"}
```

The request is described in [Call command](#call-command).

JSON request to retrieve the call status:

```bash
{    "axcall:GetCallStatus": {        "CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"    }}
```

JSON response:

```bash
{  "CallStatus": {"CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF",                "CallState": "Calling",                "CallType": "SIP",                ... }}
```

The request is described in [GetCallStatus command](#getcallstatus-command). The `CallStatus` data structure is described in [CallStatus](#callstatus).

Simplified request to make a call:

```bash
format=simple&action=axcall:Call&To=sip:6002@example.axis.com
```

Simplified response:

```bash
CallId="Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKFgSGIVX5lwi"
```

Simplified request to retrieve the call status:

```bash
format=simple&action=axcall:GetCallStatus&CallId=Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF
```

Simplified response:

```bash
CallStatus\_CallId="Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"CallStatus\_CallState="Calling"CallStatus\_CallType="SIP"
```

### Terminate a call

A call in progress can be terminated using `axcall:TerminateCall`.

The following pseudocode shows how to terminate a call.

```bash
{  call\_response = axcall.Call(To="sip:6002@example.axis.com")  axcall.TerminateCall(CallId=call\_response\['CallId'\])}
```

JSON request to terminate a call:

```bash
{    "axcall:TerminateCall": {        "CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKFgSGIVX5lwi"    }}
```

The request is described in [TerminateCall command](#terminatecall-command).

Simplified request to terminate a call:

```bash
format=simple&action=axcall:TerminateCall&CallId=Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF
```

### Set up a DTMF event

The Call service can recognize a DTMF sequence, for example `#1234#` and use the sequence to emit a DTMF event. The Axis product or a third-party application that listens to DTMF events can use the event to trigger actions, for example to activate an output port in order to unlock a door, or to send a notification. For more information, see [DTMF signaling](#dtmf-signaling).

The DTMF event syntax is described in [DTMF event](#dtmf-event).

The following pseudocode shows the workflow for setting up a DTMF event:

1.  Create a DTMF event using `axcall:SetDTMFEvent`. The event in this example is called `OpenDoorEvent`.
    
2.  Create a DTMF trigger using `axcall:SetDTMFTrigger`. The DTMF trigger connects a DTMF event with a specific DTMF sequence, in this case `#1234#`.
    
3.  Add the DTMF trigger to a DTMF configuration using `axcall:SetDTMFConfiguration`.
    
4.  Add the DTMF configuration to a SIP account using `axcall:SetSIPAccount`.
    

Pseudocode:

```bash
// Create a DTMF eventDTMFEventId dtmf\_event\_id =    axcall.SetDTMFEvent({"Name": "OpenDoorEvent",                      "Enabled": true});// Create a DTMF trigger.DTMFTriggerId dtmf\_trigger\_id =    axcall.SetDTMFTrigger({"DTMFSequence": "#1234#",                          "DTMFEventId" : dtmf\_event\_id});// Add the DTMF trigger to a DTMF configuration.DTMFConfigurationId dtmf\_conf\_id =    axcall.SetDTMFConfiguration({"Name": "OpenDoorDTMFConf",                              "DTMFTriggerId": \[dtmf\_trigger\_id\]})// Add the DTMF configuration to a SIP account.SIPAccount account = axcall.GetSIPAccount({"AccountId": "sip\_account\_0"});account\["DTMFConfigurationId"\] = dtmf\_conf\_id;axcall.SetSIPAccount(account);
```

The same DTMF configuration can be used in multiple SIP accounts but a SIP account can also have its own DTMF configuration. Using different DTMF configurations in different SIP accounts makes it possible to restrict access to certain DTMF sequences. For example, a more restrictive configuration might be required when calling an exposed cell phone as compared to calling the in-house security office.

The following pseudocode shows a setup with two different DTMF configurations `Limited` and `Full Access`. Workflow:

1.  Create two DTMF events, `Event A` and `Event B`, using `axcall:SetDTMFEvents`.
    
2.  Create one DTMF trigger for each event using `axcall:SetDTMFTriggers`. The first trigger connects DTMF sequence `1` to `Event A`. The second trigger connects DTMF sequence `2` to `Event B`.
    
3.  Create a DTMF configuration `Full Access` that contains both triggers. SIP accounts with this DTMF configuration will accept both DTMF sequences.
    
4.  Create a DTMF configuration `Limited` with only one of the triggers. SIP accounts with this DTMF configuration will only accept DTMF sequence `1`.
    

```bash
// Create two DTMF events.DTMFEventId\[\] dtmf\_events = axcall.SetDTMFEvents(\[{"Name": "Event A"},                    {"Name": "Event B"}\]);DTMFEventId dtmf\_event\_a = dtmf\_events\[0\]; // Assumption of order.DTMFEventId dtmf\_event\_b = dtmf\_events\[1\];// Create two DTMF triggersDTMFTriggerId\[\] dtmf\_trigger\_ids = axcall.SetDTMFTriggers(\[{"DTMFSequence": "1",                    "DTMFEventId" : dtmf\_event\_a},                    {"DTMFSequence": "2",                    "DTMFEventId" : dtmf\_event\_b}\]);// Create the DTMF configuration "Full Access"DTMFConfigurationId dtmf\_conf\_full\_access =    axcall.SetDTMFConfiguration({"Name": "Full Access",                          "DTMFSequence": dtmf\_trigger\_ids});// Create the DTMF configuration "Limited"DTMFTriggerId only\_trigger\_a = dtmf\_trigger\_ids\[0\] // Assumption of order.DTMFConfigurationId dtmf\_conf\_limited =    axcall.SetDTMFConfiguration({"Name": "Limited",                          "DTMFSequence": \[only\_trigger\_a\]});
```

Several DTMF sequences can trigger the same DTMF event but a single DTMF sequence cannot trigger several different DTMF events. If a DTMF sequence (sequence 1) is used to trigger a certain DTMF event (event A) and one wants to change the configuration so that the DTMF sequence triggers another DTMF event (event B), then the DTMF trigger that connects sequence 1 to event A must be updated so that the trigger instead connects sequence 1 to event B.

The following pseudocode shows how to change the DTMF event triggered by a DTMF sequence:

1.  Create two DTMF events.
    
2.  Create one DTMF trigger for each event. The first trigger connects DTMF sequence `1234` to DTMF event `Event A`. The second trigger connects DTMF sequence `5678` to DTMF event `Event B`.
    
3.  Try to create a new DTMF trigger that connects the first DTMF sequence `1234` to `Event B`. This request will fail because the same DTMF sequence cannot trigger different events.
    
4.  Update the DTMF trigger for DTMF sequence `1234` so that the sequence triggers `Event B` instead. The two DTMF sequences will now trigger the same event.
    

```bash
// Create two DTMF eventsDTMFEventId\[\] dtmf\_events = axcall.SetDTMFEvents(\[{"Name": "Event A"},        {"Name": "Event B"}\]);DTMFEventId dtmf\_event\_a = dtmf\_events\[0\];DTMFEventId dtmf\_event\_b = dtmf\_events\[1\];// Add a DTMF trigger for each eventDTMFTriggerId\[\] trigger\_ids =    axcall.SetDTMFTriggers(\[{"DTMFSequence": "1234",            "DTMFEventId" : dtmf\_event\_a},            {"DTMFSequence": "5678",            "DTMFEventId" : dtmf\_event\_b}\]);// Assumption of ordertrigger\_id\_1234 = trigger\_ids\[0\];trigger\_id\_5678 = trigger\_ids\[1\];// Try to connect the DTMF sequence "1234" to DTMF event B. This will fail. axcall.SetDTMFTrigger({"DTMFSequence", "1234" "DTMFEventId" : dtmf\_event\_b});// Update the DTMF trigger with identifier trigger\_id\_1234 so that both sequences trigger the same event.axcall.SetDTMFTrigger({"DTMFTriggerId": trigger\_id\_1234, "DTMFEventId": dtmf\_event\_b});
```

### Make a VMS call

A VMS call is a call simulated using the Axis product’s event system as described in [VMS calls](#vms-calls). VMS calls are intended for clients that use the Video streaming API:s instead of SIP.

VMS calls can be made also if SIP is disabled.

The following pseudocode shows how to make a VMS call from the Axis product. The call is made using `axcall:Call` with `To="VMS_CALL"`. The response returns the call identifier `CallId` which is used in subsequent requests. The call’s status is requested using `axcall:GetCallStatus`. When the call is answered, the call status changes from `Calling` to `Active`.

```bash
{  call\_response = axcall.Call(To="VMS\_CALL")  status\_response = axcall.GetCallStatus(CallId=call\_response\['CallId'\])  while (status\_response.CallState == "Calling") {    sleep(1);    status\_response = axcall.GetCallStatus(CallId=call\_response\['CallId'\])  }  if (status\_response.CallState == "Active") {    // Call ok  } else {    // No answer  }}
```

JSON request to make a call:

```bash
{    "axcall:Call": {        "To": "VMS\_CALL"    }}
```

JSON response:

```bash
{    "CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"}
```

The request is described in [Call command](#call-command).

JSON request to retrieve the call status:

```bash
{    "axcall:GetCallStatus": {        "CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"    }}
```

JSON response:

```bash
{  "CallStatus": {"CallId": "Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF",                "CallState": "Calling",                "CallType": "VMS",                ... }}
```

The request is described in [GetCallStatus command](#getcallstatus-command). The `CallStatus` data structure is described in [CallStatus](#callstatus).

Simplified request to make a call:

```bash
format=simple&action=axcall:Call&To=VMS\_CALL
```

Simplified response:

```bash
CallId="Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKFgSGIVX5lwi"
```

Simplified request to retrieve the call status:

```bash
format=simple&action=axcall:GetCallStatus&CallId=Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF
```

Simplified response:

```bash
CallStatus\_CallId="Out-0-1401964712.117694-gIRuBDTzh7BDKXw-5mDFKF"CallStatus\_CallState="Calling"CallStatus\_CallType="VMS"
```

### Configure the audio codec priority list

Use `axcall.SetAudioCodecs` to configure the audio codec priority list used for SIP calls.

Pseudocode:

```bash
// Get all audio codecsAudioCodec\[\] all\_codecs = axcall.GetSupportedAudioCodecs()// Get the default audio codec priority listAudioCodec\[\] default\_priority\_list = axcall.GetDefaultAudioCodecs()// Get the current audio codec priority listAudioCodec\[\] current\_priority\_list = axcall.GetAudioCodecs()// Rearrange the priority listAudioCodec\[\] new\_priority\_list  = ...set\_response = axcall.SetAudioCodecs(AudioCodec=new\_priority\_list)
```

### Event examples

The following sections provide an overview of the events emitted when the Axis product makes or receives a call.

The events are described in [Call state event](#call-state-event) and [Call state change event](#call-state-change-event).

#### Outgoing SIP call

An outgoing SIP call is a call from the Axis product to a SIP URI.

When no call is in progress, the call state property event shows state `Idle`.

```bash
tnsaxis:Call/StateData: CallState=Idle
```

When a call is initiated, the Axis product emits a call state change event with reason `Initiated`. The call state property event changes state to `Calling`.

```bash
tnsaxis:Call/StateChangeData: Reason=Initiated
```

```bash
tnsaxis:Call/StateData: CallState=Calling
```

When the call is answered, the Axis product emits a call state change event with reason `AcceptedByRemote`. The call state property event changes state to `Active`.

```bash
tnsaxis:Call/StateChangeData: Reason=AcceptedByRemote
```

```bash
tnsaxis:Call/StateData: CallState=Active
```

When the call is ended, the Axis product emits a call state change event with reason `Terminate`. The call state property event changes state to `Idle`.

```bash
tnsaxis:Call/StateChangeData: Reason=Terminated
```

```bash
tnsaxis:Call/StateData: CallState=Idle
```

To retrieve all details of a call in progress, the client can use `axcall:GetCallStatus(CallId=[callid])`.

#### Incoming SIP call

An incoming SIP call is a call from a remote device to the Axis product.

When no call is in progress, the call state property event shows state `Idle`.

```bash
tnsaxis:Call/StateData: CallState=Idle
```

When the Axis product answers a call, the product emits a call state change event with reason `AcceptedByDevice`. The call state property event changes state to `Active`.

```bash
tnsaxis:Call/StateChangeData: Reason=AcceptedByDevice
```

```bash
tnsaxis:Call/StateData: CallState=Active
```

When the call is ended, the Axis product emits a call state change event with reason `Terminated`. The call state property event changes state to `Idle`.

```bash
tnsaxis:Call/StateChangeData: Reason=Terminated
```

```bash
tnsaxis:Call/StateData: CallState=Idle
```

To retrieve all details of a call in progress, the client can use `axcall:GetCallStatus(CallId=[callid])`.

#### Outgoing VMS call

An outgoing VMS call is a VMS call from the Axis product to a client.

When no call is in progress, the call state property event shows state `Idle`.

```bash
tnsaxis:Call/StateData: CallState=Idle
```

VMS calls are initiated by an `axcall:Call` request with `VMS_CALL` as recipient. The call can for example by triggered by an action rule that has a digital input event as a trigger and "make call" as the action. When the call is initiated, the Axis product emits a call state change event with reason `Initiated`. The call state property event changes state to `Calling`.

```bash
tnsaxis:Call/StateChangeData: Reason=Initiated
```

```bash
tnsaxis:Call/StateData: CallState=Calling
```

When the call is initiated, a timer starts. If the call is not answered within the specified time, the Axis product emits a call state change event with reason `NoAnswer`. The call state property event changes state to `Idle`.

```bash
tnsaxis:Call/StateChangeData: Reason=NoAnswer
```

```bash
tnsaxis:Call/StateData: CallState=Idle
```

As described in [VMS calls](#vms-calls), the client, for example a video management system, could be configured to listen to the `tnsaxis:Call/State` event. To answer the call, the client should initiate streams to receive video and audio from the Axis product and to transmit audio to the Axis product. When the Axis product detects that audio is transmitted, the product emits a call state change event with reason `AcceptedByRemote`. The call state property event changes state to `Active`.

```bash
tnsaxis:Call/StateChangeData: Reason=AcceptedByRemote
```

```bash
tnsaxis:Call/StateData: CallState=Active
```

To end the call, the client should stop transmitting audio to the Axis product. When the product detects that audio is no longer transmitted, the product emits a call state change event with reason `Terminated`. The call state property event changes state to `Idle`.

```bash
tnsaxis:Call/StateChangeData: Reason=Terminated
```

```bash
tnsaxis:Call/StateData: CallState=Idle
```

To retrieve all details of a call in progress, the client can use `axcall:GetCallStatus(CallId=[callid])`.

#### Incoming VMS call

An incoming VMS call is a VMS call from a remote device to the Axis product.

When no call is in progress, the call state property event shows state `Idle`.

```bash
tnsaxis:Call/StateData: CallState=Idle
```

To initiate a call, the client should start transmitting audio to the Axis product. When the Axis product detects that audio is transmitted, the product emits a call state change event with reason `AcceptedByDevice`. The call state property event changes state to `Active`.

```bash
tnsaxis:Call/StateChangeData: Reason=AcceptedByDevice
```

```bash
tnsaxis:Call/StateData: CallState=Active
```

To end the call, the client should stop transmitting audio to the Axis product. When the product detects that audio is no longer transmitted, the product emits a call state change event with reason `Terminated`. The call state property event changes state to `Idle`.

```bash
tnsaxis:Call/StateChangeData: Reason=Terminated
```

```bash
tnsaxis:Call/StateData: CallState=Idle
```

To retrieve all details of a call in progress, the client can use `axcall:GetCallStatus(CallId=[callid])`.

## Service capabilities

**ServiceCapabilities**

The `ServiceCapabilities` data structure describes the available service capabilities.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `MaxLimit` | Integer | The maximum number of entries returned by the `GetPortList` and `GetPort` commands. |

### Data structures
#### ServiceCapabilities

The `ServiceCapabilities` data structure shows the available service capabilities.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `SIP` | Boolean | `true` = SIP operations are supported.`false` = SIP operations are not supported. |
| `DTMF` | Boolean | `true` = DTMF operations are supported.`false` = DTMF operations are not supported. |
| `AudioCodec` | Boolean | Supported from API version 1.4.`true` = Audio codec operations are supported.`false` = Audio codec operations are not supported.Audio codec operations include getting and setting the audio codec priority list. |
| `MediaEncryption` | Boolean | Supported from API version 1.7.`true` = Media encryption operations are supported.`false` = Media encryption operations are not supported. |
| `Certificate` | Boolean | Supported from API version 1.7.`true` = Certificate operations are supported.`false` = Certificate operations are not supported. |
| `Attribute` | Boolean | Supported from API version 1.7.`true` = Attribute operations for SIP accounts and SIP configurations are supported.`false` = Attribute operations for SIP accounts and SIP configurations are not supported. |

### GetServiceCapabilities command

Use the `GetServiceCapabilities` command to retrieve the capabilities supported by the service.

-   **Command**: `axcall:GetServiceCapabilities`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "Capabilities": { ServiceCapabilities }}
```

with the following data fields:

| Data field | Description |
| --- | --- |
| `Capabilities` | The `ServiceCapabilities` data structure. See [ServiceCapabilities](#servicecapabilities). |

## Call control

The Call service supports the following operations to control calls:

-   `Call` – Make a call.
-   `TerminateCall` – Terminate an ongoing call.

### Call command

Use the `Call` command to make a call. The request returns a call identifier `CallId` which is used to identify the call.

-   **Command**: `axcall:Call`

Message name: Request

```bash
{  "SIPAccountId": "<SIPAccountId>" (optional),  "To": "<string>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | Optional. The SIP account to use to make the call. If not specified, the default account is used. |
| `To` | String | The address to call to.For peer-to-peer SIP calls, use `sip:ip` where `ip` is the IP address or host name of the peer to call to.For SIP calls, use `sip:user@domain`For VMS calls, use `VMS_CALL`. |

Message name: Response

```bash
{    "CallId": "<CallId>"}
```

with the following data fields:

| Data field | Description |
| --- | --- |
| `CallId` | Call identifier. |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to initiate the call. |

### TerminateCall command

Use the `TerminateCall` command to terminate an ongoing call.

-   **Command**: `axcall:TerminateCall`

Message name: Request

```bash
{    "CallId": "<CallId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `CallId` | `CallId` | Call identifier. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no ongoing call with the specified `CallId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to terminate the call. |

## Call status

Call status shows information about current and previous calls.

### Data structures
#### CallId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `CallId` | String | minLength=0 maxLength=64 | The call identifier. |

#### CallStatus

The `CallStatus` data structure contains current aggregate runtime status of calls in progress and of recently terminated calls.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `CallId` | `CallId` | Call identifier. |
| `Source` | String | Media source used for the call.Example: For multichannel products, `Source` is the video channel from which the call is coming. |
| `CallState` | `CallState` | State of the call. See [Enumeration: CallState](#enumeration-callstate). |
| `CallStateReason` | String | Describes why the call is in the current state. See [Enumeration: CallStateChangeReason](#enumeration-callstatechangereason). |
| `StartTime` | `dateTime` | Start time of the call. |
| `Direction` | `CallDirection` | Direction of the call. See [Enumeration: CallDirection](#enumeration-calldirection). |
| `DeviceURI` | String | The Axis product’s address. |
| `RemoteURI` | String | The remote device’s address. |
| `CallType` | String | The type of call. See [Enumeration: CallType](#enumeration-calltype). |
| Optional fields |  |  |
| `StopTime` | `dateTime` | End time of the call. Only available for terminated calls. |
| `AudioCodec` | String | Audio codec used for the call. |
| `VideoCodec` | String | Video codec used for the call. |
| `SIPAccountId` | `SIPAccountId` | The SIP account used for the call. |

#### Enumeration: CallState

`CallState` is the overall status of the call.

| `CallState` **value** | Description |
| --- | --- |
| `Idle` | No call in progress. |
| `Calling` | The call is initiated. The Axis product is calling a remote device. The call is not yet answered. |
| `Active` | The call is active. |
| `Terminating` | A call is being terminated |
| `Terminated` | The call is terminated. |

#### Enumeration: CallStateChangeReason

`CallStateChangeReason` is a non-normative enum used to describe different reasons for call status change events.

| `CallStateChangeReason` **value** | State change | Description |
| --- | --- | --- |
| `Initiated` | From `Idle` to `Calling`. | The call is initiated. |
| `Denied` | From `Idle` to `Terminated`. | An incoming call is denied by the `AllowIncomingCalls` rule. |
| `NoAnswer` | From `Calling` to `Terminated`. | The call is not answered. The state changes to `Terminated` when the call times out.For VMS calls, the timeout is defined in the `VMSCallConfiguration` data structure. |
| `Busy` | From `Calling` to `Terminated`. | Line is busy. |
| `Failed` | From `Calling` to `Terminated`. | Call failed. This value is returned if the call failed for reasons other than `NoAnswer` and `Busy`. |
| `AcceptedByRemote` | From `Calling` to `Active`. | The remote device answers the call. |
| `AcceptedByDevice` | From `Calling` to `Active`. | The Axis product answers an incoming call. |
| `Terminated` | From `Active` to `Terminated`. | An active call is terminated. |

#### Enumeration: CallDirection

`CallDirection` contains the direction of the call.

| `CallDirection` **value** | Description |
| --- | --- |
| `Outgoing` | A call from the Axis product to a remote device. |
| `Incoming` | A call from a remote device to the Axis product. |

#### Enumeration: CallType

`CallType` is a non-normative enum that specifies the type of call. More values might be added in the future.

| `CallType` **value** | Description |
| --- | --- |
| `SIP` | SIP call. A SIP call is a call to a SIP URI. |
| `VMS` | VMS call. A VMS call is a simulated call. See [VMS calls](#vms-calls).In the `axcall:Call` command, the `To` field should be set to `VMS_CALL`. See [Call command](#call-command). |

### GetCallStatus command

Use the `GetCallStatus` command to request the current `CallStatus` of a given call. The call is specified by its `CallId`.

-   **Command**: `axcall:GetCallStatus`

Message name: Request

```bash
{    "CallId": "<CallId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `CallId` | `CallId` | Call identifier. |

Message name: Response

```bash
{  "CallStatus": { CallStatus }}
```

with the following data fields:

| Data field | Description |
| --- | --- |
| `CallStatus` | The `CallStatus` data structure. See [CallStatus](#callstatus). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no call with the specified `CallId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to get the `CallStatus`. |

### GetCallStatuses command

Use the `GetCallStatuses` command to request the current `CallStatus` for multiple calls. The calls are specified by a list of `CallId`:s. If no `CalllId`:s are specified, the `CallStatus` for all calls with be returned. If a `CallId` cannot be resolved, the `CallId` is ignored.

-   **Command**: `axcall:GetCallStatuses`

Message name: Request

```bash
{  "CallId": \["<CallId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `CallId` | List of `CallId` | A list of call identifiers. |

Message name: Response

```bash
{  "CallStatus": \[{ CallStatus }, ...\]}
```

with the following data fields:

| Data field | Description |
| --- | --- |
| `CallStatus` | A list of `CallStatus` data structures. See [CallStatus](#callstatus). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to get the `CallStatus`. |

## SIP configuration
### Data structures
#### SIPConfiguration

The `SIPConfiguration` data structure contains the SIP configuration.

Optional fields:

| Field | Type | Description |
| --- | --- | --- |
| `SIPEnabled` | Boolean | `true` = SIP is enabled.  
`false` = SIP is disabled.  
Default: `false` |
| `SIPPort` | Integer | The port used for incoming SIP requests. Traffic through this port is not encrypted.  
Default: `5060` |
| `SIPTLSPort` | Integer | The port used for incoming SIPS and TLS-secured SIP requests. Traffic through this port is encrypted using TLS.  
Default: `5061` |
| `STUNEnabled` | Boolean | `true` = STUN is enabled.  
`false` = STUN is disabled.  
Default: `false` |
| `STUNServers` | `STUNServer` | List of STUN servers.See [STUNServer](#stunserver). |
| `TURNEnabled` | Boolean | `true` = TURN is enabled.  
`false` = TURN is disabled.  
Default: `false` |
| `TURNServers` | `TURNServer` | List of TURN servers.See [TURNServer](#turnserver). |
| `ICEEnabled` | Boolean | `true` = ICE is enabled.  
`false` = ICE is disabled.  
Default: `false` |
| `AllowIncomingCalls` | Boolean | `true` = Incoming calls are enabled.  
`false` = Incoming calls are disabled.  
Default: `false` |
| `ApplyUserAuthentication` | Boolean | For future use. Enable user authentication when requesting video and audio streams and when using DTMF capabilities. |
| `AllowedUsers` | `UserAuthentication` | For future use. Array of allowed users. Unauthorized users are denied DTMF capabilities in SIP calls. |
| `ApplyAllowedURIs` | Boolean | Deprecated. Use `ApplyAccessList` instead. |
| `AllowedURIs` | String | Deprecated. Use `AccessList` instead. |
| `Attribute` | `Attribute` | Attributes for additional configuration. Use `GetSupportedSIPConfigurationAttributes` to list the supported attributes. |
| `RTPStartPort` | Integer | Supported from API version 1.6.RTP start port for media streams in SIP calls. This setting affects SIP calls only. It does not affect other media streams.Default: 4000 |
| `CallingTimeout` | Integer | Supported from API version 1.7.The number of seconds to wait before an initiated call terminates with `NoAnswer`.Default value: 60 secondsMaximum value: 600 seconds |
| `ApplyAccessList` | Boolean | `true`: Enables use of `AccessList`. |
| `AccessList` | String | A list of SIP URIs. Whether it is an allowlist or blocklist is specified in `AccessListPolicy`. |
| `AccessListPolicy` | String | Enum values: `Allow`, `Block`  
`Allow`: Use `AccessList` as an allowlist. Allow incoming calls from the specified URIs.  
`Block`: Use `AccessList` as a blocklist. Decline incoming calls from the specified URIs.  
Null: Default to `Allow`. |

#### Enumeration: SIPTransport

`SIPTransport` is a non-normative enum used to specify the protocol to be used for SIP transport.

| `SIPTransport` **value** | Description |
| --- | --- |
| `udp` | UDP protocol. |
| `tcp` | TCP protocol. |
| `tls` | TLS protocol. |

#### STUNServer

The `STUNServer` data structure contains the STUN server configuration.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Server` | String | Address (URI) to the STUN server. |

#### TURNServer

The `TURNServer` data structure contains the TURN server configuration.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Server` | String | Address (URI) to the TURN server. |
| `Username` | String | User name for the TURN server. |
| `Password` | String | Password for the TURN server user. |

#### Attribute

The `Attribute` data structure contains an attribute’s name and value. Attributes are additional configuration information for SIP accounts or SIP configurations.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | Attribute name. |
| `Value` | String | Attribute value. |

#### Enumeration: AttributeType

`AttributeType` is a non-normative enum that specifies the attribute types.

| `AttributeType` **value** | Description |
| --- | --- |
| `string` | String. |
| `int` | Integer. |
| `bool` | Booelan. |

#### AttributeInfo

The `AttributeInfo` data structure contains information about an attribute. Attributes are additional configuration information for SIP accounts or SIP configurations.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | Attribute name. |
| `Type` | String | Attribute type. Available values are defined by `AttributeType`. |
| Optional fields |  |  |
| `Default` | String | The attribute’s default value. |

### GetSupportedSIPConfigurationAttributes command

Use the `GetSupportedSIPConfigurationAttributes`command to list supported attributes for the SIP configuration.

-   **Command**: `axcall:GetSupportedSIPConfigurationAttributes`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "AttributeInfo": \[{ AttributeInfo },...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `AttributeInfo` | `AttributeInfo` | List of supported attributes. |

### GetSIPConfiguration command

Use the `GetSIPConfiguration` command to retrieve the current SIP configuration.

-   **Command**: `axcall:GetSIPConfiguration`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "SIPConfiguration": { SIPConfiguration }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPConfiguration` | `SIPConfiguration` | The requested `SIPConfiguration`.See [SIPConfiguration](#sipconfiguration). |

### SetSIPConfiguration command

Use the `SetSIPConfiguration` command to update the current SIP configuration. See [SIPConfiguration](#sipconfiguration).

-   **Command**: `axcall:SetSIPConfiguration`

Message name: Request

```bash
{  "SIPConfiguration": { SIPConfiguration }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPConfiguration` | `SIPConfiguration` | The `SIPConfiguration` to update. |
| `KeepCurrent` | `true`, `false` | `true`: Use the current values for those not specified in `SIPConfiguration`.  
`false`: Set to default for those not specified in `SIPConfiguration`.  
Null: Default to `true`. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The action is not supported. |

## SIP accounts
### Data structures
#### SIPAccount

The `SIPAccount` data structure defines the SIP account.

A SIP client is identified by its address-of-record (AOR). The AOR is a SIP or SIPS URI and can be thought of as the client’s public address. The AOR can have different formats:

-   `sip:username@publicdomain:port` is a typically format when using a PBX or SIP provider.
-   `sip:192.168.0.90` or `sip:sip.axis.com` can be used for direct client-to-client communication using peer-to-peer accounts. The IPv6 address format contains brackets, for instance sip:\[fd12:3456:789a:1::90\]:5060.

The data fields specified below are used to construct an AOR for the client, for example, `sip | sips:UserId[@Domain]`, where the SIP/SIPS prefix is derived from `SIPSEnabled`, where `UserId` is mandatory and where `Domain` is derived from `PublicDomain` or `Registrar` if `PublicDomain` is not specified.

`Registrar` is used when registering the SIP account at a SIP registrar. If `Registrar` is empty, `PublicDomain` is used for registration. If `Registrar` and `PublicDomain` both are empty, the account will not be registered.

A default account with identifier `peer-to-peer` is created automatically when the Axis product is restarted after factory default or if all accounts are removed.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `UserId` | String | User name for registration in the SIP registrar. The name can be an extension in the SIP registrar. |
| `Password` | String | Password for the `UserId`. |
| `Registrar` | String | Address to the SIP registrar used for registration. |
| `PublicDomain` | String | The SIP registrar’s public domain. |
| `SIPProxies` | `SIPProxy` | List of SIP proxies to use for outgoing calls from this account. |
| `Attribute` | `Attribute` | Attributes for additional configuration. Use `GetSupportedSIPAccountAttributes` to list the supported attributes. |
| Optional fields |  |  |
| `Id` | `SIPAccountId` | Identifier for the SIP account. If empty or missing, `Id` is created automatically when the SIP account is created.See also [SIPAccountId](#sipaccountid). |
| `Enabled` | Boolean | Defaults to `true` if account is enabled. |
| `Name` | `Name` | Descriptive name for the SIP account. The name is displayed in the Axis product’s user interface. |
| `CallerId` | String | `CallerId` (caller identifier) used in SIP. |
| `AuthenticationId` | String | Authentication identifier used in the registration. If empty, `AuthenticationId` is set to `UserId`. |
| `SecondaryRegistrar` | String | Supported from API version 1.9.Address of secondary registrar (backup). Optional parameter, defaults to empty string. |
| `SecondaryPublicDomain` | String | Supported from API version 1.9.Public Domain of the secondary registrar (backup). Optional parameter, defaults to empty string. |
| `IsDefault` | Boolean | `true` = The account is the default SIP account.`false` = The account is not the default account. Only one account can be the default account. If multiple accounts are set to default, the last account set to default is used. |
| `SIPSEnabled` | Boolean | `true` = SIPS (secure SIP) is enabled. If enabled, `Transport` is set to `tls`.`false` = SIPS is disabled, that is, SIP is used. |
| `Transport` | String | The transport protocol to use for calls made from and to this account. For valid values, see [Enumeration: SIPTransport](#enumeration-siptransport).If `SIPSEnabled=true`, `Transport` will be set to `tls`. |
| `PrioritizeIPv6` | Boolean | True if IPv6 should be prioritized over IPv4. The default value is `disabled`, which means that IPv4 is prioritized). This is relevant for peer-to-peer accounts and domain-names, which resolve in IPv4 and IPv6 addresses. An account can either use IPv4 or IPv6 media transports. Adding an account will check the network availability and change this flag if required. |
| `StreamParameters` | String | Percent-encoded stream parameters. If empty, default stream parameters are used.Supported stream parameters in API release 1.6: `resolution` = Resolution. `fps` = Frame rate. |
| `AllowMWI` | Boolean | `true` = Allow a SIP server to convey updated listen port using MWI (Message Waiting Indication).`false` = Allow MWI disabled.Default: `false` |
| `DTMFConfigurationId` | `DTMFConfigurationId` | Identifier for the `DTMFConfiguration` associated with the account.Default: Empty string. |
| `MediaEncryption` | String | Supported from API version 1.7.Media encryption preference to use for calls from this account. For valid values, see [Enumeration: MediaEncryption](#enumeration-mediaencryption).If media encryption is enabled, that is, if `MediaEncryption` is not set to `None`, then `Transport` must be set to `tls`. |
| `Certificate` | String | Supported from API version 1.7.The TLS transport certificate to use. This value is used for all TLS-enabled accounts. |
| `EncryptionProtocols` | String | Supported from API version 1.7.Comma-separated list of allowed encryption protocols. This value is used for all TLS-enabled accounts. For valid values, see [Enumeration: EncryptionProtocol](#enumeration-encryptionprotocol). |
| `VerifyServerCertificate` | Boolean | Supported from API version 1.7.`true` = The remote server’s certificate should be verified.`false` = The remote server’s certificate should not be verified.This value is used for all TLS-enabled accounts. |

#### SIPAccountId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `SIPAccountId` | String | minLength=0 maxLength=64 | The SIP account identifier. |

#### SIPProxy

The `SIPProxy` data structure contains the configuration for a SIP proxy server.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Server` | String | Address (URI) to the SIP proxy server. |
| `Username` | String | User name for the proxy server. |
| `Password` | String | Password for the proxy server user. |

#### Enumeration: MediaEncryption

`MediaEncryption` is a non-normative enum specifying encryption preferences for SIP media traffic. To use media encryption, `SIPTransport` must be set to `TLS`. If there are several peer-to-peer accounts with different `MediaEncryption` values, the strictest value is used for all accounts.

| `MediaEncryption` **value** | Description |
| --- | --- |
| `None` | Media encryption is disabled. SIP media traffic is unencrypted. |
| `SRTPBestEffort` | SIP media traffic is encrypted through SRTP when the call receiver supports SRTP. |
| `SRTPMandatory` | SIP media traffic is encrypted through SRTP. If the call receiver does not support SRTP, the call is not initiated. |

#### Enumeration: EncryptionProtocol

`EncryptionProtocol` is a non-normative enum specifies the encryption protocol to use.

| `EncryptionProtocol` **value** | Description |
| --- | --- |
| `TLSv1` | TLSv1.0 |
| `TLSv11` | TLSv1.1 |
| `TLSv12` | TLSv1.2 |

### GetSupportedMediaEncryptionModes command

Use the `GetSupportedMediaEncryptionModes` command to list supported media encryption modes.

-   **Command**: `axcall:GetSupportedMediaEncryptionModes`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "MediaEncryption": \["<string>",...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `MediaEncryption` | List of strings | List of supported media encryption modes. |

### GetSupportedSIPAccountAttributes command

Use the `GetSupportedSIPAccountAttributes`command to list supported attributes for the SIP account.

If an attempt is made to set an attribute which is not implemented, that attribute is silently ignored.

-   **Command**: `axcall:GetSupportedSIPAccountAttributes`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "AttributeInfo": \[{ AttributeInfo },...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `AttributeInfo` | `AttributeInfo` | List of supported attributes. |
| `DisableTCPSwitch` | Boolean | SIP can temporarily switch transport protocol from UDP to TCP, if a request is within 200 bytes of the MTU or larger than 1300 bytes, to avoid fragmentation. For systems not listening to SIP traffic over TCP, this setting can be disabled to enhance compatibility. |
| `MaxCallDuration` | Integer (in seconds) | This setting causes the device to hang up SIP calls automatically if they last longer than the specified amount of time. This has no effect on VMS calls. |
| `RegistrationInterval` | Integer (in secods) | This setting controls the re-registration interval when registering to a PBX. |

### GetSIPAccount command

Use the `GetSIPAccount` command to retrieve the settings for a SIP account. This request is used for single SIP accounts. To retrieve multiple accounts, use `GetSIPAccounts`, see [GetSIPAccounts command](#getsipaccounts-command).

-   **Command**: `axcall:GetSIPAccount`

Message name: Request

```bash
{    "SIPAccountId": "<SIPAccountId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | The identifier of the SIP account to retrieve. |

Message name: Response

```bash
{  "SIPAccount": { SIPAccount }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccount` | `SIPAccount` | The requested `SIPAccount`.See [SIPAccount](#sipaccount). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no SIP account with the supplied `SIPAccountId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the SIP account. |

### GetSIPAccounts command

Use the `GetSIPAccounts` command to retrieve the settings for multiple SIP accounts. To retrieve the settings for a single account, use `GetSIPAccount`, see [GetSIPAccount command](#getsipaccount-command).

A SIP account is specified by its `SIPAccountId`. If a `SIPAccountId` in the list cannot be resolved, that `SIPAccountId` is ignored. If there are no valid `SIPAccountId`:s, the request returns an empty set.

A request without any specified `SIPAccountId`:s returns settings for all SIP accounts.

-   **Command**: `axcall:GetSIPAccounts`

Message name: Request

```bash
{  "SIPAccountId": \["<SIPAccountId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | List of `SIPAccountId` | A list of the identifiers of the SIP accounts to retrieve. |

Message name: Response

```bash
{  "SIPAccount": \[{ SIPAccount }, ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccount` | List of `SIPAccount` | The returned `SIPAccount`:s.See [SIPAccount](#sipaccount). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the SIP accounts. |

### SetSIPAccount command

Use the `SetSIPAccount` command to add or update a SIP account. This request is used for single SIP accounts. To add or update multiple accounts, use `SetSIPAccounts`, see [SetSIPAccounts command](#setsipaccounts-command).

If the supplied `SIPAccountId` matches an existing SIP account, the SIP account is updated. Otherwise, a new SIP account is created.

-   **Command**: `axcall:SetSIPAccount`

Message name: Request

```bash
{  "SIPAccount": { SIPAccount }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccount` | `SIPAccount` | The `SIPAccount` to add or update.See [SIPAccount](#sipaccount). |

Message name: Response

```bash
{    "SIPAccountId": "<SIPAccountId>"}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | The `SIPAccountId` of the added or updated account.See [SIPAccountId](#sipaccountid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### SetSIPAccounts command

Use the `SetSIPAccounts` command to add or update multiple SIP accounts. To update a single SIP account, use `SetSIPAccount`, see [SetSIPAccount command](#setsipaccount-command).

If a supplied `SIPAccountId` matches an existing SIP account, the SIP account is updated. Otherwise, a new SIP account is created.

-   **Command**: `axcall:SetSIPAccounts`

Message name: Request

```bash
{  "SIPAccount": \[{ SIPAccount }, ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccount` | List of `SIPAccount` | The `SIPAccount` data structures to add or update.See [SIPAccount](#sipaccount). |

Message name: Response

```bash
{  "SIPAccountId": \["<SIPAccountId>", ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccountId` | List of `SIPAccountId` | The `SIPAccountId`:s of the added or updated accounts.See [SIPAccountId](#sipaccountid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### RemoveSIPAccount command

Use the `RemoveSIPAccount` command to remove a SIP account. This request removes a single account. To remove multiple accounts, use `RemoveSIPAccounts`, see [RemoveSIPAccounts command](#removesipaccounts-command).

If the `SIPAccountId` cannot be resolved, the request is ignored.

-   **Command**: `axcall:RemoveSIPAccount`

Message name: Request

```bash
{    "SIPAccountId": "<SIPAccountId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | The identifier of the SIP account to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the SIP account. |

### RemoveSIPAccounts command

Use the `RemoveSIPAccounts` command to remove multiple SIP accounts. To remove a single account, use `RemoveSIPAccount`, see [RemoveSIPAccount command](#removesipaccount-command).

If a `SIPAccountId` cannot be resolved, that `SIPAccountId` is ignored.

-   **Command**: `axcall:RemoveSIPAccounts`

Message name: Request

```bash
{  "SIPAccountId": \["<SIPAccountId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | List of `SIPAccountId` | The identifiers of the SIP accounts to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the SIP accounts. |

## SIP account status
### Data structures
#### SIPAccountStatus

The `SIPAccountStatus` data structure contains current aggregate runtime status of a SIP account.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | SIP account identifier. See [SIPAccountId](#sipaccountid). |
| `SIPURI` | String | SIP address associated with the account. |
| `RegURI` | String | URI for the SIP registrar.If the account is not registered, `RegURI` is empty. |
| `Status` | Integer | SIP response code from the SIP registrar.If the account is not registered, `Status` is 0. |
| `StatusText` | String | SIP response phrase from the SIP registrar or one of the following:`Does not register` = The account is not registered.`SIP disabled` = SIP is disabled. |

### GetSIPAccountStatus command

Use the `GetSIPAccountStatus` command to retrieve the current status of a SIP account. This request is used for single SIP accounts. To retrieve multiple accounts, use `GetSIPAccountStatuses`, see [GetSIPAccountStatuses command](#getsipaccountstatuses-command).

-   **Command**: `axcall:GetSIPAccountStatus`

Message name: Request

```bash
{    "SIPAccountId": "<SIPAccountId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | `SIPAccountId` | The identifier of the SIP account to retrieve. |

Message name: Response

```bash
{  "SIPAccountStatus": { SIPAccountStatus }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccountStatus` | `SIPAccountStatus` | The account’s `SIPAccountStatus`.See [SIPAccountStatus](#sipaccountstatus). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no SIP account with the supplied `SIPAccountId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the SIP account status. |

### GetSIPAccountStatuses command

Use the `GetSIPAccountStatuses` command to retrieve the current statuses of multiple SIP accounts. To retrieve the status of a single SIP account, use `GetSIPAccountStatus`, see [GetSIPAccountStatus command](#getsipaccountstatus-command).

A SIP account is specified by its `SIPAccountId`. If a `SIPAccountId` in the list cannot be resolved, that `SIPAccountId` is ignored. If there are no valid `SIPAccountId`:s, the request returns an empty set.

A request without any specified `SIPAccountId`:s returns statuses for all SIP accounts.

-   **Command**: `axcall:GetSIPAccountStatuses`

Message name: Request

```bash
{  "SIPAccountId": \["<SIPAccountId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SIPAccountId` | List of `SIPAccountId` | The identifiers of the SIP accounts to retrieve. |

Message name: Response

```bash
{  "SIPAccountStatus": \[{ SIPAccountStatus }, ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `SIPAccountStatus` | List of `SIPAccountStatus` | The `SIPAccountStatus` for the requested accounts.See [SIPAccountStatus](#sipaccountstatus). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the SIP account statuses. |

## DTMF configuration
### Data structures
#### DTMFConfigurationId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `DTMFConfigurationId` | String | minLength=0 maxLength=64 | The DTMF configuration identifier. |

#### DTMFSequence

| Parameter | Type | Valid values | Allowed characters | Description |
| --- | --- | --- | --- | --- |
| `DTMFSequence` | String | minLength=0 maxLength=64 | 0–9, A-D, \*, # | Specifies a DTMF sequence. |

#### DTMFConfiguration

The `DTMFConfiguration` data structure contains the DTMF configuration.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | `Name` | Descriptive name for the DTMF configuration. |
| `DTMFTriggerId` | List of `DTMFTriggerId` | List of identifiers for the DTMF triggers that are associated with the configuration.See [DTMFTriggerId](#dtmftriggerid). |
| Optional fields |  |  |
| `Id` | `DTMFConfigurationId` | Identifier for the DTMF configuration. If empty or missing, `Id` is created automatically.See [DTMFConfigurationId](#dtmfconfigurationid). |
| `RFC2833` | Boolean | `true` = DTMF over RTP (RFC 2833) is enabled.`false` = DTMF over RTP is disabled.Default: `true` |
| `RFC2976` | Boolean | `true` = DTMF over SIP INFO (RFC 2976) is enabled.`false` = DTMF over SIP INFO is disabled.Default: `true` |

### GetDTMFConfiguration command

Use the `GetDTMFConfiguration` command to retrieve the settings for a DTMF configuration. This request is used for single DTMF configurations. To retrieve multiple configurations, use `GetDTMFConfigurations`, see [GetDTMFConfigurations command](#getdtmfconfigurations-command).

-   **Command**: `axcall:GetDTMFConfiguration`

Message name: Request

```bash
{    "DTMFConfigurationId": "<DTMFConfigurationId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | `DTMFConfigurationId` | The identifier of the DTMF configuration to retrieve.See [DTMFConfigurationId](#dtmfconfigurationid). |

Message name: Response

```bash
{  "DTMFConfiguration": { DTMFConfiguration }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFConfiguration` | `DTMFConfiguration` | The requested `DTMFConfiguration`.See [DTMFConfiguration](#dtmfconfiguration). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no DTMF configuration with the supplied `DTMFConfigurationId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF configuration. |

### GetDTMFConfigurations command

Use the `GetDTMFConfigurations` command to retrieve the settings for multiple DTMF configurations. To retrieve the settings for a single configuration, use `GetDTMFConfiguration`, see [GetDTMFConfiguration command](#getdtmfconfiguration-command).

A DTMF configuration is specified by its `DTMFConfigurationId`. If a `DTMFConfigurationId` in the list cannot be resolved, that `DTMFConfigurationId` is ignored. If there are no valid `DTMFConfigurationId`:s, the request returns an empty set.

A request without any specified `DTMFConfigurationId`:s returns all DTMF configurations.

-   **Command**: `axcall:GetDTMFConfigurations`

Message name: Request

```bash
{  "DTMFConfigurationId": \["<DTMFConfigurationId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | List of `DTMFConfigurationId` | A list of the identifiers of the DTMF configurations to retrieve. |

Message name: Response

```bash
{  "DTMFConfiguration": \[{ DTMFConfiguration }, ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFConfiguration` | List of `DTMFConfiguration` | The returned `DTMFConfiguration`:s.See [DTMFConfiguration](#dtmfconfiguration). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF configurations. |

### SetDTMFConfiguration command

Use the `SetDTMFConfiguration` command to add or update a DTMF configuration. This request is used for single DTMF configurations. To add or update multiple configurations, use `SetDTMFConfigurations`, see [SetDTMFConfigurations command](#setdtmfconfigurations-command).

If the supplied `DTMFConfigurationId` matches an existing DTMF configuration, the DTMF configuration is updated. Otherwise, a new DTMF configuration is created.

-   **Command**: `axcall:SetDTMFConfiguration`

Message name: Request

```bash
{  "DTMFConfiguration": { DTMFConfiguration }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfiguration` | `DTMFConfiguration` | The `DTMFConfiguration` to add or update.See [DTMFConfiguration](#dtmfconfiguration). |

Message name: Response

```bash
{    "DTMFConfigurationId": "<DTMFConfigurationId>"}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | `DTMFConfigurationId` | The `DTMFConfigurationId` of the added or updated configuration.See [DTMFConfigurationId](#dtmfconfigurationid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### SetDTMFConfigurations command

Use the `SetDTMFConfigurations` command to add or update multiple DTMF configurations. To update a single DTMF configuration, use `SetDTMFConfiguration`, see [SetDTMFConfiguration command](#setdtmfconfiguration-command).

If a supplied `DTMFConfigurationId` matches an existing DTMF configuration, the DTMF configuration is updated. Otherwise, a new DTMF configuration is created.

-   **Command**: `axcall:SetDTMFConfigurations`

Message name: Request

```bash
{  "DTMFConfiguration": \[{ DTMFConfiguration }, ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfiguration` | List of `DTMFConfiguration` | The `DTMFConfiguration` data structures to add or update.See [DTMFConfiguration](#dtmfconfiguration). |

Message name: Response

```bash
{  "DTMFConfigurationId": \["<DTMFConfigurationId>", ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | List of `DTMFConfigurationId` | The `DTMFConfigurationId`:s of the added or updated configurations.See [DTMFConfigurationId](#dtmfconfigurationid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### RemoveDTMFConfiguration command

Use the `RemoveDTMFConfiguration` command to remove a DTMF configuration. This request removes a single configuration. To remove multiple configurations, use `RemoveDTMFConfigurations`, see [RemoveDTMFConfigurations command](#removedtmfconfigurations-command).

A DTMF configuration is specified by its `DTMFConfigurationId`. If the supplied `DTMFConfigurationId` cannot be resolved, the request is ignored.

-   **Command**: `axcall:RemoveDTMFConfiguration`

Message name: Request

```bash
{    "DTMFConfigurationId": "<DTMFConfigurationId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | `DTMFConfigurationId` | The identifier of the DTMF configuration to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF configuration. |

### RemoveDTMFConfigurations command

Use the `RemoveDTMFConfigurations` command to remove multiple DTMF configurations. To remove a single configuration, use `RemoveDTMFConfiguration`, see [RemoveDTMFConfiguration command](#removedtmfconfiguration-command).

A DTMF configuration is specified by its `DTMFConfigurationId`. If a supplied `DTMFConfigurationId` cannot be resolved, that `DTMFConfigurationId` is ignored.

-   **Command**: `axcall:RemoveDTMFConfigurations`

Message name: Request

```bash
{  "DTMFConfigurationId": \["<DTMFConfigurationId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFConfigurationId` | List of `DTMFConfigurationId` | Identifiers of the DTMF configurations to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF configurations. |

## DTMF events
### Data structures
#### DTMFEventId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `DTMFEventId` | String | minLength=0 maxLength=64 | The DTMF event identifier. |

#### DTMFEvent

The `DTMFEvent` data structure contains the DTMF event configuration.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | `Name` | Descriptive name for the DTMF event.`Name` is used as nice name in `aev:GetEventInstances`. |
| Optional fields |  |  |
| `Id` | `DTMFEventId` | Identifier for the DTMF event. If empty or missing, `Id` is created automatically.See [DTMFEventId](#dtmfeventid). |

### GetDTMFEvent command

Use the `GetDTMFEvent` command to retrieve the settings for a DTMF event configuration. This request is used for single DTMF event configurations. To retrieve multiple event configurations, use `GetDTMFEvents`, see [GetDTMFEvents command](#getdtmfevents-command).

-   **Command**: `axcall:GetDTMFEvent`

Message name: Request

```bash
{    "DTMFEventId": "<DTMFEventId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFEventId` | `DTMFEventId` | The identifier of the DTMF event to retrieve.See [DTMFEventId](#dtmfeventid). |

Message name: Response

```bash
{  "DTMFEvent": { DTMFEvent }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFEvent` | `DTMFEvent` | The requested `DTMFEvent`.See [DTMFEvent](#dtmfevent). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no DTMF event with the supplied `DTMFEventId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF event. |

### GetDTMFEvents command

Use the `GetDTMFEvents` command to retrieve the settings for multiple DTMF event configurations. To retrieve the settings for a single event configuration, use `GetDTMFEvent`, see [GetDTMFEvent command](#getdtmfevent-command).

A DTMF event configuration is specified by its `DTMFEventId`. If a `DTMFEventId` in the list cannot be resolved, that `DTMFEventId` is ignored. If there are no valid `DTMFEventId`:s, the request returns an empty set.

A request without any specified `DTMFEventId`:s returns all DTMF event configurations.

-   **Command**: `axcall:GetDTMFEvents`

Message name: Request

```bash
{  "DTMFEventId": \["<DTMFEventId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFEventId` | List of `DTMFEventId` | A list of the identifiers of the DTMF events to retrieve. |

Message name: Response

```bash
{  "DTMFEvent": \[{ DTMFEvent }, ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFEvent` | List of `DTMFEvent` | The returned `DTMFEvent`:s.See [DTMFEvent](#dtmfevent). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF events. |

### SetDTMFEvent command

Use the `SetDTMFEvent` command to add or update a DTMF event configuration. This request is used for single DTMF event configurations. To add or update multiple event configurations, use `SetDTMFEvents`, see [SetDTMFEvents command](#setdtmfevents-command).

If the supplied `DTMFEventId` matches an existing DTMF event configuration, the event configuration is updated. Otherwise, a new event configuration is created.

-   **Command**: `axcall:SetDTMFEvent`

Message name: Request

```bash
{  "DTMFEvent": { DTMFEvent }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMEvent` | `DTMFEvent` | The `DTMFEvent` to add or update.See [DTMFEvent](#dtmfevent). |

Message name: Response

```bash
{    "DTMFEventId": "<DTMFEventId>"}
```

with the following data fields:

| Data field | Data types | Description |
| --- | --- | --- |
| `DTMFEventId` | `DTMFEventId` | The `DTMFEventId` of the added or updated event configuration.See [DTMFEventId](#dtmfeventid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### SetDTMFEvents command

Use the `SetDTMFEvents` command to add or update multiple DTMF event configurations. To update a single DTMF event configuration, use `SetDTMFEvent`, see [SetDTMFEvent command](#setdtmfevent-command).

If a supplied `DTMFEventId` matches an existing DTMF event configuration, the event configuration is updated. Otherwise, a new event configuration is created.

-   **Command**: `axcall:SetDTMFEvents`

Message name: Request

```bash
{  "DTMFEvent": \[{ DTMFEvent }, ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFEvent` | List of `DTMFEvent` | The `DTMFEvent` data structures to add or update.See [DTMFEvent](#dtmfevent). |

Message name: Response

```bash
{  "DTMFEventId": \["<DTMFEventId>", ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFEventId` | List of `DTMFEventId` | The `DTMFEventId`:s of the added or updated event configurations.See [DTMFEventId](#dtmfeventid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### RemoveDTMFEvent command

Use the `RemoveDTMFEvent` command to remove a DTMF event configuration. This request removes a single DTMF event configuration. To remove multiple event configurations, use `RemoveDTMFEvents`, see [RemoveDTMFEvents command](#removedtmfevents-command).

If the `DTMFEventId` cannot be resolved, the request is ignored.

-   **Command**: `axcall:RemoveDTMFEvent`

Message name: Request

```bash
{    "DTMFEventId": "<DTMFEventId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFEventId` | `DTMFEventId` | The identifier of the DTMF event to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF event. |

### RemoveDTMFEvents command

Use the `RemoveDTMFEvents` command to remove multiple DTMF event configurations. To remove a single DTMF event configuration, use `RemoveDTMFEvent`, see [RemoveDTMFEvent command](#removedtmfevent-command).

If a `DTMFEventId` cannot be resolved, that `DTMFEventId` is ignored.

-   **Command**: `axcall:RemoveDTMFEvents`

Message name: Request

```bash
{  "DTMFEventId": \["<DTMFEventId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFEventId` | List of `DTMFEventId` | Identifiers of the DTMF events to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF events. |

## DTMF triggers
### Data structures
#### DTMFTriggerId

| Parameter | Type | Valid values | Description |
| --- | --- | --- | --- |
| `DTMFTriggerId` | String | minLength=0 maxLength=64 | The DTMF trigger identifier. |

#### DTMFTrigger

The `DTMFTrigger` data structure contains a DTMF trigger. A DTMF trigger connects a DTMF sequence to a DTMF event. Each sequence can trigger only one event.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Id` | `DTMFTriggerId` | DTMF trigger identifier.See [DTMFTriggerId](#dtmftriggerid). |
| `DTMFSequence` | `DTMFSequence` | The DTMF sequence to trigger on. Each sequence can trigger one event.See [DTMFSequence](#dtmfsequence). |
| `DTMFEventId` | `DTMFEventId` | Identifier of the DTMF event to emit when triggered.See [DTMFEventId](#dtmfeventid). |

### GetDTMFTrigger command

Use the `GetDTMFTrigger` command to retrieve the settings for a DTMF trigger. This request is used for single DTMF triggers. To retrieve multiple triggers, use `GetDTMFTriggers`, see [GetDTMFTriggers command](#getdtmftriggers-command).

-   **Command**: `axcall:GetDTMFTrigger`

Message name: Request

```bash
{    "DTMFTriggerId": "<DTMFTriggerId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFTriggerId` | `DTMFTriggerId` | The identifier of the DTMF trigger to retrieve.See [DTMFTriggerId](#dtmftriggerid). |

Message name: Response

```bash
{  "DTMFTrigger": { DTMFTrigger }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFTrigger` | `DTMFTrigger` | The requested `DTMFTrigger`.See [DTMFTrigger](#dtmftrigger). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | Not found. There is no DTMF trigger with the supplied `DTMFTriggerId`. |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF trigger. |

### GetDTMFTriggers command

Use the `GetDTMFTriggers` command to retrieve the settings for multiple DTMF triggers. To retrieve the settings for a single trigger, use `GetDTMFTrigger`, see [GetDTMFTrigger command](#getdtmftrigger-command).

A DTMF trigger is specified by its `DTMFTriggerId`. If a `DTMFTriggerId` in the list cannot be resolved, that `DTMFTriggerId` is ignored. If there are no valid `DTMFTriggerId`:s, the request returns an empty set.

A request without any specified `DTMFTriggerId`:s returns all DTMF triggers.

-   **Command**: `axcall:GetDTMFTriggers`

Message name: Request

```bash
{  "DTMFTriggerId": \["<DTMFTriggerId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFTriggerId` | List of `DTMFTriggerId` | A list of the identifiers of the DTMF triggers to retrieve. |

Message name: Response

```bash
{  "DTMFTrigger": \[{ DTMFTrigger }, ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFTrigger` | List of `DTMFTrigger` | The returned `DTMFTrigger`:s.See [DTMFTrigger](#dtmftrigger). |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to retrieve the DTMF triggers. |

### SetDTMFTrigger command

Use the `SetDTMFTrigger` command to add or update a DTMF trigger. This request is used for single DTMF triggers. To add or update multiple triggers, use `SetDTMFTriggers`, see [SetDTMFTriggers command](#setdtmftriggers-command).

If the supplied `DTMFTriggerId` matches an existing DTMF trigger, the DTMF trigger is updated. Otherwise, a new DTMF trigger is created.

If the supplied `DTMFSequence` matches the `DTMFSequence` in another DTMF trigger, the request is considered invalid.

-   **Command**: `axcall:SetDTMFTrigger`

Message name: Request

```bash
{  "DTMFTrigger": { DTMFTrigger }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMTrigger` | `DTMFTrigger` | The `DTMFTrigger` to add or update.See [DTMFTrigger](#dtmftrigger). |

Message name: Response

```bash
{    "DTMFTriggerId": "<DTMFTriggerId>"}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFTriggerId` | `DTMFTriggerId` | The `DTMFTriggerId` of the added or updated trigger.See [DTMFTriggerId](#dtmftriggerid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### SetDTMFTriggers command

Use the `SetDTMFTriggers` command to add or update multiple DTMF triggers. To update a single DTMF trigger, use `SetDTMFTrigger`, see [SetDTMFTrigger command](#setdtmftrigger-command).

If a supplied `DTMFTriggerId` matches an existing DTMF trigger, the DTMF trigger is updated. Otherwise, a new DTMF trigger is created.

If a supplied `DTMFSequence` matches the `DTMFSequence` in another DTMF trigger, the request is considered invalid.

-   **Command**: `axcall:SetDTMFTriggers`

Message name: Request

```bash
{  "DTMFTrigger": \[{ DTMFTrigger }, ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFTrigger` | List of `DTMFTrigger` | The `DTMFTrigger` data structures to add or update.See [DTMFTrigger](#dtmftrigger). |

Message name: Response

```bash
{  "DTMFTriggerId": \["<DTMFTriggerId>", ...\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `DTMFTriggerId` | List of `DTMFTriggerId` | The `DTMFTriggerId`:s of the added or updated triggers.See [DTMFTriggerId](#dtmftriggerid). |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

### RemoveDTMFTrigger command

Use the `RemoveDTMFTrigger` command to remove a DTMF trigger. This request removes a single trigger. To remove multiple triggers, use `RemoveDTMFTriggers`, see [RemoveDTMFTriggers command](#removedtmftriggers-command).

If the `DTMFTriggerId` cannot be resolved, the request is ignored.

-   **Command**: `axcall:RemoveDTMFTrigger`

Message name: Request

```bash
{    "DTMFTriggerId": "<DTMFTriggerId>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFTriggerId` | `DTMFTriggerId` | The identifier of the DTMF trigger to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF trigger. |

### RemoveDTMFTriggers command

Use the `RemoveDTMFTriggers` command to remove multiple DTMF triggers. To remove a single trigger, use `RemoveDTMFTrigger`, see [RemoveDTMFTrigger command](#removedtmftrigger-command).

If a `DTMFTriggerId` cannot be resolved, that `DTMFTriggerId` is ignored.

-   **Command**: `axcall:RemoveDTMFTriggers`

Message name: Request

```bash
{  "DTMFTriggerId": \["<DTMFTriggerId>", ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `DTMFTriggerId` | List of `DTMFTriggerId` | The identifiers of the DTMF triggers to remove. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `ter:Failure` | Failed to remove the DTMF triggers. |

## VMS call configuration

The VMS call configuration is defined by the `VMSCallConfiguration` data structure. VMS calls can be enabled and disabled and it is possible to set thresholds for the number of audio and video streams that must be started before a VMS call is considered active.

When VMS calls are enabled, the Axis product keeps track of three separate stream counts: 1) the number of audio streams sent from the product, 2) the number of audio streams sent to the product, and, 3) the number of video streams sent from the product. Each stream count is evaluated against its corresponding threshold `AudioFromDeviceToNetworkStreams`, `AudioFromNetworkToDeviceStreams` or `VideoFromDeviceToNetworkStreams`. When a stream count equals or exceeds its threshold, a VMS call is considered active and `tnsaxis:Call/State` and `tnsaxis:Call/StateChange` events are emitted.

Each stream count and its corresponding threshold are evaluated independently. If two stream counts equal or exceed their thresholds, there are two separate VMS calls.

When VMS calls are disabled, the `tnsaxis:Call/State` and `tnsaxis:Call/StateChange` events are emitted for SIP calls only.

```bash
#Axis product configurationAudioFromDeviceToNetworkStreams = 0AudioFromNetworkToDeviceStreams = 1VideoFromDeviceToNetworkStreams = 0#Streams:#One audio stream from the VMS to the Axis product#Result: One call is triggered
```

With this configuration, a call is triggered if one or more audio streams are sent from the VMS to the Axis product.

```bash
#Axis product configurationAudioFromDeviceToNetworkStreams = 0AudioFromNetworkToDeviceStreams = 1VideoFromDeviceToNetworkStreams = 0#Streams:#One video stream from the Axis product to the VMS#Result: No call is triggered
```

With this configuration, a video stream sent from the Axis product to the VMS does not trigger any call.

```bash
#Axis product configurationAudioFromDeviceToNetworkStreams = 1AudioFromNetworkToDeviceStreams = 1VideoFromDeviceToNetworkStreams = 0#Streams:#One audio stream from the VMS to the Axis product#One audio stream from the Axis product to the VMS#Result: Two calls are triggered
```

The stream counts are evaluated independently. With this configuration, two separate calls are triggered when one audio stream is sent from the Axis product to the VMS at the same time as another audio stream is sent from the VMS to the product.

```bash
#Axis product configurationAudioFromDeviceToNetworkStreams = 0AudioFromNetworkToDeviceStreams = 2VideoFromDeviceToNetworkStreams = 0#Streams:#One audio stream from the VMS to the Axis product#Result: No call is triggered
```

With this configuration, one audio stream is sent from the VMS to the Axis product does not trigger any call. Two audio streams trigger a call.

### Data structures
#### VMSCallConfiguration

The `VMSCallConfiguration` data structure defines the VMS call configuration.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Enabled` | Boolean | `true` = VMS calls are enabled.`false` = VMS calls are disabled. |
| `AudioFromDeviceToNetworkStreams` | Integer | Threshold for minimum number of audio streams from the Axis product to the VMS.If the number of streams equals or exceeds the threshold, a VMS call is considered active.If set to `0` or negative integer, the threshold is not used. |
| `AudioFromNetworkToDeviceStreams` | Integer | Threshold for minimum number of audio streams from the VMS to the Axis product.If the number of streams equals or exceeds the threshold, a VMS call is considered active.If set to `0` or negative integer, the threshold is not used. |
| `VideoFromDeviceToNetworkStreams` | Integer | Threshold for minimum number of video streams from the Axis product to the VMS.If the number of streams equals or exceeds the threshold, a VMS call is considered active.If set to `0` or negative integer, the threshold is not used. |
| `Timeout` | Integer | Supported from API version 1.5.The number of seconds to wait before an initiated call terminates with `NoAnswer`.Default: 30 seconds. |

### GetVMSCallConfiguration command

Use the `GetVMSCallConfiguration` command to retrieve the current VMS call configuration.

-   **Command**: `axcall:GetVMSCallConfiguration`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "VMSCallConfiguration": { VMSCallConfiguration }}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `VMSCallConfiguration` | `VMSCallConfiguration` | The requested `VMSCallConfiguration`.See [VMSCallConfiguration](#vmscallconfiguration). |

### SetVMSCallConfiguration command

Use the `SetVMSCallConfiguration` command to update the VMS call configuration.

-   **Command**: `axcall:SetVMSCallConfiguration`

Message name: Request

```bash
{  "VMSCallConfiguration": { VMSCallConfiguration }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `VMSCallConfiguration` | `VMSCallConfiguration` | The updated `VMSCallConfiguration`.See [VMSCallConfiguration](#vmscallconfiguration). |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The action is not supported. |

## Audio codecs

When the Axis product makes a SIP call, the call recipient receives a list of available audio codecs. The audio codecs are listed in priority order where the first codec in the list has highest priority. Use the following operations to manage the list:

-   `GetDefaultAudioCodecs` returns the Axis product’s default audio codec priority list.
-   `GetSupportedAudioCodecs` lists all audio codecs available in the Axis product.
-   `GetAudioCodecs` returns the audio codec priority list sent to call recipients.
-   `SetAudioCodecs` updates the audio codec priority list.

### Data structures {data-structures-audio-codecs}
#### AudioCodec

The `AudioCodec` data structure contains information about one supported audio codec.

Mandatory fields:

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The audio codec’s name. |
| Optional fields |  |  |
| `Options` | String | Additional parameters for the audio codec. |
| `SampleRate` | Integer | Supported sample rate.This field is returned in responses and is not required in the `SetAudioCodecs` command. |

### GetDefaultAudioCodecs command

Use the `GetDefaultAudioCodecs` command to list the Axis product’s default audio codec priority list. The first codec in the list has highest priority.

-   **Command**: `axcall:GetDefaultAudioCodecs`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "AudioCodec": \[{ AudioCodec, ... }\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `AudioCodec` | List of `AudioCodec` | `AudioCodec`:s in priority order with the highest priority first. |

### GetSupportedAudioCodecs command

Use the `GetSupportedAudioCodecs` command to list all audio codecs available in the Axis product.

-   **Command**: `axcall:GetSupportedAudioCodecs`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "AudioCodec": \[{ AudioCodec, ... }\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `AudioCodec` | List of `AudioCodec` | The returned `AudioCodec`:s |

### GetAudioCodecs command

Use the `GetAudioCodecs` command to retrieve the audio codec priority list. This is the priority list sent to call recipients. The first codec in the list has highest priority.

-   **Command**: `axcall:GetAudioCodecs`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "AudioCodec": \[{ AudioCodec, ... }\]}
```

with the following data fields:

| Data field | Data type | Description |
| --- | --- | --- |
| `AudioCodec` | List of `AudioCodec` | `AudioCodec`:s in priority order with the highest priority codec first. |

### SetAudioCodecs command

Use the `SetAudioCodecs` command to update the audio codec priority list sent to call recipients. The first codec in the list has highest priority.

-   **Command**: `axcall:SetAudioCodecs`

Message name: Request

```bash
{  "AudioCodec": \[{ AudioCodec }, ...\]}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `AudioCodec` | List of `AudioCodec` | `AudioCodec`:s in priority order with the highest priority codec first. |

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgVal` | Invalid data. The request contains invalid values. |
| `env:Sender` `ter:InvalidArgs` | Missing data. The request does not contain all required data. |

## Call state event

The current state of a call is described by the `CallState` field in the `CallStatus` data structure. When the state changes, a `tnsaxis:Call/State` event is emitted.

The event can be used to inform the caller and the call receiver about the call status. For example, by using an action rule with the play audio clip action `com.axis.action.fixed.play.audioclip`, the Axis product can play a tone while the call state is `Calling`. Using the active light action `com.axis.action.unlimited.light`, the product’s LED:s can be configured to indicate the call status, for example by flashing while a call is in progress, be steadily lit during the call and unlit when there is no ongoing call.

Use `aev:GetEventInstances` to retrieve the event declaration.

Event declaration:

```bash
<tnsaxis:Call>    <State wstop:topic="true" aev:NiceName="State">        <aev:MessageInstance aev:isProperty="true">            <aev:SourceInstance>                <aev:SimpleItemInstance Type="xsd:string" Name="Source">                    <aev:Value>\[DoorStation\]</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance Type="xsd:string" Name="CallState" isPropertyState="true">                    <aev:Value>Idle</aev:Value>                    <aev:Value>Calling</aev:Value>                    <aev:Value>Active</aev:Value>                </aev:SimpleItemInstance>            </aev:DataInstance>        </aev:MessageInstance>    </State></tnsaxis:Call>
```

The topic is `tnsaxis:Call/State`.

The `SourceInstance` specifies the device making the call.

The `DataInstance` specifies the call state. Available call states are listed in [CallStatus](#callstatus).

## Call state change event

The `tnsaxis:Call/StateChange` event is emitted when a call state changes. The event contains the following information from the `CallStatus` data structure: why the state changed, the call identifier, the Axis product’s address and the remote device’s address.

The event can be used to provide feedback to the caller and the call receiver. For example, by displaying messages in a client or by using action rules to configure the Axis product to play a special tone if the line is busy or if the call is not answered.

Use `aev:GetEventInstances` to retrieve the event declaration.

Event declaration:

```bash
<tnsaxis:Call>    <StateChange wstop:topic="true" aev:NiceName="StateChange">        <aev:MessageInstance>            <aev:SourceInstance>                <aev:SimpleItemInstance Type="xsd:string" Name="Source">                    <aev:Value>\[DoorStation\]</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance aev:NiceName="Reason" Type="xsd:string" Name="Reason">                    <aev:Value>Initiated</aev:Value>                    <aev:Value>NoAnswer</aev:Value>                    <aev:Value>Busy</aev:Value>                    <aev:Value>Denied</aev:Value>                    <aev:Value>Failed</aev:Value>                    <aev:Value>AcceptedByRemote</aev:Value>                    <aev:Value>AcceptedByDevice</aev:Value>                    <aev:Value>Terminated</aev:Value>                </aev:SimpleItemInstance>                <aev:SimpleItemInstance aev:NiceName="CallId" Type="xsd:string" Name="CallId" />                <aev:SimpleItemInstance aev:NiceName="RemoteURI" Type="xsd:string" Name="RemoteURI" />                <aev:SimpleItemInstance aev:NiceName="DeviceURI" Type="xsd:string" Name="DeviceURI" />            </aev:DataInstance>        </aev:MessageInstance>    </StateChange></tnsaxis:Call>
```

The topic is `tnsaxis:Call/StateChange`.

The `SourceInstance` specifies the device making the call.

The `DataInstance` contains four `SimpleItemInstance` fields with the `CallStateReason`, `CallId`, `RemoteURI` and `DeviceURI` from the the `CallStatus` data structure. See [Call status](#call-status). The `Reason` `SimpleItemInstance` contains the call state change reason. Available reasons are listed in [Enumeration: CallStateChangeReason](#enumeration-callstatechangereason).

## DTMF event

A DTMF event `tnsaxis:Call/DTMF` is emitted when the Axis product receives a DTMF sequence that matches a configured `DTMFEvent`.

For more information, see [Set up a DTMF event](#set-up-a-dtmf-event).

To retrieve the event declaration, use `aev:GetEventInstances`.

Event declaration:

```bash
<tnsaxis:Call>    <DTMF wstop:topic="true" aev:NiceName="DTMF">        <aev:MessageInstance>            <aev:SourceInstance>                <aev:SimpleItemInstance aev:NiceName="DTMFEventId" Type="xsd:string" Name="DTMFEventId">                    <aev:Value aev:NiceName="\[Name from axcall:DTMFEvent\]">\[Id from axcall:DTMFEvent\]</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance aev:NiceName="CallId" Type="xsd:string" Name="CallId">                    <aev:Value>\[axcall:CallId\]</aev:Value>                </aev:SimpleItemInstance>            </aev:DataInstance>        </aev:MessageInstance>    </DTMF></tnsaxis:Call>
```

The topic is `tnsaxis:Call/DTMF`.

The `SourceInstance` specifies the DTMF event. DTMF events in Axis products are set up with a `Name` and an `Id` as described in [DTMFEvent](#dtmfevent). The `Value` is the `Id` and the `Value` `NiceName` is the `Name`.

The `DataInstance` specifies the call identifier `CallId`.