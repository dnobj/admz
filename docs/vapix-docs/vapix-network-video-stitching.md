---
title: Stitching
url: "https://developer.axis.com/vapix/network-video/stitching/"
category: vapix
subcategory: network-video
sha256: 176070cc9e00940830287fcb2b4a5c0b88a455fe0ea812c6eec8361ab937109a
scraped_at: "2026-01-09T15:21:06.152Z"
page_height: 79923
---

# Stitching

## Description

The Stitching API documentation introduces you to the steps that lets you set the blending amount and parallax compensation distance in order to reach optimized alignment in a panoramic video stream. By using this API you will also be able to align the sensor images in a panoramic view in the event that one or several sensors have been moved from their original position.

### Model

The API implements `/axis-cgi/stitching.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| `getSupportedVersions` | Retrieves API versions supported by your device. |
| `getCapabilities` | Retrieves stitching capabilities available on your device. |
| `getBlendingAmount` | Retrieves the current blending amount. |
| `setBlendingAmount` | Sets the blending amount. |
| `getParallaxCompensationDistance` | Retrieves the current distance to an object. |
| `setParallaxCompensationDistance` | Sets the distance to an object (in meters). |
| `rotateAngle` | Rotates a sensor ID. |
| `restore` | Restores a sensor ID to the factory default setting, i.e. removes all changes made with: `setBlendingAmount` `setParallaxCompensationDistance` `rotateAngle` |
| `getHorizonStraighteningProperties` | Retrieves the value of horizon straightening tilt, if horizon straightening stretch is enabled, and the stretch amount. |
| `setHorizonStraighteningEnabled` | Enables or disables horizon straightening. |
| `getHorizonStraighteningEnabled` | Retrieves if horizon straightening is enabled. |
| `setHorizonStraighteningTilt` | Sets horizon straightening tilt to make the straight horizon not in the middle of the image. |
| `setHorizonStraighteningStretchEnabled` | Enables or disables horizon straightening stretch. |
| `setHorizonStraighteningStretchAmount` | Sets the horizon straightening stretch amount. |
| `getFieldOfView` | Retrieves the value of horizontal and vertical field of view. |
| `setStitchingEnabled` | Enables stitching. This method is product dependent. |
| `getStitchingEnabled` | Checks if stitching has been enabled. This method is product dependent. |

### Identification

-   **API Discovery**: `id=stitching`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Retrieve supported API versions and capabilities

Use these examples to retrieve a list of API versions and information about what parts of the `/axis-cgi/stitching.cgi` are supported by your device.

#### Retrieve supported API versions

1.  Request a list containing the API versions supported by your device.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "context": "abc",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "context": "abc",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.0", "2.1", "3.0"\]    }}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getSupportedVersions",    "error": {        "code": 8000,        "message": "Internal error, could not complete request."    }}
```

#### Retrieve supported capabilities

1.  Request a list containing supported `/axis-cgi/stitching.cgi` capabilities.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "getCapabilities"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "getCapabilities"}
```

2.  Parse the JSON response, which should include a list containing the supported methods.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getCapabilities",    "data": {        "capabilities": {            "getBlendingAmount": true,            "setBlendingAmount": true,            "getParallaxCompensationDistance": true,            "setParallaxCompensationDistance": true,            "rotateAngle": true,            "restore": true        },        "limits": {            "blendingAmountMin": 0.0,            "blendingAmountMax": 100.0,            "parallaxCompensationDistanceMin": 1.0,            "parallaxCompensationDistanceMax": 50.0,            "idMin": 0,            "idMax": 3,            "angleMin": -180,            "angleMax": 180        }    }}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getCapabilities",    "error": {        "code": 2003,        "message": "The requested API version is not supported."    }}
```

### Change blending amount

Use these examples to change the blending amount, which makes seams between sensor images appear sharper or blurrier.

#### Retrieve blending amount

1.  Request the current value of the blending amount.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "getBlendingAmount"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "getBlendingAmount"}
```

2.  Parse the JSON response, which should include the current value of the blending amount.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getBlendingAmount",    "data": {        "blendingAmount": 50.0    }}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getBlendingAmount",    "error": {        "code": 2004,        "message": "Method not supported."    }}
```

