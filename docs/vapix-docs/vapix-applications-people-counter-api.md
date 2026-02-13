---
title: People counter API
url: "https://developer.axis.com/vapix/applications/people-counter-api/"
category: vapix
subcategory: applications
sha256: 623bc2b0eed83218d1eb37710709adf18e0a15e410b692b13b9f4767099047f0
scraped_at: "2026-01-09T15:01:24.111Z"
page_height: 17905
---

# People counter API

AXIS People Counter is an application accessible on your indoor Axis camera that provides simultaneous two-way counting of people, which lets you analyze visitor trends such as peak visitor hours. It is also able to estimate occupancy levels in real-time and provide access to data on the number of people present on either the premises or in a certain area at a certain time. This is helpful when you want to understand occupancy trends that enables you to measure if the occupancy levels exceed a set threshold.

Additionally, the application can detect and notify if more than one person enters within a set time interval or move in the wrong direction. This means that if you set up the application over a one-way entrance you will receive a notification whenever someone tries to leave or if more than one person tries to enter at the same time.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Request real time data from the People Counter

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?live-sum.json"
```

```bash
GET /local/tvpc/.api?live-sum.jsonHost: <servername>
```

Return

```bash
{    "serial": "00408CAC512B",    "name": "Exit south",    "timestamp": "20170503112756",    "in": 12,    "out": 318}
```

See [Request real-time data](#request-real-time-data) for additional information.

### List all days of data available on the People Counter

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?list-cnt.json"
```

```bash
GET /local/tvpc/.api?list-cnt.jsonHost: <servername>
```

Return

```bash
{    "timestamp": "20170513132513",    "days": \["20170510", "20170511", "20170513"\]}
```

