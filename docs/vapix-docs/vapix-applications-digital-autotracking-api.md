---
title: Digital autotracking API
url: "https://developer.axis.com/vapix/applications/digital-autotracking-api/"
category: vapix
subcategory: applications
sha256: 22e1bd4f26b6a27cb0c56b0342922370aa941ceca7d7f91e3a76ac545f9f06e1
scraped_at: "2026-01-09T15:01:11.337Z"
page_height: 32435
---

# Digital autotracking API

## Description

AXIS Digital Autotracking is an AXIS Camera Application Platform (ACAP) application that detects and tracks moving objects within a defined area. When an object is tracked, the application emits an event. A client application that listens to events from AXIS Digital Autotracking can use the event to, for example, record video during tracking or send a notification when tracking starts.

When AXIS Digital Autotracking detects a moving object, the application uses one of the product’s view areas to zoom in on and track the object. While tracking, the application continues to monitor the camera’s entire field of view. If a second moving object is detected, the view area is adapted to include all moving objects. Tracking continues until all objects have stopped or disappeared from the area. This behavior differs from mechanical autotracking, which is available in some PTZ cameras. Mechanical autotracking locks on a single object and follows that object within the camera’s range of coverage.

To use AXIS Digital Autotracking, the application must be uploaded to the Axis product and it must be started. The application can be configured by setting up a view area to be used for autotracking, by modifying the include area and, optionally, by modifying exclude areas and ignore filters. Include and exclude areas define the parts of the scene in which moving objects should be tracked. Ignore filters are used to avoid tracking objects such as shadows of swaying trees, lights from passing cars and small animals regardless of where in the scene the objects appear.

When there are moving objects in the camera’s field of view, the application tests the object’s position, size and movements against the include area, exclude areas and filter conditions to determine if the object should be tracked or ignored. If an object is tracked, an event is emitted.

info

Include area, short-lived object filter and small object filter require AXIS Digital Autotracking 2 or later.

If using ignore filters, tracking will not start and events will not be emitted until the filter conditions have been tested and the tests have passed. For example, when using the `Time` parameter (short-lived object filter), tracking starts if the object is still moving when the set time has passed. That is, tracking and emitted events will be delayed by the set time. If the event is used to start a recording, it is recommended to configure the pre-trigger time in the recording setup so that the recording also includes the time the object moved in the scene before being tracked.

When the application is configured using the Axis product webpages, visual confirmation can be used to help understand the effect of the different filters. When visual confirmation is enabled, colored polygons show which objects the application tracks and which objects the application ignores.

info

Visual confirmation requires AXIS Digital Autotracking 2 or later.

The view area to use for digital autotracking must have PTZ enabled and should have the same aspect ratio as the camera’s capture mode (parameter `ImageSource.I0.Sensor.AspectRatio`). Which resolution to use depends on the camera model and the area under surveillance but the resolution cannot be larger than half the resolution of the full view. The maximum zoom level is automatically adapted to the view area resolution.

AXIS Digital Autotracking can be used while a guard tour is running. The guard tour will be stopped temporarily when digital autotracking starts and will resume when autotracking stops. Manual pan/tilt/zoom operations, for example using a joystick or mouse, have precedence over autotracking. If required, this behavior can be changed by configuring the **PTZ Control Queue** settings, see **Network Video** > **Pan/Tilt/Zoom API** in VAPIX®.

AXIS Digital Autotracking is intended for fixed cameras with at least megapixel resolution and can be installed in Axis network cameras that support view areas and AXIS Camera Application Platform. AXIS Digital Autotracking does not require any license.

### Application versions

The following table shows the differences between different versions of Digital autotracking.

| Feature | Digital autotracking 2 | Digital autotracking 1.1 |
| --- | --- | --- |
| Include area | Supported | — |
| Exclude areas | Polygons with 3–20 corners | Polygons with 3–10 corners |
| Swaying object suppression filter | Supported | Supported |
| Short-lived object filter | Supported | — |
| Small object filter | Supported | — |
| Visual confirmation | Available from camera’s webpages. Not available in the API. | — |

When upgrading from version 1.1 to version 2, the following settings will be kept: view area for autotracking, exclude areas, swaying object suppression filter. Other settings will be set to their default values.

See also:

-   [Digital autotracking 2: Application configuration](#digital-autotracking-2-application-configuration)
-   [Digital autotracking 1: Application configuration](#digital-autotracking-1-application-configuration)

### Identification

AXIS Digital Autotracking 2 can be installed on Axis products with:

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.40`
-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Image.NbrOfViews > 1`
-   **Property**: `Properties.PTZ.PTZ=yes`
-   **Property**: `Properties.PTZ.DigitalPTZ=yes`
-   **Software**: AXIS Camera Application Platform (ACAP)

AXIS Digital Autotracking 1 can be installed on Axis products with:

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.10`
-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Image.NbrOfViews > 1`
-   **Property**: `Properties.PTZ.PTZ=yes`
-   **Property**: `Properties.PTZ.DigitalPTZ=yes`
-   **Software**: AXIS Camera Application Platform (ACAP)

### Dependencies

-   The application is uploaded and controlled using [Application API](/vapix/applications/application-api/).
-   The application is configured using [Application configuration API](/vapix/applications/application-configuration-api/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Check if the Axis product supports digital autotracking. The application can be used with products that support view areas, digital PTZ and AXIS Camera Application Platform. See [Identification](#identification).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&responseformat=rfc&group=Properties.API.HTTP.Version&group=Properties.EmbeddedDevelopment.Version&group=Properties.Image.NbrOfViews&group=Properties.PTZ.PTZ&group=Properties.PTZ.DigitalPTZ"
```

```bash
GET /axis-cgi/param.cgi?action=list&responseformat=rfc&group=Properties.API.HTTP.Version&group=Properties.EmbeddedDevelopment.Version&group=Properties.Image.NbrOfViews&group=Properties.PTZ.PTZ&group=Properties.PTZ.DigitalPTZHost: <servername>
```

Response:

```bash
root.Properties.API.HTTP.Version=3root.Properties.EmbeddedDevelopment.Version=1.40root.Properties.Image.NbrOfViews=8root.Properties.PTZ.PTZ=yesroot.Properties.PTZ.DigitalPTZ=yes
```

Upload Digital autotracking.

Request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'file=@AXISDigitalAutotracking.eap;type=application/octet-stream' \\  "http://<servername>/axis-cgi/applications/upload.cgi"
```

```bash
POST /axis-cgi/applications/upload.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="file"; filename="AXISDigitalAutotracking.eap"Content-Type: application/octet-stream<application package data>--<boundary>--
```

Before configuring Digital autotracking, view areas must be enabled in the Axis product. This example shows how to enable an unused view area and configure the view area to be used for autotracking.

Find an unused view area.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&responseformat=rfc&group=Image.\*.Enabled"
```

```bash
GET /axis-cgi/param.cgi?action=list&responseformat=rfc&group=Image.\*.EnabledHost: <servername>
```

The response shows that view area 7 is unused.

Response:

```bash
root.Image.I0.Enabled=yesroot.Image.I1.Enabled=yesroot.Image.I2.Enabled=yesroot.Image.I3.Enabled=yesroot.Image.I4.Enabled=yesroot.Image.I5.Enabled=yesroot.Image.I6.Enabled=yesroot.Image.I7.Enabled=no
```

Check the camera’s aspect ratio and maximum resolution

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&responseformat=rfc&group=ImageSource.\*.Sensor.AspectRatio&group=Properties.Image.Resolution"
```

```bash
GET /axis-cgi/param.cgi?action=list&responseformat=rfc&group=ImageSource.\*.Sensor.AspectRatio&group=Properties.Image.ResolutionHost: <servername>
```

Response:

```bash
root.ImageSource.I0.Sensor.AspectRatio=4:3root.Properties.Image.Resolution=2592x1944,2048x1536,1600x1200,1280x960,1024x768,800x600,640x480,480x360,320x240,240x180,160x120,1280x1024,2592x1458,1920x1080,1280x720,800x450,640x360,480x270,320x180,160x90,176x144
```

Enable view areas in the Axis product.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&PTZ.ImageSource.I0.PTZEnabled=true"
```

```bash
GET /axis-cgi/param.cgi?action=update&PTZ.ImageSource.I0.PTZEnabled=trueHost: <servername>
```

Enable an unused view area, set the name to "Digital Autotracking View", set the resolution to `640x480` and enable PTZ in the view area. The view area should have the same aspect ratio as the camera’s capture mode. The resolution cannot be larger than half the resolution of the full view.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I7.Enabled=yes&Image.I7.Name=Digital%20Autotracking%20View&Image.I7.Appearance.Resolution=640x480&PTZ.Various.V8.Locked=False"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I7.Enabled=yes&Image.I7.Name=Digital%20Autotracking%20View&Image.I7.Appearance.Resolution=640x480&PTZ.Various.V8.Locked=FalseHost: <servername>
```

Start the application.

Request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/control.cgi?action=start&package=DigitalAutotracking"
```

```bash
POST /axis-cgi/applications/control.cgi?action=start&package=DigitalAutotrackingHost: <servername>
```

Retrieve the application configuration. The response below shows the application configuration for AXIS Digital Autotracking 2.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/vaconfig.cgi?action=get&name=DigitalAutotracking"
```

```bash
GET /axis-cgi/vaconfig.cgi?action=get&name=DigitalAutotrackingHost: <servername>
```

Response:

```bash
<reply result="ok">    <config version="1.0">        <application name="DigitalAutotracking" nicename="Digital Autotracking">            <ruleEngine>                <namedObjects>                    <namedObject name="Detection Area">                        <data knownNameType="geometry.polygon">                            <polygon>                                <point x="0.97" y="0.97" />                                <point x="0.97" y="-0.97" />                                <point x="-0.97" y="-0.97" />                                <point x="-0.97" y="0.97" />                            </polygon>                        </data>                    </namedObject>                    <namedObject name="Object Duration">                        <data knownNameType="core.int">                            <int value="-10" />                        </data>                    </namedObject>                    <namedObject name="Object Width">                        <data knownNameType="core.int">                            <int value="-10" />                        </data>                    </namedObject>                    <namedObject name="Object Height">                        <data knownNameType="core.int">                            <int value="-10" />                        </data>                    </namedObject>                    <namedObject name="Swaying Object Suppression">                        <data knownNameType="core.int">                            <int value="0" />                        </data>                    </namedObject>                    <namedObject name="Visual Duration">                        <data knownNameType="core.int">                            <int value="1" />                        </data>                    </namedObject>                </namedObjects>                <rules>                    <rule name="detection\_DigitalAutotracking" function="trackObjects">                        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />                        <parameter name="Duration" value="Visual Duration" />                        <parameter name="Time" value="Object Duration" />                        <parameter name="Width" value="Object Width" />                        <parameter name="Height" value="Object Height" />                        <parameter name="IncludeArea" value="Detection Area" />                    </rule>                </rules>                <scripts>                    <script encryption="1">combined.lua</script>                </scripts>                <events>                    <event name="tracking" nicename="Tracking">                        <attr key="camera" nicename="View Area" tag="source" />                        <attr key="active" nicename="Active" tag="property-state" />                    </event>                </events>                <moteConfig>                    <option name="boundingBox" value="false" />                    <option name="polygon" value="true" />                    <option name="velocity" value="true" />                </moteConfig>                <libraries>                    <library name="digitalAutotracking" />                    <library name="system" />                </libraries>            </ruleEngine>        </application>    </config></reply>
```

Modify the application configuration. The application is configured by uploading a new application configuration file. It is possible to define which view area to use, to modify the size of the include area, to add and configure exclude areas and to modify filter values. All other settings should be kept as is. If changing the name of a named object, the corresponding parameter value must be changed to match the new name.

info

Include area, short-lived object filter and small object filter require AXIS Digital Autotracking 2.

For more information, see [Digital autotracking 2: Application configuration](#digital-autotracking-2-application-configuration) or [Digital autotracking 1: Application configuration](#digital-autotracking-1-application-configuration).

In this example, two new named objects and corresponding parameters are added. The named object `View Area` and parameter `VA` instruct the application to use view area `7`. The named object `Exclude Area 1` and parameter `EA1` define an exclude area.

Request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/x-www-form-urlencoded" \\  "http://<servername>/axis-cgi/vaconfig.cgi" \\  --data 'action=modify&name=DigitalAutotracking<config version="1.0">  <application name="DigitalAutotracking" nicename="Digital Autotracking">    <ruleEngine>      <namedObjects>        <namedObject name="Detection Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.97" y="0.97"/>              <point x="0.97" y="-0.97"/>              <point x="-0.97" y="-0.97"/>              <point x="-0.97" y="0.97"/>            </polygon>          </data>        </namedObject>        <namedObject name="Exclude Area 1">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.20" y="0.20"/>              <point x="0.20" y="-0.20"/>              <point x="-0.20" y="-0.20"/>              <point x="-0.20" y="0.20"/>            </polygon>          </data>        </namedObject>        <namedObject name="Object Duration">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Object Width">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Object Height">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Swaying Object Suppression">          <data knownNameType="core.int">            <int value="0"/>          </data>        </namedObject>        <namedObject name="Visual Duration">          <data knownNameType="core.int">            <int value="1"/>          </data>        </namedObject>        <namedObject name="View Area">          <data knownNameType="core.int">            <int value="7"/>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="detection\_0" function="guardIncludeArea">          <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression"/>          <parameter name="Duration" value="Visual Duration"/>          <parameter name="Time" value="Object Duration"/>          <parameter name="Width" value="Object Width"/>          <parameter name="Height" value="Object Height"/>          <parameter name="VA" value="View Area"/>          <parameter name="IncludeArea" value="Detection Area"/>          <parameter name="EA1" value="Exclude Area 1"/>        </rule>      </rules>      <scripts>        <script encryption="1">combined.lua</script>      </scripts>      <events>        <event name="tracking" nicename="Tracking">          <attr key="camera" nicename="View Area" tag="source"/>          <attr key="active" nicename="Active" tag="property-state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>      <libraries>        <library name="digitalAutotracking"/>        <library name="system"/>      </libraries>    </ruleEngine>  </application></config>'
```

```bash
POST /axis-cgi/vaconfig.cgiHost: <servername>Content-Type: application/x-www-form-urlencodedContent-Length: <content length>action=modify&name=DigitalAutotracking<config version="1.0">  <application name="DigitalAutotracking" nicename="Digital Autotracking">    <ruleEngine>      <namedObjects>        <namedObject name="Detection Area">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.97" y="0.97"/>              <point x="0.97" y="-0.97"/>              <point x="-0.97" y="-0.97"/>              <point x="-0.97" y="0.97"/>            </polygon>          </data>        </namedObject>        <namedObject name="Exclude Area 1">          <data knownNameType="geometry.polygon">            <polygon>              <point x="0.20" y="0.20"/>              <point x="0.20" y="-0.20"/>              <point x="-0.20" y="-0.20"/>              <point x="-0.20" y="0.20"/>            </polygon>          </data>        </namedObject>        <namedObject name="Object Duration">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Object Width">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Object Height">          <data knownNameType="core.int">            <int value="-10"/>          </data>        </namedObject>        <namedObject name="Swaying Object Suppression">          <data knownNameType="core.int">            <int value="0"/>          </data>        </namedObject>        <namedObject name="Visual Duration">          <data knownNameType="core.int">            <int value="1"/>          </data>        </namedObject>        <namedObject name="View Area">          <data knownNameType="core.int">            <int value="7"/>          </data>        </namedObject>      </namedObjects>      <rules>        <rule name="detection\_0" function="guardIncludeArea">          <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression"/>          <parameter name="Duration" value="Visual Duration"/>          <parameter name="Time" value="Object Duration"/>          <parameter name="Width" value="Object Width"/>          <parameter name="Height" value="Object Height"/>          <parameter name="VA" value="View Area"/>          <parameter name="IncludeArea" value="Detection Area"/>          <parameter name="EA1" value="Exclude Area 1"/>        </rule>      </rules>      <scripts>        <script encryption="1">combined.lua</script>      </scripts>      <events>        <event name="tracking" nicename="Tracking">          <attr key="camera" nicename="View Area" tag="source"/>          <attr key="active" nicename="Active" tag="property-state"/>        </event>      </events>      <moteConfig>        <option name="boundingBox" value="false"/>        <option name="polygon" value="true"/>        <option name="velocity" value="true"/>      </moteConfig>      <libraries>        <library name="digitalAutotracking"/>        <library name="system"/>      </libraries>    </ruleEngine>  </application></config>
```

Retrieve an RTSP stream with event metadata.

Request:

```bash
rtsp://<servername>/axis-media/media.amp?event=on&video=0&eventtopic=onvif:RuleEngine/axis:DigitalAutotracking/tracking//.
```

The AXIS Digital Autotracking tracking event in the event stream.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tns1:RuleEnginge/tnsaxis:DigitalAutotracking/tracking            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://daf20c8-c41f-11e0-8c89-00408cb96106/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="2014-03-07T13:44:34.112703Z" PropertyOperation="Changed">                    <tt:Source>                        <tt:SimpleItem Name="View Area" Value="0" />                    </tt:Source>                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="active" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

AXIS Digital Autotracking event declaration. Use `GetEventInstances` from VAPIX® Event and Action Services to list event declarations.

```bash
<tns1:RuleEngine aev:NiceName="Application">  <tnsaxis:DigitalAutotracking aev:NiceName="Digital Autotracking">    <timer wstop:topic="true">      <aev:MessageInstance></aev:MessageInstance>    </timer>    <xinternal\_1 wstop:topic="true">      <aev:MessageInstance>        <aev:DataInstance>          <aev:SimpleItemInstance aev:NiceName="Polygons" Type="xsd:string" Name="polygons">          </aev:SimpleItemInstance>        </aev:DataInstance>      </aev:MessageInstance>    </xinternal\_1>    <tracking wstop="true" aev:NiceName="Tracking">      <aev:MessageInstance aev:isProperty="true">        <aev:SourceInstance>          <aev:SimpleItemInstance aev:NiceName="View Area" Type="xsd:string" Name="camera">          </aev:SimpleItemInstance>        </aev:SourceInstance>        <aev:DataInstance>          <aev:SimpleItemInstance aev:NiceName="Is active" Type="xsd:boolean" Name="active" isPropertyState="true">          </aev:SimpleItemInstance>        </aev:DataInstance>      </aev:MessageInstance>    <tracking>  </tnsaxis:DigitalAutotracking>...</tns1:RuleEngine>
```

info

xinternal\_1 is an internal camera event.

## Application configuration
### Digital autotracking 2: Application configuration

The application configuration is an XML file with named objects and a rule. The named objects define the view area to use, the include area, exclude areas and ignore filters. In the rule, the named objects are used as parameter values. If using exclude areas, the rule must be updated with one parameter for each exclude area.

info

This section applies to AXIS Digital Autotracking version 2. Version 1 is described in [Digital autotracking 1: Application configuration](#digital-autotracking-1-application-configuration).

The following types of named objects can be configured:

-   The view area used for autotracking. See [View area for autotracking](#view-area-for-autotracking).
-   Include area. See [Include area](#include-area).
-   (Optional) Exclude areas. See [Exclude areas](#exclude-areas).
-   Swaying object suppression. Also known as traveled distance. See [Swaying object filter](#swaying-object-filter).
-   Object duration. See [Short lived object filter](#short-lived-object-filter).
-   Object width and object height. See [Small object filter](#small-object-filter).

Example configuration:

```bash
<config version="1.0">    <application name="DigitalAutotracking" nicename="Digital Autotracking">        <ruleEngine>            <namedObjects>                <namedObject name="Detection Area">                    <data knownNameType="geometry.polygon">                        <polygon>                            <point x="0.97" y="0.97" />                            <point x="0.97" y="-0.97" />                            <point x="-0.97" y="-0.97" />                            <point x="-0.97" y="0.97" />                        </polygon>                    </data>                </namedObject>                <namedObject name="Exclude Area 1">                    <data knownNameType="geometry.polygon">                        <polygon>                            <point x="0.20" y="0.20" />                            <point x="0.20" y="-0.20" />                            <point x="-0.20" y="-0.20" />                            <point x="-0.20" y="0.20" />                        </polygon>                    </data>                </namedObject>                <namedObject name="Object Duration">                    <data knownNameType="core.int">                        <int value="-10" />                    </data>                </namedObject>                <namedObject name="Object Width">                    <data knownNameType="core.int">                        <int value="-10" />                    </data>                </namedObject>                <namedObject name="Object Height">                    <data knownNameType="core.int">                        <int value="-10" />                    </data>                </namedObject>                <namedObject name="Swaying Object Suppression">                    <data knownNameType="core.int">                        <int value="0" />                    </data>                </namedObject>                <namedObject name="Visual Duration">                    <data knownNameType="core.int">                        <int value="1" />                    </data>                </namedObject>                <namedObject name="View Area">                    <data knownNameType="core.int">                        <int value="7" />                    </data>                </namedObject>            </namedObjects>            <rules>                <rule name="detection\_0" function="guardIncludeArea">                    <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />                    <parameter name="Duration" value="Visual Duration" />                    <parameter name="Time" value="Object Duration" />                    <parameter name="Width" value="Object Width" />                    <parameter name="Height" value="Object Height" />                    <parameter name="VA" value="View Area" />                    <parameter name="IncludeArea" value="Detection Area" />                    <parameter name="EA1" value="Exclude Area 1" />                </rule>            </rules>            <scripts>                <script encryption="1">combined.lua</script>            </scripts>            <events>                <event name="tracking" nicename="Tracking">                    <attr key="camera" nicename="View Area" tag="source" />                    <attr key="active" nicename="Active" tag="property-state" />                </event>            </events>            <moteConfig>                <option name="boundingBox" value="false" />                <option name="polygon" value="true" />                <option name="velocity" value="true" />            </moteConfig>            <libraries>                <library name="digitalAutotracking" />                <library name="system" />            </libraries>        </ruleEngine>    </application></config>
```

The table below lists the XML elements and attributes used to define named objects and rules. The elements not listed in the table define how the application shall run in AXIS Camera Application Platform and must not be changed.

| XML element | Attribute | Value values | Description |
| --- | --- | --- | --- |
| `application` | `name` | `DigitalAutotracking` | Contains the application configuration. Attribute `name` is the name of the application. |
| `ruleEngine` |  |  | Contains the `ruleEngine` configuration. |
| `namedObjects` |  |  | Contains all named objects used by the application. |
| `namedObject` | `name` | String | A named object.Attribute `name` is the name of the named object. Any name can be used.The name used here should also be used as value for the `parameter` element’s attribute `value`. |
| `data` | `knownTypeName` | `core.int` `geometry.polygon` | Contains data for the named object.Attribute `knownType` specifies the type of data.`core.int` = Integer. Use for the filters and the view area.`geometry.polygon` = Polygon. Use for include and exclude areas. |
| `polygon` |  | `point` | Include and exclude areas: Contains `point` elements that describe the exclude area polygon. The polygon is defined by 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate.The top right corner of the camera view is at `x=1.0` and `y=1.0` |
| `point` | `x` | `-1.0 ... 1.0` | Attribute `x` is the `x` coordinate. |
|  | `y` | `-1.0 ... 1.0` | Attribute `y` is the `y` coordinate. |
| `int` | `value` | Integer | An integer defining the filter value or which view area to use.For information about the view area, see [View area for autotracking](#view-area-for-autotracking).For information about the different filters, see [Swaying object filter](#swaying-object-filter), [Short lived object filter](#short-lived-object-filter), and [Small object filter](#small-object-filter). |
| `rules` |  |  | Contains parameters for the application rule. |
| `parameter` |  |  | Application parameter. Each named object must have a corresponding parameter.Attribute `name` must have one of values listed below.Attribute `value` specifies which named object to use for the parameter. |
|  | `name` | `IncludeArea` | Parameter specifying which named object to use for the include area.See [Include area](#include-area). |
|  |  | `Time` | Parameter specifying which named object to use for the short-lived object filter.See [Short lived object filter](#short-lived-object-filter). |
|  |  | `Height` | Parameter specifying which named object to use for the height in the small object filter.See [Small object filter](#small-object-filter). |
|  |  | `Width` | Parameter specifying which named object to use for width in the small object filter.See [Small object filter](#small-object-filter). |
|  |  | `SwayingObjectSuppression` | Parameter specifying which named object to use for the swaying object filter.See [Swaying object filter](#swaying-object-filter). |
|  |  | `EA1` `EA2` `...` `EA10` | Optional. Parameters specifying which the named objects to use for the exclude areas. Use one parameter for each exclude area.See [Exclude areas](#exclude-areas). |
|  |  | `VA` | The view area to use.See [View area for autotracking](#view-area-for-autotracking). |
|  |  | `Duration` | Internal parameter. |
|  | `value` | String | Parameter value. The value should be the same as the `name` attribute of the corresponding `namedObject`. |

### Digital autotracking 1: Application configuration

The application configuration is an XML file with named objects and a rule. The named objects define the view area to use, exclude areas and the swaying object suppression ignore filter. In the rule, the named objects are used as parameter values. If using exclude areas, the rule must be updated with one parameter for each exclude area.

info

This section applies to AXIS Digital Autotracking version 1. Version 2 is described in [Digital autotracking 2: Application configuration](#digital-autotracking-2-application-configuration).

The following types of named objects can be configured:

-   The view area used for autotracking. See [View area for autotracking](#view-area-for-autotracking).
-   (Optional) Exclude areas. See [Exclude areas](#exclude-areas).
-   Swaying object suppression. Also known as traveled distance. See [Swaying object filter](#swaying-object-filter).

Example configuration:

```bash
<config version="1.0">    <application name="DigitalAutotracking">        <ruleEngine>            <namedObjects>                <namedObject name="Swaying Object Suppression">                    <data knownNameType="core.int">                        <int value="30" />                    </data>                </namedObject>                <namedObject name="Exclude Area 0">                    <data knownNameType="geometry.polygon">                        <polygon>                            <point x="-0.8" y="0.6" />                            <point x="-0.6" y="0.6" />                            <point x="-0.6" y="0.1" />                            <point x="-0.8" y="0.1" />                        </polygon>                    </data>                </namedObject>                <namedObject name="View Area">                    <data knownNameType="core.int">                        <int value="7" />                    </data>                </namedObject>            </namedObjects>            <rules>                <rule name="detection\_DigitalAutotracking" function="trackObjects">                    <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />                    <parameter name="EA0" value="Exclude Area 0" />                    <parameter name="VA" value="View Area" />                </rule>            </rules>            <scripts>                <script encryption="1">middleclass.lua</script>                <script encryption="1">tools.lua</script>                <script encryption="1">timer.lua</script>                <script encryption="1">paramreader.lua</script>                <script encryption="1">scenefilter.lua</script>                <script encryption="1">stabilizer.lua</script>                <script encryption="1">superobject.lua</script>                <script encryption="1">track.lua</script>                <script encryption="1">trackkeeper.lua</script>                <script encryption="1">trackfilterdistance.lua</script>                <script encryption="1">pacemaker.lua</script>                <script encryption="1">regulator.lua</script>                <script encryption="1">tracker.lua</script>                <script encryption="1">main.lua</script>            </scripts>            <events>                <event name="tracking">                    <attr key="camera" nicename="View Area" tag="source" />                    <attr key="active" nicename="Is active" tag="property-state" />                </event>            </events>            <moteConfig>                <option name="boundingBox" value="false" />                <option name="polygon" value="true" />                <option name="velocity" value="true" />            </moteConfig>            <libraries>                <library name="DigitalAutotracking" />                <library name="system" />            </libraries>        </ruleEngine>    </application></config>
```

**XML User Configuration Data Description**

The table below lists the XML elements and attributes used to define named objects and rules. The elements not listed in the table define how the application shall run in AXIS Camera Application Platform and must not be changed.

| XML element | Attribute | Valid values | Description |
| --- | --- | --- | --- |
| `application` | `name` | `DigitalAutotracking` | Contains the application configuration. Attribute `name` contains the name of the application. |
| `ruleEngine` |  |  | Contains the `ruleEngine` configuration. |
| `namedObjects` |  |  | Contains all named objects used by the application. |
| `namedObject` | `name` | String | A named object.Attribute `name` is the name of the named object. Any name can be used.The name used here should also be used as value for the `parameter` element’s attribute `value`. |
| `data` | `knownTypeName` | `core.int` `geometry.polygon` | Contains data for the named object.Attribute `knownType` specifies the type of data.`core.int` = Integer. Use for the view area and swaying object suppression filter named objects.`geometry.polygon` = Polygon. Use for exclude areas. |
| `polygon` |  | `point` | Exclude areas: Contains `point` elements that describe the exclude area polygon. The polygon is defined by 3–10 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` coordinate and one `y` coordinate.The top right corner of the camera view is at `x=1.0` and `y=1.0` |
| `point` | `x` | `-1.0 ... 1.0` | Attribute `x` is the `x` coordinate. |
|  | `y` | `-1.0 ... 1.0` | Attribute `y` is the `y` coordinate. |
| `int` | `value` | Integer | An integer defining the filter value or which view area to use.For information about the view area, see [View area for autotracking](#view-area-for-autotracking).For information about the swaying object filter, see [Swaying object filter](#swaying-object-filter). |
| `rules` |  |  | Contains parameters for the application rule. |
| `parameter` |  |  | Application parameter. Each named object must have a corresponding parameter.Attribute `name` must have one of values listed below.Attribute `value` specifies which named object to use for the parameter. |
|  | `name` | `SwayingObjectSuppression` | Parameter specifying which named object to use for the swaying object filter.See [Swaying object filter](#swaying-object-filter). |
|  |  | `EA0` `EA1` `...` `EA9` | Optional. Parameters specifying which the named objects to use for the exclude areas. Use one parameter for each exclude area.See [Exclude areas](#exclude-areas). |
|  |  | `VA` | The view area to use.See [View area for autotracking](#view-area-for-autotracking). |
|  |  | `Duration` | Internal parameter. |
|  | `value` | String | Parameter value. The value should be the same as the `name` attribute of the corresponding `namedObject`. |

### View area for autotracking

The application uses one of the product’s view areas for autotracking. For the application to work, the application configuration must be updated with the view area to use. The view area must be enabled, use the same aspect ratio as the camera’s capture mode and must have PTZ enabled.

In the application configuration, the view area is a named object.

```bash
<namedObject name="View Area">    <data knownNameType="core.int">        <int value="7" />    </data></namedObject>
```

In the rule, the view area named object is used by the `VA` parameter.

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />    </rule></rules>
```

### Include area

The include area is the area in which moving objects will be tracked. Objects moving outside the include area will be ignored.

info

Include area is supported by AXIS Digital Autotracking 2 and later.

In the application configuration, the include area is a named object.

```bash
<namedObject name="Detection Area">    <data knownNameType="geometry.polygon">        <polygon>            <point x="0.97" y="0.97" />            <point x="0.97" y="-0.97" />            <point x="-0.97" y="-0.97" />            <point x="-0.97" y="0.97" />        </polygon>    </data></namedObject>
```

The include area is set up as a polygon with 3–20 points describing the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`. The bottom left corner is at `x=-1.0` and `y=-1.0`.

info

If the video stream is rotated, the coordinates of the unrotated video stream should be used when configuring the application.

In the rule, the include area named object is used by the `IncludeArea` parameter.

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />    </rule></rules>
```

### Exclude areas

An exclude area is an area in which moving objects are ignored. Exclude areas are optional. Up to 10 exclude areas can be used.

In the application configuration, each exclude area is a named object.

```bash
<namedObject name="Exclude Area 1">    <data knownNameType="geometry.polygon">        <polygon>            <point x="0.20" y="0.20" />            <point x="0.20" y="-0.20" />            <point x="-0.20" y="-0.20" />            <point x="-0.20" y="0.20" />        </polygon>    </data></namedObject>
```

The exclude are is set up as a polygon with 3–20 points (AXIS Digital Autotracking 2) or 3–10 points (AXIS Digital Autotracking 1). The points describe the polygon corners. The line defining the polygon sides is drawn from point to point in the order the points are listed. Each point is a coordinate pair with one `x` and one `y` coordinate. The top right corner of the camera view is at `x=1.0` and `y=1.0`. The bottom left corner is at `x=-1.0` and `y=-1.0`.

info

If the video stream is rotated, the coordinates of the unrotated video stream should be used when configuring the application.

When using exclude areas, the rule must be updated with one parameter for each exclude area. The parameter is called `EA#` where `#` is an index starting from `1` (AXIS Digital Autotracking 2) or from `0` (AXIS Digital Autotracking 1).

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />        <parameter name="EA1" value="Exclude Area 1" />        <parameter name="EA2" value="Exclude Area 2" />    </rule></rules>
```

### Swaying object filter

The swaying object filter is used to avoid tracking objects that only move a short distance, for example moving trees, flags and their shadows. If the swaying objects in the scene are large, for example large ponds or large trees, it is recommended to use exclude areas instead of the filter. The filter will be applied to all moving objects in scene and, if set to a value too large, important objects might not be tracked.

When the swaying object filter is enabled and the application finds a moving object, tracking will not start until the object has travelled a distance larger than the set filter size. The event emitted by the application will be emitted when tracking starts. If the event is used to start a recording, configure the pre-trigger time so that the recording also includes the time the object moved in the scene before being tracked.

In the application configuration, the swaying object filter is the named object used by the `SwayingObjectSuppression` parameter. The filter size is an integer between `10` and `100`. The value `100` implies that an object must travel from its initial from to one third of the image width or height before being tracked. The value `50` implies half that distance, that is, the object must travel a distance one sixth of the image width or height before being tracked. To disable the filter, use `0` or a negative integer.

```bash
<namedObject name="Swaying Object Suppression">    <data knownNameType="core.int">        <int value="0" />    </data></namedObject>
```

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />    </rule></rules>
```

### Short lived object filter

info

Short lived object filter is supported by Digital Autotracking 2 and later.

The short-lived object filter is used to avoid tracking objects that only appear for a short period of time, such as light beams from a passing car and quickly moving shadows. When the short-lived object filter is enabled and the application finds a moving object, tracking will not start until the set time as passed. The event emitted by the application will be emitted when tracking starts. If the event is used to start a recording, configure the pre-trigger time so that the recording also includes the time the object moved in the scene before being tracked.

In the application configuration, the short-lived object filter is the named object used by the `Time` parameter. The filter size is an integer that specifies the number of seconds to wait before emitting the event. To disable the filter, use `0` or a negative integer.

```bash
<namedObject name="Object Duration">    <data knownNameType="core.int">        <int value="0" />    </data></namedObject>
```

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />    </rule></rules>
```

### Small object filter

info

Small object filter is supported by Digital autotracking 2 and later.

The small object filter is used to avoid tracking objects that are too small. For example, if only moving cars should be tracked, the small object filter can be used to avoid tracking people and animals. When using the small object filter, take into consideration that an object far from the camera appears smaller than an object close to the camera.

The filter is defined by specifying the maximum width and maximum height of the objects to ignore. To be ignored, the object must be smaller than the set width and by the set height.

In the application configuration, the small object filter is the named objects used by the `Height` and `Width` parameters. Each filter’s size can be set to an integer between `5` and `100` and is the maximum object width or height measured in percent of the image width or height. To disable the filters, use `0` or a negative integer.

info

The small object filter is defined using the unrotated video stream. Width and height will be interchanged if the image is rotated 90 or 270 degrees, for example for cameras that support autorotation and that are mounted at a 90 or 270 degree angle. If the image is rotated 90 or 270 degrees, the object height should be entered as Width and vice versa when the application is configured through the API. The application webpage takes image rotation into account and displays height as width if the image is rotated.

```bash
<namedObject name="Object Width">    <data knownNameType="core.int">        <int value="20"/>    </data></namedObject><namedObject name="Object Height">    <data knownNameType="core.int">        <int value="10"/>    </data></namedObject>
```

```bash
<rules>    <rule name="detection\_DigitalAutotracking" function="trackObjects">        <parameter name="SwayingObjectSuppression" value="Swaying Object Suppression" />        <parameter name="Duration" value="Visual Duration" />        <parameter name="Time" value="Object Duration" />        <parameter name="Width" value="Object Width" />        <parameter name="Height" value="Object Height" />        <parameter name="VA" value="View Area" />        <parameter name="IncludeArea" value="Detection Area" />    </rule></rules>
```

## Upload, control and modify the application

To upload and control the application, use the functions in [Application API](/vapix/applications/application-api/). To retrieve the application configuration and to modify settings, use `/axis-cgi/vaconfig.cgi` from [Application configuration API](/vapix/applications/application-configuration-api/).

## Digital autotracking event declaration

The digital autotracking event is `true` when autotracking is active, that is, then the application follows a moving object.

`camera` specifies the view area used for autotracking and is numbered starting from `1`. Example: `camera=1` corresponds to view area `0` (defined by parameter `Image.I0`).

`active` defines whether the application tracks a moving object or not. Digital autotracking will remain active until an event with `active = 0` is sent.

**Topic**

-   **Name**: `tns1:RuleEngine/tnsaxis:DigitalAutotracking/tnsaxis:tracking`
-   **Type**: Stateful
-   **Nice name**: `DigitalAutotracking`

**Source instance**

-   **Nice name**: `View Area`
-   **Type**: string
-   **Name**: `camera`

**Data instance**

-   **Nice name**: Is active
-   **Type**: boolean
-   **Name**: `active`
-   **isPropertyState**: `true`