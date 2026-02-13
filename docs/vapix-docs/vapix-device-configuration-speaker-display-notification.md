---
title: Speaker Display Notification
url: "https://developer.axis.com/vapix/device-configuration/speaker-display-notification/"
category: vapix
subcategory: device-configuration
sha256: b722ba95030261daedff00f81f92834ed1f243968b1cc26608dc956285bccabb
scraped_at: "2026-01-09T15:19:02.772Z"
page_height: 9125
---

# Speaker Display Notification

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

The VAPIX® Speaker Display Notification API provides an interface to trigger new notifications on the display, or stop an ongoing notification. It also provides the possibility to stop an ongoing notification.

Note that this API doesn't support coexistence. When used for critical installations, make sure that only one application controls the display.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Send a simple notification with horizontally scrolling large size text

This example will show you have to send a simple notification with large horizontally scrolling text. The response will contain the estimated duration of the notification in milliseconds.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-notification/v1/simple" \\  --data '{    "data": {        "message": "A horizontally scrolling notification",        "textColor": "#FFFFFF",        "textSize": "large",        "scrollDirection": "fromRightToLeft",        "scrollSpeed": 5,        "duration": {            "type": "repetitions",            "value": 3        }    }}'
```

```bash
POST /config/rest/speaker-display-notification/v1/simpleHost: <servername>Content-Type: application/json{    "data": {        "message": "A horizontally scrolling notification",        "textColor": "#FFFFFF",        "textSize": "large",        "scrollDirection": "fromRightToLeft",        "scrollSpeed": 5,        "duration": {            "type": "repetitions",            "value": 3        }    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "duration": 15000    }}
```

### Send a simple notification with vertically scrolling medium size text

This example will show you have to send a simple notification with vertically scrolling medium size text. The response will contain the estimated duration of the notification in milliseconds.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-notification/v1/simple" \\  --data '{    "data": {        "message": "A vertically scrolling notification",        "textColor": "#FFFFFF",        "backgroundColor": "#000000",        "textSize": "medium",        "scrollDirection": "fromBottomToTop",        "scrollSpeed": 8,        "duration": {            "type": "time",            "value": 10000        }    }}'
```

```bash
POST /config/rest/speaker-display-notification/v1/simpleHost: <servername>Content-Type: application/json{    "data": {        "message": "A vertically scrolling notification",        "textColor": "#FFFFFF",        "backgroundColor": "#000000",        "textSize": "medium",        "scrollDirection": "fromBottomToTop",        "scrollSpeed": 8,        "duration": {            "type": "time",            "value": 10000        }    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "duration": 10000    }}
```

### Send a simple notification with non-scrolling medium size text with indefinite duration

This example will show you how to send a simple notification with non-scrolling medium size text that will last on the display until interrupted by another request. The response will contain a duration of 0 to indicate that the notification will last indefinitely.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-notification/v1/simple" \\  --data '{    "data": {        "message": "A static text notification",        "textColor": "#FFFFFF",        "backgroundColor": "#000000",        "textSize": "medium",        "scrollSpeed": 0    }}'
```

```bash
POST /config/rest/speaker-display-notification/v1/simpleHost: <servername>Content-Type: application/json{    "data": {        "message": "A static text notification",        "textColor": "#FFFFFF",        "backgroundColor": "#000000",        "textSize": "medium",        "scrollSpeed": 0    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "duration": 0    }}
```

### Stop the ongoing notification

This example will show you how to stop an ongoing notification.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-notification/v1/stop" \\  --data '{    "data": {}}'
```

```bash
POST /config/rest/speaker-display-notification/v1/stopHost: <servername>Content-Type: application/json{    "data": {}}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {}}
```

## API definition
### Structure

```bash
speaker-display-notification.v1 (Root Entity)    ├── simple (Action)    ├── stop (Action)
```

### Entities
#### speaker-display-notification.v1

-   **Description**: Speaker Display Notification Root Entity.
-   **Type**: Singleton
-   **Operations**
    -   `Get`
-   **Attributes**
    -   **Dynamic Support**: No

#### Properties

This entity has no properties.

#### Actions
##### simple