See [List available data](#list-available-data) for additional information.

### Request historical data for the 12th to the 15th of May 2017

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-cnt&date=20170512-20170515"
```

```bash
GET /local/tvpc/.api?export-cnt&date=20170512-20170515Host: <servername>
```

See [Download binary data](#download-binary-data) for additional information.

### Request all available historical data

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-cnt&date=all"
```

```bash
GET /local/tvpc/.api?export-cnt&date=allHost: <servername>
```

See [Download binary data](#download-binary-data) for additional information.

### Request historical CSV data for the 12th and the 15th of May 2017 with 15-minute resolution

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-csv&date=20170512,20170515&res=15m"
```

```bash
GET /local/tvpc/.api?export-csv&date=20170512,20170515&res=15mHost: <servername>
```

See [Request CSV data](#request-csv-data) for additional information.

### Request historical data for all available days, with 24-hour resolution

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-csv&date=all&res=24h"
```

```bash
GET /local/tvpc/.api?export-csv&date=all&res=24hHost: <servername>
```

See [Request CSV data](#request-csv-data) for additional information.

### Request historical XML data for the 12th and the 15th of May 2017 with 15-minute resolution

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-xml&date=20170512,20170515&res=15m"
```

```bash
GET /local/tvpc/.api?export-xml&date=20170512,20170515&res=15mHost: <servername>
```

See [Request XML data](#request-xml-data) for additional information.

### Request Live view information from the People Counter

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?cntpos.json"
```

```bash
GET /local/tvpc/.api?cntpos.jsonHost: <servername>
```

Response

```bash
{    "width": 320,    "height": 240,    "left": 0,    "right": 296,    "top": 88,    "bottom": 224,    "yfirst": 88,    "ylast": 152,    "radius": 0}
```

See [Live view information](#live-view-information) for additional information.

## API specification
### Request real-time data

Returns JSON file with real time counting data.

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?live-sum.json"
```

```bash
GET /local/tvpc/.api?live-sum.jsonHost: <servername>
```

Return

```bash
{  "serial":"<camera-serial>",  "name":"<counter-name>",  "timestamp":"<timestamp>",  "in":<in>,  "out":<out>}
```

Return value descriptions

| Value | Description |
| --- | --- |
| `camera-serial` | camera serial number |
| `counter-name` | name of the counter |
| `timestamp` | time in the camera in the format `YYYYMMDDhhmmss` |
| `in` | number of people passing in until now today |
| `out` | number of people passing out until now |

### List available data

Returns a list of days where data exists.

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?list-cnt.json"
```

```bash
GET /local/tvpc/.api?list-cnt.jsonHost: <servername>
```

Return

```bash
{  "timestamp" : "<timestamp>",  "days":\["YYYYMMDD", \[..\] "YYYYMMDD"\]}}
```

Return value descriptions

| Value | Description |
| --- | --- |
| `timestamp` | time in the camera in the format `YYYYMMDDhhmmss` |
| `days` | an array of days where there exists |

### Download binary data

This script returns a binary data file for the given date(s), to be used in AXIS Store Data Manager

-   **Format**: cnt

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-cnt&date=<date>"
```

```bash
GET /local/tvpc/.api?export-cnt&date=<date>Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `date` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` for all available data |

**Return**

A binary data file for the given date(s).

### Request CSV data

Returns historical data in CSV format

-   **Format**: CSV

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-csv\[&date=<date>\]\[&res=<res>\]"
```

```bash
GET /local/tvpc/.api?export-csv\[&date=<date>\]\[&res=<res>\]Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `date` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` (default) for all available data |
| `res` | `15m` (default) for data in 15 minute bins |
|  | `1h` for data in 1 hour bins |
|  | `24h` for data in 1 day bins |

**Return**

This script returns data in plain text, comma-separated values. The first line contains a description of each element, and the following lines contain the corresponding data for the chosen time interval and resolution.

### Request JSON data

Returns historical data in JSON format

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-json\[&date=<date>\]\[&res=<res>\]"
```

```bash
GET /local/tvpc/.api?export-json\[&date=<date>\]\[&res=<res>\]Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `date` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` (default) for all available data |
| `res` | `15m` (default) for data in 15 minute bins |
|  | `1h` for data in 1 hour bins |
|  | `24h` for data in 1 day bins |

**Return**

This script returns data in JSON format.

### Request XML data

Returns historical data in XML format

-   **Format**: XML

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?export-xml\[&date=<date>\]\[&res=<res>\]"
```

```bash
GET /local/tvpc/.api?export-xml\[&date=<date>\]\[&res=<res>\]Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `date` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` (default) for all available data |
| `res` | `15m` (default) for data in 15 minute bins |
|  | `1h` for data in 1 hour bins |
|  | `24h` for data in 1 day bins |

**Return**

This script returns data in XML format. The DTD file can be found at: `http://<servername>/local/tvpc/appdata.dtd`

### Clear counting data

-   **Format**: text/plain

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.apioperator?clear-data"
```

```bash
GET /local/tvpc/.apioperator?clear-dataHost: <servername>
```

Return

```bash
OK
```

info

Please note that this method will permanently delete all counting data from your device.

### Live view information

Returns information about the placement of the lines in Live view.

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?cntpos.json"
```

```bash
GET /local/tvpc/.api?cntpos.jsonHost: <servername>
```

Response

```bash
{  "width":<width>,  "height":<height>,  "left":<left>,  "right":<right>,  "top":<top>,  "bottom":<bottom>,  "yfirst":<yfirst>,  "ylast":<ylast>,  "radius":<radius>}
```

Return value descriptions

| Value | Description |
| --- | --- |
| `width` | dimension of the video stream |
| `height` |  |
| `left` | x coordinates in pixels forstart and stop for the blue lines in Live view |
| `right` |  |
| `top` | y coordinates in pixels for the two blue lines in Live view |
| `bottom` |  |
| `yfirst` | y coordinates in pixels for the top and bottom of the red counting area, disregarding curvature |
| `ylast` |  |
| `radius` | radius in pixels describing the curvature of the red counting area, as measured in the center of the area on both axes, or if the area is not curved |

### Show the system log

-   **Format**: text/plain

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.apioperator?show-logs"
```

```bash
GET /local/tvpc/.apioperator?show-logsHost: <servername>
```

**Return**

Displays the system logs.

### Generate a log archive

-   **Format**: tar.gz

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.apioperator?generate-logs"
```

```bash
GET /local/tvpc/.apioperator?generate-logsHost: <servername>
```

**Return**

A log archive

### List people counter parameters

-   **Format**: JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?params.json"
```

```bash
GET /local/tvpc/.api?params.jsonHost: <servername>
```

**Return**

A JSON object of all the People Counter related parameters.

### Set people counter parameters

-   **Format**: text

The post format has a format where pairs and values need to be specified, best described by an example: `&p1=Counter.Enable&v1=1&p2=Counter.Height&v2=280&setparams=needstobeincluded`

info

For AXIS OS version 5.60 and later, use: setparams&Counter.Height=280 instead.

Request

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.apioperator?setparams"
```

```bash
POST /local/tvpc/.apioperator?setparamsHost: <servername>
```

Return

```bash
OK
```

## Occupancy data

The occupancy data requests fetches the total number of people entering or leaving a location and their average visit time.

info

Please note that occupancy data must be enabled in the settings page to be able to perform the requests listed in this section.

### Request

Request historical data for all available days and a 24–hour resolution.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/tvpc/.apioperator?occupancy-export-json&date=all&res=24h"
```

```bash
GET /tvpc/.apioperator?occupancy-export-json&date=all&res=24hHost: <servername>
```

### Response

```bash
{    "counter": {        "name": "Axis-ACCC8E019C5F",        "serial": "ACCC8E019C5F",        "delta": 86400,        "types": {            "Occupancy": 64,            "Average Time": 64,            "Total In": 66,            "Total Out": 67        }    },    "data": {        "20170908000000": \[0, 0, 17, 17\],        "20170909000000": \[0, 0, 18, 17\],        "20170910000000": \[0, 0, 1, 0\],        "20170911000000": \[0, 0, 0, 0\],        "20170912000000": \[0, 0, 21, 15\]    }}
```

| Parameter | Description |
| --- | --- |
| `name` | The name of the application, chosen by the client. |
| `serial` | The Mac address for the camera. |
| `delta` | The time difference between `data` entries, measured in seconds. |
| `Occupancy` | The number of people currently in the location. |
| `Average time` | Average time a person is staying in a location. |
| `Total In` | Total number of people entering a location. |
| `Total Out` | Total number of people leaving a location. |

### API specification
#### Real-time data

Request a JSON file with the real time occupancy data.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/tvpc/.api?live-occupancy.json"
```

```bash
GET /tvpc/.api?live-occupancy.jsonHost: <servername>
```

#### Reset occupancy

Request a reset of the available occupancy data.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/tvpc/.api?occupancy-reset&occ=\[value\]"
```

```bash
GET /tvpc/.api?occupancy-reset&occ=\[value\]Host: <servername>
```

info

Please note that this method only works while the people counter is set to naïve mode. See the user manual for [AXIS People Counter](https://help.axis.com/axis-people-counter#smart-and-nave-occupancy-mode) for additional information.

#### Export occupancy

Export the occupancy data by specifying a date and time frame using either the CSV, JSON or XML-format.

CSV

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?occupancy-export-csv&date=<date>&res=<res>"
```

```bash
GET /local/tvpc/.api?occupancy-export-csv&date=<date>&res=<res>Host: <servername>
```

JSON

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?occupancy-export-json&date=<date>&res=<res>"
```

```bash
GET /local/tvpc/.api?occupancy-export-json&date=<date>&res=<res>Host: <servername>
```

XML

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/tvpc/.api?occupancy-export-xml&date=<date>&res=<res>"
```

```bash
GET /local/tvpc/.api?occupancy-export-xml&date=<date>&res=<res>Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `<date>` | A date in the form `YYYYMMDD`, for example `date=20180520` |
| `<res>` | `1m` for data in 1 minute bins. |
|  | `15m` for data in 15 minute bins. |
|  | `1h` for data in 1 hour bins. |
|  | `24h` for data in 24 hour bins. |