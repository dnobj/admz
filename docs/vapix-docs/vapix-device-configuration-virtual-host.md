---
title: Virtual Host
url: "https://developer.axis.com/vapix/device-configuration/virtual-host/"
category: vapix
subcategory: device-configuration
sha256: 60e9e21e3770bb7030f7f0422f0a6c706b3af0c56a4a2d1dfa334c89acf86e1f
scraped_at: "2026-01-09T15:19:08.833Z"
page_height: 10347
---

# Virtual Host

The VAPIX® Virtual Host API makes it possible for the user to chose which authentication schemes they wish to use. Supported authentication methods include OpenID Connect, basic and digest authentication.

With this API, the user can create, list, modify and remove virtual hosts.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Create a multiple virtual hosts

By using the `create_virtualHost` action a client can set up multiple different virtual hosts using different authentication schemes. Use the `create_virtualHost` action to set up multiple virtual hosts with different authentication schemes and on separate ports.

The first one will use basic authentication.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1/create\_virtualHost" \\  --data '{    "data": {        "active": true,        "auth\_type": "basic",        "port": 8081,        "server\_name": "example-2"    }}'
```

```bash
POST /config/rest/virtualhost/v1/create\_virtualHostHost: <servername>Content-Type: application/json{    "data": {        "active": true,        "auth\_type": "basic",        "port": 8081,        "server\_name": "example-2"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

The second one will use OpenID Connect.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1/create\_virtualHost" \\  --data '{    "data": {        "active": true,        "auth\_type": "oidc",        "port": 8080,        "server\_name": "example-1"    }}'
```

```bash
POST /config/rest/virtualhost/v1/create\_virtualHostHost: <servername>Content-Type: application/json{    "data": {        "active": true,        "auth\_type": "oidc",        "port": 8080,        "server\_name": "example-1"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

The OpenID Connect authentication need to be set up with its dedicated API (see the [OpenID Connect Setup](/vapix/device-configuration/openid-connect-setup/)).

### List virtual hosts

With the root entity, a client will get a list of all configured virtual hosts.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1"
```

```bash
GET /config/rest/virtualhost/v1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "virtualhosts": \[            {                "active": true,                "auth\_type": "oidc",                "port": 8080,                "server\_name": "example-1"            },            {                "active": true,                "auth\_type": "basic",                "port": 8081,                "server\_name": "example-2"            }        \]    }}
```

### Reconfigure a virtual host

The `SET` operation on a virtual host entity can be used to edit an existing virtual host, such as changing between basic and digest. If the server name is altered, the key for the virtual host will also be changed to the new name.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1/virtualhosts/example-2/port" \\  --data '{    "data": 8082}'
```

```bash
PATCH /config/rest/virtualhost/v1/virtualhosts/example-2/portHost: <servername>Content-Type: application/json{    "data": 8082}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

The change will be visible when listing the virtual hosts.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1"
```

```bash
GET /config/rest/virtualhost/v1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "virtualhosts": \[            {                "active": true,                "auth\_type": "oidc",                "port": 8080,                "server\_name": "example-1"            },            {                "active": true,                "auth\_type": "basic",                "port": 8082,                "server\_name": "example-2"            }        \]    }}
```

### Remove a configured virtual host

The Remove operation on a virtual host entity can be used to remove an already configured virtual host. After it is removed, connections that used that virtual host will no longer be reachable.

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1/virtualhosts/example-2"
```

```bash
DELETE /config/rest/virtualhost/v1/virtualhosts/example-2Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

The change will be visible when listing the virtual hosts.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/virtualhost/v1"
```

```bash
GET /config/rest/virtualhost/v1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "virtualhosts": \[            {                "active": true,                "auth\_type": "oidc",                "port": 8080,                "server\_name": "example-1"            }        \]    }}
```

## API definition
### Structure

```bash
virtualhost.v1 (Root Entity)    ├── create\_virtualHost (Action)    ├── virtualhosts (Entity Collection)        ├── active (Property)        ├── auth\_type (Property)        ├── port (Property)        ├── server\_name (Property)
```

### Entities
#### `virtualhost.v1`

-   **Description**: VirtualHosts management.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties

This entity has no properties.

##### Actions
###### `create_virtualHost`

-   **Description**: Create a virtual host.
-   **Request Datatype**: `create_virtualhost_input`
-   **Response Datatype**: Empty Object
-   **Trigger Permissions**: admin

#### `virtualhost.v1.virtualhosts`

-   **Description**: Modify Virtual Host or delete it.
-   **Type**: Collection (Key Property: `server_name`)
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: active, auth\_type, port, server\_name
    -   **Remove** (**Permissions**: admin)
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### `active`

-   **Description**: Enalble auth type.
-   **Datatype**: `boolean_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `auth_type`

-   **Description**: The name of the authentication schema.
-   **Datatype**: `auth_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `port`

-   **Description**: The port that the auth type will use.
-   **Datatype**: `port_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `server_name`

-   **Description**: Server name for auth type.
-   **Datatype**: `server_name_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

### Data types
#### `auth_type`

-   **Description**: Authentication type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 32
-   **Pattern**: `^(basic|digest|oidc)$`

#### `boolean_type`

-   **Description**: true or false.
-   **Type**: boolean

#### `create_virtualhost_input`

-   **Description**: VirtualHost creation action parameters.
-   **Type**: complex
-   **Fields**
    -   **active**
        -   **Description**: Virtual host state, active or not.
        -   **Type**: `boolean_type`
        -   **Nullable**: No / **Gettable**: No
    -   **auth\_type**
        -   **Description**: Authentication type.
        -   **Type**: `auth_type`
        -   **Nullable**: No / **Gettable**: No
    -   **port**
        -   **Description**: Port number.
        -   **Type**: `port_type`
        -   **Nullable**: No / **Gettable**: No
    -   **server\_name**
        -   **Description**: Server name that vh will be based on.
        -   **Type**: `server_name_type`
        -   **Nullable**: No / **Gettable**: No

#### `port_type`

-   **Description**: port number.
-   **Type**: integer
-   **Minimum Value**: 1
-   **Maximum Value**: 65535

#### `server_name_type`

-   **Description**: Client ID type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 64
-   **Pattern**: `^[A-Za-z0-9-.]+$`