---
title: P8815-2 3D people counter API
url: "https://developer.axis.com/vapix/applications/p8815-2-3d-people-counter-api/"
category: vapix
subcategory: applications
sha256: 22b68c6df328cf2492dc5536d26dae9d85f204c7c86ca8679b8fe29f511ab6d0
scraped_at: "2026-01-09T15:01:22.116Z"
page_height: 26177
---

# P8815-2 3D people counter API

## Description

The AXIS 3D People Counter API contains the information and steps that makes it possible to access and integrate people counting data with the [AXIS P8815–2](https://www.axis.com/sv-se/products/axis-p8815-2-3d-people-counter). Features include being able to keep count of the number of people in indoor premises, such as shopping centers.

Using the API also lets you use several different reporting capabilities to enable integration of the people counting data collected by your device into third-party services and applications.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## API specification
### Download foot traffic statistics

This method should be used when you want to retrieve the foot traffic statistics (In/Out) stored on your Axis camera using either JSON or plain text in a comma separated format (CSV).

-   **Format**: CSV or JSON
-   **Method**: `GET`

#### Request (CSV)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export/csv?start=<date>&end=<date>&resolution=<resolution>"
```

```bash
GET /a3dpc/api/export/csv?start=<date>&end=<date>&resolution=<resolution>Host: <servername>
```

#### Request (JSON)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export/json?start=<date>&end=<date>&resolution=<resolution>"
```

```bash
GET /a3dpc/api/export/json?start=<date>&end=<date>&resolution=<resolution>Host: <servername>
```

| Field | Parameters |
| --- | --- |
| `date` | `YYYYMMDD` (start-of-day) |
|  | `yesterday` (start-of-day) |
|  | `today` (start-of-day) |
|  | `now` (current time) |
| `resolution` | `minute` |
|  | `hour` |
|  | `day` |

#### Return
##### Successful response: HTTP code `200 OK`

Returns the foot traffic statistics stored on the camera as either JSON or in plain text using the comma separated format (CSV). The first line in the CSV file contains a description of each element, while the following lines contain the corresponding data for the chosen time interval and its resolution: `start`, `end`, `in`, `out`.

##### Error response: HTTP code `400 Bad Request`

```bash
{    "error": {        "message": "Validation failed",        "error": \[            {                "field": "<field>",                "reason": "<reason>"            }        \]    }}
```

#### Example 1

This example will show you what happens when you retrieve foot traffic statistics from your camera using the JSON format. The data in this example will be from a previous day and measured in hourly intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export/json?start=yesterday&end=today&resolution=hour"
```

```bash
GET /a3dpc/api/export/json?start=yesterday&end=today&resolution=hourHost: <servername>
```

Sample output

```bash
{    "data": \[        {            "start": "2020-06-23 00:00:00",            "end": "2020-06-23 01:00:00",            "in": 0,            "out": 0        }    \]}
```

#### Example 2

This example will show you what happens when you retrieve the foot traffic statistics from your camera using the CSV format. The data in this example will be for the current day and measured in minute intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export/csv?start=today&end=now&resolution=minute"
```

```bash
GET /a3dpc/api/export/csv?start=today&end=now&resolution=minuteHost: <servername>
```

Sample output (first 10 lines)

```bash
start,end,in,out2020-09-23 00:00:00,2020-09-23 00:01:00,0,02020-09-23 00:01:00,2020-09-23 00:02:00,0,02020-09-23 00:02:00,2020-09-23 00:03:00,0,02020-09-23 00:03:00,2020-09-23 00:04:00,0,02020-09-23 00:04:00,2020-09-23 00:05:00,0,02020-09-23 00:05:00,2020-09-23 00:06:00,0,02020-09-23 00:06:00,2020-09-23 00:07:00,0,02020-09-23 00:07:00,2020-09-23 00:08:00,0,02020-09-23 00:08:00,2020-09-23 00:09:00,0,0
```

#### Example 3

This example will show you what happens when you retrieve foot traffic statistics on your camera using the CSV format for a specific date range. The data in this example will be between 2020–08–01 and up until today, measured in daily intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export/csv?start=20200801&end=today&resolution=day"
```

```bash
GET /a3dpc/api/export/csv?start=20200801&end=today&resolution=dayHost: <servername>
```

Sample output (first 10 lines)

```bash
start,end,in,out2020-08-01 00:00:00,2020-08-02 00:00:00,0,02020-08-02 00:00:00,2020-08-03 00:00:00,0,02020-08-03 00:00:00,2020-08-04 00:00:00,0,02020-08-04 00:00:00,2020-08-05 00:00:00,0,02020-08-05 00:00:00,2020-08-06 00:00:00,0,02020-08-06 00:00:00,2020-08-07 00:00:00,0,02020-08-07 00:00:00,2020-08-08 00:00:00,0,02020-08-08 00:00:00,2020-08-09 00:00:00,0,02020-08-09 00:00:00,2020-08-10 00:00:00,0,0
```

### Download occupancy statistics

This method should be used when you want to retrieve the occupancy statistics stored on your Axis camera using either JSON or plain text in a comma separated format (CSV).

-   **Format**: CSV or JSON

#### Request (CSV)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export\_occupancy/csv?start=<date>&end=<date>&resolution=<resolution>"
```

```bash
GET /a3dpc/api/export\_occupancy/csv?start=<date>&end=<date>&resolution=<resolution>Host: <servername>
```

#### Request (JSON)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export\_occupancy/json?start=<date>&end=<date>&resolution=<resolution>"
```

```bash
GET /a3dpc/api/export\_occupancy/json?start=<date>&end=<date>&resolution=<resolution>Host: <servername>
```

| Field | Parameters |
| --- | --- |
| `date` | `YYYYMMDD` (start-of-day) |
|  | `yesterday` (start-of-day) |
|  | `today` (start-of-day) |
|  | `now` (current time) |
| `resolution` | `hour` |
|  | `day` |

#### Return
##### Successful response: HTTP code `200 OK`

Returns the occupancy statistics stored on the camera as either JSON or in plain text using the comma separated format (CSV). The first line in the CSV file contains a description of each element, while the following lines contain the corresponding data for the chosen time interval and its resolution: `start`, `end` and `peak`.

##### Error response: HTTP code `400 Bad Request`

```bash
{    "error": {        "message": "Validation failed",        "error": \[            {                "field": "<field>",                "reason": "<reason>"            }        \]    }}
```

#### Example 1

This example will show you what happens when you retrieve occupancy statistics from your camera using the JSON format. The data in this example will be from a previous day and measured in hourly intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export\_occupancy/json?start=yesterday&end=today&resolution=hour"
```

```bash
GET /a3dpc/api/export\_occupancy/json?start=yesterday&end=today&resolution=hourHost: <servername>
```

Sample output

```bash
{    "data": \[        {            "start": "2023-01-08 00:00:00",            "end": "2023-01-08 01:00:00",            "peak": 0        },        {            "start": "2023-01-08 01:00:00",            "end": "2023-01-08 02:00:00",            "peak": 0        }    \]}
```

#### Example 2

This example will show you what happens when you retrieve the occupancy statistics from your camera using the CSV format. The data in this example will be for the current day and measured in hour intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export\_occupancy/csv?start=yesterday&end=today&resolution=hour"
```

```bash
GET /a3dpc/api/export\_occupancy/csv?start=yesterday&end=today&resolution=hourHost: <servername>
```

Sample output (first 10 lines)

```bash
start,end,peak2023-01-09 00:00:00,2023-01-09 01:00:00,02023-01-09 01:00:00,2023-01-09 02:00:00,02023-01-09 02:00:00,2023-01-09 03:00:00,02023-01-09 03:00:00,2023-01-09 04:00:00,02023-01-09 04:00:00,2023-01-09 05:00:00,02023-01-09 05:00:00,2023-01-09 06:00:00,02023-01-09 06:00:00,2023-01-09 07:00:00,02023-01-09 07:00:00,2023-01-09 08:00:00,32023-01-09 08:00:00,2023-01-09 09:00:00,172023-01-09 09:00:00,2023-01-09 10:00:00,21
```

#### Example 3

This example will show you what happens when you retrieve occupancy statistics on your camera using the CSV format for a specific date range. The data in this example will be between 2022–12–31 and up until today, measured in daily intervals.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/export\_occupancy/csv?start=20221231&end=today&resolution=day"
```

```bash
GET /a3dpc/api/export\_occupancy/csv?start=20221231&end=today&resolution=dayHost: <servername>
```

Sample output (first 10 lines)

```bash
start,end,peak2022-12-31 00:00:00,2023-01-01 00:00:00,12023-01-01 00:00:00,2023-01-02 00:00:00,22023-01-02 00:00:00,2023-01-03 00:00:00,172023-01-03 00:00:00,2023-01-04 00:00:00,212023-01-04 00:00:00,2023-01-05 00:00:00,262023-01-05 00:00:00,2023-01-06 00:00:00,192023-01-06 00:00:00,2023-01-07 00:00:00,52023-01-07 00:00:00,2023-01-08 00:00:00,22023-01-08 00:00:00,2023-01-09 00:00:00,1
```

#### Request real-time data

This method should be used when you want to retrieve real-time estimated occupancy and counting statistics for the primary camera as well as its connected secondary cameras using the JSON format.

-   **Format**: `JSON`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/a3dpc/api/occupancy"
```

```bash
GET /a3dpc/api/occupancyHost: <servername>
```

**Sample output**

```bash
{    "occupancy": 15,    "serial": "00:40:8c:18:82:27",    "timestamp": "2020-12-03T16:28:05+01:00",    "total\_in": 100,    "total\_out": 85}
```

### Generic data push

This method should be used when you want to push statistics stored on your Axis camera to HTTPS endpoints using the JSON format .

Please note that the generic data push functionality is configured in the AXIS 3D People Counter application, where the endpoint URL, send time interval and API token (optional) are all specified from the "Reporting" section.

-   **Format**: `JSON`
-   **Method**: `POST`

**Server requirements**

The remote destination must be configured by using HTTPS with a certificate validated by either a public or custom root CA, which must also be installed on your Axis camera in ensure proper encryption of the data. Supported time intervals are 1, 5 and 15 minutes.

**API token**

An API token can be specified for the push and be added to a request via the HTTP header `Authorization: Bearer <token>`

**Sample output**

```bash
{    "apiName": "Axis Retail Data",    "apiVersion": "0.4",    "utcSent": "2020-12-08T12:20:12Z",    "localSent": "2020-12-08T13:20:12",    "data": {        "utcFrom": "2020-12-08T12:19:00Z",        "utcTo": "2020-12-08T12:20:00Z",        "localFrom": "2020-12-08T13:19:00",        "localTo": "2020-12-08T13:20:00",        "measurements": \[            {                "kind": "people-counts",                "utcFrom": "2020-12-08T12:19:00Z",                "utcTo": "2020-12-08T12:20:00Z",                "localFrom": "2020-12-08T13:19:00",                "localTo": "2020-12-08T13:20:00",                "items": \[                    {                        "direction": "in",                        "count": 0,                        "adults": 0                    },                    {                        "direction": "out",                        "count": 0,                        "adults": 0                    }                \]            }        \]    },    "sensor": {        "application": "AXIS 3D People Counter",        "applicationVersion": "10.3",        "timezone": "Europe/Stockholm",        "name": "axis-accc8ef3d92e",        "serial": "accc8ef3d92e",        "ipAddress": "172.25.70.165"    }}
```

| Field | Description |
| --- | --- |
| `apiName` | The API name. |
| `apiVersion` | The version number of the API that is utilized. |
| `utcSent` | The UTC date and time when the data was delivered. |
| `localSent` | The local date and time when the data was delivered. |
| `Data` | An array containing the counting data information. |
| `data[].utcFrom` | The UTC start date and time of the counting data. |
| `data[].utcTo` | The UTC end date and time of the counting data. |
| `data[].localFrom` | The local start date and time of the counting data. |
| `data[].localTo` | The local end date and time of the counting data. |
| `data[].measurements` | An array containing the counting data measurements. |
| `data[].measurements[].kind` | The data type provided by the Axis network camera. |
| `data[].measurements[].utcFrom` | The UTC start date and time of the counting data for a specific time interval. |
| `data[].measurements[].utcTo` | The UTC end date and time of the counting data for a specific time interval. |
| `data[].measurements[].localFrom` | The local start date and time of the counting data for a specific time interval. |
| `data[].measurements[].localTo` | The local end date and time of the counting data for a specific time interval. |
| `data[].measurements[].items` | An array containing the counting data for specific time interval. |
| `data[].measurements[].items[].direction` | The direction of the data recorded during specific time intervals, either in or out. |
| `data[].measurements[].items[].count` | The number of counts recorded during specific time intervals. |
| `data[].measurements[].items[].adults` | The number of adult counts recorded during specific time intervals. |
| `Sensor` | An array containing the sensor specific information. |
| `sensor[].application` | The people counter application type. |
| `sensor[].timeZone` | The selected time zone for the Axis network camera. |
| `sensor[].name` | The device name provided by the application. |
| `sensor[].serial` | The serial number of the Axis network camera. |
| `sensor[].ipAddress` | The IP address of the Axis network camera. |

### Adjust occupancy

This method should be used when you want to manually adjust the real-time estimated occupancy of an area with a new value.

-   **Security level**: Operator

#### Request the target value 0

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/a3dpc.cgi" \\  --data '{    "apiVersion": "1",    "context": "95eb9c7a-5b30-4b78-aafd-eeaec4e87886",    "method": "adjustOccupancy",    "params": {        "occupancy": 0    }}'
```

```bash
POST /axis-cgi/a3dpc.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1",    "context": "95eb9c7a-5b30-4b78-aafd-eeaec4e87886",    "method": "adjustOccupancy",    "params": {        "occupancy": 0    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context` | A text string returned in the corresponding response (optional). |
| `method` | Specifies the method. |
| `params` | Parameter group made to set the estimated occupancy. |
| `occupancy` | The new value for estimated occupancy. |

Response

```bash
{    "apiVersion": "1.0",    "context": "95eb9c7a-5b30-4b78-aafd-eeaec4e87886",    "data": {        "message": "Request received, use the occupancy API to confirm that the changes have taken effect."    },    "method": "adjustOccupancy"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | A text string set by the user in the request (optional). |
| `method` | The requested method. |
| `params` | Parameter group made to set the estimated occupancy. |
| `occupancy` | The new value for estimated occupancy. |

#### Request rejected due to a lack of effect

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/a3dpc.cgi" \\  --data '{    "apiVersion": "1",    "context": "34b296dc-ad63-4988-92c4-fa7928de6014",    "method": "adjustOccupancy",    "params": {        "occupancy": 0    }}'
```

```bash
POST /axis-cgi/a3dpc.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1",    "context": "34b296dc-ad63-4988-92c4-fa7928de6014",    "method": "adjustOccupancy",    "params": {        "occupancy": 0    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context` | A text string returned in the corresponding response (optional). |
| `method` | Specifies the method. |
| `params` | Parameter group made to set the estimated occupancy. |
| `occupancy` | The new value for estimated occupancy. |

Response 1

```bash
{    "apiVersion": "1.0",    "context": "34b296dc-ad63-4988-92c4-fa7928de6014",    "error": {        "code": 1200,        "message": "Device is configured as occupancy secondary, adjust occupancy on primary device."    },    "method": "adjustOccupancy"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | A text string set by the user in the request (optional). |
| `error` | Contains the error information. |
| `code` | The error code. |
| `message` | The error message detailing the corresponding error code. |
| `method` | The requested method. |

**Error codes**

| Code | Description |
| --- | --- |
| `1200` | Device is configured as occupancy secondary, adjust occupancy on primary device. |

Response 2

```bash
{    "apiVersion": "1.0",    "context": "34b296dc-ad63-4988-92c4-fa7928de6014",    "error": {        "code": 1200,        "message": "Occupancy estimation is off, turn it on to use this feature."    },    "method": "adjustOccupancy"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | A text string set by the user in the request (optional). |
| `error` | Contains the error information. |
| `code` | The error code. |
| `message` | The error message detailing the corresponding error code. |
| `method` | The requested method. |

**Error codes**

| Code | Description |
| --- | --- |
| `1200` | Occupancy estimation is off, turn it on to use this feature. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### Restart a passthrough countdown

This method should be used when you want to restart the counting from 0 without emitting any passthrough threshold events.

-   **Security level**: Operator

#### Request is accepted

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/a3dpc.cgi" \\  --data '{    "apiVersion": "1",    "context": "d661abe5-56a4-4284-baff-cc5934091fa6",    "method": "restartPassthroughCountdown"}'
```

```bash
POST /axis-cgi/a3dpc.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1",    "context": "d661abe5-56a4-4284-baff-cc5934091fa6",    "method": "restartPassthroughCountdown"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context` | A text string returned in the corresponding response (optional). |
| `method` | Specifies the method. |

Response

```bash
{    "apiVersion": "1.0",    "context": "d661abe5-56a4-4284-baff-cc5934091fa6",    "data": {},    "method": "restartPassthroughCountdown"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | A text string set by the user in the request (optional). |
| `data` | An array containing the counting data information. |
| `method` | The requested method. |

#### Request is rejected due to a lack of effect

Request

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/a3dpc.cgi" \\  --data '{    "apiVersion": "1",    "context": "f85d0604-db97-4747-9e9b-cdc863957a99",    "method": "restartPassthroughCountdown"}'
```

```bash
POST /axis-cgi/a3dpc.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1",    "context": "f85d0604-db97-4747-9e9b-cdc863957a99",    "method": "restartPassthroughCountdown"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context` | A text string returned in the corresponding response (optional). |
| `method` | Specifies the method. |

Response

```bash
{    "apiVersion": "1.0",    "context": "f85d0604-db97-4747-9e9b-cdc863957a99",    "error": {        "code": 1200,        "message": "Allow passthrough threshold events is turned off."    },    "method": "restartPassthroughCountdown"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context` | A text string set by the user in the request (optional). |
| `error` | Contains the error information. |
| `code` | The error code. |
| `message` | The error message detailing the corresponding error code. |
| `method` | The requested method. |

**Error codes**

| Code | Description |
| --- | --- |
| `1200` | Allow passthrough threshold events is turned off. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

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
| `2107` | Transport level error |

## 3D people counter API (Old version)

info

This API has been deprecated and will no longer receive any updates. Please note that it is not compatible with the AXIS P8815-2 3D People Counter.

### Common examples

Open all statistics that are stored in the camera with a one minute resolution, using a browser.

Request (CSV)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/people-counter/export.csv?export-method=on&date=YYYYMMDD&resolution=60&method=open"
```

```bash
GET /stereo/people-counter/export.csv?export-method=on&date=YYYYMMDD&resolution=60&method=openHost: <servername>
```

See [List download statistics](#list-download-statistics) for more information.

Download statistics that occurred on the 10th of January of 2017.

Request (JSON)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/people-counter/export.json?resolution=day&date=20170110&method=download"
```

```bash
GET /stereo/people-counter/export.json?resolution=day&date=20170110&method=downloadHost: <servername>
```

See [List download statistics](#list-download-statistics) for more information.

### API specification
#### Request real-time data

Returns JSON file with real time counting data.

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/people-counter/counts.json"
```

```bash
GET /stereo/people-counter/counts.jsonHost: <servername>
```

Return

```bash
{    "in": 0,    "name": "Untitled AXIS 3D People Counter",    "out": 0,    "serial": "ACCC8E235294",    "timestamp": "20180115121710"}
```

Return value descriptions

| Value | Description |
| --- | --- |
| `in` | Number of people passing in until now today. |
| `name` | The name of the application, chosen by the client. |
| `out` | Number of people passing out until now. |
| `serial` | The Mac address for the camera. |
| `timestamp` | Time in the camera in the format `YYYYMMDDhhmmss`. |

#### List download statistics

Returns statistics stored in the camera in JSON or plain text comma separated format (CSV)

-   **Format**: CSV or JSON

Request (CSV)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/people-counter/export.csv?resolution=<resolution>&date=<date>&method=<method>"
```

```bash
GET /stereo/people-counter/export.csv?resolution=<resolution>&date=<date>&method=<method>Host: <servername>
```

Request (JSON)

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/people-counter/export.json?resolution=<resolution>&date=<date>&method=<method>"
```

```bash
GET /stereo/people-counter/export.json?resolution=<resolution>&date=<date>&method=<method>Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `<date>` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` (default) for all available data |
| `<resolution>` | `minute` for data in 1 minute bins |
|  | `hour` for data in 1 hour bins |
|  | `day` for data in 1 day bins |
|  | `60` for data in 1 minute bins |
|  | `3600` for data in 1 hour bins |
|  | `86400` for data in 1 day bins |
| `<method>` | select `open` to list the statistics in a web browser |
|  | select `download` to download the JSON or CSV file |

**Return**

Returns statistics stored in the camera in JSON or plain text comma separated format (CSV). The first line of the CSV file contains a description of each element, and the following lines contain the corresponding data for the chosen time interval and resolution: `Interval Start, Interval Start (Unixtime), In, Out`

#### List frame rate

Returns the current internal frame rate

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/fps.json"
```

```bash
GET /stereo/fps.jsonHost: <servername>
```

Return

```bash
{  "fps": real time fps,  "fps\_100": average FPS for the last 100 frames,  "fps\_1000": average FPS for the last 1000 frames,  "fps\_5": average FPS for the last 5 frames,  "fps\_50": average FPS for the last 50 frames,  "frames": frame counter.}
```

#### I/O interface

Get the latest I/O signals as `false` or `true`.

-   **Format**: JSON

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/io.json"
```

```bash
GET /stereo/io.jsonHost: <servername>
```

Return

```bash
"True" or "False"
```

#### List parameters

Get all parameters currently set.

-   **Format**: JSON

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/stereo/params.json"
```

```bash
GET /stereo/params.jsonHost: <servername>
```

**Return**

A JSON object of all the parameters currently set.