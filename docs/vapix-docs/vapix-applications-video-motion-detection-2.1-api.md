---
title: Video motion detection 2.1 API
url: "https://developer.axis.com/vapix/applications/video-motion-detection-2.1-api/"
category: vapix
subcategory: applications
sha256: 1fe3c51163824bea1f42f41e0565c5e290b7ed4ec7a82f9d823b56b2a7878e25
scraped_at: "2026-01-09T15:01:28.279Z"
page_height: 11237
---

# Video motion detection 2.1 API

info

This API has been deprecated and will no longer receive updates. For a newer version, see [Video motion detection 4 API](/vapix/applications/video-motion-detection-4-api/).

## Description

AXIS Video Motion Detection 2.1 is an application that detects moving objects within an area of interest. The application can be installed on Axis network video products with support for AXIS Camera Application Platform. The application allows an operator to configure a polygon in the camera view to define an area of interest. The application will monitor this area and detect moving objects within its boundaries. When a moving object is detected, the event system can be used to trigger actions. A client application can listen to the event data stream to trigger actions from the application.

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
### Check if the Axis product supports AXIS Camera Application Platform

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
Properties.EmbeddedDevelopment.Version=1.10
```

### Upload AXIS Video Motion Detection 2.1

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'file=@AXISVideoMotionDetection.eap;type=application/octet-stream' \\  "http://<servername>/axis-cgi/applications/upload.cgi"
```

```bash
POST /axis-cgi/applications/upload.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="file"; filename="AXISVideoMotionDetection.eap"Content-Type: application/octet-stream<application package data>--<boundary>--
```

Start the application.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/control.cgi?action=start&package=VideoMotionDetection"
```

```bash
GET /axis-cgi/applications/control.cgi?action=start&package=VideoMotionDetectionHost: <servername>
```

Retrieve the application configuration.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=VideoMotionDetection"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=VideoMotionDetectionHost: <servername>
```

Response:

```bash
<reply result="ok">    <config version="1.0">        <application name="VideoMotionDetection">            <ruleEngine>                <namedObjects>                    <namedObject name="Detection Area">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.60" y="0.60" />                                <point x="0.60" y="-0.60" />                                <point x="-0.60" y="-0.60" />                                <point x="-0.60" y="0.60" />                            </polygon>                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="detection\_0" function="monitor\_area">                        <parameter name="Include" value="Detection Area" />                    </rule>                </rules>                <scripts>                    <script encryption="1">detection.lua</script>                </scripts>                <events>                    <event name="motion">                        <attr key="areaid" nicename="Area ID" tag="source" value="0" />                        <attr key="areapolygon" nicename="Polygon info" tag="data" />                        <attr key="active" nicename="Motion detected" tag="property-state" />                    </event>                </events>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>            </ruleEngine>        </application>    </config></reply>
```

