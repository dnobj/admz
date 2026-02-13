---
title: Serial port API
url: "https://developer.axis.com/vapix/network-video/serial-port-api/"
category: vapix
subcategory: network-video
sha256: ccb50052ca2d4cc32b29a6c65cd5f66b68c2ac743c51343a20c94b4d43ebf1de
scraped_at: "2026-01-09T15:20:57.607Z"
page_height: 21786
---

# Serial port API

## Description

The Serial port API is used to configure serial ports on Axis products. The API description in this section is intended to be used to get knowledge about how to change settings for the serial port. For example when to change serial port settings for an uploaded PTZ driver or get to know what type of settings that could be changed when adding some type of device with a serial port to an Axis product.

The serial port allows connection of equipment such as analog PTZ cameras to Axis products. The equipment is connected to a serial port on the Axis product, which in turn works as a translator between a network client and the equipment.

Ports can be a physical serial ports or remote port clients. Remote port clients connect to other CPU:s that have remote port servers open (the other product has a physical serial port that is made available by the server). The remote port connection is used for daisy chain cameras on multi CPU video encoders. A daisy chain connection means virtually connecting several cameras (without physical serial ports) to a CPU with a physical serial port.

For both types of ports, there is a port manager that manages the port. The port manager makes it possible to share the port, for example for PTZ control from multiple video channels.

Settings for port managers are stored in the parameter group `PortManager.P#`. Serial ports are described in the group `Serial.Ser#`, and remote port clients in `RemotePort.R#`.

![Data types that can be sent using a physical serial port](/assets/images/serial-port-api.t10038207-28dbbf6148ebf418e23f2eeb4ef31772.png)

The image above describes the different types of data that can be sent using a physical serial port.

![Overview of a connection between a remote serial port, a remote port server and a serial port](/assets/images/serial-port-api.t10038208-00e340e42f20d33f6ca86d8475d9ed4e.png)

The image above describes an overview of a connection between a remote serial port, a remote port server and a serial port. The remote port forwards data from a virtual port on a CPU to a physical port on another CPU. This is used in multi CPU encoders to share the serial port between the CPU:s. This functionality is only intended for multi CPU video encoders. Remote port is similar to Generic TCP/IP, but in addition to Generic TCP/IP it also adds a protocol header to the data payload.

## Prerequisites
### Identification

-   **API Discovery**: `id=serial-port`
    
-   **Property**: `Properties.API.HTTP.Version=3`
    
-   **Property**: `Properties.Serial.Serial=yes`
    
-   AXIS OS: 5.20 or later
    
-   Product category: Axis products with serial ports.
    

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

Send data to a device connected to the serial port. The argument `write` specifies how much data that should be sent.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/serial.cgi?write=2153435253500c0d"
```

```bash
GET /axis-cgi/com/serial.cgi?write=2153435253500c0dHost: <servername>
```

Read `3` bytes from the selected serial port with a time out of 2000 milliseconds.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/serial.cgi?read=3&timeout=2000"
```

```bash
GET /axis-cgi/com/serial.cgi?read=3&timeout=2000Host: <servername>
```

Set the baud rate (transmission speed) to `9600` for the serial port and the number of databits included in the set to `8`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Serial.Ser1.BaudRate=9600&DataBits=8"
```

```bash
GET /axis-cgi/param.cgi?action=update&Serial.Ser1.BaudRate=9600&DataBits=8Host: <servername>
```

Enable a generic TCP server on port `3000`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&PortManager.P0.GenericTCPServer.Enabled=yes&PortManager.P0.GenericTCPServer.Listener.Enabled=yes&PortManager.P0.GenericTCPServer.Listener.Port=3000&PortManager.P0.PortEnabled=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&PortManager.P0.GenericTCPServer.Enabled=yes&PortManager.P0.GenericTCPServer.Listener.Enabled=yes&PortManager.P0.GenericTCPServer.Listener.Port=3000&PortManager.P0.PortEnabled=yesHost: <servername>
```

Clients that connect to port `3000` will get a TCP socket where raw data can be sent and received. That data will be forwarded to and from the serial port.

Request the remote port client to be managed by port manager `0`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&PortManager.P0.PortType=RemotePort"
```

```bash
GET /axis-cgi/param.cgi?action=update&PortManager.P0.PortType=RemotePortHost: <servername>
```

Set a remote port server to listen on port `2500` of the host `10.0.0.1`, and connect the remote port client to it.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&RemotePort.R3.Host=10.0.0.1&RemotePort.R3.Port=2500&PortManager.P0.PortEnabled=yes"
```

```bash
GET /axis-cgi/param.cgi?action=update&RemotePort.R3.Host=10.0.0.1&RemotePort.R3.Port=2500&PortManager.P0.PortEnabled=yesHost: <servername>
```

PTZ commands sent out through the remote port client will reach the remote PTZ server.

Open port 2 (`PortManager.P0`), if not already opened, and connect video source 2 to it.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/serial.cgi?port=2&camera=2"
```

```bash
GET /axis-cgi/com/serial.cgi?port=2&camera=2Host: <servername>
```

Disconnect video source 2 from any port.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/serial.cgi?port=-1&camera=2"
```

```bash
GET /axis-cgi/com/serial.cgi?port=-1&camera=2Host: <servername>
```

## Parameters
### Port manager

**PortManager.P#**

The parameter group `PortManager.P#` describes a port manager. The indices `#` in `PortManager.P#` go from `0` to (number of port managers `- 1`).

PortManager.P#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `PortEnabled` | `yes` | `yes` `no` | admin: read, write operator: read | Enable or disable the output port. The output port is defined by the parameter `PortType`. `yes` = Enable the output port. no = Disable the output port. |
| `PortType` | Product dependent. | `Serial` `RemotePort` | admin: read, write operator: read | Describes what type of local port this port manager manages.`Serial` = The device connects directly via a serial port. `RemotePort` = The port data is forwarded to a physical serial port on another CPU. |

### Serial ports

**Serial**

The parameter `Serial` controls the functionality/purpose of the serial ports and some configuration that is shared by various applications.

Serial

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `NbrOfPorts` | Product dependent. | An unsigned integer. | admin: read operator: read viewer: read | The number of physical serial ports on the product. |

**Serial.Ser#**

The sub-group `Serial.Ser#` contains settings for a serial port. The index `#` in `Serial.Ser#` starts from `1`.

Serial.Ser#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `PortMode` | Product dependent. | `RS232` `RS485` `RS485_4` `RS422` _Product-dependent. Check the product specification._ | admin: read, write operator: read | Serial port protocol. May be read-only depending on hardware. |
| `BaudRate` | Product dependent. | `300` `600` `1200` `2400` `4800` `9600` `19200` `38400` `57600` `115200` `230400` _This value is only applicable to_ `RS485` _and_ `RS485_4`. `460800` _This value is only applicable to_ `RS485` _and_ `RS485_4`. | admin: read, write operator: read | The baud rate (transmission speed) used in the serial communication. The listed values are transmission speed in bites/second. |
| `DataBits` | Product dependent. | `7` `8` | admin: read, write operator: read | The number of data bits included in a set of bits. |
| `StopBits` | Product dependent. | `1` `2` | admin: read, write operator: read | The number of stop bits included in a set of bits. |
| `Parity` | Product dependent. | `None` `Even` `Odd` `Mark` `Space` | admin: read, write operator: read | The parity. A parity bit is added to make sure that the number of bits with the value one in a set of bits is even or odd.`None` = No parity bits are added. `Even` = The parity bit is set to 1 if the number of ones in a given set of bits (not including the parity bit) is odd. `Odd` = The parity bit is set to 1 if the number of ones in a given set of bits (not including the parity bit) is even. `Mark` = The parity bit is always 1. `Space` = The parity bit is always 0. |
| `FlowControlXONXOFF` | Product dependent. | `yes` `no` | admin: read, write operator: read | Enable and disable XON/XOFF flow control (requires a full duplex port). _If this parameter is missing then this function is not supported._ `yes` = Enable XON/XOFF flow control. `no` = Disable XON/XOFF flow control. |
| `FlowControlRTSCTS` | Product dependent. | `yes` `no` | admin: read, write operator: read | Enable and disable RTS/CTS flow control is enabled (requires a RS232 port). _If this parameter is missing then this function is not supported._ `yes` = Enable RTS/CTS flow control `no` = Disable RTS/CTS flow control. |
| `Termination` | Product dependent. | `yes` `no` | admin: read, write operator: read | Enable and disable `RS485`/`RS422` termination. (If this parameter is missing then this function is not supported.)`yes` = Enable `RS485`/`RS422` termination. `no` = Disable `RS485`/`RS422` termination. |
| `Bias` | Product dependent. | `yes` `no` | admin: read, write operator: read | Enable and disable `RS485`/`RS422` bias. _If this parameter is missing then this function is not supported._ `yes` = Enable `RS485`/`RS422` bias. `no` = Disable `RS485`/`RS422` bias. |

