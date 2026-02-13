---
title: Audio mixer API
url: "https://developer.axis.com/vapix/audio-systems/audio-mixer-api/"
category: vapix
subcategory: audio-systems
sha256: 58a03d7c03a67716e2343d0a10adec6bfe97b88483ecb27849a774387ac721df
scraped_at: "2026-01-09T15:18:22.013Z"
page_height: 20295
---

# Audio mixer API

## Description

The AXIS Audio mixer API contains the information on how to support a plugin framework capable of adding audio plugins to an audio chain. In this API, a plugin is something that can alter the audio stream in some way.

### Model

The API uses `/axis-cgi/audiomixer.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getPluginSchema` | Retrieves a JSON schema for a plugin setting. |
| `getPluginsSettings` | Retrieves the plugin settings for all plugin instances. |
| `setPluginsSettings` | Sets the plugin settings for all plugin instances. |
| `getSupportedVersions` | Retrieve a list of supported API versions. |

### Identification

-   **API Discovery**: [API Discovery service](/vapix/network-video/api-discovery-service/)

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Audio plugins

The following examples are used when you want to modify the audio plugin settings.

#### Retrieve the plugin schema

Use this example to retrieve a unique set of properties for each plugin. The method in this example returns the plugin schema for each unique setting, containing a JSON schema for the settings object for a particular plugin.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginSchema",    "params": {        "plugin": "automaticGainControl"    }}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginSchema",    "params": {        "plugin": "automaticGainControl"    }}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginSchema",    "data": {        "$schema": "http://json-schema.org/draft-07/schema#",        "title": "automaticGainControl",        "type": "object",        "properties": {            "target": {                "type": "number",                "description": "Desired output level",                "minimum": -180,                "maximum": 0            },            "dynamic\_range": {                "type": "number",                "description": "Allowed dynamic range",                "minimum": 0            }        }    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginSchema",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

#### Retrieve plugin settings

Use this example to retrieve every added audio plugin setting for all available audio sources (devices, connection, busses).

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "params": {}}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "params": {}}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "data": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "automaticGainControl",                                "settings": {                                    "enabled": true,                                    "target": -6,                                    "dynamicRange": 3                                }                            },                            {                                "id": "voiceEnhancer",                                "settings": {                                    "enabled": true,                                    "noiseSuppression": -6                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "simpleEq",                                "settings": {                                    "enabled": true,                                    "band0": -16,                                    "band1": -12                                }                            }                        \]                    }                \]            }        \]    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "getPluginsSettings",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

#### Set plugin settings

