---
title: Certificate Management
url: "https://developer.axis.com/vapix/device-configuration/certificate-management/"
category: vapix
subcategory: device-configuration
sha256: b2df07ceb369efaf769aac9c8c683bdbcccdad5bc22aeb4f1794e0480ae6f22a
scraped_at: "2026-01-09T15:18:41.101Z"
page_height: 25545
---

# Certificate Management

The VAPIX® Certificate Management API makes it possible to generate and install new certificates, as well as to fetch, replace and remove existing certificates.

There are two separate collections of certificates, one for certificates with private keys, and another for CA certificates. On Axis devices, non-CA certificates are always installed with a private key, and CA certificates are never installed with a private key.

The VAPIX Certificate Management API also makes it possible to fetch information about which keystores are available for protecting private keys in, and allow you to change which is the default one.

note

This API includes operations on sensitive data. You must use a secured channel for the communication transmissions.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Manage certificates

Certificates are part of the X.509 Public Key Infrastructure (PKI) for the Internet and are used as identities for devices or services and to build chains of trust between entities represented by such certificates.

The expected users of the API are video management systems (VMS) or web UI clients.

#### List all certificates with private keys

A list of all certificates can be retrieved by getting the `cert.v1.certificates` collection. This operation will never return the private keys. No operation can be used to obtain private keys.

The `keystore` field will tell which keystore the private key is protected in, even if no `keystore` was specified when generating or uploading the certificate with private key.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates"
```

```bash
GET /config/rest/cert/v1/certificatesHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "alias": "My Certificate",            "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----",            "keystore": "SE0"        },        {            "alias": "Another Certificate",            "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----",            "keystore": "TPM0"        }    \]}
```

#### Fetch details about a certificate with private key

Information on a certificate with a private key can be had by referencing its alias in a request.

This operation will never return the private keys. No operation can be used to obtain them.

The `keystore` field will tell which keystore the private key is protected in, even if no `keystore` was specified when generating or uploading the certificate with private key.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates/My Certificate"
```

```bash
GET /config/rest/cert/v1/certificates/My CertificateHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "alias": "My Certificate",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----",        "keystore": "SE0"    }}
```

#### List all CA certificates

A list of all CA certificates can be retrieved by reading the `cert.v1.ca_certificates` collection.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/ca\_certificates"
```

```bash
GET /config/rest/cert/v1/ca\_certificatesHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "alias": "My CA",            "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"        },        {            "alias": "Another CA",            "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"        }    \]
```

#### Fetch details about a CA certificate

Information on a single CA certificate can be had by referencing its alias in a read request.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/ca\_certificates/My CA"
```

```bash
GET /config/rest/cert/v1/ca\_certificates/My CAHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "alias": "My CA",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}
```

#### Generate a new certificate

Use the `create_certificate` action to generate a new certificate with private key on the device. The private key is generated inside the chosen keystore. This is the recommended and most secure way to install a certificate with private key, as the private key will never have existed outside the device.

The certificate will be self-signed, but it is possible to later fetch a certificate signing request and get it signed, and then upload the signed certificate back onto the device replacing the existing one.

