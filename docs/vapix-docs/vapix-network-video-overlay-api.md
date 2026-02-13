---
title: Overlay API
url: "https://developer.axis.com/vapix/network-video/overlay-api/"
category: vapix
subcategory: network-video
sha256: 1da03c474e32b657878ee24efa8800cd5ee0603a10a9da0c1ec0d434ec11d734
scraped_at: "2026-01-09T15:20:34.816Z"
page_height: 91024
---

# Overlay API

The Overlay API is used to access overlay functionality such as privacy masks, text overlay and image overlay. The API is divided into:

-   [Dynamic overlay API](#dynamic-overlay-api)
-   [Overlay modifiers](#overlay-modifiers)
-   [Dynamic text](#dynamic-text)
-   [Privacy mask API](#privacy-mask-api)
-   [Overlay image API](#overlay-image-api)

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Dynamic overlay API
### Description

The Dynamic overlay API gives applications and users the ability to both get and set overlay configurations in the Axis cameras. Each overlay in the camera is identified by an ID which is returned upon creation. An overlay can be either text, image or special overlays that are provided by other applications, such as the [Privacy mask API](#privacy-mask-api). It is also possible to remove overlays created by the API. The special overlays can not be configured from this API.

| Function | Description |
| --- | --- |
| `/axis-cgi/dynamicoverlay/dynamicoverlay.cgi` | CGI holding all methods needed to add, change, remove and list overlays. Requests and responses are in the JSON format. |

| Method | Description |
| --- | --- |
| `addImage` | Creates an image overlay and returns an overlay ID if successful, otherwise returns an error. |
| `addText` | Creates a text overlay and returns an overlay ID if successful, otherwise returns an error. |
| `getSupportedVersions` | Get the available API versions. |
| `list` | Get a summary of all overlays created. |
| `remove` | Remove the overlay identified by a specific overlay ID. |
| `setImage` | Change properties of a specific image overlay identified by an specified overlay ID. |
| `setText` | Change properties of a specific text overlay identified by a specified overlay ID. |
| `getOverlayCapabilities` | Returns the number of the total overlay slots, number of slots occupied per text overlay and the number of occupied slots per image overlay. |

### Overview
#### Model

The API consists of a CGI enabling a user to control the underlaying dynamic overlays. There is one CGI request that implements a number of methods and to which the responses are in the JSON format.

The CGI gives the client the ability to:

-   Create image overlays.
-   Create text overlays.
-   Alter properties on a previously created overlay.
-   Remove a given overlay.
-   List created overlays.
-   Request a list with the supported API versions.

**Note:**

-   All of the overlays, especially those that are neither text nor image overlays, can be modified by internal applications.
-   The coordinate system used in this API is \[-1.0,1.0\] for both the X and Y axis. In addition to the coordinate system there are also several named positions, such as `topLeft`.
-   The maximum number of characters for each individual text overlay is 512.

#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.DynamicOverlay.DynamicOverlay=yes`
-   **Property**: `Properties.DynamicOverlay.Version=1.00`
-   **AXIS OS**: 7.10 and later

#### Limitations

Overlay IDs may change after a reboot. This is because the overlay system always uses the lowest available number, starting from 1.

Text rotation isn't available on ARTPEC-6 cameras, and isn't supported on ARTPEC-7 and ARTPEC-8 panoramic cameras. Use `getOverlayCapabilities` to check if text rotation is supported on your camera.

### Common examples
#### How to use the examples

The examples in the following sections are formatted to be used with cURL.

```bash
curl --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  --data @sample\_code.json  "http://<servername>/axis-cgi/dynamicoverlay/dynamicoverlay.cgi"
```

#### Add text overlays

Use this example to add text overlays with transparent backgrounds, in this case one at the top left corner of the video that shows timestamps and another at the right bottom corner that shows the address and location of the camera.

1.  Add a text overlay at the top left corner that shows the timestamp. If the font size is not specified by the user a suitable font size will be selected by the camera depending on resolution. The font size will then have to be read back with a list command should the user require it.

```bash
{    "apiVersion": "1.0",    "context": "321",    "method": "addText",    "params": {        "camera": 1,        "text": "%c",        "position": "topLeft",        "textColor": "white"    }}
```

2.  Parse the JSON response.

a. Success response example. The response returns the identity of the overlay created.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "321",    "data": {        "camera": 1,        "identity": 0    }}
```

b. Failure response example.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "321",    "error": {        "code": 304,        "message": "Invalid value for parameter text"    }}
```

3.  Add a text overlay at the bottom right corner that shows the address using a specified font size.

```bash
{    "apiVersion": "1.0",    "context": "456",    "method": "addText",    "params": {        "camera": 1,        "text": "Emdalav/u00E4gen 14\\nLund",        "position": "bottomRight",        "fontSize": 14,        "textColor": "white"    }}
```

4.  Parse the JSON response.

a. Success response example. The response returns the identity of the overlay created.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "456",    "data": {        "camera": 1,        "identity": 1    }}
```

b. Failure response example.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "456",    "error": {        "code": 300,        "message": "Unable to create overlays (limit reached)"    }}
```

**API references:**

[addText](#addtext)

#### Add image overlays

Use this example to add an image overlay at the left bottom corner of the video.

**General preparations**

Upload an image to the camera according to [Upload a new image](#upload-a-new-image).

An overlay can contain several bitmap images to be adaptable to different resolutions. By calling the `list` command, the user receives a list showing all of the available pictures.

The user may then call the `addImage` command to create an image overlay. The overlays present are:

```bash
/etc/overlays/axis(128x44).ovl/etc/overlays/image.ovl
```

where `/etc/overlays/axis(128x44).ovl` comes pre-installed.

By calling the `list` command a second time, the user receives information on all of the overlays, including the newly created overlay. In the description of the overlay is a variable called `scalable` that let the user know if the overlay is scale-to-resolution or not. Scale-to-resolution means that the image overlay re-scale based on the resolution of the video stream.

1.  Add an image overlay at the default location with a company logo.

```bash
{    "apiVersion": "1.0",    "context": "789",    "method": "addImage",    "params": {        "camera": 1,        "overlayPath": "image.ovl"    }}
```

2.  Parse the JSON response.

a. Success response example. The response returns the identity of the overlay created.

```bash
{    "apiVersion": "1.0",    "method": "addImage",    "context": "789",    "data": {        "camera": 1,        "identity": 2    }}
```

b. Failure response, see [Error handling](#error-handling)

#### List overlays

Use this example to retrieve a list of all overlays used in a device.

1.  List all overlays previously created by add methods.

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "list",    "params": {}}
```

2.  Parse the JSON response.

a. Success response example. The response gives a list of overlays with all corresponding properties. Note that scale-to-resolution overlays are only listed as a single directory as described in [Add image overlays](#add-image-overlays) for the add image overlay use case. If the overlay is scaled to the resolution, then the scalable property should be set to true.

```bash
{  "apiVersion": "1.0",  "data": {    "imageFiles": \[      "/etc/overlays/axis(128x44).ovl",      "/etc/overlays/logo.ovl"    \],  "imageOverlays": \[    { "camera": 1, "identity": 2, "overlayPath": "logo.ovl", "position": ... },    ...  \],  "textOverlays": \[    { "camera": 1, "identity": 0, ... "text": ... "fontSize": 80, "size": \[32, 48\]},    { "camera": 1, "identity": 1, ... "text": ... "fontSize": 14, "size": \[47, 256\]},    ...    \]  },  "method": "list",}
```

b. Failure response, see [Error handling](#error-handling)

**API references:**

[list](#list)

#### Update overlays

Use this example to

**Set text overlay**

1.  Set text color to white and background to red.

```bash
{    "apiVersion": "1.0",    "context": "456",    "method": "setText",    "params": {        "identity": 0,        "textBGColor": "red"    }}
```

2.  Parse the JSON response.

a. Success response example.

```bash
{    "apiVersion": "1.0",    "method": "setText",    "data": {}}
```

b. Failure response, see [Error handling](#error-handling)

**API references:**

[setText](#settext)

**Set image overlay**

1.  Update image overlay

Update overlay image.

```bash
{    "apiVersion": "1.0",    "context": "333",    "method": "setImage",    "params": {        "identity": 2,        "camera": 1,        "overlayPath": "redlogo.ovl"    }}
```

2.  Parse the JSON response.

a. Success response example.

```bash
{    "apiVersion": "1.0",    "method": "setImage",    "context": "333",    "data": {}}
```

b. Failure response, see [Error handling](#error-handling)

**API references:**

[setImage](#setimage)

#### Remove overlays

Use this example to remove an overlay based on its ID.

1.  Remove the overlay with a specified identity.

```bash
{    "apiVersion": "1.0",    "context": "444",    "method": "remove",    "params": {        "identity": 1    }}
```

2.  Parse the JSON response.

a. Success response example.

```bash
{    "apiVersion": "1.0",    "method": "remove",    "context": "444",    "data": {}}
```

b. Failure response, see [Error handling](#error-handling).

**API references:**

[remove](#remove)

#### getSupportedVersions

Use this example to check if features are supported before an application uses them.

1.  Get a list of supported JSON API versions. Note that no apiVersion is supposed to be defined in the request.

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response to find out whether the operation was successful or not.

a. Success response example.

```bash
{    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "2.0", "3.0"\]    }}
```

b. Failure response, see [Error handling](#error-handling)

**API references:**

[getSupportedVersions](#get-supported-versions-dynamic-overlay-api-api-documentation)

#### Get the maximum number of overlays

Use this example to receive information about how many overlays that can be used.

1.  Get the overlay capabilities for this camera.

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getOverlayCapabilities"}
```

2.  Parse the JSON response to find out whether the operation was successful or not.

a. Success response example.

```bash
{    "method": "getOverlayCapabilities",    "context": 123,    "apiVersion": "1.0",    "data": {        "numberAvailbleSlots": 8,        "slotsPerImageOverlay": 2,        "slotsPerTextOverlay": 1    }}
```

b. Failure response, see [Error handling](#error-handling)

**API references:**

[getOverlayCapabilities](#getoverlaycapabilities)

#### Add overlay with scrolling text

info

This feature has been deprecated as of AXIS OS version 11.10 and will no longer receive any updates.

Use this example to implement an overlay with scrolling text when the text gets to long to fit in the video stream.

1.  Create a text overlay at the bottom, then specify a background color to make the text easier to read. Set the scroll speed to negative to make the text move from right to left.

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "addText",    "params": {        "camera": 1,        "text": "Weather forecast: Sunny every day! --- Stock index OMSX +0.3%, ...",        "scrollSpeed": -1,        "position": "bottomRight",        "textColor": "white",        "textBGColor": "black"    }}
```

2.  Parse the JSON response to find out whether the operation was successful or not.

a. Success response example.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "123",    "data": {        "camera": 1,        "identity": 1    }}
```

b. Failure response example.

```bash
{    "apiVersion": "1.0",    "method": "addText",    "context": "123",    "error": {        "code": 310,        "message": "Invalid value for parameter scroll speed"    }}
```

**API references:**

[addText](#addtext)

### API documentation
#### addText

addText is used to create new text overlays. When creating an overlay using the CGI you may also specify properties at the same time.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "addText",  "params": {    "camera": <1-x>,    "text": <string>    "position": <top | topRight | bottomRight | bottom | bottomLeft | topleft> | \[decimal,decimal\],    "fontSize": <0-200>,    "rotation": <(-180)-180>,    "scrollSpeed": <(-20)-20>,    "textColor": <black | white | red | transparent | semiTransparent>,    "textBGColor": <black | white | red | transparent | semiTransparent>,    "textOLColor": <black | white | red | transparent | semiTransparent>,    "reference": <channel | scene>,    "ptPosition": <(-180)-180>,    "zoomInterval": <1-19999>,    "indicator": <string>,    "indicatorSize": <0-200>,    "indicatorColor": <black | white | red | transparent | semiTransparent>,    "indicatorBG": <black | white | red | transparent | semiTransparent>,    "indicatorOL": <black | white | red | transparent | semiTransparent>  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="addText"` Specifies that the `addText` operation is performed.
-   `context=<string>` Optional. The user sets this value and server echoes the data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `camera=<1-x>` Required. Defines the view area on which the overall shall be displayed on. "x" is the number of available view areas on the product and can be found in Plain Config/Image/Nbr of configs.
-   `text=<string>` Required. Defines text to be displayed. `%0A` can be put in text as a new line to make multi-line string.
-   `position=<top | topRight | bottomRight | bottom | bottomLeft | topLeft> | [decimal,decimal]` Optional. Defines the x, y coordinates to place the overlay either by predefined strings or a relative x, y position consisting of an array of two numbers from `-1.0` up to `1.0`. Default is `0.0,0,0`.
-   `textColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which color the text is displayed in. Default is `black`.
-   `textBGColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which background color to display. Default is `transparent`.
-   `textOLColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which outline color to display. Default is `transparent`.
-   `fontSize=<0-200>` Optional. Defines the size of the text. Default size is determined relative to the maximal camera resolution, use "list" to get the actual size.
-   `rotation=<(-180)-180>` Optional. Defines the rotation of the text in degrees. The text rotates around its center point. Default is `0`.
-   `reference=<channel | scene>` Optional. Defines how the position coordinates are expressed. Default value is `channel`.
-   When `channel` is the reference, the specified coordinates are relative to the video as it is seed by a user.
-   When `scene` is the reference, the overlay position consists of normalized pixel coordinate, like with `channel`. Pan and tilt values for the PTZ along with a zoom interval can also be used to define the overlay, while the pixel coordinates defines the position of the overlay in the camera image. The PTZ coordinates defines the pan and tilt position in degrees, where the overlay is places in the scene. The zoom interval determines between which zoom values the overlay will be visible.
-   `ptPosition=<(-180)-180> | [integer, integer]` Optional. The pan/tilt coordinates of the PTZ, measured in degrees. Defines at which PTZ position an overlay is visible on the camera image. The coordinates should be given as an array of two integers between `-180` to `180`. The default pan and tilt values reflects the position of the camera from when the overlay was created.
-   `zoomInterval=<1-19999> | [integer, integer]` Optional.
-   `scrollSpeed=<(-20)-20>` Optional. This property is used to make the text slide across the stream instead of being stationary. Positive values cause the text to slide from left to right while negative values cause it to slide from right to left. When the text has fully left the stream it reappears on the other side. The default is `0`. If `textBGColor` also is set the background will cover the whole width of the stream rather than only where the text is currently located.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "addText",  "context": "<string>",  "data": {    "camera": <integer>,    "identity": <integer>  }}
```

-   `apiVersion` Current version is 1.0.
-   `method="addText"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `data.camera` The view area on which the overlay was created.
-   `data.identity` The identity of the overlay created.

**Return value - Failure**

See [Error handling](#error-handling)

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed in [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 300 | Unable to create overlays (limit reached). |
| 301 | Invalid value for parameter `camera`. |
| 303 | Invalid value for parameter `position`. |
| 304 | Invalid value for parameter `text`. |
| 306 | Invalid value for parameter `textColor`. |
| 307 | Invalid value for parameter `textBGColor`. |
| 308 | Invalid value for parameter `textOLColor`. |
| 309 | Invalid value for parameter `fontSize`. |
| 310 | Invalid value for parameter `scrollSpeed`. |
| 311 | Invalid value for parameter `visible` |
| 312 | Invalid value for parameter `zIndex`. |
| 313 | Invalid value for parameter `reference`. |
| 314 | Invalid value for parameter `ptPosition`. |
| 315 | Invalid value for parameter `zoomInterval`. |
| 316 | Invalid value for parameter `indicator`. |
| 317 | Invalid value for parameter `indicatorSize`. |
| 318 | Invalid value for parameter `indicatorColor`. |
| 319 | Invalid value for parameter `indicatorBG`. |
| 320 | Invalid value for parameter `indicatorOL`. |
| 321 | Invalid value for parameter `rotation`. |

#### addImage

addImage is used to create new image overlays. When creating an overlay using the CGI you may also specify properties at the same time.

Refer to the Overlay API section on uploading images for instruction on how to upload new images.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "addImage",  "params": {    "camera": <1-x>,    "overlayPath": <string>,    "position": <top | topRight | bottomRight | bottom | bottomLeft | topLeft> | \[decimal,decimal\]  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="addImage"` Specifies that the `addImage` operation is performed.
-   `context=<string>` Optional. Client sets this value and server echoes data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `camera=<1-x>` Required. Defines the view area on which the overlay shall be displayed on. x is the number of available view areas on the product and can be found in Plain Config/Image/Nbr of configs.
-   `overlayPath=<string>` Required. Defines path to image to display. Default is an empty string.
-   `position=<top | topRight | bottomRight | bottom | bottomLeft | topLeft> | [decimal,decimal]` Optional. Defines the x,y coordinates to place the overlay either by predefined strings or a relative x,y position consisting of an array of two numbers from `-1.0` up to `1.0`. Default is `0.0,0.0`.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "addImage",  "context": "<string>",  "data": {    "camera": <integer>,    "identity": <integer>  }}
```

-   `apiVersion` Current version is 1.0.
-   `method="addImage"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `data.camera` The view area on which the overlay was created.
-   `data.identity` The identity of the overlay created.

**Return value - Failure**

See [Error handling](#error-handling)

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed in [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 300 | Unable to create overlays (limit reached). |
| 301 | Invalid value for parameter camera. |
| 303 | Invalid value for parameter position. |
| 305 | Invalid value for parameter overlayPath |

#### setText

setText is used to update parameters for a certain text overlay. The user may specify more than one parameter at any time. Optional parameters that are not supplied will not be charged.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setText",  "params": {    "identity": <integer>,    "text": <string>,    "position": <top | topRight | bottomRight | bottom | bottomLeft | topLeft> | \[decimal,decimal\],    "fontSize": <0-200>,    "rotation": <(-180)-180>,    "scrollSpeed": <(-20)-20>,    "textColor": <black | white | red | transparent | semiTransparent>,    "textBGColor": <black | white | red | transparent | semiTransparent>,    "textOLColor": <black | white | red | transparent | semiTransparent>  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="setText"` Specifies that the `setText` operation is performed.
-   `context=<string>` Optional. Client sets this value and server echoes data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `identity=<integer>` Required. Defines which overlay to change.
-   `text=<string>` Optional. Defines the text to be displayed.
-   `position=<top | topRight | bottomRight | bottom | bottomLeft | topLeft>` Optional. Defines the x, y coordinates to place the overlay either by predefined strings or a relative x, y position consisting of an array of two numbers from `-1.0` up to `1.0`. Default is `0.0,0.0`.
-   `textColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which color the text is displayed in.
-   `textBGColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which background color to display.
-   `textOLColor=<black | white | red | transparent | semiTransparent>` Optional. Defines which outline color to display.
-   `fontSize=<0-200>` Optional. Defines the size of the text.
-   `rotation=<(-180)-180>` Optional. Defines the rotation of the text in degrees. The text rotates around its center point. Default is `0`.
-   `scrollSpeed=<(-20)-20>` Defines the speed by which the text slides across the stream.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "setText",  "context": "<string>",  "data": {}}
```

-   `apiVersion` Current version is 1.0.
-   `method="setText"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.

Successful calls contains an empty `data` object.

**Return value - Failure**

See [Error handling](#error-handling)

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed in [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 302 | Invalid value for parameter `identity`. |
| 303 | Invalid value for parameter `position`. |
| 304 | Invalid value for parameter `text`. |
| 306 | Invalid value for parameter `textColor`. |
| 307 | Invalid value for parameter `textBGColor`. |
| 308 | Invalid value for parameter `textOLColor`. |
| 309 | Invalid value for parameter `fontSize`. |
| 310 | Invalid value for parameter `scrollSpeed`. |
| 311 | Invalid value for parameter `visible`. |
| 312 | Invalid value for parameter `zIndex`. |
| 313 | Invalid value for parameter `reference`. |
| 314 | Invalid value for parameter `ptPosition`. |
| 315 | Invalid value for parameter `zoomInterval`. |
| 316 | Invalid value for parameter `indicator`. |
| 317 | Invalid value for parameter `indicatorSize`. |
| 318 | Invalid value for parameter `indicatorColor`. |
| 319 | Invalid value for parameter `indicatorBG`. |
| 320 | Invalid value for parameter `indicatorOL`. |
| 321 | Invalid value for parameter `rotation`. |

#### setImage

setImage is used to update parameters for a certain image overlay. The user may specify more than one parameter at one time, however optional parameters that are not supplied will not be changed.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion". <string>,  "context": "<string>",  "method": "setImage",  "params": {    "identity": <integer>    "overlayPath": <string>    "position": <top | topRight | bottomRight | bottom | bottomLeft | topLeft> | \[decimal,decimal\]  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="setImage"` Specifies that the `setImage` operation is performed.
-   `context=<string>` Optional. Client sets this value and server echoes data in response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `identity=<integer>` Required. Defines which overlay to change.
-   `overlayPath=<string>` Optional. Defines path to image to display.
-   `position=<top | topRight | bottomRight | bottom | bottomLeft | topLeft> | [decimal,decimal]` Optional. Defines the x, y coordinates to place the overlay either by predefined strings or a relative x, y position consisting of an array of two numbers from `-1.0` up to `1.0`. Default is `0.0,0.0`.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "setImage",  "context": "<string>",  "data": {}}
```

-   `apiVersion` Current version is 1.0.
-   `method="setImage"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.

Successful calls contains an empty `data` object.

**Return value-Failure**

See [Error handling](#error-handling).

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed in [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 302 | Invalid value for parameter identity. |
| 303 | Invalid value for parameter position. |
| 305 | Invalid value for parameter overlayPath. |

#### list

`list` all overlays created by the add CGIs and display both their IDs and other properties. If specified, properties for all overlays can be listed for a given camera or, if further specified, for a specific camera layer. The IDs may change for each overlay after a reboot. It is therefore recommended to check the current overlay ID with `list` before it is updated or removed.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "list",  "params": {    "camera": <1-x>,    "identity": <integer>  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="list"` Specifies that the `list` operation is performed.
-   `context=<string>` Optional. Client sets this value and the server echoes data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `camera=<1-x>` Optional. Defines which view area we want to list properties for. Supplied either by the add or list CGIs. If not specified all view areas are listed.
-   `identity=<integer>` Optional. Defines which specific overlay to list properties for.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.8",  "method": "list",  "context": <string>  "data": {    "imageFiles": \["fileName", "fileName"\],    "imageOverlays": \[      {        "camera": <integer>,        "identity": <integer>,        "overlayPath": <string>,        "position": \[<decimal>,<decimal>\] | <string>,        "zIndex": <integer>,        "visible": <boolean>        "scalable": <boolean>      }    \],    "textOverlays": \[      {        "camera": <integer>,        "identity": <integer>,        "indicator": <string>,        "indicatorBG": "<string>",        "indicatorColor": "<string>",        "indicatorOL": "<string>",        "indicatorSize": <integer>,        "position": \[<decimal>,<decimal>\] | <string>,        "ptPosition": \[<decimal>,<decimal>\],        "text": <string>,        "textColor": <string>,        "textBGColor": <string>,        "textOLColor": <string>,        "fontSize": <integer>,        "reference": <string>,        "rotation": <integer>,        "scrollSpeed": <integer>,        "size": \[<integer>, <integer>\],        "zIndex": <integer>,        "zoomInterval": \[<decimal>,<decimal>\],        "visible": <boolean>,        "scalable": <boolean>,        "textLength": <integer>      }    \]  }}
```

-   `apiVersion` Current version is 1.8.
-   `method="list"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `data.imageFiles[]=<list of image overlay files>` List of file names available to use as image overlays, for example: \["/etc/overlays/image1.ovl", "/etc/overlay/image2.ovl"\]
-   `data.imageOverlays[].camera` The view area.
-   `data.imageOverlays[].identity` The overall identity.
-   `data.imageOverlays[].position` The textual position string or x, y coordinates where the overlay is located.
-   `data.imageOverlays[].overlayPath` The path to the image used for the overlay.
-   `data.imageOverlays[].zIndex` If zIndex of the overlay.
-   `data.imageOverlays[].visible` If the overlay is visible.
-   `data.imageOverlays[].scalable` If the overlay is scaled, based on the resolution.
-   `data.textOverlays[].camera` The view area.
-   `data.textOverlays[].identity` The overlay identity.
-   `data.textOverlays[].position` The textual position string or x, y coordinate where the overlay is located.
-   `data.textOverlays[].text` The overlay text.
-   `data.textOverlays[].textColor` The text color for the overlay.
-   `data.textOverlay[].textBGColor` The background color for the overlay.
-   `data.textOverlay[].textOLColor` The outline color for the overlay.
-   `data.textOverlay[].fontSize` The outline color for the overlay.
-   `data.textOverlay[].rotation` The rotation of the overlay.
-   `data.textOverlay[].reference` The coordinate system of the position of the overlay.
-   `data.textOverlays[].scrollSpeed` The scroll speed for the overlay.
-   `data.textOverlays[].size` The actual size in pixels of the text overlay.
-   `data.textOverlays[].zIndex` If zIndex of the overlay.
-   `data.textOverlays[].visible` If the overlay is visible.
-   `data.textOverlays[].scalable` If the overlay is scaled, based on the resolution.
-   `data.textOverlays[].textLength` The length of the text (in bytes) after any modifiers have been expanded with default values.
-   `data.textOverlays[].ptPosition` The pan/tilt coordinates of the PTZ, measured in degrees. Defines at which PTZ position an overlay is visible on the camera image.
-   `data.textOverlays[].zoomInterval` The zoom interval in which the overlay is visible.
-   `data.textOverlays[].indicator` The overlay indicator text.
-   `data.textOverlays[].indicatorSize` The font size for the indicator.
-   `data.textOverlays[].indicatorColor` The text color for the indicator.
-   `data.textOverlays[].indicatorBG` The background color for the indicator.
-   `data.textOverlays[].indicatorOL` The outline color for the indicator.

**Return value - Failure**

See [Error handling](#error-handling).

**Error codes**

The following table lists error codes that can be returned form this method. General errors are listed in [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 301 | Invalid value for parameter camera. |
| 302 | Invalid value for parameter identity. |

#### remove

remove will delete the overlay identified by the provided id.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "<remove>",  "params": {    "identity": <integer>  }}
```

-   `apiVersion` The API version that the response should use.
-   `method="list"` Specifies that the +remove+1 operation is performed.
-   `context=<string>` Optional. User sets this value and the server echoes the data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `identity=<integer>` Required. Defines which overlay to remove. Supplied either by the add or list CGIs.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "method": "remove",  "context": "<string>",  "data": {}}
```

-   `apiVersion` Current version is 1.0.
-   `method="remove"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.

All successful calls contains an empty `data` object.

**Return value - Failure**

See [Error handling](#error-handling).

**Error codes**

The following table lists error codes that can be returned from this method. General errors are listed under [Error handling](#error-handling).

| Code | Description |
| --- | --- |
| 301 | Invalid value for parameter camera. |
| 302 | Invalid value for parameter identity. |

#### getSupportedVersions

getSupportedVersions is used to retrieve the list of supported response schema versions that are available.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "context": "<string>",  "method": "getSupportedVersions"}
```

-   `method="getSupportedVersions"` Specifies that the `getSupportedVersions` operation is performed.
-   `context=<string>` Optional. Client sets this value and server echoes data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "method": "getSupportedVersions",  "context": "<string>",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

-   `method="getSupportedVersions"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `data.apiVersions[]=<list of versions>` List of supported versions, all major versions with highest supported minor version.
-   `<list of versions>` List of "<Major>.<Minor>" versions e.g. \["1.4", "2.5"\].

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "method": "The called method",  "context": "Echoed if provided by the client in the corresponding request",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

-   `method=<string>` The method name.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `error.code` The error code.
-   `error.message` The error message.

**Error codes**

There are no specific error codes for this method. General errors are listed under [Error handling](#error-handling).

#### getOverlayCapabilities

getOverlayCapabilities returns the number of total overlay slots, the number of slots occupied per text overlay and the number of slots occupied per image overlay.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getOverlayCapabilities"}
```

-   `method="getOverlayCapabilities"` Specifies that the `getOverlayCapabilities` operation is performed.
-   `context=<string>` Optional. Client sets this value and server echoes data in the response. If set, it will be present in the response regardless of whether the response is successful or an error.
-   `apiVersion` The API version that the response should use.

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "method": "getOverlayCapabilities",  "context": "<string>",  "apiVersion": "1.8",  "data": {    "maxFontSize": <integer>,    "minFontSize": <integer>,    "maxImageHeight": <integer>,    "maxImageSize": <integer>,    "maxImageWidth": <integer>,    "maxTextLength": <integer>,    "numAvailableSlots": <integer>,    "rotationSupported": <boolean>,    "slotsPerImageOverlay": <integer>,    "slotsPerOverlay": <integer>,    "slotsPerTextOverlay": <integer>,    "supportedReferences": \[<string>, <string>, <string>\]  }}
```

-   `method="getOverlayCapabilities"` The method described in this section.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `apiVersion` Current version is 1.8.
-   `data.maxFontSize=<integer>` The maximum font size for a text overlay.
-   `data.minFontSize=<integer>` The minimum font size for a text overlay.
-   `data.maxImageHeight=<integer>` The maximum height in pixels for an image overlay.
-   `data.maxImageSize=<integer>` The maximum number of pixels for an image overlay.
-   `data.maxImageWidth=<integer>` The maximum width in pixels of an image overlay.
-   `data.maxTextLength=<integer>` The maximum length of a text string for a text overlay.
-   `data.numAvailableSlots=<integer>` The number of slots available that can be used by overlays.
-   `data.rotationSupported=<boolean>` Indicates if rotation is supported.
-   `data.slotsPerImageOverlay=<integer>` The number of slots an image overlay occupies.
-   `data.slotsPerOverlay=<integer>` The number of slots used by an overlay.
-   `data.slotsPerTextOverlay=<integer>` The number of slots an text overlay occupies.
-   `data.supportedReferences=[<string>, <string>, <string>]` List of supported overlay references.

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "method": "The called method",  "context": "Echoed if provided by the client in the corresponding request",  "error": {    "code": integer error code,    "message": "Error message"  }}
```

-   `method=<string>` The method name.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `error.code` The error code.
-   `error.message` The error message.

**Error codes**

There are no specific error codes for this method. General errors are listed under [Error handling](#error-handling).

#### Error handling

**General JSON error codes**

The following table lists general error that can occur for any CGI method. Errors that are specific for a method are listed under the API description for that method.

| Code | Description |
| --- | --- |
| 100 | The requested API version is not supported. |
| 101 | Internal error. |
| 102 | A mandatory input parameter was not found in the input. |
| 103 | Invalid parameter. |
| 200 | The provided input was invalid. |
| 201 | Unexpected error. |
| 202 | Generic error. |
| 203 | Invalid method. |

**Return value - Failure**

If a request fails the response follows for the following syntax.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "Major.Minor",  "method": "The called method",  "context": "Echoed if provided by the client in the corresponding request",  "error": {    "code": integer error code,    "message": "Error message"}
```

-   `apiVersion=<string>` Current version is 1.0.
-   `method=<string>` The method name.
-   `context=<string>` Text-string echoed back if provided by the client in the corresponding request.
-   `error.code` The error code.
-   `error.message` The error message.

## Overlay modifiers
### Description

Overlay modifiers is to describe the Overlay modifiers functionality in Axis products.

Overlay modifiers are markup strings that when present in overlay text strings are expanded according to their corresponding function.

Modifiers can, among other things, be used to:

-   insert text, such as date, time, system and sensor information, into the video stream that will be recorded together with the image.
-   format file names, folders for uploaded images, notification messages and text in image overlays.
-   retrieve functional groups and supported modifiers.

| Function | Usage |
| --- | --- |
| `getOverlayModifiers` | Retrieve supported overlay modifiers. |

### Overview
#### Model

The API consists of the single CGI `/axis-cgi/overlaymodifiers.cgi` which allows querying for supported overlay modifiers.

#### Identification

-   **Property**: `Properties.OverlayModifiers.OverlayModifiers="yes"`
-   **AXIS OS**: 5.1 and later

### Common examples
#### Present supported modifiers

This example will show you how to create a list of overlay modifiers for other users to choose from.

1.  Retrieve a list of available groups and modifiers.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/overlaymodifiers.cgi"
```

```bash
GET /axis-cgi/overlaymodifiers.cgiHost: <servername>
```

2.  Parse JSON response.

Successful response example

```bash
{  "apiVersion": "0.2",  "context": 1,  "method": "getOverlayModifiers",  "data": {    "groups": {      "data": \[        {"mod": "%c"},        {"mod": "%D"},        {"mod": "%F"},        {"mod": "%X"}      \],      ........      "sysinfo": \[        {"mod": "#i"},        {"mod": "#m"},        {"mod": "#M"},        {"mod": "#n"},        {"mod": "#TC", "index": true},        {"mod": "#TF", "index": true}      \],      ........    }  }}
```

Error response example

```bash
{    "apiVersion": "0.2",    "context": "1",    "method": "getOverlayModifiers",    "error": {        "code": 1000,        "message": "Internal Error"    }}
```

3.  Create a list and present it to the user.

### API documentation
#### getOverlayModifiers

This method should be used when you want to retrieve overlay modifiers supported by your device.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/overlaymodifiers.cgi"
```

```bash
GET /axis-cgi/overlaymodifiers.cgiHost: <servername>
```

| Parameter | Description |
| --- | --- |
| `context` | Integer user data either echoed in the response or returned as `0` when left out (optional). |

**Return value - Success**

Returns available groups along with an array of modifiers.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "0.2",  "context": 1,  "method": "getOverlayModifiers",  "data": {    "groups": {      "data": \[        {"mod": "%c"},        {"mod": "%D"},        {"mod": "%F"},        {"mod": "%X"}      \],      ........      "sysinfo": \[        {"mod": "#i"},        {"mod": "#m"},        {"mod": "#M"},        {"mod": "#n"},        {"mod": "#TC", "index": true},        {"mod": "#TF", "index": true}      \],      ........    }  }}
```

See [Schema for `/axis-cgi/overlaymodifiers.cgi` response](#schema-for-axis-cgioverlaymodifierscgi-response) for the JSON schema.

**Return value - Failure**

N/A, can only fail on a HTTP level.

#### Overlay modifiers properties

| Parameter | Description |
| --- | --- |
| `"apiVersion": {"type": "string"}` | The API version that the data complies with. |
| `"context": {"type": "integer"}` | Set by the user in the request and echoed in the response. Automatically becomes `0` when not set in the request. |
| `"method": {"type": "string"}` | The requested method. |
| `"data": {object}` | A container for group objects. |
| `"groups": [{objects}]` | An array of objects detailing the modifiers belonging to the group. |

```bash
"properties": {  "mod": {"type": "string"},  "index": {"type": "boolean"}}
```

See [Overlay modifier groups](#overlay-modifier-groups) for a complete list of available groups.

| Parameter | Description |
| --- | --- |
| `"mod": {"type": "string"}` | A modifier always starts with either a `%` or `#` character, followed by one or two characters and an index. Modifiers that require an index has the optional parameter `index` set to `true`, as detailed below. See [Overlay modifiers](#overlay-modifiers) for a complete list of available modifiers. |
| `"index": {"type": "boolean"}` | Optional property that exists in overlay modifiers that requires an additional index to be complete, for example modifiers `#U`, `#TC` and `#TF` are used to determine which fan or temperature sensor the modifier applies to. A modifier for fan 1 status would then be `#U1` and for temperature sensor 2, in Celsius, `#TC2`. |

### Schema for `/axis-cgi/overlaymodifiers.cgi` response

```bash
{    "$schema": "http://json-schema.org/draft-04/schema#",    "title": "Axis Overlay Modifiers JSON Schema",    "description": "Axis Overlay Modifiers schema for JSON requests and responses",    "type": "object",    "allOf": \[{ "$ref": "#/definitions/overlaymodifiers\_response" }\],    "definitions": {        "array\_of\_modifiers": {            "type": "array",            "items": {                "type": "object",                "properties": {                    "mod": { "type": "string" },                    "index": { "type": "boolean" }                },                "required": \["mod"\],                "additionalProperties": false            }        },        "overlaymodifiers\_response": {            "properties": {                "apiVersion": {                    "type": "string"                },                "context": {                    "type": "integer"                },                "method": {                    "type": "string"                },                "data": {                    "type": "object",                    "properties": {                        "groups": {                            "type": "object",                            "properties": {                                "date": { "$ref": "#/definitions/array\_of\_modifiers" },                                "time": { "$ref": "#/definitions/array\_of\_modifiers" },                                "year": { "$ref": "#/definitions/array\_of\_modifiers" },                                "month": { "$ref": "#/definitions/array\_of\_modifiers" },                                "week": { "$ref": "#/definitions/array\_of\_modifiers" },                                "day": { "$ref": "#/definitions/array\_of\_modifiers" },                                "hour": { "$ref": "#/definitions/array\_of\_modifiers" },                                "minute": { "$ref": "#/definitions/array\_of\_modifiers" },                                "second": { "$ref": "#/definitions/array\_of\_modifiers" },                                "sysinfo": { "$ref": "#/definitions/array\_of\_modifiers" },                                "vidinfo": { "$ref": "#/definitions/array\_of\_modifiers" },                                "ptzinfo": { "$ref": "#/definitions/array\_of\_modifiers" },                                "eventinfo": { "$ref": "#/definitions/array\_of\_modifiers" },                                "sensor": { "$ref": "#/definitions/array\_of\_modifiers" },                                "mqtt": { "$ref": "#/definitions/array\_of\_modifiers" },                                "autotracking": { "$ref": "#/definitions/array\_of\_modifiers" },                                "others": { "$ref": "#/definitions/array\_of\_modifiers" }                            }                        }                    },                    "required": \["groups"\],                    "additionalProperties": false                },                "required": \["apiVersion", "data"\],                "additionalProperties": false            }        }    }}
```

### Overlay modifier groups

| Group | Description |
| --- | --- |
| `date` | Group Date - according to libc standard |
| `time` | Group Time - according to libc standard |
| `year` | Group Year - according to libc standard |
| `month` | Group Month - according to libc standard |
| `week` | Group Week - according to libc standard |
| `day` | Group Day - according to libc standard |
| `hour` | Group Hour - according to libc standard |
| `minute` | Group Minute - according to libc standard |
| `second` | Group Second - according to libc standard |
| `sysinfo` | Group Product and system information |
| `vidinfo` | Group Video information |
| `ptzinfo` | Group Pan/Tilt/Zoom information |
| `sensor` | Group Sensor and Optics |
| `zwave` | Group Z-Wave |
| `mqtt` | Group MQTT |
| `autotracking` | Group Autotracking |
| `others` | Group Others |

### Overlay modifiers

Date modifiers

| Modifiers | Description | Example |
| --- | --- | --- |
| `%c` | Date and time. | Sun Dec 25 10:25:01 2011 |
| `%D` | Date in format MM/DD/YY. | 12/25/11 |
| `%F` | Date in format YYYY-MM-DD. | 2011–12–25 |
| `%x` | Same as %D. | 12/25/11 |

Time modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%p` | AM or PM according to the given time or the corresponding strings for the current locale. Noon is treated as PM and midnight as AM. | AM |
| `%r` | Time in AM or PM notation. | 10:25:01 AM |
| `%R` | Time in 24–hour notation without seconds. | 10:25 |
| `%T` | Time in 24–hour notation with seconds. | 10:25:01 |
| `%X` | Same as %T. | 10:25:01 |
| `%z` | Time zone as offset from UTC. | +0000 |
| `%Z` | Time zone name or abbreviation. | GMT |

Year modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%C` | The century as a 2–digit number (year/100). | 20 |
| `%G` | The ISO 8601 week-numbering year as a 4–digit number. | 2011 |
| `%g` | The ISO 8601 week-numbering year as a 2–digit number without the century, range 00 to 99. | 11 |
| `%Y` | The Gregorian calendar year as a 4–digit number. | 2011 |

Month modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%b` | Abbreviated month name. | Dec |
| `%B` | Full month name. | December |
| `%h` | Same as %b. | Dec |
| `%m` | Month as a 2–digit number, range 01 to 12. | 12 |

Week modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%U` | The week number as a 2–digit number, range 00 to 53. Sunday is the first day of the week. Week 01 is the week starting with the first Sunday of the current year. | 52 |
| `%V` | The ISO 8601 week number as a 2–digit number, range from 01 to 53. Monday is the first day of the week. Week 01 is the first week that has at least four days in the current year. | 51 |
| `%W` | The ISO 8601 week number as a 2–digit number, range from 01 to 53. Monday is the first day of the week. Week 01 is the week starting with the first Monday of the current year. | 51 |

Day modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%a` | Abbreviated weekday name. | Sun |
| `%A` | Full weekday name. | Sunday |
| `%d` | Day of the month as a 2–digit number, range from 01 to 31. | 25 |
| `%e` | Same as %d but a leading zero is replaced by a blank space. | 25 |
| `%j` | Day of the year as a 3–digit number, ranging from 001 to 366. | 359 |
| `%u` | Day of the week as an 1–digit number, ranging from 1 to 7. Monday is 1. | 7 |
| `%w` | Day of the week as an 1–digit number, ranging from 0 to 6. Sunday is 0. | 0 |

Hour modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%H` | Hour in 24–hour format, ranging from 00 to 23. | 09 |
| `%I` | Hour in 12–hour format, ranging from 01 to 12. | 09 |
| `%k` | Same as %H but a leading zero is replaced by a blank space. | 9 |
| `%l` | Same as %I but a leading zero is replaced by a blank. | 9 |

Minute modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%M` | Minute as a 2–digit number, range 00 to 59. | 25 |

Second modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `%f` | 1/100 seconds as a 2–digit number. | 67 |
| `%s` | The number of seconds since EPOCH, that is, since 1970–01–01 00:00:00 UTC. | 1319178723 |
| `%S` | The current seconds as a 2–digit number, ranging from 00 to 59. | 10 |

Product and system information modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#i` | The IP address. | 10.13.24.88 |
| `#m` | The short MAC address (last 6 characters). | 77:F8:26 |
| `#M` | The full MAC address (all characters). | 00:40:8C:77:F8:26 |
| `#n` | The host name. | axis-00408c77f826 |
| `#U<index>` | The fan status. <index> is which fan, for example #U1. | Stopped |
| `#TC<index>` | The temperature in Celsius. <index> is which temperature sensor, for example #TC1. | 48.4 |
| `#TF<index>` | The temperature in Fahrenheit. <index> is which temperature sensor, for example #TF1. | 119.1 |

Video information modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#b` | Bit rate in kbit/s (no decimals). | 16333 |
| `#B` | Bit rate in Mbit/s (two decimals). | 16.33 |
| `#r` | Frame rate with two decimals. | 30.00 |
| `#R` | Frame rate without decimals. | 30 |
| `#v` | Video source number. | 1 |

Pan/tilt/zoom information modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#x` | Pan coordinate (signed, with two decimals). | \-77.61 |
| `#y` | Tilt coordinate (signed, with two decimals). | \-7.61 |
| `#z` | Zoom coordinate (range 1 to 19999). | 256 |
| `#Z` | Zoom magnification (with one decimal). | 12.0 |
| `#p` | Preset position number. If not a preset position, blank space is used. | 3 |
| `#P` | Preset name. If not a preset position, blank space is used. | Door |
| `#L` | OSDI (On Screen Directional Indicator) zone name. A zone within specified pan and tilt coordinates. If not within an OSDI zone, blank space is used. | Construction |

Sensor and optics modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#av` | Current aperture value. | 2.8 |
| `#al` | Lowest aperture value. | 2.8 |
| `#ah` | Highest aperture value. | 32 |
| `#gv` | Current gain value (dB). | 10 |
| `#gl` | Lowest gain value (dB). | 0 |
| `#gh` | Highest gain value (dB). | 60 |
| `#Gv` | Current ISO gain value (ASA). | 320 |
| `#Gl` | Lowest ISO gain value (ASA). | 100 |
| `#Gh` | Highest ISO gain value (ASA). | 102400 |
| `#hv` | Current shutter value (seconds). | 1/250.0 |
| `#hl` | Lowest shutter value (seconds). | 1/1.0 |
| `#hh` | Highest shutter value (seconds). | 1/4000.0 |
| `#lv` | Current focal length value (mm). | 50.0 |
| `#ln` | Current lens name. | EF85mm f/1.2L II USM |

Z-Wave modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#WB<index>` | Battery status in percentage. `<index>` is the node ID (1–232), for example `#WB1`. | 32 |
| `#WOS<index>` | The output switch status (on/off). `<index>` is the node ID (1–232), for example `#WOS1`. | 1 |
| `#WTC<index>` | Temperature, in Celsius, of a multilevel sensor. `<index>` is the node ID (1–232), for example `#WTC1`. | 48.4 |
| `#WTF<index>` | Temperature, in Fahrenheit, of a multilevel sensor. `<index>` is the node ID (1–232), for example `#WTF1`. | 119.1 |
| `#WIS<index>` | The input switch status (on/off). `<index>` is the node ID (1–232), for example `#WOS1`. | 1 |

Autotracking modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#ATN` | Active profile name. | Parkinglot |
| `#ATP` | Active profile priority. | 2 High |
| `#ATS` | Sensors that confirm the tracked object. | Video and Radar |
| `#ATC` | Video classification of the current object. | car |
| `#ATD` | Distance to the current object (m or ft). | 15 |
| `#ATV` | Speed of the current object (km/h or mph). | 12 |

MQTT modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#XMP<index>` | Displays the full MQTT payload on the subscription of a topic tied to `index`. | `{temperature_data: 23.2}` |
| `#XMD<index>` | Displays specific data fields in an MQTT payload on the subscription of a topic tied to `<index>`. The payload is a text string and must be written in the JSON format. | 23.2 |

Other modifiers

| Modifier | Description | Example |
| --- | --- | --- |
| `#s` | Sequence number of the video image as a 5–digit number. | 00129 |
| `#D<index>` | Dynamic text in an overlay. `<index>` is optional and specifies a dynamic text slot. See [Dynamic text](#dynamic-text) for additional information. |  |
| `%%` | The % character. | % |
| `##` | The # character. | # |

## Dynamic text

Dynamic text can be inserted to text overlays. This API only accept GET calls.

-   **Security level**: Operator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/dynamicoverlay.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/dynamicoverlay.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `settext` `gettext` | `gettext` = Get the dynamic text. `settext` = Set the dynamic text. |
| `text=<string>` | A string | The overlay text to apply, only applicable with action=settext. |
| `text_index=<integer>` | `1...16` | Select a dynamic text slot. A text index for a slot maps text to the modifiers `#D1...#D16` . For example, `text_index=3&text=Hello` means that `Hello` will be mapped to `#D3`. |
| `camera=<string>[,string,...]` | `1 (default) ...` _Product/release-dependent. Check the product’s release notes._ | Selects the video channel. If omitted the default value camera=1 is used. This argument is only valid for Axis products with more than one video channel. That is cameras with multiple view areas and video encoders with multiple video channels. |

## Privacy mask API

Privacy masking is a feature that makes it possible to mask out, i.e. cover areas in the picture that should not be visible to the viewers, such as the face of a person, logotypes and license plates. The masks will adapt their position and size when the cameras pan/tilt/zoom position changes to make sure that areas that have been masked remain that way.

### Mask shape

The shape of a privacy mask is defined by a list of corner coordinates that either forms a rectangle or a polygon. Which form that is supported is described by a property parameter.

-   If `Properties.PrivacyMask.Polygon=yes` is active, then a simple polygon shape is supported by`Properties.PrivacyMask.MaxNbrOfCorners` corners .  
    The corners should be sorted in a clockwise rotation around the polygon, however, it’s up to the client to decide on the starting corner.
-   The other option supports 4 corners in the shape of a rectangle, where the corners should be sorted in a clockwise rotation starting at the upper left corner.

### Prerequisites
#### Identification

-   **API Discovery**: `id=privacy-mask version=3.x`
    
-   Property
    
    `Properties.API.HTTP.Version=3`
    
-   Property
    
    `Properties.PrivacyMask.PrivacyMask=yes`
    

A number of additional properties are used to signal support for various privacy mask features:

-   **Property**: `Properties.PrivacyMask.MaxNbrOfPrivacyMasks=<number of supported privacy masks>`
-   **Property**: `Properties.PrivacyMask.Polygon=<yes/no>`
-   **Property**: `Properties.PrivacyMask.MaxNbrOfCorners=<int>`
-   **Property**: `Properties.PrivacyMask.Query=<list of supported query types>`
-   **Property**: `Properties.PrivacyMask.MainSwitch=<yes/no>`
-   **Property**: `ImageSource.NbrOfSources=<number of image sources>`

#### Obsoletes

The `image.PrivacyMaskType` is a legacy parameter that was used to enable settings for privacy masks and other overlays before the introduction of privacy-mask 2.0. Instead, use the parameter `Properties.PrivacyMask.PrivacyMask` to determine if a privacy mask is supported.

#### Dependencies

There currently exist two ways to create privacy masks. One is by using `/axis-cgi/privacymask.cgi` and the other by using `/axis-cgi/param.cgi`. Some functions, such as color and mosaic scale, can only be set using `/axis-cgi/param.cgi`, which means that some products will be using both.

-   For cameras lacking support for `/axis-cgi/privacymask.cgi`, `/axis-cgi/param.cgi` is used on its own, as these cameras cannot adapt mask positions when the pan/tilt/zoom positions change, e.g. when connecting an external PTZ head on the serial port for a fix camera. Masks created on DPTZ are not affected by this.
-   Cameras supporting the `/axis-cgi/param.cgi` use the "add", "update" and "remove" options described in [Parameter management](/vapix/network-video/parameter-management/). Using the "add" option in the `/axis-cgi/param.cgi` will create new privacy masks denoted M0, M1 and M2, up to the maximum number of supported privacy masks.

### Common examples

**Add a privacy mask to the center of the image**

Add a privacy mask named `mask1` to the center of the image. The width and height of the mask are set in percent of the image size.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?action=add&name=mask1&imagesource=2&width=20.0&height=20.0"
```

```bash
GET /axis-cgi/privacymask.cgi?action=add&name=mask1&imagesource=2&width=20.0&height=20.0Host: <servername>
```

**Add and position a privacy mask to the image**

Add a privacy mask named `mask1` centered around 20% of the image width and 20% of the image height of the picture. Width and height are set in percent of the image size.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?action=add&name=mask1&width=20.0&height=20.0¢er=20.0,20.0"
```

```bash
GET /axis-cgi/privacymask.cgi?action=add&name=mask1&width=20.0&height=20.0¢er=20.0,20.0Host: <servername>
```

**Add a privacy mask to the image using pixel coordinates**

Add a privacy mask named `mask1` using pixel coordinates to set the position of the mask.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?action=add&name=mask1&pxpolygon=500,500:800,500:700,700:400,700"
```

```bash
GET /axis-cgi/privacymask.cgi?action=add&name=mask1&pxpolygon=500,500:800,500:700,700:400,700Host: <servername>
```

**Retrieve information about the size of a privacy mask**

Get width and height for privacy mask p1.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?query=positionpxjson&name=Mask1"
```

```bash
GET /axis-cgi/privacymask.cgi?query=positionpxjson&name=Mask1Host: <servername>
```

**Add multiple privacy masks**

Add two privacy masks named `mask1` and `mask2` using the `/axis-cgi/param.cgi`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=add&template=0\_maskwindows&group=Image.I0.Overlay.MaskWindows&Image.I0.Overlay.MaskWindows.M.Enabled=yes&Image.I0.Overlay.MaskWindows.M.Width=250&Image.I0.Overlay.MaskWindows.M.Height=300&Image.I0.Overlay.MaskWindows.M.Xpos=500&Image.I0.Overlay.MaskWindows.M.YPos=400&Image.I0.Overlay.MaskWindows.M.Name=mask1"
```

```bash
GET /axis-cgi/param.cgi?action=add&template=0\_maskwindows&group=Image.I0.Overlay.MaskWindows&Image.I0.Overlay.MaskWindows.M.Enabled=yes&Image.I0.Overlay.MaskWindows.M.Width=250&Image.I0.Overlay.MaskWindows.M.Height=300&Image.I0.Overlay.MaskWindows.M.Xpos=500&Image.I0.Overlay.MaskWindows.M.YPos=400&Image.I0.Overlay.MaskWindows.M.Name=mask1Host: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=add&template=0\_maskwindows&group=Image.I0.Overlay.MaskWindows&Image.I0.Overlay.MaskWindows.M.Enabled=yes&Image.I0.Overlay.MaskWindows.M.Width=200&Image.I0.Overlay.MaskWindows.M.Height=100&Image.I0.Overlay.MaskWindows.M.Xpos=200&&Image.I0.Overlay.MaskWindows.M.YPos=100&Image.I0.Overlay.MaskWindows.M.Name=mask2"
```

```bash
GET /axis-cgi/param.cgi?action=add&template=0\_maskwindows&group=Image.I0.Overlay.MaskWindows&Image.I0.Overlay.MaskWindows.M.Enabled=yes&Image.I0.Overlay.MaskWindows.M.Width=200&Image.I0.Overlay.MaskWindows.M.Height=100&Image.I0.Overlay.MaskWindows.M.Xpos=200&&Image.I0.Overlay.MaskWindows.M.YPos=100&Image.I0.Overlay.MaskWindows.M.Name=mask2Host: <servername>
```

**Rename a privacy mask**

Rename the previously created `mask2` to `mask2_old` using `/axis-cgi/param.cgi`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Image.I0.Overlay.MaskWindows.M1.Enabled=yes&Image.I0.Overlay.MaskWindows.M1.Width=200&Image.I0.Overlay.MaskWindows.M1.Height=100&Image.I0.Overlay.MaskWindows.M1.Xpos=200&Image.I0.Overlay.MaskWindows.M1.YPos=100&Image.I0.Overlay.MaskWindows.M1.Name=mask2\_old"
```

```bash
GET /axis-cgi/param.cgi?action=update&Image.I0.Overlay.MaskWindows.M1.Enabled=yes&Image.I0.Overlay.MaskWindows.M1.Width=200&Image.I0.Overlay.MaskWindows.M1.Height=100&Image.I0.Overlay.MaskWindows.M1.Xpos=200&Image.I0.Overlay.MaskWindows.M1.YPos=100&Image.I0.Overlay.MaskWindows.M1.Name=mask2\_oldHost: <servername>
```

**Remove privacy masks**

Remove the previously created `mask1` and `mask2_old` using `/axis-cgi/param.cgi`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=remove&group=Image.I0.Overlay.MaskWindows.M0,Image.I0.Overlay.MaskWindows.M1"
```

```bash
GET /axis-cgi/param.cgi?action=remove&group=Image.I0.Overlay.MaskWindows.M0,Image.I0.Overlay.MaskWindows.M1Host: <servername>
```

**Disable all privacy masks**

Disables all privacy masks. This is useful during an emergency when you want to make sure that nothing vital gets hidden behind a mask.

1.  Disable all privacy masks.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?action=disable\_all"
```

```bash
GET /axis-cgi/privacymask.cgi?action=disable\_allHost: <servername>
```

2.  Enable all privacy masks.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?action=enable\_all"
```

```bash
GET /axis-cgi/privacymask.cgi?action=enable\_allHost: <servername>
```

Please note that this method will disable all masks. If you wish to disable individual privacy masks you should use `/axis-cgi/param.cgi`.

### Parameters
#### Using `/axis-cgi/privacymask.cgi`

-   List security level: Operator
-   Update security level: Admin

Image.I#.Overlay.MaskWindows

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Color` | `black` | `black` `grey` `white` `red` `mosaic` _Hardware dependent_`chameleon` _Hardware dependent_ | admin: read, write | Set the color for the privacy masks of `Image.I#`.`black` = Black colored privacy mask. `grey` = Grey colored privacy mask. `white` = White colored privacy mask. `red` = Red colored privacy mask. `mosaic` = Pixelated (chessboard) privacy mask. Each pixel in a square have the same color, which is decided by the image behind the privacy mask. The square will adapt to the zoom level of a camera to keep the object behind the privacy mask obscured. `chameleon` = Changes color depending on the background. For example, if the mask is covering a red wall, the mask will become red. |
| `MosaicScale` _Hardware dependent_ | 3 | 3–16 | admin: read, write | Set the mosaic effect scale for privacy masks of `Image.I#` when color is set to `mosaic`Defines the size of the squares in the mosaic, such as `8x8`, `16x16`, etc. |

Image.I#.Overlay:MaskWindows.M#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes, no` | admin: read, write | Decides whether the privacy mask should be visible in the picture.`yes` = Privacy mask is visible. `no` = Privacy mask is not visible. |
| `Name` | `<Mask#>` | String | admin: read, write | The name of the privacy mask. |
| `ZoomLowLimit` | `0` | `0 ... 19999` | admin: read, write | Hides the privacy mask if the current zoom value is below the parameter value. |

The index in `Image.I#` represents the video channel.

The index in `MaskWindows.M#` represents the index of the privacy mask.

#### Using param.cgi

Image.IO.Overlay.MaskWindows

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Color` | `black` | `black` `grey` `white` `red` `blurred` _Hardware dependent_ | admin: read, write | Set the color for the privacy masks of `Image.I#`.`black` = Black colored privacy mask. `grey` = Grey colored privacy mask. `white` = White colored privacy mask. `red` = Red colored privacy mask. `blurred` = Pixelated (chessboard) privacy mask. Each pixel in a square have the same color, which is decided by the image behind the privacy mask. The square will have a fixed size of 8x8 pixels. |

Image.IO.Overlay.MaskWindows.M#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes, no` | admin: read, write | Decides whether the privacy mask should be visible in the picture.`yes` = Privacy mask is visible. `no` = Privacy mask is not visible. |
| `XPos` | `0` | Integer | admin: read, write | The Privacy masks upper left corner is positioned at this horizontal position (0 = at the top). |
| `YPos` | `0` | Integer | admin: read, write | The Privacy masks upper left corner is positioned at this vertical position (0 = at the top). |
| `Width` | `0` | Integer | admin: read, write | Width of mask in pixel. |
| `Height` | `0` | Integer | admin: read, write | Height of mask in pixel. |
| `Name` | `No name` | String | admin: read, write | The name of the Privacy mask. |

The index in `Image.IO` represents the video channel.

The index in `MaskWindows.M#` represents the index of the privacy mask.

### Privacy mask arguments

If the Axis product supports pan, tilt or zoom it is also possible to set privacy masks via the `/axis-cgi/privacymask.cgi`.

-   **Security level**: Administrator

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/privacymask.cgi?<argument>=<value>\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/privacymask.cgi?<argument>=<value>\[<argument>=<value>...\]Host: <servername>
```

With the following parameters and values.

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `add` _Requires_ `name` _argument._ _Requires either_ `width` _and_ `height` , `pxpolygon`. `update` _Requires_ `name` _argument._ _Requires either_ `width` _and_ `height` , `pxpolygon`. `remove` _Requires_ `name` _argument._ `goto` _Requires_ `name` _argument._ `enable_all` `disable_all` | `add` = Add a new mask with unique name. `update` = Change position and/or size of existing mask. `remove` = Remove an existing mask. `goto` = Center camera on an existing mask. For modifying existing masks. `enable_all` = Enables all masks. The parameter `Image.I#.Overlay.MaskWindows.M#.Enabled` will be set to `yes` for all configured masks. Supported if `root.Properties.PrivacyMask.MainSwitch=yes`. `disable_all` = Disables all masks. The parameter `Image.I#.Overlay.MaskWindows.M#.Enabled` will be set to `no` for all configures masks. Supported if `root.Properties.PrivacyMask.MainSwitch=yes`. |
| `query=<query>` | `listpxjson` `positionpxjson` _Requires_ `name` _argument._ | `listpxjson` = List all masks with pixel coordinates in the JSON format. The pixel coordinates are given in the max resolution of the camera and with rotation = 0 degrees. Two lists are returned, one containing only the external corners and one with both external and internal corners. External corners are provided by the user, while internal corners are added by the service. Supported if listed in `root.Properties.PrivacyMask.Query`. `positionpxjson` = List all masks with pixel coordinates in the JSON format. The pixel coordinates are given in the max resolution of the camera and with rotation = 0 degrees. Supported if listed in `root.Properties.PrivacyMask.Query`. |
| `imagesource=<int>` | `0 ... n` (n = number of image sources -1.) | Selects the Image source. If the Image source is omitted, the parameter defaults to 0. |
| `name=<string>` | `<string>` | Unique name to identify a mask. Maximum length is 128 characters. |
| `width=<float>` | `0.0 ... 100.0` | Width of mask, in percent of image width. |
| `height=<float>` | `0.0 ... 100.0` | Height of mask, in percent of image height. |
| `center=<string>` | `0.0 ... 100.0,0.0 ...100.0` | Center coordinates, in percentage of image width and image height, of the mask stored as float values in a string, `width,height`. Used together with `width` and `height` parameters. If left out the mask will be placed in the center of the picture. |
| `pxpolygon=<int>` _Optional_ | `<0,0:0,0:0,0>` | Pixel coordinates of the corners of the privacy mask stored as integer values in a string of coordinated pairs, `<x1>,<y1>:<x2>,<y2>:<x3>,<y3>`. The pixel coordinates are given in the max resolution of the camera and with rotation = 0 degrees. The number of supported corners and the shape they represent is defined by `root.Properties.PrivacyMask.MaxNbrOfCorners` and `root.Properties.PrivacyMask.Polygon`. |
| `zoomlowlimit=<int>` _Optional_ | `0 ... 19999` _If digital zoom is supported,_ `zoomlowlimit` _can have values up to 19999._ | The minimum VAPIX zoom position for the privacy mask to be rendered. At zoom values wider than this position the mask will not be rendered. Should be set to 0 if omitted. Notes: 1. Requires name argument. 2. Requires either width and height argument or `pxpolygon` argument. |

#### Privacy mask responses

**Successful response `/axis-cgi/privacymask.cgi`**

Response after a successful request to `/axis-cgi/privacymask.cgi`.

-   **HTTP Code**: `204 No content`
-   **Content-Type**: `text/plain`

**Error response `/axis-cgi/privacymask.cgi`**

Response after an incorrectly formatted or incomplete request to `/axis-cgi/privacymask.cgi`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/plain`

```bash
Error:<Error message>
```

**Successful response query=listpxjson**

Response after a successful request to `/axis-cgi/privacymask.cgi` using `query=listpxjson`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{"listpx": \[    {"id": <int>,      "name": "<Mask name1>",      "enabled": <bool>,      "zoomlowlimit": <int>,      "zoom\_visible": <bool>,      "position": \[        {"x": <int>, "y": <int>},        ...      \]      "all\_position": \[        {"x": <int>, "y": <int>},        ...      \]    },    ...  \]}
```

Please note that pixel coordinates for a corner that is outside the current camera view will have values that are negative or larger than the image´s resolution.

`zoom_visible` is _optional_. If present, it will indicate whether the position polygon is visible due to the `zoomlowlimit` setting.

Position array can contain up to `Properties.PrivacyMask.MaxNbrOfCorners` x/y pairs. If the privacy mask is not visible in the current camera position, an empty position array will be returned.

`all_position` is _optional_. If present, it will contain the values found in `position`, as well as any helper corners added by the service.

**Successful response query=positionpxjson**

Response after a successful request to the `/axis-cgi/privacymask.cgi` using `query=positionpxjson`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{"position": \[    {"x": <int>, "y": <int>},    ...  \],}
```

info

Pixel coordinates for a corner that is outside the current camera view will have values that are negative or larger than the image´s resolution.

> Position array may contain up to Properties.PrivacyMask.MaxNbrOfCorners x/y pairs. If the privacy mask is not visible in the current camera position, an empty position array will be returned.

## Overlay image API
### Description

The Overlay image API makes it possible for applications to upload and manage images used for image overlays and configure the default image used in stream profiles.

#### Model

The API consists of the following CGI:s:

| Function | Description |
| --- | --- |
| `/axis-cgi/uploadoverlayimage.cgi` | Used for uploading images to the camera. The request uses multipart/form-data with one part being in the JSON format and one part containing the image data. |
| `/axis-cgi/manageoverlayimages.cgi` | Used for managing uploaded images. Requests and responses are in the JSON format. |

-   `/axis-cgi/uploadoverlayimage.cgi` uses the following methods:

| Method | Description |
| --- | --- |
| `uploadOverlayImage` | Upload an image to the camera. |
| `getSupportedVersions` | Get a list of supported API versions. |

-   `/axis-cgi/manageoverlayimages.cgi` uses the following methods:

| Method | Description |
| --- | --- |
| `supportedFormats` | Get a list of supported image formats. |
| `validateImageHeader` | Check if an image is supported based on provided image header data. It also checks that there is enough space available on the camera. |
| `listImages` | List all images present on the camera. |
| `deleteImage` | Delete an image. |
| `getDefaultImage` | Get the currently configured default image. |
| `setDefaultImage` | Set the default image. |
| `getSupportedVersions` | Get a list of supported API versions. |

#### Identification

-   **API Discovery**: `id=overlayimage`

### Common examples
#### Upload a new image

Use this example to upload an image to use for an image overlay.

**Upload image**

1.  Upload an image to the camera.

HTTP POST

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --form 'json={"apiVersion": "1.0","method": "uploadOverlayImage","params": {"scaleToResolution": true,"alpha": "ffffff"}};type=application/json' \\  --form 'image=@image.bmp;type=image/bmp' \\  "http://<servername>/axis-cgi/uploadoverlayimage.cgi"
```

```bash
POST /axis-cgi/uploadoverlayimage.cgiHost: <servername>Content-Type: multipart/form-data; boundary=<boundary>--<boundary>Content-Disposition: form-data; name="json"Content-Type: application/json{  "apiVersion": "1.0",  "method": "uploadOverlayImage",  "params": {    "scaleToResolution": true,    "alpha": "ffffff"  }}--<boundary>Content-Disposition: form-data; name="image"; filename="image.bmp"Content-Type: image/bmp<Image data>--<boundary>--
```

CURL

```bash
curl --request POST 'http://<servername>/axis-cgi/uploadoverlayimage.cgi'--digest -s -u '<username>:<password>'--form 'json=@"request.json"'--form 'image=@"image.bmp"'request.json{  "apiVersion": "1.0",  "method": "uploadOverlayImage",  "params": {    "scaleToResolution": true,    "alpha": "ffffff"  }}
```

2.  Parse the JSON response.

a) Successful response. The response returns the path of the image.

```bash
{    "apiVersion": "1.0",    "method": "uploadOverlayImage",    "data": {        "path": "/etc/overlays/image.ovl"    }}
```

b) Error response.

```bash
{    "apiVersion": "1.0",    "method": "uploadOverlayImage",    "error": {        "code": "1003",        "message": "Invalid parameter"    }}
```

#### List available images

Use this example to list all available overlay images.

**List images**

1.  List all available images.

```bash
{    "apiVersion": "1.0",    "method": "listImages"}
```

2.  Parse the JSON response.

a) Successful response example. The response list all available images. For each image a path identifying the image and a flag indicating the `scaleWithResolution` status is provided.

```bash
{    "apiVersion": "1.0",    "method": "listImages",    "data": {        "files": \[            { "path": "/etc/overlays/image1.ov1", "scaleWithResolution": true },            { "path": "/etc/overlays/image2.ov1", "scaleWithResolution": false }        \]    }}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "listImages",    "error": {        "code": "1003",        "message": "Invalid parameter"    }}
```

#### Delete an image

Use this example to delete an overlay image.

**Delete image**

1.  Delete an image.

```bash
{    "apiVersion": "1.0",    "method": "deleteImage",    "params": {        "path": "/etc/overlays/image.ovl"    }}
```

2.  Parse the JSON response.

a) Successful response example. The response will give information if the image was successfully deleted or not.

```bash
{    "apiVersion": "1.0",    "method": "deleteImage"}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "deleteImage",    "error": {        "code": "1003",        "message": "Invalid parameter"    }}
```

#### Set the default image

Use this example to set a default overlay image.

1.  Set the default image.

```bash
{    "apiVersion": "1.0",    "method": "setDefaultImage",    "params": {        "path": "/etc/overlays/image.ovl"    }}
```

2.  Parse the JSON response.

a) Successful response example. The response will give information if the default image was correctly set or not.

```bash
{    "apiVersion": "1.0",    "method": "setDefaultImage"}
```

b) Error response example.

```bash
{    "apiVersion": "1.0",    "method": "setDefaultImage",    "error": {        "code": "1003",        "message": "Invalid parameter"    }}
```

### API specification
#### uploadOverlayImage

Use `uploadOverlayImage` to upload a new overlay image by using a multipart/form-data.

The first part should contain a JSON request and be set up with the following parameters:

-   Content-disposition
    
    `form-data; name="json"`
    
-   **Content-Type**: `application/json`
    

The second part should contain the image data and should be set up with the following parameters:

-   Content-disposition
    
    `form-data; name="image"; filename=<name of file>`
    
-   **Content-Type**: `<image mime-type>`
    

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "uploadOverlayImage",  "context": "<string>",  "params": {    "scaleToResolution": <boolean>,    "alpha": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="uploadOverlayImage"` | Specifies that the `uploadOverlayImage` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `scaleToResolution` | _Required_. Specifies if the image should be configured as "scale-to-resolution" or not. Scale-to-resolution means that the size of an overlay that uses this image will be scaled based on the stream resolution. |
| `alpha` | _Optional_. Specifies a color to use as transparency. This can be used to support transparency for BMP images that normally doesn’t support it. For image formats that support transparency this parameter is ignored. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "uploadOverlayImage",  "context": "<string>",  "data": {    "path": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="uploadOverlayImage"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `data.path` | Path that should be used when referring to this image. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### supportedFormats

Use `supportedFormats` to get a list of image formats supported by the camera. Possible values are:

-   bmp
-   jpeg
-   png
-   svg

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "supportedFormats",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="supportedFormats"` | Specifies that the `supportedFormats` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "supportedFormats",  "context": "<string>",  "data": {    "formats": \[<string>, <string>\]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current of the API. |
| `method="supportedFormats"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `data.formats` | List of supported image formats. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### validateImageHeader

`validateImageHeader` will check if the image described by the parameters are supported, is of an acceptable file-size and that there are enough memory on the device. In cases where there are an invalid parameter, an error response is sent and the status code is set to reflect what the problem might be.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "validateImageHeader",  "context": "<string>",  "params": {    "type": <string>,    "width": <int>,    "height": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="validateImageHeader"` | Specifies that the `validateImageHeader` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `type=<string>` | _Required_. The image type. Should be one of the values listed in the documentation for `supportedFormats`. |
| `width=<integer>` | _Required_. The width of the image. |
| `height=<integer>` | _Required_. The height of the image. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "validateImageHeader",  "context": "<string>",  "data": {    "supportsAlpha": <boolean>,    "supportsScaling": <boolean>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="validateImageHeader"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `data.supportsAlpha` | Indicates if an alpha value may be specified for this image. |
| `data.supportsScaling` | Indicates if scale-to-resolution is supported for this image. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### listImages

Use `listImages` to get a list of available overlay images.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "listImages",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="listImages"` | Specifies that the `listImages` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response . If set, it will be present in the response whether the response was successful or an error. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "listImages",  "context": "<string>",  "data": {    "files": \[      {"path": <string>, "scaleWithResolution": <boolean>},      {"path": <string>, "scaleWithResolution": <boolean>}    \]  }}
```

| Parameter | Descriptions |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="listImages"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `data.files` | The list of available images. |
| `data.files.path` | The path identifying the image. |
| `data.files.scaleWithResolution` | A flag indicating if the image is scaled with the stream resolution. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "listImages",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### deleteImage

Use `deleteImage` to delete an overlay image.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "deleteImage",  "context": "<string>",  "params": {    "path": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="deleteImage"` | Specifies that the `deleteImage` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `path=<string>` | _Required_. The path identifying the image. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "deleteImage",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="deleteImage"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |

**Return value-Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### getDefaultImage

`getDefaultImage` retrieves the currently configured default overlay image.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "getDefaultImage",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="getDefaultImage"` | Specifies that the `getDefaultImage` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present regardless of whether the response is successful or an error. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "getDefaultImage",  "context": "<string>",  "data": {    "path": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="getDefaultImage"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `data.path=<string>` | Path that should be used when referring to this image. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### setDefaultImage

Use `setDefaultImage` to set the default overlay image.

**Request**

-   **Security level**: Operator
-   **Method**: `POST`

```bash
{  "apiVersion": <string>,  "method": "setDefaultImage",  "context": <string>  "params": {    "path": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="setDefaultImage"` | Specifies that the `setDefaultImage` operation is performed. |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `path=<string>` | _Required_. The path identifying the image to set. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "1.0",  "method": "setDefaultImage",  "context": <string>}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The current version of the API. |
| `method="setDefaultImage"` | The method described in this section. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### getSupportedVersions

Use `getSupportedVersions` to retrieve the list of supported API versions.

**Request**

-   **Security level**: Operator

```bash
POST /<functionality>.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | _Optional_. The string echoed back in the response. If set, it will be present in the response regardless of whether the response is successful or an error. |
| `method="getSupportedVersions` | Specifies that the `getSupportedVersions` operation is performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersion": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method="getSupportedVersions"` | The method described in this section. |
| `data.apiVersion[]=<list of versions>` | List of supported versions. All major versions are listed with their highest supported minor version. |
| `<list of versions>` | List of <Major>.<Minor> versions e.g. \["1.4", "2.5"\]. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<major>.<minor>` | The API version that is used. |
| `context=<string>` | The string echoed back if it is provided by the client in the corresponding request. |
| `method=<string>` | The method described in this section. |
| `error.code` | Contains an error code. This method can be a method specific or a general error code. |
| `error.message` | Contains a detailed message about the occurred failure. |

**Error codes**

See [Error codes](#error-codes) for a full list of potential error codes.

#### Error codes

| Error code | Description |
| --- | --- |
| `1000` | Internal error. |
| `1001` | The requested API version is not supported. |
| `1002` | Invalid method. |
| `1003` | Invalid parameter. |
| `1004` | The provided input was invalid. |
| `1005` | Image size is too big. |
| `1006` | Unsupported image format. |
| `1007` | Not enough space left on the device. |
| `1008` | Alpha is not supported. |
| `1009` | Scale-to-resolution is not supported. |
| `1010` | Image already exists. |
| `1011` | Image is being used by a dynamic overlay. |
| `1012` | Image is being used by a legacy overlay. |
| `1013` | Image is being used as default image. |
| `1014` | Image is being used by an overlay. |