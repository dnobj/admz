---
title: Basic device information
url: "https://developer.axis.com/vapix/network-video/basic-device-information/"
category: vapix
subcategory: network-video
sha256: 93f56035b11d75f4a4ecce244b77b6d1ddb4c4b1c753628f9aa51819b5fba981
scraped_at: "2026-01-09T15:19:21.766Z"
page_height: 14963
---

# Basic device information

## Description

The AXIS Basic device information API can be used to retrieve simple information about the product. This information is used to identify basic properties of the product, and is based around the following methods:

| Method | Usage |
| --- | --- |
| `getProperties` | Get a list of requested parameter values. |
| `getAllProperties` | Get a list of all supported parameters. |
| `getAllUnrestrictedProperties` | Get a list of all unrestricted parameters. |
| `getSupportedVersions` | Get a list of supported API versions. |

The API consists of an authenticated CGI which should be called using the `HTTP POST` method and JSON formatted data as an input. Using the API makes it possible to:

-   Get all supported properties in one shot.
-   Get a selected subset of properties.
-   Get all unrestricted properties.
-   Get a list of supported API versions.

### Identification

-   **AXIS OS**: 8.40 and later
-   **API Discovery**: `id=basic-device-info`
-   **Property**: `BasicDeviceInfo.BasicDeviceInfo="yes"`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Get basic device information

Use this example to receive information on how to identify and communicate with a device before it is configured/initialized in its internal state, or to identify the way how to communicate with the device.

Basic device information (BDI) service will provide some information about the device that will make it easier to identify. For example, on some low-end products where Parameter management isn’t available, this service will be an entry point to identify the device.

All requests to the BDI service is done by following this `HTTP` request with a proper `JSON` body. Responses to the API calls will also be delivered as `JSON` data.

**Get all properties**

1.  Request all properties with the following JSON request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAllProperties"}'
```

```bash
POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getAllProperties"}
```

2.  Parse the JSON response to include all properties:

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "data": {        "propertyList": {            "Architecture": "mips",            "Brand": "AXIS",            "BuildDate": "Feb 14 2018 13:08",            "HardwareID": "714.4",            "ProdFullName": "AXIS Q3505 Mk II Fixed Dome Network Camera",            "ProdNbr": "Q3505 Mk II",            "ProdShortName": "AXIS Q3505 Mk II",            "ProdType": "Network Camera",            "ProdVariant": "",            "SerialNumber": "ACCC8E78B977",            "Soc": "Axis Artpec-5",            "SocSerialNumber": "00000000-00000000-44123C08-C840037D",            "Version": "8.20.1",            "WebURL": "http://www.axis.com"        }    }}
```

**Get some properties**

1.  Request a subset of the properties with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getProperties",    "params": {        "propertyList": \["Brand", "ProdNbr", "Version"\]    }}
```

2.  Parse the JSON response which includes selected properties.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "data": {        "propertyList": {            "Brand": "AXIS",            "ProdNbr": "Q3505 Mk II",            "Version": "8.20.1"        }    }}
```

**Handle errors**

If an error occur while processing the clients request a JSON response will be returned containing an error code and a detailed message.

1.  Request properties that does not exist with the following JSON request.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getProperties",    "params": {        "propertyList": \["Brand", "ProdNbr", "Version", "invalid\_property\_name"\]    }}
```

2.  Parse the JSON response which includes an error message and a message.

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "error": {        "code": 1000,        "message": "Property not supported: invalid\_property\_name"    }}
```

### Get basic device information as an anonymous user

Use this example to show some device information during the initial access before a root user has been defined, or when no user is logged in.

**Get all unrestricted properties**

1.  Request all unrestricted properties using the following JSON request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{    "apiVersion": "1.2",    "context": "Client defined request ID",    "method": "getAllUnrestrictedProperties"}'
    ```
    
    ```bash
    POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.2",    "context": "Client defined request ID",    "method": "getAllUnrestrictedProperties"}
    ```
    
2.  Parse the JSON response.
    
    ```bash
    {    "apiVersion": "1.2",    "context": "Client defined request ID",    "data": {        "propertyList": {            "Brand": "AXIS",            "BuildDate": "Aug 04 2020 11:15",            "HardwareID": "75E.1",            "ProdFullName": "AXIS Q1785-LE Network Camera",            "ProdNbr": "Q1785-LE",            "ProdShortName": "AXIS Q1785-LE",            "ProdType": "Network Camera",            "ProdVariant": "",            "SerialNumber": "ACCC8EAF8C30",            "Version": "8.20.1",            "WebURL": "http://www.axis.com"        }    }}
    ```
    

**Handle errors**

If an error occur while processing the clients request a JSON response will be returned containing an error code and a detailed message.

See [Get basic device information](#get-basic-device-information) for an example and [Error handling](#error-handling) for general error guidelines.

## API specification
### getAllProperties

Use `getAllProperties` to retrieve all properties provided by the BDI service. This API can also be used to identify what type of properties BDI service is providing.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getAllProperties"}'
```

