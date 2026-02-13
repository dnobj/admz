---
title: Basic Device Info
url: "https://developer.axis.com/vapix/device-configuration/basic-device-info-api/"
category: vapix
subcategory: device-configuration
sha256: aeacf52ac7c0c792d8513f743244ee839c736274739eb6d8871e5102f336cb9d
scraped_at: "2026-01-09T15:18:37.984Z"
page_height: 4104
---

# Basic Device Info

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in BETA stage and provided for testing purposes. It is subject to backward-incompatible changes, including modifications to its functionality, behavior and availability. The API should not be used in production environments.

The VAPIX® Basic Device Info API makes it possible to turn on/off anonymous access to a set of Basic Device Info properties on the device. The access to these properties is currently only possible via the `/axis-cgi/basicdeviceinfo.cgi`.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Get root entity

Here is an example on how to get the root entity.

_Example_

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/basic-device-info/v2beta"
```

```bash
GET /config/rest/basic-device-info/v2betaHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "allowAnonymous": false    }}
```

#### Enable anonymous users to access Basic Device Info

Set the property `basic-device-info.v2beta.allowAnonymous` to `true`. This will enable anonymous access. Set it to `false` to turn off anonymous access. This setting is enabled by default.

_Example_

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/basic-device-info/v2beta/allowAnonymous" \\  --data '{    "data": {        "allowAnonymous": true    }}'
```

```bash
PATCH /config/rest/basic-device-info/v2beta/allowAnonymousHost: <servername>Content-Type: application/json{    "data": {        "allowAnonymous": true    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Get the state of anonymous user access

Retrieve the property `basic-device-info.v2.allowAnonymous`. When `true`, then anonymous access is activated. When `false`, anonymous access has been deactivated.

_Example_

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/basic-device-info/v2beta/allowAnonymous"
```

```bash
GET /config/rest/basic-device-info/v2beta/allowAnonymousHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": true}
```

## Structure

```bash
basic-device-info.v2 (Root Entity)    ├── allowAnonymous (Property)
```

### Entities
#### basic-device-info.v2 (Entity)

-   **Description**: Basic Device Info Root Entity
-   **Type**: Singleton
-   **Operations**
    -   `Get`
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### allowAnonymous

-   **Description**: Allow anonymous users to access the get properties functions
-   **Datatype**: boolean
-   **Operations**
    -   `Get` (**Permissions:** admin, operator, viewer)
    -   `Set` (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.