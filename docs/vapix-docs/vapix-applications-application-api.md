---
title: Application API
url: "https://developer.axis.com/vapix/applications/application-api/"
category: vapix
subcategory: applications
sha256: 2675d7305f5832e86f83748282c1a385d1f11651dc11a0287969dda5988223c3
scraped_at: "2026-01-09T15:01:01.299Z"
page_height: 14208
---

# Application API

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Description

Use VAPIX® Application API to upload, control and manage AXIS Camera Application Platform (ACAP) applications and their license keys.

Supported functionality:

-   [Upload application](#upload-application) to the Axis device.
-   [Control application](#control-application) - Start, stop, restart, or remove applications.
-   [Configure applications](#configure-applications) - Manage settings that affect all applications.
-   [Manage license keys](#manage-license-keys) - Upload and remove license keys.
-   [List installed applications](#list-installed-applications) - Retrieve information about installed applications.

### Identification

VAPIX® Application API is supported if:

-   **Property**: `Properties.EmbeddedDevelopment.Version` exists.

`/axis-cgi/applications/list.cgi` requires:

-   **Property**: `Properties.EmbeddedDevelopment.Version=1.20` and later.

`/axis-cgi/applications/config.cgi` requires:

-   **AXIS OS**: 11.2 or later

## Upload application

Use `/axis-cgi/applications/upload.cgi` to upload ACAP applications to the Axis device. Applications are automatically installed when uploaded. However, they are not started.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'file=@<application package (.eap)>;type=application/octet-stream' \\  "http://<servername>/axis-cgi/applications/upload.cgi"
```

```bash
POST /axis-cgi/applications/upload.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="file"; filename="<application package (.eap)>"Content-Type: application/octet-stream<application package data>--<boundary>--
```

### Response
#### Success

```bash
200 OKContent-Type: text/plainOK
```

#### Error

```bash
200 OKContent-Type: text/plainError: <error code>
```

| Error code | Description |
| --- | --- |
| `1` | Invalid application package. The package is not an Embedded Axis Package. |
| `2` | Verification failed. The verification of the application package contents failed. The signature is either missing or invalid. |
| `3` | Application package too large. The package file is too large or the disk is full. |
| `5` | Application package not compatible. The package is not compatible with the Axis device. See the system log for more information. |
| `10` | Unspecified error. See the system log for more information. |
| `12` | Upload currently unavailable. An application package upload is ongoing. |
| `13` | Installation failed. The application package requires a user or group that is not allowed. |
| `14` | Application package already exists. The package already exists in the application store but with a different letter case. |
| `15` | Operation timed out. The outcome of the operation could not be determined. Check logs for more information. |
| `27` | Upgrade not allowed. The vendor ID of the package must be the same as the vendor ID of the application it replaces. |
| `29` | Invalid `manifest.json` or `package.conf` file. |

## Control application

Use `/axis-cgi/applications/control.cgi` to start, stop, restart and remove the ACAP application.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/control.cgi?action=<action>&package=<package>"
```

```bash
POST /axis-cgi/applications/control.cgi?action=<action>&package=<package>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `start`  
`stop`  
`restart`  
`remove` | `start` - Start the application.  
`stop` - Stop the application.  
`restart` - Restart the application.  
`remove` - Remove the application. |
| `package=<string>` | `<package name>` | The application package to perform the action on. |
| `returnpage=<string>`  
_Optional_ | `<path to return page>` | The web page to return to after performing the action. |

### Response
#### Success

```bash
200 OKContent-Type: text/plainOK
```

#### Error

```bash
200 OKContent-Type: text/plainError: <error code>
```

| Error code | Description |
| --- | --- |
| `1` | Invalid application package. The package is not an Embedded Axis Package or it contains an invalid manifest. |
| `4` | Application not found. The specified application package could not be found. |
| `6` | The application is already running. |
| `7` | Application not running. The application must be running to perform the action. |
| `9` | Too many applications are running. The application cannot be started. _This limitation was removed in AXIS OS 12.6_ |
| `10` | Unspecified error. See the system log for more information. |
| `15` | Operation timed out. The outcome of the operation could not be determined. Check logs for more information. |

## Configure applications

Use `/axis-cgi/applications/config.cgi` to access or configure settings that are used by all ACAP applications, such as whether the device will allow unsigned applications to be installed.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/config.cgi?action=<action>&name=<name>"
```

```bash
POST /axis-cgi/applications/config.cgi?action=<action>&name=<name>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `get`  
`set` | `get` - Retrieves the value of a config parameter.  
`set` - Sets the value of a config parameter. |
| `name=<string>` | `AllowUnsigned` (from AXIS OS 11.2)  
`AllowRoot` (AXIS OS 11.5-11.11) | The name of the config parameter that should be operated on. Valid values are described in the _Configuration parameters_ table below. |
| `value=<string>`  
_Optional_ | `true`  
`false` | Should be used when the action is `set` to specify the required value for the config parameter. |

Configuration parameters

| Configuration name | Type | Default value | Description |
| --- | --- | --- | --- |
| `AllowUnsigned` | Boolean | `true` (until AXIS OS 11.11)  
`false` (from AXIS OS 12.0) | Controls whether unsigned applications can be installed. Can be either `true` or `false`. |
| `AllowRoot` | Boolean | `true` (until AXIS OS 11.7)  
`false` (from AXIS OS 11.8) | Controls whether applications running as root can be installed, and if the install scripts are run as root or as the application user. Can be either `true` or `false`. |

### Response
#### Success

Given a request for `AllowUnsigned`:

```bash
200 OKContent-Type: text/xml<reply result="ok">    <param name="AllowUnsigned" value="true" /></reply>
```

#### Error

Given error code `1`:

```bash
200 OKContent-Type: text/xml<reply result="error">    <error type="1" message="Error: gdbus call failed" /></reply>
```

| Error code | Description |
| --- | --- |
| `1` | Malformed request. `value` must be either `true` or `false`. (From AXIS OS 12.2, this has been replaced with HTTP 400 Bad Request) |

#### Success response schema

```bash
<?xml version="1.0" encoding="utf-8" ?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">    <xs:element name="reply">        <xs:complexType>            <xs:sequence>                <xs:element name="param">                    <xs:complexType>                        <xs:simpleContent>                            <xs:extension base="xs:string">                                <xs:attribute type="xs:string" name="name" />                                <xs:attribute type="xs:string" name="value" />                            </xs:extension>                        </xs:simpleContent>                    </xs:complexType>                </xs:element>            </xs:sequence>            <xs:attribute type="xs:string" name="result" />        </xs:complexType>    </xs:element></xs:schema>
```

## Manage license keys

Use `/axis-cgi/applications/license.cgi` to upload, install and remove license keys.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/license.cgi?action=<action>&package=<package>"
```

```bash
POST /axis-cgi/applications/license.cgi?action=<action>&package=<package>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `uploadlicensekey`  
`removelicensekey` | `uploadlicensekey` - Upload a license key.  
`removelicensekey` - Remove a license key. |
| `package=<string>` | `<package name>` | The name of the application package to which the license key belongs. |

### Response
#### Success

```bash
200 OKContent-Type: text/plainOK
```

#### Error

```bash
200 OKContent-Type: text/plainError: <error code>
```

| Error code | Description |
| --- | --- |
| `21` | Invalid license key file. |
| `22` | File upload failed. See the system log for more information. |
| `23` | Failed to remove the license key file. See the system log for more information. |
| `24` | The application is not installed. |
| `25` | The key’s application ID does not match the installed application. |
| `26` | The license key cannot be used with this version of the application. |
| `30` | Wrong serial number. |
| `31` | The license key has expired. |

## List installed applications

Use `/axis-cgi/applications/list.cgi` to list information about installed ACAP applications.

info

`/axis-cgi/applications/list.cgi` is supported for `Properties.EmbeddedDevelopment.Version=1.20` and later.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/list.cgi"
```

```bash
POST /axis-cgi/applications/list.cgiHost: <servername>
```

### Response
#### Success

```bash
200 OKContent-Type: text/xml<reply result="ok">    <application        Name="<Application Name>"        NiceName="<Nice name>"        Vendor="<Vendor name>"        Version="<Version>"        ApplicationID="<ID>"        License="<License status>"        LicenseExpirationDate="<Expiration date>"        Status="<Application status>"        ConfigurationPage="<Configuration link>"        ValidationResult="<Validation URL>" /></reply>
```

Supported elements, attributes and values:

| Element/Attribute | Description |
| --- | --- |
| `application` | Information about one application |
| `application/@Name` | Application short name. |
| `application/@NiceName` | Application official name. |
| `application/@Vendor` | Application vendor. |
| `application/@Version` | Application version. |
| `application/@ApplicationID` | Application ID |
| `application/@License` | `Valid` - License is installed and valid.  
`Invalid` - License is installed but not valid.  
`Missing` - No license is installed.  
`Custom` - Custom license is used. License status cannot be retrieved.  
`None` - Application does not require any license. |
| `application/@LicenseExpirationDate` | Date (YYYY-MM-DD) when the license expires. |
| `application/@Status` | `Running` - Application is running.  
`Stopped` - Application is not running.  
`Idle` - Application is idle. |
| `application/@ConfigurationPage` | Relative URL to application configuration page. |
| `application/@ValidationResult` | Complete URL to a validation or result page. |

#### Response schema

```bash
<?xml version="1.0" encoding="utf-8" ?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">    <xs:simpleType name="EnumResult">        <xs:restriction base="xs:string">            <xs:enumeration value="ok" />            <xs:enumeration value="error" />        </xs:restriction>    </xs:simpleType>    <xs:simpleType name="StatusType">        <xs:restriction base="xs:string">            <xs:enumeration value="Running" />            <xs:enumeration value="Stopped" />            <xs:enumeration value="Idle" />        </xs:restriction>    </xs:simpleType>    <xs:simpleType name="LicenseType">        <xs:restriction base="xs:string">            <xs:enumeration value="Valid" />            <xs:enumeration value="Invalid" />            <xs:enumeration value="Missing" />            <xs:enumeration value="Custom" />            <xs:enumeration value="None" />        </xs:restriction>    </xs:simpleType>    <xs:complexType name="ErrorType">        <xs:attribute name="type" type="xs:string" use="required" />        <xs:attribute name="message" type="xs:string" use="required" />        <xs:anyAttribute processContents="lax" />    </xs:complexType>    <xs:complexType name="ApplicationType">        <xs:attribute name="Name" type="xs:string" use="required" />        <xs:attribute name="ApplicationID" type="xs:integer" />        <xs:attribute name="NiceName" type="xs:string" />        <xs:attribute name="Vendor" type="xs:string" />        <xs:attribute name="Version" type="xs:string" />        <xs:attribute name="Status" type="StatusType" />        <xs:attribute name="License" type="LicenseType" />        <xs:attribute name="LicenseExpirationDate" type="xs:string" />        <xs:attribute name="ConfigurationPage" type="xs:string" />        <xs:attribute name="VendorHomePage" type="xs:string" />        <xs:attribute name="LicenseName" type="xs:string" />        <xs:anyAttribute processContents="lax" />    </xs:complexType>    <xs:element name="reply">        <xs:complexType>            <xs:choice>                <xs:element name="application" type="ApplicationType" minOccurs="0" maxOccurs="unbounded" />                <xs:element name="error" type="ErrorType" minOccurs="0" />            </xs:choice>            <xs:attribute name="result" type="EnumResult" />        </xs:complexType>    </xs:element></xs:schema>
```

## Read general information

Use `/axis-cgi/applications/info.cgi` to retrieve general information related to ACAP support on the device.

### Request

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/applications/info.cgi"
```

```bash
POST /axis-cgi/applications/info.cgiHost: <servername>
```

### Response
#### Success

```bash
200 OKContent-Type: text/xml<reply result="ok">    <supportedSdks>        <sdk>acap3</sdk>        <sdk>acap4-cv</sdk>        <sdk>acap4-native</sdk>    </supportedSdks></reply>
```

Supported elements, attributes and values:

| Argument | Description |
| --- | --- |
| `supportedSdks` | SDKs whose applications able to run on the device. |
| `sdk` | A specific SDK. |