#### Set blending amount

1.  Set a new blending amount value.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "setBlendingAmount",    "params": {        "blendingAmount": 75.0    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "setBlendingAmount",    "params": {        "blendingAmount": 75.0    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "setBlendingAmount",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "setBlendingAmount",    "error": {        "code": 2004,        "message": "Method not supported."    }}
```

### Change parallax compensation distance

Use these examples to change the parallax compensation distance so that the most important object is aligned around the seams.

#### Retrieve parallax compensation distance

1.  Request the current value of the parallax compensation distance.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "getParallaxCompensationDistance"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "getParallaxCompensationDistance"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getParallaxCompensationDistance",    "data": {        "parallaxCompensationDistance": 10.0    }}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "getParallaxCompensationDistance",    "error": {        "code": 2004,        "message": "Method not supported."    }}
```

#### Set parallax compensation distance

1.  Set the new value for the parallax compensation distance.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "setParallaxCompensationDistance",    "params": {        "parallaxCompensationDistance": 20.0    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "setParallaxCompensationDistance",    "params": {        "parallaxCompensationDistance": 20.0    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "setParallaxCompensationDistance",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "setParallaxCompensationDistance",    "error": {        "code": 2004,        "message": "Method not supported."    }}
```

### Align the sensor images in a panoramic view

Use these examples to align the sensor images in a panoramic view in the event that they have become unaligned.

**Pan the sensor**

1.  Pan sensor 2 by 0.05 degrees.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 2,        "axis": "pan",        "angle": 0.05    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 2,        "axis": "pan",        "angle": 0.05    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
```

**Tilt the sensor**

1.  Tilt sensor 0 by 0.15 degrees.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 0,        "axis": "tilt",        "angle": 0.15    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 0,        "axis": "tilt",        "angle": 0.15    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
```

**Roll the sensor**

1.  Roll sensor 3 by -0.2 degrees.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 3,        "axis": "roll",        "angle": -0.2    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "params": {        "id": 3,        "axis": "roll",        "angle": -0.2    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "rotateAngle",    "error": {        "code": 4001,        "message": "Mandatory input parameter was not found in the input."    }}
```

### Restore settings back to factory default

Use this example to restore the device settings to factory default. This is useful when you have made changes to either the blending amount, parallax compensation distance or alignment in the previous examples and want to return to the original settings.

1.  Undo the current actions on sensor 0 with the `restore` method. This will restore the configuration back to factory default.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.0",    "context": "abc",    "method": "restore",    "params": {        "id": 0    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.0",    "context": "abc",    "method": "restore",    "params": {        "id": 0    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "restore",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.0",    "context": "abc",    "method": "restore",    "error": {        "code": 1000,        "message": "Invalid parameter value."    }}
```

### Enable or disable horizon straightening

Use these examples to enable horizon straightening to make the horizon to be straight, or disable horizon straightening.

#### Enable horizon straightening

1.  Use a supported version to enable horizon straightening.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": true    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": true    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "error": {        "code": 2300,        "message": "Internal vipd error, could not complete request."    }}
```

#### Disable horizon straightening

1.  Use a supported version to disable horizon straightening.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": false    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": false    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningEnabled",    "error": {        "code": 2004,        "message": "Method not supported."    }}
```

### Check if horizon straightening is enabled

Use this example to check if horizon straightening is enabled.

1.  Use a supported version to retrieve horizon straightening.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningEnabled"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningEnabled"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningEnabled",    "data": {        "enabled": true    }}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningEnabled",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

### Change horizon straightening tilt

Use these examples to change the horizon straightening tilt to make the straight horizon not in the middle of the image.

#### Retrieve horizon straightening properties

1.  Request the horizon straightening properties.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "data": {        "horizonStraighteningTilt": 10.0,        "horizonStraighteningStretchEnabled": true,        "horizonStraighteningStretchAmount": 50.0    }}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "error": {        "code": 2215,        "message": "Horizon Straightening is not enabled."    }}
```

#### Set horizon straightening tilt

1.  Set a new value for horizon straightening tilt.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningTilt",    "params": {        "horizonStraighteningTilt": 10    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningTilt",    "params": {        "horizonStraighteningTilt": 10    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningTilt",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningTilt",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

### Enable or disable horizon straightening stretch

Use these examples to enable or disable horizon straightening stretch to hide or show the black areas in the corners of the image.

#### Retrieve horizon straightening properties

1.  Request the horizon straightening properties.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "data": {        "horizonStraighteningTilt": 10.0,        "horizonStraighteningStretchEnabled": true,        "horizonStraighteningStretchAmount": 50.0    }}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "error": {        "code": 2215,        "message": "Horizon Straightening is not enabled."    }}
```

#### Enable horizon straightening stretch

1.  Use a supported version to enable horizon straightening stretch.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": true    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": true    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

#### Disable horizon straightening stretch

1.  Use a supported version to disable horizon straightening stretch.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": false    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": false    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchEnabled",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

### Change horizon straightening stretch amount

Use these examples to change the horizon straightening stretch amount.

#### Retrieve horizon straightening properties

1.  Request the horizon straightening properties.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "data": {        "horizonStraighteningTilt": 10.0,        "horizonStraighteningStretchEnabled": true,        "horizonStraighteningStretchAmount": 50.0    }}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "error": {        "code": 2215,        "message": "Horizon Straightening is not enabled."    }}
```

#### Set horizon straightening stretch amount

1.  Set a new value for horizon straightening stretch amount.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchAmount",    "params": {        "horizonStraighteningStretchAmount": 50    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchAmount",    "params": {        "horizonStraighteningStretchAmount": 50    }}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchAmount",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "setHorizonStraighteningStretchAmount",    "error": {        "code": 2216,        "message": "Horizon Straightening stretch is disabled."    }}
```

### Get horizontal and vertical field of view

Use this example to get the supported horizontal and vertical field of view.

1.  Use a supported version to retrieve supported horizontal and vertical field of view.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getFieldOfView"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getFieldOfView"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getFieldOfView",    "data": {        "hFoV": 180,        "vFoV": 90    }}
```

Error response example

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getFieldOfView",    "error": {        "code": 2003,        "message": "The requested API version is not supported."    }}
```

### Disable the stitching

Use this example to turn off the stitching and instead perform it on the server.

**Enable stitching**

1.  Enable the current stitching value. A supported API version is required to use this method.

```bash
http://<servername>/axis-cgi/stitching.cgi
```

JSON input parameters

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "getStitchingEnabled"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "getStitchingEnabled",    "data": {        "stitchingEnabled": true    }}
```

Error response example

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "getStitchingEnabled",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

**Disable the stitching**

1.  Disable the current stitching value. A supported API version is required to use this method.

```bash
http://<servername>/axis-cgi/stitching.cgi
```

JSON input parameters

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "setStitchingEnabled"}
```

2.  Parse the JSON response.

Successful response example

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "setStitchingEnabled",    "data": {}}
```

