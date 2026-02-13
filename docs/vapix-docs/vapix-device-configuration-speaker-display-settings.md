---
title: Speaker Display Settings
url: "https://developer.axis.com/vapix/device-configuration/speaker-display-settings/"
category: vapix
subcategory: device-configuration
sha256: 891ff8298071300ece66f3636e89857af665f788b800676e2fe90eb560648101
scraped_at: "2026-01-09T15:19:04.282Z"
page_height: 12598
---

# Speaker Display Settings

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in BETA stage and provided for testing purposes. It is subject to backward-incompatible changes, including modifications to its functionality, behavior and availability. The API should not be used in production environments.

The VAPIX® Speaker Display Settings API enables configurations for the appearance and availability of the display clock, display brightness and localization.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Get all settings

This example will show you how to retrieve the full collection of settings.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-settings/v1beta"
```

```bash
GET /config/rest/speaker-display-settings/v1betaHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "appearance": {            "backgroundColor": "#000000",            "fontColor": "#670f0f",            "language": "en",            "showDate": true,            "showSeconds": false,            "use24HourClock": true        },        "brightness": {            "adaptiveBrightness": true,            "manualLevel": 6,            "maxAdaptiveLevel": 6,            "minAdaptiveLevel": 1        },        "powerSave": {            "mode": "presenceDetection",            "presenceDetection": {                "powerSaveTimerMinutes": 20            },            "schedule": {                "invert": false,                "scheduleId": "com.axis.schedules.office\_hours"            }        }    }}
```

### Set appearance settings

This example will show you how to apply the appearance settings.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-settings/v1beta/appearance" \\  --data '{    "data": {        "backgroundColor": "#000000",        "fontColor": "#670f0f",        "language": "en",        "showDate": true,        "showSeconds": false,        "use24HourClock": true    }}'
```

```bash
PATCH /config/rest/speaker-display-settings/v1beta/appearanceHost: <servername>Content-Type: application/json{    "data": {        "backgroundColor": "#000000",        "fontColor": "#670f0f",        "language": "en",        "showDate": true,        "showSeconds": false,        "use24HourClock": true    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Set brightness settings

This example will show you how to apply the brightness settings.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-settings/v1beta/brightness" \\  --data '{    "data": {        "adaptiveBrightness": true,        "manualLevel": 6,        "maxAdaptiveLevel": 5,        "minAdaptiveLevel": 4    }}'
```

```bash
PATCH /config/rest/speaker-display-settings/v1beta/brightnessHost: <servername>Content-Type: application/json{    "data": {        "adaptiveBrightness": true,        "manualLevel": 6,        "maxAdaptiveLevel": 5,        "minAdaptiveLevel": 4    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Set power saving settings

This example will show you how to apply the power saving settings.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/speaker-display-settings/v1beta/powerSave" \\  --data '{    "data": {        "mode": "alwaysOff",        "presenceDetection": {            "powerSaveTimerMinutes": 40        },        "schedule": {            "invert": true,            "scheduleId": "com.axis.schedules.office\_hours"        }    }}'
```

```bash
PATCH /config/rest/speaker-display-settings/v1beta/powerSaveHost: <servername>Content-Type: application/json{    "data": {        "mode": "alwaysOff",        "presenceDetection": {            "powerSaveTimerMinutes": 40        },        "schedule": {            "invert": true,            "scheduleId": "com.axis.schedules.office\_hours"        }    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
speaker-display-settings.v1 (Root Entity)    ├── appearance (Entity)        ├── backgroundColor (Property)        ├── fontColor (Property)        ├── language (Property)        ├── showDate (Property)        ├── showSeconds (Property)        ├── use24HourClock (Property)    ├── brightness (Entity)        ├── adaptiveBrightness (Property)        ├── manualLevel (Property)        ├── maxAdaptiveLevel (Property)        ├── minAdaptiveLevel (Property)    ├── powerSave (Entity)        ├── mode (Property)        ├── presenceDetection (Property)        ├── schedule (Property)
```

### Entities
#### speaker-display-settings.v1

-   **Description**: Speaker Display Settings Root Entity.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
        -   **Properties**: appearance, brightness, powerSave
-   **Attributes**
    -   **Dynamic Support**: No

_Properties_

This entity has no properties.

_Actions_

This entity has no actions.

#### speaker-display-settings.v1.appearance

-   **Description**: Speaker Display Clock Entity.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
-   **Properties**: backgroundColor, fontColor, language, showDate, showSeconds, use24HourClock
-   **Attributes**
    -   **Dynamic Support**: No

_Properties_

##### backgroundColor

