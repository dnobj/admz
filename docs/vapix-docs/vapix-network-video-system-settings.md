---
title: System settings
url: "https://developer.axis.com/vapix/network-video/system-settings/"
category: vapix
subcategory: network-video
sha256: 0e33007fee2fed98a20177eae3ef5798468c23f09993ba0591045ad98e4da93e
scraped_at: "2026-01-09T15:21:12.456Z"
page_height: 24637
---

# System settings

## Description

The HTTP-based video interface provides the functionality for configuring system settings. This document describes the general syntaxes, requests and values that are used for general configurations of your Axis product.

The following CGIs are described in this document:

| Name | Description |
| --- | --- |
| `/axis-cgi/pwdgrp.cgi` | Add, delete and manage user accounts. |
| `/axis-cgi/factorydefault.cgi` | Reload factory default. Some parameters are not set to their factory default value. |
| `/axis-cgi/hardfactorydefault.cgi` | Reload factory default. All parameters are set to their factory default value. |
| `/axis-cgi/firmwareupgrade.cgi` | Upgrade the AXIS OS version. |
| `/axis-cgi/restart.cgi` | Restart the Axis product. |
| `/axis-cgi/serverreport.cgi` | Get a server report from the Axis product. |
| `/axis-cgi/systemlog.cgi` | Get system log information. |
| `/axis-cgi/accesslog.cgi` | Get client log information. |

## Prerequisites
### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 5.00 and later.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Add, modify and delete user accounts

Use `/axis-cgi/pwdgrp.cgi` to add a new user account with password and group membership, modify the information and remove a user account.

**Identification**

-   **API Discovery**: `id=user-management`
-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 5.00 and later
-   **Security level**: Administrator (Administrator privileges are required if an administrator user exists)
-   **Method**: `GET`/`POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/pwdgrp.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `add` `update` `remove` `get` | `add` = Create a new user account. `update` = Change user account information of specified parameters if the user account exists. `remove` = Remove an existing user account. `get` = Get a list of the user accounts which belong to each group defined. |
| `user=<string>` _Required if_ `action=add`. _Adding a value to_ `comment` _is optional._ | String | The user account name (1-14 characters), a non-existing user account name. Valid characters are a-z, A-Z and 0-9. |
| `pwd=<string>` _Required if_ `action=add`. _Adding a value to_ `comment` _is optional._ | String | The password for the account. It must contain one or more characters. |
| `grp=<string>` _Required if_ `action=add`. _Adding a value to_ `comment` _is optional._ | String | An existing primary group account name. The recommended value for this argument is `users`. VAPIX® also supports the value `root`, but it should only be used when creating the initial user account. |
| `sgrp=<string>`\[:`<string>``...`\] _Required if_ `action=add`. _Adding a value to_ `comment` _is optional._ | `<string>`\[`:``<string>``...`\] | Colon separated existing secondary group account names. This argument sets the user access rights for the user account: The supported values for this group are: `viewer` = Viewer role. `viewer:ptz` = Viewer role, with PTZ control. `operator:viewer` = Operator role. `operator:viewer:ptz` = Operator role, with PTZ control. `admin:operator:viewer` = Admin role. `admin:operator:viewer:ptz` = Admin role, with PTZ control.Please note that the group names can be in any order. Please note: On Axis network door controllers, users assigned the _viewer_, _operator_, or _admin_ roles can access PINs and card numbers in plain text through event metadata streaming. |
| `comment=<string>` _Required if_ `action=add`. _Adding a value to_ `comment` _is optional._ _Optional in device software and service releases since autumn 2019._ | String | Description of the user account. This value can be empty. |
| `strict_pwd=<integer>` | Integer | Set to `1` to enforce VAPIX® password standard. Valid characters for passwords are ASCII characters with byte codes in the range of `0x20 - 0x7E`. The password must be within 64 characters. |

info

It is not advisable to create user access data in the URL, as that might compromise security. Instead, pass the arguments to `/axis-cgi/pwdgrp.cgi` in the request body.

**Example 1:**

Create the initial admin account on the device. This must be done to log in to the device for the first time. The initial admin account has the following restrictions on devices running AXIS OS versions older than 11.5:

-   The user name must be `root` and the role must be Administrator with PTZ control.
-   The comment parameter must be either empty or omitted.
-   This user can not be deleted, and can only be created once.

The only restriction on devices running AXIS OS 11.5 and later is that the role must be Administrator with PTZ control.

Since logging in to the device is impossible at this stage, no authentication is required to create it. This changes as soon as this user has been created however, and authentication and admin privileges will be required for all future user handling operations.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=add&user=root&pwd=foo&grp=root&sgrp=admin:operator:viewer:ptz"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=add&user=root&pwd=foo&grp=root&sgrp=admin:operator:viewer:ptzHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Created account root.
```

