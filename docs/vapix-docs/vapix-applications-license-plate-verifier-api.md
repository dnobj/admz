---
title: License plate verifier API
url: "https://developer.axis.com/vapix/applications/license-plate-verifier-api/"
category: vapix
subcategory: applications
sha256: 12369f58005757e966acb1601a0f7a14bb17b912905df054f9536061f556b5ef
scraped_at: "2026-01-09T15:01:15.812Z"
page_height: 65598
---

# License plate verifier API

The VAPIX® License plate verifier API contains the information and steps that makes it possible to detect and recognize license plates and whether the vehicle should be allowed to enter a restricted area such as a parking garage. It is split into three groups that handles everything from settings to how to query events and retrieve real time data from the system:

-   VAPIX events
-   Push events (HTTP, TCP, FTP)
-   Heartbeat services
-   Direct integration
-   Application API
-   Web services API

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Analytic (ALPV) event types

The following table contain event types for the real-time, new, update and lost statuses.

| # | RAW recognition event, time ms | Number plate | Car ID | LPR event (VAPIX ALLPLATES) | Comments |
| --- | --- | --- | --- | --- | --- |
| 1 | 10:12:10 AM 100 | AA7690EQ | 123 | ~10:12:10 AM 100 LPR Event - **NEW** -AA7690EQ | Events are sent immediately. |
| 2 | 10:12:10 AM 150 | AA7690EQ | 123 | ~10:12:10 AM 400 LPR Event - **UPDATE** - AA7690EQ | A direction has been detected. An event has been sent. |
| 3 | 10:12:10 AM 200 | AA7690EQ | 123 |  |  |
| 4 | 10:12:10 AM 250 | AA7690EO | 123 |  |  |
| 5 | 10:12:10 AM 350 | AA7690EO | 123 |  |  |
| 6 | 10:12:10 AM 400 | AA7690EO | 123 | ~10:12:10 AM 400 LPR Event - **UPDATE** - AA7690EO | A license plate has been changed. An event has been sent. |
| 7 | 10:12:10 AM 450 | AA7690EO | 123 |  |  |
| 8 | 10:12:10 AM 750 | AA7690EO | 123 |  |  |
| 9 | 10:12:10 AM 850 | AA7690EO | 123 |  |  |
| 10 | License plate left the frame |  | 123 |  |  |
| 11 | 10:12:16 AM 050 | \----/---- | 123456789 | ~10:12:15 AM 1050 LPR Event - **LOST**\- AA7690EO | An event has been sent after the last license plate recognition +10 s. |

-   A **NEW** event is generated on the first license plate detection (the direction is always undefined in this event).
-   The **Update** event is generated if direction, license plate, zone, etc. changes.
-   The **LOST** event is generated +10 seconds after the last recognition (this is a configurable parameter).

**Examples**

The ACAP will generate two events, **NEW** at first detection and **LOST** +10 seconds after the first detection.

Access control systems (real-time systems) use **NEW** and **UPDATE** events to check and open barriers. In traffic solutions, **LOST** events are used to get the final result. This means one car for every event.

Use the `CARID` field in the package to merge or update all events into one. This field is unique and the can be used by **NEW**, **UPDATE** and **LOST** for one vehicle.

**Used times in the events**

| Name | Example | Description | NEW | UPDATE | LOST |
| --- | --- | --- | --- | --- | --- |
| `capture_timestamp` | 1678715164683 | UNIX frame timestamp, ms UTC timestamp of event | Same | Different | Same |
| `frame_timestamp` | 167871564683793 | UNIX frame timestamp (internal from camera) | Different | Different | 0 |
| `capture_ts` | 1678715164683000000 | The same as `frame_timestamp` but `capture_timestamp*1000000` is used. | Same | Different | Same |
| `Datetime` | 20230313 144604683 | YYYYMMDD HHMMSSFFF YYYY - year 4 digits MM - month 2 digits DD - day 2 digits HH - hours MM - minutes SS - seconds FFF - milliseconds | Same | Different | Same |

## VAPIX Events

Real time recognition events can be received from a camera using VAPIX protocols in a format where all recognition related data except images are present. For more information see Event data streaming.

| # | Events | Description |
| --- | --- | --- |
| 1 | `ALPV.ALLPlates` | Event with complete metadata sent several times during recognition (**NEW**, **UPDATE** and **LOST** event types). These events does not have any conditions. |
| 2 | `ALPV.Allow_list` | Trigger events if there is a match to the list name. Sent only once. |
| 3 | `ALPV.Block_list` | Trigger events if there is a match to the list name. Sent only once. |
| 4 | `ALPV.Custom_list` | Trigger events if there is a match to the list name. Sent only once. |
| 5 | `ALPV.NotInList` | Trigger events if there is no match to the list name. Sent only once. |
| 6 | `ALPV.Roi1` | Trigger events if there is a match to the recognition zone/area of interest. Sent only once. |
| 7 | `ALPV.Roi2` | Trigger events if there is a match to the recognition zone/area of interest. Sent only once. |
| 8 | `ALPV.PlateIN` | Trigger events if there is a match to the detect direction. Sent only once. |
| 9 | `ALPV.PlateOUT` | Trigger events if there is a match to the detect direction. Sent only once. |
| 10 | `ALPV.PlateInView` | Trigger events for as long as a license plate is in the Area of Interest with a post event of 10 seconds. |
| 11 | `ALPV.New` | Event with complete metadata. Sent at the first license plate detection. |
| 12 | `ALPV.Update` | Event with complete metadata. Sent if direction, license plate text, etc. changes. |
| 13 | `ALPV.Lost` | Event with complete metadata. Sent 10 seconds after the last recognition. |
| 14 | `ALPV.RealTime` | Event with complete metadata. Internal events Radar integration. |

### Events and Examples
#### ALPV.ALLPlates

This general metadata event is always available and contains all data from the LPR engine. The event can be sent several times for each individual license plate:

-   **NEW**: Used when a new License plate is detected. Only one event is produced and it does not contain direction.
-   **UPDATE**: Used when something changes in the LPR package. Multiple events can be produced depending on the changes of the LPR package and how long the license plate is on the scene.
-   **LOST**: Used when a vehicle exits the image. Only one image event is produced (sent +10 seconds after the last **UPDATE** event).

| Parameter | Description |
| --- | --- |
| `Width` | The width of the license plate, measured in pixels. |
| `carMoveDirection` | The detected movement against a set of pre-set directions. |
| `roIID` | ID of an area of interest where the plate was recognized. |
| `vehicleType` | The vehicle type. Can be CAR | TRUCK | BUS. This is parameter is supported from ALPV 2.9.19 or later. |
| `View` | The vehicle’s view. Can be front | rear. |
| `Top` | The top coordinate of the license plate, measured in pixels. |
| `consumedTime` | The license plate recognition time, measured in milliseconds (ms). |
| `Text` | The license plate text. |
| `iso3166-2` | The iso3166-2 code. |
| `Region` | The local region name. |
| `listName` | The name of the list. It will be empty if the plate text cannot be found in the list, or labelled on either the **Block list** or **Allow list** if it exists. |
| `regionCode` | The region letter. |
| `Left` | The left coordinate of the license plate, measured in pixels. |
| `capture_timestamp` | The UNIX frame timestamp. |
| `listDescription` | The plate’s description if it was added to a list. |
| `lpImage` | The license plate image in Base64 (supported from ALPV 2.9.19 or later). |
| `action` | Set to either `Accepted`, `Denied` depending on whether an application configuration has occurred. |
| `vehicleColor` | The color of the vehicle. This is parameter is supported from ALPV 2.9.19 or later. |
| `carID` | The internal runtime plate ID. |
| `country` | The 3 letter country names in the Alpha-3 ISO-3166 format. |
| `height` | The height of the license plate, measured in pixels. |
| `frame_timestamp` | The UNIX frame timestamp from the camera. |
| `listMode` | The list mode. Can be allow | block | none |
| `MACAddress` | The camera’s MAC address. |
| `carState` | The event type. Can be new | update | lost. |

