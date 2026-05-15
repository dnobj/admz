---
title: Third party credential service
url: "https://developer.axis.com/vapix/physical-access-control/third-party-credential-service/"
category: vapix
subcategory: physical-access-control
sha256: 9f74d013e3ac12161d27c2f74c260b78e3de3b5110239bd06193ca8561dac3c1
scraped_at: "2026-01-09T15:21:55.564Z"
page_height: 34182
---

# Third party credential service

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

info

The AXIS A1601 network door controller is not supported by this API.

## Third party credential service guide

The third party credential service handles credentials that are issued by third-party providers, as opposed to the normal credential management provided by the Access Control service.

HID Mobile Access is currently the only supported third-party credential provider. It allows for creating "Mobile IDs" that are installed on a user’s mobile phone. Together with compatible card readers, the Mobile IDs can then replace physical access cards as means to gain entry to access controlled areas.

To use the third-party credential service, the recommended set-up is to designate one door controller as a gateway towards the third-party credential provider. All communication with the third-party provider is then done through this designated unit and the resulting credentials are then propagated out to remaining door controllers in the system. Note: the door controller used as a gateway must be allowed outbound internet access in order to work properly.

A typical system overview using HID mobile credential service and AXIS A1001 is shown as below:

![system overview using HID mobile credential service and AXIS A1001](/assets/images/third-party-credential-service.t10112772-10f7f03a6d4a93512c837df6be2c00df.png)

1.  The ADP creates a HID user on the AXIS A1001.
    
2.  That user get sent to the HID cloud.
    
3.  An invitation is sent to the user’s e-mail. The user then installs the HID Mobile Access app on to a phone and enters the invitation code received in the e-mail.
    
4.  Once the invitation is accepted, a Mobile ID is pushed to the mobile phone and the AXIS A1001 is notified of the newly generated `CardNr`. This information is then forwarded to the ADP via events.
    
5.  Credentials using HID Mobile ID’s can now be added to all the AXIS A1001’s.
    

### Set up the initial system

This section describes how to configure a third-party credential provider. HID Mobile Access will be used as credential provider in the examples.

#### Get supported providers

It is important to check the supported providers for `ThirdPartyCredential` since the upcoming API requests needs to contain the correct `ProviderName` that should be called.

Request

```bash
{    "axtpc:GetProviders": {}}
```

Request

```bash
<axtpc:GetProviders />
```

Response

```bash
{    "Providers": \[        {            "Name": "ProviderName",            "Value": "HIDMobileAccess",            "Type": "string",            "Enums": \["HIDMobileAccess"\]        }    \]}
```

Response

```bash
<axtpc:GetProvidersResponse>    <axtpc:Providers>        <axtpc:Name>ProviderName</axtpc:Name>        <axtpc:Value>HIDMobileAccess</axtpc:Value>        <axtpc:Type>string</axtpc:Type>        <axtpc:Enums>HIDMobileAccess</axtpc:Enums>        <axtpc:DependOnName />        <axtpc:DependOnValue />        <axtpc:Description />    </axtpc:Providers></axtpc:GetProvidersResponse>
```

In the response from `GetProviders` the provider `HIDMobileAccess` is supported.

#### Configuring a credential provider

With a valid provider name it is then possible to set a configuration for that credential provider.

The `ProviderName` need to match the name returned from `GetProviders`. `ProviderActions` is a list of `pt:Attribute` elements that can contain specific actions for the provider. Only one configuration can exist for each supported provider, subsequent calls for `SetProviderConfiguration` for the same `ProviderName` will overwrite the existing one.

The following configuration possibilities exists for HID Mobile access:

-   `ClientId` String containing the client id for the account provided by HID Mobile Access.
-   `ClientSecret` String containing the password for the HID Mobile Access account.
-   `ProxyURL` String containing the URL for the proxy to use (Optional).
-   `ProxyPort` String containing the port for the proxy to use (Optional).
-   `ProxyUser` String containing the user name for connecting to the proxy (Optional).
-   `ProxyPassword` String containing the password for the proxy user (Optional).
-   `DefaultPartNumberToken` String specifying the part number to be used if no part number is explicitly used in `SetThirdPartyCredential` (Optional).
-   `PortalApiURL` String containing the URL for the HID Mobile Access service (Optional).
-   `IdpURL` String containing the URL for the HID Mobile Access identification service (Optional).
-   `CardIdDataName` String containing the name of the Id Data that should be created when a card gets issued to the Credential (Optional, default is `CardNr`).