```bash
POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getAllProperties"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | _Optional._ Client sets this value and the server echoes the data back in the response. If set, it will be present in the response regardless of whether the response is successful or not. |
| `method="getAllProperties"` | _Required._ Specifies that the `getAllProperties` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "data": {        "propertyList": {            "Architecture": "<string>",            "Brand": "<string>",            "BuildDate": "<string>",            "HardwareID": "<string>",            "ProdFullName": "<string>",            "ProdNbr": "<string>",            "ProdShortName": "<string>",            "ProdType": "<string>",            "ProdVariant": "<string>",            "SerialNumber": "<string>",            "Soc": "<string>",            "SocSerialNumber": "<string>",            "Version": "<string>",            "WebURL": "<string>"        }    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | Text string echoed back if it has been provided by the client in the corresponding request. |
| `data.propertyList` | Contains all property pairs for the device the service is running on. All available properties are included in the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exists for this method. General errors are listed in [Error handling](#error-handling).

### getProperties

Use `getProperties` to retrieve a subset of the properties provided by the BDI service.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getProperties",  "params": {    "propertyList": \[      "<property1>",      "<property2>",      "<property3>",      ...    \]  }}'
```

```bash
POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getProperties",  "params": {    "propertyList": \[      "<property1>",      "<property2>",      "<property3>",      ...    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | _Optional._ Client sets this value and the server echoes the data back in the response. If set, it will be present in the response regardless of whether the response is successful or not. |
| `method="getProperties"` | _Required._ Specifies that the `getProperties` operation is performed. |
| `params.propertyList=<array of property names>` | _Required._ Specifies which properties should be returned with the response. If this field is empty an empty list will be returned. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "data": {    "propertyList": {      "<property1>": "<string>",      "<property2>": "<string>",      "<property3>": "<string>",      ...    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context=<string>` | Text string echoed back if it is provided by the client in the corresponding request. |
| `data.propertyList` | Contains selected property pairs for the device on which the service is running on. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exists for this method. General errors are listed in [Error handling](#error-handling).

### getAllUnrestrictedProperties

Use `getAllUnrestrictedProperties` to retrieve all unspecified properties by the BDI service.

**Request**

-   **Security level**: Anonymous

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getAllUnrestrictedProperties"}'
```

```bash
POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "method": "getAllUnrestrictedProperties"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | _Optional._ Client sets this value and the server echoes the data back in the response. If set, it will be present in the response regardless of whether the response is successful or not. |
| `method="getAllUnrestrictedProperties"` | _Required._ Specifies that the `getAllUnrestrictedProperties` operation is performed. |

**Return value - Success**

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "<major>.<minor>",    "context": "<string>",    "data": {        "propertyList": {            "Brand": "<string>",            "BuildDate": "<string>",            "HardwareID": "<string>",            "ProdFullName": "<string>",            "ProdNbr": "<string>",            "ProdShortName": "<string>",            "ProdType": "<string>",            "ProdVariant": "<string>",            "SerialNumber": "<string>",            "Version": "<string>",            "WebURL": "<string>"        }    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` | Text string echoed back if it has been provided by the client in the corresponding request. |
| `data.propertyList` | Contains all property pairs for the device the service is running on. All available properties are included in the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exists for this method. General errors are listed in [Error handling](#error-handling).

### getSupportedVersions

Use `getSupportedVersions` to retrieve supported API versions.

**Request**

-   **Security level**: Anonymous

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/basicdeviceinfo.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | _Optional._ The client sets this value and the server echoes the data back in the response. If set, it will be present in the response regardless of whether the response is successful or not. |
| `method="getSupportedVersions"` | _Required._ Specifies that the `getSupportedVersions` operation can be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "context": "<string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | Text string echoed back if it is provided by the client in the corresponding request. |
| `method="getSupportedVersions"` | _Required._ Specifies that the `getParameters` operation is performed. |
| `data.apiVersions` | Contains an array of supported versions. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

No specific failure exists for this method. General errors are listed in [Error handling](#error-handling).

### Error handling

The following table lists general errors that may occur for any JSON request. Errors that are specific for a method are listed under the API description for that method. Descriptions are only used to describe the type of the error code. Detailed information on the fault will be provided in a message field inside the error structure.

| Code | Description |
| --- | --- |
| `1000` | Invalid parameter with the value specified. |
| `2001` | Access forbidden. |
| `2002` | HTTP request types are not supported. Only POST is supported. |
| `2003` | The requested API version is not supported. |
| `2004` | The method is not supported. |
| `4000` | Invalid JSON format. |
| `4002` | Required parameter is either missing or invalid. |
| `8000` | Internal error. Refer to the message field or logs. |

All failures are returned with the following JSON response:

Error response body syntax

```bash
{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that is used. |
| `context=<string>` | Text string echoed back if it is provided by the client in the corresponding request. |
| `error.code` | Contains an error code. This value can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |