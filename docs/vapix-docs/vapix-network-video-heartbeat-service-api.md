---
title: Heartbeat service API
url: "https://developer.axis.com/vapix/network-video/heartbeat-service-api/"
category: vapix
subcategory: network-video
sha256: 511217b2b79f42b1b22ed420521bd0940d9600c9287315b5a4e877bc827d8f21
scraped_at: "2026-01-09T15:19:56.824Z"
page_height: 5707
---

# Heartbeat service API

## Description

VAPIX® Heartbeat service API enables devices to send heartbeats to monitor the connection between a device and a master.

The master is typically an Axis door controller connected to another Axis device, for example an I/O module with additional I/O functionality. The master could also be a video management system. The master sends heartbeats to the connected device at regular intervals. If a heartbeat call is not issued successfully within a predefined time, the connection is considered interrupted and the connected device emits a heartbeat lost event. The heartbeat lost event can be used to trigger fallback actions.

### Identification

VAPIX ® Heartbeat service API is supported if:

-   **Property**: `Properties.API.Heartbeat.Heartbeat=yes`
-   **Property**: `Properties.API.Heartbeat.Version=1.0` and later.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Using heartbeats

Use `axhbt:Heartbeat` to send a heartbeat to a device. The device responds with a session identifier.

Heartbeats should be sent at regular intervals, typically within a few seconds. The `Duration` field specifies the heartbeat duration, that is, the time the heartbeat is alive. To keep the heartbeat alive, send a new heartbeat before the time expires.

If a heartbeat expires, the session identifier in the device’s response changes. The connection to the device is considered lost and the heartbeat lost event `tns1:Device/tnsaxis:Monitor/Heartbeat` becomes true.

The heartbeat lost event indicates that the heartbeat has not reached the device. By setting up action rules that listen to the event, the Axis product can be configured to, for example, change I/O port states or send notification messages if a heartbeat is lost. Action rules are described in section [Event and action services](/vapix/network-video/event-and-action-services/).

The following pseudocode shows a typical setup that triggers an action rule `set_wanted_port_states()` if the heartbeat is lost. A new heartbeat is sent every 10 seconds. If the heartbeat is lost, the session identifier changes and the action rule triggers.

info

A changed session identifier indicates that a heartbeat lost event has been emitted. Make sure that action rules and software that use the event are reset.

Pseudocode:

```bash
{  setup\_port\_action\_rules()    loop {      session\_id = axhbt.Heartbeat(10000)      if (session\_id != old\_session\_id)        set\_wanted\_port\_states()      old\_session\_id = session\_id       wait\_until(current\_time + 5 seconds)    }}
```

API calls can be constructed using JSON or using SOAP.

The following example show how to send a heartbeat with duration 10 seconds.

Request using JSON:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/vapix/axhbt" \\  --data '{  "axhbt:Heartbeat":{    "Duration": 10000,  }}'
```

```bash
POST /vapix/axhbtHost: <servername>Content-Type: application/json{  "axhbt:Heartbeat":{    "Duration": 10000,  }}
```

JSON response:

```bash
200 OKContent-Type: application/json{  "SessionId": "14b795e4-507a-44b8-b68c-f98be55bc1dd"}
```

Request using SOAP:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: text/xml" \\  "http://<servername>/vapix/services" \\  --data '<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:SOAP-ENC="http://www.w3.org/2003/05/soap-encoding" xmlns:axgpio="http://www.axis.com/vapix/ws/Heartbeat" xmlns="http://www.axis.com/vapix/ws/Heartbeat">  <SOAP-ENV:Header></SOAP-ENV:Header>  <SOAP-ENV:Body>    <axhbt:Heartbeat>      <axhbt:Duration>10000</axhbt:Duration>    </axhbt:Heartbeat>  </SOAP-ENV:Body></SOAP-ENV:Envelope>'
```

```bash
POST /vapix/servicesHost: <servername>Content-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" xmlns:SOAP-ENC="http://www.w3.org/2003/05/soap-encoding" xmlns:axgpio="http://www.axis.com/vapix/ws/Heartbeat" xmlns="http://www.axis.com/vapix/ws/Heartbeat">  <SOAP-ENV:Header></SOAP-ENV:Header>  <SOAP-ENV:Body>    <axhbt:Heartbeat>      <axhbt:Duration>10000</axhbt:Duration>    </axhbt:Heartbeat>  </SOAP-ENV:Body></SOAP-ENV:Envelope>
```

SOAP response body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><SOAP-ENV:Envelope    xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"    xmlns:SOAP-ENC="http://www.w3.org/2003/05/soap-encoding"    xmlns:axgpio="http://www.axis.com/vapix/ws/Heartbeat"    xmlns="http://www.axis.com/vapix/ws/Heartbeat">    <SOAP-ENV:Header />    <SOAP-ENV:Body>        <axhbt:HeartbeatResponse>            <axhbt:SessionId>14b795e4-507a-44b8-b68c-f98be55bc1dd</axhbt:SessionId>        </axhbt:HeartbeatResponse>    </SOAP-ENV:Body></SOAP-ENV:Envelope>
```

## Heartbeat command

Use the `Heartbeat` command to send a heartbeat. The heartbeat is valid during the time specified by the `Duration` field.

-   **Command**: `axhbt:Heartbeat`
-   **Access class**: `ACTUATE`

Message name: Request

```bash
{    "Duration": "<int>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `Duration` | Integer | Heartbeat duration, that is, the time before a heartbeat lost event is emitted.Unit: milliseconds |

Message name: Response

```bash
{    "SessionId": "<string>"}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SessionId` | String | Session identifier. The session identifier remains the same as long as the heartbeat is kept alive. If the session identifier changes between two successive calls, action rules and software that use the heartbeat lost event might have triggered and might need to be reset. |

## Heartbeat lost event

The heartbeat lost event `tns1:Device/tnsaxis:Monitor/Heartbeat` is a stateful event which becomes true when the heartbeat duration expires.

To retrieve the event declaration, use `aev:GetEventInstances`.

Event declaration:

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:Monitor aev:NiceName="Monitor">        <Heartbeat wstop:topic="true" aev:NiceName="Heartbeat">            <aev:MessageInstance aev:isProperty="true">                <aev:DataInstance>                    <aev:SimpleItemInstance                        aev:NiceName="Heartbeat lost"                        Type="xsd:boolean"                        Name="lost"                        isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </Heartbeat>    </tnsaxis:Monitor></tns1:Device>
```