The only required fields are `alias` and `subject`. If not specifying any `keystore`, the currently configured default one will be used instead.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/create\_certificate" \\  --data '{    "data": {        "alias": "My Certificate",        "key\_type": "NIST-P256",        "keystore": "SE0",        "subject": "C=SE,CN=example.com",        "subject\_alt\_names": \[            "DNS:example.com"        \],        "valid\_from": 1681740370,        "valid\_to": 1713276370    }}'
```

```bash
POST /config/rest/cert/v1/create\_certificateHost: <servername>Content-Type: application/json{    "data": {        "alias": "My Certificate",        "key\_type": "NIST-P256",        "keystore": "SE0",        "subject": "C=SE,CN=example.com",        "subject\_alt\_names": \[            "DNS:example.com"        \],        "valid\_from": 1681740370,        "valid\_to": 1713276370    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Obtain a certificate signing request

Use the `get_csr` action to obtain a certificate signing request (CSR) for an already existing certificate with private key on the device. This CSR can then be taken to a CA to be signed. The signed certificate can later be installed back onto the device by replacing the existing one. At no point does the private key leave the device.

None of the fields are required. If a field is filled out, that value will be used in the signing request. If not filling out a field, the existing value from the existing certificate will be copied into the certificate signing request instead. If filling out a field but leaving it with a blank value such as the empty string or empty list, that field is not copied from the existing certificate nor added to the certificate signing request.

Note that there is no guarantee that the attributes in the CSR will end up in the certificate signed by a CA. The CA can decide what attributes the signed certificate will have and disregard the attributes in the CSR.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates/My-Certificate/get\_csr" \\  --data '{    "data": {        "subject": "C=SE,CN=example.com",        "subject\_alt\_names": \[            "DNS:example.com"        \]    }}'
```

```bash
POST /config/rest/cert/v1/certificates/My-Certificate/get\_csrHost: <servername>Content-Type: application/json{    "data": {        "subject": "C=SE,CN=example.com",        "subject\_alt\_names": \[            "DNS:example.com"        \]    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "alias": "----BEGIN CERTIFICATE REQUEST-----\\npem-encoded-data\\n-----END CERTIFICATE REQUEST-----"    }}
```

#### Upload a certificate with private key

Certificates can be uploaded to the device by adding them to the `cert.v1.certificates` collection. The certificate and associated private key must be in PEM encoded text format. The private key will be protected by the chosen keystore, but the same security cannot be guaranteed when importing a certificate with private key as when generating it on the device itself. Since the private key was created outside the device at one point in time, there may still be copies of it outside of the device.

This operation supports all the common plain text RSA and EC private key PEM header formats, not just the generic one illustrated.

If not specifying any `keystore`, the currently configured default one will be used instead.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates" \\  --data '{    "data": {        "alias": "My Certificate",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----",        "keystore": "SE0",        "private\_key": "-----BEGIN PRIVATE KEY-----\\npem-encoded-data\\n-----BEGIN PRIVATE KEY-----"    }}'
```

```bash
POST /config/rest/cert/v1/certificatesHost: <servername>Content-Type: application/json{    "data": {        "alias": "My Certificate",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----",        "keystore": "SE0",        "private\_key": "-----BEGIN PRIVATE KEY-----\\npem-encoded-data\\n-----BEGIN PRIVATE KEY-----"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Replace a certificate but keep its private key

Use the the alias of an existing certificate to replace a certificate with a new one, which can be done as long as the new certificate is for the same private key as the one being replaced. This is useful if you earlier had generated a certificate on the device, obtained a CSR for it and got it signed by a real CA, and now want to install this signed certificate to the device. This is also useful if you have renewed a CA signed certificate, and want to install this new one over the old one.

The private key will stay on the same keystore as it was originally generated on or imported into, it is not possible to change that, or replace the private key itself.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates/My-Certificate" \\  --data '{    "data": {        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}'
```

```bash
PATCH /config/rest/cert/v1/certificates/My-CertificateHost: <servername>Content-Type: application/json{    "data": {        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Upload a CA certificate

New CA certificates can be added to the `cert.v1.ca_certificates` collection. The CA certificate must be in PEM encoded text format.

CA certificates do not have any private keys, so there is nothing to protect in any keystore.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/ca\_certificates" \\  --data '{    "data": {        "alias": "My CA",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}'
```

```bash
POST /config/rest/cert/v1/ca\_certificatesHost: <servername>Content-Type: application/json{    "data": {        "alias": "My CA",        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Replace a CA certificate

Existing CA certificates can be replaced with a new one, as long as the new CA certificate is for the same public key as the one being replaced. This is useful if you have a newer version of a CA certificate, and want to replace the old one.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/ca\_certificates/My-CA" \\  --data '{    "data": {        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}'
```

```bash
PATCH /config/rest/cert/v1/ca\_certificates/My-CAHost: <servername>Content-Type: application/json{    "data": {        "certificate": "-----BEGIN CERTIFICATE-----\\npem-encoded-data\\n-----END CERTIFICATE-----"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Upload a passphrase protected PKCS#12 archive

Use the `install_from_pkcs12` action to upload and install a certificate together with its private key from a passphrase protected PKCS#12 archive into the device. Both the certificate and private key will be extracted as PEM data from the archive, and the private key will be protected by the chosen keystore. Once installed, it will look just the same as if it was installed without using a PKCS#12 archive.

Passphrase protected PKCS#12 archives are used to mitigate some of the risks with passing private keys from one device to another, but the same security can still not be guaranteed when importing a certificate with private key as when generating it on the device itself.

If not specifying any `keystore`, the currently configured default one will be used instead.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/install\_from\_pkcs12" \\  --data '{    "data": {        "alias": "My-Certificate",        "pkcs12": "base64-encoded-pkcs12-file-data",        "passphrase": "my-password",        "keystore": "SE0"    }}'
```

```bash
POST /config/rest/cert/v1/install\_from\_pkcs12Host: <servername>Content-Type: application/json{    "data": {        "alias": "My-Certificate",        "pkcs12": "base64-encoded-pkcs12-file-data",        "passphrase": "my-password",        "keystore": "SE0"    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Delete a certificate with private key

Individual certificates in the `cert.v1.certificates` collection, along with their private keys can be removed from the device. The private key is always deleted, but depending on which keystore the private key is protected in, it may also be securely wiped to really guarantee it cannot ever be recovered again.

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/certificates/My-Certificate"
```

```bash
DELETE /config/rest/cert/v1/certificates/My-CertificateHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

#### Delete a CA certificate

A CA certificate can be removed from the `cert.v1.ca_certificates` collection using the alias of the certificate.

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/ca\_certificates/My CA"
```

```bash
DELETE /config/rest/cert/v1/ca\_certificates/My CAHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

### Manage keystores

Some devices offer a choice of how to protect private keys associated with certificates. A device has a default keystore it will use to store all private keys used by certificates.

In devices with multiple keystores, this API can be used to select a keystore that fits the user or system owner's security or performance requirements.

The expected users of the API are video management systems (VMS) or web UI clients.

#### List all available keystores

A list of all keystores can be read from the `cert.v1.keystores` collection. These are keystore that are available for protecting or generating new private keys in. This includes both software based and hardware based keystores.

The `security_level` field says what kind of keystore it is, and will contain the value `SOFTWARE`, `TRUSTED_ENVIRONMENT`, or `STRONG`, where `SOFTWARE` is the fastest but least secure kind of keystore, using no dedicated hardware or trust zone for protecting the key, and `STRONG` is the slowest but most secure kind of keystore, using a dedicated piece of hardware for protecting private keys.

The `certifications` field contain a list with zero or more elements showing what certifications the keystore meets. This may be certifications like FIPS 140-3 or Common Criteria.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/keystores"
```

```bash
GET /config/rest/cert/v1/keystoresHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": \[        {            "id": "TPM0",            "security\_level": "STRONG",            "certifications": \[                "CC EAL4+",                "FIPS 140-2 Level 2"            \]        },        {            "id": "SOFTWARE0",            "security\_level": "SOFTWARE",            "certifications": \[\]        }    \]}
```

#### Fetch details about a keystore

Information about a specific keystore can be retrieved using its ID when accessing the `cert.v1.keystores` collection. The keystore may be either a software based or hardware based keystore.

The `security_level` field says what kind of keystore it is, and will contain the value `SOFTWARE`, `TRUSTED_ENVIRONMENT`, or `STRONG`, where `SOFTWARE` is the fastest but least secure kind of keystore, using no dedicated hardware or trust zone for protecting the key, and `STRONG` is the slowest but most secure kind of keystore, using a dedicated piece of hardware for protecting private keys.

The `certifications` field contain a list with zero or more elements showing what certifications the keystore meets. This may be certifications like FIPS 140-3 or Common Criteria.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/keystores/SE0"
```

```bash
GET /config/rest/cert/v1/keystores/SE0Host: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "id": "SE0",        "security\_level": "STRONG",        "certifications": \[            "CC EAL6+"        \]    }}
```

#### Get which keystore is currently the default keystore

The default keystore can be determined via the `cert.v1.settings.keystore` property. The default keystore is the one that is used when protecting or generating new private keys without specifying a keystore.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/setttings/keystore"
```

