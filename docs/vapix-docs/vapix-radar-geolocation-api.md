---
title: Geolocation API
url: "https://developer.axis.com/vapix/radar/geolocation-api/"
category: vapix
subcategory: radar
sha256: 92e0ce02c2214ff7f04f0d0eb58d7de6c068c4fbc5d54a4f8dcc2acc7a120e0f
scraped_at: "2026-01-09T15:22:00.485Z"
page_height: 15292
---

# Geolocation API

The VAPIX® Geolocation API provides the information that makes it possible to use position and orientation data on an Axis device.

The Position API provides the information that makes it possible to set up and check the position of a device. Position is specified in latitude, longitude and a free text field. The latitude and longitude coordinates should be in the WGS-84 format. Supported formats are DD, DMS and DMM, however no conversions will be done. The output format is always the same as the input format.

Position API functions

| Function | Usage |
| --- | --- |
| `/axis-cgi/geolocation/set.cgi` | Set position |
| `/axis-cgi/geolocation/get.cgi` | Get position |

The Orientation API provides the information that makes it possible to set up and use the orientation capabilities of a device. Orientation is specified by a heading, installation height, tilt and a roll field. The output format is always the same as the input format.

Orientation API functions

| Function | Description |
| --- | --- |
| `geoorientation` | Set and get the orientation. |

## Overview

The Position API consists of 2 interfaces. One is used to query for all the data and one for updating either some or all of the fields.

The Orientation API consists of 1 interface where get/set is chosen by the parameter `action`.

### Identification

**Position API**

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Geolocation.Geolocation=yes`
-   **Property**: `Properties.Geolocation.Version=0.01`
-   **AXIS OS**: 6.25 and later

**Orientation API**

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.Geoorientation.Geoorientation=yes`
-   **Property**: `Properties.Geoorientation.Version=0.01`
-   **AXIS OS**: 11.5 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Format

Annex H of the ISO-6709 standard is used to set and read geographical positions. ISO-6709 is an international standard that represents latitude, longitude and altitude for geographical point locations.

All of the device rotations described by the orientation CGI are extrinsic, which means that they are independently described.

### Signs

-   North latitude and East longitude are positive (+).
-   South latitude and West longitude are negative (-).
-   The values 0.0 0.0 (lat/long) are valid data for a device residing in the Gulf of Guinea. When no geographical position data is available, or the current data for a moving device is outdated, the parameter `ValidPosition` should be set to `false`. Meanwhile, `ValidPosition` should be `true` for valid geographical position data.

### Unit types

There exists three types of representation for representing the position that is currently supported:

-   DD - degrees
-   DDMM - degrees/minutes
-   DDMMSS - degrees/minutes/seconds

#### Degrees (DD)

The position is only given in whole and decimal degrees. The integer part is of fixed length, using 2 digits (-90 to +90 degrees) for latitude and 3 digits (-180 to +180 degrees) for longitude. The number of digits indicates the units, which means that leading zero(es) must be filled when necessary. The fractional part must have the appropriate number of digits to represent the required precision of the coordinate.

Example latitude

```bash
33.55555 to 33.55555 degrees+33.5555 to 33.5555 degrees-45.5555 to -45.5555 degrees03.55555 to 3.55555 degrees
```

Example longitude

```bash
013.55555 to 13.55555 degrees+013.5555 to 13.5555 degrees-110.5555 to -110.5555 degrees002.55555 to 2.55555 degrees
```

#### Degrees/Minutes (DDMM)

The position is given in whole degrees as well as whole and decimal minutes. The integer part is of a fixed length with 4 digits (-90 to +90 degrees and 0 to 60 minutes) for latitude and 5 digits (-180 to +180 degrees and 0 to 60 minutes) for longitude. The number of digits indicates the units, which means that leading zero(es) must be filled when necessary.

Example latitude

```bash
3312.55555 to 33 degrees, 12.55555 minutes+3312.5555 to 33 degrees, 12.5555 minutes-4512.5555 to -45 degrees 12.5555 minutes0300.55555 to 3 degrees, 0.55555 minutes
```

Example longitude

```bash
01322.55555 to 13 degrees, 22.55555 minutes+01322.5555 to 13 degrees, 22.5555 minutes-11022.5555 to -110 degrees, 22.5555 minutes00200.55555 to 2 degrees, 0.55555 minutes
```

#### Degrees/Minutes/Seconds (DDMMSS)

