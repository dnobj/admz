---
title: External IP Device Information
url: "https://developer.axis.com/vapix/network-video/external-ip-device-information/"
category: vapix
subcategory: network-video
sha256: c6a4a5e239d40ce2cbd028869cac8f55f34e83f7142a339ddd417c7571792627
scraped_at: "2026-01-09T15:19:45.379Z"
page_height: 35662
---

# External IP Device Information

## Description

The External IP Device Information API features the steps that makes it possible to store information that can then be used to access an external IP device, which in the context of this API is a unit capable of generating data streams, such as a network camera. Stored information can be used to set up communications with the IP device, which is useful when an Axis Network Video Recorder is pulling videos from multiple camera sources.

### Model

The API implements `externalipdeviceinfo` as its communications interface and supports the following CGI methods accessed using either `HTTP GET` or `HTTP POST`:

| Method | Description | Latest ver. |
| --- | --- | --- |
| `/axis-cgi/externalipdeviceinfo/create.cgi` | Creates an external IP device. | `2.1` |
| `/axis-cgi/externalipdeviceinfo/update.cgi` | Updates an external IP device. | `2.1` |
| `/axis-cgi/externalipdeviceinfo/delete.cgi` | Removes an external IP device. | `2.0` |
| `/axis-cgi/externalipdeviceinfo/list.cgi` | Lists created external IP devices. | `2.1` |
| `/axis-cgi/externalipdeviceinfo/geteventsenabled.cgi` | Retrieves the enable status for events on external IP devices. | `2.0` |
| `/axis-cgi/externalipdeviceinfo/seteventsenabled.cgi` | Enables or disables events on external IP devices. | `2.0` |
| `/axis-cgi/externalipdeviceinfo/getcacertificates.cgi` | Retrieves CA certificates for validation. | `2.1` |
| `/axis-cgi/externalipdeviceinfo/setcacertificates.cgi` | Sets up CA certificates for validation. | `2.1` |
| `/axis-cgi/externalipdeviceinfo/schemaversions.cgi` | Retrieves XML schema versions supported by your product. | `2.0` |

### Identification

-   **API Discovery**: `id=ext-ip-dev-info`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Configure a network recorder for camera motion events

Use this example to configure a network recorder to pull a video when a motion event in the camera is triggered. Please note that the camera needs to support and have motion detection enabled.

1.  Create two external IP devices.
    
    Device 1
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/create.cgi?schemaversion=2&id=example-id\_123&address=192.168.0.123&username=device1&password=pass1&description="Exampleextipdev"&serialnumber=AABBCCDDEEFF1234"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/create.cgi?schemaversion=2&id=example-id\_123&address=192.168.0.123&username=device1&password=pass1&description="Exampleextipdev"&serialnumber=AABBCCDDEEFF1234Host: <servername>
    ```
    
    Device 2
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/create.cgi?schemaversion=2&id=example-id\_124&address=fe80::aecc:8eff:fee3:64fd&username=device2&password=pass2&description="Second example extipdev"&serialnumber=AABBCCDDEEFF5678"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/create.cgi?schemaversion=2&id=example-id\_124&address=fe80::aecc:8eff:fee3:64fd&username=device2&password=pass2&description="Second example extipdev"&serialnumber=AABBCCDDEEFF5678Host: <servername>
    ```
    
2.  Parse the XML response, which will result in either the successful creation of an external IP device or an error. In this example, the error appeared because the id parameter was not supplied.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>40</ErrorCode>        <Description>Invalid or no id</Description>    </GeneralError></DeviceResponse>
    ```
    
3.  List external IP devices to verify that your devices were created with the correct parameters.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2Host: <servername>
    ```
    
4.  Parse the response.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8"?><DeviceResponse SchemaVersion="2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <ListDevicesSuccess>        <Device>            <Id>example-id\_123</Id>            <Serialnumber>AABBCCDDEEFF1234</Serialnumber>            <Description>Example extipdev</Description>            <Address>192.168.0.123</Address>            <Username>device1</Username>            <Protocol>rtspt</Protocol>            <Port>0</Port>            <CertificateValidation>off</CertificateValidation>        </Device>        <Device>            <Id>example-id\_124</Id>            <Serialnumber>AABBCCDDEEFF5678</Serialnumber>            <Description>Second example extipdev</Description>            <Address>fe80::aecc:8eff:fee3:64fd</Address>            <Username>device2</Username>            <Protocol>rtspt</Protocol>            <Port>0</Port>            <CertificateValidation>off</CertificateValidation>        </Device>        <Device>            ...        <Device/>    <ListDevicesSuccess></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>10</ErrorCode>        <Description>An error occurred at system level</Description>    </GeneralError></DeviceResponse>
    ```
    
5.  Enable events for the external IP device `example-id_123`. At this stage the stored ID credentials will be used to connect to the camera and retrieve the events.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/seteventsenabled.cgi?schemaversion=2&id=example-id\_123&enabled=yes"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/seteventsenabled.cgi?schemaversion=2&id=example-id\_123&enabled=yesHost: <servername>
    ```
    
6.  Parse the XML response.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>40</ErrorCode>        <Description>Invalid or no id</Description>    </GeneralError></DeviceResponse>
    ```
    
7.  Check if the events were enabled.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/geteventsenabled.cgi?schemaversion=2&id=example-id\_123"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/geteventsenabled.cgi?schemaversion=2&id=example-id\_123Host: <servername>
    ```
    
8.  Parse the XML response.
    
    Successful response example
    
    ```bash
    <DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GetEventsEnabledSuccess>        <Id>example-id\_123</Id>        <EventsEnabled>YES</EventsEnabled>    </GetEventsEnabledSuccess></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>40</ErrorCode>        <Description>Invalid or no id</Description>    </GeneralError></DeviceResponse>
    ```
    

### Enable certificate validation for a network recorder on a pre-existing motion event recording

Use this example to change a network recorder configuration and pull a video from an encrypted link using certificate validation.

1.  Configure two CA certificates for validation. The validation will succeed if the signature is verified by at least one of the certificates. The following example shows separate CA certificates used on different cameras.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/setcacertificates.cgi?schemaversion=2&certids=caid1,caid2"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/setcacertificates.cgi?schemaversion=2&certids=caid1,caid2Host: <servername>
    ```
    
2.  Parse the XML response
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
    ```
    
3.  List external IP devices to find out how each network camera is configured. This example contains two cameras that we want to change.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2Host: <servername>
    ```
    
4.  Parse the XML response.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8"?><DeviceResponse SchemaVersion="2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <ListDevicesSuccess>        <Device>            <Id>example-id\_123</Id>            <Serialnumber>AABBCCDDEEFF1234</Serialnumber>            <Description>Example extipdev</Description>            <Address>192.168.0.123</Address>            <Username>device1</Username>            <Protocol>rtspt</Protocol>            <Port>0</Port>            <CertificateValidation>off</CertificateValidation>        </Device>        <Device>            <Id>example-id\_124</Id>            <Serialnumber>AABBCCDDEEFF5678</Serialnumber>            <Description>Second example extipdev</Description>            <Address>fe80::aecc:8eff:fee3:64fd</Address>            <Username>device2</Username>            <Protocol>rtspt</Protocol>            <Port>0</Port>            <CertificateValidation>off</CertificateValidation>        </Device>        <Device>            ...        <Device/>    </ListDevicesSuccess></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>10</ErrorCode>        <Description>An error occurred at system level</Description>    </GeneralError></DeviceResponse>
    ```
    
5.  Update the two devices to use https and certificate validation.
    
    Device 1
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/update.cgi?schemaversion=2&id=example-id\_123&address=192.168.0.123&username=device1&password=pass1&protocol=rtspsh&certvalidation=standard"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/update.cgi?schemaversion=2&id=example-id\_123&address=192.168.0.123&username=device1&password=pass1&protocol=rtspsh&certvalidation=standardHost: <servername>
    ```
    
    Device 2
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/update.cgi?schemaversion=2&id=example-id\_124&address=fe80::aecc:8eff:fee3:64fd&username=device2&password=pass2&protocol=rtspsh&port=443&certvalidation=standard"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/update.cgi?schemaversion=2&id=example-id\_124&address=fe80::aecc:8eff:fee3:64fd&username=device2&password=pass2&protocol=rtspsh&port=443&certvalidation=standardHost: <servername>
    ```
    
6.  Parse the XML response. A successful response means that the external IP device was successfully updated.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
    ```
    
    In this example, we show a couple of potential errors. The first one will occur if the protocol is not supported, while the second one will happen if the port number is outside the range of 0 to 65535, and the third one will occur if the `certvalidation` parameter is set to something other than off/standard/limited.
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>190</ErrorCode>        <Description>Invalid protocol</Description>    </GeneralError></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>200</ErrorCode>        <Description>Invalid port</Description>    </GeneralError></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>210</ErrorCode>        <Description>Invalid certificate validation</Description>    </GeneralError></DeviceResponse>
    ```
    
7.  List the external IP devices to see the changed configuration.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2"
    ```
    
    ```bash
    GET /axis-cgi/externalipdeviceinfo/list.cgi?schemaversion=2Host: <servername>
    ```
    
8.  Parse the XML response.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8"?><DeviceResponse SchemaVersion="2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <ListDevicesSuccess>        <Device>            <Id>example-id\_123</Id>            <Serialnumber>AABBCCDDEEFF1234</Serialnumber>            <Description>Example extipdev</Description>            <Address>192.168.0.123</Address>            <Username>device1</Username>            <Protocol>rtspsh</Protocol>            <Port>0</Port>            <CertificateValidation>standard</CertificateValidation>        </Device>        <Device>            <Id>example-id\_124</Id>            <Serialnumber>AABBCCDDEEFF5678</Serialnumber>            <Description>Second example extipdev</Description>            <Address>fe80::aecc:8eff:fee3:64fd</Address>            <Username>device2</Username>            <Protocol>rtspsh</Protocol>            <Port>443</Port>            <CertificateValidation>standard</CertificateValidation>        </Device>        <Device>            \[...\]        <Device/>    </ListDevicesSuccess></DeviceResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>10</ErrorCode>        <Description>An error occurred at system level</Description>    </GeneralError></DeviceResponse>
    ```
    

## API specifications
### `/axis-cgi/externalipdeviceinfo/create.cgi`

This method is used when you want to create an external IP device.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/create.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/create.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `id=<EXTIPDEVID>` | The unique external IP device identifier. |
| `description=<DESCRIPTION>` | The external IP device description (optional). |
| `serialnumber=<SERIALNUMBER>` | The external IP device serial number. Can be either MAC-addresses or alpha numeric strings (optional). |
| `address=<ADDRESS>` | The external IP device address or hostname (optional). Both username and password are required when an address is set. |
| `username=<USERNAME>` | The IP device account name. This parameter is mandatory when address is set. |
| `password=<PASSWORD>` | The password connected to a username. This parameters is mandatory when address is set. |
| `protocol=<PROTOCOL>` | The protocol used to retrieve an event stream (optional). In cases where default port mode is used (port given as 0) specifying the protocol will also indirectly set the actual port number. Default port numbers are listed under the port description below. Supported protocols are:  
\- rtspt: RTP over RTSP (default)  
\- `rtsph`: RTP over RTSP over HTTP  
\- `rtspsh`: RTP over RTSP over HTTPS (supports certificate validation) |
| `certvalidation="standard" | "limited" | "off"` | Optional parameter. The following protocols are supported:  
\- `standard`: Enables certificate validation. Please make sure that the protocol supports validation, as the connection will not be permitted otherwise. The signature in the remote device response will be validated along with the installed CA certificates. A connection will not be established unless the response signature matches one of the installed certificates.  
\- `limited`: Enables certificate validation when Common Name is disabled. You need to make sure that the protocol supports validation, otherwise the connection will not be permitted. The signature in the remote device response will be validated along with the installed certificates. A connection will not be established unless the response signature matches one of the installed certificates.  
\- `off`: Disables certificate validation. This is the default value. |
| `port=<PORT>` | The port used to fetch the event stream (optional). Default value is 0, which means that the stream is using the standard port of the specified protocol.  
**Port defaults**  
  
\- `rtspt`: 554  
\- `rtsph`: 80  
\- `rtspsh`: 443 |

info

Please note that setting the username and password presumes that an account with those credentials has already been created for the external IP device.

info

External IP devices can be created using only the ID parameter.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `30` | Maximum amount of devices reached. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `70` | Invalid request. |
| `80` | Processing error. |
| `150` | Device already exists. |
| `170` | Invalid description. |
| `180` | Invalid serialnumber. |
| `190` | Invalid protocol. |
| `200` | Invalid port. |
| `210` | Invalid certificate validation. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/update.cgi`

This method is used when you want to change parameter values on existing IP devices. Please note that the changes won’t take effect until the recording is manually restarted.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/update.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/update.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `id=<EXTIPDEVID>` | The unique external IP device identifier. |
| `description=<DESCRIPTION>` | The external IP device description (optional). |
| `serialnumber=<SERIALNUMBER>` | The external IP device serial number. Can be either MAC-addresses or alpha numeric strings (optional). |
| `address=<ADDRESS>` | The external IP device address or hostname (optional). Both username and password are required when an address is set. |
| `username=<USERNAME>` | The IP device account name. This parameter is mandatory when address is set. |
| `password=<PASSWORD>` | The password connected to a username. This parameters is mandatory when address is set. |
| `protocol=<PROTOCOL>` | The protocol used to retrieve an event stream (optional). The protocol used to retrieve an event stream (optional). In cases where default port mode is used (port given as 0) specifying the protocol will also indirectly set the actual port number. Default port numbers are listed under the port description below. Supported protocols are:  
\- rtspt: RTP over RTSP (default)  
\- `rtsph`: RTP over RTSP over HTTP  
\- `rtspsh`: RTP over RTSP over HTTPS (supports certificate validation) |
| `certvalidation="standard" | "limited" | "off"` | Optional parameter. The following protocols are supported:  
\- `standard`: Enables certificate validation. Please make sure that the protocol supports validation, as the connection will not be permitted otherwise. The signature in the remote device response will be validated along with the installed CA certificates. A connection will not be established unless the response signature matches one of the installed certificates.  
\- `limited`: Enables certificate validation when Common Name is disabled. You need to make sure that the protocol supports validation, otherwise the connection will not be permitted. The signature in the remote device response will be validated along with the installed certificates. A connection will not be established unless the response signature matches one of the installed certificates.  
\- `off`: Disables certificate validation. This is the default value. |
| `port=<PORT>` | The port used to fetch the event stream (optional). Default value is 0, which means that the stream is using the standard port of the specified protocol.  
**Port defaults**  
  
\- `rtspt`: 554  
\- `rtsph`: 80  
\- `rtspsh`: 443 |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |
| `90` | No device. |
| `170` | Invalid description. |
| `180` | Invalid serialnumber. |
| `190` | Invalid protocol. |
| `200` | Invalid port. |
| `210` | Invalid certificate validation. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/delete.cgi`

This method is used when you want to delete an external IP device.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/delete.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/delete.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `id=<EXTIPDEVID>` | The unique external IP device identifier. |

info

Use `/axis-cgi/externalipdeviceinfo/update.cgi` to delete individual parameters from an existing device.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |
| `90` | No device. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/list.cgi`

This method is used when you want to list all available external IP devices.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/list.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/list.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Successful response example

```bash
<?xml version="1.0" encoding="UTF-8"?><DeviceResponse SchemaVersion="2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd"><ListDevicesSuccess>  <Device>    <Id>example-id\_123</Id>    <Serialnumber>AABBCCDDEEFF1234</Serialnumber>    <Description>Example extipdev</Description>    <Address>192.168.0.123</Address>    <Username>device1</Username>    <Protocol>rtspt</Protocol>    <Port>0</Port>    <CertificateValidation>off</CertificateValidation>  </Device>  <Device>    <Id>example-id\_124</Id>    <Serialnumber>AABBCCDDEEFF5678</Serialnumber>    <Description>Second example extipdev</Description>    <Address>fe80::aecc:8eff:fee3:64fd</Address>    <Username>device2</Username>    <Protocol>rtspt</Protocol>    <Port>0</Port>    <CertificateValidation>off</CertificateValidation>  </Device>  <Device>    ...  <Device/></ListDevicesSuccess></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/seteventsenabled.cgi`

This method is used when you want to enable or disable events from an external IP device. Supported events are VMD2, VMD3, VMD4 and VMDLite.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/seteventsenabled.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/seteventsenabled.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `id=<EXTIPDEVID>` | The unique external IP device identifier. |
| `enabled="YES" | "yes" | "enabled" | "NO" | "no" | "disabled"` | `"YES" | "yes" | "enabled"`: Enables events found on the external IP device. `"NO" | "no" | "disabled"`: Disables events found on the external IP device. |

info

Please note that events may not be supported depending on AXIS OS version or device type.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `70` | Invalid request. |
| `80` | Processing error. |
| `90` | No device. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/geteventsenabled.cgi`

