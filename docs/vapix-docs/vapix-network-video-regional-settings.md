---
title: Regional settings
url: "https://developer.axis.com/vapix/network-video/regional-settings/"
category: vapix
subcategory: network-video
sha256: 71957982468f5dd819fe6cfd793fda97db482ccb83674e40bb16e007040ecc7b
scraped_at: "2026-01-09T15:20:52.855Z"
page_height: 12124
---

# Regional settings

## Description

The Regional settings API makes it possible to store regional settings in the camera, such as different units for length. This information can then be used to determine how these units should be presented. This API does not have any methods that lets you convert the units directly.

### Model

The API consists of the CGI `/axis-cgi/regionalsettings.cgi` and the following methods:

| Method | Description |
| --- | --- |
| `setRegionalSettings` | Set the regional settings. |
| `getRegionalSettings` | Receive the current regional settings. |
| `getSupportedVersions` | Receive a list of supported API versions. |

### Identification

-   **Property**: `root.Properties.RegionalSettings.RegionalSettings="yes"`
-   **AXIS OS**: 9.20 and later
-   **API Discovery**: `id=regional-settings`

An alternative way to identify the API is to check for the existence of the `/axis-cgi/regionalsettings.cgi`.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Get supported versions

Use this example to view a list of API versions supported by the device.

1.  Request a list of supported API versions:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

a) Successful response example listing supported API versions.

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "1.1"\]    }}
```

b) Failed response example.

```bash
{    "apiVersion": "1.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 1000,        "message": "Internal error"    }}
```

For further instructions, see [getSupportedVersions](#getsupportedversions) .

### Get regional settings

Use this example to request information on how to present length in either meters or US customary feet.

1.  Request the current regional settings.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{    "apiVersion": "1.0",    "method": "getRegionalSettings",    "context": "abc"}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "method": "getRegionalSettings",    "context": "abc"}
```

2.  Parse the JSON response.

a) Successful response example indicating that metric units have been selected.

```bash
{    "apiVersion": "1.0",    "method": "getRegionalSettings",    "context": "abc",    "data": {        "units": {            "length": "metric"        }    }}
```

b) Failed response example indicating when an unsupported method has been called.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "unknownMethod",    "error": {        "code": 1002,        "message": "Unknown method"    }}
```

For further instructions, see [getRegionalSettings](#getregionalsettings).

### Set regional settings

Use this example to apply a regional setting.

1.  Update the regional length settings. In this example we will use the US customary units.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{    "apiVersion": "1.0",    "method": "setRegionalSettings",    "context": "abc",    "params": {        "units": {            "length": "us\_customary"        }    }}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "method": "setRegionalSettings",    "context": "abc",    "params": {        "units": {            "length": "us\_customary"        }    }}
```

2.  Parse the JSON response.

a) Successful response example.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setRegionalSettings"}
```

b) Failed response example that appears when the request doesn’t contain any parameters, or an invalid value.

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setRegionalSettings",    "error": {        "code": 1003,        "message": "Invalid argument"    }}
```

For further instructions, see [setRegionalSettings](#setregionalsettings).

## API specification
### getSupportedVersions

This CGI method can be used to retrieve a list of supported API versions.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The client sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | Specifies that the `getSupportedVersions` method is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | A text string that is echoed back if it was provided by the client in the corresponding request. |
| `method="getSupportedVersions"` | The performed method. |
| `data.apiVersions[]=<list of versions>` | Lists all supported major versions along with their highest supported minor version. |
| `<list of versions>` | List of "<Major>.<Minor>" versions, e.g. \["1.4", "2.5"\] |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### getRegionalSettings

This CGI method that can be used to retrieve the current regional settings, which is useful when you wish to determine the length unit in the GUI.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": "getRegionalSettings"}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": "getRegionalSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The client sets this value and the server echoes the data back in the response (optional). |
| `method="getRegionalSettings"` | Specifies that the `getRegionalSettings` method is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion":"<major>.<minor>",  "method": "getRegionalSettings",  "context": "<string>",  "data": {    "units": {      "length": \[metric | us\_customary\]    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string that is echoed back if it was provided by the client in the corresponding request. |
| `method="getRegionalSettings"` | Specifies that the `getRegionalSettings` method is performed. |
| `data.units.length=<metric | us_customary>` | Specifies what unit that should be used for length values. Default unit is metric. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "method": "getRegionalSettings",  "context": "<string>",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setRegionalSettings

This CGI method can be used to set the regional settings used in the GUI.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/regionalsettings.cgi" \\  --data '{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": "setRegionalSettings",  "params": {    "units": {      "length": \[metric | us\_customary\]    }  }}'
```

```bash
POST /axis-cgi/regionalsettings.cgiHost: <servername>Content-Type: application/json{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": "setRegionalSettings",  "params": {    "units": {      "length": \[metric | us\_customary\]    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | The client sets this value and the application echoes it back in the response (optional). |
| `method="setRegionalSettings"` | Specifies that the `setRegionalSettings` method is performed. |
| `params.units.length=<metric | us_customary>` | Specifies what unit to use for length values. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setRegionalSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | A text string that is echoed back if it was provided by the client in the corresponding request. |
| `method="setRegionalSettings"` | Specifies that the `setRegionalSettings` method is performed. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "method": "setRegionalSettings",  "context": "<string>",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### General error codes

The table lists the general errors that can occur for any CGI method. Specific errors are listed in the API specifications.

| Code | Description |
| --- | --- |
| `1000` | Internal error. |
| `1001` | The requested API version is not supported. |
| `1002` | Unknown method. |
| `1003` | Invalid argument. |
| `1004` | Invalid request. |