---
title: Stream profiles
url: "https://developer.axis.com/vapix/network-video/stream-profiles/"
category: vapix
subcategory: network-video
sha256: b0845be3ec7139a261228ce545172a48e2d6376e010196c38ad383e68c3ad641
scraped_at: "2026-01-09T15:21:07.666Z"
page_height: 19188
---

# Stream profiles

## Description

The Stream profile API makes it possible to create and manage stream profiles suitable for different applications and devices when recording a video or requesting a live video. A stream profile contains a collection of parameters such as video codecs, resolutions, frame rates and compressions, and should be used to retrieve a video stream from your Axis product. Lastly, all parameters that can be used in a video stream request (both HTTP or RTSP) can be saved in a stream profile.

### Model

The API implements `/axis-cgi/streamprofile.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `list` | Lists all available stream profiles. |
| `create` | Creates a new stream profile. |
| `update` | Updates an existing stream profile. |
| `remove` | Removes a stream profile. |
| `getSupportedVersions` | Retrieves a list of supported API versions. |

### Identification

-   **API Discovery**: `id=stream-profiles`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Backup and restore stream profiles

Use this example to backup all stream profiles currently saved on your device and restore them without having to set each parameters individually later on.

For backup purposes, you will not need to parse or understand the configuration that is returned. What you do remember though is that a backed up configuration can be re-applied to the camera and that this will restore the stream profiles for the configuration as well.

1.  Request the current stream profiles.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "params": {        "streamProfileName": \[\]    }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "params": {        "streamProfileName": \[\]    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "data": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080",                "parameters": "resolution=1920x1080"            },            {                "name": "My inverted image profile",                "description": "The image is inverted",                "parameters": "resolution=640x360&fps=25&rotation=180"            },            {                "name": "My high compression profile",                "description": "Compression is max: low quality",                "parameters": "resolution=1920x1080&compression=100"            }        \],        "maxProfiles": 26    }}
```

3.  Restore settings by posting `streamProfile[]` as `params` by using the JSON structure from the `data` received in the previous call.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "create",    "params": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080",                "parameters": "resolution=1920x1080"            },            {                "name": "My inverted image profile",                "description": "The image is inverted",                "parameters": "resolution=640x360&fps=25&rotation=180"            },            {                "name": "My high compression profile",                "description": "Compression is max: low quality",                "parameters": "resolution=1920x1080&compression=100"            }        \]    }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "create",    "params": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080",                "parameters": "resolution=1920x1080"            },            {                "name": "My inverted image profile",                "description": "The image is inverted",                "parameters": "resolution=640x360&fps=25&rotation=180"            },            {                "name": "My high compression profile",                "description": "Compression is max: low quality",                "parameters": "resolution=1920x1080&compression=100"            }        \]    }}
```

### Configure an existing stream profile

Use this example to retrieve a stream profile, change some of its values and re-upload it as an updated configuration to the camera. In this example, the FPS of the profile "My full HD profile" is set to 30.

1.  Request a stream profile named "My full HD profile".

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "params": {        "streamProfileName": \[            {                "name": "My full HD profile"            }        \]    }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "params": {        "streamProfileName": \[            {                "name": "My full HD profile"            }        \]    }}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "my context",    "method": "list",    "data": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080",                "parameters": "resolution=1920x1080"            }        \],        "maxProfiles": 26    }}
```