**Example 2:**

Create a new user account with administrator and PTZ control privileges.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=add&user=joe&pwd=foo&grp=users&sgrp=admin:operator:viewer:ptz&comment=Joe"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=add&user=joe&pwd=foo&grp=users&sgrp=admin:operator:viewer:ptz&comment=JoeHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Created account joe.
```

**Example3:**

Change the password of an existing account.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=update&user=joe&pwd=bar"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=update&user=joe&pwd=barHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Modified account joe.
```

**Example 4:**

Remove an account.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=remove&user=joe"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=remove&user=joeHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Removed account joe.
```

**Example 5:**

List groups and users. In this example Joe is the administrator, Ellen is the operator with PTZ rights and Frank is the viewer without PTZ rights.

The `digusers` parameter is used to list all created users , however, `admin`, `operator`, `viewer` and `ptz` are all access group rights. This means that Joe, who is the administrator, will be listed in all groups, while Ellen is only visible in `operator`, `viewer` and `ptz`, as her account only has the access rights to these.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=get"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=getHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
admin="root,joe"operator="root,joe,ellen"viewer="root,joe,ellen,frank"ptz="root,joe,ellen"digusers="root,joe,ellen,frank"
```

**Example 6:**

Create an account with enforced VAPIX® password standards.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/pwdgrp.cgi?action=add&user=joe&pwd=foo&grp=users&sgrp=admin:operator:viewer:ptz&comment=Joe&strict\_pwd=1"
```

```bash
GET /axis-cgi/pwdgrp.cgi?action=add&user=joe&pwd=foo&grp=users&sgrp=admin:operator:viewer:ptz&comment=Joe&strict\_pwd=1Host: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Modified the account joe.
```

**Error Responses:**

**Example 7:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Error: consult the system log file.
```

**Example 8:**

If the action is omitted or is not one of `add`, `update`, `remove` or `get`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Error: action operation type.
```

**Example 9:**

No user name was supplied, or the user name contains characters other than A-Z, a-z or 0-9.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Error: account user name.
```

**Example 10:**

The user name is not appropriate for the action.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
Error: malformed action operation, <action>.
```

**Example 11:**

No admin user has been created and the user that attempted to be added is not a valid initial admin user.

-   **HTTP code**: `401 Unauthorized`
-   **Content-Type**: `text/html`

```bash
Error: not a valid initial admin user.
```

**Example 12:**

No admin user has been created. Start by creating one and use it to login and perform the requested operation.

-   **HTTP code**: `401 Unauthorized`
-   **Content-Type**: `text/html`

```bash
Error: initial admin user must be created first.
```

## Factory default

info

See [factoryDefault](/vapix/network-video/firmware-management-api/#factorydefault) in the Firmware management API for updated information.

Use `/axis-cgi/factorydefault.cgi` to reset to factory default. All settings are set to their factory default values except.

-   The boot protocol (`Network.BootProto`).
-   The static IP address (`Network.IPAddress`).
-   The default router (`Network.DefaultRouter`).
-   The subnet mask (`Network.SubnetMask`).
-   The broadcast IP address (`Network.Broadcast`).
-   The system time.
-   The IEEE 802.1X settings.

Since these parameters are not reset the Axis product can be accessed on the same address. This is especially important when using NAT router. After the Axis product has been reset to factory default it is restarted as part of this function.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/factorydefault.cgi"
```

```bash
GET /axis-cgi/factorydefault.cgiHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
<html response>
```

## Hard factory default

info

