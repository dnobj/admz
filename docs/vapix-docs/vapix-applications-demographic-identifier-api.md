---
title: Demographic identifier API
url: "https://developer.axis.com/vapix/applications/demographic-identifier-api/"
category: vapix
subcategory: applications
sha256: 38c04c037abe3787927f7da6822ae33b3c777637400e204ddef200405746c6e8
scraped_at: "2026-01-09T15:01:09.307Z"
page_height: 11166
---

# Demographic identifier API

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Get live tracks

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-live.json"
```

```bash
GET /local/demographics/.api?tracks-live.jsonHost: <servername>
```

Return (example) - No active track found

```bash
{    "live": {        "tracks": \[\]    }}
```

Return (example) - One active track found

```bash
{    "live": {        "tracks": \[            {                "time\_start": 1447749079.091622,                "time\_end": 1447749081.011605,                "gender\_average": 1,                "age\_average": 20,                "boxsize\_average": 177,                "gender\_last": 1,                "age\_last": 21,                "boxsize\_last": 180            }        \]    }}
```

Return (example) - Two active tracks found

```bash
{    "live": {        "tracks": \[            {                "time\_start": 1447749104.451576,                "time\_end": 1447749109.451567,                "gender\_average": 1,                "age\_average": 20,                "boxsize\_average": 198,                "gender\_last": 1,                "age\_last": 18,                "boxsize\_last": 195            },            {                "time\_start": 1447749107.811568,                "time\_end": 1447749109.451567,                "gender\_average": -1,                "age\_average": 21,                "boxsize\_average": 160,                "gender\_last": -1,                "age\_last": 23,                "boxsize\_last": 158            }        \]    }}
```

### Get ended tracks

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-ended.json"
```

```bash
GET /local/demographics/.api?tracks-ended.jsonHost: <servername>
```

Return (example) - No active track found

```bash
{    "ended": {        "time\_start": 1447748743.039911,        "time\_end": 1447749643.039911,        "tracks": \[\]    }}
```

Return (example) - One ended track found

```bash
{    "ended": {        "time\_start": 1447749887.539835,        "time\_end": 1447749947.539835,        "tracks": \[            {                "time\_start": 1447749942.930319,                "time\_end": 1447749946.210321,                "gender\_average": 1,                "age\_average": 21,                "boxsize\_average": 219            }        \]    }}
```

Return (example) - Two ended tracks found

```bash
{    "ended": {        "time\_start": 1447750011.470372,        "time\_end": 1447750071.470372,        "tracks": \[            {                "time\_start": 1447750064.890142,                "time\_end": 1447750067.690133,                "gender\_average": 1,                "age\_average": 22,                "boxsize\_average": 217            },            {                "time\_start": 1447750066.130135,                "time\_end": 1447750067.690133,                "gender\_average": -1,                "age\_average": 18,                "boxsize\_average": 192            }        \]    }}
```

### Get live and ended tracks

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-live-and-ended.json&time=60"
```

```bash
GET /local/demographics/.api?tracks-live-and-ended.json&time=60Host: <servername>
```

Return (example) - Two Live and one Ended track

```bash
{    "live": {        "tracks": \[            {                "time\_start": 1447750516.809464,                "time\_end": 1447750523.329454,                "gender\_average": 1,                "age\_average": 19,                "boxsize\_average": 218,                "gender\_last": 1,                "age\_last": 19,                "boxsize\_last": 218            },            {                "time\_start": 1447750521.569459,                "time\_end": 1447750523.329454,                "gender\_average": -1,                "age\_average": 17,                "boxsize\_average": 222,                "gender\_last": 260,                "age\_last": 19,                "boxsize\_last": 217            }        \]    },    "ended": {        "time\_start": 1447750463.936758,        "time\_end": 1447750523.936758,        "tracks": \[            {                "time\_start": 1447750514.24947,                "time\_end": 1447750515.329465,                "gender\_average": 1,                "age\_average": 20,                "boxsize\_average": 239            }        \]    }}
```

## API specification
### Get live tracks

This API returns live face tracks (boxes), currently active in the video stream.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-live.json"
```

```bash
GET /local/demographics/.api?tracks-live.jsonHost: <servername>
```

