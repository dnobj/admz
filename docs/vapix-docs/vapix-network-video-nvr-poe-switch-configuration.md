---
title: NVR PoE switch configuration
url: "https://developer.axis.com/vapix/network-video/nvr-poe-switch-configuration/"
category: vapix
subcategory: network-video
sha256: f0e3d9702f6cdc267db15a02ed10b602cc461281d1c5f90567f1f714c77537e7
scraped_at: "2026-01-09T15:20:22.559Z"
page_height: 24529
---

# NVR PoE switch configuration

## Description

The Network Video Recorder Power over Ethernet (NVR PoE) switch configuration API provides the information that will help you interact with the individual PoE ports on a network video recorder. With it, you will be able to request power from a PoE switch to supply a connected device, such as a camera.

### Terminology

| Term | Description |
| --- | --- |
| PD | Powered Device, e.g. a camera or some other power consuming device. |
| PSE | Power Sourcing Equipment, e.g. a PoE switch or some other power sourcing equipment. |
| LLDPDU | Link Layer Discovery Protocol Data Unit. A protocol used by network devices. |

### Model

The API is based on the PoE PSE functionality of the Recorder that will help you check the status of and control connected PoE devices, such as PoE cameras. The main feature of the API, however, is to present the status information of connected PoE devices, manage the port PoE power and notify the user about PoE errors.

### Identification

-   **API Discovery**: `id=nvr-poe`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Retrieve supported versions

This example will show you how to retrieve a listing of API versions supported by your device.

1.  Retrieve a list containing all supported API versions.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/schemaversions.cgi"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/schemaversions.cgiHost: <servername>
    ```
    
2.  Parse the XML response.
    
    Successful response example
    
    ```bash
    <?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major1\].\[minor1\]</VersionNumber>            <Deprecated>\[deprecated1\]</Deprecated>        </SchemaVersion>        ...        <SchemaVersion>            <VersionNumber>\[majorN\].\[minorN\]</VersionNumber>            <Deprecated>\[deprecatedN\]</Deprecated>        </SchemaVersion>    </SchemaVersionsSuccess></PoeResponse>
    ```
    
    Error response example
    
    ```bash
    <?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
    ```
    

### Create a port power cycle

This example will show you how to create a complete power cycle for a PoE connected camera.

1.  Check the port mode to see if the port is enabled.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getportmode.cgi?schemaversion=1&port=2"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/getportmode.cgi?schemaversion=1&port=2Host: <servername>
    ```
    
2.  Parse the XML response.
    
    ```bash
    ...<GetPortModeSuccess>    <Enabled>yes</Enabled></GetPortModeSuccess>...
    ```
    
3.  Disable the port mode to turn off the port.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/setportmode.cgi?schemaversion=1&port=2&enabled=no"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/setportmode.cgi?schemaversion=1&port=2&enabled=noHost: <servername>
    ```
    
4.  Parse the XML response.
    
    Successful response example
    
    ```bash
    ...    <GeneralSuccess/>...
    ```
    
5.  Enable the port mode to turn the port back on again.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/setportmode.cgi?schemaversion=1&port=2&enabled=yes"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/setportmode.cgi?schemaversion=1&port=2&enabled=yesHost: <servername>
    ```
    
6.  Parse the XML response.
    
    ```bash
    ...    <GeneralSuccess/>...
    ```
    

### Retrieve PoE port status

This example will show you how to retrieve the status information for all available PoE ports and check which ones are connected, disabled or has encountered an error.

1.  Retrieve status information.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getportstatuses.cgi?schemaversion=1"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/getportstatuses.cgi?schemaversion=1Host: <servername>
    ```
    
2.  Parse the XML response.
    
    ```bash
    ...<GetPortStatusesSuccess>    <PortStatus>        <Port>1</Port>        <StatusCode>1</StatusCode>        <Description>Connected - PoE</Description>        <Extra>0x01: 802.3af-compliant device detected</Extra>        <ClassPowerLimit>7.0</ClassPowerLimit>        <PoeClass>2</PoeClass>        <AllocatedPower>7.0</AllocatedPower>        <PowerConsumption>3.4</PowerConsumption>        <PseClassLimit>4</PseClassLimit>        <RequestedPower>6.1</RequestedPower>    </PortStatus>...</GetPortStatusesSuccess>...
    ```
    

### Enable keep power

This example will show you how to keep all PoE cameras powered up while performing a reboot of a recorder with ongoing recordings, reducing the video down time.

1.  Check if the keep power setting is enabled.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getkeeppower.cgi?schemaversion=1"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/getkeeppower.cgi?schemaversion=1Host: <servername>
    ```
    
2.  Parse the XML response.
    
    ```bash
    ...<GetKeepPowerSuccess>    <Enabled>no</Enabled></GetKeepPowerSuccess>...
    ```
    
3.  Enable the keep power setting to maintain power for the PoE devices while the recorder is rebooting.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/setkeeppower.cgi?schemaversion=1&enabled=yes"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/setkeeppower.cgi?schemaversion=1&enabled=yesHost: <servername>
    ```
    
4.  Parse the XML response.
    
    ```bash
    ...    <GeneralSuccess/>...
    ```
    

### Check power limit

This example will show you how to check the total power limit of the recorder and how much is being allocated to the connected cameras.

1.  Check the total power limit of the PSE.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/gettotalpowerlimit.cgi?schemaversion=1"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/gettotalpowerlimit.cgi?schemaversion=1Host: <servername>
    ```
    
2.  Parse the XML response.
    
    ```bash
    ...    <GetTotalPowerLimitSuccess>        <Limit>65</Limit>    </GetTotalPowerLimitSuccess>...
    ```
    
3.  Retrieve the port statuses to sum up the allocated power used by the ports.
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getportstatuses.cgi?schemaversion=1"
    ```
    
    ```bash
    GET /axis-cgi/nvr/poe/getportstatuses.cgi?schemaversion=1Host: <servername>
    ```
    
4.  Parse the XML response.
    
    ```bash
    ...<GetPortStatusesSuccess>    <PortStatus>        <Port>1</Port>        <StatusCode>1<StatusCode>        <Description>Connected - PoE</Description>        <Extra>0x01: 802.3af-compliant device detected</Extra>        <ClassPowerLimit>7.0</ClassPowerLimit>        <PoeClass>2</PoeClass>        <AllocatedPower>7.0</AllocatedPower>        <PowerConsumption>3.4</PowerConsumption>        <PseClassLimit>4</PseClassLimit>        <RequestedPower>6.1</RequestedPower>    </PortStatus>    <PortStatus>        <Port>2</Port>        <StatusCode>1<StatusCode>        <Description>Connected - PoE</Description>        <Extra>0x01: 802.3af-compliant device detected</Extra>        <ClassPowerLimit>7.0</ClassPowerLimit>        <PoeClass>3</PoeClass>        <AllocatedPower>13.0</AllocatedPower>        <PowerConsumption>5.4</PowerConsumption>        <PseClassLimit>4</PseClassLimit>        <RequestedPower>11.0</RequestedPower>    </PortStatus>...</GetPortStatusesSuccess>...
    ```
    
5.  This will allocate 20 W out of the available 65 W.
    

## API specifications
### `/axis-cgi/nvr/poe/schemaversions.cgi`

This method should be used when you want to retrieve a listing of all supported XML schema versions.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/schemaversions.cgi"
```

```bash
GET /axis-cgi/nvr/poe/schemaversions.cgiHost: <servername>
```

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8"?><PoeResponse SchemaVersion="1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">  <SchemaVersionSuccess>    <SchemaVersion>      <VersionNumber>\[major1\].\[minor1\]</VersionNumber>      <Deprecated>\[deprecated1\]<Deprecated>    </SchemaVersion>    \[...\]    <SchemaVersion>      <VersionNumber>\[majorN\].\[minorN\]</VersionNumber>      <Deprecated>\[deprecatedN\]<Deprecated>    </SchemaVersion>  </SchemaVersionSuccess></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<VersionNumber>` | Number | The supported XML-schema version. |
| `<Deprecated>` | Boolean | The deprecation status. Valid values are: `true` `false` (default value) |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/getportmode.cgi`

This method should be used when you want to check the status of the PoE port mode.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getportmode.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/getportmode.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |
| `port=<integer>` | The port number. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GetPortModeSuccess>        <Enabled>\[yes, no\]</Enabled>    </GetPortModeSuccess></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<Enabled>` | String | Shows if the specified port is enabled or disabled. `yes`: Enabled `no`: Disabled |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/setportmode.cgi`

This method should be used when you want to set the status for the PoE port mode.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/setportmode.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/setportmode.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |
| `port=<integer>` | The port number. |
| `enabled=yes | no` | Enables/disables the specified port. `yes`: Enable `no`: Disable |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralSuccess /></PoeResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/getportstatuses.cgi`