Use this example to implement the settings structure retrieved from the previous example. Please note that only parameters that are changed needs to be specified in the request, as non-specified parameters will retain their existing values.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "params": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "automaticGainControl",                                "settings": {                                    "enabled": true,                                    "target": -2,                                    "dynamicRange": 4                                }                            },                            {                                "id": "voiceEnhancer",                                "settings": {                                    "enabled": false,                                    "noiseSuppression": -6                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "simpleEq",                                "settings": {                                    "enabled": true,                                    "band0": -16,                                    "band1": -12                                }                            }                        \]                    }                \]            }        \]    }}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "params": {        "devices": \[            {                "id": "0",                "inputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "automaticGainControl",                                "settings": {                                    "enabled": true,                                    "target": -2,                                    "dynamicRange": 4                                }                            },                            {                                "id": "voiceEnhancer",                                "settings": {                                    "enabled": false,                                    "noiseSuppression": -6                                }                            }                        \]                    }                \],                "outputs": \[                    {                        "id": "0",                        "plugins": \[                            {                                "id": "simpleEq",                                "settings": {                                    "enabled": true,                                    "band0": -16,                                    "band1": -12                                }                            }                        \]                    }                \]            }        \]    }}
```

Successful response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings"}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "abc",    "method": "setPluginsSettings",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

### Retrieve available API versions

Use this example to retrieve a list containing available API versions on your connected devices and available plugins.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Error response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

## API specifications
### getPluginSchema

This method can be used when you want to retrieve the JSON schema for a settings object used in the response from the methods `getPluginsSettings` and `setPluginsSettings`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginSchema",  "params": {    "plugin": <string>  }}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginSchema",  "params": {    "plugin": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getPluginSchema"` | Specifies the API method. |
| `plugin=<string>` | The name of the plugin that retrieves the settings object JSON schema. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginSchema",  "data": {    "$schema": <string>,    "title": <string>,    "type": <string>,    "properties": <object>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getPluginSchema"` | Specifies the API method. |
| `data.$schema=<string>` | The URL to the core schema meta-schema. |
| `data.title=<string>` | The schema title. |
| `data.type=<string>` | The type of settings, most likely an object. |
| `data.properties=<object>` | A unique JSON schema describing the properties for the settings object returned in the response from `getPluginsSettings` and sent in the request to `setPluginsSettings`. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginSchema",  "error":{    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### getPluginsSettings

This method can be used when you want to retrieve the settings for all available plugins. Each plugin has a unique method for retrieving the current settings added to a specific device, as described in `getPluginSchema`.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings"}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getPluginsSettings"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings",  "data": {    "devices": \[      {        "id": <string>,        "inputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getPluginsSettings"` | Specifies the API method. |
| `data=<object>` | Container for method specific parameters. |
| `data.devices[]=<list of audio devices>` | List of available audio devices. |
| `<audio device>.id` | The audio device ID. |
| `<audio device>.inputs[]=<list of inputs>` | List of device inputs. |
| `inputs.id` | The input ID. |
| `input.plugins[]=<list of plugin settings>` | List of plugin settings. |
| `plugins.id` | The plugin instance identification. |
| `plugins.settings=<object>` | An object containing the settings parameters described in the response from `getPluginSchema`. |
| `<audio device>.outputs[]=<list of outputs>` | List of outputs in a device. |
| `outputs.id` | The output ID. |
| `output.plugins[]=<list of plugin settings>` | List of plugin settings. |
| `plugins.id` | The plugin instance identification. |
| `plugins.settings=<object>` | Object containing the settings parameters described by the response from `getPluginSchema`. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPluginsSettings",  "error":{    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### setPluginsSettings

This method can be used when you want to configure a plugin instance retrieved from using the `getPluginsSettings` method.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings",  "params": {    "devices": \[      {        "id": <string>,        "inputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \]      }    \]  }}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings",  "params": {    "devices": \[      {        "id": <string>,        "inputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \],        "outputs": \[          {            "id": <string>,            "plugins": \[              {                "id": <string>,                "settings": <object>              }            \]          }        \]      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context string provided by the request (optional). |
| `method="setPluginsSettings"` | Specifies the API method. |
| `params=<object>` | Container for the method specific parameters listed below. |
| `data.devices[]=<list of audio devices>` | List of available audio devices. |
| `<audio device>.id` | The audio device ID. |
| `<audio device>.inputs[]=<list of inputs>` | List of device inputs. |
| `inputs.id` | The input ID. |
| `input.plugins[]=<list of plugin settings>` | List of plugin settings. |
| `plugins.id` | The plugin instance identification. |
| `plugins.settings=<object>` | An object containing the settings parameters described in the response from `getPluginSchema`. |
| `<audio device>.outputs[]=<list of outputs>` | List of outputs in a device. |
| `outputs.id` | The output ID. |
| `output.plugins[]=<list of plugin settings>` | List of plugin settings. |
| `plugins.id` | The plugin instance identification. |
| `plugins.settings=<object>` | Object containing the settings parameters described by the response from `getPluginSchema`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=string` | A text string echoed back from the corresponding request. |
| `method="setPluginsSettings"` | Specifies the API method. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPluginsSettings",  "error":{    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### getSupportedVersions

This method can be used when you want to retrieve a list of API versions supported by your device. The list will consist of the supported major versions along with their highest supported minor version.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/audiomixer.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/audiomixer.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | A text string echoed back in the corresponding response (optional). |
| `method="getSupportedVersions"` | Specifies the API method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>","<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context string provided by the request (optional). |
| `method="getSupportedVersions"` | Specifies the API method. |
| `data.apiVersions[]=<list of versions>` | Lists the supported major versions along with their highest supported minor version. |
| `<list of versions>` | Lists the <Major>.<Minor> versions, e.g. `["1.2", "3.4"]` |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error":{    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of API specific errors.

### General error codes

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
| `2107` | TRANSPORT\_LEVEL\_ERROR | Transport level error. |