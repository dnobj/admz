---
title: Best Snapshot Configuration API
url: "https://developer.axis.com/vapix/device-configuration/best-snapshot-configuration/"
category: vapix
subcategory: device-configuration
sha256: 79a10bdbde4230823cd70505aad1399261b66bfab9c74270a7e1cd786a3e75c2
scraped_at: "2026-01-09T15:18:39.441Z"
page_height: 4788
---

# Best Snapshot Configuration API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Description

The Best Snapshot Configuration API provides configuration for sending cropped snapshots of objects with metadata from analytics metadata producers, for example, "Analytics Scene Description".

With this API, you can configure:

-   Whether to generate cropped snapshots of objects to be included by analytics metadata producers.
-   Whether the cropped snapshot should have a margin which includes more of the image around the bounding box.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Enable best snapshot with margin

This example shows how to enable best snapshot with margin.

JSON request:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/best-snapshot/v1" \\  --data '{    "data": {        "enabled": true,        "margin": true    }}'
```

```bash
PATCH /config/rest/best-snapshot/v1Host: <servername>Content-Type: application/json{    "data": {        "enabled": true,        "margin": true    }}
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Disable best snapshot

This example shows how to disable best snapshot.

JSON request:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/best-snapshot/v1/enabled" \\  --data '{    "data": false}'
```

```bash
PATCH /config/rest/best-snapshot/v1/enabledHost: <servername>Content-Type: application/json{    "data": false}
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Get best snapshot settings

This example shows how to get and understand the best snapshot settings.

JSON request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/best-snapshot/v1"
```

```bash
GET /config/rest/best-snapshot/v1Host: <servername>Content-Type: application/json
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "enabled": true,        "margin": true    }}
```

-   If the value of `enabled` is `true`, best snapshot is included in the data stream.
-   If the value of `enabled` is `false`, best snapshot is not included in the data stream.
-   If the value of `margin` is `true`, best snapshot includes margins.
-   If the value of `margin` is `false`, best snapshot does not include margins.

## API definition
### Structure

```bash
best-snapshot.v1 (Root Entity)    ├── enabled (Property)    ├── margin (Property)
```

#### Entities
##### best-snapshot.v1

-   **Description:** Root entity
-   **Type**: Singleton
-   **Operations:**
    -   Get
    -   Set
        -   Fields: `enabled`, `margin`

#### Properties
##### best-snapshot.v1.enabled

-   **Description:** Whether to generate cropped snapshots of objects that can be included by downstream analytics metadata producers
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: admin
    -   Set
        -   Permissions: admin

##### best-snapshot.v1.margin

-   **Description:** Whether the cropped snapshot should include more of the image around the object bounding box
-   **Data Type:** boolean
-   **Operations:**
    -   Get
        -   Permissions: admin
    -   Set
        -   Permissions: admin