3.  Upload new settings.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "my context",    "method": "update",    "params": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080 with FPS:30",                "parameters": "resolution=1920x1080&fps=30"            }        \]    }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "my context",    "method": "update",    "params": {        "streamProfile": \[            {                "name": "My full HD profile",                "description": "HD profile:1920x1080 with FPS:30",                "parameters": "resolution=1920x1080&fps=30"            }        \]    }}
```

## API specification
### list

This API method can be used to list the content of a stream profile. It is possible to list either one or multiple profiles and if the parameter `streamProfileName` is the empty list `[]` all available stream profiles will be listed.

**Request**

-   **Security level**: Administrator, Operator, Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{  "apiVersion": "1.0",  "context": "<string>",  "method": "list"  "params": {    "streamProfileName": \[      {        "name": "My full HD profile"      },      {        "name": "My low resolution"      },      {        ...      }    \]  }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.0",  "context": "<string>",  "method": "list"  "params": {    "streamProfileName": \[      {        "name": "My full HD profile"      },      {        "name": "My low resolution"      },      {        ...      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="list"` | The method that should be used. |
| `params` | Container for method specific parameters. See [Parameter description](#parameter-description) for a complete list. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "list",  "data": {    "streamProfile": \[      {        "name": "My full HD profile",        "description": "HD profile:1920x1080",        "parameters": "resolution=1920x1080"      },      {        ...      },      {        ...      },      {        ...      }    \],    "maxProfiles": 26  }}
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "list",  "error": {    "code": <integer>    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Application Error | `1000` | The application failed to return a configuration. |
| Unsupported Version | `2000` | The major version number isn’t supported. |
| Invalid Format | `2001` | The request was not formatted correctly, i.e. does not follow JSON schema. |
| Unsupported Method | `2005` | The method in the request is not supported. |
| Profile does not exist | `2006` | The requested profile does not exist. |

### create

This API method can be used to add a new stream profile. The name of each stream profile needs to be unique, otherwise, an error will be returned.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{  "apiVersion": "1.0",  "context": "<string>",  "method": "create",  "params": {    "streamProfile": \[      {        "name": "My low resolution profile",        "description": "Low resolution:640x360 and FPS:25"        "parameters": "resolution=640x360&FPS=25"      }    \]  }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.0",  "context": "<string>",  "method": "create",  "params": {    "streamProfile": \[      {        "name": "My low resolution profile",        "description": "Low resolution:640x360 and FPS:25"        "parameters": "resolution=640x360&FPS=25"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="create"` | The method that should be used. |
| `params` | Container for method specific parameters. See [Parameter description](#parameter-description) for a complete list. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "create",  "data": {}}
```

Please note that successful calls contains an empty `data` object.

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "create",  "error": {    "code": <integer>    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Application Error | `1000` | The application failed to set the configuration. |
| Unsupported Version | `2000` | The major version number isn’t supported. |
| Invalid Format | `2001` | The configuration was not formatted correctly, i.e. does not follow JSON-schema. |
| Incoherent Configuration | `2002` | Parts of the configuration contradict each other, e.g. several profiles have the same name. |
| Missing Parameter | `2003` | The request has a missing mandatory parameter. |
| Invalid Parameter | `2004` | The request has parameter that has an invalid value. |
| Unsupported Method | `2005` | The method in the request is not supported. |

### update

This API method can be used to update an already existing stream profile. You can not rename a profile unless you first delete it and create a new one with the required name.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{  "apiVersion": "1.0",  "context": "<string>",  "method": "update",  "params": {    "streamProfile": \[      {        "name": "My low resolution profile",        "description": "Low resolution:640x360 and FPS:30",        "parameters": "resolution=640x360&FPS=30"      }    \]  }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.0",  "context": "<string>",  "method": "update",  "params": {    "streamProfile": \[      {        "name": "My low resolution profile",        "description": "Low resolution:640x360 and FPS:30",        "parameters": "resolution=640x360&FPS=30"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="update"` | The method that should be used. |
| `params` | Container for method specific parameters. See [Parameter description](#parameter-description) for a complete list. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "update",  "context": "<string>",  "data": {}}
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "update",  "error": {    "code": <integer>    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Application Error | `1000` | The application failed to set the configuration. |
| Unsupported Version | `2000` | The major version number isn’t supported. |
| Invalid Format | `2001` | The configuration was not formatted correctly, i.e. does not follow JSON-schema. |
| Missing Parameter | `2003` | The request has a missing mandatory parameter. |
| Invalid Parameter | `2004` | The request has parameter that has an invalid value. |
| Unsupported Method | `2005` | The method in the request is not supported. |
| Profile does not exist | `2006` | The requested profile does not exist. |

### remove

This API method can be used to remove one or several stream profiles, the latter being possible as long as you provide a list of profile names.

**Request**

-   **Security level**: Administrator, Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{  "apiVersion": "1.0",  "context": "<string>",  "method": "remove",  "params": {    "streamProfileName": \[      {        "name": "My full HD profile"      },      {        "name": "XXX"      },      {        ...      }    \]  }}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.0",  "context": "<string>",  "method": "remove",  "params": {    "streamProfileName": \[      {        "name": "My full HD profile"      },      {        "name": "XXX"      },      {        ...      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="remove"` | The method that should be used. |
| `params` | Container for method specific parameters. See [Parameter description](#parameter-description) for a complete list. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "remove",  "data": {}}
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "remove",  "error": {    "code": <integer>    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Application Error | `1000` | The application failed to set the configuration. |
| Unsupported Version | `2000` | The major version number isn’t supported. |
| Invalid Format | `2001` | The configuration was not formatted correctly, i.e. does not follow JSON-schema. |
| Missing Parameter | `2003` | The request has a missing mandatory parameter. |
| Invalid Parameter | `2004` | The request has parameter that has an invalid value. |
| Unsupported Method | `2005` | The method in the request is not supported. |
| Profile does not exist | `2006` | The requested profile does not exist. |

### getSupportedVersions

The API method can be used to retrieve a list of available supported API versions.

**Request**

-   **Security level**: Administrator, Operator, Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/streamprofile.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/streamprofile.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.1",  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The requested API version in the format "Major.Minor". |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The method that should be used. |
| `apiVersions=<list of versions>` | Lists all supported major versions along with their highest supported minor version. |
| `<list of versions>` | List of "<Major>.<Minor>" versions, e.g. \["1.4", "2.5"\]. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.1",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer>,    "message": <string>  }}
```

| Error | Code | Description |
| --- | --- | --- |
| Application Error | `1000` | The application failed to return the supported versions. |
| Unsupported Version | `2000` | The major version number isn’t supported. |
| Invalid Format | `2001` | The request was not formatted correctly, i.e. does not follow JSON-schema. |
| Unsupported Method | `2005` | The method in the request is not supported. |

### Parameter description

The structure of a configuration object is the same in both the `data` object in the response for `list` and the `params` object in the request for `create`.

The `streamProfile` object contains information about the stream profile.

| Property | Type | Description |
| --- | --- | --- |
| `streamProfile.name` | String | ASCII string that represents the name of the profile. |
| `streamProfile.description` | String | ASCII string that describes the stream profile. |
| `streamProfile.parameters` | String | List of parameters, separated by a `&`, which defines the stream profile. |

The `streamProfileName` object contains the list of profile names, whose profile needs to be listed.

| Argument | Type | Description |
| --- | --- | --- |
| `name` | String | ASCII string that represents the name of the profile. |

The `maxProfiles` parameter defines the maximum number of stream profiles that can be created/supported.

| Property | Type | Description |
| --- | --- | --- |
| `maxProfiles` | Integer | Maximum number of supported stream profiles. |