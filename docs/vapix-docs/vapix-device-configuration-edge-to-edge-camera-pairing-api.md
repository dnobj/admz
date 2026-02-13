---
title: Edge-to-edge camera pairing API
url: "https://developer.axis.com/vapix/device-configuration/edge-to-edge-camera-pairing-api/"
category: vapix
subcategory: device-configuration
sha256: fb923e653f74b27e63156945fcb5892b73f18f0ae313eaa61d0a7f0e6fe79349
scraped_at: "2026-01-09T15:18:45.735Z"
page_height: 13282
---

# Edge-to-edge camera pairing API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in BETA stage and provided for testing purposes. It is subject to backward-incompatible changes, including modifications to its functionality, behavior and availability. The API should not be used in production environments.

## Overview

With the edge-to-edge camera pairing API, you can pair your device to an external camera to view video from the external camera on your device.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Pair an external camera to a device

This example shows how to pair an external camera to a device. Currently you can only add one camera pairing.

Example request

```bash
curl -X 'POST' \\  '/config/rest/camera-pairing/v1beta/camerapairings' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": {    "address": "string",    "description": "string",    "password": "string",    "streamingprotocol": "SRTSP",    "username": "string",    "verifycertificate": true  }}'
```

Example successful response

info

`password` is not included in the response for security reasons.

```bash
{    "status": "success",    "data": {        "address": "string",        "description": "string",        "id": "CameraPairing-1717587392-934150",        "productmodel": "I7010-VE",        "productname": "AXIS I7010-VE Network Intercom",        "status": "Paired",        "streamingprotocol": "SRTSP",        "username": "string",        "verifycertificate": true    }}
```

Example failure response

```bash
{    "error": {        "code": 0,        "message": "string"    },    "status": "string"}
```

### Unpair an external camera from a device

This example shows how to unpair an external camera from a device by specifying the ID of the camera pairing.

Example request

```bash
curl -X 'DELETE' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717585565-843505' \\  -H 'accept: application/json'
```

Example successful response

```bash
{    "status": "success"}
```

Example failure response

```bash
{    "error": {        "code": 0,        "message": "string"    },    "status": "string"}
```

### Get current camera pairing settings

This example shows how to get the current camera pairing settings by specifying the ID of the camera pairing.

Example request

```bash
'/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717587844-211730' \\  -H 'accept: application/json'
```

Example successful response

```bash
{    "status": "success",    "data": {        "address": "string",        "description": "string",        "id": "CameraPairing-1717587844-211730",        "productmodel": "I7010-VE",        "productname": "AXIS I7010-VE Network Intercom",        "status": "Paired",        "streamingprotocol": "SRTSP",        "username": "string",        "verifycertificate": true    }}
```

Example failure response

```bash
{    "error": {        "code": 0,        "message": "string"    },    "status": "string"}
```

### Modify an existing camera pairing

This example shows how to modify the address, username, password, description, streamingprotocol, and verifycertificate of the current camera pairing. You need to specify the ID of the camera pairing and the property you want to modify.

Example request to modify the address

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717585565-843505/address' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": "string"}'
```

Example request to modify the username

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717585565-843505/username' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": "string"}'
```

Example request to modify the password

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717585565-843505/password' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": "string"}'
```

Example request to modify the description

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1731406548-55051/description' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": "string"}'
```

