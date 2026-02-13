---
title: Client credential grants configuration
url: "https://developer.axis.com/vapix/device-configuration/client-credential-grants-configuration/"
category: vapix
subcategory: device-configuration
sha256: 6457a51393b8a247285f605c7565e883917ec4e0755a0671d82899c85a8bc070
scraped_at: "2026-01-09T15:18:42.578Z"
page_height: 7012
---

# Client credential grants configuration

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in BETA stage and provided for testing purposes. It is subject to backward-incompatible changes, including modifications to its functionality, behavior and availability. The API should not be used in production environments.

The VAPIX® Client Credentials Grant API enables secure machine-to-machine communication by providing a mechanism that can be used to exchange authorization credentials with the help of JWKS _(JSON Web Key Set)_.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Set all settings

All Client Credentials Grant settings can be set at the same time with the auth config entity.

#### Specify the JWKS verification URI for access token verification

Enter the claim that is required by a token that allows the correct access level to initiate the request. The claim is required for all API requests and one of admin/operator/viewer should be used to assign the proper access level.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oauth-ccgrant/v1beta/AuthEntity" \\  --data '{    "data": {        "CCG\_AuthzAdminClaim": "example-claim-admin",        "CCG\_AuthzOperatorClaim": "example-claim-operator",        "CCG\_AuthzViewerClaim": "example-claim-viewer",        "CCG\_OAuth2TokenVerify": "https://example.jwksverify.uri",        "CCG\_RequireClaim": "example-claim"    }}'
```

```bash
PATCH /config/rest/oauth-ccgrant/v1beta/AuthEntityHost: <servername>Content-Type: application/json{    "data": {        "CCG\_AuthzAdminClaim": "example-claim-admin",        "CCG\_AuthzOperatorClaim": "example-claim-operator",        "CCG\_AuthzViewerClaim": "example-claim-viewer",        "CCG\_OAuth2TokenVerify": "https://example.jwksverify.uri",        "CCG\_RequireClaim": "example-claim"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Get all settings

Read out the current Client Credentials Grant settings from the auth entity.

#### The JWKS verification URI used for access token verification

Enter the claim that is required by a token that allows the correct access level to initiate the request. The claim is required for all API requests and one of admin/operator/viewer should be used to assign the proper access level.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oauth-ccgrant/v1beta/AuthEntity"
```

```bash
GET /config/rest/oauth-ccgrant/v1beta/AuthEntityHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "CCG\_AuthzAdminClaim": "example-claim-admin",        "CCG\_AuthzOperatorClaim": "example-claim-operator",        "CCG\_AuthzViewerClaim": "example-claim-viewer",        "CCG\_OAuth2TokenVerify": "https://example.jwksverify.uri",        "CCG\_RequireClaim": "example-claim"    }}
```

### Update a single setting

All settings can be applied separately, such as changing the claim for admin access.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/oauth-ccgrant/v1beta/AuthEntity/CCG\_AuthzAdminClaim" \\  --data '{    "data": "example-claim-admin"}'
```

```bash
PATCH /config/rest/oauth-ccgrant/v1beta/AuthEntity/CCG\_AuthzAdminClaimHost: <servername>Content-Type: application/json{    "data": "example-claim-admin"}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
oauth-ccgrant.v1 (Root Entity)    ├── AuthEntity (Entity)        ├── CCG\_AuthzAdminClaim (Property)        ├── CCG\_AuthzOperatorClaim (Property)        ├── CCG\_AuthzViewerClaim (Property)        ├── CCG\_OAuth2TokenVerify (Property)        ├── CCG\_RequireClaim (Property)
```

### Entities
#### oauth-ccgrant.v1

-   **Description**: CCG configuration.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
        -   **Properties**: AuthEntity
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties

This entity has no properties.

##### Actions

This entity has no actions.

#### oauth-ccgrant.v1.AuthEntity

-   **Description**: Client authentication properties.
-   **Type**: Singleton
-   **Operations**
    -   **Get**
    -   **Set**
        -   **Properties**: `CCG_AuthzAdminClaim`, `CCG_AuthzOperatorClaim`, `CCG_AuthzViewerClaim`, `CCG_OAuth2TokenVerify`, `CCG_RequireClaim`
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### CCG\_AuthzAdminClaim

-   **Description**: Claim and value corresponding to to admin access
-   **Datatype**: [optional\_claim\_type](#optional_claim_type)
-   **Operations**
    -   **Get** (_Permissions:_ admin)
    -   **Set** (_Permissions:_ admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### CCG\_AuthzOperatorClaim

-   **Description**: Claim and value corresponding to operator access
-   **Datatype**: [optional\_claim\_type](#optional_claim_type)
-   **Operations**
    -   **Get** (_Permissions:_ admin)
    -   **Set** (_Permissions:_ admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### CCG\_AuthzViewerClaim

-   **Description**: Claim and value corresponding to viewer access
-   **Datatype**: [optional\_claim\_type](#optional_claim_type)
-   **Operations**
    -   **Get** (_Permissions:_ admin)
    -   **Set** (_Permissions:_ admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### CCG\_OAuth2TokenVerify

-   **Description**: JWKS URI that serves the public keys.
-   **Datatype**: [url\_type](#url_type)
-   **Operations**
    -   **Get** (_Permissions:_ admin)
    -   **Set** (_Permissions:_ admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### CCG\_RequireClaim

-   **Description**: Required claim.
-   **Datatype**: [required\_claim\_type](#required_claim_type)
-   **Operations**
    -   **Get** (_Permissions:_ admin)
    -   **Set** (_Permissions:_ admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

### Data types
#### optional\_claim\_type

-   **Description**: Optional claims.
-   **Type**: string
-   **Maximum Length**: 256
-   **Pattern**: `^.*$`

#### required\_claim\_type

-   **Description**: Mandatory claims.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256
-   **Pattern**: `^.*$`

#### url\_type

-   **Description**: URL type.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 256
-   **Pattern**: `^[\\w "'.:\\-\\/\\/~?]+$`