This method is used when you want to retrieve an enabled event state from an external IP device.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/geteventsenabled.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/geteventsenabled.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `id=<EXTIPDEVID>` | The unique external IP device identifier. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GetEventsEnabledSuccess>        <Id>\[id\]</Id>        <EventsEnabled>\[YES/NO\]</EventsEnabled>    </GetEventsEnabledSuccess></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |
| `90` | No device. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/setcacertificates.cgi`

This method is used when you want to set up a list of installed CA certificates to validate streams from external IP devices that has certificate validation enabled. Using the `certvalidation` parameter found in [`/axis-cgi/externalipdeviceinfo/create.cgi`](#axis-cgiexternalipdeviceinfocreatecgi) and [`/axis-cgi/externalipdeviceinfo/update.cgi`](#axis-cgiexternalipdeviceinfoupdatecgi) will specify if the certificate validation should be used for a particular external IP device (default value is off). The list of CA certificate IDs passed to this function will replace the current list of IDs, while calling this function with no input, i.e. an empty list, will unset all currently configured CA certificate IDs.

-   The CA certificate must be installed prior to calling this method. See [Certificate management API](/vapix/network-video/certificate-management-api/) for additional information on how to upload CA certificates.
-   A CA certificate must be unset with this method before it can be uninstalled.
-   [`/axis-cgi/externalipdeviceinfo/getcacertificates.cgi`](#axis-cgiexternalipdeviceinfogetcacertificatescgi) can be used to list already configured CA certificate IDs that would be overridden by this method.
-   External IP devices with both events and certificate validation enabled when calling this method will have their event streams reset to ensure that the event stream use the correct CA. Using an installed CA certificate while the same CA certificate ID is missing from the `certids` parameter will cause a disruption in the event stream.
-   Changes made to ongoing recordings will take effect the next time the recording is manually restarted. This API is able to restart the event streams for External IP devices, but not recordings. Any ongoing recording will continue, but they will not use the new list of CA certificates before being restarted.
-   It is possible to set multiple CA certificates in the same API call.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/setcacertificates.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/setcacertificates.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML schema version that should be used. |
| `certids=<CERTID>[,<CERTID>[,...]]` | Defines the CA id (optional). All current CAs will be turned off if this parameter is left undefined. Multiple CA ids can be set at once as a comma separated list. Please note that using this method will replace any pre-existing list of CA certificates. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralSuccess /></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |
| `220` | Invalid CA certificate. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/getcacertificates.cgi`

This method is used when you want to retrieve a list of one or multiple configured CA certificates using a single API call.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/getcacertificates.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/externalipdeviceinfo/getcacertificates.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML schema version that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="UTF-8"?><DeviceResponse SchemaVersion="2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GetCACertificatesSuccess>        <CACertificate>            <Id>Ca-id\_1</Id>        </CACertificate>        <CACertificate>            <Id>Ca-id\_2</Id>        </CACertificate>        <CACertificate>            \[...\]        <CACertificate/>    </GetCACertificatesSuccess></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

**Error codes**

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `60` | Unsupported schema version. |
| `80` | Processing error. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/externalipdeviceinfo/schemaversions.cgi`

This method is used when you want to retrieve a list of supported XML schema versions.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`, `POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/externalipdeviceinfo/schemaversions.cgi"
```

```bash
GET /axis-cgi/externalipdeviceinfo/schemaversions.cgiHost: <servername>
```

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major\].\[minor\]</VersionNumber>        </SchemaVersion>    </SchemaVersionsSuccess></DeviceResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<DeviceResponse    SchemaVersion="2.1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/ExternalIpDeviceInfo2.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></DeviceResponse>
```

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

The following table contains all errors that can occur for any CGI method. For method specific errors, see the API description for that particular method.

| Error code | Description |
| --- | --- |
| `10` | An error occurred at system level. |
| `30` | Maximum amount of devices reached. |
| `40` | Invalid or no id. |
| `60` | Unsupported schema version. |
| `70` | Invalid request. |
| `80` | Processing error. |
| `90` | No device. |
| `150` | Device already exists. |
| `170` | Invalid description. |
| `180` | Invalid serialnumber. |
| `190` | Invalid protocol. |
| `200` | Invalid port. |
| `210` | Invalid certificate validation. |
| `220` | Invalid CA certificate. |