Example request to modify the streamingprotocol setting

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1731406548-55051/streamingprotocol' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": "SRTSP"}'
```

Example request to modify the verifycertificate setting

```bash
curl -X 'PATCH' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1731406548-55051/verifycertificate' \\  -H 'accept: application/json' \\  -H 'Content-Type: application/json' \\  -d '{  "data": true}'
```

Example successful response

```bash
{    "status": "success"}
```

Example failure response

```bash
{    "error": {        "code": 0,        "message": "string"    },    "status": "string"}
```

### Get current camera pairing status

This example shows how to get the current status of the camera pairing by specifying the ID of the camera pairing.

Example request

```bash
curl -X 'GET' \\  '/config/rest/camera-pairing/v1beta/camerapairings/CameraPairing-1717585565-843505/status' \\  -H 'accept: application/json'
```

Example successful response

```bash
{    "status": "success",    "data": "string"}
```

info

If `Error` is returned, use [Get current camera pairing settings](#get-current-camera-pairing-settings) to get more information about the error.

Example failure response

```bash
{    "error": {        "code": 0,        "message": "string"    },    "status": "string"}
```

## API definition
### Structure

```bash
camera-pairing.v1 (Root Entity)    camerapairings (Entity Collection)        address (Property)        description (Property)        id (Property)        password (Property)        productmodel (Property)        productname (Property)        status (Property)        streamingprotocol (Property)        username (Property)        verifycertificate (Property)
```

### Entities

`camera-pairing.v1`

-   **Description:** The configuration of edge-to-edge camera pairing.
-   **Type:** Singleton
-   **Operation:**
    -   `GET`
-   **Attributes:**
    -   Dynamic support: No

`camera-pairing.v1.camerapairings`

-   **Description:** Camera pairing
-   **Type**: Collection (Key property: `id`)
-   **Operation:**
    -   `GET`
    -   `ADD` (Permissions: admin)
        -   Required properties: `address`, `username`, `password`, `streamingprotocol`, `verifycertificate`, `description`
    -   `REMOVE` (Permissions: admin)

#### Properties

`id`

-   **Description:** The unique ID generated automatically for the camera pairing.
-   **Datatype:** ID
-   **Operations:**
    -   `GET` (Permissions: admin)

`address`

-   **Description:** Address for the camera pairing.
-   **Datatype:** Address
-   **Operations:**
    -   `SET` (Permissions: admin)
    -   `GET` (Permissions: admin)

`username`

-   **Description:** Username for the camera pairing.
-   **Datatype:** Username
-   **Operations:**
    -   `SET` (Permissions: admin)
    -   `GET` (Permissions: admin)

`password`

-   **Description:** Password for the camera pairing.
-   **Datatype:** Password
-   **Operations:**
    -   `SET` (Permissions: admin)

`status`

-   **Description:** Current status of the camera pairing.
-   **Datatype:** CameraPairingStatus
-   **Operations:**
    -   `GET` (Permissions: admin)

`streamingprotocol`

-   **Description:** Streaming protocol used for the camera pairing (RTSP or SRTSP).
    -   When `SRTSP` is set, you can specify `verifycertificate` to
        -   `true` to verify the certificate
        -   `false` to ignore the certificate verification, for example for self-signed certificates
    -   When `RTSP` is set, `verifycertificate` will be ignored.
-   **Datatype:** CameraPairingStreamingProtocol
-   **Operations:**
    -   `SET` (Permissions: admin)
    -   `GET` (Permissions: admin)

`verifycertificate`

-   **Description:** Indicates whether to verify the certificates. It is only useful when `streamingprotocol` is set to `SRTSP`.
-   **Datatype:** boolean
-   **Operations:**
    -   `SET` (Permissions: admin)
    -   `GET` (Permissions: admin)

`productmodel`

-   **Description:** The product model of the paired camera.
-   **Datatype:** ProductModel
-   **Operations:**
    -   `GET` (Permissions: admin)

`productname`

-   **Description:** The full product name of the paired camera.
-   **Datatype:** ProductName
-   **Operations:**
    -   `GET` (Permissions: admin)

`description`

-   **Description:** Description of the paired camera.
-   **Datatype:** Description
-   **Operations:**
    -   `SET` (Permissions: admin)
    -   `GET` (Permissions: admin)

### Data types
#### Address

```bash
{    "description": "Address for the camera pairing",    "maxLength": 64,    "type": "string"}
```

#### Username

```bash
{    "description": "Username for the camera pairing",    "maxLength": 64,    "type": "string"}
```

#### Password

```bash
{    "description": "Password for the camera pairing",    "maxLength": 64,    "type": "string"}
```

#### ID

```bash
{    "description": "The unique ID generated automatically for the camera pairing",    "maxLength": 64,    "type": "string"}
```

#### CameraPairingStatus

```bash
{    "description": "Current status of the camera pairing",    "enum": \["NotPaired", "Paired", "Error", "Connecting"\],    "type": "string"}
```

info

-   `NotPaired`: The device is not paired to an external camera.
-   `Paired`: The device is paired to an external camera and the streaming works fine.
-   `Error`: The device is paired to an external camera but there is some problem with the streaming.
-   `Connecting`: The device is connecting to the external camera.

#### CameraPairingStreamingProtocol

```bash
{    "description": "Streaming protocol used for the camera pairing",    "enum": \["RTSP", "SRTSP"\],    "type": "string"}
```

#### ProductModel

```bash
{    "description": "The product model of the paired camera",    "maxLength": 64,    "type": "string"}
```

#### ProductName

```bash
{    "description": "The full product name of the paired camera",    "maxLength": 64,    "type": "string"}
```

#### Description

```bash
{    "description": "Description of the paired camera",    "maxLength": 128,    "type": "string"}
```

### Error codes

| Error code | Error message | Description |
| --- | --- | --- |
| `101` | The specified address is already assigned to the device itself. | Occurs when you try to create a camera pairing to the device itself. |
| `102` | The specified address is not valid. | Occurs when the specified address is not a valid IPv4/IPv6 address, or a DNS name. |
| `104` | Maximum number of camera pairings reached. | Occurs when you try to create a second camera pairing. |
| `106` | Lost connection | Streaming connection is lost. |
| `107` | Unauthorized | Unauthorized streaming. |
| `108` | Could Not Connect | Couldn't connect to streaming. |