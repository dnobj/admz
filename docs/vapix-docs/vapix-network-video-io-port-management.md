---
title: I/O port management
url: "https://developer.axis.com/vapix/network-video/io-port-management/"
category: vapix
subcategory: network-video
sha256: 69d650958f1d3c216a5145a4bd9ce7b8722671364afea77a4d76fe9f07018e4c
scraped_at: "2026-01-09T15:20:06.870Z"
page_height: 27723
---

# I/O port management

## Description

The I/O port management API makes it possible to retrieve information about the ports and apply product dependent configurations. The API should not be confused with Supervised I/O, which is used to set up to detect tampering and breaks of the cables.

### Model

The API is built around the `/axis-cgi/io/portmanagement.cgi`, which shall be called using the HTTP POST method with JSON formatted data as its input. API includes the following methods:

| Methods | Description |
| --- | --- |
| `getPorts` | Retrieves all ports and their capabilities. |
| `setPorts` | Configures anything from one to several ports. Some of the available options are:  
\- Setting a nice name that can be used in the user interface.  
\- Configuring the states and what constitutes a normal and triggered state respectively. This will make triggers activate in either open or closed circuits.  
The reason the change is treated as a nice name is because it doesn’t affect the underlying behavior of the port. Devices with configurable ports can change the direction to either `input` or `output`. |
| `setStateSequence` | Applies a sequence of state changes with a delay in milliseconds between states. This method can only be used on output ports. |
| `getSupportedVersions` | Retrieves information on which API versions the product is supporting. |

The following events are related to the API:

```bash
tns1:Device/tnsaxis:IO/tnsaxis:Porttns1:Device/Trigger/DigitalInputtns1:Device/Trigger/Relay
```

### Identification

-   **API discovery**: `id=io-port-management`
-   **AXIS OS**: 9.70 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Retrieve information

Use this example to check which I/O ports that are currently available, their states and the capabilities on your device. Example of capabilities are if the port is configurable and what direction it has, which is important to know as not all capabilities can be applied to both directions.

#### Retrieve port information for all ports

1.  Request port information for all ports with the following JSON request.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getPorts"}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getPorts"}
```

2.  Parse the JSON response. The `data` object in the response will return the `numberOfPorts` and depending on how many ports being returned the number of objects will be identical in `items`. The property names that can be included in the `items` array are listed in the table below.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getPorts",    "data": {        "numberOfPorts": 3,        "items": \[            {                "port": "0",                "state": "closed",                "configurable": true,                "readonly": true,                "usage": "Button",                "direction": "input",                "name": "Call button",                "normalState": "open"            },            {                "port": "1",                "state": "closed",                "configurable": true,                "usage": "Door",                "direction": "output",                "name": "Output 1",                "normalState": "closed"            },            {                "port": "2",                "state": "closed",                "configurable": true,                "usage": "",                "direction": "input",                "name": "Input 2",                "normalState": "closed"            }        \]    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "getPorts",    "error": {        "code": 4004,        "message": "Invalid parameter(s)"    }}
```

### Configure port

Use this example to configure the ports of the device. Possible configurations includes:

-   Putting a description on the port to indicate what the port is controlling (`usage`).
-   Setup the port to be either an input or an output (`direction`).
-   Configure a user friendly name for the port (`name`).
-   Configure what state that should be considered the normal state (`normalState`).
-   Change the state of an output port (`state`).

#### Configure I/O ports with all values

1.  Retrieve the I/O port IDs using [Retrieve port information for all ports](#retrieve-port-information-for-all-ports).
    
2.  Request to apply changes to the I/O ports with the following JSON request. Please note that port 0, which has `readonly=0`, can not be modified.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "params": {        "ports": \[            {                "port": "0",                "usage": "Button",                "direction": "input",                "name": "Call button",                "normalState": "open"            },            {                "port": "1",                "usage": "Door",                "direction": "output",                "name": "Output 1",                "normalState": "open",                "state": "open"            },            {                "port": "2",                "usage": "",                "direction": "input",                "name": "Input 2",                "normalState": "closed"            }        \]    }}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "params": {        "ports": \[            {                "port": "0",                "usage": "Button",                "direction": "input",                "name": "Call button",                "normalState": "open"            },            {                "port": "1",                "usage": "Door",                "direction": "output",                "name": "Output 1",                "normalState": "open",                "state": "open"            },            {                "port": "2",                "usage": "",                "direction": "input",                "name": "Input 2",                "normalState": "closed"            }        \]    }}
```

3.  Parse the JSON response. This will echo the ports of the `params` object in the `data` object if the request is successful.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "data": {        "ports": \["0", "1", "2"\]    }}
```

4.  Parse the JSON failed response if the request is a failure.

a) If the failure is generic, for example if the required parameter `port` is missing, the whole request will fail.

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "error": {        "code": 2103,        "message": "Required parameter missing"    }}
```

b) If the failure is in an optional parameters in the `params` object (and only one error), only the reported error has failed while the other parameters are successfully set.

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "error": {        "code": 2104,        "message": "Invalid parameter value specified",        "details": {            "port": "0",            "propertyName": "direction"        }    }}
```

c) If the failure is in an optional parameter in the `params` object (with multiple errors), only the reported error has failed while the other parameters are successfully set.

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "error": {        "code": 2104,        "message": "Invalid parameter value specified",        "details": {            "port": "0",            "propertyName": "direction"        },        "errors": \[            {                "code": 1100,                "message": "Internal error",                "details": {                    "port": "1"                }            },            {                "code": 2104,                "message": "Invalid parameter value specified",                "details": {                    "port": "2",                    "propertyName": "direction"                }            },            {                "code": 2104,                "message": "Invalid parameter value specified",                "details": {                    "port": "2",                    "propertyName": "normalState"                }            }        \]    }}
```

#### Set the direction of the I/O port

1.  Retrieve the I/O port IDs using [Retrieve port information for all ports](#retrieve-port-information-for-all-ports).
    
2.  Send a request to apply changes to the I/O ports with the following JSON request.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "params": {        "ports": \[            {                "port": "1",                "direction": "input"            }        \]    }}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "params": {        "ports": \[            {                "port": "1",                "direction": "input"            }        \]    }}
```

3.  Parse the JSON response. This will echo the ports of the `params` object in the `data` object if the request is successful.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setPorts",    "data": {        "ports": \["1"\]    }}
```

4.  Parse the JSON response and the error responses from the previous example if the request failed.

#### Set a sequence of state changes on the output port

1.  Retrieve the I/O port IDs using [Retrieve port information for all ports](#retrieve-port-information-for-all-ports).
    
2.  Request a sequence of state changes on the output port, that includes a delay in milliseconds between state changes, using the following JSON request
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setStateSequence",    "params": {        "port": "1",        "sequence": \[            {                "state": "open",                "time": 1000            },            {                "state": "closed",                "time": 2000            },            {                "state": "open",                "time": 1000            },            {                "state": "closed",                "time": 4000            },            {                "state": "open",                "time": 0            }        \]    }}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setStateSequence",    "params": {        "port": "1",        "sequence": \[            {                "state": "open",                "time": 1000            },            {                "state": "closed",                "time": 2000            },            {                "state": "open",                "time": 1000            },            {                "state": "closed",                "time": 4000            },            {                "state": "open",                "time": 0            }        \]    }}
```

3.  Parse the JSON response. This will echo the ports of the `params` object in the `data` object if the request is successful.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setStateSequence",    "data": {        "port": "1"    }}
```

4.  Parse the JSON error response.

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setStateSequence",    "error": {        "code": 2104,        "message": "Invalid parameter value specified"    }}
```

Please note that the state sequence is executed only once. The last state will be the permanent until a new sequence is launched.

The `setStateSequence` request will return immediately, but issuing a new sequence while another sequence is running will result in an error. Changing `direction` or `normalState` will cancel an ongoing sequence. It is possible to change `state` during a running sequence, but that state will be overridden when the next part of the sequence is executed.

### Get supported versions

Use this example to retrieve a list of API versions that the device is supporting.

1.  Retrieve a list of supported API versions using the following JSON request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response to find out if the operation succeeded.

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Error response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 2102,        "message": "Method not supported"    }}
```

## API specifications
### getPorts

This CGI method can be used to retrieve information about all ports on the device and their capabilities.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPorts"}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPorts"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getPorts"` | The performed method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPorts",  "data": {    "numberOfPorts": <0-255>,    "items": \[      {        "port": <string>,        "state": "<open | closed>",        "configurable": <boolean>,        "readonly": <boolean>,        "usage": <string>,        "direction": "<input | output>",        "name": <string>,        "normalState": "<open | closed>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the client in the corresponding request (optional). |
| `method` | The method that was performed. |
| `data.numberOfPorts` | The number of ports available on the device. |
| `data.items[]` | Omitted if `numberOfPorts` is zero. |
| `data.items[].port=<string>` | The port ID. |
| `data.items[].state="<open | closed>"` | The current state of the port. |
| `data.items[].configurable=<boolean>` | Indicates if the port direction can be configured. |
| `data.items[].readonly=<boolean>` | Tells if the port is read-only and is only present if the value is true. |
| `data.items[].usage=<string>` | Tells the intended usage of a port. In this case `usage` is treated as a nice name. Any underlying behavior will not be affected by its value. |
| `data.items[].direction="<input | output>"` | The direction of the port. |
| `data.items[].name=<string>` | Specifies the nice name of the port. |
| `data.items[].normalState="<open | closed>"` | Specifies the normal state of the port. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getPorts",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the client in the corresponding request (optional). |
| `method` | The method that was performed. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message corresponding to the `error code`. |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setPorts

This CGI method can be used to configure the I/O port. Possible property names are listed in the table below.

| Property name | Description |
| --- | --- |
| `port` | The port ID. |
| `usage` | Tells the intended usage of a port, which is useful when you want an application to handle a port in a specific way. In this case `usage` is treated as a nice name. Example of values are: Button, Door, REX and Tampering. |
| `direction` | Tells if the port is configured as an `input` or `output`. This parameters is read-only for non-configurable ports. |
| `name` | The nice name of the port. |
| `normalState` | Defines the normal state for the port. |
| `state` | Applies the current state for the port (output port only). |

A request can apply anything from one to all properties above for one or many ports. It can generate one of the following responses:

-   If everything was properly set, a successful response will be generated.
-   If a generic error occurred, an error response will be generated. In this case, the entire request is considered a failure.
-   If some property value(s) wasn’t able to be set, an error response will be generated. The property for a port that was not successfully set will be pointed out in the error with a `port` and `propertyName`.

Changing the `normalState` of the port changes the logical state according to the table below. If the `normalState` is specified, this state transition will take priority before the current state is changed to the value specified in the `state`.

Old value

| normalState | state |
| --- | --- |
| open | open |
| open | closed |
| closed | open |
| closed | closed |

New value

| normalState | state |
| --- | --- |
| closed | closed |
| closed | open |
| open | closed |
| open | open |

Unlike output ports, an input port is not affected by `normalState` changes, but changes made to an input port may trigger a port active event.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPorts",  "params": {    "ports": \[      {        "port": <string>,        "usage": <string>,        "direction": "<input | output>",        "name": <string>,        "normalState": "<open | closed>",        "state": "<open | closed>"      }    \]  }}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPorts",  "params": {    "ports": \[      {        "port": <string>,        "usage": <string>,        "direction": "<input | output>",        "name": <string>,        "normalState": "<open | closed>",        "state": "<open | closed>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setPorts"` | The performed method. The maximum number of ports that can be configured in one request is limited to 256. |
| `params.ports[].port=<string>` | Specifies the port ID affected by the current request. The port is retrieved by using the method `getPorts`. If all optional parameters are omitted, the request will not change anything and the response will not include the current port in the port list. |
| `params.ports[].usage=<string>` | Specifies the intended usage of the port (optional). |
| `params.ports[].direction="<input | output>"` | Specifies the direction that should be applied to the port (optional). `input`: Configure the port to be an input port. `output`: Configure the port to be an output port. |
| `params.ports[].name=<string>` | Specifies the nice name that should be used on the specified port (optional). |
| `params.ports[].normalState="<open | closed>"` | Specifies the normal state of the port (optional). `open`: Configure the open circuit state to be the normal state of the port. `closed`: Configure the closed circuit state to be the normal state of the port. |
| `params.ports[].state="<open | closed>"` | Specifies the current state of the output port (optional). This can only be used by output ports. `open`: Sets the current state of the output port to open circuit. `closed`: Sets the current state of the output port to closed circuit. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPorts",  "data": {    "ports": \["<Port1>", "<Port2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the client in the corresponding request (optional). |
| `method` | The method that was performed. |
| `data.ports[]=<list of ports>` | List of the affected port IDs: `<list of ports>`: List of "<Port>", e.g. \["1", "2"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setPorts",  "error": {    "code": <integer error code>,    "message": <string>,    "details": {      "port": <string>,      "propertyName": <string>,    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "port": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the user in the corresponding request (optional). |
| `method` | The method that was performed. |
| `error.code=<integer error code>` | The error code of the first encountered error. |
| `error.message=<string>` | The error message corresponding to the `error.code`. |
| `error.details.port=<string>` | The port related to `error.code` (optional). |
| `error.details.propertyName=<string>` | The property name related to `error.code` (optional). |
| `error.errors[]` | Available only if there is more than one error (optional). |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding to the `error.errors[].code`. |
| `error.errors[].details.port=<string>` | The port related to the `error.errors[].code` (optional). |
| `error.errors[].details.propertyName=<string>` | The property name related to the `error.errors[].code` (optional). |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### setStateSequence

This CGI method can be used to create a sequence of state changes on your output ports. Between states there should also be a delay measured in milliseconds and the sequence will only be executed once, with the last state becoming the permanent one until a new sequence is launched.

Issuing a new sequence while another sequence is running will result in an error, while changing either `direction` or `normalstate` will cancel any ongoing sequence. It is possible to change `state` during a running sequence, although that state will be overridden by the next part of the sequence.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setStateSequence",  "params": {    "port": <string>,    "sequence": \[      {        "state": "<open | closed>",        "time": <integer>      }    \]  }}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setStateSequence",  "params": {    "port": <string>,    "sequence": \[      {        "state": "<open | closed>",        "time": <integer>      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion="<major>.<minor>"` | The API version that should be used. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setStateSequence"` | The method that should be used. |
| `params.port=<integer>` | Specifies the affected port ID. Retrieved by using the method [getPorts](#getports). |
| `params.sequence[].state="<open | closed>"` | Specifies the state that should be set. |
| `params.sequence[].time=<integer>` | Specifies the delay in milliseconds between state changes. The maximum time that can be specified is 65535 milliseconds. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setStateSequence",  "data": {    "port": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the user in the corresponding request (optional). |
| `method` | The method that was performed. |
| `data.port` | The affected port ID. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setStateSequence",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the user in the corresponding request (optional). |
| `method` | The method that was performed. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message that corresponds to the `error.code` |

**Error codes**

| Code | Description |
| --- | --- |
| `2200` | State sequence already ongoing. |

See [General error codes](#general-error-codes) for a list of potential errors.

### getSupportedVersions

This CGI method can be used to retrieve a list of supported API versions.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/io/portmanagement.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/io/portmanagement.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
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
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context` | A text string that will be echoed back if it was provided by the user in the corresponding request (optional). |
| `method` | The method that was performed. |
| `data.apiVersions[]=<list of versions>` | A list of supported versions containing all major versions with the highest supported minor version for each. |
| `<list of versions>` | List of <Major>.<Minor> versions, e.g. \["1.4", "2.5"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used. |
| `context` | A text string that will be echoed back if it was provided by the user in the corresponding request (optional). |
| `method` | The method that was performed. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message that corresponds to the `error.code` |

**Error codes**

See [General error codes](#general-error-codes) for a list of potential errors.

### General error codes

The table below will list the general error codes that can occur for any CGI method. The codes are split into the following ranges:

-   **1100–1199:** Generic error codes that are common for many API: s, such as server errors, and can usually be solved by restarting the device.
-   **1200–1999:** API-specific server errors occurring when different API: s collide.
-   **2100–2199:** Generic error codes that are common for many API: s, such as client errors, and can usually be solved by changing the input data to the API.
-   **2200–2999:** API-specific user errors occurring when different API: s collide.

| Code | Description |
| --- | --- |
| `1100` | Internal error. |
| `2100` | API version not supported. |
| `2101` | Invalid JSON. |
| `2102` | Method not supported. |
| `2103` | Required parameter missing. |
| `2104` | Invalid parameter value specified. |
| `2105` | Authorization failed. |