This method should be used when you want to check the status of all PoE ports.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getportstatuses.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/getportstatuses.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GetPortStatusesSuccess>        <PortStatus>            <Port>\[A port number\]</Port>            <StatusCode>\[A status code\]</StatusCode>            <Description>\[A string\]</Description>            <Extra>\[A string\]</Extra>            <ClassPowerLimit>\[A number\]</ClassPowerLimit>            <PoeClass>\[A number\]</PoeClass>            <AllocatedPower>\[A number\]</AllocatedPower>            <PowerConsumption>\[A number\]</PowerConsumption>            <PseClassLimit>\[A number\]</PseClassLimit>            <RequestedPower>\[A number\]</RequestedPower>        </PortStatus>        \[...\]        <PortStatus>            <Port>\[A port number\]</Port>            <StatusCode>\[A status code\]</StatusCode>            <Description>\[A string\]</Description>            <Extra>\[A string\]</Extra>            <ClassPowerLimit>\[A number\]</ClassPowerLimit>            <PoeClass>\[A number\]</PoeClass>            <AllocatedPower>\[A number\]</AllocatedPower>            <PowerConsumption>\[A number\]</PowerConsumption>            <PseClassLimit>\[A number\]</PseClassLimit>            <RequestedPower>\[A number\]</RequestedPower>        </PortStatus>    </GetPortStatusesSuccess></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<Port>` | Number | The port number. |
| `<StatusCode>` | Code | The numeric status code. |
| `<Description>` | String | A human-readable status description. |
| `<Extra>` | String | Container for additional status information. |
| `<ClassPowerLimit>` | Number | The maximum power delivered by the PSE for the detected PD class, measured in watts. |
| `<PoeClass>` | Number | The detected PoE class of the PD. Shows up as an empty element if no class is detected. |
| `<AllocatedPower>` | Number | The allocated power for the PoE, measured in watts. |
| `<PowerConsumption>` | Number | A snapshot of the power consumed by the PD. |
| `<PseClassLimit>` | Number | The maximum PoE class supported by the port. |
| `<RequestedPower>` | Number | The requested power by the PD, measured in watts. Shows up as an empty element if no LLDPDU was received from the PD. |

**StatusCode element**

| Code | Description |
| --- | --- |
| `0` | Not connected |
| `1` | Connected - PoE |
| `2` | Connected - No PoE |
| `3` | Disabled |
| `4` | Error: Power budget exceeded |
| `5` | Error: Other |

Please note that code `2` "Connected - No PoE" is only reported from PSEs that support detecting devices that do not require PoE.

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/gettotalpowerlimit.cgi`

This method should be used when you want to find out the total power limit of the PoE supply source, i.e. the limit of how much total power the PSE can supply.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/gettotalpowerlimit.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/gettotalpowerlimit.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GetTotalPowerLimitSuccess>        <Limit>\[A number\]</Limit>    </GetTotalPowerLimitSuccess></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<Limit>` | Number | The Total Power Limit, measured in watts. |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/getkeeppower.cgi`

This method should be used when you want to check the value of the keep power setting and specify whether the keep power function should be turned on or off. Please note that the call will return the error message `NotSupported` on devices where the CGI is not supported.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/getkeeppower.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/getkeeppower.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GetKeepPowerSuccess>        <Enabled>\[yes, no\]</Enabled>    </GetKeepPowerSuccess></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<Enabled>` | String | Shows if the keep power function is active. `yes`: Active `no`: Inactive |

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### `/axis-cgi/nvr/poe/setkeeppower.cgi`

This method should be used when you want to control whether the PoE power should be kept active when the recorder is rebooting. Please note that the call will return the error message `NotSupported` on devices where the CGI is not supported.

**Request**

-   **Security level**: Operator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/nvr/poe/setkeeppower.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/nvr/poe/setkeeppower.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `schemaversion=<integer>` | The major XML version that should be used along with it highest minor version. |
| `enabled=yes | no` | Enables/disables the keep power feature. `yes`: Power is kept when the recorder is rebooting `no`: Power is cut when the recorder is rebooting |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralSuccess /></PoeResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Response body syntax

```bash
<?xml version="1.0" encoding="utf-8" ?><PoeResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/nvr/Poe1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <Description>\[description\]</Description>    </GeneralError></PoeResponse>
```

| Parameter | Type | Description |
| --- | --- | --- |
| `<ErrorCode>` | Integer | An error code. |
| `<Description>` | String | A message detailing the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

| Code | Description |
| --- | --- |
| `10` | An error occurred while processing the request. |
| `20` | Invalid request. |
| `30` | Unauthorized request. |
| `40` | Specified version not supported. |
| `50` | Not supported. |

## Event API documentation

PoE errors are notified through a PoE event with the tag `format_modifier_user_string` to retrieve a user friendly explanation of potential errors with the PoE controller. The event itself is presented in the format returned from `GetEventInstances`, further described in [Event and action services](/vapix/network-video/event-and-action-services/), where the port value `-1` and the nicename `Any` can be used as an aggregated status for all ports.

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:HardwareFailure aev:NiceName="Hardware failure">        <PoEFailure wstop:topic="true" aev:NiceName="Power over ethernet failure">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance aev:NiceName="Port Identifier" Type="xsd:int" Name="port">                        <aev:Value>1</aev:Value>                        <aev:Value>2</aev:Value>                        <aev:Value>3</aev:Value>                        <aev:Value>4</aev:Value>                        <aev:Value>5</aev:Value>                        <aev:Value>6</aev:Value>                        <aev:Value>7</aev:Value>                        <aev:Value>8</aev:Value>                        <aev:Value aev:NiceName="Any">-1</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance aev:NiceName="Reason Code" Type="xsd:int" Name="reason" />                    <aev:SimpleItemInstance aev:NiceName="Reason Description" Type="xsd:string" Name="reasonstr" />                    <aev:SimpleItemInstance                        aev:NiceName="PoE provider Disruption"                        Type="xsd:boolean"                        Name="disruption"                        isPropertyState="true" />                </aev:DataInstance>            </aev:MessageInstance>        </PoEFailure>    </tnsaxis:HardwareFailure></tns1:Device>
```