```bash
GET /config/rest/cert/v1/setttings/keystoreHost: <servername>Content-Type: application/json
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": "TPM0"}
```

#### Set a keystore as the default keystore

The default keystore can be changed by modifying the `cert.v1.settings.keystore` property. The specified keystore will be used from now when protecting or generating new private keys without specifying a keystore.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/cert/v1/settings/keystore" \\  --data '{    "data": "SE0"}'
```

```bash
PATCH /config/rest/cert/v1/settings/keystoreHost: <servername>Content-Type: application/json{    "data": "SE0"}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
cert.v1 (Root Entity)    ├── create\_certificate (Action)    ├── install\_from\_pkcs12 (Action)    ├── ca\_certificates (Entity Collection)        ├── alias (Property)        ├── certificate (Property)    ├── certificates (Entity Collection)        ├── alias (Property)        ├── certificate (Property)        ├── keystore (Property)        ├── private\_key (Property)        ├── get\_csr (Action)    ├── keystores (Entity Collection)        ├── certifications (Property)        ├── id (Property)        ├── security\_level (Property)    ├── settings (Entity)        ├── keystore (Property)
```

### Entities
#### cert.v1

-   **Description**: The certificate management root object.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties

This entity has no properties.

##### Actions
###### create\_certificate

-   **Description**: Create a self-signed certificate.
-   **Request Datatype**: `create_certificate_input`
-   **Response Datatype**: Empty Object
-   **Trigger Permissions**: admin

###### install\_from\_pkcs12

-   **Description**: Install a server/client certificate with a private key from a password protected encrypted PKCS12 archive.
-   **Request Datatype**: `install_from_pkcs12_input`
-   **Response Datatype**: Empty Object
-   **Trigger Permissions**: admin

#### cert.v1.ca\_certificates

-   **Description**: Installed CA certificates.
-   **Type**: Collection (Key Property: `alias`)
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: certificate
    -   **Add** (**Permissions**: admin)
        -   **Required properties**: alias, certificate
        -   **Optional properties**:
    -   **Remove** (**Permissions**: admin)
-   **Attributes**
    -   **Dynamic Support**: No

This is the entity collection with all currently installed CA certificates. Each CA certificate is identified by its `alias`. There cannot be a CA certificate that has the same alias as a certificate with private key.

##### Properties
###### alias

-   **Description**: Identifier for this certificate entry.
-   **Datatype**: `alias`
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### certificate

-   **Description**: The X.509 certificate in PEM format. Can be replaced with a newer version.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### cert.v1.certificates

-   **Description**: Installed server and client certificates.
-   **Type**: Collection (Key Property: `alias`)
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: certificate
    -   **Add** (**Permissions**: admin)
        -   **Required properties**: alias, certificate, private\_key
        -   **Optional properties**: keystore
    -   **Remove** (**Permissions**: admin)
-   **Attributes**
    -   **Dynamic Support**: No

This is the entity collection with all currently installed certificates with private keys. Each certificate is identified by its `alias`. There cannot be a certificate with private key that has the same alias as a CA certificate.

##### Properties
###### alias

-   **Description**: Identifier for this certificate entry.
-   **Datatype**: `alias`
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### certificate

-   **Description**: The X.509 certificate in PEM format. Can be replaced with a freshly signed version for the same private key.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### keystore

-   **Description**: The keystore this private key is protected by. Can not be changed once the private key has been protected.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### private\_key

-   **Description**: The private key in PEM format. The key can only be used to add a certificate and can not be extracted again once it is protected.
-   **Datatype**: string
-   **Operations**
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions
###### get\_csr

-   **Description**: Get a PKCS10 certificate signing request in PEM format.
-   **Request Datatype**: `get_csr_input`
-   **Response Datatype**: string
-   **Trigger Permissions**: admin

#### cert.v1.keystores

-   **Description**: List of keystores available on the system.
-   **Type**: Collection (Key Property: `id`)
-   **Operations**
    -   **`GET`**
-   **Attributes**
    -   **Dynamic Support**: No

This is the entity collection with all keystores that are available for usage. Each keystore is identified by its `id`.

This collection includes both software and hardware based keystores. Which keystores are available may differ from one product to another and one software version to another, depending on the capabilities of the hardware and the software. All units of the same product running the same software will have the same keystores available.

Sometimes a certificate may be shown as protected by a keystore that is not available in this entity collection. This is normal if it is a pre-installed certificate that is provided by a hardware that is not usable for storing new private keys in.

##### Properties
###### certifications

-   **Description**: The list of security standards of the subsystem that this keystore is certified with.
-   **Datatype**: `keystore_certifications`
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### id

-   **Description**: Keystore identifier.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

###### security\_level

-   **Description**: The level of protection for private keys that this keystore offers.
-   **Datatype**: `keystore_seclevel`
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

#### cert.v1.settings

-   **Description**: Global settings for certificate management.
-   **Type**: Singleton
-   **Operations**
    -   **`GET`**
    -   **`SET`**
        -   **Properties**: keystore
-   **Attributes**
    -   **Dynamic Support**: No

##### Properties
###### keystore

-   **Description**: The selected keystore. Newly installed or generated private keys are protected in it by default.
-   **Datatype**: string
-   **Operations**
    -   **`GET`** (**Permissions:** admin, operator, viewer)
    -   **`SET`** (**Permissions:** admin)
-   **Attributes**
    -   **Nullable**: No
    -   **Dynamic Support**: No / **Dynamic Enum**: No / **Dynamic Range**: No

##### Actions

This entity has no actions.

### Data types
#### alias

-   **Description**: The client-defined alias of the certificate.
-   **Type**: string
-   **Minimum Length**: 1
-   **Maximum Length**: 128

#### create\_certificate\_input

-   **Description**: Certificate creation action parameters.
-   **Type**: complex
-   **Fields**
    -   **alias**
        -   **Description**: Identifier for this certificate.
        -   **Type**: `alias`
        -   **Nullable**: No / **Gettable**: No
    -   **key\_type**
        -   **Description**: The key algorithm and strength that should be used. Default value is EC-P256. For RSA keys this is RSA-bitlength, e.g. RSA-2048. For EC keys this is EC-P256, EC-P384 and EC-P521 for the widely used NIST curves supported by the TLS standard. Not all keystores support all key types.
        -   **Type**: string
        -   **Nullable**: Yes / **Gettable**: No
    -   **keystore**
        -   **Description**: The keystore in which this private key should be generated. If not specified, the configured default keystore is used.
        -   **Type**: string
        -   **Nullable**: Yes / **Gettable**: No
    -   **subject**
        -   **Description**: Subject distinguished name, defined in RFC 4514.
        -   **Type**: string
        -   **Nullable**: No / **Gettable**: No
    -   **subject\_alt\_names**
        -   **Description**: Subject alternative names, each prefixed with either "IP:" or "DNS:", e.g. "DNS:example.org".
        -   **Type**: `san_list`
        -   **Nullable**: Yes / **Gettable**: No
    -   **valid\_from**
        -   **Description**: The validity start date for the certificate. Default value is today. Number of seconds since Unix epoch, 1970-01-01 00:00:00 UTC.
        -   **Type**: integer
        -   **Nullable**: Yes / **Gettable**: No
    -   **valid\_to**
        -   **Description**: The validity end date for the certificate. Default value is one year from today's date. Number of seconds since Unix epoch, 1970-01-01 00:00:00 UTC.
        -   **Type**: integer
        -   **Nullable**: Yes / **Gettable**: No

#### get\_csr\_input

-   **Description**: Certificate Signing Request action parameters.
-   **Type**: complex
-   **Fields**
    -   **subject**
        -   **Description**: Optional new subject DN, which if used, will replace the original.
        -   **Type**: string
        -   **Nullable**: Yes / **Gettable**: No
    -   **subject\_alt\_names**
        -   **Description**: Optional new list of alternative names, which if used, will replace the original.
        -   **Type**: `san_list`
        -   **Nullable**: Yes / **Gettable**: No

#### install\_from\_pkcs12\_input

-   **Description**: PKCS12 installation action parameters.
-   **Type**: complex
-   **Fields**
    -   **alias**
        -   **Description**: New identifier for this certificate.
        -   **Type**: `alias`
        -   **Nullable**: No / **Gettable**: No
    -   **keystore**
        -   **Description**: The keystore protecting the private key. The configured default keystore will be used if this parameter is not specified.
        -   **Type**: string
        -   **Nullable**: Yes / **Gettable**: No
    -   **passphrase**
        -   **Description**: The passphrase for the PKCS12 archive.
        -   **Type**: string
        -   **Nullable**: No / **Gettable**: No
    -   **pkcs12**
        -   **Description**: The raw data for the PKCS12 archive, base64-encoded.
        -   **Type**: string
        -   **Nullable**: No / **Gettable**: No

#### keystore\_certifications

-   **Description**: A list of security standards for the subsystem that a keystore is certified with. E.g. "FIPS 140-2 Level 2".
-   **Type**: array
-   **Element type**: string
-   **Null Value**: No

#### keystore\_seclevel

-   **Description**: The protection level of private keys offered by a keystore.
-   **Type**: string
-   **Enum Values**: "SOFTWARE", "TRUSTED\_ENVIRONMENT", "STRONG"

#### san\_list

-   **Description**: Subject alternative names, each prefixed with either "IP:" or "DNS:", e.g. "DNS:example.org".
-   **Type**: array
-   **Element type**: string
-   **Null Value**: No