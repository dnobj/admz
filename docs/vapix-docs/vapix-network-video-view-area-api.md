---
title: View Area API
url: "https://developer.axis.com/vapix/network-video/view-area-api/"
category: vapix
subcategory: network-video
sha256: 5a3b778599e1c34fb86c5972966087f64a7f9f70e863cfb0ff360fb1c21fa689
scraped_at: "2026-01-09T15:21:28.506Z"
page_height: 28064
---

# View Area API

## Description

The View Area API makes it possible to define the subsections of a camera’s full view as individual, virtual channels. This means that a wide angle and/or high resolution camera can provide multiple video streams at a lower resolution where each stream covers a specific region of interest. The API is also able to simplify the installation process by fine tuning an area digitally after the camera has been manually pointed at a scene.

It is desirable to stream the same area to multiple clients so that both the recording and live view show the same scene, i.e. each area is linked to a virtual channel accessed through the device’s configuration GUI. For more information about streaming, see [Video streaming](/vapix/network-video/video-streaming/).

### Model

The API implements `/axis-cgi/viewarea/info.cgi` and `/axis-cgi/viewarea/configure.cgi` as its communications interface and supports the following methods:

Methods for `/axis-cgi/viewarea/info.cgi`

| Method | Description |
| --- | --- |
| `list` | Retrieve information about available view areas |
| `getSupportedVersions` | List the supported API versions (for security level Viewer). |

Methods for `/axis-cgi/viewarea/configure.cgi`:

| Method | Description |
| --- | --- |
| `setGeometry` | Set the geometry of a view area. |
| `resetGeometry` | Reset the geometry of a view area back to default geometry. |
| `getSupportedVersions` | List the supported API versions (for security level Administrator). |

A view area is defined as a separate view from the camera view and can take up either the full or parts of that view. The view areas are referenced in the camera interface and can be used in streaming, PTZ and other APIs that refer to a video channel.

All Axis cameras has a pre-defined maximum number of view areas disabled by default with the exception of the first one. See the [Video streaming](/vapix/network-video/video-streaming/) for information on how to enable and disable different video channels, as this API doesn’t support these methods.

Geometries are defined in pixel coordinates and refers to a canvas size that is set by this API. The scene that is covered by the canvas is identical to the overview video stream and the API will assume that the pixel coordinates matches the rotation and mirroring of the stream. Due to the way cropping is done, the geometry of the view area needs to be aligned to a grid on the canvas, usually consisting of 8x8 pixels.

If the device supports Digital PTZ, it can be enabled on a view area using the PTZ API. If so, the PTZ Home preset position will refer to the view area’s position, while the PTZ position pan=0, tilt=0, zoom=0 will refer to the full camera view.

By using the PTZ API, the view can be freely zoomed in and out and moved around the canvas, although the geometry listed for the view that uses the View Area API will not change when using the PTZ functionality and it will keep referring to the PTZ Home preset position.

### Identification

-   **API Discovery**: `id=view-area`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### List view areas

Use this example to see which parts of the full camera view that is covered by your view areas.

1.  Get view areas properties.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/info.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "list"}'
```

```bash
POST /axis-cgi/viewarea/info.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "list"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "list",    "data": {        "viewAreas": \[            {                "id": 1000001,                "source": 0,                "camera": 1,                "configurable": false            },            {                "id": 1001002,                "source": 1,                "camera": 2,                "configurable": true,                "rectangularGeometry": {                    "horizontalOffset": 128,                    "horizontalSize": 480,                    "verticalOffset": 64,                    "verticalSize": 270                },                "canvasSize": {                    "horizontal": 1920,                    "vertical": 1080                },                "minSize": {                    "horizontal": 256,                    "vertical": 144                },                "maxSize": {                    "horizontal": 1920,                    "vertical": 1080                },                "grid": {                    "horizontalOffset": 1,                    "horizontalSize": 2,                    "verticalOffset": 0,                    "verticalSize": 2                }            }        \]    }}
```

Failed response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "list",    "error": {        "code": 101,        "message": "The requested API version is not supported"    }}
```

