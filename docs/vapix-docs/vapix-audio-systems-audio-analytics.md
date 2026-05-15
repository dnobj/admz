---
title: Audio Analytics
url: "https://developer.axis.com/vapix/audio-systems/audio-analytics/"
category: vapix
subcategory: audio-systems
sha256: f08935644c2bc9367c43fe816e9b29c08263d43abc7ea16d768d308932340bdb
scraped_at: "2026-01-09T15:18:15.741Z"
page_height: 22326
---

# Audio Analytics

The VAPIX® Audio Analytics API provides the information that makes it possible to manage the settings for an audio plugin framework.

## Overview

The API implements `/axis-cgi/audioanalytics.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getPluginsSchemas` | Lists the JSON schema for all settings related to an analytics plugin. |
| `getPluginsSettings` | Lists the plugin settings for all plugin instances. |
| `setPluginsSettings` | Applies the plugin settings for all plugin instances. |
| `getSupportedVersions` | Lists all API versions supported by your device. |

This API works with the [Audio Device Control](/vapix/audio-systems/audio-device-control/) API, which can be used to configure hardware devices. The Audio Analytics API can then be used to configure the audio analytics features on the devices.

### Identification

-   **API Discovery**: `id=audio-analytics`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Audio analytics plugin

These examples will show you how to configure an existing audio analytics plugin. A plugin is made to analyze and react to an audio signal received from an audio source. Each plugin has its own unique settings object that can be used by the set/get methods detailed below.

**getPluginsSchemas**

Each plugin has its own individual settings object. This means that the method `getPluginsSchemas` will return the JSON schema for all analytics plugins.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSchemas",    "params": {}}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSchemas",    "params": {}}
```

Parse the JSON response.

Successful response example

```bash
{  "apiVersion": "1.0",  "context": "abc",  "method": "getPluginsSchemas",  "data": {    "schemas": \[      {        "$schema": "http://json-schema.org/draft/2020-12/schema#",        "title": Adaptive Audio Detection",        "type": "object",        "properties": {          "threshold": {            "type": "number",            "description": "Required threshold (dBFs) for detection",            "minimum": -180,            "maximum": 0          },          "enable": {            "type": "boolean",            "description": "Enable detection"          }        }      },      {        "$schema": "http://json-schema.org/draft/2020-12/schema#",        "title": "Classification",        "id": "Classification",        "type": "object",        "properties": {          "enable": {            "title": "Enable",            "type": "boolean",            "description": "Enable classification"          }        }      }    \]  }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSchemas",    "error": {        "code": 2104,        "message": "Invalid parameter value specified."    }}
```

See [getPluginsSchemas](#getpluginsschemas) for additional details.

**getPluginsSettings**

Return added audio plugin settings for all audio sources. The properties in the settings object are unique to the plugin and are described by the JSON schema returned with `getPluginsSchemas`.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "params": {}}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "params": {}}
```

Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "data": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AdaptiveAudioDetection",                                "settings": {                                    "enabled": true,                                    "threshold": -6                                }                            },                            {                                "id": "DirectionOfArrival",                                "settings": {                                    "enable": true                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AggressionDetection",                                "settings": {                                    "enable": true,                                    "level": 0                                }                            }                        \]                    }                \]            }        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "error": {        "code": 2100,        "message": "The requested API version is not supported."    }}
```

See [getPluginsSettings](#getpluginssettings) for additional details.

**setPluginsSettings**

The settings returned by `getPluginsSettings` can be used to configure the plugins with the following request. Descriptions for the settings can be requested with the method `getPluginsSchemas`.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "params": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AdaptiveAudioDetection",                                "settings": {                                    "enable": false,                                    "threshold": -3                                }                            },                            {                                "id": "DirectionOfArrival",                                "settings": {                                    "enable": false                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AggressionDetection",                                "settings": {                                    "enable": true,                                    "level": 2                                }                            }                        \]                    }                \]            }        \]    }}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "params": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AdaptiveAudioDetection",                                "settings": {                                    "enable": false,                                    "threshold": -3                                }                            },                            {                                "id": "DirectionOfArrival",                                "settings": {                                    "enable": false                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "AggressionDetection",                                "settings": {                                    "enable": true,                                    "level": 2                                }                            }                        \]                    }                \]            }        \]    }}
```

Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings"}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "error": {        "code": 2104,        "message": "Invalid parameter value specified."    }}
```

See [setPluginsSettings](#setpluginssettings) for additional details.

### Retrieve supported API versions

This example will show you how to list all API versions supported by your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

Successful response example

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Error response example

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 2100,        "message": "The requested API version is not supported."    }}
```

