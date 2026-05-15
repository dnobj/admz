---
title: Event streaming over WebSocket
url: "https://developer.axis.com/vapix/network-video/event-streaming-over-websocket/"
category: vapix
subcategory: network-video
sha256: a5a9a4c6d77c2e1815572f3f786105259f5130f89f9f341fac0dd3cdec995a0f
scraped_at: "2026-01-09T15:19:43.675Z"
page_height: 11891
---

# Event streaming over WebSocket

The VAPIX® Event streaming over WebSocket API provides a way to retrieve events produced by the Event System using the WebSocket protocol.

## Overview

The API is based on the JSON RPC style communication over WebSocket protocol with a full-duplex connection. This means that a configuration request sent by the user will chose the events that will be included in the stream.

The examples presented in this API use namespaces in their implementations. More information on how to use namespaces can be found in [Namespaces](/vapix/network-video/event-data-streaming/#namespaces) in the [Event data streaming](/vapix/network-video/event-data-streaming/) API.

**Identification**

-   **API Discovery**: `id=event-streaming-over-websocket`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Receive events over WebSocket

Axis products generate events when they need to notify the client that a state change has occurred. Some examples include motion detection or I/O port state change. These events are used to trigger an action on the client’s side. The following examples will show you how to receive events over a WebSocket connection.

#### Establish WebSocket connection

This example will show you how to establish a WebSocket connection to receive event information from your Axis device. Each connection is a separate session that will end when the connection is terminated. The sessions themselves are stateless and cannot be continued after the connection is terminated.

WebSocket connections are initiated as an HTTP handshake sequence that is upgraded to a WebSocket connection. The client should use the endpoint `ws(s)://<device>/vapix/ws-data-stream` and [digest access authentication](/vapix/authentication/#digest-access-authentication), or tokens, for the authentication.

The following example showcases a common WebSocket connection flow.

Client WebSocket handshake request

```bash
GET /vapix/ws-data-stream?sources=eventsHost: 192.168.0.90Connection: UpgradePragma: no-cacheCache-Control: no-cacheAuthorization:  Digest username="root" realm="AXIS\_ACCC8EC43707",  nonce="rMSij/TBQA=646b1c2c4c0a80a7feb4e34ef9e3422180924c37",  uri="/vapix/ws-data-stream?sources=events",  algorithm=MD5,  response="683f06da91f927fa1772c42f16597"Upgrade: websocketOrigin: chrome-extension://cbcbkhdmedgianpaifchdaddpnmgnknnSec-WebSocket-Version: 13Sec-WebSocket-Key: 1L91ICBqd8iwa0I0e6Wgzg==
```

Server handshake responses, which can be either successful or failures.

Successful handshake response

```bash
HTTP/1.1 101 Switching ProtocolsDate: Tue, 02 Nov 2021 16:09:47 GMTUpgrade: websocketConnection: UpgradeSec-WebSocket-Accept: kZ1kuOZMJmrfKnY8FvL7Tjwb0iw=Sec-WebSocket-Extensions: permessage-deflate; client\_max\_window\_bits=15
```

Failed handshake response

```bash
HTTP/1.1 401 UnauthorizedDate: Tue, 02 Nov 2021 16:09:47 GMTServer: Apache/2.4.48 (Unix) OpenSSL/1.1.1lX-Content-Type-Options: nosniffX-Frame-Options: SAMEORIGINX-XSS-Protection: 1; mode=blockWWW-Authenticate:  Digest realm="AXIS\_ACCC8EC43707",  nonce="5X26hdDPBQA=f1d9367d1b0699f406a95bbf79e35f6e08c5d3af",  algorithm=MD5,  stale=true,  qop="auth"Content-Length: <content length>Content-Type: text/html; charset=iso-8859-1
```

#### Select events to receive

This is an example of a request made by a user to select which events they want to receive through the stream. It is possible to update the filter by sending a new configuration request. Only the latest filter will be applied.

Send a configuration request with event filters

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "events:configure",    "params": {        "eventFilterList": \[            {                "topicFilter": "tns1:PTZController/tnsaxis:PTZReady"            },            {                "contentFilter": "boolean(//SimpleItem\[@Name=\\"ready\\" and @Value=\\"1\\"\])"            },            {                "topicFilter": "tns1:Device/tnsaxis:IO/VirtualPort",                "contentFilter": "boolean(//SimpleItem\[@Name=\\"port\\" and @Value=\\"1\\"\]) and boolean(//SimpleItem\[@Name=\\"state\\" and @Value=\\"0\\"\])"            }        \]    }}
```

Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "events:configure",    "data": {}}
```

Failed response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "events:configure",    "error": {        "code": 1100,        "message": "Internal Error"    }}
```

#### Event streaming

This example will show you an event and the format it will use.

```bash
{    "apiVersion": "1.0",    "method": "events:notify",    "params": {        "notification": {            "timestamp": 1639385866198,            "topic": "tns1:Device/tnsaxis:IO/VirtualPort",            "message": {                "source": {                    "port": "1"                },                "key": {},                "data": {                    "state": "0"                }            }        }    }}
```

## API specifications
### Data streaming WebSocket endpoint

This method should be used when you want to perform event streaming over a WebSocket using a common WebSocket endpoint. The endpoint location for data streaming is `ws(s)://<device>/vapix/ws-data-stream` and the WebSocket connection established on this endpoint can be used simultaneously with multiple data sources.

The data source that should be used is given as a parameter in the URL when the connection is established. Multiple data sources can be given as a comma-separated list. The URL `ws(s)://<device>/vapix/ws-data-stream?sources=events` should be used for the event streaming.

