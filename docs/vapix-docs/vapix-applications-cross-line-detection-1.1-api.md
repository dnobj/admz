---
title: Cross line detection 1.1 API
url: "https://developer.axis.com/vapix/applications/cross-line-detection-1.1-api/"
category: vapix
subcategory: applications
sha256: b404adb41f1698ef8ff232d4171c3d496f775bfa26c0ce4939ad824f4fcd524c
scraped_at: "2026-01-09T15:01:07.380Z"
page_height: 11367
---

# Cross line detection 1.1 API

## Description

AXIS Cross Line Detection 1.1 is a trip-wire application which detects moving objects that cross a virtual line. The application can be installed on Axis network video products with support for AXIS Camera Application Platform. The application allows an operator to configure a virtual line in the camera view. The application will monitor this line and detect moving objects that cross the line. When a moving object crosses the line, the event system can be used to trigger actions. A client application can listen to the event data stream to trigger actions from the application.

### Identification

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.10`
-   **Embedded development version**: 1.10 or later
-   **AXIS OS**: 5.40 or later
-   **Software**: AXIS Camera Application Platform (ACAP)

### Dependencies

-   The application is uploaded and controlled using [Application API](/vapix/applications/application-api/).
-   The application is configured using [Application configuration API](/vapix/applications/application-configuration-api/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Check if the Axis product supports AXIS Camera Application Platform.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.EmbeddedDevelopment.Version"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.EmbeddedDevelopment.VersionHost: <servername>
```

Response:

```bash
200 OKContent-Type: text/plainProperties.EmbeddedDevelopment.Version=1.10
```

Upload AXIS Cross Line Detection 1.1.

Request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'file=@CrossLineDetection.eap;type=application/octet-stream' \\  "http://<servername>/axis-cgi/applications/upload.cgi"
```

```bash
POST /axis-cgi/applications/upload.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="file"; filename="CrossLineDetection.eap"Content-Type: application/octet-stream<application package data>--<boundary>--
```

Start the application.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/control.cgi?action=start&package=CrossLineDetection"
```

```bash
GET /axis-cgi/applications/control.cgi?action=start&package=CrossLineDetectionHost: <servername>
```

Retrieve the application configuration.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=CrossLineDetection"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=CrossLineDetectionHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/xml<reply result="ok">    <application name="CrossLineDetection">        <ruleEngine>            <namedObjects>                <namedObject name="CrossLine0">                    <data knownNameType="geometry.segment">                        <segment>                            <point x="-0.5" y="0.0" />                            <point x="0.5" y="0.0" />                        </segment>                    </data>                </namedObject>            </namedObjects>            <rules>                <rule name="crossed\_CrossLine0" function="line\_touching">                    <parameter name="LineObj" value="CrossLine0" />                    <parameter name="Direction" value="both" />                </rule>            </rules>            <scripts>                <script encryption="1">dbgutils.lua</script>                <script encryption="1">lineTouching.lua</script>            </scripts>            <events>                <event name="linetouched">                    <attr key="type" nicename="Touched" value="touched" />                    <attr key="line" nicename="Cross line" />                    <attr key="object" nicename="Passed object id" />                </event>                <event name="timer" hiddenFromTriggerList="true" />            </events>            <moteConfig>                <option name="boundingBox" value="false" />                <option name="polygon" value="true" />                <option name="velocity" value="true" />            </moteConfig>        </ruleEngine>    </application></reply>
```

Modify the application configuration. Only the named object `CrossLine0`(the virtual line) and the `Direction` parameter are modified, all other settings should be kept as is. For more information, see [Application configuration](#application-configuration).

Request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=CrossLineDetection<application name="CrossLineDetection">  <ruleEngine>    <namedObjects>      <namedObject name="CrossLine0">        <data knownNameType="geometry.segment">          <segment>            <point x="-0.5" y="0.0"/>            <point x="0.5" y="0.0"/>          </segment>        </data>      </namedObject>    </namedObjects>    <rules>      <rule name="crossed\_CrossLine0" function="line\_touching">        <parameter name="LineObj" value="CrossLine0"/>        <parameter name="Direction" value="both"/>      </rule>    </rules>    <scripts>      <script encryption="1">dbgutils.lua</script>      <script encryption="1">lineTouching.lua</script>    </scripts>    <events>      <event name="linetouched">        <attr key="type" nicename="Touched" value="touched"/>        <attr key="line" nicename="Cross line"/>        <attr key="object" nicename="Passed object id" />      </event>      <event name="timer" hiddenFromTriggerList="true">    </events>    <moteConfig>      <option name="boundingBox" value="false"/>      <option name="polygon" value="true"/>      <option name="velocity" value="true"/>    </moteConfig>  </ruleEngine></application>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=CrossLineDetection<application name="CrossLineDetection">  <ruleEngine>    <namedObjects>      <namedObject name="CrossLine0">        <data knownNameType="geometry.segment">          <segment>            <point x="-0.5" y="0.0"/>            <point x="0.5" y="0.0"/>          </segment>        </data>      </namedObject>    </namedObjects>    <rules>      <rule name="crossed\_CrossLine0" function="line\_touching">        <parameter name="LineObj" value="CrossLine0"/>        <parameter name="Direction" value="both"/>      </rule>    </rules>    <scripts>      <script encryption="1">dbgutils.lua</script>      <script encryption="1">lineTouching.lua</script>    </scripts>    <events>      <event name="linetouched">        <attr key="type" nicename="Touched" value="touched"/>        <attr key="line" nicename="Cross line"/>        <attr key="object" nicename="Passed object id" />      </event>      <event name="timer" hiddenFromTriggerList="true">    </events>    <moteConfig>      <option name="boundingBox" value="false"/>      <option name="polygon" value="true"/>      <option name="velocity" value="true"/>    </moteConfig>  </ruleEngine></application>
```

