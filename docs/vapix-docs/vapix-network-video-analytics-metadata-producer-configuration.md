---
title: Analytics Metadata Producer Configuration
url: "https://developer.axis.com/vapix/network-video/analytics-metadata-producer-configuration/"
category: vapix
subcategory: network-video
sha256: c598184d2972c61d15dc4b672c9ad5823e320d952e62669493b47dfe2a867a23
scraped_at: "2026-01-09T15:19:17.004Z"
page_height: 21331
---

# Analytics Metadata Producer Configuration

## Description

The Analytics Metadata Producer Configuration API is an interface for applications and users to look up information about and configure RTSP metadata producers. This includes listing available RTSP metadata producers, enabling/disabling producers on separate video channels or requesting samples of metadata to check the functionality of each individual producer. A producer in this context is a product dependent application running on your device.

info

This API is currently only designed to be used with single- and dual channel devices. A version with support for devices with more channels might be released in the future.

### Model

The API implements `/axis-cgi/analyticsmetadataconfig.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `listProducers` | Lists either all or a specific number of metadata producers. |
| `setEnabledProducers` | Enables/disables a specific metadata producer and their supported video channels. |
| `getSupportedMetadata` | Retrieves a sample frame for either all or a specific number of metadata producers. |
| `getSupportedVersions` | Retrieves the API versions supported by your device. |

### Identification

-   **API Discovery**: `id=analytics-metadata-config`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Configure metadata producers

These examples will showcase the steps you need to take to list all available metadata producers and configure whether they should be enabled or disabled in the RTSP metadata stream.

1.  Send a request with an empty `params` to find available RTSP analytics producers.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "params": {}}'
    ```
    
    ```bash
    POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "params": {}}
    ```
    
2.  Parse the JSON response.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "data": {        "producers": \[            {                "name": "producer",                "niceName": "Producer Name",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "error": {        "code": 1000,        "message": "The application failed to handle the request."    }}
    ```
    
3.  Send a request containing an array of producers and which video channels they should enable/disable.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "params": {        "producers": \[            {                "name": "producer",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}'
    ```
    
    ```bash
    POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "params": {        "producers": \[            {                "name": "producer",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}
    ```
    
4.  Parse the JSON response. The `data` parameter will be empty if the request is successful.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "data": {}}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "error": {        "code": 1000,        "message": "The application failed to handle the request."    }}
    ```
    

### Retrieve supported metadata

This example will showcase the steps you need to take to retrieve information regarding the RTSP metadata analytics producers and what kind of metadata they can produce. One of reasons you would want to do this is to get an idea about what kind of metadata that can be included in the RTSP stream and request a response from a select number of specific producers.

1.  Send a request.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "params": {        "producers": \["producer"\]    }}'
    ```
    
    ```bash
    POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "params": {        "producers": \["producer"\]    }}
    ```
    
2.  Parse the JSON response.
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "data": {        "producers": \[            {                "name": "producer",                "sampleFrameXML": "<tt:Frame></tt:Frame>"            }        \]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "error": {        "code": 1000,        "message": "The application failed to handle the request."    }}
    ```
    

### Retrieve supported API versions

This example will showcase the steps you need to take to retrieve all API versions supported by your device.

1.  Send a request.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
    ```
    
    ```bash
    POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
    ```
    
2.  Parse the JSON response
    
    Successful response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "1.1"\]    }}
    ```
    
    Error response example
    
    ```bash
    {    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "error": {        "code": 1000,        "message": "The application failed to handle the request."    }}
    ```
    

## API specifications
### listProducers

This method is used when you wish to list a select number of metadata producers along with their supported video channel and status. Using this method can lead to either one of the following responses:

-   All available analytics producers will be listed in cases where the parameter producers are absent.
-   The response will be successful when the parameter producers are set even if one or more of them doesn’t exist. These producers will not be listed.

**Request**

-   **Security level**: Administrator, Operator, Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "params": {        "producers": \["producer"\]    }}'
```

```bash
POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "params": {        "producers": \["producer"\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | _Optional_. A text string echoed back in the corresponding response. |
| `method` | String | Specifies the method. |
| `params` | Object | Parameters sent to and included in the API call by the method. |
| `producers` | Array | Container for the producers. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "listProducers",    "data": {        "producers": \[            {                "name": "producer",                "niceName": "Producer Name",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `data` | Object | Contains the producer information and their assigned video channels. |
| `producers` | Array | Container for the producers. |
| `name` | String | The producer name. |
| `niceName` | String | _Optional_. The display friendly name. |
| `videochannels` | Array | Container for the video channels assigned to the producer. |
| `channel` | Integer | The name of the video channel. |
| `enabled` | Boolean | The status of the video channel. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "listProducers",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `error` | Object | The error object. |
| `code` | Integer | And error code describing the kind of error. |
| `message` | String | An error message detailing the error. |

**Error codes**

The following error codes are specific for this method. See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1000` | The application failed to handle the request. |
| `2000` | The major version number isn’t supported. |
| `2001` | The request was not formatted correctly, i.e. does not follow json-schema. |
| `2004` | The request has parameter that has an invalid value. |
| `2005` | The method in the request is not supported. |

