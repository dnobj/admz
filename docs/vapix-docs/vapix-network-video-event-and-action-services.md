---
title: Event and action services
url: "https://developer.axis.com/vapix/network-video/event-and-action-services/"
category: vapix
subcategory: network-video
sha256: 59f7a7017b376702aa5d3153fe1dd37196c051d5826506112eccb0abb87f9496
scraped_at: "2026-01-09T15:19:40.507Z"
page_height: 80649
---

# Event and action services

This section describes how to use the VAPIX® Event service and action service APIs available in Axis network video products with AXIS OS 5.50 and later. The APIs are based on web services.

The Event and action services are used to configure the Axis product to perform actions when the product detects an occurrence of some kind, for example to start a recording if motion is detected outside office hours or to run a guard tour once every hour.

The **Event service** is used to:

-   List events
-   Configure recurring events (schedules and recurrences)
-   Emit virtual input events

Events can be used in actions rules and in notification subscriptions.

For information about available events, see [Event declarations](#event-declarations).

The **Action service** is used to:

-   List action and recipient templates
-   Create action configurations
-   Create action rules

For information about available action templates, see [Action templates](#action-templates).

For information about available recipient templates, see [Recipient templates](#recipient-templates).

See also the Event and action services sample code and the VAPIX® Entry service sample code.

## Prerequisites
### Identification

Use VAPIX® Entry service API to check if the API is supported.

-   **Namespace**: `http://www.axis.com/vapix/ws/event1`
-   **Namespace**: `http://www.axis.com/vapix/ws/action1`
-   **AXIS OS**: 5.50

Supported events, action templates and recipient templates are product dependent.

### API specification

The API specifications are available as WSDL files at:

-   VAPIX® Event service API: [http://www.axis.com/vapix/ws/event1/EventService.wsdl](http://www.axis.com/vapix/ws/event1/EventService.wsdl)
-   VAPIX® Action service API: [http://www.axis.com/vapix/ws/action1/ActionService.wsdl](http://www.axis.com/vapix/ws/action1/ActionService.wsdl)

### Obsoletes

The parameter-based event handling system in products with AXIS OS prior to 5.40 is deprecated but supported for backward compatibility.

Event and action configurations created using the parameter-based API and the web services-based API are stored in separate configuration domains.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Relationship to parameter based API

VAPIX® Event and action services APIs replace the parameter-based event handling system in products with AXIS OS prior to 5.40. Some changes include:

-   Event servers are replaced by Recipients.
-   Event types (parameter group `Event.E#`) are replaced by Action rules. In contrast to Event types, an Action rule can have multiple conditions (triggers).
-   Triggers are replaced by Start event and conditions.

See also [Terminology](#terminology).

Existing Event types can be converted to Action rules from the product’s webpages.

## Terminology

-   **Action**: An action is a task that can be performed by the Axis product. The action is initiated by an action rule. Examples: record video, send e-mail, activate output port.
-   **Action rule**: An action rule specifies how and when the Axis product should perform an action. Example: record video when motion is detected outside office hours.
-   **Condition**: An additional condition that must be fulfilled to trigger the action rule.
-   **Event**: Event is used as a collective name for stateful and stateless events. Events are emitted when the Axis product detects an occurrence of some kind, for example motion in the camera’s field of view or a signal from an I/O port. Events can be used in action rules (as start event or condition) and in notification subscriptions.
-   **Fixed action**: A fixed action runs during a fixed, predefined time. Depending on the action type, the length of time is defined by one or more action parameters, by the length of the audio clip to be played or similar.
-   **Recipient**: A recipient is a network resource that can receive data, for example video clips or notification messages. Examples: network share, FTP server, email address.
-   **Stateful event**: A stateful event is a property (a state variable) with a number of states. The event is always in one of its states. Example: The Motion Detection event is in state `true` when motion is detected and in state `false` when motion is not detected.
-   **Stateless event**: A stateless event is a momentary occurrence (a pulse). Example: Storage device removed.
-   **Unlimited action**: An unlimited action runs as long as all conditions are fulfilled.
-   **Start event**: A condition that must be fulfilled to trigger the action rule. Called **Trigger** in the product’s webpages.

## Events, actions and action rules

This section contains examples showing how to use the Event and action services. All examples are written in C#; modify as required for applications in other languages.

### Identification using entry service

To check if the Axis product supports the Event and action services APIs, use `GetServices` from VAPIX® Entry service API as outlined below. The Entry service API is available for products with AXIS OS 5.60 and later. For products with AXIS OS 5.50, use the helper functions defined in appendix [Helper functions](#helper-functions).

We start by defining the IP address, user name and password for the Axis product and the namespaces of the event and action services. Then we use `CreateEntryServiceClient` to create an entry service client.

info

The function CreateEntryServiceClient is defined in the VAPIX® Entry service API sample code. For more information about the entry service, see the VAPIX® Entry service API documentation.

```bash
// Define the address, user name and password for the Axis product. <servername> is an IP address or host name.string address="<servername>";string username="<user name>";string password="<password>";// Define the namespaces of the event and action services.string eventTargetNamespace = "http://www.axis.com/vapix/ws/event1";string actionTargetNamespace = "http://www.axis.com/vapix/ws/action1";// Create an Entry Service client.EntryClient myEntryService = CreateEntryServiceClient(address, username, password);
```

Next, we use the entry service client and `GetServices` to get a list of all services in the Axis product. We then search the list to check if the event and action services are included.

If a service is found, use `CreateEventServiceClient` and `CreateActionServiceClient` to create service clients. See [Helper functions](#helper-functions). These functions are not part of the API and are created in the same way as `CreateEntryServiceClient`.

```bash
// Get a list of all services.Service\[\] serviceList = myEntryService.GetServices(false);// Check if event service is supported. If supported, create a service client.for (i = 0; i < serviceList.count; i++){  if (serviceList\[i\].Namespace == eventTargetNamespace)  {    // Get the service address.    string eventXaddr = serviceList\[i\].Xaddr;    // Create an event client.     EventClient myEventService = CreateEventServiceClient(eventXaddr, username, password);  }// Check if action service is supported. If supported, create a service client.  if (serviceList\[i\].Namespace == actionTargetNamespace)  {    // Get the service address.    string actionXaddr = serviceList\[i\].Xaddr;    // Create an action client.     ActionClient myActionService = CreateActionServiceClient(actionXaddr, username, password);  }}
```

### Events

The term **event** is used as a collective name for stateful and stateless events.

-   **Stateful event**: A stateful event is a property (a state variable) with a number of states. The event is always in one of its states. Example: The Motion detection event is in state `true` when motion is detected and in state `false` when motion is not detected.
-   **Stateless event**: A stateless event is a momentary occurrence (a pulse). Example: Storage device removed

Events are emitted when the Axis product detects an occurrence of some kind, for example motion in the camera's field of view or a signal from an I/O port. Events can be used in action rules (as start event or as a condition) and in notification subscriptions.

Events are added and removed dynamically depending on device configuration. For example, when a motion detection window is configured, a motion detection event is added.

To list the currently available events, use `GetEventInstances` as described in section [List events](#list-events). The response is the event declaration topic tree described in section [Event topic tree syntax](#event-topic-tree-syntax). The list of events can be used to construct event filter expressions for notification subscriptions and for action rule configuration.

It is also possible to list events using HTTP as described in section [List events using HTTP](#list-events-using-http).

#### List events

To list events, use `GetEventInstances` as in the example outlined below. The example uses `myEventService` created in section [Identification using entry service](#identification-using-entry-service).

```bash
try{  // List event instances.  TopicSetType response = myEventService.GetEventInstances();  XmlElement\[\] eventInstances = response.Any;}catch (Exception e){  HandleException(e);}
```

#### Event topic tree syntax

The events are listed as a `wstop:TopicSet` tree containing `aev:MessageInstance` elements in each leaf topic. The `aev:MessageInstance` element describes the content of the event.

The topic tree has the following syntax:

```bash
<aev:GetEventInstancesResponse><wstop:TopicSet><TOPIC1 aev:NiceName="topic1\_nicename" wstop:topic="true">  <TOPIC2 aev:NiceName="topic2\_nicename" wstop:topic="true">    <aev:MessageInstance aev:isProperty="true">      <aev:SourceInstance>        <aev:SimpleItemInstance aev:NiceName="key\_nicename" Type="VALUETYPE"         Name="KEYNAME">          <aev:Value aev:NiceName="value1\_nicename">value1</aev:Value>          <aev:Value aev:NiceName="value2\_nicename">value2</aev:Value>          ...        </aev:SimpleItemInstance>        ...      </aev:SourceInstance>      <aev:DataInstance>        <aev:SimpleItemInstance aev:NiceName="NICENAME" Type="VALUETYPE" Name="KEYNAME"        isPropertyState="true">          <aev:Value>VALUE1</aev:Value>          <aev:Value>VALUE2</aev:Value>          ...        </aev:SimpleItemInstance>      </aev:DataInstance>    </aev:MessageInstance>  </TOPIC2></TOPIC1></wstop:TopicSet></aev:GetEventInstancesResponse>
```

A real case would look like this:

```bash
<aev:GetEventInstancesResponse>    <wstop:TopicSet>        <tns1:AudioSource>            <tnsaxis:TriggerLevel aev:NiceName="Audio detection" wstop:topic="true">                <aev:MessageInstance aev:isProperty="true">                    <aev:SourceInstance>                        <aev:SimpleItemInstance aev:NiceName="Channel" Type="xsd:int" Name="channel">                            <aev:Value>1</aev:Value>                        </aev:SimpleItemInstance>                    </aev:SourceInstance>                    <aev:DataInstance>                        <aev:SimpleItemInstance                            aev:NiceName="Above alarm level"                            Type="xsd:boolean"                            Name="triggered"                            isPropertyState="true" />                    </aev:DataInstance>                </aev:MessageInstance>            </tnsaxis:TriggerLevel>        </tns1:AudioSource>    </wstop:TopicSet></aev:GetEventInstancesResponse>
```

The prefix `aev` is a placeholder for the namespace `http://www.axis.com/vapix/ws/event1`.

Each `MessageInstance` element describes one type of event. If the event is stateful, the `isProperty` attribute is `true`. If the event is stateless, the `isProperty` attribute is omitted.

The `MessageInstance` element lists `SourceInstance` and `DataInstance` elements. Depending on the type of event, `SourceInstance` or `DataInstance` can be omitted. An event may have several `DataInstance` elements.

`SourceInstance` contains a `SimpleItem`describing the source of the event, for example an I/O port. `DataInstance` contains a `SimpleItem` describing the data that generates the event.

SimpleItems are described by `SimpleItemInstance` elements. Each `SimpleItemInstance` contains attributes and a list of `Value` child elements. The `Name` attribute is the name of the `SimpleItem`. The `Type` attribute describes the datatype for the `SimpleItem` values. The `NiceName` attribute is optional and contains the Key's nice name.

If the event is stateful, one of the `DataInstance` elements contains a `SimpleItem` of type boolean with the `isPropertyState` attribute set to `true`. This `SimpleItem` describes the current state of the event (for example the state of the I/O port).

For stateless event, the `isPropertyState` attribute is omitted.

The `Value` elements contains the possible values for the `SimpleItem`. The `NiceName` attribute is optional.

#### List events using HTTP

Listing events using HTTP is an alternative to using `GetEventInstances`. The HTTP method gives the same topic tree as `GetEventInstances`.

To request a list of events (the topic tree) using HTTP, send the following SOAP message to the Axis product using the URL `http://<servername>/vapix/services`. The HTTP header must contain the `Content-Type` below.

Example:

-   **Content-Type**: `application/soap+xml; action=http://www.axis.com/vapix/ws/event1/GetEventInstances; Charset=UTF-8`

Body:

```bash
<SOAP-ENV:Envelope    xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"    xmlns:SOAP-ENC="http://www.w3.org/2003/05/soap-encoding"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xmlns:xsd="http://www.w3.org/2001/XMLSchema">    <SOAP-ENV:Body>        <m:GetEventInstances xmlns:m="http://www.axis.com/vapix/ws/event1" />    </SOAP-ENV:Body></SOAP-ENV:Envelope>
```

### Actions

An **action** is a task that can be performed by the Axis product. The action is initiated by an action rule (see [Action rules](#action-rules)). Examples: record video, send e-mail, activate output port.

A **fixed action** runs during a fixed, predefined time. Depending on the action type, the length of time is defined by one or more action parameters, by the length of the audio clip to be played or similar. An **unlimited action** runs as long as all conditions are fulfilled.

#### Action templates

An **action template** defines an action type. The template lists the parameters needed to configure the action. If the action uses a recipient, the supported recipient type is also listed.

Supported operations:

-   `GetActionTemplates` — list the action templates supported by the Axis product

An example of how to get an action template could look like:

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope xmlns:aa="http://www.axis.com/vapix/ws/action1" xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:GetActionTemplates xmlns="http://www.axis.com/vapix/ws/action1" />    </soap:Body></soap:Envelope>
```

An example of how an action implementation could look like:

```bash
NewActionConfiguration newAction = new NewActionConfiguration{  TemplateToken = "com.axis.action.fixed.play.audioclip",  Parameters = new ActionParameters  {    Parameter = new\[\]    {      new ActionParameter { Name = "location", Value = "etc/audioclips/alarm.au" }    }  }};
```

For available action templates, see [Action templates](#action-templates).

#### Action configurations

An **action configuration** specifies an action to be performed. The action configuration is created by specifying an action template and a list of parameters. If the action template refers to a recipient template, the parameters in the recipient template must also be added to the action configuration.

The action configuration ID identifies the action configuration and is used as input when creating an action rule.

Supported operations:

-   `AddActionConfiguration` — create a new action configuration
-   `GetActionConfigurations` — list all stored action configurations
-   `RemoveActionConfiguration` — remove an action configuration

An example of how to get an action configuration could look like:

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope xmlns:aa="http://www.axis.com/vapix/ws/action1" xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:GetActionConfigurations xmlns="http://www.axis.com/vapix/ws/action1" />    </soap:Body></soap:Envelope>
```

#### Create an action configuration

The example in this section shows how to create an action configuration that sets output port 1 to state `high`.

The example uses `myActionService` created in section [Identification using entry service](#identification-using-entry-service).

The action template `com.axis.action.unlimited.io.toggle` defines the unlimited output port action which has two parameters: `port` is I/O port number and `state` is the state to set the port to. For more information about the output port action template, see [Output Port Action](/vapix/network-video/input-and-outputs/#output-port-action).

info

All parameters must be specified; if a parameter should not be used, its value should be set to an empty string.

```bash
try{  // Verify that the camera supports the action.  ActionTemplate\[\] actiontemplates = myActionService.GetActionTemplates();  if (actiontemplates.Any(    template => template.TemplateToken == "com.axis.action.unlimited.io.toggle") == false)  {    // Camera does not support the output port action.    return;  }  // Create output port action  NewActionConfiguration newAction = new NewActionConfiguration  {    TemplateToken = "com.axis.action.unlimited.io.toggle",    Parameters = new ActionParameters    {      Parameter = new\[\]      {        new ActionParameter { Name = "port", Value = "1" }        new ActionParameter { Name = "state", Value = "high" }      }    }  };  // Add the action to the camera.  string actionId = myActionService.AddActionConfiguration(newAction);}catch (Exception e){  HandleException(e);}
```

### Recipients

A **recipient** is a network resource that can receive data, for example video clips or notification messages. Examples: network share, FTP server, email address.

#### Recipient templates

A **recipient template** defines a recipient type. The template lists the parameters used to configure a recipient of the given type.

Supported operations:

-   `GetRecipientTemplates` — list the recipient templates supported by the Axis product

An example of how to get a recipient template could look like:

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope xmlns:aa="http://www.axis.com/vapix/ws/action1" xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:GetRecipientTemplates xmlns="http://www.axis.com/vapix/ws/action1" />    </soap:Body></soap:Envelope>
```

For available recipient templates, see [Recipient templates](#recipient-templates).

#### Recipient configurations

A **recipient configuration** specifies the parameters for a recipient. A recipient configuration is created by specifying a recipient template and a list of parameters. Recipient configurations are optional and are only used to store the parameters on the Axis product. The recipient configurations are not used directly in action configurations.

Supported operations:

-   `AddRecipientConfiguration` — create a new recipient configuration
-   `GetRecipientConfigurations` — list all stored recipient configurations
-   `RemoveRecipientConfiguration` — remove a recipient configuration

An example of how to get a recipient configurations could look like:

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xmlns:xsd="http://www.w3.org/2001/XMLSchema"    xmlns:aa="http://www.axis.com/vapix/ws/action1"    xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"    xmlns:tns1="http://www.onvif.org/ver10/topics"    xmlns:tnsaxis="http://www.axis.com/2009/event/topics"    xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:GetRecipientConfigurations xmlns="http://www.axis.com/vapix/ws/action1" />    </soap:Body></soap:Envelope>
```

#### Using recipients in an action configuration

The example in this section shows how to use a recipient in an action configuration. The action and the recipient are both defined by the action template. For example, the template `com.axis.action.fixed.notification.http` defines the action Send Notification and the recipient HTTP.

The action parameters and the recipient parameters are provided as `ActionParameters` in the `NewActionConfiguration` operation. In this example, parameters `message` and `parameters` belong to the Send Notification action while the remaining parameters belong to the HTTP recipient.

For more information about the action and the recipient templates, see [Send notification action](#send-notification-action) and [HTTP recipient](#http-recipient).

info

All parameters must be specified; if a parameter should not be used, its value should be set to an empty string.

The example uses `myActionService` created in section [Identification using entry service](#identification-using-entry-service).

```bash
try{  // Create send notification action  NewActionConfiguration newAction = new NewActionConfiguration  {    TemplateToken = "com.axis.action.fixed.notification.http",    Parameters = new ActionParameters    {      Parameter = new\[\]      {        new ActionParameter{ Name = "message", Value = "The message to send" },        new ActionParameter{ Name = "parameters", Value = "" },        new ActionParameter{ Name = "upload\_url", Value = "http://ip\_address/cgi-bin/notify.cgi" },        new ActionParameter{ Name = "login", Value = "myusername" },        new ActionParameter{ Name = "password", Value = "mypassword" },        new ActionParameter{ Name = "proxy\_host", Value = "" },        new ActionParameter{ Name = "proxy\_port", Value = "" },        new ActionParameter{ Name = "proxy\_login", Value = "" },        new ActionParameter{ Name = "proxy\_password", Value = "" },        new ActionParameter{ Name = "qos", Value = "0" }      }    }  };  // Add action to the camera.  string actionId = myActionService.AddActionConfiguration(newAction);}catch (Exception e){  HandleException(e);}
```

### Action rules

An **action rule** specifies how and when the Axis product performs an action. Example: record video when motion is detected outside office hours.

An action rule consists of:

-   a start event
-   one or more conditions
-   a primary action

info

Fallback actions are not supported.

The primary action will be executed when the start event occurs and all specified conditions are fulfilled. The start event can be omitted. Conditions can also be omitted, but either a start event or at least one condition must be specified. The action will be stopped when any of the conditions is no longer fulfilled.

info

Fixed actions can be used with any combination of start events and conditions. Unlimited actions require at least one condition to prevent the action from running indefinitely; the start event may however be omitted.

The start event and the conditions are specified using `TopicExpression` and `MessageContent` filters. See [Event topic tree syntax](#event-topic-tree-syntax) . All mandated dialects specified in ONVIF™ Core Specification 1.02 are supported.

The start event can be any valid filter expression, as defined by ONVIF™ Core Specification 1.02.

Each condition should be specified by a separate filter expression which must describe one stateful event. Stateless events cannot be used as conditions. If the provided filter does not match any stateful events or matches multiple stateful events, the `AddActionRule` request will fail with `InvalidconditionFilterFault` reply.

The primary action is specified using an action configuration as described in [Setting up an action rule](#setting-up-an-action-rule). Fallback actions are not supported.

Supported operations:

-   `AddActionRule` — create a new action rule
-   `GetActionRules` — list all stored action rules
-   `RemoveActionRule` — remove an action rule

#### Setting up an action rule

This example shows how to set up an action rule that plays an audio clip (alarm.au) if tampering is detected while Input 1 is active.

The example uses `myActionService` created in section [Identification using entry service](#identification-using-entry-service).

| Step | Type | Reference |
| --- | --- | --- |
| Start event: Tampering | Event: `tns1:VideoSource/tnsaxis:Tampering` | See [Camera tampering event](#camera-tampering-event). |
| Condition: Input 1 active | Event: `tns1:Device/tnsaxis:I0/tnsaxis:Port` | See [Digital Input Event](/vapix/network-video/input-and-outputs/#digital-input-event). |
| Primary action: Play audio clip | Action template: `com.axis.action.fixed.play.audioclip` | See [Play audio clip action](#play-audio-clip-action). |

The action rule is created in two steps:

1.  The action rule is created in two steps:
    
    The action configuration is created using `AddActionConfiguration`.
    
2.  The action rule is created using `AddActionRule`. The Action Configuration ID `actionId` returned by `AddActionConfiguration` specifies the primary action.
    

```bash
try{  // Verify that the camera supports the action.  ActionTemplate\[\] actiontemplates = myActionService.GetActionTemplates();  if (actiontemplates.Any(    template => template.TemplateToken == "com.axis.action.fixed.play.audioclip") == false)  {    // Camera does not support the play audio clip action.    return;  }  // Create play audio clip action  NewActionConfiguration newAction = new NewActionConfiguration  {    TemplateToken = "com.axis.action.fixed.play.audioclip",    Parameters = new ActionParameters    {      Parameter = new\[\]      {        new ActionParameter { Name = "location", Value = "etc/audioclips/alarm.au" }      }    }  };  // Add the action to the camera.  string actionId = myActionService.AddActionConfiguration(newAction);  // Create action rule  NewActionRule newActionRule = new NewActionRule  {    Name = "Play audio clip on tampering",    StartEvent = FormatTopicExpression("tns1:VideoSource/tnsaxis:Tampering"),    Conditions = new\[\]    {      FormatTopicExpression(        "tns1:Device/tnsaxis:I0/tnsaxis:Port",        "boolean(//SimpleItem\[@Name=\\"port\\" and @Value=\\"1\\"\]) and "        + "boolean(//SimpleItem\[@Name=\\"state\\" and @Value=\\"1\\"\])")      },    PrimaryAction = actionId,    Enabled = true  };  // Add the action rule to the camera.  string actionRuleId = myActionService.AddActionRule(newActionRule);}catch (Exception e){  HandleException(e);}
```

### Scheduled events

A **scheduled event** is active during specific time periods defined by an iCalendar schedule. Scheduled events can be used in action rules and in notification subscriptions.

There are two types of schedules:

-   An **interval schedule** emits a stateful event at the scheduled start time. The event will remain active until the scheduled end time. The schedule can be repeated according to a recurring rule. Example: A schedule named "Office Hours" which is active from 9 a.m. to 5 p.m. Monday through Friday.
-   A **pulse schedule** emits a stateless event at the scheduled start time and can be repeated according to a recurring rule. Pulse schedules are typically used for recurrences, for example to run an action once every hour.

Supported operations:

-   `AddScheduledEvent` — create a scheduled event
-   `GetScheduledEvents` — list scheduled events
-   `RemoveScheduledEvent` — remove a scheduled event

#### Schedules

A schedule is specified by providing a start time, an end time and a recurring rule. The schedule format is designated by a wrapper element whose name defines the syntax and semantics of the schedule description format. The supported schedule description format is a subset of the iCalendar format specified in RFC 5545.

```bash
<aev:ICalendar>  DTSTART:<start date>  DTEND:<end date>  RRULE:<recurring rule></aev:ICalendar>
```

`<start date>` is the start date and time of the first occurrence of the event. Both date and time are required and should be specified according to ISO 8601. The time is the product's local time; time zone information is not supported.

For interval schedules, `<end date>` is the end date and time of the first occurrence of the event. Use the same format as for `<start date>`. For pulse schedules, `<end date>` should be omitted.

`<recurring rule>` specifies the repetitions of the event. The following subset of the iCalendar specification is supported:

```bash
RRULE:FREQ=YEARLY\[;BYMONTH=<1-12>,...\]\[;INTERVAL=<1-\*>\]RRULE:FREQ=MONTHLY\[;BYDAY=\[\[-\]<0-5>\]<MO | TU | WE | TH | FR | SA | SU>,...\]\[;INTERVAL=<1-\*>\]RRULE:FREQ=WEEKLY\[;BYDAY=<MO | TU | WE | TH | FR | SA | SU>,...\]\[;INTERVAL=<1-\*>\]RRULE:FREQ=DAILY\[;INTERVAL=<1-\*>\]RRULE:FREQ=HOURLY\[;INTERVAL=<1-\*>\]RRULE:FREQ=MINUTELY\[;INTERVAL=<1-\*>\]RRULE:FREQ=SECONDLY\[;INTERVAL=<1-\*>\]
```

#### Create a scheduled event

This examples shows how to create a scheduled event with an interval schedule that runs from 6 am to 9 am, Monday through Friday.

The example uses `myEventService` created in section [Identification using entry service](#identification-using-entry-service).

```bash
try{  // Create the scheduled event.  NewScheduledEvent scheduledEvent = new NewScheduledEvent  {    Name = "My schedule",    Schedule = new Schedule    {      ICalendar = new ICalendar      {        Value =          "DTSTART:20111212T06:00 " +          "DTEND:20111212T09:00 " +          "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"      }    }  };  // Add the scheduled event.  string scheduledEventId = myEventService.AddScheduledEvent(scheduledEvent);}catch (Exception e){  HandleException(e);}
```

### Virtual input events

A **virtual input event** is emitted when the state of a virtual input port is changed. Virtual input ports can be used in the same way as (physical) input ports. A virtual input port is in one of the states: `true` and `false`.

Use `ChangeVirtualInputState` to emit a virtual input event. An emitted virtual input event is stateful.

See also [Virtual input API](/vapix/network-video/input-and-outputs/#virtual-input-api).

## Event declarations

Call events:

-   `Call/State`. See [Call state event](/vapix/intercom/call-service-api/#call-state-event).
-   `Call/StateChange`. See [Call state change event](/vapix/intercom/call-service-api/#call-state-change-event).
-   `Call/DTMF`. See [DTMF events](/vapix/intercom/call-service-api/#dtmf-events).

PTZ events:

-   `PTZController/PTZPresets/Channel_X`. See [PTZ preset reached event](/vapix/network-video/pantiltzoom-api/#ptz-preset-reached-event).
-   `PTZController/Move/Channel_X`. See [PTZ moving event](/vapix/network-video/pantiltzoom-api/#ptz-moving-event).
-   `PTZController/PTZReady`. See [PTZ ready event](/vapix/network-video/pantiltzoom-api/#ptz-ready-event).
-   `PTZController/ControlQueue`. See [PTZ control queue event](/vapix/network-video/pantiltzoom-api/#ptz-control-queue-event).
-   `PTZController/Autotracking`. See [Autotracking event](/vapix/network-video/pantiltzoom-api/#autotracking-event).
-   `PTZController/PTZError`. See [PTZ error event](/vapix/network-video/pantiltzoom-api/#ptz-error-event).

Edge storage events:

-   `Storage/Recording`. See [Event recording ongoing](/vapix/network-video/edge-storage-api/#event-recording-ongoing)
-   `Storage/Disruption`. See [Event storage disruption detection](/vapix/network-video/edge-storage-api/#event-storage-disruption-detection)

I/O events:

-   `Device/IO/Port`. See [Digital Input Event](/vapix/network-video/input-and-outputs/#digital-input-event).
-   `Device/IO/SupervisedPort`. See [Supervised port event](/vapix/network-video/input-and-outputs/#supervised-port-event).
-   `Device/IO/VirtualInput`. See [Virtual Input Event](/vapix/network-video/input-and-outputs/#virtual-input-event).
-   `Device/IO/VirtualPort`. See [Manual Trigger Event](/vapix/network-video/input-and-outputs/#manual-trigger-event).

Scheduled and recurring events:

-   `UserAlarm/Recurring/Interval`. See [Scheduled event](#scheduled-event).
-   `UserAlarm/Recurring/Pulse`. See [Recurring event](#recurring-event).

Device status events:

-   `Device/Status/SystemReady`. See [System ready event](#system-ready-event).
-   `Device/Status/Temperature/Above`. See [Temperature above event](#temperature-above-event).
-   `Device/Status/Temperature/Below`. See [Temperature below event](#temperature-below-event).
-   `Device/Status/Temperature/Inside`. See [Temperature inside event](#temperature-inside-event).
-   `Device/Status/Temperature/Above_or_below`. See [Temperature outside event](#temperature-outside-event).

Device events:

-   `Device/Casing/Open`. See [Open casing detection event](#open-casing-detection-event).
-   `Device/HardwareFailure/FanFailure`. See [Fan failure event](#fan-failure-event).
-   `Device/HardwareFailure/PowerSupplyFailure`. See [Power supply failure event](#power-supply-failure-event).
-   `Device/HardwareFailure/TemperatureCritical`. See [Temperature critical event](#temperature-critical-event).
-   `Device/Network/Lost`. See [Network lost event](#network-lost-event).
-   `Device/Sensor/PIR`. See [PIR sensor event](#pir-sensor-event).
-   `Device/Tampering/ShockDetected`. See [Shock detection event](/vapix/network-video/shock-detection-api/#shock-detection-event).

Heartbeat events:

-   `Device/Monitor/Heartbeat`. See [Heartbeat lost event](/vapix/network-video/heartbeat-service-api/#heartbeat-lost-event).

Connector events:

-   `Connector/Source`. See [Audio connector event](#audio-connector-event).

Video encoder events:

-   `VideoEncoder/Connections`. See [Video connected event](#video-connected-event).

Video analytics events:

-   `VideoAnalytics/MotionDetection`. See [Motion detection event](#motion-detection-event).

Video source events:

-   `VideoSource/DayNightVision`. See [Day/night vision mode event](#daynight-vision-mode-event).
-   `VideoSource/LiveStreamAccessed`. See [Live stream accessed event](#live-stream-accessed-event).
-   `VideoSource/Tampering`. See [Camera tampering event](#camera-tampering-event).
-   `VideoSource/TemperatureDetection`. See [Temperature detection event](/vapix/network-video/thermal-imaging/#temperature-detection-event).

Audio source events:

-   `AudioSource/TriggerLevel`. See [Audio detection event](/vapix/audio-systems/audio-api/#audio-detection-event).

Media clip events:

-   `MediaClip/Playing`. See [Playing event](#playing-event).
-   `MediaClip/CurrentlyPlaying`. See [CurrentlyPlaying event](#currentlyplaying-event).

System message events:

-   `Device/SystemMessage/ActionFailed`. See [Action failed event](#action-failed-event).

ACAP events:

-   `CameraApplicationPlatform/`. See [Application event - C applications](#application-event---c-applications)
-   `RuleEngine/`. See [Application event - Lua applications](#application-event---lua-applications).

### UserAlarm/Recurring Events
#### Scheduled event

A scheduled event triggers actions during specific time periods.

For information about supported schedule formats, see [Schedules](#schedules).

**Topic**

-   **Name**: `tns1:UserAlarm/tnsaxis:Recurring/tnsaxis:Interval`
-   **Type**: Stateful
-   **Nice name**: `Scheduled event`

**Source instance**

-   **Nice name**: `Schedule`
-   **Type**: string
-   **Name**: `id`

| Value | Nice name |
| --- | --- |
| `com.axis.schedules.weekdays` | `Weekdays` |
| `com.axis.schedules.office_hours` | `Office Hours` |
| `com.axis.schedules.after_hours` | `After Hours` |
| `com.axis.schedules.weekends` | `Weekends` |
| `com.axis.schedules.genid.id-0` | `[User-defined name]` |

**Data instance**

-   **Nice name**: Active
-   **Type**: boolean
-   **Name**: `active`
-   **isPropertyState**: `true`

#### Recurring event

A recurring event triggers actions repeatedly, for example every 5 minutes.

For information about supported schedule formats, see [Schedules](#schedules).

**Topic**

-   **Name**: `tns1:UserAlarm/tnsaxis:Recurring/tnsaxis:Pulse`
-   **Type**: Stateless
-   **Nice name**: `Recurring pulse`

**Source instance**

-   **Nice name**: `Schedule`
-   **Type**: string
-   **Name**: `id`

| Value | Nice name |
| --- | --- |
| `com.axis.schedules.genid.id-0` | `[User-defined name]` |

**Data instance**

Not applicable.

### Device status events
#### System ready event

The system ready event is `true` when the product has been started and all services are running. The event can for example be used to detect that a product has been restarted.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Status/tnsaxis:SystemReady`
-   **Type**: Stateful
-   **Nice name**: `System ready`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: `Ready`
-   **Type**: boolean
-   **Name**: `ready`
-   **isPropertyState**: `true`

#### Temperature above event

The temperature above event is `true` when the temperature is above the operating range of the product.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Status/tnsaxis:Temperature/tnsaxis:Above`
-   **Type**: Stateful
-   **Nice name**: `Above operating temperature`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Above range
-   **Type**: boolean
-   **Name**: `sensor_level`
-   **isPropertyState**: `true`

#### Temperature below event

The temperature below event is `true` when the temperature is below the operating range of the product.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Status/tnsaxis:Temperature/tnsaxis:Below`
-   **Type**: Stateful
-   **Nice name**: `Below operating temperature`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Below range
-   **Type**: boolean
-   **Name**: `sensor_level`
-   **isPropertyState**: `true`

#### Temperature inside event

The temperature inside event is `true` when the temperature is inside the operating range of the product.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Status/tnsaxis:Temperature/tnsaxis:Inside`
-   **Type**: Stateful
-   **Nice name**: `Within operating temperature`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Within range
-   **Type**: boolean
-   **Name**: `sensor_level`
-   **isPropertyState**: `true`

#### Temperature outside event

The Temperature outside event is `true` when the temperature is outside the operating range of the product.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Status/tnsaxis:Temperature/tnsaxis:Above_or_below`
-   **Type**: Stateful
-   **Nice name**: `Above or below operating temperature`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Above or below range
-   **Type**: boolean
-   **Name**: `sensor_level`
-   **isPropertyState**: `true`

### Hardware failure events
#### Fan failure event

The fan failure event is `true` if the product’s fan does not work. The fan can be built into the product or be a rack fan connected to a video encoder blade. For products with multiple fans, there is one event for each fan.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:HardwareFailure/tnsaxis:FanFailure`
-   **Type**: Stateful
-   **Nice name**: `Fan failure`

**Source instance**

-   **Nice name**: `Fan`
-   **Type**: integer
-   **Name**: `fan`

| Value | Nice name |
| --- | --- |
| `0` | — |
| `1` | — |
| `...` | — |
| `[number of fans]` | — |

**Data instance**

-   **Nice name**: Fan failure
-   **Type**: boolean
-   **Name**: `fan_failure`
-   **isPropertyState**: `true`

#### Power supply failure event

The power supply failure event is `true` if the power supply does not work.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:HardwareFailure/tnsaxis:PowerSupplyFailure`
-   **Type**: Stateful
-   **Nice name**: `Power supply failure`

**Source instance**

-   **Nice name**: `Power`
-   **Type**: integer
-   **Name**: `power`

| Value | Nice name |
| --- | --- |
| `0` | — |
| `1` | — |
| `...` | — |
| `[number of power supplies]` | — |

**Data instance**

-   **Nice name**: Power critical
-   **Type**: boolean
-   **Name**: `power_critical`
-   **isPropertyState**: `true`

#### Temperature critical event

The temperature critical event is `true` if the temperature measured by the temperature sensors exceeds the operating range of the product.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:HardwareFailure/tnsaxis:TemperatureCritical`
-   **Type**: Stateful
-   **Nice name**: `Temperature critical`

**Source instance**

-   **Nice name**: `—`
-   **Type**: integer
-   **Name**: `temperature`

| Value | Nice name |
| --- | --- |
| `0` | — |
| `1` | — |
| `...` | — |
| `[number of temperature sensors]` | — |

**Data instance**

-   **Nice name**: Temperature is critical
-   **Type**: boolean
-   **Name**: `temperature_critical`
-   **isPropertyState**: `true`

### Network events
#### Network lost event

The network lost event is `true` if network connection is lost.

The event can for example be used to start recording to the SD card if network is lost.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Network/tnsaxis:Lost`
-   **Type**: Stateful
-   **Nice name**: `Network lost`

**Source instance**

-   **Nice name**: `Interface`
-   **Type**: string
-   **Name**: `interface`

| Value | Nice name |
| --- | --- |
| `eth0` | — |
| `eth1` | — |
| `...` | — |
| `ethn [n = number of network interfaces + 1]` | — |

**Data instance**

-   **Nice name**: Lost
-   **Type**: boolean
-   **Name**: `lost`
-   **isPropertyState**: `true`

#### IP address added

The network IP address event is triggered when the device is assigned a new IP address from, for example, the DHCP server.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Network/AddressAdded`
-   **Type**: Stateless
-   **Nice name**: `AddressAdded`

**Source instance**

-   **Nice name**: `Interface`
-   **Type**: string
-   **Name**: `interface`

| Value | Nice name |
| --- | --- |
| `eth0` | — |
| `eth1` | — |
| `...` | — |

**Data instance**

-   **Nice name**: Origin
-   **Type**: string
-   **Name**: `origin`

| Parameter | Description |
| --- | --- |
| `Link local` | Used for linklocal addresses. |
| `DHCP` | Used for DHCP assigned addresses. |
| `RA` | Router advertisements (only for IPv6 addresses). |
| `Static` | Configured static addresses. |

-   **Nice name**: Address
-   **Type**: string
-   **Name**: `address`

Please note that the `address` can be either an `IPv4` or `IPv6` address.

#### IP address removed

The IP address removed event is triggered when an address is removed from the device.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Network/AddressRemoved`
-   **Type**: Stateless
-   **Nice name**: `AddressRemoved`

**Source instance**

-   **Nice name**: `Interface`
-   **Type**: string
-   **Name**: `interface`

| Value | Nice name |
| --- | --- |
| `eth0` | — |
| `eth1` | — |
| `...` | — |

**Data instance**

-   **Nice name**: Origin
-   **Type**: string
-   **Name**: `origin`

| Parameter | Description |
| --- | --- |
| `Link local` | Used for linklocal addresses. |
| `DHCP` | Used for DHCP assigned addresses. |
| `RA` | Router advertisements (only for IPv6 addresses). |
| `Static` | Configured static addresses. |

-   **Nice name**: Address
-   **Type**: string
-   **Name**: `address`

Please note that the `address` can be either an `IPv4` or `IPv6` address.

### Device sensor events
#### PIR sensor event

The PIR sensor event is `true` when the PIR sensor detects motion.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Sensor/tnsaxis:PIR`
-   **Type**: Stateful
-   **Nice name**: `PIR sensor`

**Source instance**

-   **Nice name**: `Sensor`
-   **Type**: integer
-   **Name**: `sensor`

| Value | Nice name |
| --- | --- |
| `0` | — |
| `1` | — |
| `...` | — |
| `n = number of PIR sensors - 1` | — |

**Data instance**

-   **Nice name**: Active
-   **Type**: boolean
-   **Name**: `state`
-   **isPropertyState**: `true`

### Device casing events
#### Open casing detection event

The open casing detection event is `true` when the casing of a connected external device, such as a junction box or cabinet, is removed or opened. This can for example be used to send notifications of maintenance or unauthorized tampering.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:Casing/tnsaxis:Open`
-   **Type**: Stateful
-   **Nice name**: `Casing Open`

**Source instance**

Not applicable.

| Value | Nice name |
| --- | --- |
| `JunctionBox` | Junction box |

**Data instance**

-   **Nice name**: Open
-   **Type**: boolean
-   **Name**: `Open`
-   **isPropertyState**: `true`

### Connector events
#### Audio connector event

The audio connector event is `true` if equipment is connected to the audio connector.

**Topic**

-   **Name**: `tns1:Connector/tnsaxis:Source`
-   **Type**: Stateful
-   **Nice name**: `Audio connector`

**Source instance**

-   **Nice name**: `Connector`
-   **Type**: integer
-   **Name**: `connector`

| Value | Nice name |
| --- | --- |
| `0` | — |
| `1` | — |
| `...` | — |
| `[number of connectors]` | — |

**Data instance**

-   **Nice name**: Connected
-   **Type**: boolean
-   **Name**: `connected`
-   **isPropertyState**: `true`

### Video encoder events
#### Video connected event

The video connected event is available in video encoders. The event is `true` when the video encoder receives a video signal from the analog camera. There is one event for each video channel.

**Topic**

-   **Name**: `tns1:VideoEncoder/tnsaxis:Connections`
-   **Type**: Stateful
-   **Nice name**: `Video connected`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

| Value | Nice name |
| --- | --- |
| `1` | — |
| `2` | — |
| `...` | — |
| `[number of video channels]` | — |

**Data instance**

-   **Nice name**: Connected
-   **Type**: boolean
-   **Name**: `connected`
-   **isPropertyState**: `true`

### Video analytics events
#### Motion detection event

info

Deprecated in AXIS OS 5.80 and later. The parameter-based motion detection is deprecated and replaced by the AXIS Video motion detection 3 API in the Applications folder.

The Motion detection event is `true` when motion is detected in a motion detection window.

**Topic**

-   **Name**: `tns1:VideoAnalytics/tnsaxis:MotionDetection`
-   **Type**: Stateful
-   **Nice name**: `Motion detection`

**Source instance**

-   **Nice name**: `Window`
-   **Type**: integer
-   **Name**: `window`

| Value | Nice name |
| --- | --- |
| `0` | User-defined name (default: `[0] DefaultWindow`) |
| `1` | User-defined name (default: `[1] DefaultWindow`) |
| `...` | `...` |
| `n = maximum number of windows + 1` | User-defined name (default: `[n] DefaultWindow`) |

**Data instance**

-   **Nice name**: motion detected
-   **Type**: boolean
-   **Name**: `motion`
-   **isPropertyState**: `true`

### Video source events
#### Day/night vision mode event

The Day/night vision mode event is `true` when the product is in day mode (IR cut filter is on).

This event can for example be used to control an external IR light connected to the product’s digital output port.

**Topic**

-   **Name**: `tns1:VideoSource/tnsaxis:DayNightVision`
-   **Type**: Stateful
-   **Nice name**: `Day night vision`

**Source instance**

-   **Nice name**: `Video source configuration token`
-   **Type**: integer
-   **Name**: `VideoSourceConfigurationToken`

| Value | Nice name |
| --- | --- |
| `1` | — |
| `2` | — |
| `...` | — |
| `n = number of video channels` | — |

**Data instance**

-   **Nice name**: day
-   **Type**: boolean
-   **Name**: `day`
-   **isPropertyState**: `true`

#### Live stream accessed event

The live stream accessed event is `true` when the Axis product sends a live media stream (video, audio or metadata) to a client.

**Topic**

-   **Name**: `tns1:VideoSource/tnsaxis:LiveStreamAccessed`
-   **Type**: Stateful
-   **Nice name**: `Live stream accessed`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Accessed
-   **Type**: boolean
-   **Name**: `accessed`
-   **isPropertyState**: `true`

#### Camera tampering event

The camera tampering event is emitted when the camera is redirected, covered or de-focused.

**Topic**

-   **Name**: `tns1:VideoSource/tnsaxis:Tampering`
-   **Type**: Stateless
-   **Nice name**: `Camera tampering`

**Source instance**

-   **Nice name**: `Channel`
-   **Type**: integer
-   **Name**: `channel`

**Data instance**

-   **Nice name**: Tampering
-   **Type**: integer
-   **Name**: `tampering`

| Value | Nice name |
| --- | --- |
| `1` | — |

### Media clip events
#### Playing event

This media clip event is true whenever a media clip is played. The state is activated by HTTP API using `/axis-cgi/mediaclip.cgi` with action play, `/axis-cgi/playclip.cgi` or via action rules. It will be deactivated when either the media clip is finished or by using the HTTP API method `/axis-cgi/record/stop.cgi`.

-   **Topic**: `tnsaxis:MediaClip/tnsaxis:Playing`
-   **Type**: Stateful
-   **Nice name**: Playing state

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| _Source fields_ |  |  |  |  |
| `AudioOutput` | Integer | AudioOutput | **Note**: This parameter has been deprecated as of AXIS OS 11.7 and will no longer receive any updates. Audio output if state is relevant. 0 if undefined. | `0... (if 1+ index as in Properties.Audio.Source.A[AudioOuput - 1].Output = "yes" #)` |
| `audiodeviceid` | Integer | AudioDeviceId | Parameter that determines what audio device that should play a media clip. Used as an alternative to audiooutput and they can not be used together. Needs to be paired with `audiooutputid` `(audiodeviceid=0&audiooutputid=0)`. | `0...` |
| `audiooutputid` | Integer | AudioOutputId | Parameter that determines which output on an audio device that should play a media clip. Required when `audiodeviceid` is specified. | `0...` |
| _Data fields_ |  |  |  |  |
| `Playing (STATE)` | Boolean | Playing status | True when active. | True/False |

#### CurrentlyPlaying event

This media clip event is will be triggered whenever the `Playing` state is true and a new media clip is played. Using the repeat option will trigger this event multiple times.

-   **Topic**: `tnsaxis:MediaClip/tnsaxis:CurrentlyPlaying`
-   **Type**: Stateless
-   **Nice name**: Currently playing media clip

| Field name | Type | Nice name | Description | Values |
| --- | --- | --- | --- | --- |
| _Source fields_ |  |  |  |  |
| `AudioOutput` | Integer | AudioOutput | **Note**: This parameter has been deprecated as of AXIS OS 11.7 and will no longer receive any updates. Audio output if state is relevant. 0 if undefined. | `0... (if 1+ index as in Properties.Audio.Source.A[AudioOuput - 1].Output = "yes" #)` |
| `audiodeviceid` | Integer | AudioDeviceId | Parameter that determines what audio device that should play a media clip. Used as an alternative to audiooutput and they can not be used together. Needs to be paired with `audiooutputid` `(audiodeviceid=0&audiooutputid=0)`. | `0...` |
| `audiooutputid` | Integer | AudioOutputId | Parameter that determines which output on an audio device that should play a media clip. Required when `audiodeviceid` is specified. | `0...` |
| _Data fields_ |  |  |  |  |
| `FileName` | String | File Name | File name of played clip. | String containing the name. |

### System message events
#### Action failed event

The action failed event is emitted if an action cannot be started. The event is emitted for both primary actions and fallback actions.

info

Fallback actions are not supported.

**Topic**

-   **Name**: `tns1:Device/tnsaxis:SystemMessage/tnsaxis:ActionFailed`
-   **Type**: Stateless
-   **Nice name**: `Action failed`

**Source instance**

Not applicable.

**Data instance**

-   **Nice name**: Description
-   **Type**: string
-   **Name**: `description`

**Value:** String that describes the error.

### ACAP events
#### Application event - C applications

Events from the ACAP are defined by its application. For applications written in C, events are defined using the library `libs/acapevent`.

**Topic**

-   **Name**: `tns1:CameraApplicationPlatform/tnsaxis:`\[ApplicationName\]
-   **Type**: Application dependent
-   **Nice name**: Defined by the application

**Source instance**

-   **Nice name**: —
-   **Type**: string
-   **Name**: `app`

| Value | Nice name |
| --- | --- |
| \[ApplicationName\] |  |

**Data instance**

-   **Nice name**: —
-   **Type**: string
-   **Name**: `event`
-   **isPropertyState**: `true`. Omitted if the event is stateless.

| Value | Nice name |
| --- | --- |
| \[String with the name of the event.\] |  |

#### Application event - Lua applications

Events from the ACAP are defined by its application. For applications written in Lua, events are defined from the application package’s xml configuration file.

**Topic**

-   **Name**: `tns1:RuleEngine/tnsaxis:`\[ApplicationName\]`/tnsaxis:`\[EventName\]
-   **Type**: Application dependent
-   **Nice name**: Defined by the application

**Source instance**

-   **Nice name**: Defined from application configuration
-   **Type**: boolean or string (defined from application configuration)
-   **Name**: Defined from application configuration

| Value | Nice name |
| --- | --- |
| Defined from application configuration |  |

**Data instance**

-   **Nice name**: Defined from application configuration
-   **Type**: boolean or string (defined from application configuration)
-   **Name**: Defined from application configuration
-   **isPropertyState**: `true`. Omitted if the event is stateless.

## Action templates

This section describes available action templates. Each template lists the parameters needed to configure the action. All parameters must be specified; if a parameter should not be used, its value should be set to an empty string.

info

Supported templates are product and AXIS OS dependent. Use GetActionTemplates to list the action templates supported by the Axis product.

-   [Activate light action](#activate-light-action)
-   [Autotracking action](/vapix/network-video/pantiltzoom-api/#autotracking-action)
-   [Day/night mode action](#daynight-mode-action)
-   [Go to PTZ preset action](/vapix/network-video/pantiltzoom-api/#go-to-ptz-preset-action)
-   [Guard tour action](/vapix/network-video/guard-tour-api/#guard-tour-action)
-   [LED control](#led-control)
-   [Output Port Action](/vapix/network-video/input-and-outputs/#output-port-action)
-   [Overlay text action](#overlay-text-action)
-   [Play audio clip action](#play-audio-clip-action)
-   [Recorded tour action](/vapix/network-video/guard-tour-api/#recorded-tour-action)
-   [Record video action template](/vapix/network-video/edge-storage-api/#record-video-action-template)
-   [Send images action](#send-images-action)
-   [Send an MQTT message](#send-an-mqtt-message)
-   [Send notification action](#send-notification-action)
-   [Send video clip action](#send-video-clip-action)

### Activate light action

Use the activate light action to turn on the product’s built-in light.

This action can be run as:

-   **fixed action** — keep the light lit for a predefined time (defined by parameter `duration`).
    
-   **unlimited action** — keep the light lit as long as all event conditions are fulfilled.
    
-   Action ID
    
    `com.axis.action.fixed.light`
    
-   Action ID
    
    `com.axis.action.unlimited.light`
    

| Parameter | Valid values | Description |
| --- | --- | --- |
| `source` | Unsigned integer | The Light ID. |
| `level` _Product-dependent_ | `0 ... 100` | The light intensity. |
| `fade_in` _Product-dependent_ | `0` `1` | `0` = Set light directly to the set `level` `1` = Turn on the light gradually until the set `level` is reached. |
| `fade_out` _Product-dependent_ | `0` `1` | `0` = Turn off the light abruptly `1` = Turn off the light gradually |
| `frequency` _Product-dependent_ | `0 ... 100` | The strobe frequency in Hz. Set to `0` to disable. |
| `duration` | Unsigned integer | Fixed actions: Number of seconds to keep the light lit. |

### Day/night mode action

Use the Day/night mode action to enable and disable the IR cut filter. The action is unlimited and the IR cut filter remains in set state as long as all conditions are fulfilled. When the conditions are no longer fulfilled, the IR cut filter returns to the opposite state.

-   **Action ID**: `com.axis.action.unlimited.ircutfilter`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `active_state` | `yes` `no` `auto` _Product dependent. Not supported by video encoders and mechanical PTZ cameras._ | Active state. `yes` = The IR cut filter is enabled. `no` = The IR cut filter is disabled. `auto` = The IR cut filter is enabled and disabled automatically depending on the lighting conditions. |
| `inactive_state` | `yes` `no` `auto` _Product dependent. Not supported by video encoders and mechanical PTZ cameras._ | Inactive state. `yes` = The IR cut filter is enabled. `no` = The IR cut filter is disabled. `auto` = The IR cut filter is enabled and disabled automatically depending on the lighting conditions. |

info

For fixed cameras, the IR cut filter is controlled by the ImageSource.I0.DayNight.IrCutFilter parameter. For mechanical PTZ cameras and for video encoders, the IR cut filter is controlled by the PTZ.Various.V1.IrCutFilter parameter.

### LED control

Use LED control action to flash the product’s LED indicators.

This action can be run as:

-   This action can be run as:
    
    **fixed action** — flash the LED during the time defined by parameter `duration`
    
-   **unlimited action** — flash the LED as long as all event conditions are fulfilled
    
-   Action ID
    
    `com.axis.action.fixed.ledcontrol`
    
-   Action ID
    
    `com.axis.action.unlimited.ledcontrol`
    

| Parameter | Valid values | Description |
| --- | --- | --- |
| `led` | String | The LED name. Valid names are listed as `LedName` in the response from `/axis-cgi/ledcontrol/getleds.cgi?schemaversion=1` |
| `color` | String | The color. Valid color names are listed as `ColorName` in the response from `/axis-cgi/ledcontrol/getleds.cgi?schemaversion=1` |
| `duration` | Unsigned integer | Fixed actions: Number of seconds to keep flashing the LED. |
| `interval` | Unsigned integer | Number of milliseconds between flashes. |

#### Common examples

**Example 1**

Use the following command to make your device present you with the number of available LEDs (`LEDname`) and colors (`ColorName`).

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ledcontrol/getleds.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/ledcontrol/getleds.cgi?schemaversion=1Host: <servername>
```

**Example 2**

Use the following command to make the tally-led flash for 10 seconds with the color red.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/ledcontrol/set.cgi?name=tallyled&color=RED&schemaversion=1&duration=10"
```

```bash
GET /axis-cgi/ledcontrol/set.cgi?name=tallyled&color=RED&schemaversion=1&duration=10Host: <servername>
```

### Overlay text action

Use the overlay text action to display a dynamic text overlay. The action makes use of the modifier `#D`. By default, `#D` is an empty string. When the overlay text action is activated, `#D` is replaced by the text stored in parameter `text` (see table below).

If you use the `index` parameter, the action will write text to a specific text overlay specified by the modifier `#D<index>`. See [Dynamic text](/vapix/network-video/overlay-api/#dynamic-text). An action configured with an index will ignore the `channels` parameter.

When using this action, enable overlay text in the video channel and include the modifier `#D` in the overlay text. See example below.

This action can be run as:

-   **fixed action** — keep the overlay text during a predefined time (defined by parameter `duration`)
    
-   **unlimited action** — keep the overlay text as long as all event conditions are fulfilled.
    
-   Action ID
    
    `com.axis.action.fixed.set_overlay`
    
-   Action ID
    
    `com.axis.action.unlimited.set_overlay`
    

| Parameter | Valid values | Description |
| --- | --- | --- |
| `text` | String | The text to display. The modifier `#D` will be replaced by this text when the action is active. |
| `channels` | String | Comma-separated list of the video channels where the overlay text should be displayed. |
| `duration` | Unsigned integer | Fixed actions: Number of seconds to display the text. |
| `index` | integer from 1 to 16 | Optional. Specifies the dynamic text index to which the action applies. Using this parameter makes the `channels` parameter redundant. |

This example shows how to use to the overlay text action to display the text "Active input ports: input 1" for 10 seconds when input port 1 becomes active. When the input port is inactive, the text "Active input ports:" is displayed.

First, enable overlay text and set the text to "Active input ports: #D".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.Text.TextEnabled=yes&Image.I0.Text.String=Active%20input%20ports%3A%20%23D"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.Text.TextEnabled=yes&Image.I0.Text.String=Active%20input%20ports%3A%20%23DHost: <servername>
```

Next, create an action configuration and an action rule. This example uses `myActionService` created in section [Identification using entry service](#identification-using-entry-service).

```bash
try{  // Verify that the camera supports the action.  ActionTemplate\[\] actiontemplates = myActionService.GetActionTemplates();  if (actiontemplates.Any(    template => template.TemplateToken == "com.axis.action.fixed.set\_overay") == false)  {    // Camera does not support the overlay text action.    return;  }  // Create overlay text action  NewActionConfiguration newAction = new NewActionConfiguration  {    TemplateToken = "com.axis.action.fixed.set\_overlay",    Parameters = new ActionParameters    {      Parameter = new\[\]      {        new ActionParameter { Name = "text", Value = "input 1" }        new ActionParameter { Name = "channels", Value = "1" }        new ActionParameter { Name = "duration", Value = "10" }      }    }  };  // Add the action to the camera.  string actionId = myActionService.AddActionConfiguration(newAction);  // Create action rule  NewActionRule newActionRule = new NewActionRule  {    Name = "Display overlay text",    StartEvent = FormatTopicExpression("tns1:Device/tnsaxis:IO/tnsaxis:Port",        "boolean(//SimpleItem\[@Name=\\"port\\" and @Value=\\"1\\"\]) and "        + "boolean(//SimpleItem\[@Name=\\"state\\" and @Value=\\"1\\"\])")    PrimaryAction = actionId,    Enabled = true  };  // Add the action rule to the camera.  string actionRuleId = myActionService.AddActionRule(newActionRule);}catch (Exception e){  HandleException(e);}
```

### Play audio clip action

Use the play audio clip action to play an audio clip. The audio clip is an uploaded or recorded audio file which can be played by speakers built into or connected to the Axis product.

**Action ID**

-   **Fixed**: `com.axis.action.fixed.play.audioclip`
-   **Unlimited**: `com.axis.action.unlimited.play.audioclip`

| Parameter | Data type | Valid values | Description |
| --- | --- | --- | --- |
| `location` | String | `<location>` | Location of the clip. When using the location parameter for the play action, the clip parameter is not necessary. Accepts `*` as wildcard to play a random matching clip. Supported only if PlayOptions include `location`. |
| `audiooutput` | Integer | `0... (if 1+ index as in Properties.Audio.Source.A[AudioOuput - 1].Output = "yes" #)` | **Note**: This parameter has been deprecated as of AXIS OS 11.7 and will no longer receive any updates. Audio output if state is relevant. 0 if undefined. |
| `audiodeviceid` | Integer | `0, ...` | Parameter that determines what audio device that should play a media clip. Used as an alternative to audiooutput and they can not be used together. Needs to be paired with `audiooutputid` `(audiodeviceid=0&audiooutputid=0)`. |
| `audiooutputid` | Integer | `0...` | Parameter that determines which output on an audio device that should play a media clip. Required when `audiodeviceid` is specified. |
| `repeat` | Integer | `-1,0...` | Number of times to repeat the clip, where `-1` means repeat forever. `0` (default) means play once (no repeat). Supported by `action=play`. Supported only if PlayOptions include `repeat`. |
| `volume` | Integer | `0...1000` | The clip volume in percentage and linear volume scale. `0` means mute. Default is `100`. Supported by `action=play`. Only supported if PlayOptions include `volume`. |

info

The # in MediaClip.M# identifies the clip and is replaced by an integer starting from 0.

It is also possible to stop the play audio clip action. This is done with a fixed action that halts the ongoing playback of the audio clips. No parameters exist for this action.

**Action ID**

-   **Fixed**: `com.axis.action.fixed.stop.audioclip`

### Send images action

Use the send images action to send a images (JPEG) to a recipient.

This action can be run as:

-   **fixed action** — images are sent during a pre-event and post-event time.
-   **unlimited action** — images are sent during a pre-event time, while the event is running and during a post-event time.

| Recipient | Recipient ID | Action ID |
| --- | --- | --- |
| HTTP | `com.axis.recipient.http` | `com.axis.action.fixed.send_images.http` `com.axis.action.unlimited.send_images.http` |
| HTTPS | `com.axis.recipient.https` | `com.axis.action.fixed.send_images.https` `com.axis.action.unlimited.send_images.https` |
| SMTP | `com.axis.recipient.smtp` | `com.axis.action.fixed.send_images.smtp` `com.axis.action.unlimited.send_images.smtp` |
| FTP | `com.axis.recipient.ftp` | `com.axis.action.fixed.send_images.ftp` `com.axis.action.unlimited.send_images.ftp` |
| SFTP | `com.axis.recipient.sftp` | `com.axis.action.fixed.send_images.sftp` `com.axis.action.unlimited.send_images.sftp` |
| Network Share | `com.axis.recipient.networkshare` | `com.axis.action.fixed.send_images.networkshare` `com.axis.action.unlimited.send_images.networkshare` |

Specify the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `stream_options` | Percent-encoded string | List of stream parameters such as resolution, compression etc. All parameters supported by RTSP and HTTP stream requests can be used.Example: `stream_options=resolution%3D640x480%26compression%3D30%26rotation%3D180`Available RTSP stream parameters are listed in [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url).Available HTTP stream parameters are listed in [Image request arguments](/vapix/network-video/video-streaming/#image-request-arguments). |
| `pre_duration` | Unsigned integer | Pre-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately before the event. |
| `post_duration` | Unsigned integer | Post-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately after the event. |
| `create_folder` | String | Create a folder on the recipient to store uploaded files in. Modifiers can be used, see [Modifiers](#modifiers). |
| `filename` | String | File name for uploaded files. Modifiers can be used, see [Modifiers](#modifiers). |
| `max_sequence_number` | Unsigned integer | The maximum sequence number to use in file names if modifier `#s` is used. `0` = no maximum |
| `max_images` | Unsigned integer | Maximum number of images to upload. `0` = no limit |
| `images_per_mail` | Unsigned integer | SMTP recipients: The maximum number of images per email. |
| `custom_params` | String | HTTP and HTTPS recipients: Additional CGI arguments. |
| `subject` | String | SMTP recipients: Email subject. Modifiers can be used, see [Modifiers](#modifiers). |
| `message` | String | SMTP recipients: Email message. Modifiers can be used, see [Modifiers](#modifiers). |

### Send an MQTT message

This action is used when you want to configure an action rule by sending an MQTT message using the template `com.axis.action.fixed.mqttpublish`.

| Parameter | Valid values | Description |
| --- | --- | --- |
| Topic | String | The message topic. Must be at least one character and up to 1024. |
| QoS | 0, 1, 2 | Sets the Quality of Service level of the MQTT message, |
| Retained | true, false | Dictates if the MQTT message should be sent as a retained message. |
| Payload | String | The message payload that may include modifiers as per the modifiers section. May be empty, but not contain any more than 8192 characters. |

Please note that the MQTT client needs to be configured, activated and connected for messages to be successfully published.

### Send notification action

Use the send notification action to send notification messages to a recipient. The notification message can be formatted using modifiers, see [Modifiers](#modifiers).

The action can be run as:

-   **fixed action** — messages are sent during a pre-event and post-event time
-   **unlimited action** — (TCP recipients only) messages are sent during a pre-event time, while the event is running and during a post-event time. Please note that a minimum period of 1 is required when using this action.

| Recipient | Recipient ID | Action ID |
| --- | --- | --- |
| HTTP | `com.axis.recipient.http` | `com.axis.action.fixed.notification.http` |
| HTTPS | `com.axis.recipient.https` | `com.axis.action.fixed.notification.https` |
| SMTP | `com.axis.recipient.smtp` | `com.axis.action.fixed.notification.smtp` |
| TCP | `com.axis.recipient.tcp` | `com.axis.action.fixed.notification.tcp` `com.axis.action.unlimited.notification.tcp` |

Specify the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `message` | String | Notification message. Spaces are allowed. Modifiers can be used, see [Modifiers](#modifiers).HTTP and HTTPS recipients: The message will be sent in a CGI argument called `Message`. Spaces are allowed. If using more than 255 characters, some or all of the information provided in `parameters` (see below) will be excluded. |
| `parameters` | String | HTTP and HTTPS recipients: Additional CGI arguments. Spaces are not allowed; all text must be percent-encoded. |
| `period` | Unsigned integer | TCP recipients, continuous upload: Number of seconds between successive notification messages. |
| `subject` | String | SMTP recipients: Email subject. Modifiers can be used, see [Modifiers](#modifiers). |
| `method` | `GET` `POST` `PUT` `PATCH` `DELETE` | For HTTP and HTTPS notifications: The HTTP method to use when sending a notification. Defaults to `GET` if empty. |
| `http_headers` | Valid HTTP headers | For HTTP and HTTPS notifications: Multiple lines of valid HTTP headers, such as Content-Type: "`application/json`". |
| `body` | String | For HTTP and HTTPS notifications: The data that will be sent in the request body by `POST`, `PUT` and `PATCH`. |

### Send video clip action

Use the send video clip action to send a video clip to a recipient.

This action can be run as:

-   **fixed action** — video is recorded during a pre-event and post-event time
-   **unlimited action** — video is recorded during a pre-event time, while the event is running and during a post-event time

| Recipient | Recipient ID | Action ID |
| --- | --- | --- |
| HTTP | `com.axis.recipient.http` | `com.axis.action.fixed.send_videoclip.http` `com.axis.action.unlimited.send_videoclip.http` |
| HTTPS | `com.axis.recipient.https` | `com.axis.action.fixed.send_videoclip.https` `com.axis.action.unlimited.send_videoclip.https` |
| SMTP | `com.axis.recipient.smtp` | `com.axis.action.fixed.send_videoclip.smtp` `com.axis.action.unlimited.send_videoclip.smtp` |
| FTP | `com.axis.recipient.ftp` | `com.axis.action.fixed.send_videoclip.ftp` `com.axis.action.unlimited.send_videoclip.ftp` |
| SFTP | `com.axis.recipient.sftp` | `com.axis.action.fixed.send_videoclip.sftp` `com.axis.action.unlimited.send_videoclip.sftp` |
| Network share | `com.axis.recipient.networkshare` | `com.axis.action.fixed.send_videoclip.networkshare` `com.axis.action.unlimited.send_videoclip.networkshare` |

Specify the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `stream_options` | Percent-encoded string | List of stream parameters such as resolution, compression etc. All parameters supported by RTSP and HTTP stream requests can be used.Example: `stream_options=resolution%3D640x480%26compression%3D30%26rotation%3D180`Available RTSP stream parameters are listed in [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url).Available HTTP stream parameters are listed in [Image request arguments](/vapix/network-video/video-streaming/#image-request-arguments). |
| `pre_duration` | Unsigned integer | Pre-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately before the event. |
| `post_duration` | Unsigned integer | Post-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately after the event. |
| `create_folder` | String | Create a folder on the recipient to store uploaded files in. Modifiers can be used, see [Modifiers](#modifiers). |
| `filename` | String | File name for uploaded files. Modifiers can be used, see [Modifiers](#modifiers). |
| `max_file_size` | Unsigned integer | Not supported. Use empty string. |
| `max_duration` | Unsigned integer | Not supported. Use empty string. |
| `custom_params` | String | HTTP and HTTPS recipients: Additional CGI arguments. |
| `subject` | String | SMTP recipients: Email subject. Modifiers can be used, see [Modifiers](#modifiers). |
| `message` | String | SMTP recipients: Email message. Modifiers can be used, see [Modifiers](#modifiers). |

## Recipient templates

This section describes available recipient templates. Each template lists the parameters needed to configure the recipient. All parameters must be specified; if a parameter should not be used, its value should be set to an empty string.

info

Supported templates are product and AXIS OS dependent. Use GetRecipientTemplates to list the recipient templates supported by the Axis product.

### FTP recipient

An FTP recipient can receive video clips, uploaded images and notification messages.

-   **Recipient ID**: `com.axis.recipient.ftp`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `host` | String (IP address or host name) | Required. The address to connect to. Use the FTP server’s IP address or host name. |
| `upload_path` | String | Path to the FTP server directory where uploaded files should be stored. The directory must exist. |
| `port` | Unsigned integer | FTP port. Default: `21` |
| `login` | String | User name for the FTP server. |
| `password` | String | Password for the FTP server user. |
| `passive` | `1` `0` | Use passive mode. If `passive=1` the Axis product establishes a passive FTP connection to the FTP server using the `PASV` command. A passive connection is often required if there is a firewall between the product and the FTP server. |
| `temporary` | `1` `0` | Supported in AXIS OS 5.70 and later.Use temporary mode. If `temporary=1`, files are first uploaded to a temporary file on the FTP server. When upload is completed, the file is renamed and transferred to the final destination. |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the FTP recipient. Default: `0` |

### SFTP recipient

An SFTP recipient uses SSH File Transfer Protocol (SFTP) for encrypted transfer of video clips (action send video clip) and uploaded images (action send images). SFTP is a more secure method than FTP but file transfer might be slower, especially for large files such as high resolution video.

The SFTP recipient supports SFTP servers using SSH-2 with RSA and DSA host key types. RSA is the preferred method. To use DSA, disable the RSA key on the SFTP server.

-   **Recipient ID**: `com.axis.recipient.sftp`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `host` | String (IP address or host name) | Required. The address to connect to. Use the SFTP server’s IP address or host name. |
| `upload_path` | String | Path to the SFTP server directory where uploaded files should be stored. The directory must exist. |
| `port` | Unsigned integer | SFTP server port.Default: `22` |
| `login` | String | User name for the SFTP user. |
| `password` | String | Password for the SFTP user. |
| `ssh_host_pub_key_md5` | 32 hexadecimal digits | The MD5 checksum of the SFTP server’s public key.Case-insensitive string with 32 hexadecimal characters `[0..9,A..F]`.It is mandatory to have at least one key. If SHA256 is given MD5 can be skipped. |
| `ssh_host_pub_key_sha256` | String | The SHA256 checksum of the server’s public key.It is mandatory to have at least one key. If MD5 is given SHA256 can be skipped. |
| `ssh_auth_type` | `1` _Currently not supported_ `2` | SSH authentication type.`1` = Public key authentication`2` = Password authentication |
| `ssh_public_key` (Currently not supported) | String | SSH public key. |
| `ssh_private_key` (Currently not supported) | String | SSH private key. |
| `ssh_private_key_passphrase` (Currently not supported) | String | SSH private key passphrase. |
| `temporary` | `1` `0` | Not supported. |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the SFTP recipient.Default: `0` |

### HTTP recipient

An HTTP recipient can receive video clips, uploaded images and notification messages.

-   **Recipient ID**: `com.axis.recipient.http`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `upload_url` | String | Required. A URL containing the network address to the HTTP server and the script that will handle the request. For example: `http://ip_address/cgi-bin/notify.cgi` |
| `login` | String | User name for the HTTP server |
| `password` | String | Password for the HTTP server user |
| `proxy_host` | IP address or host name | Proxy address |
| `proxy_port` | Unsigned integer | Proxy port |
| `proxy_login` | String | User name for the proxy |
| `proxy_password` | String | Password for the proxy user |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the HTTP recipient. Default: `0` |

### HTTPS recipient

An HTTPS recipient can receive video clips, uploaded images and notification messages.

-   **Recipient ID**: `com.axis.recipient.https`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `upload_url` | String | Required. A URL containing the network address to the HTTPS server and the script that will handle the request. For example: `https://ip_address/cgi-bin/notify.cgi` |
| `login` | String | User name for the HTTPS server |
| `password` | String | Password for the HTTPS server user |
| `proxy_host` | IP address or host name | Proxy address |
| `proxy_port` | Unsigned integer | Proxy port |
| `proxy_login` | String | User name for the proxy |
| `proxy_password` | String | Password for the proxy user |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the HTTPs recipient. Default: `0` |
| `validate_server_cert` | `0` `1` | `1` = validate the HTTPS server certificate against certificates installed in the product. `0` = Do not validate the certificate. |

### Network share recipient

A network share recipient can receive video clips and uploaded images.

A network share can be a share on a NAS (Network Attached Storage) or any server that uses CIFS (Common Internet File System) also known as SMB (Server Message Block).

Using a network share recipient allows you to store recordings with user defined directory, structure and file names. The files are stored as mkv files.

-   **Recipient ID**: `com.axis.recipient.networkshare`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `upload_path` | String | The path to the directory on the network share where uploaded images or recordings should be stored. |
| `share_id` | Share ID | The Share ID. The Share ID can be retrieved from `/axis-cgi/disks/networkshare/list.cgi?shareid=all` |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the Network Share recipient. Default: `0` |

### SMTP recipient

An SMTP recipient can receive notification messages. Snapshots can be attached as email attachments.

-   **Recipient ID**: `com.axis.recipient.smtp`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `email_to` | Email address | The email address to send messages to |
| `email_from` | Email address | Email address of the sender |
| `host` | IP address or host name | IP address or host name for the SMTP server |
| `port` | Unsigned integer | SMTP server port |
| `login` | String | User name for the SMTP server |
| `password` | String | Password for the SMTP server user |
| `pop_host` | IP address or host name | IP address or host name for the POP3 server used for authentication |
| `pop_port` | Unsigned integer | POP3 server port |
| `pop_login` | String | User name for the POP server |
| `pop_password` | String | Password for the POP server user |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the SMTP recipient. Default: `0` |
| `encryption` | `none` `ssl` `tls` | The encryption method to use. |
| `validate_server_cert` | `0` `1` | `1` = validate the SMTP server certificate against certificates installed in the product. `0` = Do not validate the certificate. |

### TCP recipient

A TCP recipient can receive notification messages.

-   **Recipient ID**: `com.axis.recipient.tcp`

| Parameter | Valid values | Description |
| --- | --- | --- |
| `host` | IP address or host name | Required. The IP address or host name of the TCP server. |
| `port` | Unsigned integer | TCP port |
| `qos` | `0 ... 63` | Quality of Service. The DSCP (Differentiated Services Codepoint) value for network traffic from the TCP recipient. Default: `0` |

### Adding recipients

**FTP recipient**

```bash
<?xml version="1.0" encoding="UTF-8" ?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope">    <SOAP-ENV:Header />    <SOAP-ENV:Body xmlns:act="http://www.axis.com/vapix/ws/action1">        <act:AddRecipientConfiguration>            <act:NewRecipientConfiguration>                <act:Name>FTP-Server</act:Name>                <act:TemplateToken>com.axis.recipient.ftp</act:TemplateToken>                <act:Parameters>                    <act:Parameter Name="host" Value="172.25.200.100" />                    <act:Parameter Name="upload\_path" Value="" />                    <act:Parameter Name="port" Value="21" />                    <act:Parameter Name="login" Value="test" />                    <act:Parameter Name="password" Value="test" />                    <act:Parameter Name="passive" Value="0" />                    <act:Parameter Name="temporary" Value="0" />                    <act:Parameter Name="qos" Value="0" />                </act:Parameters>            </act:NewRecipientConfiguration>        </act:AddRecipientConfiguration>    </SOAP-ENV:Body></SOAP-ENV:Envelope>
```

**TCP recipient**

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope xmlns:aa="http://www.axis.com/vapix/ws/action1" xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:AddRecipientConfiguration xmlns="http://www.axis.com/vapix/ws/action1">            <NewRecipientConfiguration>                <TemplateToken>com.axis.recipient.tcp</TemplateToken>                <Name>Test</Name>                <Parameters>                    <Parameter Name="host" Value="172.25.200.100" />                    <Parameter Name="port" Value="50000" />                    <Parameter Name="qos" Value="0" />                </Parameters>            </NewRecipientConfiguration>        </aa:AddRecipientConfiguration>    </soap:Body></soap:Envelope>
```

**HTTP recipient**

```bash
<?xml version="1.0" encoding="utf-8" ?><soap:Envelope xmlns:aa="http://www.axis.com/vapix/ws/action1" xmlns:soap="http://www.w3.org/2003/05/soap-envelope">    <soap:Body>        <aa:AddRecipientConfiguration xmlns="http://www.axis.com/vapix/ws/action1">            <NewRecipientConfiguration>                <TemplateToken>com.axis.recipient.http</TemplateToken>                <Name>{{HTTP\_NAME}}</Name>                <Parameters>                    <Parameter Name="upload\_url" Value="{{HTTP\_URL}}" />                    <Parameter Name="login" Value="{{HTTP\_USER}}" />                    <Parameter Name="password" Value="{{HTTP\_PASSWD}}" />                    <Parameter Name="proxy\_host" Value="{{HTTP\_PROXY}}" />                    <Parameter Name="proxy\_port" Value="{{HTTP\_PROXY\_PORT}}" />                    <Parameter Name="proxy\_login" Value="{{HTTP\_PROXY\_USER}}" />                    <Parameter Name="proxy\_password" Value="{{HTTP\_PROXY\_PASSWD}}" />                    <Parameter Name="qos" Value="0" />                </Parameters>            </NewRecipientConfiguration>        </aa:AddRecipientConfiguration>    </soap:Body></soap:Envelope>
```

**HTTPS recipient**

```bash
<?xml version="1.0" encoding="utf-8" ?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope">    <SOAP-ENV:Header />    <SOAP-ENV:Body xmlns:act="http://www.axis.com/vapix/ws/action1">        <act:AddRecipientConfiguration>            <act:NewRecipientConfiguration>                <act:Name>MyHTTPSServer</act:Name>                <act:TemplateToken>com.axis.recipient.https</act:TemplateToken>                <act:Parameters>                    <act:Parameter Name="validate\_server\_cert" Value="1" />                    <act:Parameter Name="upload\_url" Value="{{HTTP\_URL}}" />                    <act:Parameter Name="login" Value="{{HTTP\_USER}}" />                    <act:Parameter Name="password" Value="{{HTTP\_PASSWD}}" />                    <act:Parameter Name="proxy\_host" Value="{{HTTP\_PROXY}}" />                    <act:Parameter Name="proxy\_port" Value="{{HTTP\_PROXY\_PORT}}" />                    <act:Parameter Name="proxy\_login" Value="{{HTTP\_PROXY\_USER}}" />                    <act:Parameter Name="proxy\_password" Value="{{HTTP\_PROXY\_PASSWD}}" />                    <act:Parameter Name="qos" Value="0" />                </act:Parameters>            </act:NewRecipientConfiguration>        </act:AddRecipientConfiguration>    </SOAP-ENV:Body></SOAP-ENV:Envelope>
```

## Modifiers

Modifiers can be used to format file names, folders for uploaded images, notification messages, text in image overlays and similar. A modifier always starts with a **%** or **#** character, followed by another character.

The percent ("%") and hashtag ("#") must be percent-encoded. That means:

-   % = `%25`
-   \# = `%23`

Use `image-%F-%H-%M-%S.jpg` so timestamp uploaded video snapshots with the date, hour, minute and second the snapshot was taken.

The following modifiers are available:

Date

| Modifier | Description | Example |
| --- | --- | --- |
| `%c` | Date and time. | Sun Dec 25 10:25:01 2011 |
| `%D` | Date in format MM/DD/YY. | 12/25/11 |
| `%F` | Date in format YYYY-MM-DD. | 2011–12–25 |
| `%x` | Same as `%D`. | 12/25/11 |

Time

| Modifier | Description | Example |
| --- | --- | --- |
| `%p` | AM or PM according to the given time or the corresponding strings for the current locale. Noon is treated as PM and midnight as AM. |  |
| `%r` | Time in a.m or p.m. notation. | 10:25:01 AM |
| `%R` | Time in 24-hour notation without seconds. | 10:25 |
| `%T` | Time in 24-hour notation with seconds. | 10:25:01 |
| `%X` | Same as `%T`. |  |
| `%z` | Time zone as offset from UTC. | +0000 |
| `%Z` | Time zone name or abbreviation. | GMT |

Year

| Modifier | Description | Example |
| --- | --- | --- |
| `%C` | The century as a 2-digit number (year/100). | 20 |
| `%G` | The ISO 8601 week-numbering year as a 4-digit number. | 2011 |
| `%g` | The ISO 8601 week-numbering year as a 2-digit number without the century, range 00 to 99. | 11 |
| `%Y` | The Gregorian calendar year as a 4-digit number. | 2011 |
| `%y` | The Gregorian calendar year as a 2-digit number without the century, range 00 to 99. | 11 |

Month

| Modifier | Description | Example |
| --- | --- | --- |
| `%b` | Abbreviated month name. | Dec |
| `%B` | Full month name. | December |
| `%h` | Same as `%b`. |  |
| `%m` | Month as a 2-digit number, range 01 to 12. | 12 |

Week

| Modifier | Description | Example |
| --- | --- | --- |
| `%U` | The week number as a 2-digit number, range 00 to 53. Sunday is the first day of the week. Week 01 is the week starting with the first Sunday of the current year. | 52 |
| `%V` | The ISO 8601 week number as a 2-digit number, range 01 to 53. Monday is the first day of the week. Week 01 is the first week that has at least four days in the current year. | 51 |
| `%W` | The week number as a 2-digit number, range 00 to 53. Monday is the first day of the week. Week 01 is the week starting with the first Monday of the current year. | 51 |

Day

| Modifier | Description | Example |
| --- | --- | --- |
| `%a` | Abbreviated weekday name. | Sun |
| `%A` | Full weekday name. | Sunday |
| `%d` | Day of the month as a 2-digit number, range 01 to 31. | 25 |
| `%e` | Same as `%d` but a leading zero is replaced by a blank space. | 25 |
| `%j` | Day of the year as a 3-digit number, range 001 to 366. | 359 |
| `%u` | Day of the week as an 1-digit number, range 1 to 7. Monday is 1. | 7 |
| `%w` | Day of the week as an 1-digit number, range 0 to 6. Sunday is 0. | 0 |

Hour

| Modifier | Description | Example |
| --- | --- | --- |
| `%H` | Hour in 24-hour fomat, range 00 to 23. | 10 |
| `%I` | Hour in 12-hour format, range 01 to 12. | 10 |
| `%k` | Same as `%H` but a leading zero is replaced by a blank space. |  |
| `%l` | Same as `%I` but a leading zero is replaced by a blank space. |  |

Minute

| Modifier | Description | Example |
| --- | --- | --- |
| `%M` | Minute as a 2-digit number, range 00 to 59. | 25 |

Second

| Modifier | Description | Example |
| --- | --- | --- |
| `%f` | 1/100 seconds as a 2-digit number. | 67 |
| `%s` | The number of seconds since EPOCH, that is, since 1970–01–01 00:00:00 UTC. | 1319178723 |
| `%S` | The current second as a 2-digit number, range 00 to 59. | 10 |

Product and system information

| Modifier | Description | Example |
| --- | --- | --- |
| `#i` | The IP address. | 10.13.24.88 |
| `#m` | The short MAC address (last 6 characters). | 77:F8:26 |
| `#M` | The full MAC address (all characters). | 00:40:8C:77:F8:26 |
| `#n` | The host name. | axis-00408c77f826 |
| `#U<index>` | The fan status. `<index>` = A specified fan. For example `1`. | Stopped |
| `#TC<index>` | The temperature of the camera sensor in Celsius. `<index>` = A specified camera sensor. For example `1`. | 48,4 |
| `#TF<index>` | The temperature of the camera sensor in Fahrenheit. _index_\> = A specified camera sensor. For example `1`. | 119,1 |

**Video information** _Bit rate and frame rate modifiers are available in products with ARTPEC® chips._

| Modifier | Description | Example |
| --- | --- | --- |
| `#b` | Bit rate in kbit/s (no decimals). | 16333 |
| `#B` | Bit rate in Mbit/s (two decimals). | 16.33 |
| `#r` | Frame rate with two decimals. | 30.00 |
| `#R` | Frame rate without decimals. | 30 |
| `#v` | Video source number. | 1 |

Pan/Tilt/Zoom information

| Modifier | Description | Example |
| --- | --- | --- |
| `#x` | Pan coordinate (signed, with two decimals). | —77.61 |
| `#y` | Tilt coordinate (signed, with two decimals). | —7.61 |
| `#z` | Zoom coordinate (range 1 to 19999). | 256 |
| `#Z` | Zoom magnification (with one decimal). | 12.0 |
| `#p` | Preset position number. If not at a preset position, blank space is used. | 3 |
| `#P` | Preset name. If not at a preset position, blank space is used. | Door |
| `#L` | OSDI (On Screen Directional Indicator) zone name. A zone within specified pan and tilt coordinates. If not within an OSDI zone, blank space is used. | Construction |

Others

| Modifier | Description | Example |
| --- | --- | --- |
| `#s` | Sequence number of the video image as a 5-digit number. |  |
| `#D` | Dynamic text overlay. |  |
| `%%` | The `%` character. |  |
| `##` | The `#` character. |  |

## Helper functions

This section defines the helper functions used in this document.

-   `CreateActionServiceClient` and `CreateEventServiceClient`, see [Create web service connections](#create-web-service-connections).
-   Functions for data formatting, see [Formatting data](#formatting-data).
-   Error handling functions, see [Error handling](#error-handling).

### Create web service connections

`CreateActionServiceClient` creates an action service client.

```bash
/// <summary>/// Creates an action service client with the specified address and the provided credentials./// </summary>private static ActionClient CreateActionServiceClient(  string address, string userName, string password){  // Create SOAP 1.2 text encoding binding element.  TextMessageEncodingBindingElement soap12Encoding =    new TextMessageEncodingBindingElement(MessageVersion.Soap12, Encoding.UTF8);  // Create HTTP transport binding element with Digest authentication.  HttpTransportBindingElement httpTransport = new HttpTransportBindingElement();  httpTransport.AuthenticationScheme = AuthenticationSchemes.Digest;  System.ServiceModel.Channels.Binding binding = new CustomBinding(soap12Encoding, httpTransport);  EndPointAddress endpoint = new EndpointAddress(string.Format("http://<0>/vapix/services", address));  // Create the client and set credentials.  ActionClient client = new ActionClient(binding, endpoint);  client.ClientCredentials.HttpDigest.AllowedImpersonationLevel = System.Security.Principal.TokenImpersonationLevel.Impersonation;  client.ClientCredentials.HttpDigest.ClientCredential.UserName = userName;  client.ClientCredentials.HttpDigest.ClientCredential.Password = password;  client.ClientCredentials.HttpDigest.ClientCredential.Domain = "localhost";  client.ClientCredentials.UserName.UserName = userName;  client.ClientCredentials.UserName.Password = password;   return client;}
```

`CreateEventServiceClient` creates an event service client.

```bash
/// <summary>/// Creates an event service client with the specified address and the provided credentials./// </summary>private static EventClient CreateEventServiceClient(  string address, string userName, string password){  // Create SOAP 1.2 text encoding binding element.  TextMessageEncodingBindingElement soap12Encoding =    new TextMessageEncodingBindingElement(MessageVersion.Soap12, Encoding.UTF8);  // Create HTTP transport binding element with Digest authentication.  HttpTransportBindingElement httpTransport = new HttpTransportBindingElement();  httpTransport.AuthenticationScheme = AuthenticationSchemes.Digest;   Binding binding = new CustomBinding(soap12Encoding, httpTransport);  EndpointAddress endpoint = new EndpointAddress(string.Format("http://<0>/vapix/services", address));  // Create the client and set credentials.  EventClient client = new EventClient(binding, endpoint);  client.ClientCredentials.HttpDigest.AllowedImpersonationLevel = System.Security.Principal.TokenImpersonationLevel.Impersonation;  client.ClientCredentials.HttpDigest.ClientCredential.UserName = userName;  client.clientCredentials.HttpDigest.ClientCredential.Password = password;  client.ClientCredentials.HttpDigest.ClientCredential.Domain = "localhost";  client.ClientCredentials.UserName.UserName = userName;  client.ClientCredentials.UserName.Password = password;   return client;}
```

### Formatting data

The following functions are used to format XML data.

```bash
/// <summary>/// Document header for XML documents./// </summary>private const string DocumentHeader = @"<?xml version=""1.0"" encoding=""UTF-8""?>";
```

```bash
/// <summary>/// XML for a topic filter./// </summary>private const string TopicXml =  @"<wsnt:TopicExpression " +    @"xmlns:tns1=""http://www.onvif.org/ver10/topics"" " +    @"xmlns:tnsaxis=""http://www.axis.com/2009/event/topics"" " +    @"xmlns:wsnt=""http://docs.oasis-open.org/wsn/b-2"" " +    @"Dialect=""http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet"">" +    @"<0>" +  @"</wsnt:TopicExpression>";
```

```bash
/// <summary>/// XML for a message filter./// </summary>private const string MessageXml =  @"<wsnt:MessageContent " +    @"xmlns:wsnt=""http://docs.oasis-open.org/wsn/b-2"" " +    @"Dialect=""http://www.onvif.org/ver10/tev/messageContentFilter/ItemFilter"">" +    @"<0>" +  @"</wsnt:MessageContent>";
```

```bash
/// <summary>/// Formats a topic expression from the provided topic and message filters./// </summary>private static FilterType FormatTopicExpression(string topicFilter, string messageFilter = null){  // Create a list with the topic filter formatted as XML.  List<XmlElement> xmlElements = new List<XmlElement>  {    ToXml(TopicXml, topicFilter)  };  // If there is a message filter add it to the list.  if (!string.IsNullOrWhiteSpace(messageFilter))  {    xmlElements.Add(ToXml(MessageXml, messageFilter));  }  // Return the formatted topic expression.  return new FilterType { Any = xmlElements.ToArray() };}
```

```bash
/// <summary>/// Converts a string to an <see cref="XmlElement"/>./// </summary>private static XmlElement ToXml(string xml, string data){  string document = DocumentHeader + string.Format(xml, data);  XmlDocument doc = new XmlDocument();  doc.LoadXml(document);  return doc.DocumentElement;}
```

### Error handling

The following functions are used for error handling.

```bash
/// <summary>/// Method for handling exceptions that can occur during web service calls./// </summary>/// <param name="exception">The exception.</param>private void HandleException(Exception exception){  if (exception is MessageSecurityException)  {    // Invalid credentials.  }  if (exception is FaultException)  {    // Check the documentation to see a list of possible faults.  }  if (exception is ProtocolException)  {    // .NET fails to catch some FaultExceptions so look at the ProtocolException to be sure    // that it isn't a hidded FaultException.    Exception e = ToFaultException(exception as ProtocolException);    if (e is FaultException)    {      // Check the documentation to see a list of possible faults.    }    else    {      // It is a real ProtocolException.      // These can be thrown if the client and server uses different versions of the WSDL.    }  }  if (exception is CommunicationException ||      exception is TimeoutException)  {    // Failed to contact camera.  }  // No recognized exception  throw exception;}
```

```bash
/// <summary>/// Transforms the exception to a FaultException if possible./// </summary>/// <param name="e">The exception to transform.</param>/// <returns>A FaultException or e if transformation failed.</returns>private static Exception ToFaultException(CommunicationException e){  WebException webException = e.InnerException as WebException;  if (webException != null && webException.Status == WebExceptionStatus.ProtocolError)  {    try    {      using (HttpWebResponse response = (HttpWebResponse)webException.Response)      using (Stream responseStream = response.GetResponseStream())      {        if (responseStream != null && responseStream.CanRead)        {          using (StreamReader textStream = new StreamReader(responseStream, Encoding.UTF8))          {            string soapErrorXml = textStream.ReadToEnd();            return ParseFaultException(soapErrorXml) ?? e;          }        }      }    catch (IOException)    {      return e;    }  }  return e;}
```

```bash
// Strings used in the XML parsing.private const string SoapNamespace = "{http://www.w3.org/2003/05/soap-envelope}";private const string Fault = SoapNamespace + "Fault";private const string Code = SoapNamespace + "Code";private const string SubCode = SoapNamespace + "Subcode";private const string Value = SoapNamespace + "Value";private const string Reason = SoapNamespace + "Reason";private const string Text = SoapNamespace + "Text";
```

```bash
/// <summary>/// Parses the SOAP error./// </summary>/// <param name="soapErrorXml">The SOAP error XML.</param>/// <returns>The parsed error or null if parsing failed.</returns>private static FaultException ParseFaultException(string soapErrorXml){  try  {    XDocument xml = XDocument.Parse(soapErrorXml);    var dec = xml.Descendants(Fault);    var fault =      (from faultItem in dec        select new        {          Code = GetValueOrDefault(faultItem.Elements(Code).Elements(Value)),          SubCode = GetValueOrDefault(          faultItem.Elements(Code).Elements(SubCode).Elements(Value)),          SubSubCode = GetValueOrDefault(          faultItem.Elements(Code).Elements(SubCode).Elements(SubCode).Elements(Value)),          Reason = GetValueOrDefault(faultItem.Elements(Reason).Elements(Text))        }).First();    FaultCode code;    if (!string.IsNullOrWhiteSpace(fault.SubSubCode))    {      FaultCode subSubCode = new FaultCode(fault.SubSubCode, string.Empty);      FaultCode subCode = new FaultCode(fault.SubCode, string.Empty, subSubCode);      code = new FaultCode(fault.Code, string.Empty, subCode);    }    else if (!string.IsNullOrWhiteSpace(fault.SubCode))    {      FaultCode subCode = new FaultCode(fault.SubCode, string.Empty);      code = new FaultCode(fault.Code, string.Empty, subCode);    }    else    {      code = new FaultCode(fault.Code, string.Empty);    }    FaultException error = new FaultException(fault.Reason, code);    return error;  }  catch (XmlException)  {    // Parsing failed - return null;    return null;  }}
```

```bash
/// <summary>/// Gets the value of the first element in the list or an empty string if list is empty./// </summary>/// <returns>The value or an empty string if list is empty.</returns>private static string GetValueOrDefault(IEnumerable<XElement> elements){  var element = elements == null ? null : elements.FirstOrDefault();  return element == null ? string.Empty : element.Value;}
```