When a connection has been established, the client can send configuration requests in the JSON-RPC style defined in the following sections. Events streamed back to the client should use the same messaging style.

**Authentication**

The client need to authenticate itself before it can use the API. This can be done in one of two ways:

-   **Digest**: Digest authentication can be achieved by following the standard Digest authentication process. When authentication is performed the connection will be upgraded to a WebSocket connection.
-   **Session token**: Generate a session token and use it for authentication in cases where digest authentication isn’t supported. A session token is generated with a `GET` request to the URL `http(s)://<device>/axis-cgi/wssession.cgi`. This request itself require standard digest authentication to work. The device will respond with a session token that is valid for 15 seconds and will expire immediately when the time has passed. The token shall be used in the WebSocket connection URL as a parameter (wssession) `ws(s)://<device>/vapix/ws-data-stream?wssession=<session-token>&sources=events`, which can look like this: `wss://<device>/vapix/ws-data-stream?wssession=1331901001644832701&sources=events`

info

Please note that it is always recommended to use secure/encrypted connections with HTTPS and WSS protocols. Data transferred in clear format with HTTP and WS protocols are not secure.

### Client configuration request

This method should be used when you want to send a configuration request to the event data source.

**Request**

Client configuration request syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "events:configure",  "params": {    "eventFilterList": \[      {        "topicFilter": <string>,        "contentFilter": <string>      },      {        "topicFilter": <string>,        "contentFilter": <string>      },      {        "topicFilter": <string>,        "contentFilter": <string>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method=<string>` | The method that should be used. |
| `params=<JSON object>` | Container for the event filter list. |
| `params.eventFilterList=<list>` | A list of filters that are applied on messages from the event system. Each filter is a separate subscription, which means that an event that matches multiple filters will be sent more than once. This can be avoided by using a single filter with logical topic expression. |
| `params.eventFilterList[].topicFilter=<string>` _Optional_ | Optional if `contentFilter` exists in the configuration request. Used as subscription filter on the event system and based around `ConcreteSet TopicExpression Dialect` specified in the ONVIF Core specification. This type of filter uses namespaces like the following example:  
  
tns1:Device/tnsaxis:Status/SystemReady  
tns1:Device/tnsaxis:IO//  
tns1:RuleEngine/MotionRegionDetector/Motion | tns1:Device/axis:IO/VirtualPort  
tnsaxis:CameraApplicationPlatform/VMD/Camera1ProfileANY  
  
See [Namespaces](/vapix/network-video/event-data-streaming/#namespaces) in the [Event data streaming](/vapix/network-video/event-data-streaming/) API for information on how to use namespaces. |
| `params.eventFilterList[].contentFilter=<string>` _Optional_ | Optional if `topicFilter` exist in the configuration request. Used by the client to filter notifications like the following example:  
  
boolean(//SimpleItem\[@Name="ready" and @Value="1"\])  
boolean(//SimpleItem\[@Name="port" and @Value="1"\]) and boolean(//SimpleItem\[@Name="active" and @Value="0"\]) |

**Return value - Success**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "events:configure",  "data": {  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<string>` | The requested method. |
| `data=<JSON object>` | An empty JSON object, indicating the success of the request. |

**Return value - Failure**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "events:configure",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method=<string>` | The requested method. |
| `error.code=<integer>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### Event streaming

Events are sent to the client as JSON requests. The client should not respond to these notification requests.

Event notification syntax

```bash
{  "apiVersion": "<major>.<minor>",  "method": "events:notify",  "params": {    "notification": {      "timestamp": <integer>,      "topic": <string>,      "message": {        "source": {          <string>: <string>,          <string>: <string>        }        "key": {          <string>: <string>,          <string>: <string>        },        "data": {          <string>: <string>,          <string>: <string>        }      }    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `method=<string>` | The method that should be used. |
| `params.notification=<JSON object>` | Specifies the event notification details. |
| `params.notification.timestamp=<integer>` _Optional_ | Specifies the notification timestamp and should be set if the device has an accurate clock with, preferably, UTC time. In cases where the time is unknown, the device is able to use local time or not set a timestamp at all, which means that the user needs to add the timestamp manually. |
| `params.notification.topic=<string>` | Specifies the notification topic. |
| `params.notification.message=<JSON object>` | Specifies the notification message. |
| `params.notification.message.source=<key-value pairs>` _Optional_ | Specifies the notification source. |
| `params.notification.message.key=<key-value pairs>` _Optional_ | Specifies the notification key. |
| `params.notification.message.data=<key-value pairs>` _Optional_ | Specifies the notification data. |

### General error codes

The following table consist of errors that may occur for any method. Errors specific to a method are listed under their separate API description. The error codes exist in the following ranges.

-   1100–1199
    
    Generic error codes common for many APIs and reserved for server errors such as "Could not read configuration from file". The actual cause can be seen in the server log and can sometimes be solved by restarting the device.
    
-   1200–1999
    
    API-specific server errors that may collide between different APIs.
    
-   2100–2199
    
    Generic error codes common to many APIs and reserved for client errors such as "Invalid parameter". These errors should be possible to solve by changing the input data to the API.
    
-   2200–2999
    
    API-specific client errors that may collide between different APIs.
    

| Code | Description |
| --- | --- |
| `1100` | Internal error. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing. |
| `2104` | Invalid parameter value specified. |
| `2105` | Authorization failed. |
| `2106` | Authentication failed. |
| `2107` | Request too large. |