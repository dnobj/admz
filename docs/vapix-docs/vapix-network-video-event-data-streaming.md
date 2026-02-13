---
title: Event data streaming
url: "https://developer.axis.com/vapix/network-video/event-data-streaming/"
category: vapix
subcategory: network-video
sha256: df2d0bcd7b81d9f24acca9a1be1067e4e87b9e95014f60a73962ad66793e03ec
scraped_at: "2026-01-09T15:19:42.124Z"
page_height: 14649
---

# Event data streaming

## Description

The event stream described in this section is available in Axis network video products with AXIS OS 5.50 and later and contains all events emitted by the Axis product. A client may receive event notifications by subscribing to specific events in the stream. The events can be used to trigger actions in the Axis product or in other systems and can also be stored together with video and audio data for later access.

The event stream is sent over RTSP/RTP. Events emitted by Axis products are in XML format and follows the ONVIF standard. For more information about the standard, see ONVIF Core specification available at [www.onvif.org](http://www.onvif.org)

This section describes how to get event notifications from the event stream using the RTSP API, that is, without implementing web services. The section discusses how to query the Axis product for supported events, how to subscribe to the event stream and how to interpret the response.

See also section [Event and action services](/vapix/network-video/event-and-action-services/).

### Event streaming workflow

Recommended workflow:

1.  Query the Axis product for supported events. See [Query event declarations](#query-event-declarations).
    
2.  Find the event topic names and select the events to subscribe to.
    
3.  Construct an event streaming RTSP request by specifying `eventtopic` and/or `eventcontent` filters. See [Subscribe to the event stream](#subscribe-to-the-event-stream), [Event topic filter](#event-topic-filter) and [Event content filter](#event-content-filter).
    
4.  Interpret the response. See [Parse the event stream](#parse-the-event-stream).
    

### Event streaming considerations

To avoid overloading the Axis product, only subscribe to the events interesting to the client or application. Do not subscribe to more events than necessary. Event subscriptions start internal services in the Axis product and may cause performance problems.

A client should never assume that a specific event is available in the Axis product. Start by query the event declaration list.

Event producers, such as motion detection windows and uploaded applications, may be added or removed, for example by the product administrator.

### Stateful and stateless events

Events are emitted when the Axis product detects an occurrence of some kind, for example motion in the camera’s field of view or a change of status from an I/O port. The events can be used to trigger actions in the Axis product or in other systems and can also be stored together with video and audio data for later access.

The term event is used as a collective name for stateful and stateless events.

-   **Stateful event**: A stateful event is a property (a state variable) with a number of states. The event is always in one of its states. Example: The Motion detection event is in state `true` when motion is detected and in state `false` when motion is not detected.
-   **Stateless event**: A stateless event is a momentary occurrence (a pulse). Example: Storage device removed.

A stateful event has attribute `isProperty="true"`. Stateful events also have a `DataInstance` that contains a `SimpleItem` with attribute `isPropertyState="true"`. This `SimpleItem` describes the current state of the event.

When connecting to a new event stream, all stateful events will send a notification with their current state.

An **event declaration** describes the event. The declaration consists of a `MessageInstance` with a `SourceInstance` that provides information about the source of the event and a `DataInstance` that specifies the event data. For an example of an event declaration, see [Response example](#response-example).

An **event notification** is the event information in the event stream. For an example of an event notification, see [Event notifications](#event-notifications).

### Prerequisites

The following requirements must be fulfilled:

-   **AXIS OS**: 5.50 and later
-   **Property**: `Properties.API.Metadata.Metadata=yes`
-   **Property**: `Properties.API.Metadata.Version="1.00"` and later

info

Previous AXIS OS versions may also support event streaming, but due to differences in the implementation, some information in this section does not apply to older AXIS OS versions.

> When upgrading from AXIS OS 5.40 to AXIS OS 5.50, existing events are converted.

#### Obsoletes

The parameter-based event handling system in products with AXIS OS prior to 5.40 is deprecated but supported for backward compatibility.

Event and action configurations created using the parameter-based API and the web services-based API are stored in separate configuration domains.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Query event declarations

To query the Axis product for supported events, send a `GetEventInstances` request to the product. The response is a list of event declarations for all event types supported by the product. The information is organized as an event topic tree in XML format.

### GetEventInstances request

Use `GetEventInstances` to get information about event instances. The request can be sent using the web services framework or using an HTTP POST request.

```bash
POST http://<servername>/vapix/servicesHeaderfield1: val1<CRLF>Headerfield2: val2<CRLF>...<CRLF>\[Body\]
```

Required header fields:

| Header Field | Description |
| --- | --- |
| `Authorization` | Authorization information from the client. Use standard VAPIX authorization. |
| `Content-Type` | The `Content-Type` header field should contain:`action="http://www.axis.com/vapix/ws/event1/GetEventInstances"` |

The request body should contain the following SOAP message:

```bash
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">    <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">        <GetEventInstances xmlns="http://www.axis.com/vapix/ws/event1" />    </s:Body></s:Envelope>
```

The following is an example of a POST request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/soap+xml; action="http://www.axis.com/vapix/ws/event1/GetEventInstances"; charset=utf-8;" \\  "http://<servername>/vapix/services" \\  --data '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">  <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">    <GetEventInstances xmlns="http://www.axis.com/vapix/ws/event1"/>  </s:Body></s:Envelope>'
```

```bash
POST /vapix/servicesHost: <servername>Content-Type: application/soap+xml; action="http://www.axis.com/vapix/ws/event1/GetEventInstances"; charset=utf-8;<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">  <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">    <GetEventInstances xmlns="http://www.axis.com/vapix/ws/event1"/>  </s:Body></s:Envelope>
```

### Response example

The response to the `GetEventInstances` request is an XML-formatted list with information about the event instances. The following example shows the part of the response describing the motion detection event.

info

The response below shows the event emitted by the Axis product’s built-in motion detection. Motion detection must be enabled for the event to appear in the event stream.

```bash
<SOAP-ENV:body>...  <tns1:VideoAnalytics>    <tnsaxis:MotionDetection wstop:topic="true" aev:NiceName="Motion detection">      <aev:MessageInstance aev:isProperty="true">        <aev:SourceInstance>          <aev:SimpleItemInstance Type="xsd:int" Name="window">            <aev:Value aev:UserString="\[0\] DefaultWindow">0</aev:Value>          </aev:SimpleItemInstance>        </aev:SourceInstance>        <aev:DataInstance>          <aev:SimpleItemInstance aev:NiceName="motion detected" Type="xsd:boolean"               Name="motion" isPropertyState="true">          </aev:SimpleItemInstance>        </aev:DataInstance>      </aev:MessageInstance>    </tnsaxis:MotionDetection>  </tns1:VideoAnalytics>...</SOAP-ENV:body>
```

Attribute `topic="true"` means that the event is available. The `SourceInstance` element contains information about where the event came from. For the motion detection event, `SourceInstance` shows the window that generated the event. The `DataInstance` element contains the data that generated the event, in this case motion.

The prefixes `tns1`, `tnsaxis` and `aev` are placeholders for different namespaces. `tns1` is the ONVIF namespace. `tnsaxis` is used for Axis-specific extensions to ONVIF. `aev` is the event namespace `http://www.axis.com/vapix/ws/event1`. See also [Namespaces](#namespaces).

The event topic tree syntax is described in [Event topic tree syntax](/vapix/network-video/event-and-action-services/#event-topic-tree-syntax). A list of event declarations is available in [Event declarations](/vapix/network-video/event-and-action-services/#event-declarations).

#### Event topic tree attributes

The event topic tree is an XML structure. The following table lists the most important attributes.

| Attribute | Description |
| --- | --- |
| `NiceName` | This attribute contains a user-friendly and human-readable name describing the event.A client should use `NiceName` when displaying the event to an end user. If there is no `NiceName`, use the `Name` attribute. If there is no `Name`, use the tag name. |
| `isPropertyState` | This attribute defines the event as a stateful or stateless event.Stateful events have `isPropertyState = true`. The attribute is omitted for stateless events. |
| `isApplicationData` | This attribute indicates that the event and/or data is produced for a specific system or application.Events with `isApplicationData=true` are usually intended to be used only by the specific system or application, that is, they are not intended to be used as triggers in an action rule in the Axis product.A client that does not know what the event or data is used for should not display the event to the end user.**Note**: `isApplicationData` should not be used in the event content filter when subscribing to the event stream. |
| `isDeprecated` | This attribute indicates that the event is deprecated. A deprecated event is supported for backward compatibility but should not be used by a client or in an action rule. Instead, the event replacing the deprecated event should be used.A client should not display deprecated events. |

## Subscribe to the event stream

info

To avoid overloading the Axis product, only subscribe to the events interesting to the client or application. Do not subscribe to more events than necessary. Event subscriptions start internal services in the Axis product and may cause performance problems.

The event stream is sent over RTSP/RTP. To subscribe to the event stream, use the same syntax as when retrieving video and audio streams but include the arguments `event` and `eventtopic` in the request. If required, for example to pass firewalls, the request can be tunneled over HTTP in the same way as video streams.

For information about retrieving video and audio streams over RSTP and for information about HTTP tunneling, see section [Video streaming over RTSP](/vapix/network-video/video-streaming/#video-streaming-over-rtsp).

Syntax:

```bash
rtsp://<servername>/axis-media/media.amp?<argument>=<value>\[&<argument>=<value>...\]
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `event` | `on` `off` | Defines whether event metadata should be available in the stream.`on` = Event data is included.`off` = Event data is not included.Default: `off` |
| `eventtopic` | string | Defines the event topic filters to include in the stream. Default value is an empty string, which means that all events are included.Do not subscribe to more events than necessary. Event subscriptions start internal processes in the Axis product and may cause performance problems.For more information and supported syntax, see [Event topic filter](#event-topic-filter). |
| `eventcontent` | string | Defines the event content filters to include in the stream. Default value is an empty string.For more information and supported syntax, see [Event content filter](#event-content-filter). |
| `video` | `0` `1` | Defines whether video should be included in the stream.`0` = No video.`1` = Video.Default: `1` |
| `audio` | `0` `1` | Defines whether audio should be included in the stream.`0` = No audio.`1` = Audio.Default: `1` |
| For additional arguments, see section [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url). |  |  |

The arguments `eventtopic` and `eventcontent` follow the Xpath syntax. XPath uses path expressions to select nodes or node sets in an XML document. The node is selected by following a path.

info

The namespaces used in eventtopic differ from the event declaration namespaces. For more information, see [Namespaces](#namespaces).

Selected XPath expressions:

| Expression | Description |
| --- | --- |
| `/` | Selects the child topic name from the topic tree. |
| `//.` | Matches the topic subtree including the specified topic. |
| `@` | Selects attributes. |
| `|` | Logical OR operation that combines multiple topics into a single filter. |

### Namespaces

Event declarations and event topic filters use different namespaces. Event declarations use `tns1` and `tnsaxis` while event topic filters use `onvif` and `axis`.

Use the following table to translate event declaration namespaces to event topic filter namespaces:

| Event declaration namespace | Event topic filter namespace |
| --- | --- |
| `tns1` | `onvif` |
| `tnsaxis` | `axis` |

The motion detection event is `tns1:VideoAnalytics/tnsaxis:MotionDetection` in the event declaration. When subscribing to the event stream, this event should be referred to as `onvif:VideoAnalytics/axis:MotionDetection` in the `eventtopic` argument.

| Event Topic Name | Topic Filter |
| --- | --- |
| `tns1:AudioSource` | `onvif:AudioSource` |
| `tnsaxis:IO/Port` | `axis:IO/Port` |

### Event topic filter

To specify the events to be included in the stream, use the argument `eventtopic`. The argument should be a comma-separated list of event topic filters.

Syntax:

```bash
eventtopic=<filter1>\[,<filter2>\[...<filterN>\]\]
```

where `<filter#>` is a topic expression filter using the `ConcreteSet` dialect defined by ONVIF. The `ConcreteSet` dialect uses the following syntax:

```bash
TopicExpression ::= TopicPath (‘|’ TopicPath)\*TopicPath ::= RootTopic ChildTopicExpression\*RootTopic ::= QnameChildTopicExpression ::= ‘/’ ChildTopicName '//.'?ChildTopicName ::= QName | NCName
```

Here, the syntax is written in simple Extended Backus-Naur Form (EBNF). For more information about the syntax, see the ONVIF core specification.

To set up an event topic filter, the topic name must be known. A list of event names and event declarations is available in section [Event declarations](/vapix/network-video/event-and-action-services/#event-declarations).

info

The namespaces used in eventtopic differ from the event declaration namespaces. For more information, see [Namespaces](#namespaces).

Subscribe to motion detection events.

```bash
rtsp://<servername>/axis-media/media.amp?video=0&audio=0&event=on&eventtopic=onvif:VideoAnalytics/axis:MotionDetection//.
```

Subscribe to events triggered by a signal from the I/O port.

```bash
rtsp://<servername>/axis-media/media.amp?video=0&audio=0&event=on&eventtopic=onvif:Device/axis:IO/Port//. | onvif:UserAlarm/axis:Recurring/Interval//.
```

### Event content filter

To specify the event content to be included in the stream, use the argument `eventcontent`.

Syntax:

```bash
eventcontent=<filter>
```

where `<filter>` is a message content filter expression using the `ItemFilter` dialect defined by ONVIF. The `ItemFilter` dialect uses the following syntax:

```bash
Expression ::= BoolExpr | Expression ‘and’ Expression | Expression ‘or’ Expression | ‘(‘ Expression ‘)’ | ‘not’ ‘(‘ Expression ‘)’BoolExpr ::= ‘boolean’ ‘(‘ PathExpr ‘)’PathExpr ::= // ’Prefix ‘:’ SimpleItem‘ NodeTest | //Prefix ‘:’? ElementItem‘ NodeTestNodeTest ::= ‘\[‘ AttrExpr ‘\]’AttrExpr ::= AttrComp | AttrExpr ‘and’ AttrExpr | AttrExpr ‘or‘ AttrExpr | ‘(‘ AttrExpr ‘)‘ | ‘not’ ‘(‘ AttrExpr ‘)‘AttrComp ::= Attribute ‘=’ ‘"’ String ‘"’Attribute ::= ‘@Name’ | ‘@Value’
```

Here, the syntax is written in simple Extended Backus-Naur Form (EBNF). For more information about the syntax, see the ONVIF Core Specification.

Consider the following notification:

```bash
<wsnt:Message>    <tt:Message UtcTime="2010-04-01T07:42:58.859045Z" PropertyOperation="Initialized">        <tt:Source>            <tt:SimpleItem Name="port" Value="1" />        </tt:Source>        <tt:Data>            <tt:SimpleItem Name="state" Value="high" />        </tt:Data>    </tt:Message></wsnt:Message>
```

It is possible to construct message content filters for the source, key and data elements. Some examples are shown in the table below.

| Filter examples | Description |
| --- | --- |
| `eventcontent=boolean(//SimpleItem[@Name="port"])` | Filter events based on `Name`. |
| `eventcontent=boolean(//SimpleItem[@Value="high"])` | Filter events based on `Value` |
| `eventcontent=boolean(//SimpleItem[@Name="port" and @Value="high"])` | Filter events based on a `Name` and `Value` pair. |
| `eventcontent=boolean(//SimpleItem[@Name="port" and @Value="1"]) and boolean(//SimpleItem[@Name="state" and @Value="high"])` | Filter events based on two `Name` and `Value` pairs. |

The event content filter `eventcontent` is most useful when used together with the event topic filter `eventtopic`. For example:

```bash
eventtopic=onvif:Device/axis:IO/port//.eventcontent=boolean(//SimpleItem\[@Name="port" and @Value="1"\]) and boolean(//SimpleItem\[@Name="state" and @Value="high"\])
```

info

The spaces in the filter expression may need to be removed or percent-encoded to prevent parsing problems. Special characters, including quotation marks, should be percent-encoded.

The following example shows an event stream subscription with the `eventtopic` and `eventcontent` filters. In the `eventcontent` filter, spaces and quotation marks are percent-encoded.

```bash
rtsp://<server>/axis-media/media.amp?video=0&audio=0&event=on&eventtopic=onvif:VideoAnalytics/axis:MotionDetection//.&eventcontent=boolean(//SimpleItem\[@Name=%22motion%22%20and%20@Value=%221%22\])
```

## Parse the event stream

Using the event streaming request including the `eventtopic` and/or `eventcontent` filters, a standard RTSP client can be used to establish a connection to the Axis product and receive the event stream.

info

It is recommended to retrieve the event stream over TCP and not UDP.

The next step is to parse the event notifications in the event stream. Event notifications are in XML format and follows the ONVIF standard defined in ONVIF Core specification. For an example, see [Event notifications](#event-notifications).

To synchronize the event stream with the video stream, a time conversion is required. The event stream uses UTC time which is an absolute time whereas the video stream uses RTP timestamps, that is, a relative time. The conversion between RTP timestamps and UTC time can be found in the RTCP packets.

### Event notifications

Event notifications contain information such as: who produced the event, what happened and when did it happen.

As an example, consider motion detection. If motion detection is enabled in the Axis product, the following notification message is included in the event stream when motion is detected:

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tns1:VideoAnalytics/tnsaxis:MotionDetection            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://7fc24c8a-f67b-11e1-b4e5-00408ca0c954/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2013-12-12T13:25:15.900235Z" PropertyOperation="Changed">                    <tt:Source>                        <tt:SimpleItem Name="window" Value="0" />                    </tt:Source>                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="motion" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

For a detailed description of the XML structure, see [Event and action services](/vapix/network-video/event-and-action-services/) and the ONVIF Core specification. The table below lists some of the XML elements in the example notification above.

| XML element | Description |
| --- | --- |
| `Topic` | Topic. The `Topic` element contains the name of the topic. The topic name shows what happened, that is, the type of event emitted.Here, the topic name is `tns1:VideoAnalytics/tnsaxis:MotionDetection` |
| `ProducerReference` | Producer reference. The `ProducerReference` element identifies the product that emitted the event. |
| `Source` | Source. The `Source` element identifies the component in the product that emitted the event.Here, the `Source` element contains `<tt:SimpleItem Name="window" Value="0" />` which shows that the source of the event is motion detection window 0. |
| `Data` | Data. The `Data` element contains event data.Here, the `Data` element contains `<tt:SimpleItem Name="motion" Value="1" />` which shows that the event was emitted when motion was detected (`Value="1"`). |
| `Message` with attribute `UtcTime` | The `UtcTime` attribute shows when the event took place. |