Request

```bash
{    "axtpc:SetProviderConfiguration": {        "ProviderName": "HIDMobileAccess",        "ProviderActions": \[\],        "Configuration": {            "HIDMobileConfig": {                "ClientId": "1824-SRV443124455",                "ClientSecret": "HIDpassword123!",                "ProxyURL": "http://wwwproxy.se.axis.com",                "ProxyPort": "3128",                "DefaultPartNumberToken": "CRD633ZZ-TST0030",                "PortalApiURL": "https://test-ma.api.assaabloy.com/credential-management/",                "IdpURL": "https://test.idp.hidglobal.com/idp/SISDOMAIN/"            }        }    }}
```

Request

```bash
<axtpc:SetProviderConfiguration>    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:Configuration>        <axtpc:HIDMobileConfig>            <axtpc:ClientId>1824-SRV443124455</axtpc:ClientId>            <axtpc:ClientSecret>HIDpassword123!</axtpc:ClientSecret>            <axtpc:ProxyURL>http://wwwproxy.se.axis.com</axtpc:ProxyURL>            <axtpc:ProxyPort>3128</axtpc:ProxyPort>            <axtpc:ProxyUser />            <axtpc:ProxyPassword />            <axtpc:DefaultPartNumberToken>CRD633ZZ-TST0030</axtpc:DefaultPartNumberToken>            <axtpc:PortalApiURL>https://test-ma.api.assaabloy.com/credential-management/</axtpc:PortalApiURL>            <axtpc:IdpURL>https://test.idp.hidglobal.com/idp/SISDOMAIN/</axtpc:IdpURL>        </axtpc:HIDMobileConfig>    </axtpc:Configuration></axtpc:SetProviderConfiguration>
```

Response

```bash
{}
```

Response

```bash
<axtpc:SetProviderConfigurationResponse />
```

#### Retrieve the configuration of a credential provider

It is supported to retrieve the credential provider´s configuration. The `PartNumbers` field in the response returns a list of objects with information of the different part numbers for the account:

-   `PartNumbers` Array of Part number objects.
-   `Token` String of the token of the part number. Used in `DefaultPartNumberToken` for `SetProviderConfiguration`.
-   `Name` String containing the name of the part number.
-   `Description` String containing a description of the part number.
-   `Quantity` Integer that holds the number of mobile ids (i.e card numbers) that are available for the part number.

Request

```bash
{    "axtpc:GetProviderConfiguration": {        "ProviderName": "HIDMobileAccess"    }}
```

Request

```bash
<axtpc:GetProviderConfiguration>    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:GetProviderConfiguration>
```

Response

```bash
{    "Configuration": {        "HidMobileConfig": {            "ClientId": "1824-SRV443124455",            "ClientSecret": "\*\*\*",            "ProxyURL": "wwwproxy.se.axis.com",            "ProxyPort": "3128",            "PartNumbers": \[                {                    "token": "CRD633ZZ-TST0030",                    "Name": "Company part number",                    "Description": "Part numbers for inner doors",                    "Quantity": 42                }            \],            "DefaultPartNumberToken": "CRD633ZZ\_TST0030",            "PortalApiURL": "https://ma.api.assaabloy.com/credential-management/",            "IdpURL": "https://idp.hidglobal.com/idp/SISDOMAIN/",            "CardIdDataName": "CardNr"        }    }}
```

Response

```bash
<axtpc:GetProviderConfigurationResponse>    <axtpc:Configuration>        <axtpc:HIDMobileConfig>            <axtpc:ClientId>1824-SRV443124455</axtpc:ClientId>            <axtpc:ClientSecret>\*\*\*</axtpc:ClientSecret>            <axtpc:ProxyURL>wwwproxy.se.axis.com</axtpc:ProxyURL>            <axtpc:ProxyPort>3128</axtpc:ProxyPort>            <axtpc:ProxyUser />            <axtpc:ProxyPassword />            <axtpc:PartNumbers token="CRD633ZZ-TST0030">                <axtpc:Name>Company part number</axtpc:Name>                <axtpc:Description>Part numbers for inner doors</axtpc:Description>                <axtpc:Quantity>42</axtpc:Quantity>            </axtpc:PartNumbers>            <axtpc:DefaultPartNumberToken>CRD633ZZ-TST0030</axtpc:DefaultPartNumberToken>            <axtpc:PortalApiURL>https://ma.api.assaabloy.com/credential-management/</axtpc:PortalApiURL>            <axtpc:IdpURL>https://idp.hidglobal.com/idp/SISDOMAIN/</axtpc:IdpURL>            <axtpc:CardIdDataName>CardNr</axtpc:CardIdDataName>        </axtpc:HIDMobileConfig>    </axtpc:Configuration></axtpc:GetProviderConfigurationResponse>
```

#### Disable a configuration

Providing an empty configuration will disable a third party credential configuration:

Request

```bash
{    "axtpc:SetProviderConfiguration": {        "ProviderName": "HIDMobileAccess",        "ProviderAction": \[\],        "Configuration": {            "HIDMobileConfig": {}        }    }}
```

Request

```bash
<axtpc:SetProviderConfiguration>    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:Configuration>        <axtpc:HIDMobileConfig>            <axtpc:ClientId />            <axtpc:ClientSecret />            <axtpc:ProxyURL />            <axtpc:ProxyPort />            <axtpc:ProxyUser />            <axtpc:ProxyPassword />            <axtpc:DefaultPartNumberToken />            <axtpc:PortalApiURL />            <axtpc:IdpURL />            <axtpc:CardIdDataName />        </axtpc:HIDMobileConfig>    </axtpc:Configuration></axtpc:SetProviderConfiguration>
```

Response

```bash
{}
```

Response

```bash
<axtpc:SetProviderConfigurationResponse />
```

### Managing third-party credentials

A third-party credential contains a normal access control credential as well as additional information from the third-party provider.

#### Creating third-party credentials

`SetThirdPartyCredential` will create a new third-party user and a Credential linked to that at the same time. Since the "Credential" part of the `ThirdPartyCredential` is the same as the normal access control credential it is used exactly the same way as a normal credential in the access control system. Also included in the `ThirdPartyCredential` structure is an Options field that is used to enter provider specific options for the Credential. For HID Mobile Access there exists an option to specify the part number that should be used to generate the mobile id (i.e. the card number). If that option is not used the default part number that was configured in `axtpc:SetProviderConfiguration` will be used to generate the mobile id. After the call to `SetThirdPartyCredential` the Credential will get the status `NotActivated` until a card has been issued from the provider (in this case HID). It is important to not try to specify any Id Data with the same name as the provider will use (`CardNr` by default) since that Id Data will be overwritten when the provider issues the card.

For HID Mobile Access there will be no card created until the invitation has been accepted. The invitation will be sent to the e-mail specified in the Credential attribute with the name `Email`. There are three attributes that needs to be set in order to create a new HID Mobile user:

-   `Email` The e-mail that should be used to send the invitation e-mail.
-   `FirstName` The first name of the user.
-   `LastName` The last name of the user.

Once the invitation has been accepted by entering the invitation code in a HID Mobile access application a new card number will be saved to the Credential and the status will be changed to `Active`. This generally takes a couple of minutes after the invitation has been accepted.

The `SetThirdPartyCredential` request has some optional `ProviderActions`:

-   `{"Name":"ForceUpdate"}` Force an update to HID Mobile service. Will overwrite any old user that uses the same e-mail.
-   `{"Name":"SendInvitationOnly"}` No writing to the access control credential database is performed, only sends a new invitation e-mail.
-   `{"Name":"NoLocalModification"}` Do not update the access control credential once the card number has been issued. An event containing the card details will still be sent.

Request

