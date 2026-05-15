---
title: Application configuration API
url: "https://developer.axis.com/vapix/applications/application-configuration-api/"
category: vapix
subcategory: applications
sha256: a2cadd135a5f4e460af81ce406c9e25377df60776f646bfdb3804bb4a457bb07
scraped_at: "2026-01-09T15:01:03.276Z"
page_height: 18402
---

# Application configuration API

## Description

VAPIX® AXIS Application Configuration API is used to configure applications developed by Axis, for example AXIS Video Motion Detection and AXIS Cross Line Detection.

Supported functionality:

-   Get the application configuration. See [Get application configuration](#get-application-configuration).
-   Modify the application configuration. [Modify application configuration](#modify-application-configuration).
-   Obsolete: List installed applications. This operation has been removed from AXIS OS 12.0. Replaced by `/axis-cgi/applications/list.cgi` in [Application API](/vapix/applications/application-api/).

### Identification

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.00` or later
-   **AXIS OS**: 5.11 or later. Removed in 12.0

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

### Dependencies

Applications are uploaded and controlled using [Application API](/vapix/applications/application-api/).

### Obsoletes

-   The list operation `/axis-cgi/vaconfig.cgi?action=list` is obsolete and should not be used. This operation is replaced by `/axis-cgi/applications/list.cgi` in [Application API](/vapix/applications/application-api/).
-   The application configuration interface has been made obsolete as of Axis OS version 11.11 and will be removed and made unavailable with Axis OS version 12.0.

## Common examples

These examples demonstrate how to use VAPIX® AXIS Application Configuration API.

### Get the application configuration

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=ExampleApp"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=ExampleAppHost: <servername>
```

Response:

```bash
<reply result="ok">    <config version="1.0">        <application name="ExampleApp">            <ruleEngine>                <namedObjects>                    <namedObject name="ExampleLine1">                        <data knownNameType="geometry.segment">                            <segment>                                <point x="-0.5" y="0.0" />                                <point x="0.5" y="0.0" />                            </segment>                        </data>                    </namedObject>                    <namedObject name="ExamplePolygon1">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.60" y="0.60" />                                <point x="0.60" y="-0.60" />                                <point x="-0.60" y="-0.60" />                                <point x="-0.60" y="0.60" />                            </polygon>                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="example\_rule" function="example\_function">                        <parameter name="ExampleLineParameter" value="ExampleLine1" />                        <parameter name="ExamplePolygonParameter" value="ExamplePolygon1" />                    </rule>                </rules>                <scripts>                    <script encryption="1">example.lua</script>                </scripts>                <events>                    <event name="example\_event">                        <attr key="example\_state" nicename="Example State" tag="property\_state" />                    </event>                </events>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>            </ruleEngine>        </application>    </config></reply>
```

### Modify the application configuration

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=ExampleApp<config version="1.0">  <application name="ExampleApp">    <ruleEngine>      <namedObjects>        <namedObject name="ExampleLine1">          <data knownNameType="geometry.segment">            <segment>              <point x="-0.5" y="0.0"/>              <point x="0.5" y="0.0"/>            </segment>          </data>        </namedObject>        <namedObject name="ExamplePolygon1">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.60" y="0.60"/>              <point x="0.60" y="-0.60"/>              <point x="-0.60" y="-0.60"/>              <point x="-0.60" y="0.60"/>            </polygon>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="example\_rule" function="example\_function">          <parameter name="ExampleLineParameter" value="ExampleLine1"/>          <parameter name="ExamplePolygonParameter" value="ExamplePolygon1"/>        </rule>      </rules>      <scripts>        <script encryption="1">example.lua</script>      </scripts>      <events>        <event name="example\_event">          <attr key="example\_state" nicename="Example State" tag="property\_state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>    </ruleEngine>  </application></config></reply>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=ExampleApp<config version="1.0">  <application name="ExampleApp">    <ruleEngine>      <namedObjects>        <namedObject name="ExampleLine1">          <data knownNameType="geometry.segment">            <segment>              <point x="-0.5" y="0.0"/>              <point x="0.5" y="0.0"/>            </segment>          </data>        </namedObject>        <namedObject name="ExamplePolygon1">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.60" y="0.60"/>              <point x="0.60" y="-0.60"/>              <point x="-0.60" y="-0.60"/>              <point x="-0.60" y="0.60"/>            </polygon>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="example\_rule" function="example\_function">          <parameter name="ExampleLineParameter" value="ExampleLine1"/>          <parameter name="ExamplePolygonParameter" value="ExamplePolygon1"/>        </rule>      </rules>      <scripts>        <script encryption="1">example.lua</script>      </scripts>      <events>        <event name="example\_event">          <attr key="example\_state" nicename="Example State" tag="property\_state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>    </ruleEngine>  </application></config></reply>
```

### Example of an event emitted from the application

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tns1:RuleEnginge/tnsaxis:ExampleApp/example\_event            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://daf20c8-c41f-11e0-8c89-00408cb96106/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2012-03-07T13:44:34.112703Z" PropertyOperation="Initialized">                    <tt:Source />                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="example\_state" Value="0" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

## Application configuration

The application configuration is an XML file stored in the Axis product. If the application configuration is modified, the file is replaced by a new configuration file.

If the application configuration is modified while the application is running, the application will be restarted with the new configuration.

The application cannot be started if it is not possible to parse the XML file. If the application configuration is malformed, but still parsable, the application may not work properly or may fail to run.

**XML Application Setup Data Description**

The application configuration is defined in XML format. Most parts define how the application shall run and should not be modified.

For description of the application configuration for a particular application, see the documentation provided with the application.

| XML path | Attribute | Valid values | Description |
| --- | --- | --- | --- |
| `application/ruleEngine/namedObjects` |  |  | Section with all named objects used by the application. |
| `application/ruleEngine/rules` |  |  | Section will all rules used by the application. |
| `application/ruleEngine/rules/rule` | `name` | String | Name of the rule. |
|  | `function` | String | Name of the rule function used to execute the rule. The function which is defined in a script file (see scripts section), is executed with the provided parameter values as input. |
| `application/ruleEngine/rules/rule/parameter` | `name` | String | Name of a paramer used by the rule function. |
|  | `value` | String | Value of a parameter used by the rule function. |
| `application/ruleEngine/scripts` |  |  | Section with scripts used by the application. |
| `application/ruleEngine/scripts/script` |  | String | Name of a script file used by the application. |
|  | `encryption` | `0` `1` | `1` = The script is encrypted. `0` = The script is not encrypted. |
| `application/ruleEngine/events` |  |  | Section with all events used by the application. |
| `application/ruleEngine/events/event` | `name` | String | Name of an event emitted by the application. |
| `application/ruleEngine/events/event/attr` | `key` | String | Key string for the event. |
|  | `tag` | `source` `data` `property-state` | `source` = This is source information in the event metadata. `data` = This is data information in the event metadata. `property-state` = This is a stateful event. The current state is `0` or `1`. |
| `application/ruleEngine/moteConfig` |  |  | Section with all MOTE configuration options. Different applications may have different MOTE configuration. |
| `application/ruleEngine/moteConfig/option` | `name` | `boundingBox` | Name of the MOTE configuration option. |
|  | `value` | `true` `false` | `true` = Bounding box should be used. `false` = Bounding box should not be used. |
| `application/ruleEngine/moteConfig/option` | `name` | `polygon` | Name of the MOTE configuration option. |
|  | `value` | `true` `false` | `true` = Polygon should be used. `false` = Polygon should not be used. |
| `application/ruleEngine/moteConfig/option` | `name` | `velocity` | Name of the MOTE configuration option. |
|  | `value` | `true` `false` | `true` = Velocity should be used. `false` = Velocity should not be used. |

## HTTP API
### Manage I/O ports

Use `/axis-cgi/io/port.cgi` to retrieve information about port status and directions, to activate and deactivate ports and to monitor ports.

info

In `/axis-cgi/io/port.cgi` requests and in all responses, port numbering (Port ID below) starts from one (where one corresponds to the physical port labeled `1`).

#### Request

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/io/port.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/io/port.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `check=<int>[,<int>,...]` | `<Port ID 1>[<Port ID 2>,...]` | Return the status (1 or 0) of one or more ports numbered `<Port ID 1>`, `<Port ID 2>`, ... `1` = Closed circuit. `0` = Open circuit. |
| `checkactive=<int>` `[,<int>,...]` | `<Port ID 1>[,Port ID 2>,...]` | Return the status (`active` or `inactive`) of one or more ports numbered `<Port ID 1>`, `<Port ID 2>`, ... This value depends on the parameters `Output.Active` for an output and `Input.Trig` for an input.If the port is an output and `Output.Active` is configured as closed, then this request will return active if the port state is closed. The same goes for an input port that has `Input.Trig` configured as closed. |
| `checkdirection=<int>` `[,<int>,...]` | `<Port ID 1>[,<Port ID 2>,...]` | Return the port direction (input or output) of one or more ports numbered `<Port ID 1>`, `<Port ID 2>`,... |
| `monitor=<int>[,<int>,...]` _Outputs and inputs must be monitored separately._ | `<Port ID 1>[,Port ID 2>,...]` | Return a multipart stream of "check" ports (see return description below). Input and output ports must be monitored separately. |
| `action=<string>`  
_Valid for output ports only._ | `[<Port ID>]:<a>[<wait><a>...]` | Activate or deactivate an output. Use the `<wait>` option to activate/deactivate the port for a limited period of time.`<Port ID>` = Port number. If omitted, output 1 is selected.`<a>` = Action character. `/`\=active, `\`\=inactive`<wait>` = Delay before the next action. Unit: milliseconds**Note**: The `:`, `/` and `\` characters must be percent-encoded in the URI. See .**Example**: To set output 1 to active, use `1:/`. In the URI, the action argument becomes `action=1%3A%2F` |

##### Example 1

Retrieve information about port 1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=IOPort.I0"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=IOPort.I0Host: <servername>
```

**Response**

```bash
200 OKContent-Type: text/plainroot.IOPort.I0.Configurable=yesroot.IOPort.I0.Direction=outputroot.IOPort.I0.Input.Name=Input 1root.IOPort.I0.Input.Trig=closedroot.IOPort.I0.Output.Name=Output 1root.IOPort.I0.Output.Active=openroot.IOPort.I0.Output.Button=actinactroot.IOPort.I0.Output.PulseTime=0
```

##### Example 2

Configure port 2 to act as output. This example is only applicable to configurable ports.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&IOPort.I2.Direction=output"
```

```bash
GET /axis-cgi/param.cgi?action=update&IOPort.I2.Direction=outputHost: <servername>
```

##### Example 3

Set port 2 to active, wait 300 ms and then set the port to inactive. Some characters in the action argument `action=2:/300\` must be percent-encoded.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/io/port.cgi?action=2%3A%2F300%5C"
```

```bash
GET /axis-cgi/io/port.cgi?action=2%3A%2F300%5CHost: <servername>
```

#### Successful response, all arguments except `monitor`

```bash
200 OKContent-Type: text/plain<Port ID>=<information>
```

info

The body is empty for the action argument.

#### Successful response, argument `monitor`

```bash
200 OKContent-Type: multipart/x-mixed-replace; boundary=<boundary>--<boundary><monitor data>
```

Where the returned `<monitor data>` is:

```bash
<Port ID><port direction>:<action character>--<boundary><monitor data>
```

Here `<id>` is the port and `<port direction>` is `I` for inputs and `O` for outputs. The `<action character>` is `/` or `H` for active and `\` or `L` for inactive ports. The characters `/` and `\` indicates a change in the state. The characters `H` and `L` indicates that the state is unchanged.

info

Non-empty boundaries are sent when the port status changes. If there are no changes, empty boundaries are sent at 15-second intervals.

### Get application configuration

info

`/axis-cgi/vaconfig.cgi?action=get` is obsolete and should not be used.

Use `/axis-cgi/vaconfig.cgi?action=get` to retrieve the application configuration.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=<name>"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=<name>Host: <servername>
```

with the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `name=<string>` | String | Application name |

#### Error response

```bash
200 OKContent-Type: text/xml<reply result="error">    <script />    <error type="no\_such\_application" message="No application 'hello\_glib' exists" /></reply>
```

For a description of the application configuration, see the API documentation for the application.

For error responses, see [Error responses](#error-responses).

### Modify application configuration

info

`/axis-cgi/vaconfig.cgi?action=modify` is obsolete and should not be used.

Use `/axis-cgi/vaconfig.cgi?action=modify` to modify the application configuration.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=modify&name=<name>"
```

```bash
POST /axis-cgi/vaconfig.cgi?action=modify&name=<name>Host: <servername>
```

with the following query string parameters:

| Argument | Valid values | Description |
| --- | --- | --- |
| `name=<string>` | String | Application name |

##### Example 1

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=<name><config version="1.0">  <application xml configuration></config>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=<name><config version="1.0">  <application xml configuration></config>
```

#### Error response

```bash
200 OKContent-Type: text/xml<reply result="error">    <script />    <error type="no\_such\_application" message="No application 'hello\_glib' exists" /></reply>
```

The XML Schema is available at `http://www.axis.com/vapix/http_cgi/vaconfig/modify_response1.xsd`.

For error responses, see [Error responses](#error-responses).

### List installed applications

info

`/axis-cgi/vaconfig.cgi?action=list` is obsolete and should not be used. Replaced by `/axis-cgi/applications/list.cgi` in [Application API](/vapix/applications/application-api/).

`/axis-cgi/vaconfig.cgi?action=list` lists the installed applications.

#### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=list"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=listHost: <servername>
```

#### Response

```bash
200 OKContent-Type: text/xml<reply result="ok">    <application name="<name>"/>    <application name="<name>"/></reply>
```

XML Schema: `http://www.axis.com/vapix/http_cgi/vaconfig/list1.xsd`.

For error responses, see [Error responses](#error-responses).

### Error responses

If the requested operation cannot be executed, the type of error and an error message will be returned.

```bash
200 OKContent-Type: text/xml<reply result="error">  <error type="<type>" message="<message>"/></reply>
```

| Error type | Description |
| --- | --- |
| `bad_request` | Bad request. The request URL was not formatted correctly. |
| `no_such_application` | There is no application with the given `name`. |
| `internal` | The action could not be performed. This is for example returned if the application fails to restart after a configuration modification. |

## Get RTSP stream with event topic filter

Retrieve an RTSP stream with an event topic filter.

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

```bash
rtsp://<servername>/axis-media/media.amp?<argument>=<value>\[&<argument>=<value>...\]
```

with the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `video` | `0` `1` | Specify whether video should be available in the stream.`0` = no video `1`\= video |
| `event` | `on` `off` | Specify whether event metadata should be available in the stream.`on` = event metadata is included `off` = event metadata is not included |
| `eventtopic` | String | The event topic filter to include.For AXIS Video Motion Detection 3, use `onvif:RuleEngine/axis:VMD3//.`For AXIS Video Motion Detection 2.1 use `onvif:RuleEngine/axis:VideoMotionDetection//motion`For AXIS Digital Autotracking, use `onvif:RuleEngine/axis:DigitalAutotracking/tracking//.`For AXIS Cross Line Detection 1.1, use `onvif:RuleEngine/axis:CrossLineDetection//.` |

For additional arguments, see [Parameter Specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url).