See [factoryDefault](/vapix/network-video/firmware-management-api/#factorydefault) in the Firmware management API for updated information.

Use `/axis-cgi/hardfactorydefault.cgi` to reset to factory default. All settings, including the IP addresses, are set to their factory default values. After the Axis product has been reset to factory default it is restarted as part of this function.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/hardfactorydefault.cgi"
```

```bash
GET /axis-cgi/hardfactorydefault.cgiHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
<html response>
```

## AXIS OS upgrade

info

See [Upgrade](/vapix/network-video/firmware-management-api/#upgrade) in the Firmware management API for updated information.

Use `/axis-cgi/firmwareupgrade.cgi` to upgrade the AXIS OS version. After the upgrade, the device will be restarted automatically.

-   **Security level**: Administrator

Syntax:

```bash
POST /axis-cgi/firmwareupgrade.cgi\[?<argument>=<value>\]Host: <servername>Content-Type: multipart/form-data; boundary=<boundary>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `type=<string>` | `normal` `factorydefault` | Specifies the type of AXIS OS upgrade. `normal` = Upgrade and restore old settings. `factorydefault` = All parameters are set to their default value. Default: `normal`. |

The file content is provided in the HTTP body according to the format given in RFC 1867. The body is created automatically by the browser if using HTML form with input type "file".

Body:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form '<name>=@<file name>;type=application/octet-stream' \\  "http://<servername>/axis-cgi/firmwareupgrade.cgi?type=normal"
```

```bash
POST /axis-cgi/firmwareupgrade.cgi?type=normalHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>Content-Length: <content length>--<boundary>Content-Disposition: form-data; name="<name>"; filename="<file name>"Content-Type: application/octet-stream<AXIS OS file content>--<boundary>--
```

For more AXIS OS upgrade options, see [Firmware management API](/vapix/network-video/firmware-management-api/)

## Restart server

info

See [Reboot](/vapix/network-video/firmware-management-api/#reboot) in the Firmware management API for updated information.

Use `/axis-cgi/restart.cgi` to restart the Axis product.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/restart.cgi"
```

```bash
GET /axis-cgi/restart.cgiHost: <servername>
```

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/html`

```bash
<html response>
```

## Server report
### Description

Use `/axis-cgi/serverreport.cgi` to generate and return a server report. This report is useful as an input when requesting support. The report includes product information, parameter settings and system logs.

### HTTP API

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/serverreport.cgi\[?<argument>=<value>\]"
```

```bash
GET /axis-cgi/serverreport.cgi\[?<argument>=<value>\]Host: <servername>
```

| Parameter | Valid value | Description |
| --- | --- | --- |
| `mode=<string>` | `tar_all` `text` `zip` `zip_with_image` _Only available on products with application support._ | The server report presentation mode. `tar_all` will return all log files (including system log, access log, audit log, etc) as a .tar file. `text` will return the server report as text. `zip` will return the server report as a .zip-file. `zip_with_image` will return report together with a snapshot image taken using the Image Appearance settings as a single .zip-file. _Optional_. If `mode` is not specified, the value defaults to `text`. |

### Common examples

**Example 1: Get the server report as text**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/serverreport.cgi?mode=text"
```

```bash
GET /axis-cgi/serverreport.cgi?mode=textHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
<server report>
```

**Example 2: Get the server report as a .zip-file**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/serverreport.cgi?mode=zip"
```

```bash
GET /axis-cgi/serverreport.cgi?mode=zipHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/zip`

```bash
<.zip-file>
```

**Example 3: Get the server report and a snapshot image with the current image settings as a .zip-archive**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/serverreport.cgi?mode=zip\_with\_image"
```

```bash
GET /axis-cgi/serverreport.cgi?mode=zip\_with\_imageHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/zip`

```bash
<message>
```

## Logs
### Parameters

**Log.Access**

These parameters control inclusion of information in the client access log.

info

Parameter Log.Access is not available in AXIS OS 5.60 and later.

Log.Access

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `MaxSize` | `40000` | `1000 ... 100000` | admin: read, write | The maximum size of the access log. |
| `Critical` | `detailed` | `off` `on` `detailed` | admin: read, write | Set the level of critical messages that should be shown in the access log. |
| `Warning` | `detailed` | `off` `on` `detailed` | admin: read, write | Set the level of warning messages that should be shown in the access log. `off` = No warning messages will be shown. `on` = All suspected intrusions are shown. `detailed` = All suspected intrusions and access denied events are shown. |
| `Informational` | `off` | `off` `on` `detailed` | admin: read, write | Set the level of informational messages that should be shown in the access log. `off` = No informational messages will be shown. `on` = Most access information will be shown, but some similar and trivial messages are filtered out. `detailed` = All information will be shown. |

**Log.System**

These parameters control inclusion of information in the system log.

info

Parameter Log.System is not available in AXIS OS 5.60 and later.

Log.System

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `MaxSize` | `40000` | `1000 ... 100000` | admin: read, write | The maximum size of the system log. |
| `Critical` | `detailed` | `off` `on` `detailed` | admin: read, write | Set the level of critical messages that should be shown in the system log. `off` = No critical messages will be shown. `on` = All critical messages will be shown. `detailed` = All critical messages will be shown. Note: Today there is no difference setting the level to on or detailed. |
| `Warning` | `detailed` | `off` `on` `detailed` | admin: read, write | Set the level of warning messages that should be shown in the system log. `off` = No warning messages will be shown. `on` = All warning messages will be shown. `detailed` = All warning messages will be shown. Note: Today there is no difference setting the level to on or detailed. |
| `Informational` | `off` | `off` `on` `detailed` | admin: read, write | Set the level of informational messages that should be shown in the system log. `off` = No informational messages will be shown. `on` = All informational messages will be shown. `detailed` = All informational messages will be shown. Note: Today there is no difference setting the level to on or detailed. |

**MailLogd**

Parameters for log levels to send as e-mail.

MailLogd

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `LogSendLevel` | 0 | `0` ... `3` | admin: read, write | Message that are sent in e-mail: `0` = None. `1` = Critical. `2` = Critical and Warning. `3` = Critical, Warning and Information. |
| `ToEmail` |  | `<string>` | admin: read, write | The e-mail address to where log messages are sent. |

### HTTP API
#### System log

Use `/axis-cgi/systemlog.cgi` to retrieve system log information. The level of information included in the log is set in the `Log.System` parameter group.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/systemlog.cgi\[?<argument>=<value>\]"
```

```bash
GET /axis-cgi/systemlog.cgi\[?<argument>=<value>\]Host: <servername>
```

| Parameter | Valid value | Description |
| --- | --- | --- |
| `text=<string>` | Any string that contains only letters and digits. | The log entries are filtered on this text. Log entries that contain this text will be shown in the web interface. Available on AXIS OS 11.11.45 and later. |

**Response**:

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Body:

```bash
<system log information>
```

#### Access log

Use `/axis-cgi/accesslog.cgi` to retrieve client access log information. The level of information included in the log is set in the `Log.Access` parameter group.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/accesslog.cgi"
```

```bash
GET /axis-cgi/accesslog.cgiHost: <servername>
```

**Response**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Body:

```bash
<access log information>
```

## System date and time

info

This API will no longer receive updates. For a newer version on how to configure date, time and time zones, see [Time API](/vapix/device-configuration/time-api/).

Get or set the system date and time.

### Parameters

**Time**

The parameters in the `time` group control the common time information for the time zone, how date and time are synchronized and the offset related to the chosen time zone and Coordinated Universal Time, UTC.

Time

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `ObtainFromDHCP` | `yes` | `yes` `no` | admin: read, write | DHCP servers may provide names/IP addresses for local/remote NTP servers. Enable this feature by setting this parameter to `yes`. |
| `SyncSource` | Product/release dependent. | `PC` `NTP` `None` _Product/release dependent. Check the product’s release notes._ | admin: read, write | The source to synchronize the time with. `PC` = Synchronize the time with the connected PC. `NTP` = Synchronize the time with a NTP server. `None` = Set the time manually. |
| `POSIXTimeZone` | `GMT0BST,M3.5.0/1,M10.5.0` | `<name>``<offset>`\[`<dst name>`\[`dst offset`\>\[,`<start rule>`,`<stop rule>`\]\]\] _POSIX TZ rule strings as defined for the TZ variable in Chapter 8.3, The Open Group Base Specifications Issue 6 IEEE Std 1003.1, 2004._ The ':' prefixed format is not allowed. | admin: read, write operator: read | This parameter specifies the time zone with and/or without DST. See section Time zone below for more information. |

Set the TimeZone.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Time.POSIXTimeZone=GMT0BST,M3.5.0/1,M10.5.0"
```

```bash
GET /axis-cgi/param.cgi?action=update&Time.POSIXTimeZone=GMT0BST,M3.5.0/1,M10.5.0Host: <servername>
```

This timezone, standard time named `GMT` and daylight saving time named `BST`, has daylight saving time. The standard local time is `GMT`. Daylight saving time, 1 hour ahead of `GMT`, starts the last Sunday in March at 01:00 and ends the last Sunday in October at 02:00.

**Time.DST**

The parameter in the `Time.DST` group controls the Daylight Saving Time (DST).

Time.DST

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write operator: read | Enable/disable DST. `yes` = Enable DST. `no` = Disable DST. |

**Time zone**

`POSIXTimeZone` specifies the time zone with or without DST. The value is added according to the following syntax:

`<name>``<offset>`\[`<dst name>`\[`dst offset`\>\[,`<start rule>`,`<stop rule>`\]\]\]

`<name>` and `<dst name>` = The name of the time zone without and with DST. A name is at least 3 characters long and at most 6 characters long. It can be unquoted or quoted. An unqouted name may only contain the characters `A`\-`Z` and `a`\-`z`. A quoted name starts with the < character and ends with a > character. It can have the characters `A`\-`Z`, `a`\-`z`, `0-9`, `-` and `+`.

`<offset>` and `<dst offset>` = The offset for the time zone and the daylight saving time, respectively. An offset specifies the amount of time that when added to the local time is equal to UTC. For example the offset for Paris, France, without daylight saving time, is `-1` and the offset for Chicago, Ill., without daylight saving time, is `+6`. Offsets are specified as `HH:MM:SS` (hours, `0-24`; minutes `0-59` and seconds `0-59`) preceded by '`-`' indicating a negative offset or an optional '`+`', indicating a positive offset. Minutes and seconds are optional, thus the valid formats are "`HH`" "`HH`:`MM`" "`HH`:`MM`:`SS`". The dst offset may be omitted and will then default to one hour ahead of the zone's standard time.

`<start rule>` and `<stop rule>` = The daylight saving time start and stop rules are specified in the form _date_ or _date/time_. The date is specified in the form _Month_._Week_._Day_, _Jday_, or _day_. The _Month_._Week_._Day_form sets the month (_1_\-_12_), week (_1_\-_5_, with _5_ meaning the last week in Month that Day occurs) and day (_0_\-_6_, _0_ is Sunday). The _Jn_ form sets the _n_:th day (_1_\-_365_, leap days are not counted). The _n_ form sets the day (_0_\-_365_, leap days are counted; day _365_ thus only exists in leap years).

The time is specified as _HH_, _HH_:_MM_ or _HH_:_MM_:_SS_, as the offsets above. It is the local time for the DST transition. The time is always positive and must not be preceded by a sign. If the time is omitted the daylight saving time transition occurs at 02:00:00.

_Example_: If a zone has a 1 hour DST to standard time offset and the transition time to DST is 02:00 then 01:59:59 will be followed by 03:00:00. If the transition time from DST to standard time in the same zone is 02:00 then 01:59:59 (daylight saving time) will be followed by 01:00:00 (standard time).

**Time.NTP**

The parameters in the `Time.NTP` set time and date with the NTP protocol.

Time.NTP

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Server` | `0.0.0.0` | An IP address or a host name. | admin: read, write | The NTP server to connect to when synchronizing the time in the Axis product. |
| `VolatileServer` |  | An IP address or a host name. | admin: read | The name/IP address of the NTP server, received from the DHCP server. Only one NTP server is currently supported. The NTP server name/IP address will be valid only until the next DHCP renewal or reboot. |