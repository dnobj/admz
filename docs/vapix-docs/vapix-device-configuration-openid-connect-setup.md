---
title: OpenID Connect Setup
url: "https://developer.axis.com/vapix/device-configuration/openid-connect-setup/"
category: vapix
subcategory: device-configuration
sha256: 725b8ffcec57102cb69df2673f38bbfa30b199f29484145e4e9a02233860f2ba
scraped_at: "2026-01-09T15:18:56.745Z"
page_height: 10148
---

# OpenID Connect Setup

The VAPIX® OpenID Connect Setup API makes it possible to set up a configuration that allows a user to log in to the device with the OpenID Connect authentication code flow.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Set all settings

All OpenID Connect settings can be set at the same time with the base config entity.

Specify the metadata uri together with the client ID and secret strings. If the unit requires proxy settings to reach out those are included as well.

Enter the proper claims that is validated in the given token. The remote user claim value is used to identify the logged in user and the require claim is validated for all requests. The different claims for admin/operator/viewer access must also be fulfilled and values configured in the client.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oidcsetup/v1/BaseConfigEntity" \\  --data '{    "data": {        "AuthEntity": {            "OIDC\_AuthzAdminClaim": "example-claim-admin",            "OIDC\_AuthzOperatorClaim": "example-claim-operator",            "OIDC\_AuthzViewerClaim": "example-claim-viewer",            "OIDC\_AuthzScopes": "some:scope",            "OIDC\_ClientID": "example-id",            "OIDC\_ClientSecret": "example-secret"        },        "OIDC\_OutgoingProxy": "optional.proxy.settings",        "OIDC\_ProviderMetadataURL": "https://example.metadata.uri",        "OIDC\_RemoteUserClaim": "email",        "OIDC\_RequireClaim": "example-claim"    }}'
```

```bash
PATCH /config/rest/oidcsetup/v1/BaseConfigEntityHost: <servername>Content-Type: application/json{    "data": {        "AuthEntity": {            "OIDC\_AuthzAdminClaim": "example-claim-admin",            "OIDC\_AuthzOperatorClaim": "example-claim-operator",            "OIDC\_AuthzViewerClaim": "example-claim-viewer",            "OIDC\_AuthzScopes": "some:scope",            "OIDC\_ClientID": "example-id",            "OIDC\_ClientSecret": "example-secret"        },        "OIDC\_OutgoingProxy": "optional.proxy.settings",        "OIDC\_ProviderMetadataURL": "https://example.metadata.uri",        "OIDC\_RemoteUserClaim": "email",        "OIDC\_RequireClaim": "example-claim"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Get all settings

Read out the current OpenID Connect settings from the base config entity.

The client secret will never be returned.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oidcsetup/v1/BaseConfigEntity"
```

```bash
GET /config/rest/oidcsetup/v1/BaseConfigEntityHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "AuthEntity": {            "OIDC\_AuthzAdminClaim": "example-claim-admin",            "OIDC\_AuthzOperatorClaim": "example-claim-operator",            "OIDC\_AuthzViewerClaim": "example-claim-viewer",            "OIDC\_AuthzScopes": "some:scope",            "OIDC\_ClientID": "example-id"        },        "OIDC\_OutgoingProxy": "optional.proxy.settings",        "OIDC\_ProviderMetadataURL": "https://example.metadata.uri",        "OIDC\_RemoteUserClaim": "email",        "OIDC\_RequireClaim": "example-claim"    }}
```

### Update a single setting

All settings can be applied separately, such as clearing a proxy setting without changing anything else.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oidcsetup/v1/BaseConfigEntity/OIDC\_OutgoingProxy" \\  --data '{    "data": ""}'
```