```bash
{    "axtpc:SetThirdPartyCredential": {        "ProviderName": "HIDMobileAccess",        "ProviderActions": \[\],        "ThirdPartyCredential": {            "Options": {                "HIDMobileOptions": {                    "PartNumberToken": "CRD633ZZ-TST0030"                }            },            "Credential": {                "token": "credential\_token",                "UserToken": "user\_token",                "IdData": \[{ "Name": "PIN", "Value": "1234" }\],                "Attribute": \[                    { "Name": "Email", "Value": "kalle.karlsson@example.com" },                    { "Name": "LastName", "Value": "Karlsson" },                    { "Name": "FirstName", "Value": "Kalle" }                \]            }        }    }}
```

Request

```bash
<axtpc:SetThirdPartyCredential>    <axtpc:ThirdPartyCredential>        <axtpc:Credential token="credential\_token">            <axtpc:UserToken />            <axtpc:Description />            <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>            <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>            <axtpc:Enabled>true</axtpc:Enabled>            <axtpc:Status>NotActivated</axtpc:Status>            <axtpc:IdData Name="PIN" Value="1234" />            <axtpc:Attribute type="" Name="Email" Value="kalle.karlsson@example.com" />            <axtpc:Attribute type="" Name="LastName" Value="Karlsson" />            <axtpc:Attribute type="" Name="FirstName" Value="Kalle" />            <axtpc:AuthenticationProfile />            <axtpc:AuthenticationProfile />            <axtpc:CredentialAccessProfile>                <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>                <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>                <axtpc:AccessProfile />            </axtpc:CredentialAccessProfile>            <axtpc:CredentialAccessProfile>                <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>                <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>                <axtpc:AccessProfile />            </axtpc:CredentialAccessProfile>        </axtpc:Credential>    </axtpc:ThirdPartyCredential>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:SetThirdPartyCredential>
```

Response

```bash
{    "Token": "credential\_token"}
```

Response

```bash
<axtpc:SetThirdPartyCredentialResponse>    <axtpc:Token>credential\_token</axtpc:Token></axtpc:SetThirdPartyCredentialResponse>
```

#### Retrieving third-party credentials

It is possible to get credential information with the normal access control API (i.e. pacsaxis:GetCredential), but to get additional provider specific info there exists `axtpc:GetThirdPartyCredentialbyEmail`, `axtpc:GetThirdPartyCredential` and `axtpc:GetThirdPartyCredentialList` APIs. To get information about the `ThirdPartyCredential` that was previously created it is possible to use either token `axtpc:GetThirdPartyCredential` or e-mail `axtpc:GetThirdPartyCredentialByEmail` as reference.

The Options field in the response contains provider specific information about the third-party credential. HID Mobile Access currently has two fields:

-   `PartNumberToken` The part number that was used when creating the card number.
-   `InvitationCode` The invitation code that is sent to the e-mail addres of the credential.

If the `ProviderAction` has `ForceUpdate` set then the call will also contact the provider to retrieve information from the remote servers. This should not be needed in daily use since the information is stored locally on the AXIS A1001.

Request

```bash
{    "axtpc:GetThirdPartyCredentialByEmail": {        "ProviderActions": \[\],        "ProviderName": "HIDMobileAccess",        "Email": "kalle.karlsson@example.com"    }}
```

Request

```bash
<axtpc:GetThirdPartyCredentialByEmail>    <axtpc:Email>kalle.karlsson@example.com</axtpc:Email>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:GetThirdPartyCredentialByEmail>
```

Response

```bash
{    "ThirdPartyCredential": {        "Credential": {            "token": "credential\_token",            "UserToken": "",            "Description": "",            "ValidFrom": "",            "ValidTo": "",            "Enabled": true,            "Status": "Enabled",            "IdData": \[                { "Name": "CardNr", "Value": "18302" },                { "Name": "PIN", "Value": "1234" }            \],            "Attribute": \[                { "Name": "FirstName", "Value": "Kalle" },                { "Name": "LastName", "Value": "Karlsson" },                { "Name": "Email", "Value": "kalle.karlsson@example.com" }            \],            "AuthenticationProfile": \[\],            "CredentialAccessProfile": \[\]        },        "Options": {            "HIDMobileOptions": {                "PartNumberToken": "CRD633ZZ-TST0030",                "InvitationCode": "BUFI-LH56-AJTD-KFGS"            }        }    }}
```