Modify the application configuration. Only the named object `Detection Area` (the area of interest) is modified, all other settings should be kept as is. If required, an exclude area can also be defined, see [Application configuration](#application-configuration).

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=VideoMotionDetection<config version="1.0">  <application name="VideoMotionDetection">    <ruleEngine>      <namedObjects>        <namedObject name="Detection Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.60" y="0.60"/>              <point x="0.60" y="-0.60"/>              <point x="-0.60" y="-0.60"/>              <point x="-0.60" y="0.60"/>            </polygon>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="detection\_0" function="monitor\_area">          <parameter name="Include" value="Detection Area"/>        </rule>      </rules>      <scripts>        <script encryption="1">detection.lua</script>      </scripts>      <events>        <event name="motion">          <attr key="areaid" nicename="Area ID" tag="source" value="0"/>          <attr key="areapolygon" nicename="Polygon info" tag="data"/>          <attr key="active" nicename="Motion detected" tag="property-state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>    </ruleEngine>  </application></config>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=VideoMotionDetection<config version="1.0">  <application name="VideoMotionDetection">    <ruleEngine>      <namedObjects>        <namedObject name="Detection Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.60" y="0.60"/>              <point x="0.60" y="-0.60"/>              <point x="-0.60" y="-0.60"/>              <point x="-0.60" y="0.60"/>            </polygon>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="detection\_0" function="monitor\_area">          <parameter name="Include" value="Detection Area"/>        </rule>      </rules>      <scripts>        <script encryption="1">detection.lua</script>      </scripts>      <events>        <event name="motion">          <attr key="areaid" nicename="Area ID" tag="source" value="0"/>          <attr key="areapolygon" nicename="Polygon info" tag="data"/>          <attr key="active" nicename="Motion detected" tag="property-state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>    </ruleEngine>  </application></config>
```

Retrieve the RTSP stream with event metadata.

```bash
rtsp://<servername>/axis-media/media.amp?event=on&video=0&eventtopic=onvif:RuleEngine/axis:VideoMotionDetection//motion
```

The AXIS Video Motion Detection 2.1 event. The prefix `aev` is a placeholder for the namespace `http://www.axis.com/vapix/ws/event1`

```bash
<tnsaxis:VideoMotionDetection aev:NiceName="VideoMotionDetection" xmlns:tnsaxis="http://www.axis.com/2009/event/topics">    <motion wstop:topic="true" xmlns:wstop="http://docs.oasis-open.org/wsn/t-1">        <aev:MessageInstance aev:isProperty="true">            <aev:SourceInstance>                <aev:SimpleItemInstance aev:NiceName="Area ID" Type="xsd:string" Name="areaid">                    <aev:Value>0</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance aev:NiceName="Polygon info" Type="xsd:string" Name="areapolygon" />                <aev:SimpleItemInstance                    aev:NiceName="Motion detected"                    Type="xsd:boolean"                    Name="active"                    isPropertyState="true" />            </aev:DataInstance>        </aev:MessageInstance>    </motion></tnsaxis:VideoMotionDetection>
```

## Application configuration

The application configuration is in XML format. The XML schema is available at [http://www.axis.com/vapix/http\_cgi/](http://www.axis.com/vapix/http_cgi/).

The application defines two named objects: The area of interest (required) and the exclude area (optional). The application will detect objects moving inside the area of interest. The exclude area is an area inside the area of interest in which moving objects are ignored.

The area of interest and the exclude area are polygons defined by 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`.

To modify the application, update the following:

1.  Modify the area of interest (named object `Detection Area`).
2.  Optionally, add an exclude area (named object `Exclude Area`).
3.  If using an exclude area, add the parameter `Exclude`.
4.  All other settings must be kept as is.

```bash
<config version="1.0">  <application name="VideoMotionDetection">    <ruleEngine>      <namedObjects>        <namedObject name="Detection Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.60" y="0.60"/>              <point x="0.60" y="-0.60"/>              <point x="-0.60" y="-0.60"/>              <point x="-0.60" y="0.60"/>            </polygon>          </data>        </namedObject>        <namedObject name="Exclude Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.50" y="-0.20"/>              <point x="-0.50" y="-0.20"/>              <point x="-0.50" y="0.20"/>              <point x="0.50" y="0.20"/>            </polygon>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="detection\_0" function="monitor\_area">          <parameter name="Include" value="Detection Area"/>          <parameter name="Exclude" value="Exclude Area"/>        </rule>      </rules>      <scripts>        <script encryption="1">detection.lua</script>      </scripts>      <events>        <event name="motion">          <attr key="areaid" nicename="Area ID" tag="source" value="0"/>          <attr key="areapolygon" nicename="Polygon info" tag="data"/>          <attr key="active" nicename="Motion detected" tag="property-state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>    </ruleEngine>  </application></config>
```

**XML user configuration data description**

The application is configured by defining the area of interest and the exclude area as named objects.

The XML node semi xpaths not listed here define how the application shall run in AXIS Camera Application Platform. These values must not be changed.

| XML Node Semi XPath | Attribute | Valid values | Description |
| --- | --- | --- | --- |
| `application` | `name` | `VideoMotionDetection` | Name of the application. |
| `application/ruleEngine/ namedObjects` |  | Section with all named objects used by the application. The application can have two objects:  
\- Area of interest (Required)  
\- Exclude area (Optional) |  |
| `application/ruleEngine/ namedObjects/namedObject` | `name` | `Detection Area` `Exclude Area` | Name of the video motion detection object.`Detection Area` = Area of interest `Exclude Area` = Exclude area |
| `application/ruleEngine/ namedObjects/namedObject/data` | `knownTypeName` | `geometry.polygon` | The supported object type. `geometry.polygon` = polygon |
| `application/ruleEngine/ namedObjects/namedObject/data/polygon` |  | XML node with points | The polygon is defined by 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate.The top right corner of the camera view is at `x=1.0` and `y=1.0` |
| `application/ruleEngine/ namedObjects/namedObject/data/polygon/point` | `x` | `-1.0 ... 1.0` | The `x` coordinate. |
|  | `y` | `-1.0 ... 1.0` | The `y` coordinate. |
| `application/ruleEngine/ rules/rule/parameter` | `value` | `Detection Area` | The parameter value specifying the named object for the `Include` parameter. |
|  |  | `Exclude Area` | The parameter value specifying the named object for the `Exclude` parameter. |
| `application/ruleEngine/ rules/rule/parameter` | `name` | `Include` | The parameter that specifies the area of interest. |
|  |  | `Exclude` | Optional. The parameter that specifies the exclude area. |

## Upload, control and modify the application

To upload and control the application, use the functions in [Application API](/vapix/applications/application-api/). To retrieve the application configuration and to modify settings, use `/axis-cgi/vaconfig.cgi` from [Application configuration API](/vapix/applications/application-configuration-api/).

## Video motion detection 2.1 event declaration

The AXIS Video Motion Detection 2.1 event is `true` when motion is detected in the area of interest.

`areaid` is the Area ID defining the area of interest.

`areapolygon` is a string with the coordinates defining the area of interest.

`active` is `true` if the application has detected motion in the area of interest.

**Topic**

-   **Name**: `tns1:RuleEngine/tnsaxis:VideoMotionDetection/tnsaxis:motion`
-   **Type**: Stateful
-   **Nice name**: `VideoMotionDetection`

**Source instance**

-   **Nice name**: `Area ID`
-   **Type**: string
-   **Name**: `areaid`

| Value | Nice name |
| --- | --- |
| `0` | — |

**Data instance**

-   **Nice name**: Polygon info
    
-   **Type**: string
    
-   **Name**: `areapolygon`
    
-   Nice name
    
    Motion detected
    
-   Type
    
    boolean
    
-   Name
    
    `active`
    
-   isPropertyState
    
    true