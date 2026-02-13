---
title: Orientation API
url: "https://developer.axis.com/vapix/network-video/orientation-api/"
category: vapix
subcategory: network-video
sha256: 5c405e9545feeb3339916b943ce5878217ab4529423094da861b634a6ad84e7f
scraped_at: "2026-01-09T15:20:33.032Z"
page_height: 11515
---

# Orientation API

## Description

VAPIX® Orientation API is used to retrieve information about the camera lens orientation. The API is available in products with built-in orientation devices such as gyroscopes and accelerometers.

Supported functionality:

-   Get the longitudinal angle.
-   Get the lateral angle.

**Longitudinal angle**. The longitudinal angle (0 to 359 degrees) is the lens’ rotation around its longitudinal axis.

![Longitudinal angle](/assets/images/orientation-api.t10052884-13afc35b9ebadeb5dbb7d336cf2e0a9a.jpg)

**Lateral angle**. The lateral angle (0 to 180 degrees) is the angle between the lens’ longitudinal axis and a line perpendicular to the ground surface. 0 degrees represents a lens pointing straight downwards. 180 degrees represents a lens pointing straight upwards.

![Lateral angle](/assets/images/orientation-api.t10052883-03bfe09cde02ed8af56d12997ca5d781.jpg)

### Identification

VAPIX® Orientation API is available if:

-   **Property**: `Properties.Orientation.Reporting=yes`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Retrieve supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getschemaversions.cgi"
```

```bash
GET /axis-cgi/orientation/getschemaversions.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><OrientationResponse xmlns="http://www.axis.com/vapix/http\_cgi/orientation1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1" SchemaVersion="1.0">  <Success>    <GetSchemaVersionsSuccess>      <SchemaVersion>        <VersionNumber>1.0</VersionNumber>        <Deprecated>false</Deprecated>      </SchemaVersion>    </GetSchemaVersionsSuccess>  </Success></OrientationResponse>
```

Get the longitudinal angle.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getlongitudinalvalue.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/orientation/getlongitudinalvalue.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><OrientationResponse xmlns="http://www.axis.com/vapix/http\_cgi/orientation1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1" SchemaVersion="1.0">  <Success>    <GetLongitudinalValueSuccess>      <LongitudinalValue>        <Value>180</Value>      </LongitudinalValue>    </GetLongitudinalValueSuccess>  </Success></OrientationResponse>
```

Get the lateral angle.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getlateralvalue.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/orientation/getlateralvalue.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><OrientationResponse xmlns="http://www.axis.com/vapix/http\_cgi/orientation1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1" SchemaVersion="1.0">  <Success>    <GetLateralValueSuccess>      <LateralValue>        <Value>72</Value>      </LateralValue>    </GetLateralValueSuccess>  </Success></OrientationResponse>
```

## Get schema versions

Use `/axis-cgi/orientation/getschemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getschemaversions.cgi"
```

```bash
GET /axis-cgi/orientation/getschemaversions.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/orientation/getschemaversions.cgi`

**Success**

A successful request returns the supported schema version.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><OrientationResponse    xmlns="http://www.axis.com/vapix/http\_cgi/orientation1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1"    SchemaVersion="1.0">    <Success>        <GetSchemaVersionsSuccess>            <SchemaVersion>                <VersionNumber>\[major.minor\]</VersionNumber>                <Deprecated>\[true/false\]</Deprecated>            </SchemaVersion>            \[...\]        </GetSchemaVersionsSuccess>    </Success></OrientationResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `OrientationResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request. |
| `GetSchemaVersionsSuccess` | Successful response from `/axis-cgi/orientation/getschemaversions.cgi`. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## Get longitudinal angle

Use `/axis-cgi/orientation/getlongitudinalvalue.cgi` to retrieve the longitudinal angle.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getlongitudinalvalue.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/orientation/getlongitudinalvalue.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Response**

Responses from `/axis-cgi/orientation/getlongitudinalvalue.cgi`

**Success**

A successful request returns the lateral angle.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><OrientationResponse    xmlns="http://www.axis.com/vapix/http\_cgi/orientation1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1"    SchemaVersion="1.0">    <Success>        <GetLongitudinalValueSuccess>            <LongitudinalValue>                <Value>\[angle\]</Value>            </LongitudinalValue>        </GetLongitudinalValueSuccess>    </Success></OrientationResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `OrientationResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request. |
| `GetLongitudinalValueSuccess` | Successful response from `/axis-cgi/orientation/getlongitudinalvalue.cgi`. |
| `LongitudinalValue` | Contains the longitudinal angle. |
| `Value` | The angle in degrees. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## Get lateral angle

Use `/axis-cgi/orientation/getlateralvalue.cgi` to retrieve the lateral angle.

**Request**

-   **Security level**: Administrator, Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/orientation/getlateralvalue.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/orientation/getlateralvalue.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Response**

Responses from `/axis-cgi/orientation/getlateralvalue.cgi`

**Success**

A successful request returns the lateral angle.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><OrientationResponse    xmlns="http://www.axis.com/vapix/http\_cgi/orientation1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1"    SchemaVersion="1.0">    <Success>        <GetLateralValueSuccess>            <LateralValue>                <Value>\[angle\]</Value>            </LateralValue>        </GetLateralValueSuccess>    </Success></OrientationResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `OrientationResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request. |
| `GetLateralValueSuccess` | Successful response from `/axis-cgi/orientation/getlateralvalue.cgi`. |
| `LateralValue` | Contains the lateral angle. |
| `Value` | The angle in degrees. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response).

Error codes: 10, 20, 40

## General error response

General error response in the orientation API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><OrientationResponse    xmlns="http://www.axis.com/vapix/http\_cgi/orientation1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/orientation1 http://www.axis.com/vapix/http\_cgi/orientation1"    SchemaVersion="1.0">    <Error>        <GeneralError>            <ErrorCode>\[error code\]</ErrorCode>            <ErrorDescription>\[description\]</ErrorDescription>        </GeneralError>    </Error></OrientationResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `OrientationResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Error` | The request contains errors. |
| `GeneralError` | General error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |