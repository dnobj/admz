---
title: Remote Syslog
url: "https://developer.axis.com/vapix/network-video/remote-syslog/"
category: vapix
subcategory: network-video
sha256: 5688ced93a60a4147b5de43fb10b47dfa18565f4c864940abd74c36e6459b226
scraped_at: "2026-01-09T15:20:54.559Z"
page_height: 44841
---

# Remote Syslog

## Description

The Remote Syslog API makes it possible to configure your Axis device to send system logs (syslogs) to a chosen number of remote servers.

### Model

The API is implemented by the `/axis-cgi/remotesyslog.cgi` called with a HTTP POST and JSON formatted input data. Doing this makes it possible to:

-   Configure up to two remote server addresses that are supposed to receive the log message from your device.
-   Configure the severity level of the log messages. For example, if "Warning" is selected, the device will send all log messages ranked warning and higher.
-   Configure the log message type. For example, the device will send all log messages if `All` is selected. If `Audit` is selected, only user behavior such as configuration through the API is sent.
-   Configure the transport protocol. Valid formats are UDP, TCP, or TCP with TLS.
-   Stop the log from sending messages to avoid clogging the system in case of a failure event, meaning that no messages will be buffered.

Methods for Remote Syslog

| Function | Description |
| --- | --- |
| `setup` | Set the configuration and send system logs to the remote servers. |
| `enable` | Send system logs to the remote servers. |
| `disable` | Stop sending system logs to the remote servers. |
| `status` | Retrieve the status information for remote system logs. |
| `test` | Test your configuration by sending system logs to the remote servers. |
| `getSupportedVersions` | Retrieve the API versions supported by the device. |

Remote Syslog properties

| Property | Description |
| --- | --- |
| `Server1.Address` | The address for `Server1` |
| `Server1.Port` | The port for `Server1` |
| `Server1.Protocol` | The protocol for `Server1` |
| `Server1.SyslogFormat` | The output format for `Server1` |
| `Server1.Severity` | The severity level for `Server1` |
| `Server1.Type` | The log type for `Server1` |
| `Server2.Address` | The address for `Server2` |
| `Server2.Port` | The port for `Server2` |
| `Server2.Protocol` | The protocol for `Server2` |
| `Server2.SyslogFormat` | The output format for `Server2` |
| `Server2.Serverity` | The severity level for `Server2` |
| `Server2.Type` | The log type for `Server2` |
| `Enabled` | Whether the remote system log feature is enabled or disabled. |

### Identification

-   **API Discovery**: `id=remote-syslog`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Setup a remote server

Use this example to configure your device to send system logs to a remote server.

#### Send syslogs over TCP

1.  Retrieve information about pre-existing server configurations using [Get status for one or several remote servers](#get-status-for-one-or-several-remote-servers).
    
2.  Configure the available remote servers.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 1999,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Error"            }        \]    }}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 1999,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Error"            }        \]    }}
```

3.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 1999,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Error"            }        \]    }}
```

If the parameter `address` is missing you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "error": {        "code": 2103,        "message": "Required parameter missing",        "details": {            "propertyName": "address"        }    }}
```

If the servers are identical, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "error": {        "code": 2201,        "message": "Identical servers not allowed"    }}
```

If too many servers are specified, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "error": {        "code": 2203,        "message": "Too many servers specified"    }}
```

If an invalid optional parameter in `params` is specified, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "error": {        "code": 2104,        "message": "Invalid parameter value specified",        "details": {            "address": "10.92.1.29",            "propertyName": "severity"        }    }}
```

If several parameters have invalid values, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "error": {        "code": 2104,        "message": "Invalid parameter value specified",        "details": {            "address": "10.92.1.29",            "propertyName": "protocol"        },        "errors": \[            {                "code": 2104,                "message": "Invalid parameter value specified",                "details": {                    "address": "172.25.77.186",                    "propertyName": "protocol"                }            },            {                "code": 2104,                "message": "Invalid parameter value specified",                "details": {                    "address": "172.25.77.186",                    "propertyName": "severity"                }            }        \]    }}
```

#### Send syslogs over UDP

1.  Retrieve information about pre-existing server configurations using [Get status for one or several remote servers](#get-status-for-one-or-several-remote-servers).
    
2.  Configure the remote servers.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "protocol": "UDP"            },            {                "address": "172.25.77.186",                "protocol": "UDP"            }        \]    }}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "protocol": "UDP"            },            {                "address": "172.25.77.186",                "protocol": "UDP"            }        \]    }}
```

3.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "UDP",                "syslogFormat": "RFC5424",                "severity": "Warning"            },            {                "address": "172.25.77.186",                "port": 514,                "protocol": "UDP",                "syslogFormat": "RFC5424",                "severity": "Warning"            }        \]    }}
```

For possible error responses, see [Send syslogs over TCP](#send-syslogs-over-tcp).

#### Send syslogs over TLS

It is possible for the Axis device to validate the remote syslog authenticity by attaching CA certificates to the TLS configuration. To do this you must first install the CA certificate by using either the WEB UI or ONVIF. The following request is used when you want to configure these CA certificates.

```bash
http://<servername>/vapix/services
```

SOAP input parameters

```bash
<?xml version="1.0" encoding="UTF-8" ?><Envelope xmlns="http://www.w3.org/2003/05/soap-envelope">    <Header />    <Body        xmlns:acertificate="http://www.axis.com/vapix/ws/certificates"        xmlns:acert="http://www.axis.com/vapix/ws/cert">        <SetCertSet xmlns="http://www.axis.com/vapix/ws/certificates">            <CertSetName>RemoteSyslog</CertSetName>            <CertSet>                <acert:Certificates />                <acert:CACertificates>                    <acert:Id>CertificateID\_1</acert:Id>                    <acert:Id>CertificateID\_2</acert:Id>                </acert:CACertificates>                <acert:TrustedCertificates />            </CertSet>        </SetCertSet>    </Body></Envelope>
```

1.  In order to use a CA certificate, you must first install it using either the WEB UI or ONVIF.
    
2.  Retrieve the server configurations using [Get status for one or several remote servers](#get-status-for-one-or-several-remote-servers).
    
3.  Configure the remote servers.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "protocol": "TLS"            }        \]    }}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "params": {        "servers": \[            {                "address": "10.92.1.29",                "protocol": "TLS"            }        \]    }}
```

4.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "setup",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 6514,                "protocol": "TLS",                "syslogFormat": "RFC5424",                "severity": "Warning"            }        \]    }}
```

For possible error responses, see [Send syslogs over TCP](#send-syslogs-over-tcp).

### Disable/Enable and send the syslog to a remote server

Use this example to either disable or enable the system log for the remote servers.

#### Disable syslog from remote server

1.  Retrieve server configurations using [Get status for one or several remote servers](#get-status-for-one-or-several-remote-servers).
    
2.  Disable the system log from a remote server.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "disable"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "disable"}
```

3.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "disable",    "data": {        "enabled": false,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 5140,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Emergency"            }        \]    }}
```

#### Enable syslog from remote server

1.  Enable the system log to send to a specified number of remote servers.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "enable"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "enable"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "enable",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 5140,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Emergency"            }        \]    }}
```

If no server is configured, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "enable",    "error": {        "code": 2200,        "message": "No server configured"    }}
```

If the servers are identical, you will receive the following error response:

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "enable",    "error": {        "code": 2201,        "message": "Identical servers not allowed"    }}
```

### Get status for one or several remote servers

Use this example to retrieve status information from a specified number of remote servers.

1.  Request status information from a remote server

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "status"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "status"}
```

2.  Parse the JSON response.

a) If both servers are configured you will get the following response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "status",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "172.25.77.186",                "port": 1999,                "protocol": "UDP",                "syslogFormat": "RFC5424",                "severity": "Debug"            }        \]    }}
```

b) If no server has been configured you will get the following response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "stauts",    "data": {        "enabled": false,        "servers": \[\]    }}
```

c) If only one server has been configured you will get the following response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "status",    "data": {        "enabled": false,        "servers": \[            {                "address": "172.25.77.186",                "port": 5140,                "protocol": "UDP",                "syslogFormat": "RFC3164",                "severity": "Emergency"            }        \]    }}
```

d) If `Server1.Address` has not been configured and `Server2.Address` has been configured through the Parameter handling API you will get the following response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "status",    "data": {        "enabled": false,        "servers": \[\]    }}
```

### Send a test message to the remote servers

Use this example to send a test system log message to the remote server.

1.  Retrieve information about pre-existing server configurations using [Get status for one or several remote servers](#get-status-for-one-or-several-remote-servers).
    
2.  Send a test system log message to a remote server.
    

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "test"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "test"}
```

3.  Parse the JSON response

Successful response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "test",    "data": {        "enabled": true,        "servers": \[            {                "address": "10.92.1.29",                "port": 514,                "protocol": "TCP",                "syslogFormat": "RFC3164",                "severity": "Warning"            },            {                "address": "2001:4860:4860::8888",                "port": 5140,                "protocol": "TCP",                "syslogFormat": "RFC5424",                "severity": "Emergency"            }        \]    }}
```

Error response

```bash
{    "apiVersion": "1.0",    "context": "Client defined request ID",    "method": "test",    "error": {        "code": 2202,        "message": "Remote syslog is disabled, send test message is not possible"    }}
```

### Get supported versions

Use this example to retrieve a list of API versions supported by your device.

1.  Get a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Error response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 2102,        "message": "Method not supported"    }}
```

## API specifications
### setup

This API method is used when you want to configure the remote servers provided by the API. If the request is successful, you will also be able to send system log messages with properties specified in the table below.

| Property | Description |
| --- | --- |
| `address` | Specifies the address of the remote server. |
| `port` | Specifies the UDP or TCP port. |
| `protocol` | Specifies the protocol. |
| `syslogFormat` | Specifies the system log output format. |
| `severity` | Specifies the severity of the log messages. |
| `type` | Specifies the log message type. |

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setup",  "params": {    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<Audit | All>"      }    \]  }}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setup",  "params": {    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<Audit | All>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setup"` | The operation that should be performed. |
| `params.servers[]` | The maximum number of servers possible to configure in a request is limited to 2. These servers can be removed if the server list is empty. |
| `params.servers[].address=<string>` | Specifies the remote server address. |
| `params.servers[].port=<integer>` | Specifies the port. The maximum number of ports that can be specified is 65535 (optional). |
| `params.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol that should be used to send syslogs to a remote server. If not set in the request, TLS will be used as the default (optional). Possible values are:  
  
\- `UDP`  
\- `TCP`  
\- `TLS` |
| `params.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. If not set in the request, RFC5424 will be used as the default (optional). Possible values are:  
  
\- `AXIS`: The AXIS syslog protocol is used.  
\- `RFC3164`: The BSD syslog protocol is used.  
\- `RFC5424`: The syslog protocol is used. |
| `params.servers[].severity=<string>` | Specifies the syslog severity. Warning will be used as the default (optional). Example: If "Warning" is selected, your device will send all syslogs with `Warning`, `Error`, `Alert` and `Emergency` severity. Possible severity levels are listed in the table below. |
| `params.servers[].type=<string>`  
_Optional_ | Specifies what log type that will be created. If this parameter is not set `All` will be used by default. Valid values:  
`Audit`: Audit logs are sent.  
`All`: All logs are sent. |

Severity levels

| Severity level | Description |
| --- | --- |
| `Emergency` | System is unusable. |
| `Alert` | Action must be taken immediately. |
| `Critical` | Critical conditions. |
| `Error` | Error conditions. |
| `Warning` | Warning conditions. |
| `Notice` | Normal but significant condition. |
| `Informational` | Informational messages. |
| `Debug` | Debug level messages. |

Default port list

| Protocol | AXIS | RFC3164 | RFC5424 |
| --- | --- | --- | --- |
| `UDP` | 514 | 514 | 514 |
| `TCP` | 514 | 514 | 601 |
| `TLS` | 6514 | 6514 | 6514 |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setup",  "data": {    "enabled": <boolean>,    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<All | Audit>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `data.enabled=<boolean>` | Specifies if the remote syslog feature was enabled. |
| `data.servers[]` | Specifies the list of servers. The list will be empty if no servers has been configured. |
| `data.servers[].address` | Specifies the address of the remote server. |
| `data.servers[].port=<integer>` | Specifies the port. The maximum number that can be specified is 65535. |
| `data.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol. |
| `data.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. |
| `data.servers[].severity` | Specifies the syslog severity. |
| `data.servers[].type` | Specifies the syslog output type. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setup",  "error": {    "code": <integer error code>,    "message": <string>,    "details": {      "address": <string>,      "propertyName": <string>    },    "errors": \[      {        "code": <integer error code>,        "message": <string>,        "details": {          "address": <string>,          "propertyName": <string>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `error.code=<integer error code>` | The error code for the first encountered error. |
| `error.message=<string>` | The error message for the first encountered error. |
| `error.details.address=<string>` | The server related to the error code (optional). |
| `error.details.propertyName=<string>` | The property name related to the error code (optional). |
| `error.errors[]` | Available when there are more than one error (optional). |
| `error.errors[].code=<integer error code>` | The error code. |
| `error.errors[].message=<string>` | The error message corresponding second error code. |
| `error.errors[].details.address=<string>` | The server related to the second error code (optional). |
| `error.errors[].details.propertyName=<string>` | The property name related to the second error code (optional). |

**General errors**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `error.code=<integer error code>` | The error code for the first encountered error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2201` | Identical servers not allowed. |
| `2203` | Too many servers specified. |

See [General error codes](#general-error-codes) for a complete list of error codes.

### enable

This API method is used when you want to enable system logs to send messages to a remote server.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "enable"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "enable"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="enable"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "data": {    "enabled": <boolean>,    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<All | Audit>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `data.enabled=<boolean>` | Specifies whether the remote syslog feature is enabled. |
| `data.servers[]` | Specifies the list of servers. The list will be empty if no servers were configured. |
| `data.servers[].address` | Specifies the address of the remote server. |
| `data.servers[].port=<integer>` | Specifies the port. The maximum port that can be specified is 65535. |
| `data.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol. |
| `data.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. |
| `data.servers[].severity` | Specifies the syslog severity for filtering. |
| `data.servers[].type` | Specifies the syslog output type. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `error.code=<integer error code>` | The error code for the first encountered error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2200` | No server configured. |
| `2201` | Identical servers not allowed. |

See [General error codes](#general-error-codes) for a complete list of error codes.

### disable

This API method is used when you want to disable system logs from sending messages to a remote server.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "disable"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "disable"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="disable"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "data": {    "enabled": <boolean>,    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<All | Audit>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `data.enabled=<boolean>` | Specifies whether the remote syslog feature is enabled. |
| `data.servers[]` | Specifies the list of servers. The list will be empty if no servers were configured. |
| `data.servers[].address` | Specifies the address of the remote server. |
| `data.servers[].port=<integer>` | Specifies the port. The maximum port that can be specified is 65535. |
| `data.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol. |
| `data.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. |
| `data.servers[].severity` | Specifies the syslog severity for filtering. |
| `data.servers[].type` | Specifies the syslog output type. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `error.code=<integer error code>` | The error code for the first encountered error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

No specific errors exist for this method. See [General error codes](#general-error-codes) for a complete list of error codes.

### status

This API method is used when you want to retrieve the current configuration of the remote servers.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "status"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "status"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="status"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "data": {    "enabled": <boolean>,    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "type": "<All | Audit>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `data.enabled=<boolean>` | Specifies whether the remote syslog feature is enabled. |
| `data.servers[]` | Specifies the list of servers. The list will be empty if no servers were configured. |
| `data.servers[].address` | Specifies the address of the remote server. |
| `data.servers[].port=<integer>` | Specifies the port. The maximum port that can be specified is 65535. |
| `data.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol. |
| `data.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. |
| `data.servers[].severity` | Specifies the syslog severity for filtering. |
| `data.servers[].type` | Specifies the syslog output type. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `error.code=<integer error code>` | The error code for the first encountered error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

No specific error codes exist for this method. See [General error codes](#general-error-codes) for a complete list of error codes.

### test

This API method is used when you want to generate log messages for all severity levels, however, only configured severity level log messages will be sent to the remote servers.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "test"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "test"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion:"<major>.<minor>"` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="test"` | The operation that should be performed. |

info

This method is used when you want to generate log messages. It doesn't check if the messages are received on the server.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "data": {    "enabled": <boolean>,    "servers": \[      {        "address": <string>,        "port": <integer>,        "protocol": "<UDP | TCP | TLS>",        "syslogFormat": "<RFC3164 | RFC5424>",        "severity": "<Emergency | Alert | Critical | Error | Warning | Notice | Informational | Debug>",        "test": "<All | Audit>"      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `method` | The operation that was performed. |
| `data.enabled=<boolean>` | Specifies whether the remote syslog feature is enabled. |
| `data.servers[]` | Specifies the list of servers. The list will be empty if no servers were configured. |
| `data.servers[].address` | Specifies the address of the remote server. |
| `data.servers[].port=<integer>` | Specifies the port. The maximum port that can be specified is 65535. |
| `data.servers[].protocol="<UDP | TCP | TLS>"` | Specifies the protocol. |
| `data.servers[].syslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. |
| `data.servers[].severity` | Specifies the syslog severity for filtering. |
| `data.servers[].type` | Specifies the syslog output type. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | The context that was used when the request was made (optional). |
| `error.code=<integer error code>` | The error code for the first encountered error code. |
| `error.message=<string>` | The error message corresponding to the error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2202` | Remote syslog is disabled, sending test messages is not possible. |

See [General error codes](#general-error-codes) for a complete list of error codes.

### getSupportedVersions

This API method is used when you want to retrieve a list of supported API versions.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/remotesyslog.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/remotesyslog.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>","<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="getSupportedVersions"` | The operation that was performed. |
| `data.apiVersions[]=<list of versions>` | Specifies the list of supported versions and includes all major versions together with their highest supported minor version. |
| `<list of versions>` | The list of "<Major>.<Minor>" versions e.g. \["1.4", "2.5"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersions": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

No specific errors exist for this method. See [General error codes](#general-error-codes) for a complete list of error codes.

### API.RemoteSyslog1

This section will show you how to handle parameters found in this API.

#### API.RemoteSyslog1.Server

The parameters found in this group are used when you want to configure the servers. Please note that any changes made to these parameters will disable remote logging and put `API.RemoteSyslog1.Enabled` to `false`. Also, changes made here might now be shown in the JSON responses. For example, if `Server1.Address` is empty, no servers will be shown, while if `Server2.Address` is empty, only `Server1` parameters will be shown.

-   **List security level**: Admin
-   **Update security level**: Admin

```bash
root.API.RemoteSyslog1.Server#.<parameter>
```

Valid values for `#` ranges from 1 to 2.

| Parameter | Description |
| --- | --- |
| `Address=<string>` | Specifies the address of the remote server. |
| `Port=<integer>` | Specifies the port. Default port value is `6514`, while the maximum number of ports that can be specified is `65535`. |
| `Protocol="<UDP | TCP | TLS>"` | Specifies the protocol. Default protocol is `TLS`. |
| `SyslogFormat="<AXIS | RFC3164 | RFC5424>"` | Specifies the syslog output format. Default output format is `RFC5424`. |
| `Severity` | Specifies the severity filtering for the syslog. Default severity is `Warning`. See [setup](#setup) for a complete list of severity levels. |
| `Type="<Audit | All>"` | Specifies the syslog output type. The default type is `All`. |

#### API.RemoteSyslog1.Enabled

This parameter is used when you want to either enable or disable the remote syslog. `Enabled` can be either `true` or `false`, with `false` being the default. When `Enable` is `true` the logging service will be configured with the current values. It is possible to probe the `Enabled` flag, and if it is `false` after being set to `true`, the configured values where incomplete and the configuration failed. Please note that a valid `Server1.Address` is required to enable the feature, meaning that using `Server2.Address` on its own is not possible.

-   **List security level**: Admin
-   **Update security level**: Admin

```bash
root.API.RemoteSyslog1.Enabled
```

| Parameter | Description |
| --- | --- |
| `Enabled=<boolean>` | Specifies whether the remote syslog feature has been enabled. |

### General error codes

The error codes for this API are sorted into the following ranges:

**1100–1199**

Generic errors common to many API:s and reserved for server errors, e.g. "Could not read configuration from file". The cause can be seen in the server log and the problems can in some cases be solved by restarting the device.

**1200–1999**

API-specific server errors.

**2100–2199**

Generic error codes common to many API:s and reserved for client errors, e.g. "Invalid parameter". These errors can be solved by changing the input data to the API.

**2200–2999**

API-specific client errors. Codes in this range may collide between different API:s.

General error codes

| Code | Description |
| --- | --- |
| `1100` | Internal error |
| `2100` | API version not supported |
| `2101` | Invalid JSON |
| `2102` | Method not supported |
| `2103` | Required parameter missing |
| `2104` | Invalid parameter value specified |
| `2105` | Authorization failed |
| `2106` | Authentication failed |
| `2107` | Request too large |

Method specific error codes

| Code | Description |
| --- | --- |
| `2200` | No server configured |
| `2201` | Identical servers not allowed |
| `2202` | Remote syslog is disabled, sending test messages is not possible |
| `2203` | Too many servers specified |