info

The # in Serial.Ser# is replaced with a number starting from 1.

**PortManager.P#.SerialCGI**

The `Enabled` parameter in this sub-group is used to enable or disable the internal server that `/axis-cgi/com/serial.cgi` uses for connecting to the port manager.

PortManager.P#.SerialCGI

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable the server that `/axis-cgi/com/serial.cgi` needs.`yes` = Enable the server that `/axis-cgi/com/` needs. `no` = Disable the server that `/axis-cgi/com/serial.cgi` needs. |

### Remote ports

Remote ports can be used to daisy chain and forward data from a remote port on one CPU to a physical port on another CPU. This is used in video encoder blades to share the serial port between the CPU:s. This functionality is only intended for multi CPU video encoders. Daisy chain is similar to Generic TCP/IP, but in addition to Generic TCP/IP it also adds a protocol header to the data payload.

**RemotePort.R#**

The parameter group `RemotePort.R#` contains settings for a remote port client. The index `#` in `RemotePort.R#` starts from `0`. Remote port server settings can be found in the parameter group `PortManager.P#.RemotePortServer`.

info

If the Axis product does not support the functionality this parameter group does not exist.

RemotePort.R#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `AutoConf` | `yes` | `yes` `no` | admin: read, write operator: read | Automatically determine the address and port of the remote port server using Bonjour®.`yes` = The client will try to determine the address and port of the remote port server automatically. `no` = The client will not try to determine the address and port of the remote port server automatically. |
| `AuthenticationKey` |  | A string. | admin: read, write operator: read | The key to use for authentication when connecting to a remote port server. The authentication key for the remote port server can be found in the parameter `PortManager.P#.RemotePortServer.AuthenticationKey`. |
| `Host` |  | Host name or IP address. | admin: read, write operator: read | Host name or IP address of the remote port server. Ignored if `AutoConf=yes`. |
| `Port` | `5555` | `1024` ... `65535` | admin: read, write operator: read | Listen port of the remote port server. Ignored if `AutoConf=yes`. |

**PortManager.P#.RemotePortServer**

The sub-group `RemotePortServer` contains parameters for remote port server, used for tunneling PTZ commands, generic TCP, and `/axis-cgi/com/serial.cgi` traffic.

info

If the Axis product does not support the functionality this parameter group does not exist.

PortManager.P#.RemotePortServer

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable the remote port server.`yes` = Enable the remote port server. `no` = Disable the remote port server. |
| `AllowedIPAddresses` |  | A comma separated list of IP addresses. | admin: read, write operator: read | Allow only certain IP addresses to connect to the Listener. The default value is an empty string. That means all IP addresses are allowed.Ranges may be specified. For example `1.2.3.4, 2.3.4.5-9, 3.4.5.*` |
| `Timeout` | `0` | `0 ... 3600` | admin: read, write operator: read | If there is no activity on the connection for this time (in seconds), it will be closed.`0` = No timeout/wait forever. |
| `AuthenticationKey` |  | A string. | admin: read, write operator: read | The key for the remote port clients to use when connecting to this remote port server. |