```bash
PATCH /config/rest/oidcsetup/v1/BaseConfigEntity/OIDC\_OutgoingProxyHost: <servername>Content-Type: application/json{    "data": ""}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
oidcsetup.v1 (Root Entity)    ├── BaseConfigEntity (Entity)        ├── OIDC\_OutgoingProxy (Property)        ├── OIDC\_ProviderMetadataURL (Property)        ├── OIDC\_RemoteUserClaim (Property)        ├── OIDC\_RequireClaim (Property)        ├── AuthEntity (Entity)            ├── OIDC\_AuthzAdminClaim (Property)            ├── OIDC\_AuthzOperatorClaim (Property)            ├── OIDC\_AuthzScopes (Property)            ├── OIDC\_AuthzViewerClaim (Property)            ├── OIDC\_ClientID (Property)            ├── OIDC\_ClientSecret (Property)
```

### Entities
#### `oidcsetup.v1`

-   **Description**: OIDC client configurations.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: BaseConfigEntity
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties

This entity has no properties.

##### Actions

This entity has no actions.

#### `oidcsetup.v1.BaseConfigEntity`

-   **Description**: Required configuration for OIDC client.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: AuthEntity, OIDC\_OutgoingProxy, OIDC\_ProviderMetadataURL, OIDC\_RemoteUserClaim, OIDC\_RequireClaim
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### `OIDC_OutgoingProxy`

-   **Description**: Proxy configuration.
-   **Datatype**: `proxy_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_ProviderMetadataURL`

-   **Description**: OIDC discovery API endpoint. Required format `https://<host>/<optional directory>/.well-known/openid-configuration`
-   **Datatype**: `url_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_RemoteUserClaim`

-   **Description**: OIDC Remote User Claim (sub, email, preferred\_username).
-   **Datatype**: `RemoteUserClaim_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_RequireClaim`

-   **Description**: Required claim.
-   **Datatype**: `claim_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### `oidcsetup.v1.BaseConfigEntity.AuthEntity`

-   **Description**: Client authentication properties.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: OIDC\_AuthzAdminClaim, OIDC\_AuthzOperatorClaim, OIDC\_AuthzScopes, OIDC\_AuthzViewerClaim, OIDC\_ClientID, OIDC\_ClientSecret
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### `OIDC_AuthzAdminClaim`

-   **Description**: To set which claim and value that corresponds to admin
-   **Datatype**: `claim_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_AuthzOperatorClaim`

-   **Description**: To set which claim and value that corresponds to operator
-   **Datatype**: `claim_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_AuthzScopes`

-   **Description**: Optional list of additional scopes
-   **Datatype**: `scope_list_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_AuthzViewerClaim`

-   **Description**: To set which claim and value that corresponds to viewer
-   **Datatype**: `claim_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_ClientID`

-   **Description**: OIDC client ID.
-   **Datatype**: `client_id_type`
-   **Operations**
    -   **`GET`** (**Permissions:** admin)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### `OIDC_ClientSecret`

-   **Description**: OIDC client secret.
-   **Datatype**: `passphrase_type`
-   **Operations**
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

### Data types
#### `RemoteUserClaim_type`

-   **Description**: Normal string type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 64
-   **Pattern**: ^(sub|email|preferred\_username|("\[a-zA-Z0-9\]\*"))$

#### `claim_type`

-   **Description**: Claim type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256
-   **Pattern**: ^.\*$

#### `client_id_type`

-   **Description**: Client ID type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256

#### `passphrase_type`

-   **Description**: Passphrase type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256

#### `proxy_type`

-   **Description**: Proxy type.
-   **Type**: string
-   **Maximum Length**: 256
-   **Pattern**: `^[\\w "'.:\\/\\/?]*$`

#### `scope_list_type`

-   **Description**: Scope list type.
-   **Type**: string
-   **Maximum Length**: 256
-   **Pattern**: `^[\\w "'.:\\/\\/?]*$`

#### `switch_type`

-   **Description**: 'no' and 'yes' switch.
-   **Type**: string
-   **Enum Values**: "yes", "no"

#### `url_type`

-   **Description**: URL type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256
-   **Pattern**: `^[\\w "'.:\\-\\/\\/~?]+$`