#### Response

See [Common examples](#common-examples) for return examples.

Return value descriptions

| Value | Description |
| --- | --- |
| `<time_start>` | Time of the first face observation in seconds in form of UTC (Coordinated Universal Time) |
| `<time-end>` | Time of the last face observation in seconds. |
| `<gender_average>` | `-1` for female estimate and `1` for male estimate on average since `<time_start>`. |
| `<age_average>` | Estimated age over the track since `<time_start>`. |
| `<boxsize_average>` | Average box size over the track since `<time_start>`. |
| `<gender_last>` | `-1` for female guess and `1` for male guess on last observation. |
| `<age_last>` | Estimated age on last observation. |
| `<boxsize_last>` | Boxsize on last observation. |

### Get ended tracks

This API returns previously detected (ended) tracks.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-ended.json&<time>"
```

```bash
GET /local/demographics/.api?tracks-ended.json&<time>Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `<time>` | Use `time` to adjust the amount of time (in seconds) to include in the return. The default value is 15 minutes. |

#### Response

See [Common examples](#common-examples) for return examples.

Return value descriptions

| Value | Description |
| --- | --- |
| `<time_start>` | Time of the first face observation in seconds in form of UTC (Coordinated Universal Time) |
| `<time-end>` | Time of the last face observation in seconds. |
| `<gender_average>` | `-1` for female estimate and `1` for male estimate on average since `<time_start>`. |
| `<age_average>` | Estimated age over the track since `<time_start>`. |
| `<boxsize_average>` | Average box size over the track since `<time_start>`. |

### Get live and ended tracks

This API combines the Live API described in [Get live tracks](#get-live-tracks-common-examples), and the Ended API described in [Get ended tracks](#get-ended-tracks-common-examples). It returns both live information, as well as ended tracks.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?tracks-live-and-ended.json"
```

```bash
GET /local/demographics/.api?tracks-live-and-ended.jsonHost: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `<time>` | Use `time` to adjust the amount of time (in seconds) to include in the return. The default value is 15 minutes. |

#### Response

See [Common examples](#common-examples) for return examples.

Return value descriptions

| Value | Description |
| --- | --- |
| `<time_start>` | Time of the first face observation in seconds in form of UTC (Coordinated Universal Time) |
| `<time_end>` | Time of the last face observation in seconds. |
| `<gender_average>` | `-1` for female estimate and `1` for male estimate on average since `<time_start>`. |
| `<age_average>` | Estimated age over the track since `<time_start>`. |
| `<boxsize_average>` | Average box size over the track since `<time_start>`. |
| `<gender_last>` | `-1` for female guess and `1` for male guess on last observation. |
| `<age_last>` | Estimated age on last observation. |
| `<boxsize_last>` | Boxsize on last observation. |

### Get FPS

This API checks the FPS used by the Demographics algorithm.

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/demographics/.api?fps.json"
```

```bash
GET /demographics/.api?fps.jsonHost: <servername>
```

#### Response

```bash
200 OKContent-Type: application/json{  "fps": <fps>}
```

### Restart service

Restarts the Demographics service

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/demographics/.apioperator?restart"
```

```bash
GET /demographics/.apioperator?restartHost: <servername>
```

### Reboot the camera

Reboots the camera

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/demographics/.apioperator?reboot"
```

```bash
GET /demographics/.apioperator?rebootHost: <servername>
```

### Get statistics

Returns historical data in JSON format

#### Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/local/demographics/.api?export-json\[&date=<date>\]\[&res=<res>\]"
```

```bash
GET /local/demographics/.api?export-json\[&date=<date>\]\[&res=<res>\]Host: <servername>
```

Request parameter descriptions

| Parameter | Description |
| --- | --- |
| `<date>` | a date of the form `YYYYMMDD` |
|  | a date interval of the form `YYYYMMDD-YYYYMMDD` |
|  | comma separated dates of the form `YYYYMMDD,[..],YYYYMMDD` |
|  | `all` (default) for all available data |
| `<res>` | `15m` (default) for data in 15 minute bins |
|  | `1h` for data in 1 hour bins |
|  | `24h` for data in 1 day bins |

#### Response

This script returns data in JSON format.