-   **Description**: Color of the background.
-   **Datatype**: [ColorFormat](#colorformat)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### fontColor

-   **Description**: Color of the text displayed.
-   **Datatype**: [ColorFormat](#colorformat)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### language

-   **Description**: Language of the date displayed.
-   **Datatype**: [DateLanguage](#datelanguage)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### showDate

-   **Description**: If set to true, the date will be displayed.
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### showSeconds

-   **Description**: If set to true, seconds will be displayed.
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### use24HourClock

-   **Description**: If set to true, the clock will display the 24-hour format; otherwise, it will display the 12-hour format with AM/PM.
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

_Actions_

This entity has no actions.

#### speaker-display-settings.v1.brightness

-   **Description**: Speaker Display Brightness Entity.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
        -   **Properties**: `adaptiveBrightness`, `manualLevel`, `maxAdaptiveLevel`, `minAdaptiveLevel`
-   **Attributes**
    -   **Dynamic Support**: No

_Properties_

##### adaptiveBrightness

-   **Description**: Adaptive brightness ON/OFF. If ON, brightness will be automatically adjusted.
-   **Datatype**: boolean
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### manualLevel

-   **Description**: Manual level of brightness set by user, in case adaptiveBrightness is set to false.
-   **Datatype**: [BrightnessRange](#brightnessrange)
-   **Operations**
    -   **Get** (Permissions: admin)
    -   **Set** (Permissions: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### maxAdaptiveLevel

-   **Description**: Maximal screen brightness value.
-   **Datatype**: [BrightnessRange](#brightnessrange)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### minAdaptiveLevel

-   **Description**: Minimal screen brightness value.
-   **Datatype**: [BrightnessRange](#brightnessrange)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

_Actions_

This entity has no actions.

#### speaker-display-settings.v1.powerSave

-   **Description**: Speaker Display Power Save Entity.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
        -   **Properties**: `mode`, `presenceDetection`, `schedule`
-   **Attributes**
-   **Dynamic Support**: No

_Properties_

##### mode

-   **Description**: Power saving mode can be alwaysOn, alwaysOff, schedule, presenceDetection.
-   **Datatype**: [PowerSaveModes](#powersavemodes)
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### presenceDetection

-   **Description**: Parameters belonging to the mode "presenceDetection".
-   **Datatype**: PresenceDetection
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### schedule

-   **Description**: Parameters belonging to the mode "schedule".
-   **Datatype**: Schedule
-   **Operations**
    -   **Get** (_Permissions_: admin)
    -   **Set** (_Permissions_: admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

_Actions_

This entity has no actions.

#### Data types
##### BrightnessRange

-   Description: Brightness range.
-   Type: integer
-   Minimum Value: 1
-   Maximum Value: 7

##### ColorFormat

-   Description: Colors are represented using RGB hexadecimal values.
-   Type: string
-   Pattern: ^#\[0-9a-fA-F\]{6}$

##### DateLanguage

-   **Description**: String enums for supported languages.
-   **Type**: string
-   **Enum Values**: `"de"`, `"en"`, `"es"`, `"fr"`, `"it"`

##### PowerSaveModes

-   **Description**: String enum for power saving modes.
-   **Type**: string
-   **Enum Values**: `"alwaysOn"`, `"alwaysOff"`, `"presenceDetection"`, `"schedule"`

##### PowerSaveTimerMinutes

-   **Description**: Sets the display timeout in minutes, resetting if presence is detected.
-   **Type**: integer
-   **Minimum** Value: 1
-   **Maximum Value**: 60

##### PresenceDetection

-   **Description**: Parameters belonging to the mode "presenceDetection".
-   **Type**: complex
-   **Fields**
    -   **powerSaveTimerMinutes**
        -   **Description**: Time without presence before the display turns off.
        -   **Type**: [PowerSaveTimerMinutes](#powersavetimerminutes)
        -   **Nullable**: No / **Gettable**: No

##### Schedule

-   **Description**: Parameters belonging to the mode "schedule".
-   **Type**: complex
-   **Fields**
    -   **invert**
        -   **Description**: If set to true, the schedule will be inverted. Therefore, during the time-slot when the clock would normally be ON, it will be OFF instead.
        -   **Type**: boolean
        -   **Nullable**: No / **Gettable**: No
    -   **scheduleId**
        -   **Description**: ID of action engine schedule to follow.
        -   **Type**: [ScheduleIdStr](#scheduleidstr)
        -   **Nullable**: Yes / **Gettable**: No

##### ScheduleIdStr

-   **Description**: Schedule ID string.
-   **Type**: string
-   **Maximum Length**: 100