### setEnabledProducers

This method is used when you wish to enable/disable specific metadata producers and their supported video channels. Please note that not using this method correctly can lead to one of the following responses:

-   The response will be an error if a video channel that the producer does not support is specified.
-   Likewise, an error will be returned if a fault occurred on any of the producer’s channels, meaning that no updates will be applied.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "params": {        "producers": \[            {                "name": "producer",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}'
```

```bash
POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "params": {        "producers": \[            {                "name": "producer",                "videochannels": \[                    {                        "channel": 1,                        "enabled": true                    },                    {                        "channel": 2,                        "enabled": false                    }                \]            }        \]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | _Optional_. A text string echoed back in the corresponding response. |
| `method` | String | Specifies the method. |
| `params` | Object | Parameters sent to and included in the API call by the method. |
| `producers` | Array | Container for the producers. |
| `name` | String | The producer name. |
| `videochannels` | Array | Container for the video channels assigned to the producer. |
| `channel` | Integer | The name of the video channel. |
| `enabled` | Boolean | The status of the video channel. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "setEnabledProducers",    "data": {}}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `data` | Object | Contains the producer information and their assigned video channels. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "setEnabledProducers",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `error` | Object | The error object. |
| `code` | Integer | And error code describing the kind of error. |
| `message` | String | An error message detailing the error. |

**Error codes**

The following error codes are specific for this method. See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1000` | The application failed to handle the request. |
| `2000` | The major version number isn’t supported. |
| `2001` | The request was not formatted correctly, i.e. does not follow json-schema. |
| `2003` | The request has a missing mandatory parameter. |
| `2004` | The request has parameter that has an invalid value. |
| `2005` | The method in the request is not supported. |

### getSupportedMetadata

This method is used when you wish to retrieve a sample frame for a select number of metadata producers. The frame will be compatible with the ONVIF XML metadata format and have one of the following characteristics:

-   All analytics producers will be listed if the parameter producer is absent.
-   The response will be successful even if not all parameter producers are set. The missing producers will be omitted from the response.

**Request**

-   **Security level**: Administrator, Operator, Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "params": {        "producers": \["producer"\]    }}'
```

```bash
POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "params": {        "producers": \["producer"\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version that should be used. |
| `context` | String | _Optional_. A text string echoed back in the corresponding response. |
| `method` | String | Specifies the method. |
| `params` | Object | Parameters sent to and included in the API call by the method. |
| `producers` | Array | Container for the producers. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedMetadata",    "data": {        "producers": \[            {                "name": "producer",                "sampleFrameXML": "<tt:Frame></tt:Frame>"            }        \]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `data` | Object | Contains the producer information and their assigned video channels. |
| `producers` | Array | Container for the producers. |
| `name` | String | The producer name. |
| `sampleFrameXML` | String | The sample frame associated with the producer. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getSupportedMetadata",  "error": {    "code": <integer>    "message": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `error` | Object | The error object. |
| `code` | Integer | And error code describing the kind of error. |
| `message` | String | An error message detailing the error. |

**Error codes**

The following error codes are specific for this method. See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1000` | The application failed to handle the request. |
| `2000` | The major version number isn’t supported. |
| `2001` | The request was not formatted correctly, i.e. does not follow json-schema. |
| `2004` | The request has parameter that has an invalid value. |
| `2005` | The method in the request is not supported. |

### getSupportedVersions

This method is used when you wish to retrieve a list containing the API versions supported by your device.

**Request**

-   **Security level**: Administrator, Operator, Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/analyticsmetadataconfig.cgi" \\  --data '{    "context": "my context",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/analyticsmetadataconfig.cgiHost: <servername>Content-Type: application/json{    "context": "my context",    "method": "getSupportedVersions"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `context` | String | _Optional_. A text string echoed back in the corresponding response. |
| `method` | String | Specifies the method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `data` | Object | Contains the producer information and their assigned video channels. |
| `apiVersions` | Array | Contains the supported API versions in the format "Major.Minor", i.e. `1.4` or `2.1`. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "my context",  "method": "getSupportedVersions",  "error": {    "code": <integer>    "message": <string>  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `apiVersion` | String | The API version returned from the request. |
| `context` | String | _Optional_. The context set by the user in the request. |
| `method` | String | The requested method. |
| `error` | Object | The error object. |
| `code` | Integer | And error code describing the kind of error. |
| `message` | String | An error message detailing the error. |

**Error codes**

The following error codes are specific for this method. See [General error codes](#general-error-codes) for a complete list of potential errors.

| Code | Description |
| --- | --- |
| `1000` | The application failed to handle the request. |
| `2001` | The request was not formatted correctly, i.e. does not follow json-schema. |
| `2005` | The method in the request is not supported. |

### General error codes

| Code | Description |
| --- | --- |
| `1000` | The application failed to handle the request. |
| `2000` | The major version number isn’t supported. |
| `2001` | The request was not formatted correctly, i.e. does not follow json-schema. |
| `2003` | The request has a missing mandatory parameter. |
| `2004` | The request has parameter that has an invalid value. |
| `2005` | The method in the request is not supported. |