---
title: Thermal imaging
url: "https://developer.axis.com/vapix/network-video/thermal-imaging/"
category: vapix
subcategory: network-video
sha256: 15a98cea67cab7e4d7093a01493e6c98d902bfc5a19da4c078b2f8aa65907275
scraped_at: "2026-01-09T15:21:17.183Z"
page_height: 46633
---

# Thermal imaging

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Color palettes
### Description

Color palettes applied to thermal images help the human eye distinguish image details. The colors in the palette are artificially created pseudocolors that emphasize temperature differences.

Depending on model, Axis thermal network cameras have different types of palettes:

-   Stream palettes are palettes that can be applied to individual streams, that is, different streams can have different palettes. The palette is specified when requesting a stream using RTSP or HTTP.
-   Global palettes are used for all streams. The palette is specified by parameter `Image.I0.Appearance.Palette`.
-   Isotherm palettes display temperature ranges in predefined colors. The temperature ranges are set by the user, who thereby associates specific temperature ranges to specific color ranges. Use VAPIX® Isotherm API to enable the use of isotherm palettes and to set the temperature ranges. See [Isotherm API](#isotherm-api).

#### Identification

Palettes are supported if:

-   **Property**: `Properties.Image.Palette.Palette=yes`

Stream palettes are supported if `Properties.Image.Palette.StreamPalette` does not exist or if:

-   **Property**: `Properties.Image.Palette.StreamPalette=yes`

Global palettes are supported if:

-   **Property**: `Properties.Image.Palette.StreamPalette=no`

### Using stream palettes

Stream palettes are palettes that can be applied to individual streams, that is, different streams can have different palettes. The palette is specified then requesting a stream using RTSP or HTTP. If no palette is included in the RTSP or HTTP request, the palette in parameter `Image.I0.Appearance.Palette` is used.

Check if stream palettes are supported.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.PaletteHost: <servername>
```

The response shows that stream palettes are supported. Stream palettes are also supported if `Properties.Image.Palette.StreamPalette` does not exist.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/plainProperties.Image.Palette.Palette=yesProperties.Image.Palette.StreamPalette=yes
```

List available palettes. Use `/axis-cgi/param.cgi?action=listdefinitions`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.PaletteHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-type: text/xml<parameterDefinitions xmlns="http://www.axis.com/ParameterDefinitionsSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/ParameterDefinitionsSchema http://<servername>/pub/parameterdefinitions.xsd" version="1.0">  <model>AXIS Q1931-E PT Mount</model>  <firmwareVersion>5.75.1</firmwareVersion>  <group name="root">    <group name="Image">      <group name="I0">        <group name="Appearance">          <parameter name="Palette" value="White-hot" securityLevel="7714" niceName="Palette">            <type>              <enum>                <entry value="White-hot"/>                <entry value="Black-hot"/>                <entry value="Axis"/>                <entry value="Rainbow"/>                <entry value="Planck"/>                <entry value="Atlantis"/>                <entry value="Nightvision"/>                <entry value="Ice-and-fire"/>              </enum>            </type>          </parameter>        </group>      </group>    </group>  </group></parameterDefinitions>
```

Retrieve an RTSP stream with palette "Axis".

Request:

```bash
rtsp://<servername>/axis-media/media.amp?videocodec=h264&palette=Axis
```

Retrieve an HTTP stream with palette "Axis".

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/mjpg/video.cgi?palette=Axis"
```

```bash
GET /axis-cgi/mjpg/video.cgi?palette=AxisHost: <servername>
```

### Using global palettes

For products that do not support stream palettes, all streams will use the global palette from parameter `Image.I0.Appearance.Palette`.

Check if palettes are supported.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.PaletteHost: <servername>
```

The response shows that palettes are supported but that stream palettes are not supported.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/plainProperties.Image.Palette.Palette=yesProperties.Image.Palette.StreamPalette=no
```

List available palettes. Use `/axis-cgi/param.cgi?action=listdefinitions`

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.PaletteHost: <servername>
```

The names starting with "iso" are isotherm palettes.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<parameterDefinitions xmlns="http://www.axis.com/ParameterDefinitionsSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/ParameterDefinitionsSchema http://<servername>/pub/parameterdefinitions.xsd" version="1.0">  <model>AXIS Q2901-E</model>  <firmwareVersion>5.55.4</firmwareVersion>  <group name="root">    <group name="Image">      <group name="I0">        <group name="Appearance">          <parameter name="Palette" value="Red-hot" securityLevel="7714" niceName="Palette">            <type>              <enum>                <entry value="White-hot"/>                <entry value="Black-hot"/>                <entry value="Planck"/>                <entry value="Axis"/>                <entry value="Rainbow"/>                <entry value="Red-hot"/>                <entry value="Nightvision"/>                <entry value="Iso-Fire-WH"/>                <entry value="Iso-Fire-BH"/>                <entry value="Iso-Planck-WH"/>                <entry value="Iso-Axis-WH"/>                <entry value="Iso-Midrange-WH"/>                <entry value="Iso-Midrange-BH"/>                <entry value="Iso-Rainbow-WH"/>              </enum>            </type>          </parameter>        </group>      </group>    </group>  </group></parameterDefinitions>
```

Change the global palette to "Axis".

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=Axis"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=AxisHost: <servername>
```

### Using isotherm palettes

Before using isotherm palettes, make sure to enable isothermal imaging and to set the temperature limits as described in [Isotherm API](#isotherm-api).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/setmode.cgi?mode=enabled"
```

```bash
GET /axis-cgi/isotherm/setmode.cgi?mode=enabledHost: <servername>
```

List available palettes. Use `/axis-cgi/param.cgi?action=listdefinitions`

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.PaletteHost: <servername>
```

Isotherm palettes have names starting with "iso".

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<parameterDefinitions xmlns="http://www.axis.com/ParameterDefinitionsSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/ParameterDefinitionsSchema http://<servername>/pub/parameterdefinitions.xsd" version="1.0">  <model>AXIS Q2901-E</model>  <firmwareVersion>5.55.4</firmwareVersion>  <group name="root">    <group name="Image">      <group name="I0">        <group name="Appearance">          <parameter name="Palette" value="Red-hot" securityLevel="7714" niceName="Palette">            <type>              <enum>                <entry value="White-hot"/>                <entry value="Black-hot"/>                <entry value="Planck"/>                <entry value="Axis"/>                <entry value="Rainbow"/>                <entry value="Red-hot"/>                <entry value="Nightvision"/>                <entry value="Iso-Fire-WH"/>                <entry value="Iso-Fire-BH"/>                <entry value="Iso-Planck-WH"/>                <entry value="Iso-Axis-WH"/>                <entry value="Iso-Midrange-WH"/>                <entry value="Iso-Midrange-BH"/>                <entry value="Iso-Rainbow-WH"/>              </enum>            </type>          </parameter>        </group>      </group>    </group>  </group></parameterDefinitions>
```

Change the global palette to the isotherm palette "Iso-Axis-WH".

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=Iso-Axis-WH"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=Iso-Axis-WHHost: <servername>
```

## Isotherm API
### Description

VAPIX® Isotherm API is used to enable isothermal imaging and to set the isotherm palette temperature ranges. An isotherm palette is a pseudocolor palette where user-defined temperature ranges are displayed in predefined colors, that is, temperature ranges are associated with color ranges.

The temperature ranges are defined by three limits: lower, middle and upper. Most isotherm palettes display temperatures below the lower limit in grayscale. When using the "Iso-Fire-WH" palette, temperatures between the lower and middle limits are displayed in yellow, temperatures between the lower and middle limits are displayed in orange and temperatures above the upper limit are displayed in red.

Supported functionality:

-   Enable and disable isothermal imaging.
-   Set and get the temperature limits.

How to list available isotherm palettes and how to set isotherm palettes is described in [Using isotherm palettes](#using-isotherm-palettes).

#### Identification

VAPIX® Isotherm API is available if:

-   **Property**: `Properties.Isotherm.Isotherm=yes`
-   **AXIS OS**: 5.55 and later

### Common examples

Retrieve supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/schemaversions.cgi"
```

```bash
GET /axis-cgi/isotherm/schemaversions.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><IsothermResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">  <SchemaVersionsSuccess>    <SchemaVersion>      <VersionNumber>1.0</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>    \[...\]  </SchemaVersionsSuccess></IsothermResponse>
```

Set the temperature scale to Celsius. Use `/axis-cgi/temperature_alarm/settemperaturescale.cgi` from VAPIX® Temperature Alarm API. See [Set temperature scale](#set-temperature-scale).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/settemperaturescale.cgi?unit=Celsius"
```

```bash
GET /axis-cgi/temperature\_alarm/settemperaturescale.cgi?unit=CelsiusHost: <servername>
```

Check if isothermal imaging is enabled.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/getmode.cgi"
```

```bash
GET /axis-cgi/isotherm/getmode.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><IsothermResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">  <Success>    <GetModeSuccess>      <Mode>disabled</Mode>    </GetModeSuccess>  </Success></IsothermResponse>
```

Enable isothermal imaging.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/setmode.cgi?mode=enabled"
```

```bash
GET /axis-cgi/isotherm/setmode.cgi?mode=enabledHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><IsothermResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">  <GeneralSuccess /></IsothermResponse>
```

Set the upper, middle and lower limits for the isotherm palette temperature ranges.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/setlimits.cgi?upper=80&middle=70&lower=50"
```

```bash
GET /axis-cgi/isotherm/setlimits.cgi?upper=80&middle=70&lower=50Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><IsothermResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">  <GeneralSuccess /></IsothermResponse>
```

This example shows how to apply an isotherm palette. See also [Color palettes](#color-palettes).

To check that palettes are supported, use:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=Properties.Image.Palette.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=Properties.Image.Palette.PaletteHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xmlProperties.Image.Palette.Palette=yes
```

List available isotherm palettes. Use `/axis-cgi/param.cgi?action=listdefinitions`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.Palette"
```

```bash
GET /axis-cgi/param.cgi?action=listdefinitions&listformat=xmlschema&group=Image.\*.Appearance.PaletteHost: <servername>
```

The response lists all palettes. The isotherm palettes are the ones starting with "iso".

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<parameterDefinitions xmlns="http://www.axis.com/ParameterDefinitionsSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/ParameterDefinitionsSchema http://<servername>/pub/parameterdefinitions.xsd" version="1.0">  <model>AXIS Q2901-E</model>  <firmwareVersion>5.55.4</firmwareVersion>  <group name="root">    <group name="Image">      <group name="I0">        <group name="Appearance">          <parameter name="Palette" value="Red-hot" securityLevel="7714" niceName="Palette">            <type>              <enum>                <entry value="White-hot"/>                <entry value="Black-hot"/>                <entry value="Planck"/>                <entry value="Axis"/>                <entry value="Rainbow"/>                <entry value="Red-hot"/>                <entry value="Nightvision"/>                <entry value="Iso-Fire-WH"/>                <entry value="Iso-Fire-BH"/>                <entry value="Iso-Planck-WH"/>                <entry value="Iso-Axis-WH"/>                <entry value="Iso-Midrange-WH"/>                <entry value="Iso-Midrange-BH"/>                <entry value="Iso-Rainbow-WH"/>              </enum>            </type>          </parameter>        </group>      </group>    </group>  </group></parameterDefinitions>
```

The Axis product used in this example does not support stream palettes. The palette specified by parameter `Image.I0.Appearance.Palette` is used for all streams. To change to the isotherm palette, "Iso-Axis-WH", use:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=Iso-Axis-WH"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.Appearance.Palette=Iso-Axis-WHHost: <servername>
```

### Get schema versions

Use `/axis-cgi/isotherm/schemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator, Viewer

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/schemaversions.cgi"
```

```bash
GET /axis-cgi/isotherm/schemaversions.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/isotherm/schemaversions.cgi`

**Success**

A successful request returns the supported schema version.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><IsothermResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        \[...\]    </SchemaVersionsSuccess></IsothermResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `IsothermResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `SchemaVersionsSuccess` | Successful request. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-isotherm-api).

Error codes: 10, 20, 40

### Set isotherm mode

Use `/axis-cgi/isotherm/setmode.cgi` to enable and disable isothermal imaging.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/setmode.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/isotherm/setmode.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `mode=<string>` | `enabled` `disabled` | `enabled` = Enable isothermal imaging.`disabled` = Disable isothermal imaging. |

**Response**

Responses from `/axis-cgi/isotherm/setmode.cgi`

**Success**

If the request is successful, isothermal imaging is enabled or disabled and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-isotherm-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-isotherm-api).

Error codes: 10, 20, 40

### Get isotherm mode

Use `/axis-cgi/isotherm/getmode.cgi` to check if isothermal imaging is enabled.

**Request**

-   **Security level**: Administrator, Operator, Viewer

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/getmode.cgi"
```

```bash
GET /axis-cgi/isotherm/getmode.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/isotherm/getmode.cgi`

**Success**

A successful request returns the isotherm mode.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><IsothermResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">    <Success>        <GetModeSuccess>            <Mode>\[enabled/disabled\]</Mode>        </GetModeSuccess>    </Success></IsothermResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `IsothermResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetModeSuccess` | Successful request. |
| `Mode` | The current mode.`enabled` = Isothermal imaging is enabled.`disabled` = Isothermal imaging is disabled. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-isotherm-api).

Error codes: 10, 20, 40

### Set limits

Use `/axis-cgi/isotherm/setlimits.cgi` to set temperature limits for the isotherm palette temperature ranges. There are three limits: upper, middle and lower.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/setlimits.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/isotherm/setlimits.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `upper=<integer>` | Integers | The upper temperature limit.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `middle=<integer>` | Integers | The middle temperature limit.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `lower=<integer>` | Integers | The lower temperature limit.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |

**Response**

Responses from `/axis-cgi/isotherm/setlimits.cgi`

**Success**

If the request is successful, the temperature limits are set and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-isotherm-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-isotherm-api).

Error codes: 10, 20, 40

### Get limits

Use `/axis-cgi/isotherm/getlimits.cgi` to retrieve the current temperature limits for the isotherm palette temperature ranges.

**Request**

-   **Security level**: Administrator, Operator, Viewer

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/isotherm/getlimits.cgi"
```

```bash
GET /axis-cgi/isotherm/getlimits.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/isotherm/getlimits.cgi`

**Success**

A successful request returns the temperature limits.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><IsothermResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">    <Success>        <GetLimitsSuccess>            <Upper>\[upper temperature\]</Upper>            <Middle>\[middle temperature\]</Middle>            <Lower>\[lower temperature\]</Lower>        </GetLimitsSuccess>    </Success></IsothermResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `IsothermResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetLimitsSuccess` | Successful request. |
| `Upper` | The upper temperature limit. Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `Middle` | The middle temperature limit. Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `Lower` | The lower temperature limit. Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-isotherm-api).

Error codes: 10, 20, 40

### General success response

General success response from Isotherm API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><IsothermResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">    <GeneralSuccess /></IsothermResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `IsothermResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Successful request. |

### General error response

General error response from Isotherm API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><IsothermResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Isotherm1.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></IsothermResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `IsothermResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |

## Temperature alarm API
### Description

VAPIX® Temperature alarm API is used to set up and configure temperature alarm zones in the image from a thermal camera. The API is also used to retrieve the spot temperature of a point in the image.

A temperature alarm zone is an area in the image where the monitored area’s temperature is measured. An alarm is triggered and a temperature detection event is emitted if the measured temperature rises above or falls below the threshold temperature, or if the temperature increases too quickly. As different areas in a temperature zone usually have different temperatures, it is possible to configure the zone to use the maximum or minimum temperature to determine when alarms are triggered.

Supported functionality:

-   Set the temperature scale to Celsius or Fahrenheit.
-   Set, get and remove temperature alarm zones.
-   Get the zone status. The status includes the zone’s average, maximum and minimum temperatures and if an alarm has been triggered.
-   Get the spot temperature of a point in the image.

To improve the temperature measurement, the monitored object’s emissivity can be specified when setting up an alarm zone and when requesting the spot temperature. Emissivity is a measure of a material’s ability to emit thermal radiation and is a number between 0 and 1, where 1 is the emissivity of a black body. The temperature measurement is more precise for objects with high emissivity and Axis temperature alarm cameras have a lower emissivity limit of 0.5.

#### Identification

VAPIX® Temperature alarm API is available if:

-   **Property**: `Properties.TemperatureAlarm.TemperatureDetection=yes`
-   **AXIS OS**: 5.55 and later

### Common examples

Retrieve supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/schemaversions.cgi"
```

```bash
GET /axis-cgi/temperature\_alarm/schemaversions.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><TemperatureResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">  <SchemaVersionsSuccess>    <SchemaVersion>      <VersionNumber>1.0</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>    \[...\]  </SchemaVersionsSuccess></TemperatureResponse>
```

Set the temperature scale to Celsius.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/settemperaturescale.cgi?unit=Celsius"
```

```bash
GET /axis-cgi/temperature\_alarm/settemperaturescale.cgi?unit=CelsiusHost: <servername>
```

Create a temperature alarm zone. The zone is specified by a zone id, a user-friendly zone name, the zone coordinates and the emissivity of the objects in the zone. The arguments `temperature`, `temperaturetype`, `detectiontype` and `delaytime` control when alarms are triggered.

The following zone will trigger an alarm when the zone’s maximum temperature rises above 85 degrees.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=85&temperaturetype=maximum&detectiontype=above&delaytime=5"
```

```bash
GET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=85&temperaturetype=maximum&detectiontype=above&delaytime=5Host: <servername>
```

The following zone will trigger an alarm when the zone’s minimum temperature falls below 0 degrees.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=0&temperaturetype=minimum&detectiontype=below&delaytime=5"
```

```bash
GET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=0&temperaturetype=minimum&detectiontype=below&delaytime=5Host: <servername>
```

The following zone will trigger an alarm when the zone’s minimum temperature rises above 22 degrees.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=22&temperaturetype=minimum&detectiontype=above&delaytime=5"
```

```bash
GET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=22&temperaturetype=minimum&detectiontype=above&delaytime=5Host: <servername>
```

The following zone will trigger an alarm when the temperature increases more than 20 degrees in 30 seconds.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=20&temperaturetype=maximum&detectiontype=increase&delaytime=30" \\  --data '\`\`\`httpGET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=20&temperaturetype=maximum&detectiontype=increase&delaytime=30Host: <servername>'
```

```bash
GET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=20&temperaturetype=maximum&detectiontype=increase&delaytime=30Host: <servername>\`\`\`httpGET /axis-cgi/temperature\_alarm/set.cgi?id=0&name=zone0&left=100&right=2000&top=200&bottom=2500&emissivity=0.87&temperature=20&temperaturetype=maximum&detectiontype=increase&delaytime=30Host: <servername>
```

Retrieve all alarm zones.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/get.cgi" \\  --data '\`\`\`httpGET /axis-cgi/temperature\_alarm/get.cgiHost: <servername>'
```

```bash
GET /axis-cgi/temperature\_alarm/get.cgiHost: <servername>\`\`\`httpGET /axis-cgi/temperature\_alarm/get.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><TemperatureResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">  <Success>    <GetSuccess>      <AlarmZone>        <ZoneId>0</ZoneId>        <Name>zone0</Name>        <Xleft>100</Xleft>        <Xright>2000</Xright>        <Ytop>200</Ytop>        <Ybottom>2500</Ybottom>        <Emissivity>0.87</Emissivity>        <DetectionType>above</DetectionType>        <Temperature>85</Temperature>        <TemperatureType>maximum</TemperatureType>        <DelayTime>5</DelayTime>      </AlarmZone>    </GetSuccess>  </Success></TemperatureResponse>
```

Remove an alarm zone.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/remove.cgi?id=2"
```

```bash
GET /axis-cgi/temperature\_alarm/remove.cgi?id=2Host: <servername>
```

Get the zone status. The status shows the zone’s average, maximum and minimum temperatures, and if an alarm is triggered.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/getzonestatus.cgi?id=2" \\  --data '\`\`\`httpGET /axis-cgi/temperature\_alarm/getzonestatus.cgiHost: <servername>'
```

```bash
GET /axis-cgi/temperature\_alarm/getzonestatus.cgi?id=2Host: <servername>\`\`\`httpGET /axis-cgi/temperature\_alarm/getzonestatus.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><TemperatureResponse SchemaVersion="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">  <Success>    <GetZoneStatusSuccess>      <AlarmZone>        <ZoneId>0</ZoneId>        <AverageTemperature>25</AverageTemperature>        <MinimumTemperature>22</MinimumTemperature>        <MaximumTemperature>27</MaximumTemperature>        <Triggered>No</Triggered>      </AlarmZone>    </GetZoneStatusSuccess>  </Success></TemperatureResponse>
```

Get the spot temperatures, that is the temperature of a point in the image. The point is specified by its X and Y coordinates as `x,y` where the comma in the request is percent-encoded. To improve the temperature measurement, the point’s emissivity is also specified.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/getspottemperature.cgi?coordinates=4598%2C6742&emissivity=0.98"
```

```bash
GET /axis-cgi/temperature\_alarm/getspottemperature.cgi?coordinates=4598%2C6742&emissivity=0.98Host: <servername>
```

The temperature detection event in the event stream. Here, the alarm is triggered (`AlarmActive=1`) in the zone with zone ID 0.

```bash
<tt:MetadataStream xmlns:tt="http://www.onvif.org/ver10/schema">    <tt:Event xmlns:tt="http://www.onvif.org/ver10/schema">        <wsnt:NotificationMessage            xmlns:tns1="http://www.onvif.org/ver10/topics"            xmlns:tnsaxis="http://www.axis.com/2009/event/topics"            xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"            xmlns:wsa5="http://www.w3.org/2005/08/addressing">            <wsnt:Topic Dialect="http://docs.oasis-open.org/wsn/t-1/TopicExpression/Simple">                tns1:VideoSource/tnsaxis:TemperatureDetection            </wsnt:Topic>            <wsnt:ProducerReference>                <wsa5:Address>uri://621c7eac-a3ee-4372-9e44-98fac02827d5/ProducerReference</wsa5:Address>            </wsnt:ProducerReference>            <wsnt:Message>                <tt:Message UtcTime="1971-04-30T04:28:26.976004Z" PropertyOperation="Initialized">                    <tt:Source>                        <tt:SimpleItem Name="TemperatureZone" Value="0" />                        <tt:SimpleItem Name="VideoSourceConfigurationToken" Value="1" />                    </tt:Source>                    <tt:Key />                    <tt:Data>                        <tt:SimpleItem Name="AlarmActive" Value="1" />                    </tt:Data>                </tt:Message>            </wsnt:Message>        </wsnt:NotificationMessage>    </tt:Event></tt:MetadataStream>
```

For information about the event declaration, see [Temperature detection event](#temperature-detection-event). Use `GetEventInstances` from [Event and action services](/vapix/network-video/event-and-action-services/).

### Get schema versions

Use `/axis-cgi/temperature_alarm/schemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/schemaversions.cgi"
```

```bash
GET /axis-cgi/temperature\_alarm/schemaversions.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/temperature_alarm/schemaversions.cgi`

**Success**

A successful request returns the supported schema versions.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        \[...\]    </SchemaVersionsSuccess></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `SchemaVersionsSuccess` | Successful request. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Set temperature scale

Use `/axis-cgi/temperature_alarm/settemperaturescale.cgi` to set the temperature scale to Celsius or Fahrenheit.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/settemperaturescale.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/temperature\_alarm/settemperaturescale.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `unit=<string>` | `Celsius` `Fahrenheit` | The temperature scale to use. |

**Response**

Responses from `/axis-cgi/temperature_alarm/settemperaturescale.cgi`

**Success**

If the request is successful, the temperature scale is set and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-temperature-alarm-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Set temperature alarm zone

Use `/axis-cgi/temperature_alarm/set.cgi` to create or update a temperature alarm zone.

A temperature alarm zone is identified by its zone ID. The zone is set up using the `X` coordinates `left` and `right` and the `Y` coordinates `top` and `bottom`. The point `X=0`, `Y=0` is the image upper left corner. If the image is rotated or mirrored, use the coordinates of the unrotated and unmirrored image when setting up the zone.

Arguments `temperature`, `temperaturetype`, `detectiontype` and `delaytime` control when alarms are triggered. `detectiontype` specifies if the alarm should be triggered above or below a threshold temperature or when the temperature increases.

-   For `detectiontype=above` and `detectiontype=below`, `temperature` is the threshold temperature and `delaytime` is the time between successive temperature measurements.
-   For `detectiontype=increase`, `temperature` is the change in temperature and `delaytime` is the change in time. That is, `temperature=20` and `delaytime=30` means that the alarm is triggered if the temperature increases more than 20 degrees in 30 seconds.
-   `temperaturetype` controls whether the zone’s maximum or minimum temperature determines when alarms are triggered. `detectiontype=above` and `temperaturetype=minimum` means that the alarm is triggered if the zone’s minimum temperature rises above the threshold.

Argument `emissivity` is the emissivity of objects in the zone.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/set.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/temperature\_alarm/set.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `id=<integer>` | `0...` | Required. The zone ID. |
| `name=<string>` | String | A user-friendly name for the zone. |
| `left=<integer>` | `0...9999` | The zone’s left X coordinate. |
| `right=<integer>` | `0...9999` | The zone’s right X coordinate. |
| `top=<integer>` | `0...9999` | The zone’s top Y coordinate. |
| `bottom=<integer>` | `0...9999` | The zone’s bottom Y coordinate. |
| `emissivity=<string>` | `0.5...1` | Emissivity of the objects in the zone. Used to improve temperature measurement.Default: `0.95` |
| `detectiontype=<string>` | `above` `below` `increase` | `above` = The alarm is triggered when the temperature rises above the threshold temperature.`below` = The alarm is triggered when the temperature falls below the threshold temperature.`increase` = The alarm is triggered when the temperature increases more than `temperature` degrees in `delaytime` seconds. |
| `temperature=<integer>` | Integer | The threshold temperature.For `detectiontype=increase`: The threshold temperature is the maximum allowed increase in temperature during the time specified by `delaytime`.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi`, see [Set temperature scale](#set-temperature-scale). |
| `temperaturetype=<string>` | `maximum` `minimum` | Different areas in the zone usually have different temperatures. `temperaturetype` defines if the zone’s maximum or minimum temperature should be used to determine when alarms are triggered.`maximum` = The zone’s maximum temperature determines when alarms are triggered.`minimum` = The zone’s minimum temperature determines when alarms are triggered. |
| `delaytime=<integer>` | `0 ... 60` | Time between successive temperature measurement.Unit: seconds |

**Response**

Responses from `/axis-cgi/temperature_alarm/set.cgi`

**Success**

If the request is successful, the zone is created and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-temperature-alarm-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Get temperature alarm zone

Use `/axis-cgi/temperature_alarm/get.cgi` to retrieve the current temperature alarm zones.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/get.cgi"
```

```bash
GET /axis-cgi/temperature\_alarm/get.cgiHost: <servername>
```

This CGI has no arguments.

**Response**

Responses from `/axis-cgi/temperature_alarm/get.cgi`

**Success**

If the request is successful, the response returns all temperature alarm zones.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <Success>        <GetSuccess>            <AlarmZone>                <ZoneId>\[ID\]</ZoneId>                <Name>\[Name\]</Name>                <Xleft>\[Xleft\]</Xleft>                <Xright>\[Xright\]</Xright>                <Ytop>\[Ytop\]</Ytop>                <Ybottom>\[Ybottom\]</Ybottom>                <Emissivity>\[Emissivity\]</Emissivity>                <DetectionType>\[above/below/increase\]</DetectionType>                <Temperature>\[Temperature\]</Temperature>                <TemperatureType>\[maximum/minimum\]</TemperatureType>                <DelayTime>\[Delay time\]</DelayTime>            </AlarmZone>            \[...\]        </GetSuccess>    </Success></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetSuccess` | Successful request |
| `AlarmZone` | Contains the properties of one alarm zone. |
| `ZoneId` | The zone ID. |
| `Name` | The zone’s name. |
| `Xleft` | The left X coordinate. |
| `Xright` | The right X coordinate. |
| `Ytop` | The top Y coordinate. |
| `Ybottom` | The bottom Y coordinate. |
| `Emissivity` | The emissivity. |
| `DetectionType` | When the alarm should trigger. |
| `Temperature` | The threshold temperature. |
| `TemperatureType` | If the alarm should trigger at the zone’s maximum or minimum temperature. |
| `DelayTime` | The delay time. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Get zone status

Use `/axis-cgi/temperature_alarm/getzonestatus.cgi` to retrieve the status of each temperature alarm zone. The zone status includes the maximum, minimum and average temperatures and if an alarm has been triggered.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/getzonestatus.cgi"
```

```bash
GET /axis-cgi/temperature\_alarm/getzonestatus.cgiHost: <servername>
```

This CGI has no arguments.

**Response**

Responses from `/axis-cgi/temperature_alarm/getzonestatus.cgi`

**Success**

If the request is successful, the response returns the status of all temperature alarm zones.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <Success>        <GetZoneStatusSuccess>            <AlarmZone>                <ZoneId>\[ID\]</ZoneId>                <AverageTemperature>\[Average temperature\]</AverageTemperature>                <MinimumTemperature>\[Minimum temperature\]</MinimumTemperature>                <MaximumTemperature>\[Maximum temperature\]</MaximumTemperature>                <Triggered>\[Yes/No\]</Triggered>            </AlarmZone>            \[...\]        </GetZoneStatusSuccess>    </Success></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetZoneStatusSuccess` | Successful request |
| `AlarmZone` | Contains the status of one alarm zone. |
| `ZoneId` | The zone ID. |
| `AverageTemperature` | The average temperature in the zone.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `MinimumTemperature` | The minimum temperature in the zone.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `MaximumTemperature` | The maximum temperature in the zone.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |
| `Triggered` | `Yes` = An alarm is triggered.`No` = No alarm is triggered.`tns1:VideoSource/tnsaxis:TemperatureDetection` is a stateful event. `Triggered` will remain `Yes` as long as the event is active. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Remove temperature alarm zone

Use `/axis-cgi/temperature_alarm/remove.cgi` to remove a temperature alarm zone.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/remove.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/temperature\_alarm/remove.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `id=<integer>` | `0...` | The zone ID of the zone to remove. |

**Response**

Responses from `/axis-cgi/temperature_alarm/remove.cgi`

**Success**

If the request is successful, the zone is removed and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-temperature-alarm-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### Get spot temperature

Use `/axis-cgi/temperature_alarm/getspottemperature.cgi` to retrieve the temperature at a certain point in the image. To improve the temperature measurement, specify the emissivity of the point.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/temperature\_alarm/getspottemperature.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/temperature\_alarm/getspottemperature.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `coordinates=<integer>,<integer>` | `x,y` | The `X` and `Y` coordinates of the requested point.`X` and `Y` are numbers between 0 and 9999 where the point `X=0`, `Y=0` is the image upper left corner. |
| `emissivity=<string>` | `0.5...1` | Emissivity of the object. Used to improve temperature measurement.Default: `0.95` |

**Response**

Responses from `/axis-cgi/temperature_alarm/getspottemperature.cgi`

**Success**

If the request is successful, the response returns the temperature of the requested point.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <Success>        <GetSpotTemperatureSuccess>            <SpotTemperature>\[Temperature\]</SpotTemperature>        </GetSpotTemperatureSuccess>    </Success></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetSpotTemperatureSuccess` | Successful request |
| `SpotTemperature` | The returned spot temperature.Unit: The unit set by `/axis-cgi/temperature_alarm/settemperaturescale.cgi` |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-temperature-alarm-api).

Error codes: 10, 20, 40

### General success response

General success response from Temperature alarm API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <GeneralSuccess /></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Successful request. |

### General error response

General error response from Temperature alarm API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><TemperatureResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/Temperature1.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></TemperatureResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `TemperatureResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |

### Temperature detection event

The `tns1:VideoSource/tnsaxis:TemperatureDetection` event is emitted when an alarm is triggered in a temperature alarm zone.

Event declaration:

```bash
<tns1:VideoSource aev:NiceName="Video source">    <tnsaxis:TemperatureDetection wstop:topic="true" aev:NiceName="Temperature Detection">        <aev:MessageInstance aev:isProperty="true">            <aev:SourceInstance>                <aev:SimpleItemInstance aev:NiceName="Temperature Zone" Type="xsd:int" Name="TemperatureZone">                    <aev:Value aev:NiceName="zone2">2</aev:Value>                    <aev:Value aev:NiceName="zone1">1</aev:Value>                    <aev:Value aev:NiceName="zone0">0</aev:Value>                </aev:SimpleItemInstance>                <aev:SimpleItemInstance                    aev:NiceName="Video source configuration token"                    Type="xsd:int"                    Name="VideoSourceConfigurationToken">                    <aev:Value>1</aev:Value>                </aev:SimpleItemInstance>            </aev:SourceInstance>            <aev:DataInstance>                <aev:SimpleItemInstance                    aev:NiceName="Alarm active"                    Type="xsd:boolean"                    Name="AlarmActive"                    isPropertyState="true" />            </aev:DataInstance>        </aev:MessageInstance>    </tnsaxis:TemperatureDetection></tns1:VideoSource>
```

The `SourceInstance` contains two `SimpleItemInstance`:s

-   The `SimpleItemInstance` with `Name="TemperatureZone"` contains the defined temperature alarm zones.
-   The `SimpleItemInstance` with `Name="VideoSourceConfigurationToken"` contains the video channel.

The `DataInstance` contains the alarm status: active or inactive.