Response

```bash
<axtpc:GetThirdPartyCredentialByEmailResponse>    <axtpc:ThirdPartyCredential>        <axtpc:Credential token="credential\_token">            <axtpc:UserToken />            <axtpc:Description />            <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>            <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>            <axtpc:Enabled>true</axtpc:Enabled>            <axtpc:Status>Activated</axtpc:Status>            <axtpc:IdData Name="CardNr" Value="18302" />            <axtpc:IdData Name="PIN" Value="1234" />            <axtpc:Attribute type="" Name="Email" Value="kalle.karlsson@example.com" />            <axtpc:Attribute type="" Name="LastName" Value="Karlsson" />            <axtpc:Attribute type="" Name="FirstName" Value="Kalle" />            <axtpc:AuthenticationProfile />            <axtpc:AuthenticationProfile />            <axtpc:CredentialAccessProfile>                <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>                <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>                <axtpc:AccessProfile />            </axtpc:CredentialAccessProfile>            <axtpc:CredentialAccessProfile>                <axtpc:ValidFrom>2017-05-17T22:48:01Z</axtpc:ValidFrom>                <axtpc:ValidTo>2017-05-17T22:48:01Z</axtpc:ValidTo>                <axtpc:AccessProfile />            </axtpc:CredentialAccessProfile>        </axtpc:Credential>        <axtpc:Options>            <axtpc:HIDMobileOptions>                <axtpc:PartNumberToken>CRD633ZZ-TST0030</axtpc:PartNumberToken>                <axtpc:InvitationCode>BUFI-LH56-AJTD-KFGS</axtpc:InvitationCode>            </axtpc:HIDMobileOptions>        </axtpc:Options>    </axtpc:ThirdPartyCredential></axtpc:GetThirdPartyCredentialByEmailResponse>
```

In the above example, e-mail is used to get the information.

To get the same information using token instead:

Request

```bash
{    "axtpc:GetThirdPartyCredential": {        "ProviderActions": \[\],        "ProviderName": "HIDMobileAccess",        "Token": "credential\_token"    }}
```

Request

```bash
<axtpc:GetThirdPartyCredential>    <axtpc:Token>credential\_token</axtpc:Token>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:GetThirdPartyCredential>
```

#### Removing third-party credentials

To remove third-party credentials in a similar manner as retrieving users by token or e-mail. Remove operations also support the `NoLocalModification` option. When this is in use only the third-party credential will be removed and not the local access control credential.

#### Removing credential by token

Request

```bash
{    "axtpc:RemoveThirdPartyCredential": {        "ProviderName": "HIDMobileAccess",        "ProviderActions": \[\],        "Token": "credential\_token"    }}
```

Request

```bash
<axtpc:RemoveThirdPartyCredential>    <axtpc:Token>credential\_token</axtpc:Token>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:RemoveThirdPartyCredential>
```

#### Removing credential by e-mail

Request

```bash
{    "axtpc:RemoveThirdPartyCredentialByEmail": {        "ProviderName": "HIDMobileAccess",        "ProviderActions": \[\],        "Email": "kalle.karlsson@example.com"    }}
```

Request

```bash
<axtpc:RemoveThirdPartyCredentialByEmail>    <axtpc:Email>kalle.karlsson@example.com</axtpc:Email>    <axtpc:ProviderActions type="" Name="" Value="" />    <axtpc:ProviderName>HIDMobileAccess</axtpc:ProviderName></axtpc:RemoveThirdPartyCredentialByEmail>
```

#### API errors

Possible fault subcodes of the third-party credential APIs.

-   `ter:NetworkError`
-   `ter:CurlError`
-   `ter:ConnectionError`
-   `ter:Timeout`
-   `ter:CredentialProviderError`
-   `ter:GeneralProviderError`
-   `ter:AuthenticationFailed`
-   `ter:Unavailable`
-   `ter:ResourceExists`
-   `ter:CriticalInternalError`

