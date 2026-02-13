---
title: SSH Management
url: "https://developer.axis.com/vapix/device-configuration/ssh-management/"
category: vapix
subcategory: device-configuration
sha256: 89b2f5ac6b7fcbc5bb3d7603387ed353517737d56ea972f52d4a1f87f253209d
scraped_at: "2026-01-09T15:19:05.754Z"
page_height: 8677
---

# SSH Management

The VAPIX® SSH API is used to manage SSH accounts on a device and has methods to:

-   Add an SSH user
-   Retrieve details of SSH users
-   Modify an SSH user
-   Remove an SSH user

info

This API includes sensitive data. You must use a secured channel for the communication transmissions.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Add a new SSH user

Make a request with the following information to create a new SSH user on your device:

-   **User collection**: `ssh.v2.users`
-   **Properties**: `username`, `password` and `comment`

Example

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/ssh/v2/users" \\  --data '{  "data": {    "username": "username1",    "password": "password1",    "comment": "comment1"  }}'
```

```bash
POST /config/rest/ssh/v2/usersHost: <servername>Content-Type: application/json{  "data": {    "username": "username1",    "password": "password1",    "comment": "comment1"  }}
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

Adding a new SSH user also creates a home directory for the user. Note that there is only a small amount of storage available on the device.

### Get all of the SSH users

Make a request with the following information to retrieve all SSH user information from your device:

-   **User collection**: `ssh.v2.users`

This will return an array with the following information:

-   **Properties**: `username` and `comment`

Example

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/ssh/v2/users"
```

```bash
GET /config/rest/ssh/v2/usersHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status: "success",  "data": \[    {      "username": "username1",      "comment": "comment1"    },    {      "username": "username2",      "comment": "comment2"    }  \]}
```

### Get an existing SSH user

Make a request with the following information to retrieve SSH information for a single user from your device:

-   **User collection**: `ssh.v2.users`
-   **Key property**: `username`

This will return the following information:

-   **Properties**: `username` and `comment`

Example

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/ssh/v2/users/username1"
```

```bash
GET /config/rest/ssh/v2/users/username1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "username": "username1",    "comment": "comment1"  }}
```

### Modify an existing SSH user

Make a request with the following information to modify an SSH user on your device:

-   **User collection**: `ssh.v2.users`
-   **Key property**: `username`
-   **Properties**: `password` and `comment`

Example

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/ssh/v2/users/username1" \\  --data '{  "data": {    "password": "newpassword",    "comment": "new comment"  }}'
```

```bash
PATCH /config/rest/ssh/v2/users/username1Host: <servername>Content-Type: application/json{  "data": {    "password": "newpassword",    "comment": "new comment"  }}
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

### Remove an existing SSH user

Make a request with the following information to remove an SSH user from your device:

-   **User collection**: `ssh.v2.users`
-   **Key property**: `username`

Example

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/ssh/v2/users/username1"
```

```bash
DELETE /config/rest/ssh/v2/users/username1Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

Removing an existing SSH user also deletes the corresponding home directory and all of its contents.

## API definition
### Structure

```bash
ssh.v2 (Root Entity)  users (Entity Collection)    comment (Property)    password (Property)    username (Property)
```

#### Entities

**ssh.v2**

-   **Description**: The SSH object
-   **Type**: Singleton
-   **Operations**: `GET`
-   **Attributes**: _Dynamic Support_: No

Version 1 of the SSH object.

_Properties_

This entry has no properties

_Actions_

This entry has no actions.

**ssh.v2.users**

-   **Description**: The SSH users collection
-   **Type**: Collection (Key Property: username)
-   **Operations**:
    -   `GET`
    -   `SET` - _Properties_: password, comment
    -   `ADD` - _Permissions_: admin / _Required properties_: username, password / _Optional properties_: comment
    -   `REMOVE` - _Permissions_: admin
-   **Attributes**: _Dynamic Support_: No

This is the entity collection with SSH users. Each SSH user entity is identified by the key `username`.

_Properties_

_comment_

-   **Description**: The full name or comment of the SSH user
-   **Datatype**: `comment_type`
-   **Operations**: `GET` - _Permissions_: admin | `SET` - _Permissions_: admin
-   **Attributes**:
    -   _Nullable_: No
    -   _Dynamic Support_: No
    -   _Dynamic Enum_: No
    -   _Dynamic Range_: No

The _comment_ is a property in the `ssh.v2.users` entity. It is connected to a `username`. If the _comment_ property is used then it can not be an empty string.

_password_

-   **Description**: The password of the SSH user
-   **Datatype**: `password_type`
-   **Operations**: `SET` - _Permissions_: admin
-   **Attributes**:
    -   _Nullable_: No
    -   _Dynamic Support_: No
    -   _Dynamic Enum_: No
    -   _Dynamic Rang_: No

The _password_ is a property in the `ssh.v2.users` entity. It is connected to a `username`. The _password_ can not be read once set.

_username_

-   **Description**: The user name of the SSH user
-   **Datatype**: `username_type`
-   **Operations**: `GET` - _Permissions_: admin
-   **Attributes**:
    -   _Nullable_: No
    -   _Dynamic Support_: No
    -   _Dynamic Enum_: No
    -   _Dynamic Rang_: No

The _username_ is an unique key property in the `ssh.v2.users` entity. It is used to identify an SSH user in the SSH users collection.

_Actions_

This entry has no actions.

#### Data types

_comment\_type_

-   **Description**: The full name or comment of the SSH user
-   **Type**: `string`
-   **Minimum Length**: 0
-   **Maximum Length**: 256
-   **Pattern**: ^\[^: \]\*$

_password\_type_

-   **Description**: The password of the SSH user
-   **Type**: `string`
-   **Minimum Length**: 1
-   **Maximum Length**: 256

_username\_type_

-   **Description**: The user name of the SSH user
-   **Type**: `string`
-   **Minimum Length**: 1
-   **Maximum Length**: 32
-   **Pattern**: ^\[a-z\*\]\[a-z0-9-\*\]\*\[$\]?$