### Configure a view area

Use this example to configure multiple virtual channels to cover separate areas of your wide angle or high resolution camera in order to minimize bandwidth.

#### Set the geometry of a view area

1.  Set the geometry of a view area.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/configure.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setGeometry",    "params": {        "viewArea": {            "id": 1000002,            "rectangularGeometry": {                "horizontalOffset": 0,                "horizontalSize": 960,                "verticalOffset": 0,                "verticalSize": 540            }        }    }}'
```

```bash
POST /axis-cgi/viewarea/configure.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setGeometry",    "params": {        "viewArea": {            "id": 1000002,            "rectangularGeometry": {                "horizontalOffset": 0,                "horizontalSize": 960,                "verticalOffset": 0,                "verticalSize": 540            }        }    }}
```

info

Sometimes, the geometry of the request won’t be aligned with the grid of the canvas. This can happen when the video aspect ratio is unable to align with the grid on all sides and when it does, the geometry will try to create an optimal fit.

2.  Parse the JSON response.

Successful responses will yield a reply identical to the one found in [List view areas](#list-view-areas), however, it is recommend that you update the local view area geometry to what is provided by the response, as it may differ from the geometry in the request.

Failed response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "setGeometry",    "error": {        "code": 201,        "message": "View area is not configurable"    }}
```

#### Reset the geometry of a view area

1.  Reset the geometry of a view area.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/configure.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "resetGeometry",    "params": {        "viewAreas": {            "id": 1000001        }    }}'
```

```bash
POST /axis-cgi/viewarea/configure.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "resetGeometry",    "params": {        "viewAreas": {            "id": 1000001        }    }}
```

2.  Parse the JSON response.

Successful responses will yield a reply identical to the one found in [List view areas](#list-view-areas).

Failed response

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "resetGeometry",    "error": {        "code": 201,        "message": "View area is not configurable"    }}
```

### Get supported versions

Use this example to retrieve a list of API versions that are supported by your device.

