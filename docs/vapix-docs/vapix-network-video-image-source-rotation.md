---
title: Image source rotation
url: "https://developer.axis.com/vapix/network-video/image-source-rotation/"
category: vapix
subcategory: network-video
sha256: c86189a6785f20d7691ed2e5a00954016523ff7ab8b14fe0d0ee943e122e3b18
scraped_at: "2026-01-09T15:19:58.309Z"
page_height: 6703
---

# Image source rotation

## Description

Image source rotation is a feature employed to improve performance in hardware. The rotation is set to be handled when the dataflow is already in the sensor, making all streams derived from the source being rotated in the same way.

Historically, Axis products received a native stream with a default rotation value where each video source were able to have their own user-defined rotation value. This means that if the native rotation was 0 degrees internally, the outgoing video stream could show up at either 90 or 180 degrees instead, but only as long as they had been appropriately configured. This does not hold true for newer products with auto-rotation, as they use global parameters to control the rotation of the image source. Thus, depending on what has been globally set, the video source and video stream will both have a defined rotation value, making it impossible to request a video stream with a certain rotation value when it differs from the global configuration value.

info

This API is not a stand alone API but an addendum to `/axis-cgi/param.cgi` found here: [Parameter management](/vapix/network-video/parameter-management/).

The API consists of the following parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `ImageSource.I#.SourceRotation` | `yes` `no` | Allows the client to determine whether or not a given product has image source rotation. This parameter is read-only. |
| `Properties.Image.Rotation` | `[0, 90, 180, 270]` | The rotation of the source. |
| `ImageSource.I#.AutoRotationEnabled` | `yes` `no` | In products with `AutoRotation` it is possible to activate it by setting `ImageSource.I#.AutoRotationEnabled` to ‘`yes`’. `AutoRotationEnabled` can be disabled by setting `Rotation`. |

### Identification

-   **Property**: `ImageSource.I#.SourceRotation=yes`
-   **AXIS OS**: 8.40 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Image source rotation

Use this example to determine if a stream or a source should be rotated.

**Query**

-   Check if Image source rotation is present in the device by querying `ImageSource.I#.SourceRotation`. If the value is `yes` and a rotation value is set, Image source rotation is present.

For more information, see [API specification](#api-specification).

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=list&group=ImageSource.I0"
```

```bash
GET /axis-cgi/param.cgi?action=list&group=ImageSource.I0Host: <servername>
```

**Return value - Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
...root.ImageSource.I0.SourceRotation=yesroot.ImageSource.I0.Rotation=180...
```

**Return value:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
Neither ImageSource.I0SourceRotation nor Rotation in body.
```

**Update**

-   Set `ImageSource.I#.Rotation` to a desired rotation angle from the set as defined by `Properties.Image.Rotation`, e.g `[0,90,180,270]`.
-   If `ImageSource.I#.Rotation` is changed all open streams will close, and must be reacquires in a new stream request.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&ImageSource.I0.Rotation=0"
```

```bash
GET /axis-cgi/param.cgi?action=update&ImageSource.I0.Rotation=0Host: <servername>
```

**Return value - Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
OK
```

**Return value - Not present:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
# Error: Error setting 'ImageSource.I#.Rotation' to 'nnn'!
```

### Auto rotation

Use this example to operate Image source rotation together with Auto rotation and restart all streams after changing the orientation.

**Query**

After checking the status of Image source rotation in the previous example, you can now check if Auto rotation is present and if it has been enabled.

-   Query the value of `ImageSource.I#.AutoRotationEnabled`, and if the returned value is `yes`, Auto rotation is enabled.

Request

```bash
GET /axis-cgi/param.cgi?action=list&group=ImageSource.I0Host: <servername>
```

**Return value - Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
...root.ImageSource.I0.AutoRotationEnabled=yes...
```

**Return value - Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax:

```bash
No AutoRotationEnabled in body.
```

**Update**

-   Set `ImageSource.I#.AutoRotationEnabled` to `yes` to enable AutoRotationEnabled and `no` to disable it.
-   If `ImageSource.I#.Rotation` is changed through the API `ImageSource.I#.AutoRotationEnabled` will be turned off.

**Request:**

```bash
GET /axis-cgi/param.cgi?action=update&ImageSource.I0.AutoRotationEnabled=yesHost: <servername>
```

**Return value - Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
OK
```

**Return value - Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

Response body syntax

```bash
# Error: Error setting 'ImageSource.I#.AutoRotationEnabled' to 'nnn'!
```

## API specification

-   **List security level**: `Viewer`
-   **Update security level**: `Operator or N/A`
-   **Method**: `GET`

### ImageSource.I#

```bash
ImageSource.I#.<parameter>
```

Valid values for `#` ranges from `0` to the number of image sources in the system `-1`.

| Parameter | Description |
| --- | --- |
| `SourceRotation=yes | no` | Read-only parameter specifying whether the device has image source rotation or not. |
| `Rotation=0 | 90 | 180 | 270` | A read/write parameter from a set of integers as defined in `Properties.Image.Rotation`, typically <0, 90, 180, 270>. Default value is 0. |
| `AutoRotationEnabled=yes | no` | Specifying whether the device rotation is set, depending on it’s orientation or whether it is set by the user. |