-   **Description**: A simple notification which can either be static or scrolling.
-   **Request Datatype**: [SimpleNotificationRequest](#simplenotificationrequest)
-   **Response Datatype**: [NotificationResponse](#notificationresponse)
-   **Trigger Permissions**: admin

##### stop

-   **Description**: Stop the ongoing notification.
-   **Request Datatype**: [StopNotificationRequest](#stopnotificationrequest)
-   **Response Datatype**: [StopNotificationResponse](#stopnotificationrequest)
-   **Trigger Permissions**: admin

### Data types
#### ColorFormat

-   **Description**: Colors are represented using RGB hexadecimal values.
-   **Type**: string
-   **Pattern**: `^#[0-9a-fA-F]{6}$`

#### DurationInt

-   **Description**: The value of the duration. Limited to a signed 32-bit integer.
-   **Type**: integer
-   **Minimum Value**: 1
-   **Maximum Value**: 2147483647

#### NotificationResponse

-   **Description**: Response received from a simple notification request.
-   **Type**: complex
-   **Fields**
    -   **duration**
        -   **Description**: Duration of the notification in milliseconds.
        -   **Type**: integer
        -   **Nullable**: No / **Gettable**: No

#### ScrollDirectionEnum

-   **Description**: Direction of the scrolling.
-   **Type**: string
-   **Enum Values**: `"fromRightToLeft"`, `"fromBottomToTop"`

#### ScrollSpeedInt

-   **Description**: Scroll speed range.
-   **Type**: integer
-   **Minimum Value**: 0
-   **Maximum Value**: 10

#### SimpleDurationObject

-   **Description**: Duration object for simple notification.
-   **Type**: complex
-   **Fields**
    -   **type**
        -   **Description**: Duration type can be repetitions, time or timeCompleteMessage.
        -   **Type**: [SimpleDurationType](#simpledurationtype)
        -   **Nullable**: No / **Gettable**: No
    -   **value**
        -   **Description**: If type is repetitions, the message will be displayed for a number of repetitions; otherwise, it will be displayed for a duration in milliseconds.
        -   **Type**: [DurationInt](#durationint)
        -   **Nullable**: No / **Gettable**: No

For simple notification, the following duration types are accepted:

-   **repetitions**: number of times the message will be displayed on the screen.
-   **time**: the message will be displayed on the screen for a duration given in milliseconds.
-   **timeCompleteMessage**: the message will be displayed on the screen for at least a duration given in milliseconds but rounded up to the nearest complete repetition, ensuring that the message will be entirely displayed before it stops.

#### SimpleDurationType

-   **Description**: String enums for supported duration types for simple notification.
-   **Type**: string
-   **Enum Values**: `"repetitions"`, `"time"`, `"timeCompleteMessage"`

#### SimpleMessageStr

-   **Description**: String for simple notification message.
-   **Type**: string
-   **Maximum Length**: 1000

The message field is mandatory, however an empty string will be accepted. In case of a horizontally scrolling notification, newline characters will be ignored. In case of a static notification (scroll speed 0) an attempt will be made to fit the text within display dimensions, but the text might still be trimmed.

#### SimpleNotificationRequest

-   **Description**: Available fields to send a simple notification request.
-   **Type**: complex
-   **Fields**
    -   **backgroundColor**
        -   **Description**: Background color. Format is RGB in hex 6 digits '#RRGGBB'.
        -   **Type**: [ColorFormat](#colorformat)
        -   **Nullable**: No / **Gettable**: No
    -   **duration**
        -   **Description**: Duration. Default is infinite repetitions.
        -   **Type**: [SimpleDurationObject](#simpledurationobject)
        -   **Nullable**: No / **Gettable**: No
    -   **message**
        -   **Description**: The display message. Max length is 1000 characters.
        -   **Type**: [SimpleMessageStr](#simplemessagestr)
        -   **Nullable**: No / **Gettable**: No
    -   **scrollDirection**
        -   **Description**: The scrolling direction. Can be either from right to left or bottom to top.
        -   **Type**: [ScrollDirectionEnum](#scrolldirectionenum)
        -   **Nullable**: No / **Gettable**: No
    -   **scrollSpeed**
        -   **Description**: Message scroll speed. 1 is slow and 10 is fast. 0 means no scrolling.
        -   **Type**: [ScrollSpeedInt](#scrollspeedint)
        -   **Nullable**: No / **Gettable**: No
    -   **textColor**
        -   **Description**: The color of the message letters. Format is RGB in hex 6 digits '#RRGGBB'.
        -   **Type**: [ColorFormat](#colorformat)
        -   **Nullable**: No / **Gettable**: No
    -   **textSize**
        -   **Description**: The text size. Can be either small, medium or large.
        -   **Type**: [TextSizeEnum](#textsizeenum)
        -   **Nullable**: No / **Gettable**: No

#### StopNotificationRequest

-   **Description**: Request to stop a simple notification.
-   **Type**: complex
-   **Fields**

#### StopNotificationResponse

**Description**: Response received from stop notification request. **Type**: complex **Fields**

#### TextSizeEnum

-   **Description**: Size of the text.
-   **Type**: string
-   **Enum Values**: `"small"`, `"medium"`, `"large"`