## Third party credential service API

axtpc = `http://www.axis.com/vapix/ws/thirdpartycredential`

Service in charge of creating and/or distributing access control credentials by integrating third-party credential service providers. Currently only HID Mobile access is supported.

### Service configuration
#### HIDMobilePartNumberInfo

Details about a particular Part Number that exists for the client’s HID Mobile Access account.

The following fields are available:

-   `token` - Unique ID of the Part Number.
-   `Name` - Human readable name of the Part Number.
-   `Description` - Description of the Part Number.
-   `Quantity` - The number of available Mobile IDs that are yet to be issued from this Part Number.

#### HIDMobileConfiguration

Data structure that contains all parameters needed to configure the HID Mobile Access credential provider. Required in order to issue HID Mobile Access credentials.

The following fields are available:

-   `PartNumbers` - Array of HIDMobilePartNumberInfo with details about each Part Number that exists for the account (Optional). Note: This parameter is only valid for GetProviderConfiguration.
-   `ClientId` - The client ID (login) for the HID Mobile Access account.
-   `ClientSecret` - The password for the HID Mobile Access account.
-   `ProxyURL` - HTTP(S) Proxy URL (Optional).
-   `ProxyPort` - HTTP(S) Proxy Port (Optional).
-   `ProxyUser` - HTTP(S) Proxy Username (Optional).
-   `ProxyPassword` - HTTP(S) Proxy Password (Optional)
-   `DefaultPartNumberToken` - Refers to the token of the Part Number in PartNumbers that should be used by default when creating credentials (Optional).
-   `PortalApiURL` - The URL of the HID Mobile Access Portal API (Optional) Note: Only used if the built-in default URL should be overridden.
-   `IdpURL` - The URL of the HID Mobile Access Authentication API (Optional). Note: Only used if the built-in default URL should be overridden.
-   `CardIdDataName` - The name of the Credentials IdData element where the card number should be stored (Optional). Note: Only used if the built-in default ("CardNr") should be overridden.

#### ProviderConfigurationInfo

A wrapper structure for HIDMobileConfiguration and other future provider configurations.

The following fields are available:

-   `HIDMobileConfig` - Configuration information for HID Mobile Access, see [HIDMobileConfiguration](#hidmobileconfiguration)

#### GetProviders command

Get a list of supported third-party credential providers.

-   Name: `GetProviders`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetProvidersRequest` | This message shall be empty. |
| `GetProvidersResponse` | This message contains:  
  
\- `Providers`: An array of supported credential providers.  
  
`axconf:ConfigurationInfo Providers [0][unbounded]` |

#### GetProviderConfiguration command

Get the configuration for the ProviderName.

-   Name: `GetProviderConfiguration`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetProviderConfigurationRequest` | This message contains  
  
\- `ProviderName` Provider to use for this API call. See `GetProviders.<br/><br/>`  
\- `ProviderActions` Additional actions and options for this provider.  
  
`pt:ReferenceToken ProviderName [1][1]`  
`pt:Attribute ProviderActions [0][unbounded]` |
| `GetProviderConfigurationResponse` | This message contains:  
  
\- `Configuration`: Configuration for the specified provider.  
  
`axtpc:ProviderConfigurationInfo Configuration [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### SetProviderConfiguration command

Set a Configuration for a specified provider.

-   Name: `SetProviderConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetProviderConfigurationRequest` | This message contains  
  
\- `ProviderName` Provider to use for this API call. See `GetProviders`.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `Configuration` Configuration for the specified provider.  
  
`pt:ReferenceTokenProviderName [1][1]`  
`pt:AttributeProviderActions [0][unbounded]`  
`axtpc:ProviderConfigurationInfoConfiguration [1][1]` |
| `SetProviderConfigurationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env: Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:CurlError` | Unspecified CURL error. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

### Third party credential management
#### HIDMobileOptions

HID Mobile Access specific credential options.

The following fields are available:

-   `PartNumberToken` - Token of the Part Number used to create this credential.
-   `InvitationCode` - The Invitation Code that was sent to the user´s e-mail and is connected to this credential. This code can be entered manually into the HID Mobile Access application on the user´s phone.

#### ThirdPartyOptions

A wrapper structure for HIDMobileOptions and other future provider specific credential options.

The following fields are available:

-   `HIDMobileOptions` - HID Mobile Access credential specific options, see [HIDMobileOptions](#hidmobileoptions)

#### ThirdPartyCredential

A data structure that describes a third-party credential. It consists of a regular access control credential along with provider specific credential options.

The following fields are available:

-   `Credential` - The regular access control credential structure containing most of the credential information.
-   `Options` - Third-party credential provider specific options.

#### SetThirdPartyCredential command

Create a Credential with a given third party provider.

-   Name: `SetThirdPartyCredential`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetThirdPartyCredentialRequest` | This message contains  
  
\- `ThirdPartyCredential` Access control to be sent.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this api call. See `GetProviders`.  
  
`axtpc:ThirdPartyCredentialThirdPartyCredential [1][1]`  
`pt:AttributeProviderActions [0][unbounded]`  
`pt:ReferenceTokenProviderName [1][1]` |
| `SetThirdPartyCredentialResponse` | This message contains:  
  
\- `Token`: The Token of the added Credential.  
  
`pt:ReferenceTokenToken [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Sender` `ter:InvalidArgVal` `ter:ResourceExists` | The requested resource already exists. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### GetThirdPartyCredentialList command

Get a list of Credentials.

-   Name: `GetThirdPartyCredentialList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetThirdPartyCredentialListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this API call. See `GetProviders`.  
  
`xs:intLimit [0][1]`  
`pt:ReferenceTokenStartReference [0][1]`  
`pt:AttributeProviderActions [0][unbounded]`  
`pt:ReferenceTokenProviderName [1][1]` |
| `GetThirdPartyCredentialListResponse` | This message contains  
  
\- `NextStartReference` StartReference to use in the next call to get the following items. If absent, no more items to get.  
\- `ThirdPartyCredentials` List of Credentials.  
  
`pt:ReferenceTokenNextStartReference [0][1]`  
`axtpc:ThirdPartyCredentialThirdPartyCredentials [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | StartReference is invalid or has timed out. Client need to start fetching from the beginning. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### GetThirdPartyCredential command

Get a third-party credential by token.

-   Name: `GetThirdPartyCredential`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetThirdPartyCredentialRequest` | This message contains:  
  
\- `Token`: Token of the Credential to fetch.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this API call. See `GetProviders`.  
  
`pt:ReferenceToken Token [1][1]`  
`pt:Attribute ProviderActions[0][unbounded]`  
`pt:ReferenceToken ProviderName[1][1]` |
| `GetThirdPartyCredentialResponse` | This message contains  
  
\- `ThirdPartyCredential` The requested credential.  
  
`axtpc: ThirdPartyCredential [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### GetThirdPartyCredentialByEmail command

Get a third-party credential by e-mail.

-   Name: `GetThirdPartyCredentialByEmail`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetThirdPartyCredentialByEmailRequest` | This message contains:  
  
\- `Email`: E-mail of the Credential to fetch.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this API call. See `GetProviders`  
`pt:ReferenceTokenEmail [1][1]`  
`pt:AttributeProviderActions [0][Unbounded]`  
`pt:ReferenceTokenProviderName [1][1]` |
| `GetThirdPartyCredentialByEmailResponse` | This message contains  
  
\- `ThirdPartyCredential` The requested credential.  
  
`axtpc:ThirdPartyCredential [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env: Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### RemoveThirdPartyCredential command

Remove the specified third party credential.

-   Name: `RemoveThirdPartyCredential`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveThirdPartyCredentialRequest` | This message contains:  
  
\- `Token`: Token of the Credential to remove.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this API call. See `GetProviders`.  
  
`pt:ReferenceTokenToken [1][1]`  
`pt:AttributeProviderActions [0][unbounded]`  
`pt:ReferenceTokenProviderName [1][1]` |
| `RemoveThirdPartyCredentialResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env: Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

#### RemoveThirdPartyCredentialByEmail command

Remove the specified third party Credential by e-mail address.

-   Name: `RemoveThirdPartyCredentialByEmail`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveThirdPartyCredentialByEmailRequest` | This message contains:  
  
\- `Email`: E-mail of the Credential to remove.  
\- `ProviderActions` Additional actions and options for this provider.  
\- `ProviderName` Provider to use for this API call. See `GetProviders`.  
  
`pt:ReferenceTokenEmail [1][1]`  
`pt:AttributeProviderActions[0][unbounded]`  
`pt:ReferenceTokenProviderName [1][1]` |
| `RemoveThirdPartyCredentialByEmailResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The requested resource was not found. |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidArgument` | The request contained an invalid argument. The fault reason will have more details. |
| `env:Receiver` `ter:NetworkError` `ter:Timeout` | Network request timed out. |
| `env:Receiver` `ter:NetworkError` `ter:ConnectionError` | Failed to connect to network resource. |
| `env:Receiver` `ter:CredentialProviderError` `ter:GeneralProviderError` | Unspecified error when communicating with the provider. The fault reason will have more details. |
| `env:Sender` `ter:CredentialProviderError` `ter:AuthenticationFailed` | Failed to authenticate with the credential provider. Please check provider login credentials. |
| `env:Receiver` `ter:CredentialProviderError` `ter:Unavailable` | Credential provider is currently unavailable. |

### Notification topics

The topics for the ThirdPartyCredential service are the following:

-   `tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialCreated`
-   `tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialCreatedFailed`
-   `tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialRemoved`
-   `tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialRemovedFailed`
-   `tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialEnabled`
-   `tnsaxis:ThirdPartyCredential/tnsaxis:Status/tnsaxis:ProviderConnection`

### Credential specific events
#### ThirdPartyCredential creation

Issued when a new ThirdPartyCredential has been created from the SetThirdPartyCredential API. At this point there may not exist any card data information for this credential. When the provider has acknowledged the credential a `ThirdPartyCredentialEnabled` event will be sent.

Topic: tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialCreated

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="CredentialToken" Type="pt:ReferenceToken" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="CredentialHolderName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialHolderEmail" Type="xs:string" />        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

#### ThirdPartyCredential creation failure

If a ThirdPartyCredential should fail to be created then this event will be issued.

Topic: tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialCreatedFailed

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="CredentialToken" Type="pt:ReferenceToken" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="CredentialHolderName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialHolderEmail" Type="xs:string" />        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

#### ThirdPartyCredential removal

Issued when a ThirdPartyCredential has been removed via the RemoveThirdPartyCredential API.

Topic: tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialRemoved

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="CredentialToken" Type="pt:ReferenceToken" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="CredentialHolderName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialHolderEmail" Type="xs:string" />        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

#### ThirdPartyCredential removal failure

Issued when a ThirdPartyCredential failed to be removed via the RemoveThirdPartyCredential API.

Topic: tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialRemovedFailed

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="CredentialToken" Type="pt:ReferenceToken" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="CredentialHolderName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialHolderEmail" Type="xs:string" />        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

#### ThirdPartyCredential enabled

Issued when the provider has acknowledged the ThirdPartyCredential. Note that the format of the 'CredentialCardNumber' is specific for each provider.

Topic: tns1:Configuration/tns1:Credential/tnsaxis:ThirdPartyCredentialEnabled

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="CredentialToken" Type="pt:ReferenceToken" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="CredentialHolderEmail" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialFirstName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialLastName" Type="xs:string" />        <tt:SimpleItemDescription Name="CredentialCardNumber" Type="xs:string" />        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

### Provider specific events
#### ProviderConnection

Any change in the status of the connection to the provider will generate this event.

Topic: tnsaxis:ThirdPartyCredential/tnsaxis:Status/tnsaxis:ProviderConnection

```bash
<tt:MessageDescription IsProperty="true">    <tt:Source>        <tt:SimpleItemDescription Name="ProviderName" Type="xs:string" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="Connected" Type="xs:boolean" />    </tt:Data></tt:MessageDescription>
```