1.  Get a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/info.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/viewarea/info.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.3", "2.1"\]    }}
```

Failed response

```bash
{    "apiVersion": "2.1",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error"    }}
```

## API specification
### list

This API method is used when you want to retrieve a complete listing of available view areas and how they have been configured.

**Request**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/info.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "list"}'
```

```bash
POST /axis-cgi/viewarea/info.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "list"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="list"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "list",  "data": {    "viewAreas": \[      {        "id": <unsigned int>,        "source": <unsigned int>,        "camera": <unsigned int>,        "configurable": <boolean>,        "rectangularGeometry": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }        "canvasSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "minSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "maxSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "grid": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="list"` | The operation that was performed. |
| `data=<object>` | The data of the response. |
| `viewAreas=<object>` | The view data configurations of the response. |
| `id=<unsigned int>` | Identifies the view area. |
| `source=<unsigned int>` | Identifies the image source that created the view areas. |
| `camera=<unsigned int>` | Identifies the view area used by streaming, PTZ and other APIs. |
| `configurable=<boolean>` | Defines if a view can be configured. Some view areas can not be configured and are thus unable to be changed with regards to geometry, etc. |
| `rectangularGeometry=<object>` | Defines a geometry for the view area as a rectangle related to the canvas. This is only listed if the geometry can be configured. |
| `rectangularGeometry.horizontalOffset=<unsigned int>` | Defines the offset of a rectangle’s left edge in relation to the left edge of the canvas. |
| `rectangularGeometry.horizontalSize=<unsigned int>` | Defines the width of the rectangle. |
| `rectangularGeometry.verticalOffset=<unsigned int>` | Defines the offset of the top edge of the rectangle relative to the top edge of the canvas. |
| `rectangularGeometry.verticalSize=<unsigned int>` | Defines the height of the rectangle. |
| `canvasSize=<object>` | Defines the size of the overview image that the view area geometry is defined on. This is only listed if the geometry of the view area can be configured. |
| `canvasSize.horizontal=<unsigned int>` | Defines the width of the canvas. |
| `canvasSize.vertical=<unsigned int>` | Defines the height of the canvas. |
| `minSize=<object>` | Defines the minimum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `minSize.horizontal=<unsigned int>` | Defines the minimum width that a view area can have. |
| `minSize.vertical=<unsigned int>` | Defines the minimum height that a view area can have. |
| `maxSize=<object>` | Defines the maximum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `maxSize.horizontal=<unsigned int>` | Defines the maximum width of a view area. |
| `maxSize.vertical=<unsigned int>` | Defines the maximum height of the view area. |
| `grid=<object>` | Defines the grid that a geometry is applied to on the canvas due to device limitations. This is only listed if the geometry of the view area can be configured. |
| `grid.horizontalOffset=<unsigned int>` | Defines the offset of the first vertical grid line relative to the left edge of the canvas. |
| `grid.horizontalSize=<unsigned int>` | Defines the distance between vertical grid lines. |
| `grid.verticalOffset=<unsigned int>` | Defines the offset of the first horizontal grid line relative to the top edge of the canvas. |
| `grid.verticalSize=<unsigned int>` | Defines the distance between horizontal grid lines. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of error codes.

### setGeometry

This API method is used when you want to set the geometry of a view area. The response will show a complete list of all available view areas.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/configure.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setGeometry",  "params": {    "viewArea": {      "id": <unsigned int>,      "rectangularGeometry": {        "horizontalOffset": <unsigned int>,        "horizontalSize": <unsigned int>,        "verticalOffset": <unsigned int>,        "verticalSize": <unsigned int>      }    }  }}'
```

```bash
POST /axis-cgi/viewarea/configure.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setGeometry",  "params": {    "viewArea": {      "id": <unsigned int>,      "rectangularGeometry": {        "horizontalOffset": <unsigned int>,        "horizontalSize": <unsigned int>,        "verticalOffset": <unsigned int>,        "verticalSize": <unsigned int>      }    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="setGeometry"` | The operation that should be performed. |
| `params=<object>` | Contains the data of the request. |
| `viewArea=<object>` | Contains the view area data of the request. |
| `id=<unsigned int>` | Identifies the area that should be configured. |
| `rectangularGeometry=<object>` | Defines a geometry for the view area in the shape of a rectangle that is related to the canvas. The geometry is not always aligned with the canvas grid and the video aspect ratio might make it impossible to align with the grid on all sides. The geometry will align to the best possible fit, but the view area’s geometry in the response will show the requested geometry, not the aligned geometry. |
| `rectangularGeometry.horizontalOffset=<unsigned int>` | Defines the offset of the left edge of the rectangle relative to the left edge of the canvas. |
| `rectangularGeometry.horizontalSize=<unsigned int>` | Defines the width of the rectangle. |
| `rectangularGeometry.verticalOffset=<unsigned int>` | Defines the offset of the top edge of the rectangle relative to the edge of the canvas. |
| `rectangularGeometry.verticalSize=<unsigned int>` | Defines the height of the rectangle. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setGeometry",  "data": {    "viewAreas": \[      {        "id": <unsigned int>,        "source": <unsigned int>,        "camera": <unsigned int>,        "configurable": <boolean>,        "rectangularGeometry": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }        "canvasSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "minSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "maxSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "grid": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="setGeometry"` | The operation that was performed. |
| `data=<object>` | The data of the response. |
| `viewAreas=<object>` | The view data configurations of the response. |
| `id=<unsigned int>` | Identifies the view area. |
| `source=<unsigned int>` | Identifies the image source that is used to create the view areas. |
| `camera=<unsigned int>` | Identifies the view area used by streaming, PTZ and other APIs. |
| `configurable=<boolean>` | Defines if a view can be configured. Some view areas can not be configured and are thus unable to be changed with regards to geometry, etc. |
| `rectangularGeometry=<object>` | Defines a geometry for the view area as a rectangle related to the canvas. This is only listed if the geometry of the view area can be configured. |
| `rectangularGeometry.horizontalOffset=<unsigned int>` | Defines the offset of left edge of the rectangle relative to the left edge of the canvas. |
| `rectangularGeometry.horizontalSize=<unsigned int>` | Defines the width of the rectangle. |
| `rectangularGeometry.verticalOffset=<unsigned int>` | Defines the offset of the top edge of the rectangle relative to the top edge of the canvas. |
| `rectangularGeometry.verticalSize=<unsigned int>` | Defines the height of the rectangle. |
| `canvasSize=<object>` | Defines the size of the overview image that the view area geometry is defined on. This is only listed if the geometry of the view area can be configured. |
| `canvasSize.horizontal=<unsigned int>` | Defines the width of the canvas. |
| `canvasSize.vertical=<unsigned int>` | Defines the height of the canvas. |
| `minSize=<object>` | Defines the minimum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `minSize.horizontal=<unsigned int>` | Defines the minimum width of a view area. |
| `minSize.vertical=<unsigned int>` | Defines the minimum height of the view area. |
| `maxSize=<object>` | Defines the maximum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `maxSize.horizontal=<unsigned int>` | Defines the maximum width of a view area. |
| `maxSize.vertical=<unsigned int>` | Defines the maximum height of the view area. |
| `grid=<object>` | Defines the grid that a geometry is applied to on the canvas due to device limitations. This is only listed if the geometry of the view area can be configured. |
| `grid.horizontalOffset=<unsigned int>` | Defines the offset of the first vertical grid line relative to the left edge of the canvas. |
| `grid.horizontalSize=<unsigned int>` | Defines the distance between vertical grid lines. |
| `grid.verticalOffset=<unsigned int>` | Defines the offset of the first horizontal grid line relative to the top edge of the canvas. |
| `grid.verticalSize=<unsigned int>` | Defines the distance between horizontal grid lines. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

Method specific errors

| Code | Description |
| --- | --- |
| `200` | Invalid view area ID |
| `201` | View area is not configurable |
| `202` | Invalid geometry |

See [General error codes](#general-error-codes) for a complete list of error codes.

### resetGeometry

This API method is used when you want to restore the geometry of a view area back to its default values.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/configure.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetGeometry",  "params": {    "viewArea": {      "id": <unsigned int>    }  }}'
```

```bash
POST /axis-cgi/viewarea/configure.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetGeometry",  "params": {    "viewArea": {      "id": <unsigned int>    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used in the request. |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="resetGeometry"` | The operation that should be performed. |
| `params=<object>` | Contains the data of the request. |
| `viewArea=<object>` | Contains the view area data of the request. |
| `id=<unsigned int>` | Identifies the area that should be configured. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "resetGeometry",  "data": {    "viewAreas": \[      {        "id": <unsigned int>,        "source": <unsigned int>,        "camera": <unsigned int>,        "configurable": <boolean>,        "rectangularGeometry": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }        "canvasSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "minSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "maxSize": {          "horizontal": <unsigned int>,          "vertical": <unsigned int>        },        "grid": {          "horizontalOffset": <unsigned int>,          "horizontalSize": <unsigned int>,          "verticalOffset": <unsigned int>,          "verticalSize": <unsigned int>        }      }    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that was used in the request. |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="resetGeometry"` | The operation that was performed. |
| `data=<object>` | The data of the response. |
| `viewAreas=<object>` | The view data configurations of the response. |
| `id=<unsigned int>` | Identifies the view area. |
| `source=<unsigned int>` | Identifies the image source that is used to create the view areas. |
| `camera=<unsigned int>` | Identifies the view area used by streaming, PTZ and other APIs. |
| `configurable=<boolean>` | Defines if a view can be configured. Some view areas can not be configured and are thus unable to be changed with regards to geometry, etc. |
| `rectangularGeometry=<object>` | Defines a geometry for the view area as a rectangle related to the canvas. This is only listed if the geometry of the view area can be configured. |
| `rectangularGeometry.horizontalOffset=<unsigned int>` | Defines the offset of left edge of the rectangle relative to the left edge of the canvas. |
| `rectangularGeometry.horizontalSize=<unsigned int>` | Defines the width of the rectangle. |
| `rectangularGeometry.verticalOffset=<unsigned int>` | Defines the offset of the top edge of the rectangle relative to the top edge of the canvas. |
| `rectangularGeometry.verticalSize=<unsigned int>` | Defines the height of the rectangle. |
| `canvasSize=<object>` | Defines the size of the overview image that the view area geometry is defined on. This is only listed if the geometry of the view area can be configured. |
| `canvasSize.horizontal=<unsigned int>` | Defines the width of the canvas. |
| `canvasSize.vertical=<unsigned int>` | Defines the height of the canvas. |
| `minSize=<object>` | Defines the minimum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `minSize.horizontal=<unsigned int>` | Defines the minimum width of a view area. |
| `minSize.vertical=<unsigned int>` | Defines the minimum height of the view area. |
| `maxSize=<object>` | Defines the maximum size that a view area can have. This is only listed if the geometry of the view area can be configured. |
| `maxSize.horizontal=<unsigned int>` | Defines the maximum width of a view area. |
| `maxSize.vertical=<unsigned int>` | Defines the maximum height of the view area. |
| `grid=<object>` | Defines the grid that a geometry is applied to on the canvas due to device limitations. This is only listed if the geometry of the view area can be configured. |
| `grid.horizontalOffset=<unsigned int>` | Defines the offset of the first vertical grid line relative to the left edge of the canvas. |
| `grid.horizontalSize=<unsigned int>` | Defines the distance between vertical grid lines. |
| `grid.verticalOffset=<unsigned int>` | Defines the offset of the first horizontal grid line relative to the top edge of the canvas. |
| `grid.verticalSize=<unsigned int>` | Defines the distance between horizontal grid lines. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": <string>,  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

Method specific errors

| Code | Description |
| --- | --- |
| `200` | Invalid view area ID |
| `201` | View area is not configurable |

See [General error codes](#general-error-codes) for a complete list of error codes.

### getSupportedVersions

This API method is used when you want to retrieve a list of supported API versions.

**Request `/axis-cgi/viewarea/info.cgi`**

-   **Security level**: Viewer

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/info.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/viewarea/info.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The operation that should be performed. |

**Request `/axis-cgi/viewarea/configure.cgi`**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/viewarea/configure.cgi" \\  --data '{  "context": "<string>",  "method": getSupportedVersions"}'
```

```bash
POST /axis-cgi/viewarea/configure.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The user sets this value and the application echoes it back in the response (optional). |
| `method="getSupportedVersions"` | The operation that should be performed. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Request body syntax

```bash
{    "context": "<string>",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]    }}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context that was used when the request was made (optional). |
| `method="getSupportedVersions"` | The operation that was performed. |
| `data.apiVersions[]=<list of versions>` | A list of supported API versions that includes all major versions along with their highest supported minor version. |
| `<list of versions>` | List of "<Major>.<Minor>" versions, e.g. \["1.4", "2.5"\] |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

**Error codes**

See [General error codes](#general-error-codes) for a complete list of error codes.

### General error codes

This table lists the errors that can occur for any API method. Method specific errors are listed under specific chapters.

| Code | Description |
| --- | --- |
| `101` | The requested API version is not supported |
| `102` | Method unsupported |
| `103` | Internal error |