**PortManager.P#.RemotePortServer.Listener**

The sub-group `RemotePortServer.Listener` contains settings for listening for connections from remote port clients.

info

If the Axis product does not support the functionality this parameter group does not exist.

PortManager.P#.RemotePortServer.Listener

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable to accept connections to this remote port server.`yes` = Enable connections to this remote port server. `no` = Disable connections to this remote port server. |
| `Port` | `1024 + #`([1](#user-content-fn-1)) | `1024` ... `65535` | admin: read, write operator: read | The port to listen on for connections from remote port clients. |

**PortManager.P#.PTZServer**

The `Enabled` parameter in this sub-group is used to enable or disable the internal server that PTZ drivers use for connecting to the port manager.

PortManager.P#.PTZServer

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Used to enable or disable the server that PTZ drivers need.`yes` = Enable the server that PTZ driver need. `no` = Disable the server that PTZ drivers need. |

#### RemotePort.R#

The parameter group `RemotePort.R#` contains settings for a remote port client. The index `#` in `RemotePort.R#` starts from `0`. Remote port server settings can be found in the parameter group `PortManager.P#.RemotePortServer`.

info

If the Axis product does not support the functionality this parameter group does not exist.

RemotePort.R#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `AutoConf` | `yes` | `yes` `no` | admin: read, write operator: read | Automatically determine the address and port of the remote port server using Bonjour®.`yes` = The client will try to determine the address and port of the remote port server automatically. `no` = The client will not try to determine the address and port of the remote port server automatically. |
| `AuthenticationKey` |  | A string. | admin: read, write operator: read | The key to use for authentication when connecting to a remote port server. The authentication key for the remote port server can be found in the parameter `PortManager.P#.RemotePortServer.AuthenticationKey`. |
| `Host` |  | Host name or IP address. | admin: read, write operator: read | Host name or IP address of the remote port server. Ignored if `AutoConf=yes`. |
| `Port` | `5555` | `1024` ... `65535` | admin: read, write operator: read | Listen port of the remote port server. Ignored if `AutoConf=yes`. |

#### PortManager.P#.RemotePortServer

The sub-group `RemotePortServer` contains parameters for remote port server, used for tunneling PTZ commands, generic TCP, and `/axis-cgi/com/serial.cgi` traffic.

info

If the Axis product does not support the functionality this parameter group does not exist.

PortManager.P#.RemotePortServer

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable the remote port server.`yes` = Enable the remote port server. `no` = Disable the remote port server. |
| `AllowedIPAddresses` |  | A comma separated list of IP addresses. | admin: read, write operator: read | Allow only certain IP addresses to connect to the Listener. The default value is an empty string. That means all IP addresses are allowed.Ranges may be specified. For example `1.2.3.4, 2.3.4.5-9, 3.4.5.*` |
| `Timeout` | `0` | `0 ... 3600` | admin: read, write operator: read | If there is no activity on the connection for this time (in seconds), it will be closed.`0` = No timeout/wait forever. |
| `AuthenticationKey` |  | A string. | admin: read, write operator: read | The key for the remote port clients to use when connecting to this remote port server. |

#### PortManager.P#.RemotePortServer.Listener

The sub-group `RemotePortServer.Listener` contains settings for listening for connections from remote port clients.

info

If the Axis product does not support the functionality this parameter group does not exist.

PortManager.P#.RemotePortServer.Listener

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable to accept connections to this remote port server.`yes` = Enable connections to this remote port server. `no` = Disable connections to this remote port server. |
| `Port` | `1024 + #` `#` is the indices in `PortManager.P#`. | `1024` ... `65535` | admin: read, write operator: read | The port to listen on for connections from remote port clients. |

#### PortManager.P#.PTZServer

The `Enabled` parameter in this sub-group is used to enable or disable the internal server that PTZ drivers use for connecting to the port manager.

PortManager.P#.PTZServer

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Used to enable or disable the server that PTZ drivers need.`yes` = Enable the server that PTZ driver need. `no` = Disable the server that PTZ drivers need. |

### Generic TCP

**PortManager.P#.GenericTCPServer**

The sub-group `GenericTCPServer` contains settings for the generic TCP server. Generic TCP means that the server listens on a TCP port, and when a client connects a socket is opened. Data received over the socket is sent out on the serial/remote port, and data received on the port is sent out over the socket.

PortManager.P#.GenericTCPServer

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable the generic TCP server.`yes` = Enable the generic TCP server. `no` = Disable the generic TCP server. |
| `AllowedIPAddresses` |  | A comma separated list of IP addresses. | admin: read, write operator: read | Allow certain IP addresses to connect to the Listener. The default value is an empty string. That means all IP addresses are allowed.Ranges may be specified. For example `1.2.3.4, 2.3.4.5-9, 3.4.5.*` |
| `Timeout` | `0` | `0 ... 3600` | admin: read, write operator: read | If there is no activity on the connection for this time (in seconds), it will be closed.`0` = no timeout/wait forever. |

**PortManager.P#.GenericTCPServer.ConnectTo**

The sub-group `GenericTCPServer.ConnectTo` contains settings used when the port manager acts as a client and connects to another host. A host could for example be another encoder or server. When data is received the host connects to the client via generic TCP. The connection is similar to a remote port connection (see [Remote ports](#remote-ports)) but only raw data is sent directly, without a protocol.

PortManager.P#.GenericTCPServer.ConnectTo

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable the port manager to act as a client and connect to another host. (It may still act as a server as well with `Listener.Enabled=yes`.)`yes` = Enable port manager to act as a client. `no` = Disable port manager to act as a client. |
| `Host` |  | Host name or IP address | admin: read, write operator: read | Set the host name or IP address to use if this port manager should act as a client and connect to another host. |
| `Port` | `1024 + #` `#` is the indices in `PortManager.P#`. | `1024 ... 65535` | admin: read, write operator: read | Set the TCP port number to use if this port manager should act as a client and connect to another host. |

**PortManager.P#.GenericTCPServer.Listener**

This sub-group contains settings for the server functionality of the generic TCP server.

PortManager.P#.GenericTCPServer.Listener

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable or disable connections to this TCP server. `yes` = Enable connections to this TCP server. `no` = Disable connections to this TCP server. |
| `Port` | `1024 + #` `#` is the indices in `PortManager.P#`. | `1024` ... `65535` | admin: read, write operator: read | The TCP port to listen on, if enabled. |

## Serial port control

The CGI `/axis-cgi/com/serial.cgi` enables the Axis product to write and read raw data on the serial port through a HTTP request.

-   **Security level**: Viewer
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/com/serial.cgi?<argument>=<value>\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/com/serial.cgi?<argument>=<value>\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `camera=<int>` | `1 ...` | Select the video channel. If omitted, the default video source is used. |
| `write=<string>` | `<bytestring>` | Write the specified data string to the selected port.`<bytestring>` = Hexadecimal coded bytes with values {`0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `A`, `B`, `C`, `D`, `E`, `F`, `a`, `b`, `c`, `d`, `e`, `f`}. |
| `writestring`\=`<string>` | A percent-encoded string | Write the percent-encoded string to the selected port. |
| `read`\=`<int>` | `1` ... | Reads `n` bytes from the selected port. The returned data will be hexadecimal coded and placed between `#`s (for example `#3A#`). |
| `wait` = `<int>` | `1 - 9` | Specified in seconds. Used together with the `read` argument. A `read` is terminated when the specified number of bytes is `read` or the `wait` period has ended. |
| `timeout` = `<int>` | `0` ... `9000` | Specified in milliseconds. Used together with the `read` argument. A `read` is terminated when the specified number of bytes is `read` or the `timeout` has expired. |

## Footnotes

1.  `#` is the indices in `PortManager.P#`. [↩](#user-content-fnref-1)