Retrieve the RTSP stream with event metadata.

Request:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&video=0&eventtopic=onvif:RuleEngine/axis:CrossLineDetection//.
```

The AXIS Cross Line Detection 1.1 event. The prefix `aev` is a placeholder for the namespace `http://www.axis.com/vapix/ws/event1`

```bash
<tnsaxis:CrossLineDetection aev:NiceName="CrossLineDetection" xmlns:tnsaxis="http://www.axis.com/2009/event/topics">    <linetouched wstop:topic="true" xmlns:wstop="http://docs.oasis-open.org/wsn/t-1">        <aev:MessageInstance>            <aev:SourceInstance>                <aev:SimpleItemInstance aev:NiceName="Touched" Type="xsd:string" Name="type">                    <aev:Value>touched</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance aev:NiceName="Passed object id" Type="xsd:string" Name="object" />                <aev:SimpleItemInstance aev:NiceName="Cross line" Type="xsd:string" Name="line" />            </aev:DataInstance>        </aev:MessageInstance>    </linetouched></tnsaxis:CrossLineDetection>
```

## Application configuration

The application configuration is in XML format. The XML schema is available at [http://www.axis.com/vapix/http\_cgi/](http://www.axis.com/vapix/http_cgi/)

The application defines one named object: The virtual line. The application will detect objects crossing the line in the direction defined by the `Direction` parameter.

The virtual line can be a straight line (1 line segment) or 2 adjoining line segments. The line is defined by 2–3 points describing the line segment end points. The line is drawn from the last point to the first point in the list. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`.

The value of the `Direction` parameter defines the direction in which moving object must cross the line to be detected. Which value to use depends on the order in which the coordinate pairs are listed. See Example 1.

The images below show two virtual lines defined by the same coordinate pairs but with the pairs listed in different order; `x0y0` is the first point in the list and `x2y2` is the last point. The `Direction` parameter is set to `leftright` in both cases. The black arrows show the direction in which moving objects must cross the line to be detected. Note how the arrows are reversed when the order of the coordinate pairs is reversed.

![Moving direction in relation to crossline detection](data:image/png;base64,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)

To modify the application, update the following:

1.  Modify the virtual line (named object `CrossLine0`).
    
2.  Modify the value of the parameter `Direction`.
    
3.  All other settings must be kept as is.
    

```bash
<application name="CrossLineDetection">    <ruleEngine>        <namedObjects>            <namedObject name="CrossLine0">                <data knownNameType="geometry.segment">                    <segment>                        <point x="-0.5" y="0.0" />                        <point x="0.5" y="0.0" />                    </segment>                </data>            </namedObject>        </namedObjects>        <rules>            <rule name="crossed\_CrossLine0" function="line\_touching">                <parameter name="LineObj" value="CrossLine0" />                <parameter name="Direction" value="both" />            </rule>        </rules>        <scripts>            <script encryption="1">dbgutils.lua</script>            <script encryption="1">lineTouching.lua</script>        </scripts>        <events>            <event name="linetouched">                <attr key="type" nicename="Touched" value="touched" />                <attr key="line" nicename="Cross line" />                <attr key="object" nicename="Passed object id" />            </event>            <event name="timer" hiddenFromTriggerList="true" />        </events>        <moteConfig>            <option name="boundingBox" value="false" />            <option name="polygon" value="true" />            <option name="velocity" value="true" />        </moteConfig>    </ruleEngine></application>
```

**XML User Configuration Data Description**

The application is configured by defining the virtual line and the direction in which moving objects should cross the line to be detected.

The XML node semi xpaths not listed here define how the application shall run in AXIS Camera Application Platform. These values must not be changed.

| XML Node Semi XPath | Attribute | Valid values | Description |
| --- | --- | --- | --- |
| `application` | `name` | `CrossLineDetection` | Name of the application. |
| `application/ruleEngine/ namedObjects` |  |  | Section with all named objects used by the application. The application can have one named object. |
| `application/ruleEngine/ namedObjects/namedObject` | `name` | `CrossLine0` | Name of the cross line detection object (the virtual line). |
| `application/ruleEngine/ namedObjects/namedObject/ data` | `knownTypeName` | `geometry.segment` | The supported object type. `geometry.segment` = virtual line consisting of segments |
| `application/ruleEngine/ namedObjects/namedObject/ data/segment` |  | XML node with points | The virtual line consists of 1–2 line segments. The line is defined by 2–3 points describing the line segment end points. The line is drawn from the last point to the first point in the list. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate.The top right corner of the camera view is at `x=1.0` and `y=1.0` |
| `application/ruleEngine/ namedObjects/namedObject/ data/segment/point` | `x` | `-1.0 ... 1.0` | The `x` coordinate. |
|  | `y` | `-1.0 ... 1.0` | The `y` coordinate. |
| `application/ruleEngine/ rules/rule/parameter` | `value` | `CrossLine0` | The parameter value specifying the named object for the `LineObj` parameter. |
| `application/ruleEngine/ rules/rule/parameter` | `value` | `leftright`  
`rightleft`  
`both` | The parameter value specifying in which direction a moving object must cross the virtual line to be detected.  
  
\- `leftright` = from left to right  
\- `rightleft` = from right to left  
\- `both` = both directions  
  
The direction depends on how the line is defined. See Example 1 above. |

## Upload, control and modify the application

To upload and control the application, use the functions in [Application API](/vapix/applications/application-api/). To retrieve the application configuration and to modify settings, use `/axis-cgi/vaconfig.cgi` from [Application configuration API](/vapix/applications/application-configuration-api/).

## Cross line detection 1.1 event declaration

The cross line detection 2.1 event is emitted when a moving object crosses the virtual line.

`type` defines the type of the event. The value `touched` means that the event is emitted when the virtual line was crossed.

`object` is the ID of the virtual line which the moving object has crossed. The ID is an integer and is to used as start event when creating an action rule.

`line` is a string with the coordinates defining the virtual line.

**Topic**

-   **Name**: `tns1:RuleEngine/tnsaxis:CrossLineDetection/tnsaxis:linetouched`
-   **Type**: Stateless
-   **Nice name**: `CrossLineDetection`

**Source instance**

-   **Nice name**: `Touched`
-   **Type**: string
-   **Name**: `type`

| Value | Nice name |
| --- | --- |
| `touched` | — |

**Data instance**

-   **Nice name**: Passed object id
    
-   **Type**: string
    
-   **Name**: `object`
    
-   **Nice name**: Cross line
    
-   **Type**: string
    
-   **Name**: `line`