**Package sample**

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.AllPlates            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://c37d4bf5-fa69-498d-8294-e0c8ade51ded/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2021-05-20T11:54:21.894000Z">                    <tt:Source />                    <tt:Data>                        <tt:SimpleItem Name="consumedTime" Value="153" />                        <tt:SimpleItem Name="frame\_timestamp" Value="1288416958" />                        <tt:SimpleItem Name="carMoveDirection" Value="unknown" />                        <tt:SimpleItem Name="carState" Value="new" />                        <tt:SimpleItem Name="action" Value="No action" />                        <tt:SimpleItem Name="capture\_timestamp" Value="1621511661894" />                        <tt:SimpleItem Name="width" Value="168" />                        <tt:SimpleItem Name="carID" Value="1139066" />                        <tt:SimpleItem Name="top" Value="354" />                        <tt:SimpleItem Name="country" Value="PRT" />                        <tt:SimpleItem Name="left" Value="539" />                        <tt:SimpleItem Name="height" Value="28" />                        <tt:SimpleItem Name="listName" Value="" />                        <tt:SimpleItem Name="text" Value="II04458" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Allow\_list

Triggered events dependant on a list’s application name. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Allow\_list            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:16.999671Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Block\_list

Triggered events dependant on a list’s application name. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Block\_list            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:25.288828Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Custom\_list

Triggered events dependant on a list’s application name. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Custom\_list            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-07T15:31:40.092488Z" PropertyOperation="Initialized">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="0" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.NotInList

Triggered events dependant on a list’s application name. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.NotInList            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:41.969036Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="0" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Roi1

A triggered event.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Roi1            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:25.289164Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Roi2

A triggered event.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Roi2            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:25.289164Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.PlateIN

Triggered events. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.PlateIn            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:17.212625Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.PlateOUT

Triggered events. Please note that these events are only available when a relay is connected.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.PlateOut            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://67005000-27b4-4856-b92c-490fc4cf6b15/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2023-12-08T12:21:42.378250Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.PlateInView

Triggered events. The event will trigger when the plate is first detected in an Area of Interest and stopped 10 seconds after the license plate has left the area.

```bash
active = 1active = 0
```

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.PlateInView            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://669dd136-d268-4365-83d0-b00c2e368a6c/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2024-02-14T15:36:51.583716Z" PropertyOperation="Changed">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.New

A **New** event is generated on the first license plate detection. The direction is always undefined in **New** events.

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.New            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://ae273212-d36d-4c76-bbd5-c1b08dde9e82/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2024-03-14T18:08:51.293000Z">                    <tt:Source />                    <tt:Data>                        <tt:SimpleItem Name="frame\_timestamp" Value="1710439731" />                        <tt:SimpleItem Name="vehicleColor" Value="BLACK" />                        <tt:SimpleItem Name="region" Value="" />                        <tt:SimpleItem Name="carID" Value="4" />                        <tt:SimpleItem Name="listMode" Value="none" />                        <tt:SimpleItem Name="country" Value="DNK" />                        <tt:SimpleItem Name="capture\_timestamp" Value="1710439731293" />                        <tt:SimpleItem Name="text" Value="WR6677" />                        <tt:SimpleItem Name="roiID" Value="1" />                        <tt:SimpleItem Name="regionCode" Value="" />                        <tt:SimpleItem Name="iso3166-2" Value="" />                        <tt:SimpleItem Name="view" Value="front" />                        <tt:SimpleItem Name="MACAddress" Value="ACCC8EBFB452" />                        <tt:SimpleItem Name="listName" Value="" />                        <tt:SimpleItem Name="height" Value="28" />                        <tt:SimpleItem Name="width" Value="92" />                        <tt:SimpleItem                            Name="lpImage"                            Value="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" />                        <tt:SimpleItem Name="consumedTime" Value="127" />                        <tt:SimpleItem Name="listDescription" Value="" />                        <tt:SimpleItem Name="action" Value="Denied" />                        <tt:SimpleItem Name="carState" Value="new" />                        <tt:SimpleItem Name="carMoveDirection" Value="unknown" />                        <tt:SimpleItem Name="left" Value="760" />                        <tt:SimpleItem Name="vehicleType" Value="CAR" />                        <tt:SimpleItem Name="top" Value="608" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Update

A **Update** event is generated if something changes. This include direction of the vehicle, the license plate, etc.

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Update            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://ae273212-d36d-4c76-bbd5-c1b08dde9e82/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2024-03-14T18:08:51.560000Z">                    <tt:Source />                    <tt:Data>                        <tt:SimpleItem Name="frame\_timestamp" Value="1710439731" />                        <tt:SimpleItem Name="vehicleColor" Value="BLACK" />                        <tt:SimpleItem Name="region" Value="München" />                        <tt:SimpleItem Name="carID" Value="4" />                        <tt:SimpleItem Name="listMode" Value="none" />                        <tt:SimpleItem Name="country" Value="DEU" />                        <tt:SimpleItem Name="capture\_timestamp" Value="1710439731560" />                        <tt:SimpleItem Name="text" Value="M WR6677" />                        <tt:SimpleItem Name="roiID" Value="1" />                        <tt:SimpleItem Name="regionCode" Value="M" />                        <tt:SimpleItem Name="iso3166-2" Value="" />                        <tt:SimpleItem Name="view" Value="front" />                        <tt:SimpleItem Name="MACAddress" Value="ACCC8EBFB452" />                        <tt:SimpleItem Name="listName" Value="" />                        <tt:SimpleItem Name="height" Value="28" />                        <tt:SimpleItem Name="width" Value="112" />                        <tt:SimpleItem                            Name="lpImage"                            Value="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" />                        <tt:SimpleItem Name="consumedTime" Value="131" />                        <tt:SimpleItem Name="listDescription" Value="" />                        <tt:SimpleItem Name="action" Value="Denied" />                        <tt:SimpleItem Name="carState" Value="update" />                        <tt:SimpleItem Name="carMoveDirection" Value="in" />                        <tt:SimpleItem Name="left" Value="768" />                        <tt:SimpleItem Name="vehicleType" Value="CAR" />                        <tt:SimpleItem Name="top" Value="614" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.Lost

A **Lost** event is generated +10 seconds after the last recognition.

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.Lost            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://ae273212-d36d-4c76-bbd5-c1b08dde9e82/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2024-03-14T18:08:51.293000Z">                    <tt:Source />                    <tt:Data>                        <tt:SimpleItem Name="frame\_timestamp" Value="0" />                        <tt:SimpleItem Name="vehicleColor" Value="BLACK" />                        <tt:SimpleItem Name="region" Value="München" />                        <tt:SimpleItem Name="carID" Value="4" />                        <tt:SimpleItem Name="listMode" Value="none" />                        <tt:SimpleItem Name="country" Value="DEU" />                        <tt:SimpleItem Name="capture\_timestamp" Value="1710439731293" />                        <tt:SimpleItem Name="text" Value="M WR6677" />                        <tt:SimpleItem Name="roiID" Value="1" />                        <tt:SimpleItem Name="regionCode" Value="M" />                        <tt:SimpleItem Name="iso3166-2" Value="" />                        <tt:SimpleItem Name="view" Value="front" />                        <tt:SimpleItem Name="MACAddress" Value="ACCC8EBFB452" />                        <tt:SimpleItem Name="listName" Value="" />                        <tt:SimpleItem Name="height" Value="28" />                        <tt:SimpleItem Name="width" Value="92" />                        <tt:SimpleItem                            Name="lpImage"                            Value="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" />                        <tt:SimpleItem Name="consumedTime" Value="127" />                        <tt:SimpleItem Name="listDescription" Value="" />                        <tt:SimpleItem Name="action" Value="Denied" />                        <tt:SimpleItem Name="carState" Value="lost" />                        <tt:SimpleItem Name="carMoveDirection" Value="in" />                        <tt:SimpleItem Name="left" Value="760" />                        <tt:SimpleItem Name="vehicleType" Value="CAR" />                        <tt:SimpleItem Name="top" Value="608" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

#### ALPV.RealTime

The following information used for Radar integration.

Package sample

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tnsaxis:CameraApplicationPlatform/ALPV.RealTime            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://ae273212-d36d-4c76-bbd5-c1b08dde9e82/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2024-03-14T18:08:58.162077Z">                    <tt:Source />                    <tt:Data>                        <tt:SimpleItem Name="timestamp" Value="1710439737193" />                        <tt:SimpleItem Name="isDetected" Value="1" />                        <tt:SimpleItem Name="coordinates\_left" Value="0.106250" />                        <tt:SimpleItem Name="lpText" Value="MWR6677" />                        <tt:SimpleItem Name="coordinates\_top" Value="-0.418519" />                        <tt:SimpleItem Name="carID" Value="4" />                        <tt:SimpleItem Name="coordinates\_bottom" Value="-0.500000" />                        <tt:SimpleItem Name="coordinates\_right" Value="0.368750" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