The position is given in whole degrees, whole minutes and decimal seconds. The integer part is of a fixed length at 6 digits (-90 to +90 degrees, 0 to 60 minutes and 0 to 60 seconds) for latitude and 7 digits (-180 to +180 degrees, 0 to 60 minutes and 0 to 60 seconds) for longitude. The number of digits indicates the units, which means that leading zero(es) must be filled when necessary.

Example latitude

```bash
223312.55555 to 22 degrees, 33 minutes, 12.55555 seconds+223312.5555 to 22 degrees, 33 minutes, 12.5555 seconds-334512.5555 to -33 degrees, 45 minutes, 12.5555 seconds000300.55555 to 0 degrees, 3 minutes, 0.55555 seconds
```

Example longitude

```bash
0134422.55555 to 13 degrees, 44 minutes, 22.55555 seconds+0134422.5555 to 13 degrees, 44 minutes, 22.5555 seconds-1410022.5555 to -141 degrees, 0 minutes, 22.5555 seconds0020500.55555 to 2 degrees, 5 minutes, 0.55555 seconds
```

#### Heading

The heading indicates the direction of the device in degrees and valid values are integers between 0 and 360 where 0 degrees corresponds to the North direction.

Example

```bash
heading=90 - the device is rotated 90 degrees from North and pointing Eastheading=270 - the device is pointing West
```

When no valid heading data is available, or the heading data for a moving device has become outdated, the parameter `ValidHeading` should be set to `false`.

#### Installation height

Installation height measures the height from the floor and up to the device in meters.

_Example_

```bash
height = 2.2: The device is installed 2.2 meters above the floor.
```

#### Tilt

Tilt indicates the angle of a device in degrees. Valid values range from -180 to +180, which means that the device will be pointed towards the horizon at 0 degrees.

_Example_

```bash
tilt = 0: The device is pointing towards the horizon.tilt = 90: The device is pointing straight up.tilt = -90: The device is pointing straight down.
```

#### Roll

Roll indicates the rotation level of a device in degrees. Valid values range from -180 to +180, which means that the device will be aligned with the horizon at 0 degrees.

_Example_

```bash
roll = 0: The device is aligned with the horizon.roll = 90: The device is rotated 90 degrees to the right, with its left side pointing down and its right side pointing up.roll = ±180: The device is inverted, with its top pointing down and its bottom pointing up.roll = -90: The device is rotated 90 degrees to the left, with its right side pointing down and its left side pointing up.
```

## Common examples
### Get complete position data

Use this example to locate the device as well as to get its position data in order to make a map for all installed devices.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/get.cgi"
```

```bash
GET /axis-cgi/geolocation/get.cgiHost: <servername>
```

1.  Parse the response

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GetSuccess>            <Location>                <Lat>51.0</Lat>                <Lng>-0.1</Lng>                <Heading>30</Heading>            </Location>            <Text>Free text</Text>            <ValidPosition>true</ValidPosition>            <ValidHeading>false</ValidHeading>        </GetSuccess>    </Success></PositionResponse>
```

### Retrieve complete orientation data

This example will show you how to apply available orientation data. This include checking the device orientation to calculate depth in either the image or correlate a device image to a real world space.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geoorientation/geoorientation.cgi?action=get"
```

```bash
GET /axis-cgi/geoorientation/geoorientation.cgi?action=getHost: <servername>
```

1.  Parse the response.

```bash
<OrientationResponse SchemaVersion="1.0">    <Success>        <GetSuccess>            <Tilt>70.0</Tilt>            <InstallationHeight>3.2</InstallationHeight>            <Heading>140.0</Heading>            <ValidTilt>True</ValidTilt>            <ValidInstallationHeight>True</ValidInstallationHeight>            <ValidHeading>True</ValidHeading>        </GetSuccess>    </Success></OrientationResponse>
```

### Set position

Use this example to get position data from an external source in order to set location data for a device. External sources include, but are not limited to, GPS and Mobile phones.

**Set position using DD units**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/set.cgi?lat=51.1234&lng=013.1234&heading=30&text="freetext""
```

```bash
GET /axis-cgi/geolocation/set.cgi?lat=51.1234&lng=013.1234&heading=30&text="freetext"Host: <servername>
```

1.  Receive response

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></PositionResponse>
```

**Set position using DDMM units**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/set.cgi?lat=5112.3456&lng=01312.3456&heading=30&text="freetext""
```

```bash
GET /axis-cgi/geolocation/set.cgi?lat=5112.3456&lng=01312.3456&heading=30&text="freetext"Host: <servername>
```

