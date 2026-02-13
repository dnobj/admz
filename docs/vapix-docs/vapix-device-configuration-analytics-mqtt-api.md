---
title: Analytics MQTT API
url: "https://developer.axis.com/vapix/device-configuration/analytics-mqtt-api/"
category: vapix
subcategory: device-configuration
sha256: 3d404d2ae6af04b79bfde341bd16756b7d2d24aaf150cfd7212f95be3e38f22f
scraped_at: "2026-01-09T15:18:36.580Z"
page_height: 8241
---

# Analytics MQTT API

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Overview

There are internal producers of analytics data on the camera, known as "analytics data sources". The Analytics MQTT API allows you to create publishers to send analytics data from these sources to the specified MQTT (Message Queuing Telemetry Transport) topics.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Get available analytics data sources

This example shows how to get all analytics data sources available for sending data over MQTT.

JSON request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/analytics-mqtt/v1/data\_sources"
```

```bash
GET /config/rest/analytics-mqtt/v1/data\_sourcesHost: <servername>Content-Type: application/json
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "data\_sources": \[            {                "key": "com.axis.analytics\_scene\_description.v0.beta#1"            },            {                "key": "com.axis.consolidated\_track.v1.beta#1"            },            {                "key": "some\_other\_structure#other\_information=value1"            }        \]    }}
```

#### Add a publisher

This example shows how to add a publisher that sends data from the analytics data source over MQTT.

JSON request:

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/analytics-mqtt/v1/publishers" \\  --data '{    "data": {        "id": "my\_publisher",        "data\_source\_key": "com.axis.analytics\_scene\_description.v0.beta#1",        "mqtt\_topic": "my\_mqtt\_topic",        "qos": 0,        "retain": false,        "use\_topic\_prefix": false    }}'
```

```bash
POST /config/rest/analytics-mqtt/v1/publishersHost: <servername>Content-Type: application/json{    "data": {        "id": "my\_publisher",        "data\_source\_key": "com.axis.analytics\_scene\_description.v0.beta#1",        "mqtt\_topic": "my\_mqtt\_topic",        "qos": 0,        "retain": false,        "use\_topic\_prefix": false    }}
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Get existing publishers

This example shows how to get the existing publishers.

JSON request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/analytics-mqtt/v1/publishers"
```

```bash
GET /config/rest/analytics-mqtt/v1/publishersHost: <servername>Content-Type: application/json
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "id": "my\_publisher",            "key": "com.axis.analytics\_scene\_description.v0.beta#1",            "mqtt\_topic": "my\_mqtt\_topic",            "qos": 0,            "retain": false,            "use\_topic\_prefix": false        },        {            "id": "another\_publisher",            "key": "com.axis.analytics\_scene\_description.v0.beta#1",            "mqtt\_topic": "my\_other\_mqtt\_topic",            "qos": 1,            "retain": true,            "use\_topic\_prefix": false        }    \]}
```

### Delete a publisher

This example shows how to delete a specified publisher to stop it from sending data over MQTT.

JSON request:

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/analytics-mqtt/v1/publishers/my\_publisher"
```

```bash
DELETE /config/rest/analytics-mqtt/v1/publishers/my\_publisherHost: <servername>Content-Type: application/json
```

JSON response:

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
analytics-mqtt.v1 (Root Entity)    ├── data\_sources (Entity Collection)        ├── key (Property)    ├── publishers (Entity Collection)        ├── data\_source\_key (Property)        ├── id (Property)        ├── mqtt\_topic (Property)        ├── qos (Property)        ├── retain (Property)        ├── use\_topic\_prefix (Property)
```

### Entities
#### analytics-mqtt.v1

-   **Description:** Root entity
-   **Type**: Singleton
-   **Operations:**
    -   Get

#### analytics-mqtt.v1.data\_sources

-   **Description:** The data sources
-   **Type**: Collection (Key property: [key](#analytics-mqttv1data_sourceskey))
-   **Operations:**
    -   Get

##### Properties
###### analytics-mqtt.v1.data\_sources.key

-   **Description:** A key to reference an analytics data source
-   **Data Type:** [data\_source\_key](#data_source_key)
-   **Operations:**
    -   Get
        -   Permissions: admin

#### analytics-mqtt.v1.publishers

-   **Description:** The created publishers
-   **Type**: Collection (Key property: [id](#analytics-mqttv1publishersid))
-   **Operations:**
    -   Get
    -   Add
        -   Permissions: admin
        -   Required properties: `id`, `data_source_key`, `mqtt_topic`
        -   Optional properties: `qos`, `retain`, `use_topic_prefix`
    -   Remove
        -   Permissions: admin

##### Properties
###### analytics-mqtt.v1.publishers.data\_source\_key

-   **Description:** An analytics datasource key
-   **Data Type:** [data\_source\_key](#data_source_key)
-   **Operations:**
    -   Get
        -   Permissions: admin

###### analytics-mqtt.v1.publishers.id

-   **Description:** Publisher identifier
-   **Data Type:** [id](#id)
-   **Operations:**
    -   Get
        -   Permissions: admin

###### analytics-mqtt.v1.publishers.mqtt\_topic

-   **Description:** The MQTT topic
-   **Data Type:** [mqtt\_topic](#mqtt_topic)
-   **Operations:**
    -   Get
        -   Permissions: admin

###### analytics-mqtt.v1.publishers.qos

-   **Description:** The quality of service level
-   **Data Type:** [qos](#qos)
-   **Operations:**
    -   Get
        -   Permissions: admin

###### analytics-mqtt.v1.publishers.retain

-   **Description:** The retain policy
-   **Data Type:** Boolean
-   **Operations:**
    -   Get
        -   Permissions: admin

###### analytics-mqtt.v1.publishers.use\_topic\_prefix

-   **Description:** Use topic prefix, configured in MQTT client
-   **Data Type:** Boolean
-   **Operations:**
    -   Get
        -   Permissions: admin

### Data types
#### data\_source\_key

```bash
{    "description": "An analytics datasource key.",    "maxLength": 128,    "minLength": 3,    "type": "string"}
```

#### id

```bash
{    "description": "Publisher identifier.",    "maxLength": 128,    "minLength": 1,    "type": "string"}
```

#### mqtt\_topic

```bash
{    "description": "The mqtt topic",    "maxLength": 128,    "minLength": 1,    "pattern": "^(\[a-zA-Z0-9\_-\]+)(/\[a-zA-Z0-9\_-\]+)\*$",    "type": "string"}
```

#### qos

```bash
{    "description": "The quality of service level of a publisher",    "enum": \[0, 1, 2\],    "type": "integer"}
```