## Push events
### Data format of received data

-   **TCP**: Data formats are JSON files and base64-encoded pictures in the JSON body.
-   **HTTP**: Data formats are JSON files and JPG images (or base64-encoded pictures in the JSON body with non-multipart requests).
-   **FTP**: Data format is JPG images.

The following events can be sent several times for each individual license plate:

-   **NEW**: Used when a new License plate is detected. Only one event is produced and it does not contain direction.
-   **UPDATE**: Used when something changes in the LPR package. Multiple events can be produced depending on the changes of the LPR package and how long the license plate is on the scene.
-   **LOST**: Used when a vehicle exits the image. Only one image event is produced (sent +10 seconds after the last **UPDATE** event).

#### JSON file keys description

| Argument | Description |
| --- | --- |
| `packetCounter` | The counter for sent packages. |
| `capture_timestamp` | The UNIX frame timestamp, measured as an ms UTC timestamp of the event. |
| `frame_timestamp` | The UNIX frame timestamp (internal from the camera). |
| `capture_ts` | The same as `frame_timestamp` but measured in ns (`capture_timestamp`\*1000000). |
| `Datetime` | Timestamp for the data: YYYY = year MM = month DD = day HH = hours MM = minutes SS = seconds FFF = milliseconds HHMM = optional timezones (hours, minutes) Example: YYYYMMDD HHMMSSFFF |
| `plateText` | The plate number. |
| `plateUnicode` | The plate number in Unicode. |
| `plateUTF8` | The plate text using UTF8 symbols. |
| `plateASCII` | The plate text using ASCII symbols. |
| `plateCountry` | The country code, according to ISO 3166-1 alpha-3 |
| `plateISO3166-2` | The ISO3166-2 code. |
| `plateRegion` | The local region name. |
| `plateRegionCode` | The region letter. |
| `plateList` | The name of the list The list will be empty if the plate text cannot be found in the list, or if it is on the Block or Allow lists. |
| `plateListMode` | Allow or block a plate number. |
| `plateListDescription` | The description for a plate added to the list. |
| `plateConfidence` | The recognition confidence level. |
| `carState` | The event type. Can be `new | update | lost`. |
| `roiID` | The area of interest ID where the plate was recognized. |
| `Geotag` | A JSON object that contains latitude and longitude. |
| `imageType` | The kind of attached image. Can be either a plate only rectangle with the plate number, the full frame or a vehicle crop. |
| `plateImageType` | The attached image type. |
| `plateImageSize` | The size of an plate’s image. |
| `carMoveDirection` | The detected movement against a preset direction. |
| `timeProcessing` | The time it takes for an event to process. |
| `plateCoordinates` | The coordinates of the license plate bounding box upper left corner and its dimensions calculated for the full video frame. |
| `plateCoordinatesRelative` | The coordinates of the license plate bounding box upper left corner and its dimensions recalculated for the current image crop. |
| `carID` | The internal runtime plate ID. |
| `GEOtarget` | The camera location description. |
| `imagesURI` | An array of available event images’ URIs: 1. The array element is the plate image. 2. The element dependant (AOI, frame or vehicle) image configuration. 3. The element dependant frame configuration. |
| `imageArray` | A JSON object with a base64 image. |
| `imageFile` | Path to the AOI image. |
| `imageFile2` | Path to the LP image. |
| `profileID` | The profile number. |
| `vehicle_info` | Contains vehicle recognition data (ALPV 2.9.19 or later):  
\- View  
\- Type  
\- Color |
| `camera_info` | The camera information structure. |
| `sensorProviderID` | The readable name of the sender. |

#### HTTP POST

This method should be used when you want HTTP POST events to the configured Server URL.

-   Content-Type
    
    `multipart/form-data` or `application/json`
    

This method can be used alongside JSON LPV to send event images.

Package sample

```bash
{    "packetCounter": "2117397",    "capture\_timestamp": "1702297625507",    "frame\_timestamp": "1702297625507641",    "capture\_ts": "1702297625507000000",    "datetime": "20231211 142705507",    "plateText": "HWR6677",    "plateUnicode": "HWR6677",    "plateUTF8": "HWR6677",    "plateASCII": "HWR6677",    "plateCountry": "DEU",    "plateISO3166-2": "",    "plateRegion": "Hannover",    "plateRegionCode": "H",    "plateList": "",    "plateListMode": "",    "plateListDescription": "",    "plateConfidence": "0.737210",    "carState": "update",    "roiID": "1",    "geotag": {        "lat": 55.70421,        "lon": 13.19366    },    "imageType": "plate",    "plateImageType": "jpeg",    "plateImageSize": "0",    "carMoveDirection": "out",    "timeProcessing": "0",    "plateCoordinates": \[514, 570, 120, 28\],    "plateCoordinatesRelative": \[514, 570, 120, 28\],    "carID": "54950",    "GEOtarget": "Camera",    "imagesURI": \[        "/local/fflprapp/tools.cgi?action=getImage&name=52/20231211142706\_413731lp\_HWR6677\_2117396.jpg",        "/local/fflprapp/tools.cgi?action=getImage&name=48/20231211142705\_954662roi\_MWR6677\_2117394.jpg"    \],    "imageFile": "localdata/images/48/20231211142705\_954662roi\_MWR6677\_2117394.jpg",    "imageFile2": "localdata/images/52/20231211142706\_413731lp\_HWR6677\_2117396.jpg",    "profileID": "2",    "vehicle\_info": {        "view": "front",        "type": "CAR",        "color": "BLACK"    },    "camera\_info": {        "SerialNumber": "ACCC8EBFB452",        "ProdShortName": "AXIS Q1700-LE",        "IPAddress": "10.0.3.177",        "MACAddress": "ACCC8EBFB452"    },    "sensorProviderID": "defaultID"}
```

#### Using TCP

TCP send events to a configured TCP receiver. A JSON body must be used by LPV to send appropriate event images in base64.

Package sample

```bash
{    "packetCounter": "8104955",    "capture\_timestamp": "1702299266977",    "frame\_timestamp": "1702299266977980",    "capture\_ts": "1702299266977000000",    "datetime": "20231211 145426977",    "plateText": "TÖLSL123",    "plateUnicode": "TÖLSL123",    "plateUTF8": "TÖLSL123",    "plateASCII": "TÖLSL123",    "plateCountry": "DEU",    "plateISO3166-2": "",    "plateRegion": "Bad Tölz",    "plateRegionCode": "TÖL",    "plateList": "Block list",    "plateListMode": "block",    "plateListDescription": "car\_test\_1",    "plateConfidence": "0.725149",    "carState": "new",    "roiID": "1",    "geotag": {        "lat": 55.70421,        "lon": 13.19366    },    "imageType": "plate",    "plateImageType": "jpeg",    "plateImageSize": "0",    "carMoveDirection": "unknown",    "timeProcessing": "0",    "plateCoordinates": \[670, 496, 276, 44\],    "plateCoordinatesRelative": \[670, 496, 276, 44\],    "carID": "34939",    "GEOtarget": "Camera",    "imagesURI": \[        "/local/fflprapp/tools.cgi?action=getImage&name=67/20231211145427\_793329lp\_TOLSL123\_8104954.jpg",        "/local/fflprapp/tools.cgi?action=getImage&name=68/20231211145427\_804106roi\_TOLSL123\_8104955.jpg"    \],    "ImageArray": \[        {            "ImageType": "",            "ImageFormat": "jpg",            "BinaryImage": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII="        }    \],    "imageFile": "/var/spool/storage/SD\_DISK/fflprapp/images/68/20231211145427\_804106roi\_TOLSL123\_8104955.jpg",    "imageFile2": "/var/spool/storage/SD\_DISK/fflprapp/images/67/20231211145427\_793329lp\_TOLSL123\_8104954.jpg",    "profileID": "1",    "vehicle\_info": {        "view": "front",        "type": "CAR",        "color": "BLUE"    },    "camera\_info": {        "SerialNumber": "ACCC8E9BB16D",        "ProdShortName": "AXIS P1447-LE",        "IPAddress": "10.0.3.167",        "MACAddress": "ACCC8E9BB16D"    },    "sensorProviderID": "defaultID"}
```

**Receiver example**

Use this method when you want to receive data that can be stored as files using PHP.

PHP

