---
title: Log API
url: "https://developer.axis.com/vapix/device-configuration/log-api/"
category: vapix
subcategory: device-configuration
sha256: c83af05e170353e959609afaa036d3f9ed1d2580195028e5de840f0182633bd7
scraped_at: "2026-01-09T15:18:50.750Z"
page_height: 7617
---

# Log API

The VAPIX® Log API makes it possible to manage personalized log configurations on your Axis device. With it, you will be able to:

-   Turn on/off saving logs to the persistent storage and check the current status.
-   Clear log content from the persistent storage.
-   Write messages into the system log.

These calls allow the users to save logs during a set time frame without having to care about log rotation or camera rebooting and to write messages into existing logs.

The log file can be retrieved through `/axis-cgi/serverreport.cgi` with option `tar_all`. Request to CGI with this option can get all log files from the camera.

info

Saving logs to the persistent storage shouldn't always be turned on, since the persistent storage will become full. Free up device space by clearing the persistent log.

info

Avoid writing many large messages during a short period of time, since this can overflow the storage space.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in **ALPHA** stage. The API is provided for testing purposes and is subject to backward-incompatible changes, including modifications to functionality, behavior, and availability. Please don't use in production environment.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Save logs to the persistent storage

Capture logs between boot sessions. This is achieved by:

1.  Turn on saving logs to the persistent storage.
    
2.  Reboot device (through `/axis-cgi/firmwaremanagement.cgi` with method [Reboot](/vapix/network-video/firmware-management-api/#reboot)).
    
3.  Turn off saving logs to the persistent storage.
    
4.  Retrieve the log file on the persistent storage (through `/axis-cgi/serverreport.cgi` with option `tar_all`).
    
5.  Clear log file on the persistent storage to free up device space.
    

Logs of all severity levels are saved to the persistent storage.

#### Turn on/off the saving of logs to the persistent storage

`enabled` is set to true/false to turn on/off the saving of logs to the persistent storage. The following example will show you how to turn on the saving of logs to the persistent storage.

Example

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/log/v1alpha/persistent/enabled" \\  --data '{  "data": true}'
```

```bash
PATCH /config/rest/log/v1alpha/persistent/enabledHost: <servername>Content-Type: application/json{  "data": true}
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

#### Check status of saving logs to the persistent storage

Get the value of **enabled** to check whether the logging to the persistent storage is turned on.

Example

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/log/v1alpha/persistent/enabled"
```

```bash
GET /config/rest/log/v1alpha/persistent/enabledHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": true}
```

#### Clear the log file from the persistent storage

Trigger the action to clear the log file.

Example

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/log/v1alpha/persistent/clearLog" \\  --data '{  "data": {}}'
```

```bash
POST /config/rest/log/v1alpha/persistent/clearLogHost: <servername>Content-Type: application/json{  "data": {}}
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

### Write message into the system log

Write a message into the system log with a user selected severity level.

Example

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/log/v1alpha/writeMessage" \\  --data '{  "data": {    "msg": "message",    "severity": 7  }}'
```

```bash
POST /config/rest/log/v1alpha/writeMessageHost: <servername>Content-Type: application/json{  "data": {    "msg": "message",    "severity": 7  }}
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

## API definition
### Structure

```bash
log.v1 (Root Entity)  writeMessage (Action)  persistent (Entity)    enabled (Property)    clearLog (Action)
```

### Entities

**log.v1**

-   **Description:** Log root object
-   **Type:** Singleton
-   **Operations:** `GET`
-   **Attributes:** _Dynamic Support:_ No

_Properties_

This entry has no properties

_Actions_

_writeMessage_

-   **Description:** Write log message to the system log
-   **Request Datatype:** `WriteMessageRequest`
-   **Response Datatype:** Empty Object
-   **Trigger Permissions:** admin

**log.v1.persistent**

-   **Description:** Status of saving logs to the persistent storage
-   **Type:** Singleton
-   **Operations:** `GET`
-   **Attributes:** _Dynamic Support:_ No

_Properties_

_enabled_

-   **Description:** Whether it is enabled to save logs to the persistent storage
-   **Datatype:** boolean
-   **Operations:**
    -   `GET` - _Permissions:_ admin, operator, viewer
    -   `SET` - _Permissions:_ admin
-   **Attributes:**
    -   _Nullable:_ No
    -   _Dynamic Support:_ No
    -   _Dynamic Enum:_ No
    -   _Dynamic Rang:_ No

_Actions_

_clearLog_

-   **Description:** Clear log file storing all logs
-   **Request Datatype:** Empty Object
-   **Trigger Permissions:** admin

### Data types

| LogMsg |  |
| --- | --- |
| **Description:** | The message part of the log encoded in UTF-8 |
| **Type:** | `string` |
| **Minimum Length:** | 0 |
| **Maximum Length:** | 4096 |
| **Pattern:** | ^.\*$ |

| LogSeverity |  |
| --- | --- |
| **Description:** | Severity as defined by RFC5424 |
| **Type:** | `integer` |
| **Minimum Value:** | 0 |
| **Maximum Value:** | 7 |

| WriteMessageRequest |  |  |
| --- | --- | --- |
| **Description:** | The message to be logged, it contains the severity level of the message and the message itself. |  |
| **Type:** | `complex` |  |
| **Fields:** | msg | **Description:** Text that provides information of the event **Type:** `LogMsg` **Nullable:** No **Gettable:** No |
|  | severity | **Description:** Severity level of this message, default value is 6 meaning "Informational" level **Type:** `LogSeverity` **Nullable:** Yes **Gettable:** No |