See [getSupportedVersions](#getsupportedversions) for additional details.

## API specifications
### getPluginsSchemas

This method should be used when you want to retrieve the JSON schema for a settings object originating from the `getPluginsSettings` response, or in the request set by `setPluginsSettings`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSchema",  "params": {    "plugin": <string>  }}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSchema",  "params": {    "plugin": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the server echoes it back in the response. |
| `method="getPluginsSchemas"` | The method that should be used. |
| `plugin=<string>` | The plugin name. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSchemas",  "data": {    "schemas": \[      {        "$schema": <string>,        "title": <string>,        "id": <string>,        "type": <string>,        "properties": <object>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPluginsSchemas"` | The requested method. |
| `data=<object>` | Container for method specific parameters. |
| `data.schemas[]=<list of plugin schemas>` | List of available plugin schemas. |
| `<plugin schema>.$schema=<string>` | The URL for the core schema meta-schema. |
| `<plugin schema>.title=<string>` | The schema title. |
| `<plugin schema>.id=<string>` | Identification of the plugin. |
| `<plugin schema>.type=<string>` | The settings type, usually an object. |
| `<plugin schema>.properties=<object>` | A unique JSON schema describing the properties of the settings objects returned by `getPluginsSettings` and sent in the request by `setPluginsSettings`. All JSON schemas has a link to the version used in the node property `$schema`. The plugin uses `draft/2020-12` to describe the properties. This means that a deviation will be explained if it occur from `draft/2020-12`. Example of a schema version:`"$schema": "http://json-schema.org/draft/2020-12/schema#"` |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSchemas",  "error": {    "code": <integer error code>,    "message". <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPluginsSchemas"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getPluginsSettings

This method should be used when you want to retrieve the settings for all plugins. The plugins all have their own settings object, detailed by the response from `getPluginsSchemas`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings"}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the server echoes it back in the response. |
| `method="getPluginsSetting"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSetting",  "data": {    "devices": \[{      "id": <string>,      "inputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\],      "outputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\]    }\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPluginsSettings"` | The requested method. |
| `data=<object>` | Container for the parameters listed below. |
| `data.devices[]=<list of audio devices>` | Lists all available audio devices. |
| `<audio device>.id` | The audio device id. |
| `<audio device>.inputs[]=<list of inputs>` | Lists the device inputs. |
| `inputs.id` | The input id. |
| `input.plugins[]=<list of plugin settings>` | Lists the plugin settings. |
| `plugins.id` | The plugin instance id. |
| `plugins.settings=<object>` | An object containing settings parameters detailed by the response from `getPluginsSchemas`. |
| `<audio device>.outputs[]=<list of outputs>` | Lists the device outputs. |
| `outputs.id` | The output id. |
| `output.plugins[]=<list of plugin settings>` | Lists the plugin settings. |
| `plugins.id` | The plugin instance id. |
| `plugins.settings=<object>` | An object containing the settings parameters detailed in the response from `getPluginsSchemas`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings",  "error": {    "code": <integer error code>,    "message". <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getPluginsSettings"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setPluginsSettings

This method should be used when you want to configure a plugin to work with the response from `getPluginsSettings`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSetting",  "params": {    "devices": \[{      "id": <string>,      "inputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\],      "outputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\]    }\]  }}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSetting",  "params": {    "devices": \[{      "id": <string>,      "inputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\],      "outputs": \[{        "id": <string>,        "plugins": \[{          "id": <string>,          "settings": <object>        }\]      }\]    }\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="setPluginsSettings"` | The requested method. |
| `params=<object>` | Container for method specific parameters listed below. |
| `data.devices[]=<list of audio devices>` | List containing all available audio devices. |
| `<audio device>.id` | The audio device id. |
| `<audio device>.inputs[]=<list of inputs>` | Lists the device inputs. |
| `inputs.id` | The input id. |
| `input.plugins[]=<list of plugin settings>` | Lists the plugin settings. |
| `plugins.id` | The plugin instance id. |
| `plugins.settings=<object>` | An object containing settings parameters detailed by the response from `getPluginsSchemas`. |
| `<audio device>.outputs[]=<list of outputs>` | Lists the device outputs. |
| `outputs.id` | The output id. |
| `output.plugins[]=<list of plugin settings>` | Lists the plugin settings. |
| `plugins.id` | The plugin instance id. |
| `plugins.settings=<object>` | An object containing settings parameters detailed by the response from `getPluginsSchemas`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` _Optional._ | The user sets this value and the server echoes it back in the response. |
| `method="setPluginsSettings"` | The method that should be used. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings",  "error": {    "code": <integer error code>,    "message". <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional._ | The context set by the user in the request. |
| `method="setPluginsSettings"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSupportedVersions

This method should be used when you want to request a list of all API versions supported by your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audioanalytics.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/audioanalytics.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The user sets this value and the server echoes it back in the response. |
| `method="getSupportedVersions"` | The method that should be used. |
| `data.apiVersions[]=<list of versions>` | A list containing all supported major versions along with their highest minor version, e.g. `["1.2", "3.4"]`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that was used in the request. |
| `context=<string>` _Optional_ | The context set by the user in the request. |
| `method="getSupportedVersions"` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

The following table consist of errors that may occur for any method. Errors specific to a method are listed under their separate API description.

| Code | Definition | Description |
| --- | --- | --- |
| `1100` | INTERNAL\_ERROR | Internal error. |
| `2100` | UNSUPPORTED\_API\_VERSION | The requested API version is not supported. |
| `2101` | JSON\_INVALID\_ERROR | The provided JSON input was invalid. |
| `2102` | METHOD\_NOT\_SUPPORTED | Method not supported. |
| `2103` | JSON\_KEY\_NOT\_FOUND | A mandatory input parameter was not found in the input. |
| `2104` | PARAM\_INVALID\_VALUE\_ERROR | Invalid parameter value specified. |
| `2105` | AUTHORIZATION\_ERROR | Authorization failed. |
| `2106` | AUTHENTICATION\_ERROR | Authentication failed. |
| `2107` | TRANSPORT\_LEVEL\_ERROR | Transport Level Error. |