```bash
<?php# Create files in the following directory$uploaddir = 'log/';# Set path and filename where to store the event$uploadfile = $uploaddir . basename($\_FILES\['event'\]\['name'\]);# Store the JSON file on diskif (move\_uploaded\_file($\_FILES\['event'\]\['tmp\_name'\], $uploadfile)) {  # All good, do other things here} else {  # Failed moving file, do proper error handling}# Set path end filename where to store the image$uploadfile = $uploaddir . basename($\_FILES\['image'\]\['name'\]);# Store the image file on diskif (move\_uploaded\_file($\_FILES\['image'\]\['tmp\_name'\], $uploadfile)) {  # All good, do other things here} else {  # Failed moving file, do proper error handling}?>
```

Python

```bash
import jsonfrom aiohttp.web import Response, Application, run\_app, postasync def handle\_files(request):  print("-----new request-----")  data = await request.post()  for field\_name, file\_field in data.items():    file\_contents = file\_field.file.read()    if field\_name == 'event':      json\_event = json.loads(file\_contents)      print(f'Event: {json\_event}')  return Response(status=200)if \_\_name\_\_ == '\_\_main\_\_':  app = Application()  app.add\_routes(\[post('/', handle\_files)\])  run\_app(app, host='0.0.0.0', port=5001)
```

### Get PUSH event configurations

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/cloud.cgi"
```

```bash
GET /local/fflprapp/cloud.cgiHost: <servername>
```

To get configurations for 2nd and 3rd profiles use the following requests:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/cloud2.cgi"
```

```bash
GET /local/fflprapp/cloud2.cgiHost: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/cloud3.cgi"
```

```bash
GET /local/fflprapp/cloud3.cgiHost: <servername>
```

Response sample:

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><cloud\_config>    <url>aHR0cDovLzEwLjAuNS4yMjM6NTAwMg==</url>    <latitude>55.70421</latitude>    <longitude>13.19366</longitude>    <sensorProviderID>defaultID</sensorProviderID>    <protocol>1</protocol>    <enable>false</enable>    <skip\_image\_in\_post>false</skip\_image\_in\_post>    <event\_new>true</event\_new>    <event\_update>false</event\_update>    <event\_lost>false</event\_lost>    <use\_multipart>true</use\_multipart>    <use\_event\_buffer>true</use\_event\_buffer>    <user />    <password />    <http\_auth\_type>0</http\_auth\_type>    <send\_second\_image>false</send\_second\_image>    <second\_image\_type>21</second\_image\_type>    <path\_template />    <x\_auth\_key /></cloud\_config>
```

| Field | Description |
| --- | --- |
| `URL` | The encoded target base64 URL. Determines the data that should be pushed to the URL or IP address using the format `<servername>:port/path`. No path is present when the TCP option is used, however the IP and port is still available. |
| `Latitude` | The camera latitude coordinates, represented by a float number. |
| `Longitude` | The camera longitude coordinates, represented by a float number. |
| `sensorProviderID` | The camera identifier that is sent with all requests when multiple cameras are running to separate them. |
| `Protocol` | The protocol that is sent. `TCP` = 8 `HTTP` = 1 `FTP` = 16 |
| `Enable` | True: The function is enabled. False: The function is disabled. |
| `skip_image_in_post` | True: Sends the JSON packet, but no images. False: Sends both the JSON packet and images. |
| `event_new` | Sends NEW events. Can be either true or false. |
| `event_update` | Sends UPDATE events. Can be either true or false. |
| `event_lost` | Sends LOST events. Can be either true or false. |
| `use_multipart` | True: Sends as multipart/form-data. False: Sends as application/json. |
| `use_event_buffer` | Events will be re-sent from a buffer if the target URL is not accessible. Can be either true o false. |
| `User` | The user name. |
| `Password` | The password. |
| `http_auth_type` |  |
| `send_second_image` | Sends a second image with the **License plate** type alongside the regular image configured in the LPV settings. Can be either true or false. |
| `path_template` | The custom path for FTP. |
| `x_auth_key` | The Auth-Header. |

### Update PUSH event configurations

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/cloud.cgi" \\  --data '<?xml version="1.0" encoding="utf-8" ?><cloud\_config>    <url>MTAuMC41LjIyMzo3MDAx</url>    <latitude>50.418114</latitude>    <longitude>30.476213</longitude>    <sensorProviderID>PostmanConfigured</sensorProviderID>    <protocol>8</protocol>    <enable>true</enable>    <skip\_image\_in\_post>true</skip\_image\_in\_post>    <event\_new>true</event\_new>    <event\_update>true</event\_update>    <event\_lost>true</event\_lost>    <use\_multipart>true</use\_multipart>    <use\_event\_buffer>true</use\_event\_buffer>    <user />    <password />    <http\_auth\_type>0</http\_auth\_type>    <send\_second\_image>false</send\_second\_image>    <second\_image\_type>21</second\_image\_type>    <path\_template />    <x\_auth\_key /></cloud\_config>'
```

```bash
POST /local/fflprapp/cloud.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><cloud\_config>    <url>MTAuMC41LjIyMzo3MDAx</url>    <latitude>50.418114</latitude>    <longitude>30.476213</longitude>    <sensorProviderID>PostmanConfigured</sensorProviderID>    <protocol>8</protocol>    <enable>true</enable>    <skip\_image\_in\_post>true</skip\_image\_in\_post>    <event\_new>true</event\_new>    <event\_update>true</event\_update>    <event\_lost>true</event\_lost>    <use\_multipart>true</use\_multipart>    <use\_event\_buffer>true</use\_event\_buffer>    <user />    <password />    <http\_auth\_type>0</http\_auth\_type>    <send\_second\_image>false</send\_second\_image>    <second\_image\_type>21</second\_image\_type>    <path\_template />    <x\_auth\_key /></cloud\_config>
```

To get configurations for 2nd and 3rd profiles use the following requests:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/cloud2.cgi"
```

```bash
POST /local/fflprapp/cloud2.cgiHost: <servername>
```

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/cloud3.cgi"
```

```bash
POST /local/fflprapp/cloud3.cgiHost: <servername>
```

Response sample HTTP

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><cloud\_config>    <url>aHR0cDovLzEwLjAuNS4yMjM6ODA3Ny9saXN0ZW5lci5waHA=</url>    <latitude>50.418114</latitude>    <longitude>30.476213</longitude>    <sensorProviderID>PostmanConfigured</sensorProviderID>    <protocol>1</protocol>    <enable>true</enable>    <skip\_image\_in\_post>false</skip\_image\_in\_post>    <event\_new>true</event\_new>    <event\_update>true</event\_update>    <event\_lost>true</event\_lost>    <use\_multipart>true</use\_multipart>    <use\_event\_buffer>true</use\_event\_buffer>    <user />    <password />    <http\_auth\_type>0</http\_auth\_type>    <send\_second\_image>false</send\_second\_image>    <second\_image\_type>21</second\_image\_type>    <path\_template />    <x\_auth\_key /></cloud\_config>
```

Response sample FTP

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="UTF-8" ?><cloud\_config>    <url>ZnRwOi8vMTAuMC4zLjI0MToyMQ==</url>    <user>user</user>    <password>dXNlcg==</password>    <latitude>50.418114</latitude>    <longitude>30.476213</longitude>    <sensorProviderID>PostmanConfigured</sensorProviderID>    <protocol>16</protocol>    <use\_multipart>false</use\_multipart>    <use\_event\_buffer>true</use\_event\_buffer>    <event\_new>true</event\_new>    <event\_update>false</event\_update>    <event\_lost>false</event\_lost>    <send\_second\_image>false</send\_second\_image>    <skip\_image\_in\_post>true</skip\_image\_in\_post>    <enable>true</enable>    <path\_template />    <x\_auth\_key /></cloud\_config>
```

Response sample

```bash
200 OK
```

## Heartbeat Service

The Heartbeat camera service can send a message with camera conditions to a specified web service in the JSON format. The sending period can be customized, with ranges between 5 to 60 minutes and up to once every 24 hours, as can the JSON fields in the messages.

The following table provides the information that can be included in the JSON message:

| Section | Field Name | Description |
| --- | --- | --- |
| `System` | timestamp | The date and time when the information was received. |
| `Identify` | Platform | The camera name. |
|  | Version | The AXIS OS version. |
|  | ipAddress | The camera’s IP version. |
|  | macAddress | The camera’s MAC address. |
|  | osVersion | The version of the operating system installed on the camera. |
|  | anprVersion | The ANPR application version. |
| `ALPV` | Version | The ALPV application version. |
|  | device\_id | The device ID name specified in the camera’s Integration settings. |
|  | numFrames | The number of frames. |
|  | numFramesAvg | The average number of frames. |
|  | numberOfReads | The number of reads. |
| `Services` | Available Memory | The amount of available memory on the camera. |

Package sample

```bash
Host: 10.0.3.196:8080Authorization: Basic cm9vdDpwYXNzAccept: \*/\*Content-Type: application/jsonContent-Length: <content length>{  'system': {    'timestamp': '2023-03-10T10:13:24.000Z'  },  'identify': {    'platform': 'AXIS P1447-LE',    'version': '11.1.72',    'ipAddress': '10.0.3.167',    'macAddress': 'AC:CC:8E:9B:B1:6D',    'osVersion': '11.1.72',    'anprVersion': '2.7.1'  },  'ALPV': {    'device\_ID': 'defaultID',    'version': '2.7.1',    'numFrames': '2476',    'numFramesAvg': '5',    'numberOfReads': '51'  }}
```

### Configure Heartbeat service

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/config\_hb.cgi" \\  --data '<?xml version="1.0" encoding="UTF-8" ?><hb\_config>    <url>aHR0cDovLzEwLjAuNS4yMjM6ODA3Ny9saXN0ZW5lci5waHA=</url>    <user>user</user>    <password>dXNlcg==</password>    <period>10</period>    <enable>true</enable>    <x\_auth\_key />    <http\_auth\_type>0</http\_auth\_type></hb\_config>'
```

```bash
POST /local/fflprapp/config\_hb.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="UTF-8" ?><hb\_config>    <url>aHR0cDovLzEwLjAuNS4yMjM6ODA3Ny9saXN0ZW5lci5waHA=</url>    <user>user</user>    <password>dXNlcg==</password>    <period>10</period>    <enable>true</enable>    <x\_auth\_key />    <http\_auth\_type>0</http\_auth\_type></hb\_config>
```

| Field | Value |
| --- | --- |
| `URL` | The base-64 encoded URL. |
| `User` | The user. |
| `Password` | The base-64 encoded password. |
| `Period` | The interval between messages, measured in minutes: `5, 10, 30, 60, 1440` |
| `Enable` | Enables or disables the Hearbeat service. Can be either true or false. |
| `x_auth_key` | The Auth-Header |
| `http_auth_type` |  |

Response sample

```bash
200 OK
```

### Configure and send Heartbeat service data

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fflprapp/config\_hb\_data.cgi" \\  --data '{    "system": {        "timestamp": true    },    "identify": {        "platform": true,        "version": false,        "ipAddress": true,        "macAddress": false,        "osVersion": true,        "anprVersion": false    },    "ALPV": {        "version": true,        "device\_ID": true,        "numFrames": false,        "numFramesAvg": true,        "numberofReads": true    },    "services": {        "Available Memory": false    }}'
```

```bash
POST /local/fflprapp/config\_hb\_data.cgiHost: <servername>Content-Type: application/json{    "system": {        "timestamp": true    },    "identify": {        "platform": true,        "version": false,        "ipAddress": true,        "macAddress": false,        "osVersion": true,        "anprVersion": false    },    "ALPV": {        "version": true,        "device\_ID": true,        "numFrames": false,        "numFramesAvg": true,        "numberofReads": true    },    "services": {        "Available Memory": false    }}
```

Response sample

```bash
200 OK
```

## Direct integration
### 2N integration

This part will show you how to integrate AXIS License Plate Verifier with 2N devices.

#### Get 2N integration settings

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/config\_2n.cgi"
```

```bash
GET /local/fflprapp/config\_2n.cgiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><tn\_config>    <url>127.0.0.11</url>    <enable>true</enable>    <user>operator</user>    <password>YWQ=</password>    <https>false</https>    <accessPoint>1</accessPoint>    <event\_on\_direction>2</event\_on\_direction></tn\_config>
```

#### Configure 2N integration in ALPV

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/config\_2n.cgi" \\  --data '<?xml version="1.0" encoding="utf-8" ?><tn\_config>    <url>127.0.0.11</url>    <user>operator</user>    <password>YWQ=</password>    <enable>true</enable>    <https>false</https>    <accessPoint>1</accessPoint>    <event\_on\_direction>2</event\_on\_direction></tn\_config>'
```

```bash
POST /local/fflprapp/config\_2n.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><tn\_config>    <url>127.0.0.11</url>    <user>operator</user>    <password>YWQ=</password>    <enable>true</enable>    <https>false</https>    <accessPoint>1</accessPoint>    <event\_on\_direction>2</event\_on\_direction></tn\_config>
```

| Field | Value |
| --- | --- |
| `URL` | The 2N device URL. |
| `User` | The 2N device user. |
| `Password` | The 2N device password. |
| `Enable` | Enable or disable ALPV integration. Can be either true or false. |
| `https` | Enable or disable the secure integration connection via HTTPS. Can be either true or false. |
| `accessPoint` | Entry = 0 Exit = 1 |
| `event_on_direction` | Any = 0 In = 2 Out = 3 |

Response sample

```bash
200 OK
```

### Genetec integration

This part will show you how to integrate AXIS License Plate Verifier with Genetec Video Management Systems to send events.

#### Get Genetic integration settings

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/config\_gsc.cgi"
```

```bash
GET /local/fflprapp/config\_gsc.cgiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><gsc\_config>    <url>http://10.0.5.223:8077</url>    <enable>true</enable>    <user />    <password />    <https>false</https>    <cameraID>AXIS P1447-LE</cameraID></gsc\_config>
```

#### Configure Genetec integration

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/config\_gsc.cgi" \\  --data '<?xml version="1.0" encoding="utf-8" ?><gsc\_config>    <url>http://10.0.5.223:8077</url>    <enable>true</enable>    <user />    <password />    <cameraID>AXIS P1447-LE</cameraID></gsc\_config>'
```

```bash
POST /local/fflprapp/config\_gsc.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><gsc\_config>    <url>http://10.0.5.223:8077</url>    <enable>true</enable>    <user />    <password />    <cameraID>AXIS P1447-LE</cameraID></gsc\_config>
```

| Field | Value |
| --- | --- |
| `URL` | The 2N device URL. |
| `User` | The Genetec user. |
| `Password` | The Genetec password. |
| `Enable` | Enable or disable ALPV integration. Can be either true or false. |
| `cameraID` | The camera ID. |

Response sample

```bash
200 OK
```

The following is an example for an ALPV event sent to Genetec.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/lpringestion/Reads" \\  --data '{    "ReferenceReadId": "1802305026703433",    "ReferenceCameraId": "ACCC8E9BB16D",    "Plate": "AXIS1234",    "Confidence": "0.95",    "PlateStateProvince": "AXIS",    "PlateImage": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII=",    "ContextImage": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII=",    "CameraName": "AXIS P1447-LE",    "VehicleDirection": "In",    "ReadTimeUtc": "2023-12-11T14:30:26.703Z"}'
```

```bash
POST /lpringestion/ReadsHost: <servername>Content-Type: application/json{    "ReferenceReadId": "1802305026703433",    "ReferenceCameraId": "ACCC8E9BB16D",    "Plate": "AXIS1234",    "Confidence": "0.95",    "PlateStateProvince": "AXIS",    "PlateImage": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII=",    "ContextImage": "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAQMAAAD+wSzIAAAABlBMVEX///+/v7+jQ3Y5AAAADklEQVQI12P4AIX8EAgALgAD/aNpbtEAAAAASUVORK5CYII=",    "CameraName": "AXIS P1447-LE",    "VehicleDirection": "In",    "ReadTimeUtc": "2023-12-11T14:30:26.703Z"}
```

## Application API
### Get ALPV settings

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/config.cgi"
```

```bash
GET /local/fflprapp/config.cgiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><configuration>    <roi>        <left>50</left>        <top>50</top>        <right>475</right>        <bottom>950</bottom>        <width>425</width>        <height>900</height>        <angle>0</angle>    </roi>    <roitwo>        <left>525</left>        <top>50</top>        <right>475</right>        <bottom>950</bottom>        <width>425</width>        <height>900</height>        <angle>0</angle>    </roitwo>    <direction>        <angle>180000</angle>    </direction>    <direction2>        <angle>180000</angle>    </direction2>    <active\_roi>2</active\_roi>    <roi1\_view>0</roi1\_view>    <roi2\_view>0</roi2\_view>    <plate>        <plate\_min\_size\_percent>130</plate\_min\_size\_percent>        <plate\_min\_size>130</plate\_min\_size>        <plate\_max\_size>300</plate\_max\_size>        <plate\_min\_size\_symb>5</plate\_min\_size\_symb>        <plate\_max\_size\_symb>10</plate\_max\_size\_symb>        <threshold>0.700000</threshold>        <mmr\_threshold>10</mmr\_threshold>    </plate>    <sdCardStatus>1</sdCardStatus>    <mmr\_enabled>1</mmr\_enabled>    <cropModeFlag toggle="yes">1</cropModeFlag>    <smallPicModeFlag toggle="no">1</smallPicModeFlag>    <rulesEnableFlag toggle="yes">1</rulesEnableFlag>    <dumpYUVFlag toggle="yes">0</dumpYUVFlag>    <detectorOnlyFlag toggle="yes">0</detectorOnlyFlag>    <saveReportsFlag toggle="yes">0</saveReportsFlag>    <showColorFlag toggle="yes">0</showColorFlag>    <showColorConfidenceFlag toggle="yes">0</showColorConfidenceFlag>    <showPlateConfFlag toggle="yes">0</showPlateConfFlag>    <showDirectionFlag toggle="yes">0</showDirectionFlag>    <showProcessedTimeFlag toggle="yes">0</showProcessedTimeFlag>    <showDebug toggle="yes">0</showDebug>    <ttl>10000</ttl>    <result\_delay>0</result\_delay>    <barrier\_mode>0</barrier\_mode>    <barrier\_priority>0</barrier\_priority>    <barrier\_vehicle\_direction>0</barrier\_vehicle\_direction>    <barrier\_roi>0</barrier\_roi>    <ipc\_login>root</ipc\_login>    <ipc\_password>\*\*\*\*\*\*</ipc\_password>    <relay\_port>2</relay\_port>    <relay\_port\_virtual>-1</relay\_port\_virtual>    <relay\_type>0</relay\_type>    <full\_frame>0</full\_frame>    <full\_frame\_downscale>2</full\_frame\_downscale>    <bw\_ldist>1</bw\_ldist>    <bw\_strict>0</bw\_strict>    <getframe\_driver>0</getframe\_driver>    <lpr\_text\_overlay>0</lpr\_text\_overlay>    <lpr\_text\_overlay\_duration>2</lpr\_text\_overlay\_duration>    <lpr\_text\_overlay\_format>JUYgJVggeyVwbGF0ZX0=</lpr\_text\_overlay\_format>    <nocountry\_filter>0</nocountry\_filter>    <plate\_min\_size\_symb>5</plate\_min\_size\_symb>    <plate\_max\_size\_symb>10</plate\_max\_size\_symb>    <threshold>0.700000</threshold>    <mmr\_threshold>10</mmr\_threshold>    <sdCardStatus>1</sdCardStatus>    <mmr\_enabled>1</mmr\_enabled>    <cropModeFlag toggle="yes">1</cropModeFlag>    <smallPicModeFlag toggle="no">1</smallPicModeFlag>    <rulesEnableFlag toggle="yes">1</rulesEnableFlag>    <dumpYUVFlag toggle="yes">0</dumpYUVFlag>    <detectorOnlyFlag toggle="yes">0</detectorOnlyFlag>    <saveReportsFlag toggle="yes">0</saveReportsFlag>    <showColorFlag toggle="yes">0</showColorFlag>    <showColorConfidenceFlag toggle="yes">0</showColorConfidenceFlag>    <showPlateConfFlag toggle="yes">0</showPlateConfFlag>    <showDirectionFlag toggle="yes">0</showDirectionFlag>    <showProcessedTimeFlag toggle="yes">0</showProcessedTimeFlag>    <showDebug toggle="yes">0</showDebug>    <ttl>10000</ttl>    <result\_delay>0</result\_delay>    <barrier\_mode>0</barrier\_mode>    <barrier\_priority>0</barrier\_priority>    <barrier\_vehicle\_direction>0</barrier\_vehicle\_direction>    <barrier\_roi>0</barrier\_roi>    <ipc\_login>root</ipc\_login>    <ipc\_password>\*\*\*\*\*\*</ipc\_password>    <relay\_port>2</relay\_port>    <relay\_port\_virtual>-1</relay\_port\_virtual>    <relay\_type>0</relay\_type>    <full\_frame>0</full\_frame>    <full\_frame\_downscale>2</full\_frame\_downscale>    <bw\_ldist>1</bw\_ldist>    <bw\_strict>0</bw\_strict>    <getframe\_driver>0</getframe\_driver>    <lpr\_text\_overlay>0</lpr\_text\_overlay>    <lpr\_text\_overlay\_duration>2</lpr\_text\_overlay\_duration>    <lpr\_text\_overlay\_format>JUYgJVggeyVwbGF0ZX0=</lpr\_text\_overlay\_format>    <nocountry\_filter>0</nocountry\_filter>    <plate\_min\_size\_symb>5</plate\_min\_size\_symb>    <plate\_max\_size\_symb>10</plate\_max\_size\_symb>    <config\_version>1</config\_version>    <frame\_rotate>0</frame\_rotate>    <keep\_events>0</keep\_events>    <keep\_events\_period>0</keep\_events\_period>    <stored\_events>35646</stored\_events>    <defaultActionID>3</defaultActionID>    <pulseDuration>3000</pulseDuration>    <lprUseCase>5</lprUseCase>    <debugLevel>1</debugLevel>    <login>admin</login>    <password>ZDNSbVpYa3hNdz09</password>    <security>        <use\_https>0</use\_https>        <selfsigned\_allow>0</selfsigned\_allow>        <curl\_CApath>/etc/certs/mgmt/ca/</curl\_CApath>        <curl\_CApath\_enabled>1</curl\_CApath\_enabled>    </security>    <camera>        <iskit>0</iskit>        <isparamsoptimal>0</isparamsoptimal>        <wdr>1</wdr>        <contrast>50</contrast>        <localcontrast>50</localcontrast>        <maxgain>42</maxgain>        <recommended>            <wdr>0</wdr>            <maxexposuretime>500</maxexposuretime>            <maxgain>24</maxgain>            <contrast>50</contrast>            <localcontrast>20</localcontrast>        </recommended>    </camera>    <initialsetupdone>1</initialsetupdone>    <initialsetupstage>0</initialsetupstage>    <CountryPriority />    <StatePriority />    <curl\_connect\_timeout>10000</curl\_connect\_timeout>    <events\_storage\_size>1000</events\_storage\_size>    <resolution>        <width access="priv">1920</width>        <height access="priv">1080</height>        <fk access="priv">1</fk>        <ipc\_password\_valid access="priv">1</ipc\_password\_valid>    </resolution>    <configFileName access="const">localdata/cfg/fflprapp\_config.xml</configFileName>    <sqliteName access="const">/var/spool/storage/SD\_DISK/fflprapp/fflprapp\_events\_mmr03.db</sqliteName>    <imagesPath access="priv">/var/spool/storage/SD\_DISK/fflprapp/images</imagesPath>    <logsPath access="priv">/var/spool/storage/SD\_DISK/fflprapp/logs</logsPath>    <exportPath access="priv">export</exportPath>    <maxEventsCount access="priv">100000</maxEventsCount>    <logfileSize access="priv">0</logfileSize>    <logfilesNum access="priv">10</logfilesNum>    <httpPort access="priv">8765</httpPort>    <documentRoot access="priv">.</documentRoot></configuration>
```

### Get Area of Interest configuration

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/api.cgi?api=getrroi"
```

```bash
GET /local/fflprapp/api.cgi?api=getrroiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<pre>    ROI1 is activeX0,Y0 = \[96, 54\]X1,Y1 = \[1824, 54\]X2,Y2 = \[1824, 1026\]X3,Y3 = \[96, 1026\]X4,Y4 = \[0, 0\]X5,Y5 = \[0, 0\]X6,Y6 = \[0, 0\]X7,Y7 = \[0, 0\]</pre>
```

### Set Area of Interest configuration

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/config.cgi" \\  --data '<?xml version="1.0" encoding="utf-8" ?><configuration>    <active\_roi>2</active\_roi>    <roi>        <left>50</left>        <top>50</top>        <right>350</right>        <bottom>350</bottom>        <width>300</width>        <height>300</height>        <angle>0</angle>    </roi>    <roitwo>        <left>500</left>        <top>50</top>        <right>990</right>        <bottom>990</bottom>        <width>425</width>        <height>990</height>        <angle>3000</angle>    </roitwo></configuration>'
```

```bash
POST /local/fflprapp/config.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><configuration>    <active\_roi>2</active\_roi>    <roi>        <left>50</left>        <top>50</top>        <right>350</right>        <bottom>350</bottom>        <width>300</width>        <height>300</height>        <angle>0</angle>    </roi>    <roitwo>        <left>500</left>        <top>50</top>        <right>990</right>        <bottom>990</bottom>        <width>425</width>        <height>990</height>        <angle>3000</angle>    </roitwo></configuration>
```

Response sample

```bash
200 OK
```

## Car direction
### Change direction angle

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fflprapp/config\_json.cgi" \\  --data '{  "api": "setconfig",  "config": "roi",  "roi": \[    {      "id": 1,      "name": "roi1",      "type": "polygon",      "active": true,      "angle": <0-360000>,      "coordinates": \[        \[          50,          50        \],        \[          950,          50        \],        \[          950,          950        \],        \[          50,          950        \]      \]    },    {      "id": 2,      "name": "roi2",      "type": "polygon",      "active": false,      "angle": <0-360000>,      "coordinates": \[        \[          525,          50        \],        \[          950,          50        \],        \[          950,          950        \],        \[          525,          950        \]      \]    }  \]}'
```

```bash
POST /local/fflprapp/config\_json.cgiHost: <servername>Content-Type: application/json{  "api": "setconfig",  "config": "roi",  "roi": \[    {      "id": 1,      "name": "roi1",      "type": "polygon",      "active": true,      "angle": <0-360000>,      "coordinates": \[        \[          50,          50        \],        \[          950,          50        \],        \[          950,          950        \],        \[          50,          950        \]      \]    },    {      "id": 2,      "name": "roi2",      "type": "polygon",      "active": false,      "angle": <0-360000>,      "coordinates": \[        \[          525,          50        \],        \[          950,          50        \],        \[          950,          950        \],        \[          525,          950        \]      \]    }  \]}
```

Response sample

```bash
200 OK
```

## List management
### Get list settings

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/list\_mgmt.cgi"
```

```bash
GET /local/fflprapp/list\_mgmt.cgiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/json{    "lists": \[        {            "id": "1",            "name": "Allow list",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "allow"        },        {            "id": "2",            "name": "Block list",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "block"        },        {            "id": "3",            "name": "Custom list",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "none"        }    \]}
```

| Key | Value |
| --- | --- |
| `Id` | Lists the ID string. |
| `Name` | Lists the name. |
| `Schedule` | A JSON object. |
| `Enabled` | Can be either `true` or `false`. |
| `start_time` | The start time, measured in seconds. |
| `end_time` | The end time, measured in seconds. |
| `Mon...Sun` | Days of the week when the list schedule will work. Can be either `true` or `false`. |
| `Mode` | The list mode. Can be `allow | block | none`. |

### Change list settings

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fflprapp/list\_mgmt.cgi" \\  --data '{    "lists": \[        {            "id": "1",            "name": "Allow list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": false,                    "Tue": false,                    "Wed": false,                    "Thu": true,                    "Fri": false,                    "Sat": false,                    "Sun": false                }            \]        },        {            "id": "2",            "name": "Block list",            "mode": "block",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        },        {            "id": "3",            "name": "Custom list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        }    \]}'
```

```bash
POST /local/fflprapp/list\_mgmt.cgiHost: <servername>Content-Type: application/json{    "lists": \[        {            "id": "1",            "name": "Allow list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": false,                    "Tue": false,                    "Wed": false,                    "Thu": true,                    "Fri": false,                    "Sat": false,                    "Sun": false                }            \]        },        {            "id": "2",            "name": "Block list",            "mode": "block",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        },        {            "id": "3",            "name": "Custom list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        }    \]}
```

Response sample

```bash
200 OKContent-Type: application/json{    "lists": \[        {            "id": "1",            "name": "Allow list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": false,                    "Tue": false,                    "Wed": false,                    "Thu": true,                    "Fri": false,                    "Sat": false,                    "Sun": false                }            \]        },        {            "id": "2",            "name": "Block list",            "mode": "block",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        },        {            "id": "3",            "name": "Custom list",            "mode": "allow",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "86340",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \]        }    \]}
```

### Rename lists

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/list\_mgmt.cgi"
```

