---
title: Shock detection API
url: "https://developer.axis.com/vapix/network-video/shock-detection-api/"
category: vapix
subcategory: network-video
sha256: 12200132dc3b77a7db5f6136796fc3afb340b593035d30e6fb6826a9597ee29f
scraped_at: "2026-01-09T15:20:59.371Z"
page_height: 15376
---

# Shock detection API

## Description

Shock detection is available in Axis products with built-in orientation devices such as accelerometers or gyroscopes. When shock detection is enabled, the camera’s position and acceleration is monitored. If the camera is tilted or displaced from its current position, or if the camera is subject to punches, hard blows or similar, an alarm is triggered and the Axis product emits a shock detection event.

The alarm is triggered immediately when the camera is punched or displaced. There is no pre-trigger time. After the alarm, position and acceleration monitoring continues from the camera’s new position. To prevent multiple events for the same displacement, a new shock detection event will not be emitted until 5 seconds has passed.

Shock detection sensitivity can be set to an integer between 0 and 100. Low sensitivity means that a hit must be quite powerful to trigger an alarm. High sensitivity means that very small displacements, including vibrations, will be trigger alarms.

The Shock detection API is used to enable, disable and adjust the Axis product’s shock detection functionality.

Supported functionality:

-   Enable and disable shock detection
-   Control the sensitivity level

### Identification

VAPIX Shock detection API is available if:

-   **Property**: `root.Properties.Tampering.ShockDetection=yes`
-   **AXIS OS**: 5.50 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Retrieve supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getschemaversion.cgi"
```

```bash
GET /axis-cgi/shockdetection/getschemaversion.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-type: text/xml<?xml version="1.0" encoding="utf-8"?><ShockDetectionResponse xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1" SchemaVersion="1.0">  <Success>    <GetSchemaVersionsSuccess>      <SchemaVersion>        <VersionNumber>1.0</VersionNumber>        <Deprecated></Deprecated>      </SchemaVersion>    </GetSchemaVersionsSuccess>  </Success></ShockDetectionResponse>
```

Enable shock detection in the Axis product.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/setenabled.cgi?schemaversion=1&enabled=true"
```

```bash
GET /axis-cgi/shockdetection/setenabled.cgi?schemaversion=1&enabled=trueHost: <servername>
```

Check if shock detection is enabled.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getenabled.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/shockdetection/getenabled.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-type: text/xml<?xml version="1.0" encoding="UTF-8"?><ShockDetectionResponse xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1" SchemaVersion="1.0">  <Success>    <GetEnabledSuccess>      <Enabled>true</Enabled>    </GetEnabledSuccess>  </Success></ShockDetectionResponse>
```

Set shock detection sensitivity to 60.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/setsensitivitylevel.cgi?schemaversion=1&level=60"
```

```bash
GET /axis-cgi/shockdetection/setsensitivitylevel.cgi?schemaversion=1&level=60Host: <servername>
```

Retrieve the shock detection sensitivity level.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getsensitivitylevel.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/shockdetection/getsensitivitylevel.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-type: text/xml<?xml version="1.0" encoding="UTF-8"?><ShockDetectionResponse xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1" SchemaVersion="1.0">  <Success>    <GetSensitivityLevelSuccess>      <SensitivityLevel>        <Level>60</Level>      </SensitivityLevel>    </GetSensitivityLevelSuccess>  </Success></ShockDetectionResponse>
```

## Check if enabled

Use `/axis-cgi/shockdetection/getenabled.cgi` to check if shock detection is enabled.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getenabled.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/shockdetection/getenabled.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Response**

Responses from `/axis-cgi/shockdetection/getenabled.cgi`

**Success**

A successful request returns `true` is shock detection is enabled and `false` if shock detection is disabled.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ShockDetectionResponse    xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1"    SchemaVersion="1.0">    <Success>        <GetEnabledSuccess>            <Enabled>\[true | false\]</Enabled>        </GetEnabledSuccess>    </Success></ShockDetectionResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ShockDetectionResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetEnabledSuccess` | Successful request. |
| `Enabled` | `true` = Shock detection is enabled.`false` = Shock detection is disabled. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## Enable shock detection

Use `/axis-cgi/shockdetection/setenabled.cgi` to enable and disable shock detection.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/setenabled.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/shockdetection/setenabled.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `enabled=<boolean>` | `true` `false` | `true` = Enable shock detection.`false` = Disable shock detection. |

**Response**

Responses from `/axis-cgi/shockdetection/setenabled.cgi`

**Success**

If the request is successful, shock detection is enabled and a `GeneralSuccess` response is returned. See [General success response](#general-success-response).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## Get sensitivity level

Use `/axis-cgi/shockdetection/getsensitivitylevel.cgi` to retrieve the current sensitivity level.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getsensitivitylevel.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/shockdetection/getsensitivitylevel.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Response**

Responses from `/axis-cgi/shockdetection/getsensitivitylevel.cgi`

**Success**

A successful request returns the current sensitivity level.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ShockDetectionResponse    xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1"    SchemaVersion="1.0">    <Success>        <GetSensitivityLevelSuccess>            <SensitivityLevel>                <Level>\[level\]</Level>            </SensitivityLevel>        </GetSensitivityLevelSuccess>    </Success></ShockDetectionResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ShockDetectionResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetSensitivityLevelSuccess` | Successful request |
| `SensitivityLevel` | Contains the sensitivity level. |
| `Level` | Integer defining the sensitivity level. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## Set sensitivity level

Use `/axis-cgi/shockdetection/setsensitivitylevel.cgi` to set the shock detection sensitivity level.

Shock detection sensitivity can be set to an integer between 0 and 100. Low sensitivity means that a hit must be quite powerful to trigger an alarm. High sensitivity means that very small displacements, including vibrations, will be trigger alarms.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/setsensitivitylevel.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/shockdetection/setsensitivitylevel.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `level=<integer>` | `0 .. 100` | The shock detection sensitivity level.`0` = Low sensitivity`100` = High sensitivity |

**Response**

Responses from `/axis-cgi/shockdetection/setsensitivitylevel.cgi`

**Success**

If the request is successful, the sensitivity level is set to the submitted value and a `GeneralSuccess` response is returned. See [General success response](#general-success-response).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 30, 40

## Get schema versions

Use `/axis-cgi/shockdetection/getschemaversion.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/shockdetection/getschemaversion.cgi"
```

```bash
GET /axis-cgi/shockdetection/getschemaversion.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/shockdetection/getschemaversion.cgi`

**Success**

A successful request returns the supported schema version.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ShockDetectionResponse    xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1"    SchemaVersion="1.0">    <Success>        <GetSchemaVersionsSuccess>            <SchemaVersion>                <VersionNumber>\[major.minor\]</VersionNumber>                <Deprecated>\[true/false\]</Deprecated>            </SchemaVersion>        </GetSchemaVersionsSuccess>    </Success></ShockDetectionResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ShockDetectionResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GetSchemaVersionsSuccess` | Successful request |
| `SchemaVersion` | Contains the schema version |
| `VersionNumber` | Schema version in format `major.minor` where `major` is the major version and `minor` the minor version. |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used.Default: `false` |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## General success response

General success response in Shock Detection API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><ShockDetectionResponse    xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1"    SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></ShockDetectionResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ShockDetectionResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request |
| `GeneralSuccess` | Successful request |

## General error response

General error response in Shock detection API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ShockDetectionResponse    xmlns="http://www.axis.com/vapix/http\_cgi/shockdetection1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/shockdetection1 http://www.axis.com/vapix/http\_cgi/shockdetection1"    SchemaVersion="1.0">    <Error>        <GeneralError>            <ErrorCode>\[error code\]</ErrorCode>            <ErrorDescription>\[description\]</ErrorDescription>        </GeneralError>    </Error></ShockDetectionResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ShockDetectionResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `30` | Unable to set shock detection sensitivity. Specified value is out of range. | `/axis-cgi/shockdetection/setsensitivitylevel.cgi` |
| `40` | Specified version is not supported. | All |

## Shock detection event

The shock detection event `tns1:Device/tnsaxis:Tampering/ShockDetected` is a stateless event.

To retrieve the event declaration, use `aev:GetEventInstances`.

Event declaration:

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:Tampering aev:NiceName="Tampering">        <ShockDetected wstop:topic="true" aev:NiceName="Shock Detected">            <aev:MessageInstance>                <aev:SourceInstance>                    <aev:SimpleItemInstance aev:NiceName="Channel" Type="xsd:int" Name="channel">                        <aev:Value>1</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance />            </aev:MessageInstance>        </ShockDetected>    </tnsaxis:Tampering></tns1:Device>
```

The topic is `tns1:Device/tnsaxis:Tampering/ShockDetected`. `Channel` is the video channel and is intended for future use.