1.  Receive response

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></PositionResponse>
```

**Set position using DDMMSS units**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/set.cgi?lat=511234.5678&lng=0131234.5678&heading=30&text="free text""
```

```bash
GET /axis-cgi/geolocation/set.cgi?lat=511234.5678&lng=0131234.5678&heading=30&text="free text"Host: <servername>
```

1.  Receive response

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></PositionResponse>
```

### Set location tag

Use this example to set location tags from an external source in order to distinguish between two devices in the same location but on different floors.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/set.cgi?lat=51.0&lng=-0.1&text="floor 2""
```

```bash
GET /axis-cgi/geolocation/set.cgi?lat=51.0&lng=-0.1&text="floor 2"Host: <servername>
```

1.  Receive response

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></PositionResponse>
```

### Set orientation

This example will show you how to set the orientation data on a device and improve image depth calculations.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geoorientation/geoorientation.cgi?action=set&heading=30.0&inst\_height=2.3&tilt=-80.0"
```

```bash
GET /axis-cgi/geoorientation/geoorientation.cgi?action=set&heading=30.0&inst\_height=2.3&tilt=-80.0Host: <servername>
```

1.  Parse the response.

```bash
<OrientationResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></OrientationResponse>
```

## API specification
### position/get

Get position information.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/get.cgi"
```

```bash
GET /axis-cgi/geolocation/get.cgiHost: <servername>
```

**Return value - Success**

Returns latitude, longitude and direction.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GetSuccess>            <Location>                <Lat>51.0</Lat>                <Lng>-0.1</Lng>                <Heading>30</Heading>            </Location>            <Text>Free text</Text>            <ValidPosition>true</ValidPosition>            <ValidHeading>true</ValidHeading>        </GetSuccess>    </Success></PositionResponse>
```

**Return value - Error**

0 and empty string are default values and will be returned if nothing is set.

### position/set

Set new position information.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geolocation/set.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/geolocation/set.cgi?<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `lat=latitude` | New value for latitude. |
| `lng=longitude` | New value for longitude. |
| `text=text` | New value for free text. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<PositionResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></PositionResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<PositionResponse SchemaVersion="1.0">    <Error>        <SetError>            <ErrorCode>1</ErrorCode>            <ErrorDescription>Invalid parameter</ErrorDescription>            <ErrorCode>2</ErrorCode>            <ErrorDescription>Invalid value</ErrorDescription>            <ErrorCode>3</ErrorCode>            <ErrorDescription>Internal Error</ErrorDescription>        </SetError>    </Error></PositionResponse>
```

### orientation/get

Get orientation information.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geoorientation/geoorientation.cgi?action=get"
```

```bash
GET /axis-cgi/geoorientation/geoorientation.cgi?action=getHost: <servername>
```

**Return value - Success**

Returns tilt angle, installation height and heading.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<OrientationResponse SchemaVersion="1.0">    <Success>        <GetSuccess>            <Tilt>60.0</Tilt>            <InstallationHeight>2.2</InstallationHeight>            <Heading>90.0</Heading>            <ValidTilt>true</ValidTilt>            <ValidInstallationHeight>true</ValidInstallationHeight>            <ValidHeading>true</ValidHeading>        </GetSuccess>    </Success></OrientationResponse>
```

**Return value - Error**

0 and false are default values and will be returned if nothing is set.

### orientation/set

Set new orientation information.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET/POST`

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/geoorientation/geoorientation.cgi?action=set&<argument>=<data>\[&<argument>=<data>\[&...\]\]"
```

```bash
GET /axis-cgi/geoorientation/geoorientation.cgi?action=set&<argument>=<data>\[&<argument>=<data>\[&...\]\]Host: <servername>
```

| Parameter | Description |
| --- | --- |
| `tilt=tilt` | New value for tilt. |
| `heading=heading` | New value for heading. |
| `inst_height=installation height` | New value for installation height. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<OrientationResponse SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></OrientationResponse>
```

**Return value - Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/xml`

Response body syntax:

```bash
<OrientationResponse SchemaVersion="1.0">    <Error>        <SetError>            <ErrorCode>1</ErrorCode>            <ErrorDescription>Invalid parameter</ErrorDescription>            <ErrorCode>2</ErrorCode>            <ErrorDescription>Invalid value</ErrorDescription>            <ErrorCode>3</ErrorCode>            <ErrorDescription>Internal Error</ErrorDescription>        </SetError>    </Error></OrientationResponse>
```