---
title: Feature Flag Service
url: "https://developer.axis.com/vapix/network-video/feature-flag-service/"
category: vapix
subcategory: network-video
sha256: e6b227946c2af17ecfdcffb8e3d985ec3dc8c4a622e40830be6e1ca19b6eaba1
scraped_at: "2026-01-09T15:19:47.016Z"
page_height: 18785
---

# Feature Flag Service

## Description

The Feature Flag Service API provides the information that makes it possible to use feature flags with your Axis device. Feature flags can be used to, among other things, toggle experimental features on/off and do gradual roll-outs of software updates.

### Model

The API implements `/axis-cgi/featureflag.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `set` | Set the value of one or multiple flags. |
| `get` | Retrieve the value of one or multiple flags. |
| `listAll` | Retrieve the value and metadata of all flags. |
| `getSupportedVersions` | Retrieve the API versions supported by your device. |

**Obsoletes**

This API is set to replace `streamingfeature.cgi`, that will be subsequently deprecated and no longer receive any updates.

### Identification

-   **API Discovery**: `id=feature-flag`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Set flags

This example will showcase the steps you need to take to toggle a feature wrapped around a flag that was disabled by default. Reasons for doing this includes trying out an experimental feature or preparing a feature that is ready to go live.

1.  Set a flag to true/false.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "set",    "params": {        "flagValues": {            "flag.name.1": true,            "flag.name.2": true        }    }}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "set",    "params": {        "flagValues": {            "flag.name.1": true,            "flag.name.2": true        }    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "set",    "data": {        "result": "Success"    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "set",    "error": {        "code": 2104,        "message": "Invalid parameter value specified"    }}
```

**API reference**

-   [set](#set)

### Get flags

This example will showcase the steps you need to take to check for toggled features and verify if the flags are in their expected state.

1.  Retrieve the value of a specified number of flags.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "get",    "params": {        "names": \["flag.name.1", "flag.name.2"\]    }}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "get",    "params": {        "names": \["flag.name.1", "flag.name.2"\]    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "get",    "data": {        "flagValues": {            "flag.name.1": true,            "flag.name.2": false        }    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "get",    "error": {        "code": 2200,        "message": "Flag(s) does not exist: com.axis.remotesyslog.fax"    }}
```

**API reference**

-   [get](#get)

### List all flags

This example will showcase the steps you need to take to gather statistics about the flags on your device in order to debug a potential issue. By following these steps you will retrieve a list containing all available information about the flags, including metadata containing both the current and default value and description of the flags.

1.  Retrieve a list of all flags.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "listAll"}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "listAll"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "listAll",    "data": {        "flags": \[            {                "name": "flag.name.1",                "value": true,                "description": "Use both hands for parameter handling.",                "defaultValue": false            },            {                "name": "flag.name.2",                "value": false,                "description": "Run action engine on ethanol.",                "defaultValue": false            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "listAll",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

**API reference**

-   [listAll](#listall)

### Get supported versions

This example will showcase the steps you need to take to retrieve information about the API versions that are supported by your device.

1.  Retrieve a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "context": "Client defined request ID",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "context": "Client defined request ID",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0"\]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getSupportedVersions",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

**API reference**

-   [getSupportedVersions](#getsupportedversions)

## API Specifications
### set

This method is used when you wish to set a specified number of flags.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "set"  "params": {    "flagValues": {      "<string>": bool,      "<string>": bool    }  }}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "set"  "params": {    "flagValues": {      "<string>": bool,      "<string>": bool    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="set"` | Specifies the method. |
| `params=<object>` | Parameter group made to set the flags. |
| `params.flagValues=<object>` | Contains the flag name and value pairs. The flags will be updated according to this list. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "set",    "data": {        "result": "Success"    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="set"` | The requested method. |
| `result=<string>` | If the call was successful the string "Success" is returned. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "set",  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="set"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### get

This method is used when you wish to retrieve the value for a specified number of flags.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "get",    "params": {        "names": \["flag.name.1", "flag.name.2"\]    }}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "get",    "params": {        "names": \["flag.name.1", "flag.name.2"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="get"` | Specifies the method. |
| `params=<object>` | Parameters sent to and included in the API call by the method. |
| `params.flagValues=<object>` | List containing the flag names that should be retrieved. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "get",  "data": {    "flagValues": {      "name": bool    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="get"` | The requested method. |
| `data.flagValues=<string:bool><list>` | List containing the flag name and values, corresponding to the list of names given in the request. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "get",  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="get"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### listAll

This method is used when you wish to retrieve a list containing all flags as well as their metadata.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listAll"}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "listAll"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="listAll"` | Specifies the method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAll"  "data": {    "flags": \[      {        "name": "<string>",        "value": <bool>,        "description": "<string>",        "defaultValue": <bool>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listAll"` | The requested method. |
| `data.flags=<list>` | List containing all flags along with their metadata on the device. |
| `data.flags.name=<string>` | The name of the flag. |
| `data.flags.value=<bool>` | The current flag value. |
| `data.flags.description=<string>` | A short description of the flag. |
| `data.flags.defaultValue=<bool>` | The initial flag value. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listAll"  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="listAll"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSupportedVersions

This method is used when you wish to retrieve a list containing all API versions supported by your device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/featureflag.cgi" \\  --data '{    "context": "<string>",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/featureflag.cgiHost: <servername>Content-Type: application/json{    "context": "<string>",    "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getSupportedVersions"` | Specifies the method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<major>.<minor>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `data.apiVersions[]=<list of versions>` | A list containing the supported major API versions along with their highest supported minor version. |
| `<list of versions>` | A list containing "<Major>.<Minor>" versions, e.g. \["1.4", "2.5"\] |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions"  "error": {    "code": <integer error code>,    "message": "<string>"  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

The following table lists the errors that can occur for all CGI methods.

| Code | Description |
| --- | --- |
| `1100` | Internal error. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing. |
| `2104` | Invalid parameter value specified. |
| `2105` | Authorization failed. |
| `2106` | Authentication failed. |
| `2107` | Request too large. |
| `2200` | Flags does not exist. |