```bash
POST /local/fflprapp/list\_mgmt.cgiHost: <servername>
```

The list can be renamed by specifying the new name in the `name` field of the corresponding list in the request body.

Request sample

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/local/fflprapp/list\_mgmt.cgi" \\  --data '{    "lists": \[        {            "id": "1",            "name": "<allow list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "allow"        },        {            "id": "2",            "name": "<block list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "block"        },        {            "id": "3",            "name": "<custom list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "none"        }    \]}'
```

```bash
POST /local/fflprapp/list\_mgmt.cgiHost: <servername>Content-Type: application/json{    "lists": \[        {            "id": "1",            "name": "<allow list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "allow"        },        {            "id": "2",            "name": "<block list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "block"        },        {            "id": "3",            "name": "<custom list name>",            "schedule": \[                {                    "enabled": false,                    "start\_time": "0",                    "end\_time": "0",                    "Mon": true,                    "Tue": true,                    "Wed": true,                    "Thu": true,                    "Fri": true,                    "Sat": true,                    "Sun": true                }            \],            "mode": "none"        }    \]}
```

Response sample

```bash
200 OK
```

### Get Allow/Block/Custom list

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/<list name>.cgi"
```

```bash
GET /local/fflprapp/<list name>.cgiHost: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<?xml version="1.0" encoding="UTF-8" ?><bw\_list mode="<list mode>">    <s>M SR1669,09-29-2023,car\_test\_2</s>    <s>M UG0104,09-29-2023,test\_more\_updates</s></bw\_list>
```

| Parameter | Value |
| --- | --- |
| `<list name>` | `allow list | block list | custom list` |
| `<list mode>` | The list name: `allow | block | custom` |

### Add a single plate to the Allow/Block/Custom list

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/api.cgi?api=addplate&plate=<plate text>,<plate date>,<description>&list=<list name>"
```

```bash
GET /local/fflprapp/api.cgi?api=addplate&plate=<plate text>,<plate date>,<description>&list=<list name>Host: <servername>
```

| Parameter | Value |
| --- | --- |
| `Plate` | The plate text with date and description: `AA12DD,12-12-2023,Plate_description` |
| `List` | The list name: `allow | block | custom` |

Response sample

```bash
200 OK
```

### Add a batch of plates to the Allow/Block/Custom list

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/xml" \\  "http://<servername>/local/fflprapp/<list name>.cgi" \\  --data '<?xml version="1.0" encoding="utf-8" ?><bw\_list mode="<list mode>">    <s>AA123DD</s>    <s>AA124DD</s></bw\_list>'
```

```bash
POST /local/fflprapp/<list name>.cgiHost: <servername>Content-Type: application/xml<?xml version="1.0" encoding="utf-8" ?><bw\_list mode="<list mode>">    <s>AA123DD</s>    <s>AA124DD</s></bw\_list>
```

| Parameter | Value |
| --- | --- |
| `<list name>` | `allow_list`, `block_list`, `custom_list` |
| `<list mode>` | `allow`, `block`, `custom` |

Response sample

```bash
200 OK
```

### Remove a single plate from the Allow/Block/Custom list

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/api.cgi?api=delplate&plate=<plate text>&list=<list name>"
```

```bash
GET /local/fflprapp/api.cgi?api=delplate&plate=<plate text>&list=<list name>Host: <servername>
```

| Parameter | Value |
| --- | --- |
| `<plate text>` | The plate text that should be deleted. |
| `<list name>` | `allow`, `block`, `custom` |

Response sample

```bash
200 OK
```

### Export a Allow/Block/Custom list

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/api.cgi?api=export<list name>"
```

```bash
GET /local/fflprapp/api.cgi?api=export<list name>Host: <servername>
```

| Parameter | Value |
| --- | --- |
| `<list name>` | `allow`, `block`, `custom` |

Response sample

```bash
200 OK
```

```bash
M WR6677,09-29-2023,Most wanted carTÖL SL123,09-29-2023,car\_test\_1
```

