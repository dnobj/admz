---
title: Event logger service
url: "https://developer.axis.com/vapix/physical-access-control/event-logger-service/"
category: vapix
subcategory: physical-access-control
sha256: ebcb97cc5332b69bf9bf69bfbfaba2f0cf1d54875e0a63a00e3e8cbcb9abdf7a
scraped_at: "2026-01-09T15:21:43.062Z"
page_height: 39344
---

# Event logger service

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Event logger service guide

The event logger service is used for event logging and management of events and alarms. The service provides ignore filters and alarm filters as well as functions for fetching events and alarms and for acknowledging alarms. Ignore filters determine if an event should be ignored or if it should be stored in the event log.

Alarm filters determine if an event should be marked as an alarm. Door controllers with device software 1.20 and later support global event distribution, that is, events emitted by one door controller in a door controller network are replicated on all door controllers in the network. When global distribution is enabled, logged events and alarms can be fetched from any door controller in the network, not only from the controller that emitted the event. Global distribution is enabled by default but can be disabled if required, see [Event distribution](#event-distribution). In addition to the Event Logger Service, the ONVIF Profile C conformant AXIS A1001 Network Door Controller supports the ONVIF event framework including real-time pull-point subscription, WS notification and event streaming.

### Ignore filter

Ignore filters determine if an event should be ignored or if it should be stored in the event log. The filter contains a list of key-value pairs of events to ignore and a list of UUID:s specifying the door controllers to which the filter should be applied. Events with key-value pairs and a UUID matching the filter will be ignored. If the filter is applicable to all door controllers, the UUID field can be left empty.

The following example shows how to set up an ignore filter with the key-value pair "a=1" and UUID "abc". An event that has a key "a" with value "1" will be ignored if the event was emitted from the door controller with UUID "abc".

Request

```bash
{    "axloc:SetIgnoreFilter": {        "Filter": \[{ "KeyValues": \[{ "Key": "a", "Value": "1" }\], "UUIDs": \["abc"\] }\]    }}
```

Request

```bash
<axloc:SetIgnoreFilter>    <Filter token="mytoken">        <KeyValues>            <Key>a</Key>            <Value>1</Value>        </KeyValues>        <UUIDs>abc</UUIDs>    </Filter></axloc:SetIgnoreFilter>
```

If the UUID list is empty (or omitted) the filter applies to all door controllers.

Request

```bash
{    "axloc:SetIgnoreFilter": {        "Filter": \[{ "KeyValues": \[{ "Key": "a", "Value": "1" }\] }\]    }}
```

Request

```bash
<axloc:SetIgnoreFilter>    <Filter token="mytoken">        <KeyValues>            <Key>a</Key>            <Value>1</Value>        </KeyValues>    </Filter></axloc:SetIgnoreFilter>
```

It is possible to omit the value in a key-value pair. The following example shows an ignore filter that ignores all events containing the key "b".

Request

```bash
{    "axloc:SetIgnoreFilter": {        "Filter": \[{ "KeyValues": \[{ "Key": "b" }\] }\]    }}
```

Request

```bash
<axloc:SetIgnoreFilter>    <Filter token="mytoken">        <KeyValues>            <Key>b</Key>            <Value />        </KeyValues>    </Filter></axloc:SetIgnoreFilter>
```

To list the current ignore filters, the `axloc:GetIgnoreFilterList` call is used. The response below shows the first `axloc:SetIgnoreFilter` example set up above.

Request

```bash
{    "axloc:GetIgnoreFilterList": {}}
```

Request

```bash
<axloc:GetIgnoreFilterList />
```

Response

```bash
{    "Filter": \[        {            "token": "Axis-00408c184bfa:1381327465.144879000",            "KeyValues": \[{ "Key": "a", "Value": "1" }\],            "UUIDs": \["abc"\]        }    \]}
```

Response

```bash
<axloc:Filter token="mytoken">    <axloc:KeyValues>        <axloc:Key>a</axloc:Key>        <axloc:Value>1</axloc:Value>    </axloc:KeyValues>    <axloc:UUIDs>abc</axloc:UUIDs></axloc:Filter>
```

To remove an ignore filter, use `axloc:RemoveIgnoreFilter` and specify the token of the filter to remove. The token is obtained using axloc:GetIgnoreFilterList.

Request

```bash
{    "axloc:RemoveIgnoreFilter": {        "Token": \["Axis-00408c184bfa:1381327465.144879000"\]    }}
```

Request

```bash
<axloc:RemoveIgnoreFilter>    <Token>mytoken</Token></axloc:RemoveIgnoreFilter>
```

### Alarm filter

Alarm filters determine if an event should be marked as an alarm. Alarms are typically used to mark events that are more important than other events, for example events that require human attention. Alarms are stored in a separate alarm log but are also kept in the event log together with other events. When an alarm is acknowledged, it is removed from the alarm log but is kept in the event log.

The alarm filter syntax is similar to the ignore filter syntax described in the previous section. If no UUID:s are specified, the filter will be applied to all door controllers. If one or more UUID:s are specified, only events from the specified door controllers will be elevated to alarms.

To indicate that an event is marked as an alarm, a special event is sent. This special event cannot be elevated to an alarm as that would cause a cyclic behavior.

If an event matches both an ignore filter and an alarm filter, the event will be marked as an alarm and will also be stored in the event log, that is, the ignore filter is overridden.

Request

```bash
{    "axloc:SetAlarmFilter": {        "Filter": \[{ "KeyValues": \[{ "Key": "a", "Value": "1" }\] }\]    }}
```

Request

```bash
<axloc:SetAlarmFilter>    <Filter token="my\_alarm\_token">        <KeyValues>            <Key>a</Key>            <Value>1</Value>        </KeyValues>    </Filter></axloc:SetAlarmFilter>
```

To list the current alarm filters, the `axloc:GetAlarmFilterList` call is used.

Request

```bash
{    "axloc:GetAlarmFilterList": {}}
```

Request

```bash
<axloc:GetAlarmFilterList />
```

Response

```bash
{    "Filter": \[        {            "token": "Axis-00408c184bfa:1381328407.991173000",            "KeyValues": \[{ "Key": "a", "Value": "1" }\],            "UUIDs": \[\]        }    \]}
```

Response

```bash
<axloc:Filter token="my\_alarm\_token">    <axloc:KeyValues>        <axloc:Key>a</axloc:Key>        <axloc:Value>1</axloc:Value>    </axloc:KeyValues></axloc:Filter>
```

To remove an alarm filter, use `axloc:RemoveAlarmFilter` and specify the token of the filter to remove. The token is obtained using `axloc:GetAlarmFilterList`.

Request

```bash
{    "axloc:RemoveAlarmFilter": {        "Token": \["Axis-00408c184bfa:1381328407.991173000"\]    }}
```

Request

```bash
<axloc:RemoveAlarmFilter>    <Token>my\_alarm\_token</Token></axloc:RemoveAlarmFilter>
```

### Fetch events

Use `axlog:FetchEvents` or `axlog:FetchEvents2` to fetch events from the event log. The event log can contain maximum 30,000 events but only 1000 of these events can be fetch in one call. The calls accepts the following optional parameters: `Start, Stop, Limit, RowID, Descending` and `Filters`. `axlog:FetchEvents2` also supports `FilterSets`. The parameters are described in the following sections.

#### Start and stop time

The `Start` and `Stop` parameters define start and stop times for the time interval in the `axlog:FetchEvents` call. Events with a timestamp within the time interval will be fetched. If `Start` is omitted, year 0 is assumed. If `Stop` is omitted, the time interval has no upper limit, that is, all events until the current time will be fetched. The start and stop times should be specified using the time format in ISO 8601.

Request

```bash
{    "axlog:FetchEvents": {        "Start": "2012-11-27T00:00:00",        "Stop": "2012-11-27T14:00:00"    }}
```

Request

```bash
<axlog:FetchEvents>    <Start>2012-11-27T00:00:00</Start>    <Stop>2012-11-27T14:00:00</Stop></axlog:FetchEvents>
```

#### Limit and RowID

One call to `axlog:FetchEvents` returns maximum 1000 events. If required, for example to improve performance, the maximum number of fetched events can be reduced using the `Limit` parameter.

Request

```bash
{    "axlog:FetchEvents": {        "Limit": 2    }}
```

Request

```bash
<axlog:FetchEvents>    <Limit>2</Limit></axlog:FetchEvents>
```

If the number of events matching a fetch request is larger than the set limit, the reply will have the `More` flag set to true. To fetch the rest of the events matching the request, call `axlog:FetchEvents` again but this time with the `RowID` parameter set to the row id of the last event in the previous response.

Request

```bash
{    "axlog:FetchEvents": {        "Limit": 2,        "RowID": 2    }}
```

Request

```bash
<axlog:FetchEvents>    <Limit>2</Limit>    <RowID>2</RowID></axlog:FetchEvents>
```

#### Descending

The `Descending` parameter is used to sort events in descending order. By default, `Descending` is false and events are sorted in ascending order. To get events in descending order, set `Descending` to true.

Request

```bash
{    "axlog:FetchEvents": {        "Descending": true    }}
```

Request

```bash
<axlog:FetchEvents>    <Descending>true</Descending></axlog:FetchEvents>
```

#### Filters

The `Filters` parameter is used to fetch events of a specific type. The `axlog:FetchEvents` request will return events that match the key-value pairs specified in `Filters`.

Request

```bash
{    "axlog:FetchEvents": {        "Filters": \[            { "Key": "topic0", "Value": "Door" },            { "Key": "topic1", "Value": "State" },            { "Key": "topic2", "Value": "DoorMode" },            { "Key": "State", "Value": "Locked" }        \]    }}
```

Request

```bash
<axlog:FetchEvents>    <Filters>        <Key>topic0</Key>        <Value>Door</Value>        <Key>topic1</Key>        <Value>State</Value>        <Key>topic2</Key>        <Value>DoorMode</Value>        <Key>State</Key>        <Value>Locked</Value>    </Filters></axlog:FetchEvents>
```

`Filters` can contain a single key-value pair or a list of key-value pairs. It is also possible to omit the value and only specify the key.

Request

```bash
{    "axlog:FetchEvents": {        "Filters": \[{ "Key": "State" }\]    }}
```

Request

```bash
<axlog:FetchEvents>    <Filters>        <Key>State</Key>        State        <Value />    </Filters></axlog:FetchEvents>
```

#### FiltersSets

The `FilterSets` parameter provides advanced filtering options and is supported by `axlog:FetchEvents2`. `FilterSets` contains multiple `Filters` fields that are combined with logical OR.

The request below fetches events that match the condition (`SystemReady` AND `0`) OR (`DoorPhysicalState` AND `Closed`).

Request

```bash
{    "axlog:FetchEvents2": {        "FilterSets": \[            {                "Filters": \[                    { "Key": "topic2", "Value": "SystemReady" },                    { "Key": "ready", "Value": "0" }                \]            },            {                "Filters": \[                    { "Key": "topic2", "Value": "DoorPhysicalState" },                    { "Key": "State", "Value": "Closed" }                \]            }        \]    }}
```

#### FetchEvents response

The following is an example of a `axlog:FetchEvents` response, where the request is using filters to only return results from `AccessControl`:

Request

```bash
{    "axlog:FetchEvents": {        "Filters": \[{ "topic0": "AccessControl" }\]    }}
```

Request

```bash
<axlog:FetchEvents>    <axlog:Filters>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:Filters></axlog:FetchEvents>
```

Response

```bash
{    "Event": \[        {            "rowid": 76,            "token": "Axis-00408c184c74:1382951603.616761001",            "UUID": "5581ad80-95b0-11e0-b883-00408c184c74",            "UtcTime": "2013-10-28T09:13:23.018766Z",            "KeyValues": \[                {                    "Key": "CredentialHolderName",                    "Value": "Axis-00408c184c74:1382951566.633213000",                    "Tags": \["onvif-data"\]                },                {                    "Key": "AccessPointToken",                    "Value": "Axis-00408c184c74:1382951520.315392000",                    "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]                },                {                    "Key": "topic2",                    "Value": "Credential",                    "Tags": \[\]                },                {                    "Key": "topic1",                    "Value": "AccessGranted",                    "Tags": \[\]                },                {                    "Key": "topic0",                    "Value": "AccessControl",                    "Tags": \[\]                },                {                    "Key": "CredentialToken",                    "Value": "Axis-00408c184c74:1382951567.312696000",                    "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]                }            \],            "Tags": \[\]        }    \],    "More": false}
```

Response

```bash
<axlog:FetchEventsResponse>    <axlog:Event token="Axis-00408c184c74:1382951603.616761001">        <axlog:rowid>76</axlog:rowid>        <axlog:UUID>5581ad80-95b0-11e0-b883-00408c184c74</axlog:UUID>        <axlog:UtcTime>2013-10-28T09:13:23Z</axlog:UtcTime>        <axlog:KeyValues>            <axlog:Key>CredentialHolderName</axlog:Key>            <axlog:Value>Axis-00408c184c74:1382951566.633213000</axlog:Value>            <axlog:Tags>onvif-data</axlog:Tags>        </axlog:KeyValues>        <axlog:KeyValues>            <axlog:Key>AccessPointToken</axlog:Key>            <axlog:Value>Axis-00408c184c74:1382951520.315392000</axlog:Value>            <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>            <axlog:Tags>onvif-source</axlog:Tags>        </axlog:KeyValues>        <axlog:KeyValues>            <axlog:Key>topic2</axlog:Key>            <axlog:Value>Credential</axlog:Value>        </axlog:KeyValues>        <axlog:KeyValues>            <axlog:Key>topic1</axlog:Key>            <axlog:Value>AccessGranted</axlog:Value>        </axlog:KeyValues>        <axlog:KeyValues>            <axlog:Key>topic0</axlog:Key>            <axlog:Value>AccessControl</axlog:Value>        </axlog:KeyValues>        <axlog:KeyValues>            <axlog:Key>CredentialToken</axlog:Key>            <axlog:Value>Axis-00408c184c74:1382951567.312696000</axlog:Value>            <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>            <axlog:Tags>onvif-data</axlog:Tags>        </axlog:KeyValues>    </axlog:Event>    <axlog:More>false</axlog:More></axlog:FetchEventsResponse>
```

Below is an event shown which has been received using an ONVIF pull-point subscription. The data stored in the event logger can be matched against the real-time event in every detail except namespaces. The namespaces in the topic are not stored in the event logger database and cannot be recreated in the `FetchEvents` call.

```bash
<wsnt:Topic>tns1:AccessControl/AccessGranted/Credential</wsnt:Topic><wsnt:Message>  <tt:Message UtcTime="2013-10-28T09:13:23Z">    <tt:Source>      <tt:SimpleItem Name="AccessPointToken"        Value="Axis-00408c184c74:1382951520.315392000" />    </tt:Source>    <tt:Data>      <tt:SimpleItem Name="CredentialHolderName"        Value="Axis-00408c184c74:1382951566.633213000" />      <tt:SimpleItem Name="CredentialToken"        Value="Axis-00408c184c74:1382951567.312696000" />    </tt:Data>  </tt:Message></wsnt:Message>
```

### Fetching alarms

Use `axlog:FetchAlarms` or `axlog:FetchAlarms2` to fetch alarms. These commands are used in same way and take the same parameters as the `axlog:FetchEvents` and `axlog:FetchEvents2` commands..

The alarm list contains at most 200 alarms, which makes it possible to fetch all of them with one call. However, the limit option is still supported, and is defaulted to 1000 which means all alarms are fetched by default.

Request

```bash
{    "axlog:FetchAlarms": {}}
```

The response with matched alarms will be formatted as the example in section [FetchEvents response](#fetchevents-response).

### Acknowledging alarms

An alarm is acknowledged by removing it from the alarm list. To remove the alarm `axlog:RemoveLoggedAlarm` is used. `axlog:RemoveLoggedAlarm` takes a token array with all the tokens of the alarms to be removed.

Request

```bash
{    "axlog:RemoveLoggedAlarm": {        "Token": \["Axis-00408c184bd0:1382625301.169265000", "Axis-00408c184bd0:1382625330.594026000"\]    }}
```

Request

```bash
<axlog:RemoveLoggedAlarm>    <Token>Axis-00408c184bd0:1382625301.169265000</Token>    <Token>Axis-00408c184bd0:1382625330.594026000</Token></axlog:RemoveLoggedAlarm>
```

### Event distribution

Door controllers with device software 1.20 and later support global event distribution, that is, events emitted by one door controller in a door controller network are replicated on all door controllers in the network. When global distribution is enabled, logged events and alarms can be fetched from any door controller in the network, not only from the controller that emitted the event.

To identify the door controller that emitted the event, an UUID key-value pair is automatically added to all events when global distribution is enabled.

Global distribution is enabled by default, but can be disabled if required. When global distribution is disabled, logged events and alarms are not replicated on other door controllers.

To check whether global distribution is enabled, use `axloc:GetEventDistributionConfig` without any arguments.

Response

```bash
{    "EventDistributionConfig": \[{ "GlobalDistributionEnabled": true }\]}
```

Response

```bash
<axloc:EventDistributionConfig>    <axloc:GlobalDistributionEnabled>true</axloc:GlobalDistributionEnabled></axloc:EventDistributionConfig>
```

To disable global distribution, use `axloc:DisableGlobalDistribution`.

To enable global distribution, use `axloc:EnableGlobalDistribution`.

### Distributed events in pull-point subscriptions

In ONVIF pull-point subscriptions, use content filter "device source" to listen to events from all door controllers in the network. If global event distribution is enabled and device source is not specified, the client receives event notifications from the local door controller only. This is the default behavior. To subscribe to events from all door controllers in the network, add content filter`@Name="Device Source"`. To subscribe to events from selected door controllers, add content filter `@Name="Device Source"` with specified UUIDs.

If global event distribution is disabled, the pull-point subscription must not include content filter device source. If `@Name="Device Source"` is included, the client will not receive any event notifications as the events do not have any device source.

To subscribe to events from all door controllers when global distribution is enabled and from the local door controller when global distribution is disabled, use `boolean(//tt:SimpleItem[@Name="Device Source"])OR NOT( boolean(//tt:SimpleItem[@Name="Device Source"]))`

### Notification topics

The following table lists supported notification topics. Note: The notification topics available in the door controller depend on product configuration and device software version.

Notification topics

| Topic | Description |
| --- | --- |
| Schedule service |  |
| `tns1:Schedule/tnsaxis:Interval` | Emitted when the state of an interval schedule changes. |
| `tns1:Schedule/tnsaxis:Pulse` | Emitted when a pulse schedule becomes active. |
| Door control service |  |
| `tns1:Door/State/DoorMode` | Emitted when a door’s `DoorMode` state changes, for example when the door is accessed. |
| `tns1:Door/State/DoorPhysicalState` | Emitted when a door’s `DoorPhysicalState` changes, for example when the door is opened. |
| `tns1:Door/State/LockPhysicalState` | Emitted when a lock’s `LockPhysicalState` changes, for example when the door becomes unlocked. |
| `tns1:Door/State/DoubleLockPhysicalState` | Emitted when a double-lock’s `DoubleLockPhysicalState` changes. |
| `tns1:Door/State/DoorAlarm` | Emitted when the `DoorAlarm` state changes, that is, when the `OpenTooLongTime` time expires. |
| `tns1:Door/State/DoorFault` | Emitted when the `DoorFault` state changes. |
| `tns1:Door/State/DoorTamper` | Emitted when the `DoorTamper` state changes. |
| `tns1:Door/State/DoorWarning` | Emitted when the `DoorWarning` state changes, that is, when the `PreAlarmTime` expires. |
| `tns1:Door/tnsaxis:Status/BatteryAlarm` | Emitted when the battery in a wireless Aperio door, lock or door monitor changes state, for example when it needs to be replaced. The ID field contains the Aperio device’s hardware address. |
| `tns1:Door/tnsaxis:Status/LockJammed` | Emitted when a wireless Aperio door lock is physically blocked. |
| `tns1:Door/tnsaxis:Status/RadioDisturbance` | Emitted when the radio signal from a wireless Aperio door, lock or door monitor changes state, for example when the signal is disturbed. The `ID` field contains the Aperio device’s hardware address. |
| `tns1:Configuration/Door/Changed` | Emitted when a `Door` is added or updated. |
| `tns1:Configuration/Door/Removed` | Emitted when a `Door` is removed. |
| IdPoint service |  |
| `tns1:IdPoint/tnsaxis:Activity` | Emitted when there is an initial activity at an Id- Point, for example when someone tries to access the door. This event does not contain any sensitive data. |
| `tns1:IdPoint/tnsaxis:Request/PIN` | Emitted when a person has entered a Personal Identification Number (PIN) code at an IdPoint without swiping a card. Input from the keypad is sent in the event. |
| `tns1:IdPoint/tnsaxis:Request/REX` | Emitted when a REX button or similar input device is used. |
| `tns1:IdPoint/tnsaxis:Request/IdData` | Emitted when authentication information is presented at an IdPoint, for example when someone swipes a card or enters a PIN code. The event contains a `Card` field with user identification information such as card data and/or PIN, and a `BitCount` field with the bit length of the card data. Depending on the timeout configuration, card data and PIN can be sent in the same event. |
| `tns1:IdPoint/tnsaxis:Status/BatteryAlarm` | Emitted when the battery in a wireless Aperio Id- Point changes state, for example when it needs to be replaced. The `ID` field contains the Aperio device’s hardware address. |
| `tns1:IdPoint/tnsaxis:Status/RadioDisturbance` | Emitted when the radio signal from a wireless Aperio IdPoint changes state, for example when the signal is disturbed. The `ID` field contains the Aperio device’s hardware address. |
| `tns1:IdPoint/tnsaxis:Timeout` | Emitted when the IdPoint timeout has expired. |
| `tns1:IdPoint/tnsaxis:Tampering` | Emitted when IdPoint tampering is detected. |
| `tns1:Configuration/tnsaxis:IdPoint/Changed` | Emitted when an `IdPoint` is added or updated. |
| `tns1:Configuration/tnsaxis:IdPoint/Removed` | Emitted when an `IdPoint` is removed. |
| `tns1:IdPoint/tnsaxis:Status/SecureChannel` | Indicates the status of the secure channel in a reader. |
| `tns1:IdPoint/tnsaxis:Status/Device` | Emitted when the status of the IdPoint device changes. Only for IdPoint readers using the OSDP protocol. |
| `tns1:IdPoint/tnsaxis:PreAuthorization/tnsaxis:IdData` | Issued when a Whitelist enabled credential has received access from a Whitelist enabled reader. |
| `tns1:IdPoint/tnsaxis:Status/tnsaxis:WhitelistSync/tnsaxis:Error` | Issued to indicate the failure to update a Whitelist of a reader with a specific IdData. |
| `tns1:IdPoint/tnsaxis:Status/tnsaxis:WhitelistSync/tnsaxis:Ongoing` | Issued to indicate whether there exist Whitelist Id:s that are to be sent to a physical lock or not. Ongoing is set to True if IdData exists that need to be sent/removed to/from a physical lock, i.e. if a synchronization is ongoing. Ongoing is set to False if the Whitelist of the lock and the Whitelist of the access controller is identical. |
| Access control service |  |
| `tns1:AccessControl/AccessGranted/Anonymous` | Emitted when an anonymous user is granted access. |
| `tns1:AccessControl/AccessGranted/Credential` | Emitted when a valid credential, that is, a card holder or a user with a PIN, has passed all necessary checks and is granted access. |
| `tns1:AccessControl/AccessTaken/Anonymous` | Emitted when an anonymous user accesses the door after being granted access. |
| `tns1:AccessControl/AccessTaken/Credential` | Emitted when an identified credential, that is, a card holder or a user with a PIN, accesses the door after being granted access. |
| `tns1:AccessControl/AccessNotTaken/Anonymous` | Emitted when an anonymous user who has been granted access does not access the door. |
| `tns1:AccessControl/AccessNotTaken/Credential` | Emitted when an identified credential who has been granted access does not access the door. |
| `tns1:AccessControl/Denied/Anonymous` | Emitted when an anonymous user is denied access. |
| `tns1:AccessControl/Denied/Authentication/InvalidPIN` | Emitted then access is denied because the PIN is not valid. |
| `tns1:AccessControl/Denied/Credential` | Emitted when an identified credential is denied access. |
| `tns1:AccessControl/Denied/CredentialNotFound/Card` | Emitted when access is denied because the card is not stored in the access point. |
| `tns1:AccessControl/Denied/CredentialNotFound/PIN` | Emitted when access is denied because the entered PIN is not stored in the access point. |
| `tns1:AccessControl/Duress` | Emitted when duress access is detected, that is, when the duress PIN code is used. |
| `tns1:AccessPoint/State/Enabled` | Emitted when an `AccessPoint` is enabled or disabled. |
| `tns1:Configuration/AccessPoint/Changed` | Emitted when an `AccessPoint` is added or updated. |
| `tns1:Configuration/AccessPoint/Removed` | Emitted when an `AccessPoint` is removed. |
| `tns1:Configuration/Area/Changed` | Emitted when an `Area` is added or updated. |
| `tns1:Configuration/Area/Removed` | Emitted when an `Area` is removed. |
| `tns1:Configuration/Credential/Changed` | Emitted when a `Credential` is added or updated. |
| `tns1:Configuration/Credential/Removed` | Emitted when a `Credential` is removed. |
| `tns1:Credential/State/ApbViolation` | Emitted when access is denied due to an Anti-Passback violation. |
| Connection service |  |
| `tns1:Device/tnsaxis:PeerConnection` | Emitted when a `ConnectionState` changes. |
| Event logger service |  |
| `tnsaxis:EventLogger/Alarm` | Emitted when an alarm is emitted. An alarm is an event that matches the alarm filter set by `axloc:SetAlarmFilter`. |
| `tnsaxis:EventLogger/DroppedAlarms` | Emitted if alarms are dropped. Events, including events that otherwise would be elevated to alarms, are dropped if there is extremely high activity and the Event Logger Service cannot process all events. `DroppedAlarms` contains the number of alarms that are dropped. |
| `tnsaxis:EventLogger/DroppedEvents` | Emitted if events are dropped. Events are dropped if there is extremely high activity and the Event Logger Service cannot process all events. `DroppedEvents` contains the number of events that are dropped. Frequent `DroppedEvents` events might indicate an error in system setup. |
| Other |  |
| `tns1:Device/tnsaxis:Casing/Open` | Emitted when the product casing is opened or removed. |
| `tns1:Device/tnsaxis:IO/Port` | Emitted when an I/O port configured as input changes state. |
| `tns1:Device/tnsaxis:IO/Virtualinput` | Emitted when a virtual input changes state. |
| `tns1:Device/tnsaxis:IO/Virtualport` | Emitted when the manual trigger changes state. |
| `tns1:Device/tnsaxis:Network/Lost` | Emitted if the network connection is lost. |
| `tns1:Device/tnsaxis:Status/Systemready` | Emitted when the product and all its services have been started. |
| `tns1:Device/tnsaxis:SystemMessage/Actionfailed` | Emitted if an action in the Action service cannot be started. |
| Remote I/O service |  |
| `tnsaxis:RemoteDevice/Connection/Status` | Describes the remote device’s connection status. If true (1), the door controller can communicate with the remote device. If false (0), communication was unsuccessful. Unsuccessful communication can have many reasons, for example wrong credentials, network problems or because the remote device did not respond on a heartbeat. |
| Third party credential service |  |
| `tns1:Configuration/Credential/tnsaxis:ThirdPartyCredentialCreated` | Issued when a new ThirdPartyCredential has been created from the SetThirdPartyCredential API.At this point there may not exist any card data information for this credential.When the provider has aknowledged the credential a `ThirdPartyCredentialEnabled` event will be sent. |
| `tns1:Configuration/Credential/tnsaxis:ThirdPartyCredentialCreatedFailed` | If a ThirdPartyCredential should fail to be created then this event will be issued. |
| `tns1:Configuration/Credential/tnsaxis:ThirdPartyCredentialRemoved` | Issued when a ThirdPartyCredential has been removed via the RemoveThirdPartyCredential API. |
| `tns1:Configuration/Credential/tnsaxis:ThirdPartyCredentialRemovedFailed` | Issued when a ThirdPartyCredential failed to be removed via the RemoveThirdPartyCredential API. |
| `tns1:Configuration/Credential/tnsaxis:ThirdPartyCredentialEnabled` | Issued when the provider has acknowledged the ThirdPartyCredential.Note that the format of the `CredentialCardNumber` is specific for each provider. |
| `tnsaxis:ThirdPartyCredential/Status/ProviderConnection` | Any change in the status of the connection to the provider will generate this event. |

## Event logger service API
### EventLogger service

axlog = [http://www.axis.com/vapix/ws/EventLogger](http://www.axis.com/vapix/ws/EventLogger)

The eventlogger stores events and alarms in a database. These events and alarms can be fetched using the `FetchEvents` and `FetchAlarms` calls.

#### LocalSetting data structure

Local settings stored in DB as keys and values.

The following fields are available:

-   `token`
-   `Value`

#### FilterKeyValue data structure

Key/Value pair for event filter parameters.

The following fields are available:

-   `Key`
-   `Value`

#### KeyValue data structure

Key/Value pair for logged events and alarms.

The following fields are available:

-   `Namespace`
-   `Key`
-   `Value`
-   `Type`
-   `Tags`

#### LoggedEvent data structure

Main structure for stored events.

The following fields are available:

-   `token`
    
-   `UUID`
    
    UUID of the producing device.
    
-   `UtcTime`
    
-   `KeyValues`
    
-   `Tags`
    
-   `Property`
    
-   `DeclarationID`
    

#### LoggedAlarm data structure

Main structure for stored alarms.

The following fields are available:

-   `token`
    
-   `UUID`
    
    UUID of the producing device.
    
-   `UtcTime`
    
-   `KeyValues`
    
-   `Tags`
    
-   `Property`
    
-   `DeclarationID`
    

#### FetchedEventKeyValue data structure

The following fields are available:

-   `Key`
-   `Value`
-   `Tags`

#### FetchedEvent data structure

Main structure for fetching events.

The following fields are available:

-   `rowid`
    
-   `token`
    
-   `UUID`
    
    UUID of the producing device.
    
-   `UtcTime`
    
-   `KeyValues`
    
-   `Tags`
    

#### FetchEvents command

Get stored events matching the supplied filter.

-   Name: `FetchEvents`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `FetchEventsRequest` | This message contains  
  
\- `Start`  
\- `Stop`  
\- `Filters`  
\- `Limit` Limit number of entries returned.  
\- `RowID`  
\- `Descending`  
`xs:dateTime Start [0][1]`  
`xs:dateTime Stop [0][1]`  
`axlog:FilterKeyValue Filters [0][unbounded]`  
`xs:int Limit [0][1]`  
`xs:long RowID [0][1]`  
`xs:boolean Descending [0][1]` |
| `FetchEventsResponse` | This message contains  
  
\- `Event`  
\- `More`  
`axlog:FetchedEvent Event [0][unbounded]`  
`xs:boolean More [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartTime` |  |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStopTime` |  |

#### FetchAlarms command

Get stored alarms matching the supplied filter.

-   Name: `FetchAlarms`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `FetchAlarmsRequest` | This message contains  
  
\- `Start`  
\- `Stop`  
\- `Filters`  
\- `Limit` Limit number of entries returned.  
\- `RowID`  
\- `Descending`  
`xs:dateTime Start [0][1]`  
`xs:dateTime Stop [0][1]`  
`axlog:FilterKeyValue Filters [0][unbounded]`  
`xs:int Limit [0][1]`  
`xs:long RowID [0][1]`  
`xs:boolean Descending [0][1]` |
| `FetchAlarmsResponse` | This message contains  
  
\- `Alarm`  
\- `More`  
`axlog:FetchedEvent Alarm [0][unbounded]`  
`xs:boolean More [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartTime` |  |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStopTime` |  |

#### RemoveLoggedAlarm command

Use `RemoveLoggedAlarm` to remove an alarm from the alarm list.

-   Name: `RemoveLoggedAlarm`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveLoggedAlarmRequest` | This message contains  
  
\- `Token`  
\- `xs:string Token [0][unbounded]` |
| `RemoveLoggedAlarmResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender`, `ter:InvalidArgVal`, `ter:NotFound` |  |

### EventLoggerConfig service

axloc = [http://www.axis.com/vapix/ws/EventLoggerConfig](http://www.axis.com/vapix/ws/EventLoggerConfig)

The eventlogger configuration holds filters for incoming events. These filters are matched against incoming events and decides if an event is either ignored, stays as a normal event or is upgraded to an alarm.

An event that is ignored will not be stored in any database. An event that is upgraded to an alarm is stored in both the event and alarm database.

If an event matches both an ignore filter and an alarm filter then the event will be upgraded to an alarm.

#### KeyValue data structure

A structure containing a key and a value.

The following fields are available:

-   `Key`
-   `Value`

#### IgnoreFilter data structure

A filter for events to be ignored.

The following fields are available:

-   `token`
-   `KeyValues`
-   `UUIDs`

#### AlarmFilter data structure

A filter for matching an event as an alarm.

The following fields are available:

-   `token`
-   `KeyValues`
-   `UUIDs`

#### SetIgnoreFilter command

Use `SetIgnoreFilter` to create and update ignore filters.

-   Name: `SetIgnoreFilter`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetIgnoreFilterRequest` | This message contains  
  
\- `Filter`  
\- `axloc:IgnoreFilter Filter [0][unbounded]` |
| `SetIgnoreFilterResponse` | This message contains  
  
\- `Token` List with the tokens of the created/updated filters.  
  
`xs:string Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### RemoveIgnoreFilter command

Use `RemoveIgnoreFilter` to remove ignore filters.

-   Name: `RemoveIgnoreFilter`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveIgnoreFilterRequest` | This message contains  
  
\- `Token`  
\- `xs:string Token [0][unbounded]` |
| `RemoveIgnoreFilterResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### GetIgnoreFilterList command

Use `GetIgnoreFilterList` to retrieve a list of all ignore filters.

-   Name: `GetIgnoreFilterList`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetIgnoreFilterListRequest` | This message shall be empty. |
| `GetIgnoreFilterListResponse` | This message contains  
  
\- `Filter`  
\- `axloc:IgnoreFilter Filter [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### SetAlarmFilter command

Use `SetAlarmFilter` to create or update alarm filters.

-   Name: `SetAlarmFilter`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAlarmFilterRequest` | This message contains  
  
\- `Filter`  
\- `axloc:AlarmFilter Filter [0][unbounded]` |
| `SetAlarmFilterResponse` | This message contains  
  
\- `Token` List with the tokens of the created/updated filters.  
  
`xs:string Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### RemoveAlarmFilter command

Use `RemoveAlarmFilter` to remove alarm filters.

RemoveAlarmFilter Command

-   Name: `RemoveAlarmFilter`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAlarmFilterRequest` | This message contains  
  
\- `Token`  
\- `xs:string Token [0][unbounded]` |
| `RemoveAlarmFilterResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### GetAlarmFilterList command

Use `GetAlarmFilterList` to retrieve all alarm filters.

-   Name: `GetAlarmFilterList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAlarmFilterListRequest` | This message shall be empty. |
| `GetAlarmFilterListResponse` | This message contains  
  
\- `Filter`  
\- `axloc:AlarmFilter Filter [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### DeclKeyValue data structure

Key/Value pair for logged events and alarms.

The following fields are available:

-   `Namespace`
-   `Key`
-   `Value`
-   `Type`
-   `Tags`
-   `ValueWildcard`

#### Declaration data structure

Main structure for stored alarms.

The following fields are available:

-   `token`
    
-   `UUID`
    
    UUID of the producing device.
    
-   `GlobalDeclarationID`
    
-   `Property`
    
-   `KeyValues`
    
-   `Tags`
    

#### Configuration data structure

A configuration structure containing a key and a value.

The following fields are available:

-   `token`
-   `Value`

#### ServiceCapabilities data structure

The service capabilities reflect optional functionality of a service. The information is static and does not change during device operation. The following capabilities are available:

-   `EnableGlobalEvents`
    
    True if `EnableGlobalEvents` and `DisableGlobalEvents` operations are supported.
    

#### GetServiceCapabilities command

This operation returns the capabilities of the event logger config service.

-   Name: `GetServiceCapabilities`
-   Access Class: PRE\_AUTH

| Message name | Description |
| --- | --- |
| `GetServiceCapabilitiesRequest` | This message shall be empty. |
| `GetServiceCapabilitiesResponse` | This message contains  
  
\- `Capabilities` The capability response message contains the requested event logger config service capabilities using a hierarchical XML capability structure.  
  
`axloc:ServiceCapabilities Capabilities [1][1]` |

#### EventDistributionConfig data structure

The `EventDistributionConfig` structure describes the current event distribution configuration.

The following fields are available:

-   `GlobalDistributionEnabled`
    
    Indicates that events are globally distributed among peers.
    

#### EnableGlobalDistribution command

This operation enables global distribution of generated events among all connected peers.

-   Name: `EnableGlobalDistribution`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `EnableGlobalDistributionRequest` | This message shall be empty. |
| `EnableGlobalDistributionResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The operation is not supported. |

#### DisableGlobalDistribution command

This operation disables global distribution of generated events among all connected peers.

-   Name: `DisableGlobalDistribution`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `DisableGlobalDistributionRequest` | This message shall be empty. |
| `DisableGlobalDistributionResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The operation is not supported. |

#### GetEventDistributionConfig command

The operation returns the current event distribution configuration.

-   Name: `GetEventDistributionConfig`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetEventDistributionConfigRequest` | This message contains  
  
\- `EventDistributionConfig`  
\- `axloc:EventDistributionConfig EventDistributionConfig [1][1]` |
| `GetEventDistributionConfigResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The operation is not supported. |