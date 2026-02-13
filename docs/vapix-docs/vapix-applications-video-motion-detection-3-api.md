---
title: Video motion detection 3 API
url: "https://developer.axis.com/vapix/applications/video-motion-detection-3-api/"
category: vapix
subcategory: applications
sha256: f86b2719a2f2f5eb651b6493f3d7539a5f559867018c5331859eae2a0d98a066
scraped_at: "2026-01-09T15:01:30.372Z"
page_height: 26258
---

# Video motion detection 3 API

info

This API has been deprecated and will no longer receive updates. For a newer version, see [Video motion detection 4 API](/vapix/applications/video-motion-detection-4-api/).

## Description

AXIS Video Motion Detection 3 is an AXIS Camera Application Platform (ACAP) application that detects moving objects in the camera’s field of view. When a moving object is detected, AXIS Video Motion Detection 3 sends an alarm (event). A client application that listens to events from AXIS Video Motion Detection 3 can use the event to, for example, record video or send a notification.

AXIS Video Motion Detection 3 is preinstalled in products with AXIS OS 5.80 and later but must be started before it can be used. In products with older AXIS OS, the application must first be uploaded and then started. The application can be configured by modifying the include area and, optionally, exclude areas and ignore filters. Include and exclude areas define the parts of the scene in which moving objects should be detected. Ignore filters are used to avoid detecting objects such as shadows of swaying trees, lights from passing cars and small animals regardless of where in the scene the objects appear.

When there are moving objects in the camera’s field of view, the application tests the object’s position, size and movements against the include area, exclude areas and filter conditions to determine if the object should be reported as detected or ignored. If the object is reported as detected, an event is emitted.

When using ignore filters, events will not be emitted until the filter conditions have been tested. For example, when using the `Time` parameter (short-lived object filter), events will be sent if the object is still moving when the set time has passed. That is, all events will be delayed by the set time. If the event is used to start a recording, it is recommended to configure the pre-trigger time in the recording setup so that the recording also includes the time the object moved in the scene before being detected.

When the application is configured using the Axis product webpages, visual confirmation can be used to help understand the effect of the different filters. When visual confirmation is enabled, colored polygons show which objects the application detects and which objects the application ignores.

### Identification

AXIS Video Motion Detection 3 is preinstalled in Axis network video products with AXIS OS 5.80 and later. Use `/axis-cgi/applications/list.cgi` to list applications.

AXIS Video Motion Detection 3 can be uploaded to Axis network video products with:

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.40` or later
-   **Embedded development version**: 1.40 or later
-   **Software**: AXIS Camera Application Platform (ACAP)
-   **Product category**: Axis network cameras and video encoders. Intended for fixed cameras.

Multiple `ruleEngine` elements are supported if:

-   **Property**: `Properties.EmbeddedDevelopment.RuleEngine.MultiConfiguration=yes`

### Dependencies

-   The application is uploaded and controlled using [Application API](/vapix/applications/application-api/).
-   The application is configured using [Application configuration API](/vapix/applications/application-configuration-api/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

List installed applications. Video motion detection 3 is preinstalled in products with AXIS OS 5.80 and later.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/list.cgi"
```

```bash
GET /axis-cgi/applications/list.cgiHost: <servername>
```

Response:

```bash
<reply result="ok">    <application        name="VMD3"        NiceName="Video Motion Detection"        Vendor="Axis Communications"        Version="3.1-0"        ApplicationID="46396"        License="None"        Status="Stopped"        ConfigurationPage="local/VMD3/setup.html" /></reply>
```

Check if the Axis product supports AXIS Camera Application Platform. AXIS Video Motion Detection 3 is compatible with version 1.40 and later.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&responseformat=rfc&group=Properties.EmbeddedDevelopment.Version"
```

```bash
GET /axis-cgi/param.cgi?action=list&responseformat=rfc&group=Properties.EmbeddedDevelopment.VersionHost: <servername>
```

Response:

```bash
Properties.EmbeddedDevelopment.Version=1.40
```

Upload AXIS Video Motion Detection 3.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'file=@VideoMotionDetection3.eap;type=application/octet-stream' \\  "http://<servername>/axis-cgi/applications/upload.cgi"
```

```bash
POST /axis-cgi/applications/upload.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="file"; filename="VideoMotionDetection3.eap"Content-Type: application/octet-stream<application package data>--<boundary>--
```

Start the application.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/control.cgi?action=start&package=VideoMotionDetection3"
```

```bash
GET /axis-cgi/applications/control.cgi?action=start&package=VideoMotionDetection3Host: <servername>
```

Retrieve the application configuration.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=VideoMotionDetection3"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=VideoMotionDetection3Host: <servername>
```

Response:

```bash
<reply result="ok">    <config version="2.0">        <application name="VMD3" nicename="Video Motion Detection 3">            <ruleEngines>                <ruleEngine status="enabled">                    <namedObjects>                        <namedObject name="Detection Area">                            <data knownNameType="geometry.polygon">                                <polygon>                                    <point x="0.97" y="0.97" />                                    <point x="0.97" y="-0.97" />                                    <point x="-0.97" y="-0.97" />                                    <point x="-0.97" y="0.97" />                                </polygon>                            </data>                        </namedObject>                        <namedObject name="Object Duration">                            <data knownNameType="core.int">                                <int value="0" />                            </data>                        </namedObject>                        <namedObject name="Object Height">                            <data knownNameType="core.int">                                <int value="20" />                            </data>                        </namedObject>                        <namedObject name="Object Width">                            <data knownNameType="core.int">                                <int value="10" />                            </data>                        </namedObject>                        <namedObject name="Traveled Distance">                            <data knownNameType="core.int">                                <int value="0" />                            </data>                        </namedObject>                        <namedObject name="Visual Duration">                            <data knownNameType="core.int">                                <int value="0" />                            </data>                        </namedObject>                    </namedObjects>                    <rules>                        <rule name="detection\_0" function="guardIncludeArea">                            <parameter name="IncludeArea" value="Detection Area" />                            <parameter name="Time" value="Object Duration" />                            <parameter name="Width" value="Object Width" />                            <parameter name="Height" value="Object Height" />                            <parameter name="Distance" value="Traveled Distance" />                            <parameter name="Duration" value="Visual Duration" />                        </rule>                    </rules>                    <scripts>                        <script encryption="1">combined.lua</script>                    </scripts>                    <events>                        <event name="vmd3\_video\_1" nicename="VMD 3">                            <attr key="areaid" nicename="Area ID" tag="source" value="0" />                            <attr key="areapolygon" nicename="Polygon info" tag="data" />                            <attr key="active" nicename="Active" tag="property-state" />                        </event>                    </events>                    <analyticSources>                        <analyticSource name="imageSource" value="1" />                    </analyticSources>                    <moteConfig>                        <option name="boundingBox" value="false" />                        <option name="polygon" value="true" />                        <option name="velocity" value="true" />                    </moteConfig>                    <libraries>                        <library name="system" />                    </libraries>                </ruleEngine>            </ruleEngines>        </application>    </config></reply>
```

Modify the application configuration. It is possible to modify the size of the include area, to add and configure exclude areas and to modify filter values. All other settings should be kept as is. If changing the name of a named object, the corresponding parameter value must also be changed to match the new name. For more information, see [Application configuration](#application-configuration).

In this example, an exclude area is added by adding the named object `Exclude Area 0` and the corresponding parameter `ExcludeArea0`.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=VideoMotionDetection3<config version="2.0">  <application name="VMD3" nicename="Video Motion Detection 3">    <ruleEngines>      <ruleEngine status="enabled">        <namedObjects>          <namedObject name="Detection Area">            <data knownNameType="geometry.polygon">              <polygon>                <point x="0.97" y="0.97"/>                <point x="0.97" y="-0.97"/>                <point x="-0.97" y="-0.97"/>                <point x="-0.97" y="0.97"/>              </polygon>            </data>          </namedObject>          <namedObject name="Exclude Area 0">            <data knownNameType="geometry.polygon">              <polygon>                <point x="0.20" y="0.20"/>                <point x="0.20" y="-0.20"/>                <point x="-0.20" y="-0.20"/>                <point x="-0.20" y="0.20"/>              </polygon>            </data>          </namedObject>          <namedObject name="Object Duration">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>          <namedObject name="Object Height">            <data knownNameType="core.int">              <int value="20"/>            </data>          </namedObject>          <namedObject name="Object Width">            <data knownNameType="core.int">              <int value="10"/>            </data>          </namedObject>          <namedObject name="Traveled Distance">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>          <namedObject name="Visual Duration">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>        </namedObjects>        <rules>          <rule name="detection\_0" function="guardIncludeArea">            <parameter name="IncludeArea" value="Detection Area"/>            <parameter name="ExcludeArea0" value="Exclude Area 0"/>            <parameter name="Time" value="Object Duration"/>            <parameter name="Width" value="Object Width"/>            <parameter name="Height" value="Object Height"/>            <parameter name="Distance" value="Traveled Distance"/>            <parameter name="Duration" value="Visual Duration"/>          </rule>        </rules>        <scripts>          <script encryption="1">combined.lua</script>        </scripts>        <events>          <event name="vmd3\_video\_1" nicename="VMD 3">            <attr key="areaid" nicename="Area ID" tag="source" value="0"/>            <attr key="areapolygon" nicename="Polygon info" tag="data"/>            <attr key="active" nicename="Active" tag="property-state"/>          </event>        </events>        <analyticSources>          <analyticSource name="imageSource" value="1"/>        </analyticSources>        <moteConfig>          <option name="boundingBox" value="false"/>          <option name="polygon" value="true"/>          <option name="velocity" value="true"/>        </moteConfig>        <libraries>          <library name="system"/>        </libraries>      </ruleEngine>    </ruleEngines>  </application></config>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=VideoMotionDetection3<config version="2.0">  <application name="VMD3" nicename="Video Motion Detection 3">    <ruleEngines>      <ruleEngine status="enabled">        <namedObjects>          <namedObject name="Detection Area">            <data knownNameType="geometry.polygon">              <polygon>                <point x="0.97" y="0.97"/>                <point x="0.97" y="-0.97"/>                <point x="-0.97" y="-0.97"/>                <point x="-0.97" y="0.97"/>              </polygon>            </data>          </namedObject>          <namedObject name="Exclude Area 0">            <data knownNameType="geometry.polygon">              <polygon>                <point x="0.20" y="0.20"/>                <point x="0.20" y="-0.20"/>                <point x="-0.20" y="-0.20"/>                <point x="-0.20" y="0.20"/>              </polygon>            </data>          </namedObject>          <namedObject name="Object Duration">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>          <namedObject name="Object Height">            <data knownNameType="core.int">              <int value="20"/>            </data>          </namedObject>          <namedObject name="Object Width">            <data knownNameType="core.int">              <int value="10"/>            </data>          </namedObject>          <namedObject name="Traveled Distance">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>          <namedObject name="Visual Duration">            <data knownNameType="core.int">              <int value="0"/>            </data>          </namedObject>        </namedObjects>        <rules>          <rule name="detection\_0" function="guardIncludeArea">            <parameter name="IncludeArea" value="Detection Area"/>            <parameter name="ExcludeArea0" value="Exclude Area 0"/>            <parameter name="Time" value="Object Duration"/>            <parameter name="Width" value="Object Width"/>            <parameter name="Height" value="Object Height"/>            <parameter name="Distance" value="Traveled Distance"/>            <parameter name="Duration" value="Visual Duration"/>          </rule>        </rules>        <scripts>          <script encryption="1">combined.lua</script>        </scripts>        <events>          <event name="vmd3\_video\_1" nicename="VMD 3">            <attr key="areaid" nicename="Area ID" tag="source" value="0"/>            <attr key="areapolygon" nicename="Polygon info" tag="data"/>            <attr key="active" nicename="Active" tag="property-state"/>          </event>        </events>        <analyticSources>          <analyticSource name="imageSource" value="1"/>        </analyticSources>        <moteConfig>          <option name="boundingBox" value="false"/>          <option name="polygon" value="true"/>          <option name="velocity" value="true"/>        </moteConfig>        <libraries>          <library name="system"/>        </libraries>      </ruleEngine>    </ruleEngines>  </application></config>
```

Retrieve an RTSP stream with event metadata.

```bash
rtsp://<servername>/axis-media/media.amp?event=on&video=0&eventtopic=onvif:RuleEngine/axis:VMD3/vmd3\_video\_1//.
```

The AXIS Video Motion Detection 3 event in the event stream.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tns1:RuleEnginge/tnsaxis:VMD3/vmd3\_video\_1            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://daf20c8-c41f-11e0-8c89-00408cb96106/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2014-03-07T13:44:34.112703Z" PropertyOperation="Changed">                    <tt:Source>                        <tt:SimpleItem Name="areaid" Value="0" />                    </tt:Source>                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem                            Name="areapolygon"                            Value="0.97,0.97 0.97,-0.97 -0.97,-0.97 -0.97,0.97 0.97,0.97" />                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

For information about the event declaration, see [Video motion detection 3 event declaration](#video-motion-detection-3-event-declaration). Use `GetEventInstances` from VAPIX® Event and Action Services to list event declarations.

## Application configuration

The application configuration is an XML structure with named objects and a rule. The named objects define the include area, exclude areas and ignore filters. In the rule, the named objects are used as parameter values. If using exclude areas, the rule must be updated with one parameter for each exclude area.

The following types of named objects can be configured:

-   Include area. See [Include area](#include-area).
-   (Optional) Exclude areas. See [Exclude areas](#exclude-areas).
-   Traveled distance. See [Swaying object filter](#swaying-object-filter).
-   Object duration. See [Short lived object filter](#short-lived-object-filter).
-   Object width and object height. See [Small object filter](#small-object-filter).

For information about how to configure multichannel products, see [Multichannel products](#multichannel-products).

Example configuration:

```bash
<config version="2.0">    <application name="VMD3" nicename="Video Motion Detection 3">        <ruleEngines>            <ruleEngine status="enabled">                <namedObjects>                    <namedObject name="Detection Area">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.97" y="0.97" />                                <point x="0.97" y="-0.97" />                                <point x="-0.97" y="-0.97" />                                <point x="-0.97" y="0.97" />                            </polygon>                        </data>                    </namedObject>                    <namedObject name="Object Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Object Height">                        <data knownNameType="core.int">                            <int value="20" />                        </data>                    </namedObject>                    <namedObject name="Object Width">                        <data knownNameType="core.int">                            <int value="10" />                        </data>                    </namedObject>                    <namedObject name="Traveled Distance">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Visual Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="detection\_0" function="guardIncludeArea">                        <parameter name="IncludeArea" value="Detection Area" />                        <parameter name="Time" value="Object Duration" />                        <parameter name="Width" value="Object Width" />                        <parameter name="Height" value="Object Height" />                        <parameter name="Distance" value="Traveled Distance" />                        <parameter name="Duration" value="Visual Duration" />                    </rule>                </rules>                <scripts>                    <script encryption="1">combined.lua</script>                </scripts>                <events>                    <event name="vmd3\_video\_1" nicename="VMD 3">                        <attr key="areaid" nicename="Area ID" tag="source" value="0" />                        <attr key="areapolygon" nicename="Polygon info" tag="data" />                        <attr key="active" nicename="Active" tag="property-state" />                    </event>                </events>                <analyticSources>                    <analyticSource name="imageSource" value="1" />                </analyticSources>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>                <libraries>                    <library name="system" />                </libraries>            </ruleEngine>        </ruleEngines>    </application></config>
```

The table below lists the XML elements and attributes used to define named objects and rules. The elements not listed in the table define how the application shall run in AXIS Camera Application Platform and must not be changed.

| XML element | Attribute | Value values | Description |
| --- | --- | --- | --- |
| `application` | `name` | `VMD3` | Contains the application configuration. Attribute `name` is the name of the application. |
| `ruleEngines` |  |  | Contains one or more `ruleEngine`. |
| `ruleEngine` | `status` | `enabled` `disabled` | Contains the application configuration for one video channel. For multichannel products, use one `ruleEngine` for each channel, see [Multichannel products](#multichannel-products).Attribute `status` is the status of the `ruleEngine` configuration. This attribute is AXIS OS dependent and supported from AXIS OS version 5.61 and later.`enabled` = Enabled. Configuration will be parsed by the AXIS OS.`disabled` = Disabled. Configuration will not be parsed by the AXIS OS. |
| `namedObjects` |  |  | Contains all named objects used by the application. |
| `namedObject` | `name` | String | A named objects.Attribute `name` is the name of the named object. Any name can be used.The name used here should also be used as value for element `parameter`’s attribute `value`. |
| `data` | `knownTypeName` | `core.int` `geometry.polygon` | Contains data for the named object.Attribute `knownType` specifies the type of data.`core.int` = Integer. Use for the filters.`geometry.polygon` = Polygon. Use for include and exclude areas. |
| `polygon` |  | `point` | Include and exclude areas: Contains `point` elements that describe the exclude area polygon. The polygon is defined by 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate.The top right corner of the camera view is at `x=1.0` and `y=1.0` |
| `point` | `x` | `-1.0 ... 1.0` | Attribute `x` is the `x` coordinate. |
|  | `y` | `-1.0 ... 1.0` | Attribute `y` is the `y` coordinate. |
| `int` | `value` | Integer | An integer defining the filter value.For information about the different filters, see [Swaying object filter](#swaying-object-filter), [Short lived object filter](#short-lived-object-filter), and [Small object filter](#small-object-filter). |
| `rules` |  |  | Contains parameters for the application rule. |
| `parameter` |  |  | Application parameter. Each named object must have a corresponding parameter.Attribute `name` must have one of values listed below.Attribute `value` specifies which named object to use for the parameter. |
|  | `name` | `IncludeArea` | Parameter specifying which named object to use for the include area.See [Include area](#include-area). |
|  |  | `Time` | Parameter specifying which named object to use for the short-lived object filter.See [Short lived object filter](#short-lived-object-filter). |
|  |  | `Height` | Parameter specifying which named object to use for the height in the small object filter.See [Small object filter](#small-object-filter). |
|  |  | `Width` | Parameter specifying which named object to use for width in the small object filter.See [Small object filter](#small-object-filter). |
|  |  | `Distance` | Parameter specifying which named object to use for the swaying object filter.See [Swaying object filter](#swaying-object-filter). |
|  |  | `ExcludeArea0` `ExcludeArea1` `...` `ExcludeArea9` | Optional. Parameters specifying which the named objects to use for the exclude areas. Use one parameter for each exclude area.See [Exclude areas](#exclude-areas). |
|  |  | `Duration` | Internal parameter. |
|  | `value` | String | Parameter value. The value should be the same as the `name` attribute of the corresponding `namedObject`. |

### Include area

The include area is the area in which moving objects will be detected. Objects moving outside the include area will be ignored.

In the application configuration, the include area is a named object.

```bash
<namedObject name="Detection Area">    <data knownNameType="geometry.polygon">        <polygon>            <point x="0.97" y="0.97" />            <point x="0.97" y="-0.97" />            <point x="-0.97" y="-0.97" />            <point x="-0.97" y="0.97" />        </polygon>    </data></namedObject>
```

The include area is set up as a polygon with 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`. The bottom left corner is at `x=-1.0` and `y=-1.0`.

info

If the video stream is rotated, the coordinates of the unrotated video stream should be used when configuring the application.

In the rule, the include area named object is used by the `IncludeArea` parameter.

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />    </rule></rules>
```

### Exclude areas

An exclude area is an area in which moving objects are ignored. Exclude areas are optional. Up to 10 exclude areas can be used.

In the application configuration, each exclude area is a named object.

```bash
<namedObject name="Exclude Area 0">    <data knownNameType="geometry.polygon">        <polygon>            <point x="0.20" y="0.20" />            <point x="0.20" y="-0.20" />            <point x="-0.20" y="-0.20" />            <point x="-0.20" y="0.20" />        </polygon>    </data></namedObject>
```

The exclude area is set up as a polygon with 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`. The bottom left corner is at `x=-1.0` and `y=-1.0`.

info

If the video stream is rotated, the coordinates of the unrotated video stream should be used when configuring the application.

When using exclude areas, the rule must be updated with one parameter for each exclude area. The parameter is called `ExcludeArea#` where `#` is an index starting from `0`.

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="ExcludeArea0" value="Exclude Area 0" />        <parameter name="ExcludeArea1" value="Exclude Area 1" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />    </rule></rules>
```

### Swaying object filter

The swaying object filter is used to avoid detecting objects that only move a short distance, for example moving trees, flags and their shadows. If the swaying objects in the scene are large, for example large ponds or large trees, it is recommended to use exclude areas instead of the filter. The filter will be applied to all moving objects in scene and, if set to a value too large, important objects might not be detected.

When the swaying object filter is enabled and the application finds a moving object, the object will not be reported as detected until it has travelled a distance larger than the set filter size. The event emitted by the application will be emitted when the object is detected. If the event is used to start a recording, configure the pre-trigger time so that the recording also includes the time the object moved in the scene before being detected.

In the application configuration, the swaying object filter is the named object used by the `Distance` parameter. The filter size is an integer between `10` and `100`. The value `100` implies that an object must travel from its initial from to one third of the image width or height before being detected. The value `50` implies half that distance, that is, the object must travel a distance one sixth of the image width or height before being detected. To disable the filter, use `0` or a negative integer.

```bash
<namedObject name="Traveled Distance">    <data knownNameType="core.int">        <int value="0" />    </data></namedObject>
```

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />    </rule></rules>
```

### Short lived object filter

The short-lived object filter is used to avoid detecting objects that only appear for a short period of time, such as light beams from a passing car and quickly moving shadows. When the short-lived object filter is enabled and the application finds a moving object, the object will not be reported as detected until the set time as passed. The event emitted by the application will be emitted when the object is detected. If the event is used to start a recording, configure the pre-trigger time so that the recording also includes the time the object moved in the scene before being detected.

In the application configuration, the short-lived object filter is the named object used by the `Time` parameter. The filter size is an integer that specifies the number of seconds to wait before emitting the event. To disable the filter, use `0` or a negative integer.

```bash
<namedObject name="Object Duration">    <data knownNameType="core.int">        <int value="0" />    </data></namedObject>
```

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />    </rule></rules>
```

### Small object filter

The small object filter is used to avoid detecting objects that are too small. For example, if only moving cars should be detected, the small object filter can be used to avoid detecting people and animals. When using the small object filter, take into consideration that an object far from the camera appears smaller than an object close to the camera.

The filter is defined by specifying the maximum width and maximum height of the objects to ignore. To be ignored, the object must be smaller than the set width and by the set height.

In the application configuration, the small object filter is the named objects used by the `Height` and `Width` parameters. Each filter’s size can be set to an integer between `5` and `100` and is the maximum object width or height measured in percent of the image width or height. To disable the filters, use `0` or a negative integer.

info

The small object filter is defined using the unrotated video stream. Width and height will be interchanged if the image is rotated 90 or 270 degrees, for example for cameras that support autorotation and that are mounted at a 90 or 270 degree angle. If the image is rotated 90 or 270 degrees, the object height should be entered as Width and vice versa when the application is configured through the API. The application webpage takes image rotation into account and displays height as width if the image is rotated.

```bash
<namedObject name="Object Width">  <data knownNameType="core.int">    <int value="20"/>  </data></namedObject><namedObject name="Object Height">  <data knownNameType="core.int">    <int value="10"/>  </data></namedObject>
```

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />    </rule></rules>
```

### Multichannel products

For multichannel products, the application can be used on all channels simultaneously.

In the application configuration, there is one `ruleEngine` for each channel. Attribute `status` determines if the application is enabled or disabled on that channel.

info

Multiple ruleEngine elements are supported if Properties.EmbeddedDevelopment.RuleEngine.MultiConfiguration=yes.

The following parts in `ruleEngine` control channel-specific settings:

```bash
<rules>    <rule name="detection\_0" function="guardIncludeArea">        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="Distance" value="Traveled Distance" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Channel" value="1" />    </rule></rules>
```

```bash
<event name="vmd3\_video\_1" nicename="VMD 3: Video 1">    <attr key="areaid" nicename="Area ID" tag="source" value="0" />    <attr key="areapolygon" nicename="Polygon info" tag="data" />    <attr key="active" nicename="Active" tag="property-state" /></event>
```

```bash
<analyticSources>    <analyticSource name="imageSource" value="1" /></analyticSources>
```

Element `<analyticSource>` specifies the video channel used for detection. Parameter `Channel` specifies the video channel used for sending events. These are normally set to the same value. Event names are different for different channels.

The number of supported video channels is defined by parameter `root.ImageSource.NbrOfSources`.

Example configuration with two channels:

```bash
<config version="2.0">    <application name="VMD3" nicename="Video Motion Detection 3">        <ruleEngines>            <ruleEngine status="enabled">                <namedObjects>                    <namedObject name="Detection Area">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.97" y="0.97" />                                <point x="0.97" y="-0.97" />                                <point x="-0.97" y="-0.97" />                                <point x="-0.97" y="0.97" />                            </polygon>                        </data>                    </namedObject>                    <namedObject name="Object Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Object Height">                        <data knownNameType="core.int">                            <int value="20" />                        </data>                    </namedObject>                    <namedObject name="Object Width">                        <data knownNameType="core.int">                            <int value="10" />                        </data>                    </namedObject>                    <namedObject name="Traveled Distance">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Visual Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="detection\_0" function="guardIncludeArea">                        <parameter name="IncludeArea" value="Detection Area" />                        <parameter name="Time" value="Object Duration" />                        <parameter name="Width" value="Object Width" />                        <parameter name="Height" value="Object Height" />                        <parameter name="Distance" value="Traveled Distance" />                        <parameter name="Duration" value="Visual Duration" />                        <parameter name="Channel" value="1" />                    </rule>                </rules>                <scripts>                    <script encryption="1">combined.lua</script>                </scripts>                <events>                    <event name="vmd3\_video\_1" nicename="VMD 3: Video 1">                        <attr key="areaid" nicename="Area ID" tag="source" value="0" />                        <attr key="areapolygon" nicename="Polygon info" tag="data" />                        <attr key="active" nicename="Active" tag="property-state" />                    </event>                </events>                <analyticSources>                    <analyticSource name="imageSource" value="1" />                </analyticSources>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>                <libraries>                    <library name="system" />                </libraries>            </ruleEngine>            <ruleEngine status="enabled">                <namedObjects>                    <namedObject name="Detection Area">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.97" y="0.97" />                                <point x="0.97" y="-0.97" />                                <point x="-0.97" y="-0.97" />                                <point x="-0.97" y="0.97" />                            </polygon>                        </data>                    </namedObject>                    <namedObject name="Object Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Object Height">                        <data knownNameType="core.int">                            <int value="20" />                        </data>                    </namedObject>                    <namedObject name="Object Width">                        <data knownNameType="core.int">                            <int value="10" />                        </data>                    </namedObject>                    <namedObject name="Traveled Distance">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Visual Duration">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="detection\_0" function="guardIncludeArea">                        <parameter name="IncludeArea" value="Detection Area" />                        <parameter name="Time" value="Object Duration" />                        <parameter name="Width" value="Object Width" />                        <parameter name="Height" value="Object Height" />                        <parameter name="Distance" value="Traveled Distance" />                        <parameter name="Duration" value="Visual Duration" />                        <parameter name="Channel" value="2" />                    </rule>                </rules>                <scripts>                    <script encryption="1">combined.lua</script>                </scripts>                <events>                    <event name="vmd3\_video\_2" nicename="VMD 3: Video 2">                        <attr key="areaid" nicename="Area ID" tag="source" value="0" />                        <attr key="areapolygon" nicename="Polygon info" tag="data" />                        <attr key="active" nicename="Active" tag="property-state" />                    </event>                </events>                <analyticSources>                    <analyticSource name="imageSource" value="2" />                </analyticSources>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>                <libraries>                    <library name="system" />                </libraries>            </ruleEngine>        </ruleEngines>    </application></config>
```

## Upload, control and modify the application

To upload and control the application, use the functions in [Application API](/vapix/applications/application-api/). To retrieve the application configuration and to modify settings, use `/axis-cgi/vaconfig.cgi` from [Application configuration API](/vapix/applications/application-configuration-api/).

## Video motion detection 3 event declaration

The event emitted by Video motion detection 3 is declared as follows:

```bash
<tns1:RuleEngine aev:NiceName="Application">    <tnsaxis:VMD3 aev:NiceName="Video Motion Detection 3">        <vmd3\_video\_1 wstop:topic="true">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance aev:NiceName="Area ID" Type="xsd:string" Name="areaid">                        <aev:Value>0</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance aev:NiceName="Polygon info" Type="xsd:string" Name="areapolygon" />                    <aev:SimpleItemInstance                        aev:NiceName="Active"                        Type="xsd:boolean"                        Name="active"                        isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </vmd3\_video\_1>    </tnsaxis:VMD3></tns1:RuleEngine>
```

`active` describes if the application has detected a moving object or not. An event with `active=1` is sent when a moving object is detected. When motion is no longer detected, an event with `active=0` is sent.

`areaid` and `areapolygon` define the include area. `areaid` is always 0. `areapolygon` is a string with the coordinates defining the include area.

For multichannel products, each video channel has its own event. The event from video channel 1 is `<vmd3_video_1>`, the event from video channel 2 is `<vmd3_video_2>` and so on.