### Import a list as a .csv file

Use the following sequence of commands to upload the Allow, Block or Custom list to your camera as a .csv file.

1.  Create a new list:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/upload.cgi?command=new&list=<file name>.csv"
    ```
    
    ```bash
    POST /local/fflprapp/upload.cgi?command=new&list=<file name>.csvHost: <servername>
    ```
    
2.  Upload data:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/upload.cgi?command=upload&list=<file name>.csv"
    ```
    
    ```bash
    POST /local/fflprapp/upload.cgi?command=upload&list=<file name>.csvHost: <servername>
    ```
    
3.  Save and apply:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/upload.cgi?command=save&list=<file name>.csv"
    ```
    
    ```bash
    POST /local/fflprapp/upload.cgi?command=save&list=<file name>.csvHost: <servername>
    ```
    

Shell script example

```bash
#!/bin/bash#example:#./send\_list.sh block root:pass 10.0.3.167 block\_list.csv#./send\_list.sh allow root:pass 10.0.3.167 allow\_list.csv#set -x#clean temporary folderrm -rf .$1#recreate temporary folder .block or .allowmkdir .$1#go to temporary foldercd .$1#split input file in small chunkssplit -l 500 ../$4#Create new listcurl --anyauth -u "$2" -X POST -d "command=new&list=$1" http://$3/local/fflprapp/upload.cgi#upload datafor i in \`ls\`;docurl --anyauth -u "$2" -X POST -d "command=upload&list=$1" --data-urlencode "data@$i" http://$3/local/fflprapp/upload.cgidone#save&apply listcurl --anyauth -u "$2" -X POST -d "command=save&list=$1" http://$3/local/fflprapp/upload.cgi#leave temporary foldercd .. #data in a temporary folder not deleted for checking !
```

## Event search and download
### Search events

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/events.cgi?timestampfrom=<from>×tampto=<to>"
```

```bash
GET /local/fflprapp/events.cgi?timestampfrom=<from>×tampto=<to>Host: <servername>
```

| Key | Value example | Description |
| --- | --- | --- |
| `from` | 1702386728835000 | The timstamp that filter records by time, measured in milliseconds (ms). Can be used without `to`. |
| `to` | 1702390328836000 | The timstamp that filter records by time, measured in milliseconds (ms). Can be used without `from`. |
| `text` | RZ9903F | The plate text. |
| `place desc` | String | The plate description from List management if a plate was added to any list. |
| `country` | CZE | The country shown in the ISO 3166-alpha3 format. |
| `car_type` | 1 | CAR = 1; BUS = 2; TRUCK = 32 |
| `car_color` | 0 | 65536 = for any or undefined 0 = Beige 1 = Black 2 = Blue 3 = Brown 4 = Gray 5 = Green 6 = Orange 7 = Red 8 = White 9 = Yellow 10 = Silver |
| `roi_id` | \-1 |  |
| `car_direction` | \-1 | \-1 for any |
| `car_view` | 1 | Rear = 1; Front = 0 |
| `Action` | 1 | The filter used when an action is taken. 1 = opened 0 = no action |
| `offset` |  | The amount of record that can be skipped before filling a reply, such as the SQL OFFSET clause. |
| `Limit` | 18 | Limit the result records. |

Response sample

```bash
200 OKContent-Type: application/xml<events>    <currentTimestampUs>1702390328555082</currentTimestampUs>    <event>        <TS>CAR</TS>        <MOD\_TS>2023-12-12 16:12:04 EET</MOD\_TS>        <END\_TS>0</END\_TS>        <CAR\_ID>42628</CAR\_ID>        <LPR>MSR1669</LPR>        <LPR\_UTF8>M SR1669</LPR\_UTF8>        <LPR\_UNICODE>\\u004d\\u0053\\u0052\\u0031\\u0036\\u0036\\u0039</LPR\_UNICODE>        <RTIME>223.0</RTIME>        <ACTION>100</ACTION>        <ACT\_PARAM>Allow list</ACT\_PARAM>        <THRESHOLD>0.701837122440338</THRESHOLD>        <ROI\_X>96</ROI\_X>        <ROI\_Y>54</ROI\_Y>        <ROI\_W>1728</ROI\_W>        <ROI\_H>972</ROI\_H>        <LP\_X>564</LP\_X>        <LP\_Y>478</LP\_Y>        <LP\_W>220</LP\_W>        <LP\_H>32</LP\_H>        <ROI\_ID>1</ROI\_ID>        <ROI\_IDU>0</ROI\_IDU>        <FRAMES>0</FRAMES>        <DIRECTION>2</DIRECTION>        <LP\_BMP>            tools.cgi?action=getImage & name=53/20231212161204\_601572lp\_MSR1669\_8565355.jpg        </LP\_BMP>        <ROI\_BMP>            tools.cgi?action=getImage & name=51/20231212161204\_259638roi\_MSR1669\_8565354.jpg        </ROI\_BMP>        <COUNTRY>DEU</COUNTRY>        <LP\_LIST\_MODE>1</LP\_LIST\_MODE>        <LP\_DESCRIPTION>car\_test\_2</LP\_DESCRIPTION>        <LP\_REGION\_UTF8>München</LP\_REGION\_UTF8>        <ISO3166\_2\_CODE />        <LP\_TYPE>0</LP\_TYPE>        <EXT1 />        <EXT2 />        <EXT3 />        <CAR\_M\_TYPE>CAR</CAR\_M\_TYPE>        <CAR\_COLOR>BLUE</CAR\_COLOR>        <CAR\_CONF>55.8820610046387</CAR\_CONF>        <CAR\_VIEW>0</CAR\_VIEW>    </event>    <event>        <TS>CAR</TS>        <MOD\_TS>2023-12-12 16:11:58 EET</MOD\_TS>        <END\_TS>0</END\_TS>        <CAR\_ID>42627</CAR\_ID>        <LPR>111WR6677</LPR>        <LPR\_UTF8>111WR6677</LPR\_UTF8>        <LPR\_UNICODE>\\u004d\\u0036\\u0036\\u0037\\u0037</LPR\_UNICODE>        <RTIME>286.0</RTIME>        <ACTION>100</ACTION>        <ACT\_PARAM />        <THRESHOLD>0.739800155162811</THRESHOLD>        <ROI\_X>96</ROI\_X>        <ROI\_Y>54</ROI\_Y>        <ROI\_W>1728</ROI\_W>        <ROI\_H>972</ROI\_H>        <LP\_X>528</LP\_X>        <LP\_Y>444</LP\_Y>        <LP\_W>184</LP\_W>        <LP\_H>30</LP\_H>        <ROI\_ID>1</ROI\_ID>        <ROI\_IDU>0</ROI\_IDU>        <FRAMES>0</FRAMES>        <DIRECTION>2</DIRECTION>        <LP\_BMP>            tools.cgi?action=getImage & name=48/20231212161158\_917432lp\_111WR6677\_8565325.jpg        </LP\_BMP>        <ROI\_BMP>            tools.cgi?action=getImage & name=42/20231212161153\_323507roi\_M6677\_8565307.jpg        </ROI\_BMP>        <COUNTRY>XX</COUNTRY>        <LP\_LIST\_MODE>0</LP\_LIST\_MODE>        <LP\_DESCRIPTION />        <LP\_REGION\_UTF8 />        <ISO3166\_2\_CODE />        <LP\_TYPE>0</LP\_TYPE>        <EXT1 />        <EXT2 />        <EXT3 />        <CAR\_M\_TYPE>CAR</CAR\_M\_TYPE>        <CAR\_COLOR>BLUE</CAR\_COLOR>        <CAR\_CONF>98.5452041625977</CAR\_CONF>        <CAR\_VIEW>0</CAR\_VIEW>    </event></events>
```

### Statistics

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/fflprapp/search.cgi?limit=0"
```

```bash
GET /local/fflprapp/search.cgi?limit=0Host: <servername>
```

Response sample

```bash
200 OKContent-Type: application/xml<events>    <currentTimestampUs>1702306482677809</currentTimestampUs>    <vcount>        <direction>            <in>978</in>            <out>0</out>            <unk>22</unk>        </direction>        <list>            <blocklist>0</blocklist>            <allowlist>0</allowlist>            <customlist>0</customlist>            <nonelist>1000</nonelist>        </list>        <roi>            <roi1>1000</roi1>            <roi2>0</roi2>        </roi>        <total>1000</total>    </vcount></events>
```