Error response example

```bash
{    "apiVersion": "3.4",    "context": "my context",    "method": "setStitchingEnabled",    "error": {        "code": 2213,        "message": "Operation is not supported."    }}
```

## API definition
### getSupportedVersions

This method is used when you want to retrieve a list of API versions supported by your device. The list will consist of the major API versions along with their highest supported minor version. Please note that the version is for the API as a whole, i.e. all methods supported by `/axis-cgi/stitching.cgi`.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "context": "<string>",  "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "getSupportedVersions"}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getSupportedVersions">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \[      <string>,      <string>    \]  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getSupportedVersions"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameter listed below. |
| `apiVersions=<array>` | The supported API versions in the format "Major.Minor", i.e. `1.4` or `2.1`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getSupportedVersions">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getCapabilities

This method is used when you want to retrieve a list of `/axis-cgi/stitching.cgi` methods supported on your device.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "getCapabilities"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "getCapabilities"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getCapabilities">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getCapabilities",  "data": {    "capabilities": {      "getBlendingAmount": <boolean>,      "setBlendingAmount": <boolean>,      "getParallaxCompensationDistance": <boolean>,      "setParallaxCompensationDistance": <boolean>,      "rotateAngle": true,      "restore": true,      "setHorizonStraighteningEnabled": <boolean>,    },    "limits": {      "blendingAmountMin": <number>,      "blendingAmountMax": <number>,      "parallaxCompensationDistanceMin": <number>,      "parallaxCompensationDistanceMax": <number>,      "idMin": <number>,      "idMax": <number>,      "angleMin": <number>,      "angleMax": <number>    }  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getCapabilities"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `capabilities=<JSON object>` | Container for the method support responses. |
| `getBlendingAmount=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setBlendingAmount=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `getParallaxCompensationDistance=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setParallaxCompensationDistance=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `rotateAngle=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `restore=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setHorizonStraighteningEnabled=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `getHorizonStraighteningEnabled=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `getHorizonStraighteningProperties=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setHorizonStraighteningTilt=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setHorizonStraighteningStretchEnabled=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setHorizonStraighteningStretchAmount` | Value can be either `true` or `false` depending on if the method is supported. |
| `getFieldOfView=<boolean>` | Value can be either `true` or `false` depending on if the method is supported. |
| `setStitchingEnabled` | Value can be either `true` or `false` depending on if the method is supported. |
| `getStitchingEnabled` | Value can be either `true` or `false` depending on if the method is supported. |
| `limits=<JSON object>` | Container for the limits responses. |
| `blendingAmountMin=<number>` | The minimum blending amount value used for `setBlendingAmount`. |
| `blendingAmountMax=<number>` | The maximum blending amount value used for `setBlendingAmount`. |
| `parallaxCompensationDistanceMin=<number>` | The minimum parallax compensation distance value used for `setParallaxCompensationDistance`. |
| `parallaxCompensationDistanceMax=<number>` | The maximum parallax compensation distance value used for `setParallaxCompensationDistance`. |
| `idMin=<number>` | The minimum id value used for `rotateAngle` and `restore`. |
| `idMax=<number>` | The maximum id value used for `rotateAngle` and `restore`. |
| `angleMin=<number>` | The minimum angle value used for `rotateAngle` . |
| `angleMax=<number>` | The maximum angle value used for `rotateAngle` . |
| `horizonStraighteningTiltMin=<number>` | The minimum value used for `setHorizonStraighteningTilt`. |
| `horizonStraighteningTiltMax=<number>` | The maximum value used for `setHorizonStraighteningTilt`. |
| `horizonStraighteningStretchMin<number>` | The minimum value used for `setHorizonStraighteningStretchAmount`. |
| `horizonStraighteningStretchMax=<number>` | The maximum value used for `setHorizonStraighteningStretchAmount`. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getCapabilities",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getCapabilities">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getBlendingAmount

This method is used when you want to return the current blending amount value.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "getBlendingAmount"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "getBlendingAmount"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getBlendingAmount">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getBlendingAmount",  "data": {    "blendingAmount": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getBlendingAmount"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `blendingAmount=<number>` | The returned value that specifies the current amount of blurriness around the image seams. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getBlendingAmount",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getBlendingAmount">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setBlendingAmount

This method is used when you want to set a new blending amount value. Changing this value is useful when there are differences in the white balance between sensors.

It is generally a good idea to set the blending amount to 0 when there is only one object at the same distance as the parallax compensation distance around the seams. This will add a sharp transition between seams, however, in cases where there are many different objects at different distances around the seams it is usually better to increase the blending amount. Doing this will blur our any skewered alignments that might occur around the seams.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "setBlendingAmount"  "params": {    "blendingAmount": <number>  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "setBlendingAmount"  "params": {    "blendingAmount": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"setBlendingAmount">` | The requested method. |
| `params=<JSON object>` | Container for method specific parameters. |
| `blendingAmount=<number>` | Specifies the new value with a range between 0–100. The value can be entered as a `<number>` and when using decimals only the 15 first are used. `0` = sharp edges with no blurriness. `100` = maximum blurriness. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setBlendingAmount",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setBlendingAmount"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setBlendingAmount",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setBlendingAmount">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2204` | Failed to apply blending. |
| `2214` | Blending is disabled. |

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getParallaxCompensationDistance

This method is used when you want to retrieve the value for the parallax compensation distance.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "getParallaxCompensationDistance"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "getParallaxCompensationDistance"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getParallaxCompensationDistance">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getParallaxCompensationDistance",  "data": {    "parallaxComensationDistance": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getParallaxCompensationDistance"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameter listed below. |
| `parallaxCompensationDistance=<number>` | The returned value where the alignment is currently being calculated, measured in meters. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getParallaxCompensationDistance",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getParallaxCompensationDistance">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setParallaxCompensationDistance

This method is used when you want to set a new value for the parallax compensation distance.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "setParallaxCompensationDistance"  "params": {    "parallaxCompensationDistance": <number>  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "setParallaxCompensationDistance"  "params": {    "parallaxCompensationDistance": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"setParallaxCompensationDistance">` | The requested method. |
| `params=<JSON object>` | Container for the method specific parameter below. |
| `parallaxCompensationDistance=<number>` | Specifies the distance to the objects in meters. The distance is where the alignment between the seams will be calculated with a value between 1–50 entered as a `<number>`. Please note that only the first 15 decimals can be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setParallaxCompensationDistance",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setParallaxCompensationDistance"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setParallaxCompensationDistance",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setParallaxCompensationDistance">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### rotateAngle

This method is used when you want to align the sensor images in the panoramic view to improve the stitching effect.

Each sensor can rotate on the "pan", "tilt" and "roll" axis. The hard limits of the angles can’t exceed -180 to +180 degrees, but there are lower soft limits that are product and sensor dependent. AXIS Q3819–PVE for example, has a soft limit of ± 1.4 degrees when using pan. Exceeding these limits can cause unknown behavior in the image.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "rotateAngle"  "params": {    "id": <number>,    "axis": <string>,    "angle": <number>  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "rotateAngle"  "params": {    "id": <number>,    "axis": <string>,    "angle": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"rotateAngle">` | The requested method. |
| `params=<JSON object>` | Container for the method specific parameter below. |
| `id=<number>` | Specifies what sensor image that should be rotated. Valid range is 0 to the number of sensors minus 1. |
| `axis=<string>` | Specifies which axis that should be rotated. Valid values are "pan", "tilt" and "roll". |
| `angle=<number>` | Specifies how many degrees the axis should be rotated for a chosen sensor id. The value can be entered as <number> with valid values between -180 to +180. Please note that if you are using decimals, only the first 15 are used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "rotateAngle",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="rotateAngle"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "rotateAngle",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"rotateAngle">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### restore

This method is used when you want to reset the alignment, parallax compensation distance or blending amount to the unit specific default settings.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "restore"  "params": {    "id": <number>,  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "restore"  "params": {    "id": <number>,  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"restore">` | The requested method. |
| `params=<JSON object>` | Container for the method specific parameter below. |
| `id=<number>` | Specifies what sensor image that should be restored. Valid range is 0 to the number of sensors minus 1. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "restore",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="restore"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "restore",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"restore">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setHorizonStraighteningEnabled

Use this method to enable or disable horizon straightening.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": <boolean>    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningEnabled",    "params": {        "horizonStraighteningEnabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method="setHorizonStraighteningEnabled"` | The requested method. |
| `params=<JSON object>` | Container for method specific parameters. |
| `horizonStraighteningEnabled=<boolean>` | `true`: Enable horizon straightening.  
`false`: Disable horizon straightening. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningEnabled",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setHorizonStraighteningEnabled"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningEnabled",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setHorizonStraighteningEnabled">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2300` | Internal vipd error, could not complete request. |

### getHorizonStraighteningEnabled

Use this method to retrieve if the horizon straightening is enabled.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": <string>,    "context": "<string>",    "method": "getHorizonStraighteningEnabled"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": <string>,    "context": "<string>",    "method": "getHorizonStraighteningEnabled"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getHorizonStraighteningEnabled">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": "<string>",    "method": "getHorizonStraighteningEnabled",    "data": {        "enabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getHorizonStraighteningEnabled"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `enabled=<boolean>` | `true`: Horizon straightening is enabled.  
`false`: Horizon straightening is not enabled. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": "<string>",    "method": "getHorizonStraighteningEnabled",    "error": {        "code": <number>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getHorizonStraighteningEnabled">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getHorizonStraighteningProperties

Use this method to retrieve the value of horizon straightening tilt, if horizon straightening stretch is enabled, and the stretch amount.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getHorizonStraighteningProperties">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "data": {        "horizonStraighteningTilt": 10.0,        "horizonStraighteningStretchEnabled": true,        "horizonStraighteningStretchAmount": 50.0    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getHorizonStraighteningProperties"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `horizonStraighteningTilt=<number>` | The current value of the straight horizon position. |
| `horizonStraighteningStretchEnabled=<boolean>` | Whether the image is stretched over the black areas. |
| `horizonStraighteningStretchAmount=<number>` | The returned value shows how the stretching is performed. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": "3.2",    "context": "my context",    "method": "getHorizonStraighteningProperties",    "error": {        "code": 2215,        "message": "Horizon Straightening is not enabled."    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getHorizonStraighteningProperties">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2215` | Horizon straightening is not enabled. |

### setHorizonStraighteningTilt

Use this method to set the position of the straight horizon.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningTilt"  "params": {    "horizonStraighteningTilt": <number>  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningTilt"  "params": {    "horizonStraighteningTilt": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"setHorizonStraighteningTilt">` | The requested method. |
| `params=<JSON object>` | Container for the method specific parameter below. |
| `horizonStraighteningTilt=<number>` | Specifies the position of the straight horizon in angles relative to the middle of the image. Please note that only the first 15 decimals can be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningTilt",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setHorizonStraighteningTilt"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningTilt",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setHorizonStraighteningTilt">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2215` | Horizon straightening is not enabled. |

### setHorizonStraighteningStretchEnabled

Use this method to enable or disable horizon straightening stretch.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": <boolean>    }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningStretchEnabled",    "params": {        "horizonStraighteningStretchEnabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method="setHorizonStraighteningStretchEnabled"` | The requested method. |
| `params=<JSON object>` | Container for method specific parameters. |
| `horizonStraighteningStretchEnabled=<boolean>` | `true`: Enable horizon straightening stretch.  
`false`: Disable horizon straightening stretch. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": "<string>",    "method": "setHorizonStraighteningStretchEnabled",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setHorizonStraighteningStretchEnabled"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningStretchEnabled",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setHorizonStraighteningStretchEnabled">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2215` | Horizon straightening is not enabled. |

### setHorizonStraighteningStretchAmount

Use this method to set a value of horizon straightening stretch amount.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningStretchAmount"  "params": {    "horizonStraighteningStretchAmount": <number>  }}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningStretchAmount"  "params": {    "horizonStraighteningStretchAmount": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"setHorizonStraighteningStretchAmount">` | The requested method. |
| `params=<JSON object>` | Container for method specific parameters. |
| `horizonStraighteningStretchAmount=<number>` | Specifies the new value with a range between 0–100. `0` = Stretch images non-linearly. `100` = Stretch images linearly. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningStretchAmount",  "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setHorizonStraighteningStretchAmount"` | The requested method. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "setHorizonStraighteningStretchAmount",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setHorizonStraighteningStretchAmount">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

| Code | Description |
| --- | --- |
| `2215` | Horizon straightening is not enabled. |
| `2216` | Horizon Straightening stretch is disabled. |

### getFieldOfView

Use this method to retrieve the supported horizontal and vertical field of view.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/stitching.cgi" \\  --data '{  "apiVersion": <string>,  "context": "<string>",  "method": "getFieldOfView"}'
```

```bash
POST /axis-cgi/stitching.cgiHost: <servername>Content-Type: application/json{  "apiVersion": <string>,  "context": "<string>",  "method": "getFieldOfView"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getFieldOfView">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getFieldOfView",  "data": {    "hFoV": <number>,    "vFoV": <number>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getFieldOfView"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `hFoV=<number>` | The supported horizontal field of view. |
| `vFoV=<number>` | The supported vertical field of view. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getFieldOfView",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getFieldOfView">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getStitchingEnabled

Use this method to retrieve the most recent stitching status set by `setStitchingEnabled` Can be either enabled or disabled.

**Request**

-   **Security level**: Administrator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
http://<servername>/axis-cgi/stitching.cgi
```

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getStitchingEnabled"}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"getStitchingEnabled">` | The requested method. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": <string>,    "method": "getStitchingEnabled",    "data": {        "stitchingEnabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="getStitchingEnabled"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `stitchingEnabled=<boolean>` | The returned value that specifies if stitching is enabled. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": <string>,  "context": "<string>",  "method": "getStitchingEnabled",  "error": {    "code": <number>,    "message": <string>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"getStitchingEnabled">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setStitchingEnabled

Use this method to retrieve enable or disable the stitching mechanic.

**Request**

-   **Security level**: Administrator
-   **Method**: `POST`
-   **Content-Type**: `application/json`

```bash
http://<servername>/axis-cgi/stitching.cgi
```

```bash
{    "apiVersion": <string>,    "context": <string>,    "method": "setStitchingEnabled",    "params": {        "stitchingEnabled": <boolean>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version that should be used. |
| `context=<string>` | The context set by the user and echoed in the response (optional). |
| `method=<"setStitchingEnabled">` | The requested method. |
| `params=<JSON object>` | Container for method specific parameters. |
| `stitchingEnabled=<boolean>` | Specifies if stitching should be enabled. Valid values are `true` or `false`. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": <string>,    "method": "setStitchingEnabled",    "data": {}}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method="setStitchingEnabled"` | The requested method. |
| `data=<JSON object>` | Container for the response specific parameters listed below. |
| `stitchingEnabled=<boolean>` | The returned value that specifies if stitching is enabled. |
| `data=<JSON object>` | Container for the response. |

**Return value - Failure**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{    "apiVersion": <string>,    "context": <string>,    "method": "setStitchingEnabled",    "error": {        "code": <number>,        "message": <string>    }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion=<string>` | The API version returned from the request. |
| `context=<string>` | The context set by the user in the request (optional). |
| `method=<"setStitchingEnabled">` | The requested method. |
| `error.code=<integer error code>` | The error code. |
| `error.message=<string>` | The error message for the corresponding error code. |

**Error codes**

See [General error codes](#general-error-codes) for a complete list of potential errors.

### General error codes

This table lists the errors that can occur for all CGI methods. Method specific errors are listed under their respective API specification.

| Code | Description |
| --- | --- |
| `1000` | Invalid parameter value. |
| `2000` | Failed to allocate memory. |
| `2004` | Method not supported. |
| `2200` | Unknown error has occurred. |
| `2201` | Failed to init transformation tables. |
| `2202` | Failed to generate table with given parameters. |
| `2203` | Failed to apply table with given parameters. |
| `2205` | Failed read calibration file. |
| `2206` | Calibration file is missing. |
| `2207` | Failed to unlink calibration file. |
| `2208` | Unsupported stitching mode. |
| `2209` | Failed to read configuration file. |
| `2210` | Failed to save configuration file. |
| `2211` | Failed to parse configuration file. |
| `2212` | Method is not allowed in disabled mode. |
| `2213` | Operation is not supported. |
| `2300` | Internal vipd error, could not complete request. |
| `4001` | Mandatory input parameters was not found in the input. |
| `4002` | The type of a provided JSON parameter was incorrect. |
| `8000` | Internal error, could not complete request. |
| `8002` | Generic error. |