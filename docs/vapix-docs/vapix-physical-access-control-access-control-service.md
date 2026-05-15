---
title: Access control service
url: "https://developer.axis.com/vapix/physical-access-control/access-control-service/"
category: vapix
subcategory: physical-access-control
sha256: 7cef2aa999b038f2d92bed590524846e3d3f31c50fdc0c1762f93867433fdf50
scraped_at: "2026-01-09T15:21:37.744Z"
page_height: 159833
---

# Access control service

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Access control service guide

The AccessControl service handles authentication of credential holders, that is, the service determines where and when a credential holder will get access.

### Set up the initial system

This section describes how to set up an initial system for allowing access to a door, and explains the necessary data structures and how these work together. The order in which the data structures are set does not matter. The API functions for getting, setting, and removing data structures are named according to the type of data item handled, as summarized in the table below.

API functions for getting, setting and removing data structures.

| Name | Description |
| --- | --- |
| `pacsaxis:SetAccessController`  
`pacsaxis:SetAccessPoint`  
`pacsaxis:SetAccessProfile`  
`pacsaxis:SetAuthenticationProfile`  
`pacsaxis:SetCredential`  
`pacsaxis:SetAccessControllerConfiguration` | Sets the supplied data items in the AccessControl Service. |
| `pacsaxis:GetAccessControllerList`  
`pacsaxis:GetAccessPointList`  
`pacsaxis:GetAccessProfileList`  
`pacsaxis:GetAuthenticationProfileList`  
`pacsaxis:GetCredentialList` | Retrieves a list of available data items. It is possible to specify limits and offsets to only retrieve selected parts of the data items. |
| `pacsaxis:GetAccessController`  
`pacsaxis:GetAccessPoint`  
`pacsaxis:GetAccessProfile`  
`pacsaxis:GetAuthentication`  
`pacsaxis:GetCredential`  
`pacsaxis:GetAccessControllerConfiguration` | Retrieves a list of data items as specified by the supplied token list. If the token list is empty, all data items are retrieved. |
| `pacsaxis:GetCredentialStatistics` | Lists the total number of credentials and the number of disabled credentials. |
| `pacsaxis:RemoveAccessController`  
`pacsaxis:RemoveAccessPoint`  
`pacsaxis:RemoveAccessProfile`  
`pacsaxis:RemoveAuthenticationProfile`  
`pacsaxis:RemoveCredential`  
`pacsaxis:RemoveAccessControllerConfiguration` | Removes the data items specified by the supplied token list. |
| `pacsaxis:ResetAntipassbackViolation`  
`pacsaxis:ResetAllAntipassbackViolations`  
`pacsaxis:GetAntipassbackDataList`  
`pacsaxis:SetAntipassbackData` | Lists, sets and resets anti-passback monitoring data. |

#### Retrieve default configuration

The initial configuration data structures for the AccessControl service are an access controller and default authentication profiles. These are provided to make it easier to configure the system, as the device UUID will be set in the access controller, and commonly used authentication profiles are already available.

The access controller is represented by two data types: `AccessController` and `AccessControllerConfiguration`. These are the most basic representations of the device in the Access-Control service and the default data is retrieved by calling API functions `pacsaxis:GetAccessControllerList` and `pacsaxis:GetAccessControllerConfigurationList`. The following example shows the default configuration:

```bash
{    "AccessController": \[        {            "token": "Axis-00408c184bdb AccessController",            "Name": "Axis-00408c184bdb AccessController",            "Description": "",            "AccessPoint": \[\]        }    \]}
```

```bash
{    "AccessControllerConfiguration": \[        {            "token": "Axis-00408c184bdb AccessController",            "DeviceUUID": "5581ad80-95b0-11e0-b883-00408c184bdb",            "Configuration": \[\]        }    \]}
```

```bash
<AccessController token="Axis-00408c184bdb AccessController">    <AccessPoint></AccessPoint>    <Description></Description>    <Name>Axis-00408c184bdb AccessController</Name></AccessController><AccessControllerConfiguration token="Axis-00408c184bdb AccessController">    <DeviceUUID>5581ad80-95b0-11e0-b883-00408c184bdb</DeviceUUID></AccessControllerConfiguration>
```

The access controller contains an `AccessPoint` that links to the access points of this door controller. This is described further in section [Setting the access point](#setting-the-access-point). The authentication profiles are represented by `AuthenticationProfile` and are used to set up the type of credential data that must be provided in order to be granted access. The default authentication profiles are for access using only access card, using only PIN, using access card with PIN and using a REX device. The default profiles can be retrieved by calling the API function `pacsaxis:GetAuthenticationProfileList`. The following data is returned:

```bash
{    "AuthenticationProfile": \[        {            "token": "CardOnly",            "Name": "CardOnly",            "Description": "Card only",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        },        {            "token": "PINOnly",            "Name": "PINOnly",            "Description": "PIN only",            "IdFactor": \[                {                    "IdDataName": "PIN",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        },        {            "token": "CardPlusPin",            "Name": "CardPlusPin",            "Description": "Card + PIN",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                },                {                    "IdDataName": "PIN",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        },        {            "token": "REXOnly",            "Name": "REXOnly",            "Description": "REX only",            "IdFactor": \[                {                    "IdDataName": "REX",                    "IdMatchOperatorName": "OperatorValueEqual",                    "OperatorValue": "Active"                }            \],            "Schedule": \["standard\_always"\]        }    \]}
```

```bash
<AuthenticationProfile token="CardOnly">    <Description>Card only</Description>    <IdFactor>        <IdDataName>Card</IdDataName>        <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>        <OperatorValue></OperatorValue>    </IdFactor>    <Name>CardOnly</Name>    <Schedule>standard\_always</Schedule></AuthenticationProfile><AuthenticationProfile token="PINOnly">    <Description>PIN only</Description>    <IdFactor>        <IdDataName>PIN</IdDataName>        <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>        <OperatorValue></OperatorValue>    </IdFactor>    <Name>PINOnly</Name>    <Schedule>standard\_always</Schedule></AuthenticationProfile><AuthenticationProfile token="CardPlusPin">    <Description>Card + PIN</Description>    <IdFactor>        <IdDataName>Card</IdDataName>        <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>        <OperatorValue></OperatorValue>    </IdFactor>    <IdFactor>        <IdDataName>PIN</IdDataName>        <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>        <OperatorValue></OperatorValue>    </IdFactor>    <Name>CardPlusPin</Name>    <Schedule>standard\_always</Schedule></AuthenticationProfile><AuthenticationProfile token="REXOnly">    <Description>REX only</Description>    <IdFactor>        <IdDataName>REX</IdDataName>        <IdMatchOperatorName>OperatorValueEqual</IdMatchOperatorName>        <OperatorValue>Active</OperatorValue>    </IdFactor>    <Name>REXOnly</Name>    <Schedule>standard\_always</Schedule></AuthenticationProfile>
```

The `IdFactor` fields describe the data used by the profile to validate if a request should be granted or denied. If the profile has more than one required `IdFactor`, then all must be available and added in the same order as in the `IdFactor` array, and if fewer are provided then the AccessControl service asks the user for additional ones, or deny the request if no credential can be linked to the initial `IdFactor`. For example, if only the valid card number is provided for the `CardPlusPin`profile, then the AccessControl service asks for the PIN as well. This is done by flashing LEDs, if available, on the card reader to notify the user that further credentials are needed.

The default data is not constant and can be removed or replaced if necessary. The data is restored when resetting the door controller to factory default settings.

When adding, deleting or changing an `AuthenticationProfile`, the internal representation of data types in the system must be updated. During the update, access requests are not be handled. For systems with a large number of credentials, an update can take several minutes and it is recommended to only change `AuthenticationProfile`:s at times when immediate system response is not required.

#### Setting the access point

The `AccessPoint` represents the entity a user can access and is the link between the AccessControl Service and the Door Control and IdPoint Services. A door can have more than one `AccessPoint`, for example when using a card reader at one side of the door and a REX device on the other side.

The `AccessPoint` data structure is set to the AccessControl Service by calling the API function `pacsaxis:SetAccessPoint`. The following is an example of an `AccessPoint`:

```bash
{    "pacsaxis:SetAccessPoint": {        "AccessPoint": \[            {                "token": "Axis-00408c184bdb:1351589192.102223000",                "Name": "Entry 1",                "Description": "Entry 1 main door",                "AreaFrom": "",                "AreaTo": "",                "EntityType": "axtdc:Door",                "Entity": "Door0",                "DoorDeviceUUID": "",                "Enabled": true,                "IdPointDevice": \[{ "IdPoint": "idpoint\_token", "DeviceUUID": "" }\],                "AuthenticationProfile": \["CardOnly"\],                "Attribute": \[\],                "ActionArgument": \[\],                "Action": "Access"            }        \]    }}
```

```bash
<pacsaxis:SetAccessPoint>    <pacsaxis:AccessPoint token="Axis-00408c184bdb:1351589192.102223000">        <Action>Access</Action>        <AreaFrom />        <AreaTo />        <AuthenticationProfile>CardOnly</AuthenticationProfile>        <Description>Entry 1 main door</Description>        <DoorDeviceUUID />        <Enabled>true</Enabled>        <Entity>Door0</Entity>        <IdPointDevice>            <DeviceUUID />            <IdPoint>idpoint\_token</IdPoint>        </IdPointDevice>        <Name>Entry 1</Name>        <EntityType>axtdc:Door</EntityType>    </pacsaxis:AccessPoint></pacsaxis:SetAccessPoint>
```

The example shows the `Door` entity and the `IdPoint` entities that are connected to this `AccessPoint`.

To connect a `Door` to the `AccessPoint`, the type of connected entity should be specified by setting the `EntityType` field to `axtdc:Door`. `axtdc:Door` is also the default value and is used if `EntityType` is empty. In the `Door` data structure, the token should be set to `Entity`.

To connect one or more `IdPoint`:s, specify the token for each `IdPoint` in the `IdPointDevice` array.

The two UUID fields `DoorDeviceUUID` and `DeviceUUID` are left empty as the `IdPoint` and `Door` are connected to the same door controller as the `AccessPoint`.

The `AuthenticationProfile` list specifies which authentication profiles to use with the `IdPoint` when allowing access to the connected `Door`. The authentication profiles can be overridden by other authentication profiles as described in section [Override the authentication of an access point](#override-the-authentication-of-an-access-point).

The `Action` field specifies the action associated with the `AccessPoint`. Typical actions are `Access`, `AccessDoor` and `AccessDoorWithoutUnlock`. If no action is specified, the default action `Access` is used. Access requests must have an action that matches the action in the `AccessPoint`, see section [Send access request](#send-access-request).

The `ActionArgument` field specifies arguments to be used together with the action. Each argument has a `Name`, a `Value` and, optionally, a `Type` that specifies the type of action.

After setting a new `AccessPoint` to the AccessControl service, it is necessary to refer to it in the `AccessController`. For example, with the `AccessController` from section [Retrieve default configuration](#retrieve-default-configuration), it would be necessary to replace it with the following that now includes the `token` of the `AccessPoint` (bold marks the new addition). Setting `AccessController` is done by calling `pacsaxis:SetAccessController`:

```bash
{    "pacsaxis:SetAccessController": {        "AccessController": \[            {                "token": "Axis-00408c184bdb AccessController",                "Name": "Axis-00408c184bdb AccessController",                "Description": "",                "AccessPoint": \["Axis-00408c184bdb:1351589192.102223000"\]            }        \]    }}
```

```bash
<pacsaxis:SetAccessController>    <AccessController token="Axis-00408c184bdb AccessController">        <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>        <Description />        <Name>Axis-00408c184bdb AccessController</Name>    </AccessController></pacsaxis:SetAccessController>
```

#### Setting the access profile

The access profile describes which entities can be accessed, and when this is allowed. This means that the access profile groups different access points together, and describes certain rules for them. In a way, the access profile can be seen as a group bundling users to a set of access points.

The `AccessProfile` data structure is as follows, and is set to the AccessControl service by calling the API function `pacsaxis:SetAccessProfile`:

```bash
{    "pacsaxis:SetAccessProfile": {        "AccessProfile": \[            {                "token": "Axis-00408c184bdb:1351591416.539133000",                "Name": "AccessProfile1",                "Description": "AccessProfile description",                "Enabled": true,                "Schedule": \["standard\_always"\],                "ValidFrom": "1997-01-01T00:00:00Z",                "ValidTo": "2038-01-01T00:00:00Z",                "AuthenticationProfile": \[\],                "AccessPolicy": \[                    {                        "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                        "AuthorizationProfile": \[\],                        "Attribute": \[\],                        "Schedule": \["standard\_always"\]                    }                \]            }        \]    }}
```

```bash
<pacsaxis:SetAccessProfile>    <AccessProfile token="Axis-00408c184bdb:1351591416.539133000">        <AccessPolicy>            <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>            <Schedule>standard\_always</Schedule>        </AccessPolicy>        <Description>AccessProfile description</Description>        <Enabled>true</Enabled>        <Name>AccessProfile1</Name>        <Schedule>standard\_always</Schedule>        <ValidFrom>1997-01-01T00:00:00Z</ValidFrom>        <ValidTo>2038-01-01T00:00:00Z</ValidTo>    </AccessProfile></pacsaxis:SetAccessProfile>
```

The `AccessPoints` that should be affected by this `AccessProfile` are listed by their tokens in `AccessPolicy`. This is illustrated above, as the `AccessPoint`’s token from the example in section [Setting the access point](#setting-the-access-point) is set here (marked in bold). For this example, the `AccessProfile` is always active by setting the schedule to `standard_always` (schedules are further discussed in section [Specify time-dependent access behavior](#specify-time-dependent-access-behavior)).

The `AuthenticationProfile`, `Schedule`, and `ValidFrom/ValidTo` fields is described in later sections.

#### Setting the credential

The `Credential` contains the credentials that a user (credential holder) must provide to get access to the door, for example card and PIN code. The `Credential` also specifies the access profiles where the credentials can be used. A single `Credential` can represent a unique user with a unique card and PIN, or it can represent a group of users with the same credentials.

The `Credential` data structure is set to the access control service using the API function `pacsaxis:SetCredential` as shown in the following example:

```bash
{    "pacsaxis:SetCredential": {        "Credential": \[            {                "token": "Axis-00408c184bdb:1351593020.016190000",                "UserToken": "user\_token1",                "Description": "Credential description",                "ValidFrom": "1997-01-01T00:00:00Z",                "ValidTo": "2038-01-01T00:00:00Z",                "Enabled": true,                "Status": "Enabled",                "IdData": \[                    {                        "Name": "Card",                        "Value": "12345678"                    },                    {                        "Name": "PIN",                        "Value": "1234"                    }                \],                "Attribute": \[\],                "AuthenticationProfile": \[\],                "CredentialAccessProfile": \[                    {                        "ValidFrom": "1997-01-01T00:00:00Z",                        "ValidTo": "2038-01-01T00:00:00Z",                        "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"                    }                \]            }        \]    }}
```

```bash
<pacsaxis:SetCredential>    <Credential token="Axis-00408c184bdb:1351593020.016190000">        <CredentialAccessProfile>            <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>            <ValidFrom>1997-01-01T00:00:00Z</ValidFrom>            <ValidTo>2038-01-01T00:00:00Z</ValidTo>        </CredentialAccessProfile>        <Description>Credential description</Description>        <Enabled>true</Enabled>        <IdData Name="Card" Value="12345678" />        <IdData Name="PIN" Value="1234" />        <Status>Enabled</Status>        <UserToken>user\_token1</UserToken>        <ValidFrom>1997-01-01T00:00:00Z</ValidFrom>        <ValidTo>2038-01-01T00:00:00Z</ValidTo>    </Credential></pacsaxis:SetCredential>
```

As can be seen in the example above, the credential has a link to each access profile that applies. The `CredentialAccessProfile` field contains all `AccessProfiles` the `Credential` may use.

This example includes the `AccessProfile` from [Setting the access profile](#setting-the-access-profile) (marked in bold). This gives the `Credential` access to the `AccessPoints` specified in the `AccessProfile`.

The `IdData` contains valid identification data for this `Credential`, which in this example is both `Card` and `PIN`. This data is used to identify and validate the user, depending on necessary authorization requirements of the current `AuthenticationProfile`.

If an `IdData`\-field with the name "CardNr" is supplied, an extra validation is performed when adding the credential to make sure that no other `IdData`\-field with the name "CardNr" has the same value. This is a special case added to support the use case of having unique card numbers.

Note that no validation is performed on any other `IdData`\-field except for "CardNr" to ensure that the value is unique to the system.

Further note that the `IdData`\-name is unique on the credential; There is no support for having two, for example, `PIN` `IdData`\-fields on one credential.

The `AuthenticationProfile` and `ValidFrom/ValidTo` fields are described in later sections. The `UserToken` is an optional field of the credential, and is used to link the `Credential` to a `User` as described in [User service guide](/vapix/physical-access-control/user-service/#user-service-guide).

The `Attribute` field can be used if the `Credential` should use the `ExtendedAccessTime` defined in the `Door`, see [Extend access time for a credential](#extend-access-time-for-a-credential).

#### Credential statistics

Use `pacsaxis:GetCredentialStatistics` to list the total number of credentials in the system and the number of disabled credentials. If there are 1000 credentials and 5 credentials are disabled, the call returns:

```bash
{    "CredentialStatistics": {        "NumberOfCredentials": 1000,        "NumberOfDisabledCredentials": 5    }}
```

```bash
<CredentialStatistics>    <NumberOfCredentials>1000</NumberOfCredentials>    <NumberOfDisabledCredentials>5</NumberOfDisabledCredentials></CredentialStatistics>
```

#### Overview of the initial system

The diagram shows the initial system as described previously in section [Set up the initial system](#set-up-the-initial-system).

![Overview of the initial system](/assets/images/access-control-service.t10069727-d422983bbb8174d9ee0d019e3f4d9e8b.png)

### Send access request

It is possible to send an access request to the AccessControl service. This is equivalent to initiating an access request from an ID point. If the request is granted, affected doors become accessible (if this is the specified behavior).

It is possible to verify if the request would be granted. Verification reaches the same decisions as the access request, but without interacting with any doors or ID points.

The access request shall provide `IdData` that will be matched against existing `Credentials`. The matching ensures that the credential is valid and allowed to access the access point by checking all rules for the credential, access profile, and access point. It also ensures that the request operates on the correct access controller.

If a request’s `IdData` has mixed `IdMatchOperatorName` (specified in the Authentication Profile) then `IdDataEqual` (CardNr, PIN, etc) is chosen over `OperatorValueEqual` (used by REX).

Access requests when using REX devices are almost identical to card and PIN, but with the exception of that is not relevant to check the credential and it is excluded from the check.

The following example illustrates an access request, and the API function `RequestAccess` can be replaced by `VerifyRequest` without changing the parameters to verify:

Request

```bash
{    "pacsaxis:RequestAccess": {        "Action": "Access",        "IdData": \[            {                "Name": "Card",                "Value": "12345678"            }        \],        "SourceToken": "idp\_token",        "TargetToken": "door\_token",        "Token": "Axis-00408c184bdb AccessController"    }}
```

Request

```bash
<pacsaxis:RequestAccess>    <Action>Access</Action>    <IdData Name="Card" Value="12345678" />    <SourceToken>idp\_token</SourceToken>    <TargetToken>door\_token</TargetToken>    <Token>Axis-00408c184bdb AccessController</Token></pacsaxis:RequestAccess>
```

The `Token` field shall match the `token` of `AccessController` where the request applies; `SourceToken` shall match the token of the `IdPoint` where this request originates from; `TargetToken` shall be used to specify the `token` of the `Door` the request attempts to access, but may be left empty as the request defaults to the available `Door` of the `AccessPoint` where the `IdPoint` resides. The `Action` shall specify what to do on the target resource, i.e. the `Action` as specified in the `AccessPoint`.

The AccessControl service responds with the result of the access/verification request. The response is given as the result, together with a reason if not granted. See the following examples, where the last one exemplifies the case with an invalid card or PIN:

Response

```bash
{    "AccessGranted": true,    "Reason": "Granted"}
```

Response

```bash
{    "AccessGranted": false,    "Reason": "InvalidCredential"}
```

Response

```bash
{    "AccessGranted": false,    "Reason": "InvalidCredential"}
```

Response

```bash
<AccessGranted>true</AccessGranted><Reason>Granted</Reason>
```

The AccessControl service also issues events at the end of any processed requested access. For a granted request, two events are sent. The first event is always `AccessControl/AccessGranted/Credential`, or `AccessControl/AccessGranted/Anonymous` if an anonymous access was requested. If more than one credential could be matched against the request in the case of, for example, PIN only access where two or more users share the same PIN then the `CredentialToken` is empty to signify that a specific credential couldn’t be found. The same goes for `CredentialHolderName` when multiple users gets access. The second event depends on whether the action was taken (i.e. the door was opened) or not, and is either `AccessControl/AccessTaken/Credential`, or `AccessControl/AccessNotTaken/Credential`. The events contain information about the processed request as described by the following examples of the AccessGranted events:

```bash
\[    {        "rowid": 317,        "token": "Axis-00408c185451:1383231311.023721000",        "UUID": "5581ad80-95b0-11e0-b883-00408c185451",        "UtcTime": "2013-10-31T14:55:10.136376Z",        "KeyValues": \[            {                "Key": "CredentialHolderName",                "Value": "user\_token1",                "Tags": \["onvif-data"\]            },            {                "Key": "AccessPointToken",                "Value": "Axis-00408c185451:1383040794.997528000",                "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]            },            {                "Key": "topic2",                "Value": "Credential",                "Tags": \[\]            },            {                "Key": "topic1",                "Value": "AccessGranted",                "Tags": \[\]            },            {                "Key": "topic0",                "Value": "AccessControl",                "Tags": \[\]            },            {                "Key": "CredentialToken",                "Value": "Axis-00408c185451:1383215256.021032000",                "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]            }        \],        "Tags": \[\]    },    {        "rowid": 325,        "token": "Axis-00408c185451:1383231432.473419000",        "UUID": "5581ad80-95b0-11e0-b883-00408c185451",        "UtcTime": "2013-10-31T14:57:12.106469Z",        "KeyValues": \[            {                "Key": "CredentialHolderName",                "Value": "user\_token1",                "Tags": \["onvif-data"\]            },            {                "Key": "AccessPointToken",                "Value": "Axis-00408c185451:1383040794.997528000",                "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]            },            {                "Key": "topic2",                "Value": "Credential",                "Tags": \[\]            },            {                "Key": "topic1",                "Value": "AccessTaken",                "Tags": \[\]            },            {                "Key": "topic0",                "Value": "AccessControl",                "Tags": \[\]            },            {                "Key": "CredentialToken",                "Value": "Axis-00408c185451:1383215256.021032000",                "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]            }        \],        "Tags": \[\]    }\]
```

```bash
<axlog:Event>  <axlog:rowid>167</axlog:rowid>  <axlog:token>Axis-00408c185451:1383212989.293991001</axlog:token>  <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>  <axlog:UtcTime>2013-10-31T09:49:48Z</axlog:UtcTime>  <axlog:KeyValues>    <axlog:Key>CredentialHolderName</axlog:Key>    <axlog:Value>user\_token1</axlog:Value>    <axlog:Tags>onvif-data</axlog:Tags>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>AccessPointToken</axlog:Key>    <axlog:Value>Axis-00408c185451:1383040794.997528000</axlog:Value>    <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>    <axlog:Tags>onvif-source</axlog:Tags>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic2</axlog:Key>    <axlog:Value>Credential</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic1</axlog:Key>    <axlog:Value>AccessGranted</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic0</axlog:Key>    <axlog:Value>AccessControl</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>CredentialToken</axlog:Key>    <axlog:Value>Axis-00408c185451:1383040823.666869000</axlog:Value>    <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>    <axlog:Tags>onvif-data</axlog:Tags>  </axlog:KeyValues></axlog:Event><axlog:Event>  <axlog:rowid>175</axlog:rowid>  <axlog:token>user\_token1</axlog:token>  <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>  <axlog:UtcTime>2013-10-31T09:56:59Z</axlog:UtcTime>  <axlog:KeyValues>    <axlog:Key>CredentialHolderName</axlog:Key>    <axlog:Value>Axis-00408c185451:1383040823.038021000</axlog:Value>    <axlog:Tags>onvif-data</axlog:Tags>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>AccessPointToken</axlog:Key>    <axlog:Value>Axis-00408c185451:1383040794.997528000</axlog:Value>    <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>    <axlog:Tags>onvif-source</axlog:Tags>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic2</axlog:Key>    <axlog:Value>Credential</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic1</axlog:Key>    <axlog:Value>AccessTaken</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>topic0</axlog:Key>    <axlog:Value>AccessControl</axlog:Value>  </axlog:KeyValues>  <axlog:KeyValues>    <axlog:Key>CredentialToken</axlog:Key>    <axlog:Value>Axis-00408c185451:1383040823.666869000</axlog:Value>    <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>    <axlog:Tags>onvif-data</axlog:Tags>  </axlog:KeyValues></axlog:Event>
```

If the request was not granted, then an event is dispatched depending on the reason. There exist several different events for this, some of which are discussed further in the following sections. The event for not entering with a valid credential, i.e. wrong card, is `AccessControl/Denied/CredentialNotFound/Card`. This event looks as follows:

```bash
{    "rowid": 330,    "token": "Axis-00408c185451:1383232007.384795000",    "UUID": "5581ad80-95b0-11e0-b883-00408c185451",    "UtcTime": "2013-10-31T15:06:46.680154Z",    "KeyValues": \[        {            "Key": "Card",            "Value": "00007352",            "Tags": \["onvif-data"\]        },        {            "Key": "CardNr",            "Value": "87654321",            "Tags": \["onvif-data"\]        },        {            "Key": "AccessPointToken",            "Value": "Axis-00408c185451:1383040794.997528000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]        },        {            "Key": "topic2",            "Value": "CredentialNotFound",            "Tags": \[\]        },        {            "Key": "topic1",            "Value": "Denied",            "Tags": \[\]        },        {            "Key": "topic0",            "Value": "AccessControl",            "Tags": \[\]        },        {            "Key": "topic3",            "Value": "Card",            "Tags": \[\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>180</axlog:rowid>    <axlog:token>Axis-00408c185451:1383213861.994990000</axlog:token>    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>    <axlog:UtcTime>2013-10-31T10:04:21Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>Card</axlog:Key>        <axlog:Value>00008765</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>CardNr</axlog:Key>        <axlog:Value>87654321</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>AccessPointToken</axlog:Key>        <axlog:Value>Axis-00408c185451:1383040794.997528000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic2</axlog:Key>        <axlog:Value>CredentialNotFound</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        <axlog:Value>Denied</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic3</axlog:Key>        <axlog:Value>Card</axlog:Value>    </axlog:KeyValues></axlog:Event>
```

Note that all other events when access is denied contain the `CredentialToken` rather than the `Card` field. Card field is only relevant in the case when the `Credential` is not found.

### Disable selected parts of a service

Selected `Credential`, `AccessProfile`, and `AccessPoint` data items can be disabled and enabled. Disabled items are ignored when the door controller evaluates access requests.

To disable and enable an item, use one of the following methods:

-   Toogle the boolean `Enabled` field when setting the data structure.
-   Use the provided enable and disable API functions. This option is not available for `AccessProfile`.

#### Disable a credential

To disable a credential, use `pacsaxis:DisableCredential`:

Request

```bash
{    "pacsaxis:DisableCredential": {        "Token": "Axis-00408c184bdb:1351593020.016190000",        "Status": "Disabled"    }}
```

Request

```bash
<pacsaxis:DisableCredential>    <Status>Disabled</Status>    <Token>Axis-00408c184bdb:1351593020.016190000</Token></pacsaxis:DisableCredential>
```

The `Status` field is optional but is submitted here to help human readers to note that the credential is disabled. To enable the credential, call `pacsaxis:EnableCredential` without the `Status` field, which then defaults to "Enabled".

A disabled `Credential` has the following data structure (with the changes marked in bold):

```bash
{    "Credential": {        "token": "Axis-00408c184bdb:1351593020.016190000",        "UserToken": "user\_token1",        "Description": "Credential description",        "ValidFrom": "",        "ValidTo": "",        "Enabled": false,        "Status": "Disabled",        "IdData": \[            {                "Name": "Card",                "Value": "12345678"            },            {                "Name": "PIN",                "Value": "1234"            }        \],        "Attribute": \[\],        "AuthenticationProfile": \[\],        "CredentialAccessProfile": \[            {                "ValidFrom": "",                "ValidTo": "",                "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"            }        \]    }}
```

```bash
<Credential token="Axis-00408c184bdb:1351593020.016190000">    <CredentialAccessProfile>        <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>        <ValidFrom />        <ValidTo />    </CredentialAccessProfile>    <Description>Credential description</Description>    <Enabled>false</Enabled>    <IdData Name="Card" Value="12345678" />    <IdData Name="PIN" Value="1234" />    <Status>Disabled</Status>    <UserToken>user\_token1</UserToken>    <ValidFrom />    <ValidTo /></Credential>
```

The Access Control Service returns `CredentialNotEnabled` in response to an access request with a disabled `Credential`. The service also generates the event `AccessControl/Denied/Credential` with `Reason` set to `CredentialNotEnabled`:

```bash
{    "rowid": 336,    "token": "Axis-00408c185451:1383232272.025462002",    "UUID": "5581ad80-95b0-11e0-b883-00408c185451",    "UtcTime": "2013-10-31T15:11:11.955788Z",    "KeyValues": \[        {            "Key": "CredentialHolderName",            "Value": "user\_token1",            "Tags": \["onvif-data"\]        },        {            "Key": "Reason",            "Value": "CredentialNotEnabled",            "Tags": \["onvif-data"\]        },        {            "Key": "AccessPointToken",            "Value": "Axis-00408c185451:1383040794.997528000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]        },        {            "Key": "topic2",            "Value": "Credential",            "Tags": \[\]        },        {            "Key": "topic1",            "Value": "Denied",            "Tags": \[\]        },        {            "Key": "topic0",            "Value": "AccessControl",            "Tags": \[\]        },        {            "Key": "CredentialToken",            "Value": "Axis-00408c184bdb:1351593020.016190000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>183</axlog:rowid>    <axlog:token>Axis-00408c185451:1383214246.055026000</axlog:token>    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>    <axlog:UtcTime>2013-10-31T10:10:45Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>CredentialHolderName</axlog:Key>        <axlog:Value>user\_token1</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>Reason</axlog:Key>        <axlog:Value>CredentialNotEnabled</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>AccessPointToken</axlog:Key>        <axlog:Value>Axis-00408c185451:1383040794.997528000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic2</axlog:Key>        <axlog:Value>Credential</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        <axlog:Value>Denied</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>CredentialToken</axlog:Key>        <axlog:Value>Axis-00408c185451:1383040823.666869000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues></axlog:Event>
```

#### Disable an access point

To disable and enabled access points, use `tac:DisableAccessPoint` and `tac:EnableAccessPoint`. The requests are similar to the corresponding credential requests but do not have any status field. The example below shows `DisableAccessPoint`:

Request

```bash
{    "tac:DisableAccessPoint": {        "Token": "Axis-00408c184bdb:1351589192.102223000"    }}
```

Request

```bash
<tac:DisableAccessPoint>    <Token>Axis-00408c184bdb:1351589192.102223000</Token></tac:DisableAccessPoint>
```

A disabled `AccessPoint` has the following data structure (with the changes marked in bold):

```bash
{    "AccessPoint": {        "token": "Axis-00408c184bdb:1351589192.102223000",        "Name": "Entry 1",        "Description": "Entry 1 main door",        "AreaFrom": "",        "AreaTo": "",        "Type": "tdc:Door",        "Entity": "Door0",        "DoorDeviceUUID": "",        "Enabled": false,        "IdPointDevice": \[            {                "IdPoint": "idpoint\_token",                "DeviceUUID": ""            }        \],        "AuthenticationProfile": \["CardOnly"\],        "Attribute": \[\],        "ActionArgument": \[\],        "Action": "Access"    }}
```

```bash
<AccessPoint token="Axis-00408c184bdb:1351589192.102223000">    <Action>Access</Action>    <AreaFrom />    <AreaTo />    <AuthenticationProfile>CardOnly</AuthenticationProfile>    <Description>Entry 1 main door</Description>    <DoorDeviceUUID />    <Enabled>false</Enabled>    <Entity>Door0</Entity>    <IdPointDevice>        <DeviceUUID />        <IdPoint>idpoint\_token</IdPoint>    </IdPointDevice>    <Name>Entry 1</Name>    <Type>tdc:Door</Type></AccessPoint>
```

The AccessControl Service returns `Unauthorized` in response to an access request with a disabled `AccessPoint`. The service also generates the event `AccessControl/Denied/Credential`:

```bash
{    "Data": {        "CredentialHolderName": "user\_token1",        "CredentialToken": "Axis-00408c184bdb:1351593020.016190000",        "Reason": "Unauthorized"    },    "Source": { "AccessPointToken": "Axis-00408c184bdb:1351589192.102223000" },    "Topic": "tns1:AccessControl/Denied/Credential",    "UtcTime": "2012-10-31T08:25:32Z"}
```

```bash
<Data><CredentialHolderName>user\_token1</CredentialHolderName><CredentialToken>Axis-00408c184bdb:1351593020.016190000</CredentialToken><Reason>Unauthorized</Reason></Data><Source><AccessPointToken>Axis-00408c184bdb:1351589192.102223000</AccessPointToken></Source><Topic>tns1:AccessControl/Denied/Credential</Topic><UtcTime>2012-10-31T08:25:32Z</UtcTime>
```

#### Disable an access profile

For `AccessProfile`:s, there are no enable and disable API functions. Instead, call `pacsaxis:SetAccessProfile` to set the `Enabled` field to `false`.

```bash
{    "pacsaxis:SetAccessProfile": {        "AccessProfile": \[            {                "token": "Axis-00408c184bdb:1351591416.539133000",                "Name": "AccessProfile1",                "Description": "AccessProfile description",                "ValidFrom": "",                "ValidTo": "",                "Enabled": false,                "Schedule": \["standard\_always"\],                "AuthenticationProfile": \[\],                "Attribute": \[\],                "AccessPolicy": \[                    {                        "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                        "AuthorizationProfile": \[\],                        "Attribute": \[\],                        "Schedule": \["standard\_always"\]                    }                \]            }        \]    }}
```

```bash
<AccessProfile token="Axis-00408c184bdb:1351591416.539133000">    <AccessPolicy>        <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>        <Schedule>standard\_always</Schedule>    </AccessPolicy>    <Description>AccessProfile description</Description>    <Enabled>false</Enabled>    <Name>AccessProfile1</Name>    <Schedule>standard\_always</Schedule>    <ValidFrom />    <ValidTo /></AccessProfile>
```

The AccessControl Service returns `InvalidAccessProfile` in response to an access request with a disabled `AccessProfile`. The service also generates the event `AccessControl/Denied/Credential`:

```bash
{    "rowid": 339,    "token": "Axis-00408c185451:1383232539.745263001",    "UUID": "5581ad80-95b0-11e0-b883-00408c185451",    "UtcTime": "2013-10-31T15:15:39.249125Z",    "KeyValues": \[        {            "Key": "CredentialHolderName",            "Value": "user\_token1",            "Tags": \["onvif-data"\]        },        {            "Key": "Reason",            "Value": "InvalidAccessProfile",            "Tags": \["onvif-data"\]        },        {            "Key": "AccessPointToken",            "Value": "Axis-00408c184bdb:1351589192.102223000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]        },        {            "Key": "topic2",            "Value": "Credential",            "Tags": \[\]        },        {            "Key": "topic1",            "Value": "Denied",            "Tags": \[\]        },        {            "Key": "topic0",            "Value": "AccessControl",            "Tags": \[\]        },        {            "Key": "CredentialToken",            "Value": "Axis-00408c184bdb:1351593020.016190000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>301</axlog:rowid>    <axlog:token>Axis-00408c185451:1383221383.572782000</axlog:token>    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>    <axlog:UtcTime>2013-10-31T12:09:42Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>CredentialHolderName</axlog:Key>        <axlog:Value>user\_token1</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>Reason</axlog:Key>        <axlog:Value>InvalidAccessProfile</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>AccessPointToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351589192.102223000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic2</axlog:Key>        <axlog:Value>Credential</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        <axlog:Value>Denied</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>CredentialToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351593020.016190000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues></axlog:Event>
```

### Allow access within a specified time frame

The access control service supports having access profiles and credentials valid during specific time frames. For example, if the current time is outside of an access profile’s time frame, it is equivalent to the access profile being disabled.

A time frame is set by using `ValidFrom` as start time and `ValidTo` as end time. The date fields are optional, and can be left empty, in which case there are no restrictions on start or end time.

The time format is ISO 8601, which uses the format: YYYY-MM-DDThh:mm:ssTZD (for example 1997-07- 16T19:20:30+01:00).

#### Credential

The `Credential` has a general time frame which determines when this `Credential` is active. Outside of this period, the Credential is disabled.

It is also possible to specify a time period for each `CredentialAccessProfile` of an `Credential`. Using this, the administrator can set up specific time frames for when a user is allowed to use different access profiles.

For example, a user may have access to some access profiles, but one access profile should only be available for a certain period. When that time frame has passed, it is now off limits to the user. The `AccessProfile` itself still has a valid time period, it is only this particular user who has restricted access to it.

An example of a `Credential` with valid time frames:

```bash
{    "Credential": {        "token": "Axis-00408c184bdb:1351593020.016190000",        "UserToken": "user\_token1",        "Description": "Credential description",        "ValidFrom": "2011-06-30T10:11:12Z",        "ValidTo": "2027-06-30T10:11:12Z",        "Enabled": true,        "Status": "Enabled",        "IdData": \[            {                "Name": "Card",                "Value": "12345678"            },            {                "Name": "PIN",                "Value": "1234"            }        \],        "Attribute": \[\],        "AuthenticationProfile": \[\],        "CredentialAccessProfile": \[            {                "ValidFrom": "2011-06-30T10:11:12Z",                "ValidTo": "2013-06-30T10:11:12Z",                "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"            }        \]    }}
```

```bash
<Credential token="Axis-00408c184bdb:1351593020.016190000">    <CredentialAccessProfile>        <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>        <ValidFrom>2011-06-30T10:11:12Z</ValidFrom>        <ValidTo>2013-06-30T10:11:12Z</ValidTo>    </CredentialAccessProfile>    <Description>Credential description</Description>    <Enabled>true</Enabled>    <IdData Name="Card" Value="12345678" />    <IdData Name="PIN" Value="1234" />    <Status>Enabled</Status>    <UserToken>user\_token1</UserToken>    <ValidFrom>2011-06-30T10:11:12Z</ValidFrom>    <ValidTo>2013-06-30T10:11:12Z</ValidTo></Credential>
```

The access control service returns an access denied if outside the valid time frame. Depending on whether `ValidFrom` or `ValidTo` is violated, the `Reason` field is either `CredentialNotActive` or `CredentialExpired`.

Events issued are `AccessControl/Denied/Credential` and `AccessControl/Denied/Credential` as in the following examples:

```bash
{    "rowid": 342,    "token": "Axis-00408c185451:1383232840.672639000",    "UUID": "5581ad80-95b0-11e0-b883-00408c185451",    "UtcTime": "2013-10-31T15:20:39.933137Z",    "KeyValues": \[        {            "Key": "CredentialHolderName",            "Value": "user\_token1",            "Tags": \["onvif-data"\]        },        {            "Key": "Reason",            "Value": "CredentialNotActive",            "Tags": \["onvif-data"\]        },        {            "Key": "AccessPointToken",            "Value": "Axis-00408c184bdb:1351589192.102223000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]        },        {            "Key": "topic2",            "Value": "Credential",            "Tags": \[\]        },        {            "Key": "topic1",            "Value": "Denied",            "Tags": \[\]        },        {            "Key": "topic0",            "Value": "AccessControl",            "Tags": \[\]        },        {            "Key": "CredentialToken",            "Value": "Axis-00408c184bdb:1351593020.016190000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>304</axlog:rowid>    <axlog:token>Axis-00408c185451:1383221797.885109000</axlog:token>    A    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>    <axlog:UtcTime>2013-10-31T12:16:37Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>CredentialHolderName</axlog:Key>        <axlog:Value>user\_token1</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>Reason</axlog:Key>        <axlog:Value>CredentialNotActive</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>AccessPointToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351589192.102223000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic2</axlog:Key>        <axlog:Value>Credential</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        >        <axlog:Value>Denied</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>CredentialToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351593020.016190000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues></axlog:Event>
```

```bash
{    "rowid": 345,    "token": "Axis-00408c185451:1383232972.722756000",    "UUID": "5581ad80-95b0-11e0-b883-00408c185451",    "UtcTime": "2013-10-31T15:22:51.973900Z",    "KeyValues": \[        {            "Key": "CredentialHolderName",            "Value": "user\_token1",            "Tags": \["onvif-data"\]        },        {            "Key": "Reason",            "Value": "CredentialExpired",            "Tags": \["onvif-data"\]        },        {            "Key": "AccessPointToken",            "Value": "Axis-00408c184bdb:1351589192.102223000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-source"\]        },        {            "Key": "topic2",            "Value": "Credential",            "Tags": \[\]        },        {            "Key": "topic1",            "Value": "Denied",            "Tags": \[\]        },        {            "Key": "topic0",            "Value": "AccessControl",            "Tags": \[\]        },        {            "Key": "CredentialToken",            "Value": "Axis-00408c184bdb:1351593020.016190000",            "Tags": \["wstype:pt:ReferenceToken", "onvif-data"\]        }    \],    "Tags": \[\]}
```

```bash
<axlog:Event>    <axlog:rowid>307</axlog:rowid>    <axlog:token>Axis-00408c185451:1383222889.795332002</axlog:token>    <axlog:UUID>5581ad80-95b0-11e0-b883-00408c185451</axlog:UUID>    <axlog:UtcTime>2013-10-31T12:34:49Z</axlog:UtcTime>    <axlog:KeyValues>        <axlog:Key>CredentialHolderName</axlog:Key>        <axlog:Value>user\_token1</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>Reason</axlog:Key>        <axlog:Value>CredentialExpired</axlog:Value>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>AccessPointToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351589192.102223000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-source</axlog:Tags>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic2</axlog:Key>        <axlog:Value>Credential</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic1</axlog:Key>        <axlog:Value>Denied</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>topic0</axlog:Key>        <axlog:Value>AccessControl</axlog:Value>    </axlog:KeyValues>    <axlog:KeyValues>        <axlog:Key>CredentialToken</axlog:Key>        <axlog:Value>Axis-00408c184bdb:1351593020.016190000</axlog:Value>        <axlog:Tags>wstype:pt:ReferenceToken</axlog:Tags>        <axlog:Tags>onvif-data</axlog:Tags>    </axlog:KeyValues></axlog:Event>
```

#### AccessProfile

Analogously to the case with `Credential`, the `AccessProfile` may have a time frame set for when the profile is valid. Outside this time frame, any access requests involving it are denied. See the example below:

```bash
{    "AccessProfile": {        "token": "Axis-00408c184bdb:1351591416.539133000",        "Name": "AccessProfile1",        "Description": "AccessProfile description",        "ValidFrom": "2011-06-30T10:11:12Z",        "ValidTo": "2027-06-30T10:11:12Z",        "Enabled": true,        "Schedule": \["standard\_always"\],        "AuthenticationProfile": \[\],        "Attribute": \[\],        "AccessPolicy": \[            {                "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                "AuthorizationProfile": \[\],                "Attribute": \[\],                "Schedule": \["standard\_always"\]            }        \]    }}
```

```bash
<AccessProfile token="Axis-00408c184bdb:1351591416.539133000">    <AccessPolicy>        <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>        <Schedule>standard\_always</Schedule>    </AccessPolicy>    <Description>AccessProfile description</Description>    <Enabled>true</Enabled>    <Name>AccessProfile1</Name>    <Schedule>standard\_always</Schedule>    <ValidFrom>2011-06-30T10:11:12Z</ValidFrom>    <ValidTo>2027-06-30T10:11:12Z</ValidTo></AccessProfile>
```

The response of an access request and dispatched events are the same as if the `AccessProfile` was disabled, see section [Disable an access profile](#disable-an-access-profile).

### Specify time-dependent access behavior

Schedules provide a way of configuring who has access during certain time periods. The schedules themselves are added using the schedule service, but they may be referenced from the AccessControl service to describe the desired access behavior. Schedules can be applied to authentication- and access profiles.

As described in section [Schedule service](/vapix/physical-access-control/schedule-service/), the format is compliant with the iCalendar format, which allows for schedules occurring once, at recurring times or with optional start and stop dates.

It is possible to specify both when a schedule is to be active and when there is an exception to it. It is possible to specify more than one schedule for each authentication- and access profile. All schedules are then analyzed together to determine whether the profile is active or not. The exception schedules have precedence over normal schedules, so it only requires one active exception to evaluate the list as inactive. If no exception is active, at least one regular schedule must be active for the list to be evaluated as active. Both schedules are illustrated in the following sub-sections.

#### Authentication profile

The `AuthenticationProfiles` can be configured with schedules which tells when an `AuthenticationProfile` is available. An `AccessPoint` using scheduled `AuthenticationProfiles` will have changing access requirements over time.

The example below shows how to set `CardOnly` to be scheduled as valid during office hours and `CardPlusPin` as valid outside of office hours. Additionally, an exception is set saying that during public holidays `CardPlusPin` is required. The example assumes the three schedules, `office_hours, not_public_holidays` and the default `standard_always`, already exists (and is being active when the name implies). The setup of the `AuthenticationProfiles` follows:

```bash
{    "AuthenticationProfile": \[        {            "token": "CardOnly",            "Name": "CardOnly",            "Description": "Card only",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["office\_hours", "not\_public\_holidays"\]        },        {            "token": "CardPlusPin",            "Name": "CardPlusPin",            "Description": "Card + PIN",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                },                {                    "IdDataName": "PIN",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        }    \]}
```

```bash
<AuthenticationProfile token="CardOnly">  <Description>Card only</Description>  <IdFactor>    <IdDataName>Card</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <Name>CardOnly</Name>  <Schedule>office\_hours</Schedule>  <Schedule>not\_public\_holidays</Schedule></AuthenticationProfile><AuthenticationProfile token="CardPlusPin">  <Description>Card + PIN</Description>  <IdFactor>    <IdDataName>Card</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <IdFactor>    <IdDataName>PIN</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <Name>CardPlusPin</Name>  <Schedule>standard\_always</Schedule></AuthenticationProfile>
```

The setup of the `AccessPoint`, showing the list of `AuthenticationProfiles` that applies:

```bash
{    "AccessPoint": \[        {            "token": "Axis-00408c184bdb:1351589192.102223000",            "Name": "Entry 1",            "Description": "Entry 1 main door",            "AreaFrom": "",            "AreaTo": "",            "EntityType": "tdc:Door",            "Entity": "Door0",            "DoorDeviceUUID": "",            "Enabled": true,            "IdPointDevice": \[{ "IdPoint": "idpoint\_token", "DeviceUUID": "" }\],            "AuthenticationProfile": \["CardOnly", "CardPlusPin"\],            "Attribute": \[\],            "ActionArgument": \[\],            "Action": "Access"        }    \]}
```

```bash
<AccessPoint token="Axis-00408c184bdb:1351589192.102223000">    <Action>Access</Action>    <AreaFrom />    <AreaTo />    <AuthenticationProfile>CardOnly</AuthenticationProfile>    <AuthenticationProfile>CardPlusPin</AuthenticationProfile>    <Description>Entry 1 main door</Description>    <DoorDeviceUUID />    <Enabled>true</Enabled>    <Entity>Door0</Entity>    <IdPointDevice>        <DeviceUUID />        <IdPoint>idpoint\_token</IdPoint>    </IdPointDevice>    <Name>Entry 1</Name>    <Type>tdc:Door</Type>    tdc:Door</AccessPoint>
```

#### Access profile

The `AccessProfile` has two configuration options that are possible to set specific schedules to. One main schedule which determines when the `AccessProfile` is available, making it possible to administrate time limits for a group of users. The other is for each attached `AccessPoint`, which makes it possible to have separate doors accessible to the users at different times.

In the following example, the schedules from the example in the previous section are recalled. An advanced setup has been made to the `AccessProfile` saying that the group of users linked to this access profile has access all the time, except for public holidays. In addition, access is always granted through the secondary access point called "employee-door", but the main access point ("main-door") is restricted to office hours.

```bash
{    "AccessProfile": \[        {            "token": "Axis-00408c184bdb:1351591416.539133000",            "Name": "AccessProfile1",            "Description": "AccessProfile description",            "ValidFrom": "",            "ValidTo": "",            "Enabled": true,            "Schedule": \["standard\_always", "not\_public\_holidays"\],            "AuthenticationProfile": \[\],            "Attribute": \[\],            "AccessPolicy": \[                {                    "AccessPoint": "main-door",                    "AuthorizationProfile": \[\],                    "Attribute": \[\],                    "Schedule": \["office\_hours"\]                },                {                    "AccessPoint": "employee-door",                    "AuthorizationProfile": \[\],                    "Attribute": \[\],                    "Schedule": \["standard\_always"\]                }            \]        }    \]}
```

```bash
<AccessProfile token="Axis-00408c184bdb:1351591416.539133000">    <AccessPolicy>        <AccessPoint>main-door</AccessPoint>        <AuthorizationProfile />        <Schedule>office\_hours</Schedule>    </AccessPolicy>    <AccessPolicy>        <AccessPoint>employee-door</AccessPoint>        <AuthorizationProfile />        <Schedule>standard\_always</Schedule>    </AccessPolicy>    <AuthenticationProfile />    <Description>AccessProfile description</Description>    <Enabled>true</Enabled>    <Name>AccessProfile1</Name>    <Schedule>standard\_always</Schedule>    <Schedule>not\_public\_holidays</Schedule>    <ValidFrom />    <ValidTo /></AccessProfile>
```

### Override the authentication of an access point

It is possible to set up a system with different levels of authentication profiles, providing an advanced way of overriding the common rules for accessing a door. Say the access point, uses one type of authentication, then it is possible to override this by setting other types of authentication at the access profile or the credential.

It is also possible to exclude having an `AuthenticationProfile` specified at the `AccessPoint`, and only use `AuthenticationProfiles` in the `AccessProfiles` or `Credential`. This may be useful if the intention is to have different users, or groups of users, access the same access point in different ways without a common way of doing so.

When overriding authentication profiles with lower priority, it is possible to add more levels of schedules into the system. By specifying `AuthenticationProfiles` that are active during different schedules, one can create advanced schemata where a certain user or group of users may enter using other credentials.

The precedence order for `AuthenticationProfiles` overrides are from high to low: `Credentials`, `AccessProfiles` and `AccessPoints`. This is further shown in the flowchart below.

![Authentication profiles precedence order](/assets/images/access-control-service.t10069726-77fd865b0b99fc82bd5a4cc2d2ac577a.png)

In this example, an `AccessPoint` is set up where card and pin is required and a specific group of users should be able to access it with only their cards during office hours. This is achieved by setting `CardOnly-office-hours` in the `AccessProfile`, thus overriding `CardPlusPin` in the `AccessPoint`. Outside this schedule, the default requirements of the `AccessPoint` applies.

```bash
{    "AuthenticationProfile": \[        {            "token": "CardOnly-office-hours",            "Name": "CardOnlyOfficeHours",            "Description": "Card only during office hours",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["office\_hours", "not\_public\_holidays"\]        },        {            "token": "CardOnly-always",            "Name": "CardOnlyAlways",            "Description": "Card only always",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        },        {            "token": "CardPlusPin",            "Name": "CardPlusPin",            "Description": "Card + PIN",            "IdFactor": \[                {                    "IdDataName": "Card",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                },                {                    "IdDataName": "PIN",                    "IdMatchOperatorName": "IdDataEqual",                    "OperatorValue": ""                }            \],            "Schedule": \["standard\_always"\]        }    \]}
```

```bash
<AuthenticationProfile token="CardOnly-office-hours">  <Description>Card only during office hours</Description>  <IdFactor>    <IdDataName>Card</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <Name>CardOnlyOfficeHours</Name>  <Schedule>office\_hours</Schedule>  <Schedule>not\_public\_holidays</Schedule></AuthenticationProfile><AuthenticationProfile token="CardOnly-always">  <Description>Card only always</Description>  <IdFactor>    <IdDataName>Card</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <Name>CardOnlyAlways</Name>  <Schedule>standard\_always</Schedule></AuthenticationProfile><AuthenticationProfile token="CardPlusPin">  <Description>Card + PIN</Description>  <IdFactor>    <IdDataName>Card</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <IdFactor>    <IdDataName>PIN</IdDataName>    <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>    <OperatorValue></OperatorValue>  </IdFactor>  <Name>CardPlusPin</Name>  <Schedule>standard\_always</Schedule></AuthenticationProfile>
```

The `AccessPoint` using `CardPlusPin`:

```bash
{    "AccessPoint": \[        {            "token": "Axis-00408c184bdb:1351589192.102223000",            "Name": "Entry 1",            "Description": "Entry 1 main door",            "AreaFrom": "",            "AreaTo": "",            "EntityType": "tdc:Door",            "Entity": "Door0",            "DoorDeviceUUID": "",            "Enabled": true,            "IdPointDevice": \[{ "IdPoint": "idpoint\_token", "DeviceUUID": "" }\],            "AuthenticationProfile": \["CardPlusPin"\],            "Attribute": \[\],            "ActionArgument": \[\],            "Action": "Access"        }    \]}
```

```bash
<AccessPoint token="Axis-00408c184bdb:1351589192.102223000">    <Action>Access</Action>    <AreaFrom />    <AreaTo />    <AuthenticationProfile>CardPlusPin</AuthenticationProfile>    <Description>Entry 1 main door</Description>    <DoorDeviceUUID />    <Enabled>true</Enabled>    <Entity>Door0</Entity>    <IdPointDevice>        <DeviceUUID />        <IdPoint>idpoint\_token</IdPoint>    </IdPointDevice>    <Name>Entry 1</Name>    <Type>tdc:Door</Type></AccessPoint>
```

The `AccessProfile` with overriding `CardOnly-office-hours` (`CardOnly` during `office_hours`):

```bash
{    "AccessProfile": \[        {            "token": "Axis-00408c184bdb:1351591416.539133000",            "Name": "AccessProfile1",            "Description": "AccessProfile description",            "ValidFrom": "",            "ValidTo": "",            "Enabled": true,            "Schedule": \["standard\_always"\],            "AuthenticationProfile": \["CardOnly-office-hours"\],            "Attribute": \[\],            "AccessPolicy": \[                {                    "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                    "AuthorizationProfile": \[\],                    "Attribute": \[\],                    "Schedule": \["standard\_always"\]                }            \]        }    \]}
```

```bash
<AccessProfile token="Axis-00408c184bdb:1351591416.539133000">    <AccessPolicy>        <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>        <AuthorizationProfile />        <Schedule>standard\_always</Schedule>    </AccessPolicy></AccessProfile>
```

Finally, a kind of superuser, who only needs a card at all times, shall be added. This is done by adding `CardOnly-always` to the `Credential`, thus overriding both `AccessProfile` and `AccessPoint`:

```bash
{    "Credential": \[        {            "token": "Axis-00408c184bdb:1351593020.016190000",            "UserToken": "user\_token1",            "Description": "Credential description",            "ValidFrom": "",            "ValidTo": "",            "Enabled": true,            "Status": "Enabled",            "IdData": \[                { "Name": "Card", "Value": "12345678" },                { "Name": "PIN", "Value": "1234" }            \],            "Attribute": \[\],            "AuthenticationProfile": \["CardOnly-always"\],            "CredentialAccessProfile": \[                {                    "ValidFrom": "",                    "ValidTo": "",                    "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"                }            \]        }    \]}
```

```bash
<Credential token="Axis-00408c184bdb:1351593020.016190000">    <AuthenticationProfile>CardOnly-always</AuthenticationProfile>    <CredentialAccessProfile>        <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>    </CredentialAccessProfile>    <Description>Credential description</Description>    <Enabled>true</Enabled>    <IdData Name="Card" Value="12345678" />    <IdData Name="PIN" Value="1234" />    <Status>Enabled</Status>    <UserToken>user\_token1</UserToken></Credential>
```

The diagram shows `AuthenticationProfile` added to the diagram in chapter [Overview of the initial system](#overview-of-the-initial-system), where unaffected parts are dimmed in gray.

![Initial system with added authentication profiles](/assets/images/access-control-service.t10069727-d422983bbb8174d9ee0d019e3f4d9e8b.png)

### Enable duress access

Credentials can have an extra PIN code to be used for access under duress. If a credential holder uses his normal card together with the duress PIN code, the door is unlocked and a duress event is sent.

To unlock the door and send a duress event, the `AccessPoint` must be configured to allow duress access, the duress PIN code must be defined in the `Credential` and the `Credential` must be part of an `AccessProfile` that is configured to allow duress access.

A typical duress configuration setup is shown in the figure below. The `Credential` is part of two groups: one normal group and one group with duress access. The two `AccessProfile` items are two connected to an `AccessPoint` that supports duress access. The `AccessPoint` has two connected `AuthenticationProfile` items one for `CardPlusPIN` and one for `CardPlusDuressPIN`. This setup grants normal access if the normal PIN code is used and grants duress access and sends a duress event if the duress PIN code is used.

![Duress access configuration](/assets/images/access-control-service.t10069857-9ccfba4229991ff8985eb429f28696b0.png)

The `AuthenticationProfile` used for duress access should have `IdMatchOperatorName` set to `IdDataEqualToField` and `OperatorValue` set to `DuressPIN` as illustrated in the example below. This makes the system match an incoming PIN code with the value in the `Credential` `DuressPIN` field.

```bash
{    "pacsaxis:SetAuthenticationProfile": {        "AuthenticationProfile": \[            {                "token": "CardPlusPin",                "Name": "CardPlusPin",                "Description": "Card + PIN",                "IdFactor": \[                    {                        "IdDataName": "Card",                        "IdMatchOperatorName": "IdDataEqual",                        "OperatorValue": ""                    },                    {                        "IdDataName": "PIN",                        "IdMatchOperatorName": "IdDataEqual",                        "OperatorValue": ""                    }                \],                "Schedule": \["office\_hours"\]            },            {                "token": "CardPlusDuressPIN",                "Name": "CardPlusDuressPIN",                "Description": "Card + DuressPIN",                "IdFactor": \[                    {                        "IdDataName": "Card",                        "IdMatchOperatorName": "IdDataEqual",                        "OperatorValue": ""                    },                    {                        "IdDataName": "PIN",                        "IdMatchOperatorName": "IdDataEqualToField",                        "OperatorValue": "DuressPIN"                    }                \],                "Schedule": \["office\_hours"\]            }        \]    }}
```

```bash
<pacsaxis:SetAuthenticationProfile>    <AuthenticationProfile token="CardPlusPin">        <Description>Card + PIN</Description>        <IdFactor>            <IdDataName>Card</IdDataName>            <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>            <OperatorValue />        </IdFactor>        <IdFactor>            <IdDataName>PIN</IdDataName>            <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>            <OperatorValue />        </IdFactor>        <Name>CardPlusPin</Name>        <Schedule>standard\_always</Schedule>    </AuthenticationProfile>    <AuthenticationProfile token="CardPlusDuressPIN">        <Description>Card + DuressPIN</Description>        <IdFactor>            <IdDataName>Card</IdDataName>            <IdMatchOperatorName>IdDataEqual</IdMatchOperatorName>            <OperatorValue />        </IdFactor>        <IdFactor>            <IdDataName>PIN</IdDataName>            <IdMatchOperatorName>IdDataEqualToField</IdMatchOperatorName>            <OperatorValue>DuressPIN</OperatorValue>        </IdFactor>        <Name>CardPlusDuressPIN</Name>        <Schedule>standard\_always</Schedule>    </AuthenticationProfile></pacsaxis:SetAuthenticationProfile>
```

To allow duress access at an `AccessPoint`, add an attribute with `Name` set to `Duress` and leave `Value` empty.

```bash
{    "pacsaxis:SetAccessPoint": {        "AccessPoint": \[            {                "token": "Axis-00408c184bdb:1351589192.102223000",                "Name": "Entry 1",                "Description": "",                "AreaFrom": "",                "AreaTo": "",                "Entity": "Door0",                "DoorDeviceUUID": "",                "Enabled": true,                "IdPointDevice": \[                    {                        "IdPoint": "idpoint\_token",                        "DeviceUUID": ""                    }                \],                "AuthenticationProfile": \["CardPlusPin", "CardPlusDuressPIN"\],                "Attribute": \[                    {                        "type": "",                        "Name": "Duress",                        "Value": ""                    }                \],                "ActionArgument": \[\],                "Action": "Access"            }        \]    }}
```

```bash
<pacsaxis:SetAccessPoint>    <AccessPoint token="Axis-00408c184bdb:1351589192.102223000">        <Action>Access</Action>        <AreaFrom />        <AreaTo />        <AuthenticationProfile>CardPlusPin</AuthenticationProfile>        <AuthenticationProfile>CardPlusDuressPIN</AuthenticationProfile>        <Description />        <DoorDeviceUUID />        <Enabled>true</Enabled>        <Entity>Door0</Entity>        <IdPointDevice>            <DeviceUUID />            <IdPoint>idpoint\_token</IdPoint>        </IdPointDevice>        <Name>Entry 1</Name>        <Type>axtdc:Door</Type>        <Attribute type="" Name="Duress" Value="" />    </AccessPoint></pacsaxis:SetAccessPoint>
```

To limit duress access at an `AccessPoint` to selected members of an `AccessProfile`, create an additional `AccessProfile`. Connect the new `AccessProfile` to the same `AccessPoint` and enable duress access by adding the attribute `Duress`. See example below. A member in the first `AccessProfile` (with name `NormalGroup`) gets normal access and if the member is also included in the second `AccessProfile` (with name `DuressGroup`), the member gets duress access as well.

```bash
{    "pacsaxis:SetAccessProfile": {        "AccessProfile": \[            {                "token": "Axis-00408c184bdb:1351591416.539133000",                "Name": "NormalGroup",                "Description": "Members can get normal access",                "ValidFrom": "",                "ValidTo": "",                "Enabled": true,                "Schedule": \["office\_hours"\],                "AuthenticationProfile": \[\],                "Attribute": \[\],                "AccessPolicy": \[                    {                        "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                        "AuthorizationProfile": \[\],                        "Attribute": \[\],                        "Schedule": \["office\_hours"\]                    }                \]            },            {                "token": "Axis-00408c184bdb:1351591417.539133000",                "Name": "DuressGroup",                "Description": "Members can trigger duress access",                "ValidFrom": "",                "ValidTo": "",                "Enabled": true,                "Schedule": \["office\_hours"\],                "AuthenticationProfile": \[\],                "Attribute": \[                    {                        "type": "",                        "Name": "Duress",                        "Value": ""                    }                \],                "AccessPolicy": \[                    {                        "AccessPoint": "Axis-00408c184bdb:1351589192.102223000",                        "AuthorizationProfile": \[\],                        "Attribute": \[\],                        "Schedule": \["office\_hours"\]                    }                \]            }        \]    }}
```

```bash
<pacsaxis:SetAccessProfile>    <AccessProfile token="Axis-00408c184bdb:1351591416.539133000">        <AccessPolicy>            <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>            <Schedule>office\_hours</Schedule>        </AccessPolicy>        <Description>Members can get normal access</Description>        <Enabled>true</Enabled>        <Name>NormalGroup</Name>        <Schedule>office\_hours</Schedule>    </AccessProfile>    <AccessProfile token="Axis-00408c184bdb:1351591417.539133000">        <AccessPolicy>            <AccessPoint>Axis-00408c184bdb:1351589192.102223000</AccessPoint>            <Schedule>office\_hours</Schedule>        </AccessPolicy>        <Description>Members can trigger duress access</Description>        <Enabled>true</Enabled>        <Name>DuressGroup</Name>        <Schedule>office\_hours</Schedule>        <Attribute Name="Duress" Value="" type="" />    </AccessProfile></pacsaxis:SetAccessProfile>
```

To set a duress PIN code in a `Credential`, add an extra `IdData` with Name equal to `DuressPIN` and `Value` set to PIN code that is different from the normal PIN code.

```bash
{    "pacsaxis:SetCredential": {        "Credential": \[            {                "token": "Axis-00408c184bdb:1351593020.016190000",                "UserToken": "user\_token1",                "Description": "Credential description",                "ValidFrom": "",                "ValidTo": "",                "Enabled": false,                "Status": "Disabled",                "IdData": \[                    {                        "Name": "Card",                        "Value": "12345678"                    },                    {                        "Name": "PIN",                        "Value": "1234"                    },                    {                        "Name": "DuressPIN",                        "Value": "1235"                    }                \],                "Attribute": \[\],                "AuthenticationProfile": \[\],                "CredentialAccessProfile": \[                    {                        "ValidFrom": "",                        "ValidTo": "",                        "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"                    },                    {                        "ValidFrom": "",                        "ValidTo": "",                        "AccessProfile": "Axis-00408c184bdb:1351591417.539133000"                    }                \]            }        \]    }}
```

```bash
<pacsaxis:SetCredential>    <Credential token="Axis-00408c184bdb:1351593020.016190000">        <CredentialAccessProfile>            <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>            <AccessProfile>Axis-00408c184bdb:1351591417.539133000</AccessProfile>        </CredentialAccessProfile>        <Description>Credential description</Description>        <Enabled>true</Enabled>        <IdData Name="Card" Value="12345678" />        <IdData Name="PIN" Value="1234" />        <IdData Name="DuressPIN" Value="1235" />        <Status>Enabled</Status>        <UserToken>user\_token1</UserToken>    </Credential></pacsaxis:SetCredential>
```

### Extend access time for a credential

The time the door is unlocked after access has been granted is defined by `AccessTime` in the `Door` data structure, see [Door data structure](/vapix/physical-access-control/door-control-service/#door-data-structure-guide). The `Door` can also have an extended access time which is defined by `ExtendedAccessTime` in `Door`.

A `Credential` can be configured to use the extended access time from the `Door` instead of the normal access time. To achieve this, set the `Attribute` field in the `Credential` to `ExtendedAccessTime` without any value as shown in the following example:

```bash
{    "pacsaxis:SetCredential": {        "Credential": \[            {                "token": "Axis-00408c184bdb:1351593020.016190000",                "UserToken": "user\_token1",                "Description": "Credential description",                "ValidFrom": "1997-01-01T00:00:00Z",                "ValidTo": "2038-01-01T00:00:00Z",                "Enabled": true,                "Status": "Enabled",                "IdData": \[                    {                        "Name": "Card",                        "Value": "12345678"                    },                    {                        "Name": "PIN",                        "Value": "1234"                    }                \],                "Attribute": \[                    {                        "Name": "ExtendedAccessTime"                    }                \],                "AuthenticationProfile": \[\],                "CredentialAccessProfile": \[                    {                        "ValidFrom": "1997-01-01T00:00:00Z",                        "ValidTo": "2038-01-01T00:00:00Z",                        "AccessProfile": "Axis-00408c184bdb:1351591416.539133000"                    }                \]            }        \]    }}
```

```bash
<pacsaxis:SetCredential>    <Credential token="Axis-00408c184bdb:1351593020.016190000">        <Attribute Name="ExtendedAccessTime" />        <CredentialAccessProfile>            <AccessProfile>Axis-00408c184bdb:1351591416.539133000</AccessProfile>            <ValidFrom>1997-01-01T00:00:00Z</ValidFrom>            <ValidTo>2038-01-01T00:00:00Z</ValidTo>        </CredentialAccessProfile>        <Description>Credential description</Description>        <Enabled>true</Enabled>        <IdData Name="Card" Value="12345678" />        <IdData Name="PIN" Value="1234" />        <Status>Enabled</Status>        <UserToken>user\_token1</UserToken>        <ValidFrom>1997-01-01T00:00:00Z</ValidFrom>        <ValidTo>2038-01-01T00:00:00Z</ValidTo>    </Credential></pacsaxis:SetCredential>
```

When the door is accessed using this credential, the door remains unlocked for the number of seconds specified by `ExtendedAccessTime` in `Door`. The `Attribute` field in the `Credential` can also be used to specify door timeouts that are specific to this `Credential`. The following timeouts can be used: `AccessTime`, `OpenTooLongTime`, `PreAlarmTime`. These timeouts are similar to the door timeouts described in section [Door data structure](/vapix/physical-access-control/door-control-service/#door-data-structure-guide). Each timeout must have a `Value` in the form `PTXS` where X is the number of seconds.

### Enable anti-passback

Anti-passback monitors violations to rules preventing the same card being used for access to the same area multiple times, if other conditions are not first fulfilled. A violation can be defined in two ways, depending on the anti-passback mode:

-   Logical: A violation occurs when the user enters the area (opens the door) and then requests to enter it again (e.g. the card is passed back through the door to another user).
-   TimedLogical: A violation occurs when the user enters the area and then requests to enter again within a configurable time span. After the configured time has passed, requests to re-enter will not cause violations.

Anti-passback is configured using access point attributes, and concerns the `AreaTo` of an access point. When the user requests access to `AreaTo` of an access point with anti-passback enabled, the request may be denied if it constitutes an anti-passback violation, or granted if enforcement is disabled, which can be done for a credential by setting its `AntiPassbackOverride` attribute to `True`.

**Note:** Door monitor input is needed to get anti-passback to work.

**Example 1:** Enable hard-timed logical anti-passback feature for an access point, with a timeout of 5 min. Anti-passback is configured by adding attributes to an AccessPoint.

```bash
{    "pacsaxis:SetAccessPoint": {        "AccessPoint": \[            {                "token": "Main entrance in",                "Name": "Main entrance in",                "Description": "",                "AreaFrom": "main building out",                "AreaTo": "main building in",                "EntityType": "tdc:Door",                "Entity": "main entrance door",                "Enabled": true,                "DoorDeviceUUID": "5581ad80-95b0-11e0-b883-00408cffe4b3",                "IdPointDevice": \[                    {                        "IdPoint": "main entrance idpoint",                        "DeviceUUID": ""                    }                \],                "AuthenticationProfile": \[\],                "Attribute": \[                    {                        "type": "",                        "Name": "Direction",                        "Value": "in"                    },                    {                        "type": "",                        "Name": "AntiPassbackMode",                        "Value": "TimedLogical"                    },                    {                        "type": "",                        "Name": "AntiPassbackTimeout",                        "Value": "300"                    },                    {                        "type": "",                        "Name": "AntiPassbackEnforcementMode",                        "Value": "Hard"                    }                \],                "ActionArgument": \[\],                "Action": "Access"            }        \]    }}
```

```bash
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:pacs="http://www.axis.com/vapix/ws/pacs">    <soap:Header />    <soap:Body>        <pacs:SetAccessPoint>            <!--1 or more repetitions:-->            <pacs:AccessPoint token="Main entrance in">                <pacs:Name>Main entrance in</pacs:Name>                <!--Optional:-->                <pacs:Description />                <!--Optional:-->                <pacs:AreaFrom>main building out</pacs:AreaFrom>                <!--Optional:-->                <pacs:AreaTo>main building in</pacs:AreaTo>                <!--Optional:-->                <pacs:EntityType>tdc:Door</pacs:EntityType>                <pacs:EntityType>tdc:Door</pacs:EntityType>                <pacs:Enabled>true</pacs:Enabled>                <!--Optional:-->                <pacs:DoorDeviceUUID>5581ad80-95b0-11e0-b883-00408cffe4b3</pacs:DoorDeviceUUID>                <!--Zero or more repetitions:-->                <pacs:IdPointDevice>                    <pacs:IdPoint>main entrance idpoint</pacs:IdPoint>                    <!--Optional:-->                    <pacs:DeviceUUID />                </pacs:IdPointDevice>                <!--Zero or more repetitions:-->                <pacs:AuthenticationProfile />                <!--Zero or more repetitions:-->                <pacs:Attribute type="" Name="Direction" Value="in" />                <pacs:Attribute type="" Name="AntiPassbackMode" Value="TimedLogical" />                <pacs:Attribute type="" Name="AntiPassbackTimeout" Value="300" />                <pacs:Attribute type="" Name="AntiPassbackEnforcementMode" Value="Hard" />                <!--Zero or more repetitions:-->                <pacs:ActionArgument type="?">                    <pacs:Name />                    <pacs:Value />                </pacs:ActionArgument>                <pacs:Action />            </pacs:AccessPoint>        </pacs:SetAccessPoint>    </soap:Body></soap:Envelope>
```

**Example 2:** Configure anti-passback override for a credential.

```bash
{    "pacsaxis:SetCredential": {        "Credential": \[            {                "token": "credential token",                "UserToken": "user\_token",                "Description": "credential description",                "ValidFrom": "1997-01-01T00:00:00Z",                "ValidTo": "2038-01-01T00:00:00Z",                "Enabled": true,                "Status": "Enabled",                "IdData": \[                    {                        "Name": "Card",                        "Value": "12345678"                    },                    {                        "Name": "PIN",                        "Value": "1234"                    }                \],                "Attribute": \[                    {                        "type": "",                        "Name": "AntiPassbackOverride",                        "Value": "True"                    }                \],                "AuthenticationProfile": \[\],                "CredentialAccessProfile": \[                    {                        "ValidFrom": "1997-01-01T00:00:00Z",                        "ValidTo": "2038-01-01T00:00:00Z",                        "AccessProfile": "AccessProfile token"                    }                \]            }        \]    }}
```

```bash
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:pacs="http://www.axis.com/vapix/ws/pacs">    <soap:Body>        <pacs:SetCredential>            <!--1 or more repetitions:-->            <pacs:Credential token="credential token">                <!--Optional:-->                <pacs:UserToken />                <!--Optional:-->                <pacs:Description>credential description</pacs:Description>                <!--Optional:-->                <pacs:ValidFrom>1997-01-01T00:00:00Z</pacs:ValidFrom>                <!--Optional:-->                <pacs:ValidTo>2038-01-01T00:00:00Z</pacs:ValidTo>                <pacs:Enabled>true</pacs:Enabled>                <pacs:Status>Enabled</pacs:Status>                <!--Zero or more repetitions:-->                <pacs:IdData Name="Card" Value="12345678" />                <pacs:IdData Name="PIN" Value="1234" />                <!--Zero or more repetitions:-->                <pacs:Attribute type="" Name="AntiPassbackOverride" Value="True" />                <!--Zero or more repetitions:-->                <pacs:AuthenticationProfile />                <!--Zero or more repetitions:-->                <pacs:CredentialAccessProfile>                    <!--Optional:-->                    <pacs:ValidFrom>1997-01-01T00:00:00Z</pacs:ValidFrom>                    <!--Optional:-->                    <pacs:ValidTo>2038-01-01T00:00:00Z</pacs:ValidTo>                    <pacs:AccessProfile>AccessProfile token</pacs:AccessProfile>                </pacs:CredentialAccessProfile>            </pacs:Credential>        </pacs:SetCredential>    </soap:Body></soap:Envelope>
```

**Example 3:** Set anti-passback data for the controller.

```bash
{    "pacsaxis:SetAntipassbackData": {        "AntipassbackData": \[            {                "CredentialToken": "credential token",                "CurrentArea": "main building in",                "ByTime": false,                "PassOkThreshold": 0,                "Violation": ""            }        \]    }}
```

```bash
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:pacs="http://www.axis.com/vapix/ws/pacs">    <soap:Header />    <soap:Body>        <pacs:SetAntipassbackData>            <!--1 or more repetitions:-->            <pacs:AntipassbackData>                <pacs:CredentialToken>credential token</pacs:CredentialToken>                <pacs:PassOkThreshold>0</pacs:PassOkThreshold>                <pacs:CurrentArea>main building in></pacs:CurrentArea>                <pacs:ByTime>False></pacs:ByTime>                <pacs:Violation />            </pacs:AntipassbackData>        </pacs:SetAntipassbackData>    </soap:Body></soap:Envelope>
```

#### Configure anti-passback

Anti-passback is configured by adding attributes to an AccessPoint. The following configuration attributes are available:

| Name | Type | Value | Default |
| --- | --- | --- | --- |
| `AntiPassbackMode` | String | Logical or TimedLogical | N/A |
| `AntiPassbackTimeout` | int | 0..tdb | 0 |
| `AntiPassbackEnforcementMode` | String | "Soft" or "Hard" | Hard |

Note: `AntiPassbackMode` is mandatory to enable the feature. The other two attributes will use default values if not entered.

`AntiPassbackMode`:

-   Logical - Two card readers attached to the door. The user cannot access the area twice without exiting in between. The timer is not used.
-   TimedLogical - Same as Logical, but the user can access the area again when the AntiPassbackTimeout timer has expired.

`AntiPassbackEnforcementMode`:

-   Soft - Anti-passback is not enforced, but violations still produce anti-passback events.
-   Hard - Anti-passback is enforced and violations produce anti-passback events.

`AntiPassbackTimeout`:

-   Number of seconds the user will be locked out when anti-passback occurs.

Note 1: `AntiPassbackTimeout` is only used in TimedLogical mode. Timer is not restarted on consecutive card swipes.

Note 2: Even if all configuration attributes are entered in the AccessPoint, Areas (SetArea) will also need to be created, and specified in the AccessPoint (AreaTo and AreaFrom).

#### Configure anti-passback override

Anti-passback may be overridden for a credential by adding a credential attribute. When set to `True`, anti-passback is disabled entirely for that credential.

| Name | Type | Value | Default |
| --- | --- | --- | --- |
| `AntiPassbackOverride` | bool | True or False | False |

#### List and set anti-passback

The anti-passback feature is enforced based on the anti-passback monitoring data stored locally in the access controller. Anti-passback monitoring data is updated once the anti-passback feature is enabled, with a list of credentials and related information. The following data types for anti-passback monitoring data are valid:

-   **pt:ReferenceToken CredentialToken**  
    Credential token number
-   **xs:long PassOkThreshold**  
    Anti-passback timer value (in microseconds)
-   **xs:string CurrentArea**  
    The current area token
-   **xs:boolean ByTime**  
    Used to indicate AntiPassbackMode. `False` denotes Logical, `True`denotes TimedLogical.

Anti-passback monitoring data of the access controller can be configured by the client, directly through the function `SetAntipassbackData`. The client can list the anti-passback database of the controller through `GetAntipassbackDataList`. A typical use case for this feature is to synchronize anti-passback database in multiple controllers in the same area, to achieve area-based anti-passback. The recommended way to configure the anti-passback monitoring data is to first employ`GetAntipassbackDataList` and then send this same data to the controller directly. In most cases, there is no need to modify the data from `GetAntipassbackDataList` before using it for `SetAntipassbackData`.

#### Reset anti-passback

The clearing of anti-passback data for specific or all credentials stored in the controller is supported. If the credential is currently not in anti-passback violation, then nothing happens. For further details, refer to the Access Control Service API [Enable anti-passback](#enable-anti-passback).

-   **Clear anti-passback data for all credentials**  
    Function: `ResetAllAntipassbackViolations`
-   **Clear anti-passback monitoring data for a specific credential**  
    Function: `ResetAntipassbackViolation`

#### Anti-passback notifications

When access is denied because of anti-passback, the existing event `AccessControl/Denied/Credential` is sent with `AntiPassbackViolation` as the reason.  
A new event is also sent, `Credential/State/ApbViolation`, as shown below:

```bash
\[CredentialToken = 'Axis-accc8e25445a:1480425881.133982000'\] {onvif-source} {wstype:pt:ReferenceToken}\[tns1:topic2 = 'ApbViolation'\] {evvnn:Anti Passback Violation}\[tns1:topic1 = 'State'\] {evvnn:State}\[tns1:topic0 = 'Credential'\]\[CredentialHolderName = 'Axis-accc8e25445a:1480425880.628047000'\] {onvif-source} {wstype:pt:ReferenceToken}\[Device Source = '5581ad80-95b0-11e0-b883-accc8e25445a'\] {onvif-source}\[Reason = 'AntiPassbackViolation'\] {onvif-data}\[ApbViolation = '1'\] {onvif-data}\[ClientUpdated = '0'\] {onvif-data}
```

The event `Credential/State/ApbViolation`, can also be sent in the following scenarios:

-   If the anti-passback violation is reset by an API call, i.e. `ResetAntipassbackViolation` (`ApbViolation 0, ClientUpdated 1`).

```bash
\[CredentialToken = 'Axis-accc8e25445a:1480425881.133982000'\] {onvif-source} {wstype:pt:ReferenceToken}\[tns1:topic2 = 'ApbViolation'\] {evvnn:Anti Passback Violation}\[tns1:topic1 = 'State'\] {evvnn:State}\[tns1:topic0 = 'Credential'\]\[CredentialHolderName = 'Axis-accc8e25445a:1480425880.628047000'\] {onvif-source} {wstype:pt:ReferenceToken}\[Device Source = '5581ad80-95b0-11e0-b883-accc8e25445a'\] {onvif-source}\[Reason = 'AntiPassbackViolation'\] {onvif-data}\[ApbViolation = '0'\] {onvif-data}\[ClientUpdated = '1'\] {onvif-data}
```

-   If the internal anti-passback cleanup timer (currently running every 10 minutes) finds any credentials where the violation should be removed (`ApbViolation 0, ClientUpdated 0`). This is only applicable if TimedLogical is used as the anti-passback mode.

```bash
\[CredentialToken = 'Axis-accc8e25445a:1480425881.133982000'\] {onvif-source} {wstype:pt:ReferenceToken}\[tns1:topic2 = 'ApbViolation'\] {evvnn:Anti Passback Violation}\[tns1:topic1 = 'State'\] {evvnn:State}\[tns1:topic0 = 'Credential'\]\[CredentialHolderName = 'Axis-accc8e25445a:1480425880.628047000'\] {onvif-source} {wstype:pt:ReferenceToken}\[Device Source = '5581ad80-95b0-11e0-b883-accc8e25445a'\] {onvif-source}\[Reason = 'AntiPassbackViolation'\] {onvif-data}\[ApbViolation = '0'\] {onvif-data}\[ClientUpdated = '0'\] {onvif-data}
```

-   If the credential in violation is removed by the API call `RemoveCredential`(`ApbViolation 0, ClientUpdated 1`).

```bash
\[CredentialToken = 'Axis-accc8e25445a:1480425881.133982000'\] {onvif-source} {wstype:pt:ReferenceToken}\[tns1:topic2 = 'ApbViolation'\] {evvnn:Anti Passback Violation}\[tns1:topic1 = 'State'\] {evvnn:State}\[tns1:topic0 = 'Credential'\]\[CredentialHolderName = 'Axis-accc8e25445a:1480425880.628047000'\] {onvif-source} {wstype:pt:ReferenceToken}\[Device Source = '5581ad80-95b0-11e0-b883-accc8e25445a'\] {onvif-source}\[Reason = 'AntiPassbackViolation'\] {onvif-data}\[ApbViolation = '0'\] {onvif-data}\[ClientUpdated = '1'\] {onvif-data}
```

Note that due to load considerations, the `Credential/State/ApbViolation` event is not sent in the following scenarios:

-   `ResetAllAntipassbackViolations`
-   `SetAntipassbackData`

## Access control service API

The AccessControl service implements the Authentication and Authorization functionality and controls the actions to get access to various Access Points controlling access to Doors and Areas.

The AccessControl service can have multiple AccessController instances (configurations).

The basic data structures used by the service are:

-   CredentialInfo holding basic information of a credential.
-   AccessPointInfo holding basic information on how access is controlled in one direction for a door (from which area to which area) defined in the DoorControl service.
-   AccessController holding information on which AccessPoints are handled by which controller.
-   AccessProfileInfo and AccessProfile holding authorization information.
-   AuthenticationProfileInfo and AuthenticationProfile holding authentication requirements.

Standardised attributes:

ExtendedTime - Use extended timer for Door Control Access.

Extensions and new features can be controlled with the existing API:s and datastructures by using new Attributes or adding new MatchOperators.

Attributes can exist in the Credential indicating that a Credential (or holder) needs or provides certain checks.

Other Attributes that perhaps should be standardized (but not mandatory): EscortRequired - if the holder of the Credential requires escort.

EscortNotRequired - if the holder of the Credential does not require escort.

Escort - the holder of the credential is an escort.

VideoVerifiation and similar extra authentication or authorization checks - can be implemented using a specific IdMatchOperator used by an IdFactor in an AuthenticationProfile, where the OperatorValue points to a remote AccessController where the check is done.

### Design considerations
#### Instance-level capabilities

A single PACS device may have diverse components of the same type. For example, a controller may operate two doors: one at the entrance to the building which has secure locking, monitoring and alarm abilities, and the other one is internal which can be only locked and unlocked.

Therefore, capabilities can be divided into 2 groups:

-   Overall service capabilities;
-   Capabilities for a particular entity in the service. It can also work in conjunction with GetEventProperties function to provide finer control over system.

Please refer to section \[Service capabilities\] for more information.

#### Retrieving status

The PACS family of ONVIF services defines 2 parallel mechanisms for retrieving status information for most entities:

-   Get<Entity>State functions return a cumulative snapshot of the current state, operating mode and other run-time information.
-   The Event Service returns up-to-date and consistent states of entities. Each entity provides a set of events (usually one per each field in the State type) to notify a client about status changes. As far as these events are property events, a client receives the current state whenever a new subscription is initialized.

#### Retrieving system configuration

The PACS family of ONVIF services defines several Get-functions that can return data incrementally. These functions allow the processing of a large number of entities even though resources are highly constrained.

To return data incrementally, these functions make use of a parameter called StartReference. StartReference is a device internal identifier used to continue fetching data from the last position, and allows a client to iterate over a large dataset in smaller chunks. The device handles a reasonable number of different StartReferences at the same time and they live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client always passes the value returned from a previous request to continue fetching data. Client do not use the same reference more than once.

For example, the StartReference can be incrementing start position number or underlying database transaction identifier.

The returned NextStartReference is used as the StartReference parameter in successive calls, and may be changed by device in each call.

The following pseudo-code demonstrates how information about all Access Points can be obtained from a device:

```bash
StartRef = nulldo {  Response = GetAccessPointInfoList(StartReference = StartRef)  if (Response.AccessPointInfo != null) {    AllAccessPoints.Append(Response.AccessPointInfo)  }  StartRef = Response.NextStartReference} while (StartRef != null)
```

### Service capabilities

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl%20)

#### ServiceCapabilities data structure

The service capabilities reflect optional functionality of a service. The information is static and does not change during device operation. The following capabilities are available:

-   `MaxLimit`
    
    The maximum number of entries returned by a single `GetList` request. The device shall never return more than this number of entities in a single response.
    
-   `DisableCredential`
    
    True if `EnableCredential` and `DisableCredential` operations is supported.
    
-   `GetAccessPoint`
    
    True if `GetAccessPointList` and `GetAccessPoint` operations are supported.
    
-   `SetAccessPoint`
    
    True if `SetAccessPoint` operations is supported.
    
-   `RemoveAccessPoint`
    
    True if `RemoveAccessPoint` operation is supported.
    
-   `GetArea`
    
    True if `GetAreaList` and `GetArea` operations are supported.
    
-   `SetArea`
    
    True if `SetArea` operation is supported.
    
-   `RemoveArea`
    
    True if `RemoveArea` operation is supported.
    
-   `GetCredential`
    
    True if `GetCredentialList` and `GetCredential` operations are supported
    
-   `SetCredential`
    
    True if `SetCredential` operation is supported.
    
-   `RemoveCredential`
    
    True if `RemoveCredential` operation is supported.
    
-   `StandardAttributesSupported`
    
    True if the `GetStandardAttributes` operation is supported.
    
-   `VendorAttributesSupported`
    
    True if the `GetVendorAttributes` operation is supported.
    

#### GetServiceCapabilities command

This operation returns the capabilities of the Access Control service.

An ONVIF compliant device which provides the Access Control service shall implement this method.

GetServiceCapabilities Command

-   Name: `GetServiceCapabilities`
-   Access Class: PRE\_AUTH

| Message name | Description |
| --- | --- |
| `GetServiceCapabilitiesRequest` | This message shall be empty. |
| `GetServiceCapabilitiesResponse` | This message contains:  
  
\- `Capabilities`: The capability response message contains the requested Access Control service capabilities using a hierarchical XML capability structure.  
  
`tac:ServiceCapabilities Capabilities [1][1]` |

### Access point information

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

#### AccessPointInfo data structure

The `AccessPointInfo` structure contains basic information about an `AccessPoint` instance. An `AccessPoint` defines an entity a `Credential` can be granted or denied access to. The `AccessPointInfo` provides basic information on how access is controlled in one direction for a door (from which area to which area).

Door is the typical device involved, but other type of devices may be supported as well. Multiple `AccessPoint` items may cover the same `Door` and/or `IdPoint` items. A typical case is one `AccessPoint` for entry and another for exit, both referencing the same `Door`.

If an `AccessPoint` is disabled, it shall not be considered in the decision making process and no commands (e.g. `AccessDoor` requests) will be issued from that `AccessPoint` to the door (or other type of Entity) configured for that `AccessPoint`.

An ONVIF compliant device shall provide the following fields for each `AccessPoint` instance:

-   `token`
    
    A service-unique identifier of the `AccessPoint`.
    
-   `Name`
    
    A user readable name. It shall be up to 64 characters.
    
-   `Entity`
    
    Reference to the entity used to control access; the entity type may be specified by the optional `EntityType` field explained below but is typically a `Door`.
    
-   `Capabilities`
    
    The capabilities for the `AccessPoint`.
    

To provide more information, the device may include the following optional fields:

-   `Description`
    
    Optional user readable description for the `AccessPoint`. It shall be up to 1024 characters.
    
-   `AreaFrom`
    
    Optional reference to the `Area` from which access is requested.
    
-   `AreaTo`
    
    Optional reference to the `Area` to which access is requested.
    
-   `EntityType`
    
    Optional entity type; if missing, a Door type as defined by the ONVIF DoorControl service should be assumed. This can also be represented by the QName value "`tdc:Door`". This field is provided for future extensions; it will allow an `AccessPoint` being extended to cover entity types other than `Door` items as well.
    

#### AccessPointCapabilities data structure

The `AccessPoint` capabilities reflect optional functionality of a particular physical entity. Different `AccessPoint` instances may have different set of capabilities. This information may change during device operation, e.g. if hardware settings are changed. The following capabilities are available:

-   `DisableAccessPoint`
    
    Indicates whether or not this `AccessPoint` instance supports `EnableAccessPoint` and `DisableAccessPoint` commands.
    
-   `Duress`
    
    Indicates whether or not this `AccessPoint` instance supports generation of duress events.
    
-   `AnonymousAccess`
    
    Indicates whether or not this `AccessPoint` has a REX switch or other input that allows anonymous access.
    
-   `AccessTaken`
    
    Indicates whether or not this `AccessPoint` instance supports generation of `AccessTaken` and `AccessNotTaken` events. If `AnonymousAccess` and `AccessTaken` are both true, it indicates that the `Anonymous` versions of `AccessTaken` and `AccessNotTaken` are supported.
    
-   `ExternalAuthorization`
    
    Indicates whether or not this `AccessPoint` instance supports the `ExternalAuthorization` operation and the generation of `Request` events. If `AnonymousAccess` and `ExternalAuthorization` are both true, it indicates that the `Anonymous` version is supported as well.
    

#### GetAccessPointInfoList command

This operation requests a list of all `AccessPointInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAccessPointInfoList Command

-   Name: `GetAccessPointInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessPointInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessPointInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessPointInfo`: List of `AccessPointInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`tac:AccessPointInfo AccessPointInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessPointInfo command

This operation requests a list of `AccessPointInfo` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens. The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessPointInfo Command

-   Name: `GetAccessPointInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessPointInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessPointInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessPointInfoResponse` | This message contains:  
  
\- `AccessPointInfo`: List of `AccessPointInfo` items.  
  
`tac:AccessPointInfo AccessPointInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

### Area information

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

#### AreaInfo data structure

The `AreaInfo` structure contains basic information about an `Area`. An ONVIF compliant device shall provide the following fields for each `Area`:

-   `token`
    
    A service-unique identifier of the `Area`.
    
-   `Name`
    
    User readable name. It shall be up to 64 characters.
    

To provide more information, the device may include the following optional field:

-   `Description`
    
    User readable description for the `Area`. It shall be up to 1024 characters.
    

#### GetAreaInfoList command

This operation requests a list of all `AreaInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAreaInfoList Command

-   Name: `GetAreaInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAreaInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAreaInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AreaInfo`: List of `AreaInfo` items.  
  
xs:string **NextStartReference \[0\]\[1\]**  
tac:AreaInfo **AreaInfo \[0\]\[unbounded\]** |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAreaInfo command

This operation requests a list of `AreaInfo` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens. The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAreaInfo Command

-   Name: `GetAreaInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAreaInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `AreaInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAreaInfoResponse` | This message contains:  
  
\- `AreaInfo`: List of `AreaInfo` items.  
  
`tac:AreaInfo AreaInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

### Access point status

The state of the `AccessPoint` is determined by a number of operations that can be performed on it depending on its capabilities.

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

#### AccessPointState data structure

The `AccessPointState` contains state information for an `AccessPoint`. An ONVIF compliant device shall provide the following fields for each `AccessPoint` instance:

-   `Enabled`
    
    Indicates that the `AccessPoint` is enabled. By default this field value shall be `True`, if the `DisableAccessPoint` capabilities is not supported.
    

#### GetAccessPointState command

This operation requests the `AccessPointState` for the `AccessPoint` instance specified by token.

An ONVIF compliant device that provides Access Control service shall implement this method.

GetAccessPointState Command

-   Name: `GetAccessPointState`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessPointStateRequest` | This message contains:  
  
\- `Token`: Token of `AccessPoint` instance to get `AccessPointState` for.  
  
`pt:ReferenceToken Token [1][1]` |
| `GetAccessPointStateResponse` | This message contains:  
  
\- `AccessPointState`: `AccessPointState` item.  
  
`tac:AccessPointState AccessPointState [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessPoint` is not found. |

### Access control commands

The service control commands contain operations that allow modifying `AccessPoint` states and controlling `AccessPoints`.

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

#### Decision data structure

The `Decision` enumeration represents a choice of two available options for an access request:

-   `Granted`
    
    The decision is to grant access.
    
-   `Denied`
    
    The decision is to deny access.
    

#### EnableAccessPoint command

This operation allows enabling an access point.

A device that signals support for `DisableAccessPoint` capability for a particular `AccessPoint` instance shall implement this command.

EnableAccessPoint Command

-   Name: `EnableAccessPoint`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `EnableAccessPointRequest` | This message contains:  
  
\- `Token`: Token of the `AccessPoint` instance to enable.  
  
`pt:ReferenceToken Token [1][1]` |
| `EnableAccessPointResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The specified token is not found. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The operation is not supported. |

#### DisableAccessPoint command

This operation allows disabling an access point.

A device that signals support for `DisableAccessPoint` capability for a particular `AccessPoint` instance shall implement this command.

DisableAccessPoint Command

-   Name: `DisableAccessPoint`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `DisableAccessPointRequest` | This message contains:  
  
\- `Token`: Token of the `AccessPoint` instance to disable.  
  
`pt:ReferenceToken Token [1][1]` |
| `DisableAccessPointResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The specified token is not found. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The operation is not supported. |

#### ExternalAuthorization command

This operation allows to deny or grant decision at an `AccessPoint` instance.

A device that signals support for `ExternalAuthorization` capability for a particular `AccessPoint` instance shall implement this method.

ExternalAuthorization Command

-   Name: `ExternalAuthorization`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `ExternalAuthorizationRequest` | This message contains:  
  
\- `AccessPointToken`: Token of the `AccessPoint` instance.:  
\- `CredentialToken`: Optional. Token of the `Credential` involved.:  
\- `Reason`: Optional. Reason for decision.:  
\- `Decision`: Decision. Granted or Denied.  
  
`pt:ReferenceToken AccessPointToken [1][1]`  
`pt:ReferenceToken CredentialToken [0][1]`  
`xs:string Reason [0][1]`  
`tac:Decision Decision [1][1]` (extendable) |
| `ExternalAuthorizationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The specified token is not found. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | `AccessPoint` is not found. |

### AccessPoint configuration

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### AccessPoint data structure

The `AccessPoint` structure provides the full configuration for an `AccessPoint`. The `AccessPoint` structure defines a mapping between one or multiple `axtid:IdPoints` and some `Entity` (typically of the `EntityType` `tdc:Door`) used to control access. Multiple mappings covering the same `IdPoint` and the same `Door` may exist.

The `IdPointDevice` list may contain multiple I`dPoint` items in cases where request can or must come from more than one `IdPoint` - e.g. one fingerprint reader and one card reader.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AccessPoint`.
    
-   `Name`
    
    A user readable name. It shall be up to 64 characters.
    
-   `Entity`
    
    Reference to the entity used to control access; the entity type may be specified by the optional `EntityType` field explained below but is typically a `Door`.
    
-   `Enabled`
    
    Whether this `AccessPoint` is enabled or not.
    
-   `IdPointDevice`
    
    List of `IdPoint` items and their device info.
    
-   `AuthenticationProfile`
    
    List of `AuthenticationProfile` items that apply for this `AccessPoint`.
    
-   `Attribute`
    
    Optional attributes associated with this `AccessPoint`.
    
-   `ActionArgument`
    
    Optional arguments to action associated with this `AccessPoint`.
    
-   `Action`
    
    Action associated with this `AccessPoint`, typically "`AccessDoor`".
    

To provide more information, the device may include the following optional fields:

-   `Description`
    
    Optional user readable description for the `AccessPoint`. It shall be up to 1024 characters.
    
-   `AreaFrom`
    
    Optional reference to the `Area` from which access is requested.
    
-   `AreaTo`
    
    Optional reference to the `Area` to which access is requested.
    
-   `EntityType`
    
    Optional entity type; if missing, a Door type as defined by the ONVIF DoorControl service should be assumed. This can also be represented by the QName value "`tdc:Door`". This field is provided for future extensions; it will allow an `AccessPoint` being extended to cover entity types other than door as well.
    
-   `DoorDeviceUUID`
    
    DeviceUUID, if empty or not specified, the `Door` token refers to this device and may be filled in by the device.
    

#### IdPointDevice data structure

The following fields are available:

-   `IdPoint`
    
    Reference to a `axtid:IdPoint`.
    

To provide more information, the device may include the following optional field:

-   `DeviceUUID`
    
    DeviceUUID of the device where `IdPoint` is located. if empty or not specified, the `IdPoint` token refers to this device and may be filled in by the device.
    

#### ActionArgument

Argument to be used in `Action` items.

The following fields are available:

-   `Name`
    
    Name of argument.
    
-   `Value`
    
    Value of argument.
    

To provide more information, the device may include the following optional field:

-   `type`
    
    Type of argument.
    

#### GetAccessPointList command

This operation requests a list of all of `AccessPoint` items provided by the device. This function shall be implemented if the `GetAccessPoint` service capability is true.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAccessPointList Command

-   Name: `GetAccessPointList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessPointListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessPointListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessPoint`: List of `AccessPoint` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessPoint AccessPoint [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessPoint command

This operation requests a list of `AccessPoint` items matching the given tokens.

This method shall be supported if the `GetAccessPoint` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessPoint Command

-   Name: `GetAccessPoint`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessPointRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessPoint` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessPointResponse` | This message contains:  
  
\- `AccessPoint`: List of `AccessPoint` items.  
  
`pacsaxis:AccessPoint AccessPoint [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetAccessPoint command

Add/update a list of `AccessPoint` items.

If `AccessPoint` items with the specified tokens already exist, they shall be updated. If not, they shall be added.

If the token field of any `AccessPoint` is empty, the service shall allocate a token for the `AccessPoint`.

All tokens shall be returned in the response.

This function must be available if the `SetAccessPoint` service capability is true.

SetAccessPoint Command

-   Name: `SetAccessPoint`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAccessPointRequest` | This message contains:  
  
\- `AccessPoint`: The `AccessPoint` items to add/update.  
  
`pacsaxis:AccessPoint AccessPoint [1][unbounded]` |
| `SetAccessPointResponse` | This message contains:  
  
\- `Token`: The Tokens of the added/updated `AccessPoint` items.  
  
`pt:ReferenceToken Token [1][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` |  |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotAllowed` |  |

#### RemoveAccessPoint command

Remove the specified `AccessPoint` items.

This function must be available if the `RemoveAccessPoint` service capability is true.

RemoveAccessPoint Command

-   Name: `RemoveAccessPoint`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAccessPointRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessPoint` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveAccessPointResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessPoint` is not found. |

### Area configuration

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### Area data structure

An area is configured using the `Area` data structure which contains information and settings about an area.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `Area`.
    
-   `Name`
    
    User readable name. It shall be up to 64 characters.
    
-   `Attribute`
    
    Attribute list for the `Area`.
    

To provide more information, the device may include the following optional fields:

-   `Description`
    
    User readable description for the Area. It shall be up to 1024 characters.
    
-   `Extension`
    
    Future extension .
    

#### GetAreaList command

This operation requests a list of all of `Area` items provided by the device. This function shall be implemented if the `GetArea` service capability is true.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAreaList Command

-   Name: `GetAreaList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAreaListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAreaListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `Area`: List of `Area` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:Area Area [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetArea command

This operation requests a list of `Area` items matching the given tokens.

This method shall be supported if the `GetArea` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetArea Command

-   Name: `GetArea`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAreaRequest` | This message contains:  
  
\- `Token`: Tokens of `Area` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAreaResponse` | This message contains:  
  
\- `Area`: List of `Area` items.  
  
`pacsaxis:Area Area [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetArea command

Add/update a list of `Area` items.

If `Area` with the specified tokens already exist, they shall be updated. If not, they shall be added.

If the token field of any `Area` is empty, the service shall allocate a token for the `Area`.

All tokens shall be returned in the response.

This function must be available if the `SetArea` service capability is true.

SetArea Command

-   Name: `SetArea`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAreaRequest` | This message contains:  
  
\- `Area`: The `Area` items to add/update.  
  
`pacsaxis:Area Area [1][unbounded]` |
| `SetAreaResponse` | This message contains:  
  
\- `Token`: The tokens of the added/updated `Area` items.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` |  |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotAllowed` |  |

#### RemoveArea command

Remove the specified `Area` items.

This function must be available if the `RemoveArea` service capability is true.

RemoveArea Command

-   Name: `RemoveArea`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAreaRequest` | This message contains:  
  
\- `Token`: Tokens of `Area` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveAreaResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `Area` is not found. |

### AccessController information

The `AccessController` entity provides a grouping of `AccessPoint` items.

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### AccessControllerInfo

Information for an `AccessController`.

Provides a list of the available `AccessPoint` items controlled by the `AccessController` so that a topological view can be generated for systems consisting of multiple `AccessController` items exposed thru one device.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AccessController`.
    
-   `Name`
    
    Short name of `AccessController`.
    
-   `AccessPoint`
    
    List of `AccessPoint` items the `AccessController` manages.
    

To provide more information, the device may include the following optional field:

-   `Description`
    
    Description of the `AccessController`.
    

#### GetAccessControllerInfoList command

This operation requests a list of all `AccessControllerInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAccessControllerInfoList Command

-   Name: `GetAccessControllerInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessControllerInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessControllerInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessControllerInfo`: List of `AccessControllerInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessControllerInfo AccessControllerInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessControllerInfo command

This operation requests a list of `AccessControllerInfo` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens. The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessControllerInfo Command

-   Name: `GetAccessControllerInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessControllerInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessControllerInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessControllerInfoResponse` | This message contains:  
  
\- `AccessControllerInfo`: List of `AccessControllerInfo` items.  
  
`pacsaxis:AccessControllerInfo AccessControllerInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

### AccessController configuration

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### AccessController data structure

The `AccessController` structure contains the full configuration from an access controller.

The `AccessController` receives request for access from IDP:s - Identification Points, by some internal means, using the ONVIF Event mechanism or API call and controls Doors and other resources/targets.

You can do get/set/remove on `AccessController` items depending on capabilities.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AccessController`.
    
-   **Name**: Short name of `AccessController`.
    
-   `AccessPoint`
    
    List of `AccessPoint` items the `AccessController` manages.
    

To provide more information, the device may include the following optional field:

-   `Description`
    
    Description of the `AccessController`.
    

#### GetAccessControllerList command

This operation requests a list of all `AccessController` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAccessControllerList Command

-   Name: `GetAccessControllerList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessControllerListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessControllerListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessController`: List of `AccessController` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessController AccessController [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessController command

This operation requests a list of `AccessController` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens.

The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessController Command

-   Name: `GetAccessController`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessControllerRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessController` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessControllerResponse` | This message contains:  
  
\- `AccessController`: List of `AccessController` items.  
  
`pacsaxis:AccessController AccessController [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetAccessController command

Add/update a list of `AccessController` items.

If `AccessController` items with the specified tokens already exist, they shall be updated. If not, they shall be added.

If the `Token` field of any `AccessController` is empty, the service shall allocate a token for the `AccessController`.

All tokens shall be returned in the response.

SetAccessController Command

-   Name: `SetAccessController`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAccessControllerRequest` | This message contains:  
  
\- `AccessController`: The `AccessController` items to add/update.  
  
`pacsaxis:AccessController AccessController [1][unbounded]` |
| `SetAccessControllerResponse` | This message contains:  
  
\- `Token`: The Tokens of the added/updated `AccessController` items.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` |  |
| `env:Sender` `ter:ActionNotSupported` `ter:NotAllowed` |  |

#### RemoveAccessController command

Remove the specified `AccessController` items.

RemoveAccessController Command

-   Name: `RemoveAccessController`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAccessControllerRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessController` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveAccessControllerResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessController` is not found. |

### Access management

Credential management involves a number of data structures that defines the requirements for granting access, and a number of operations to modify those structures. The major structures involved are the `Credential`, `AccessProfile` and `AuthenticationProfile` structures.

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

#### Credential datatype

A `Credential` contains a number of `IdData` items that represent the credential data such as card number, PIN etc.

The `Credential` is assigned a number of `AccessProfile` items using the `CredentialAccessProfile` where `ValidFrom` and `ValidTo` can be individually assigned.

#### CredentialInfo data structure

Information about a `Credential`.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `Credential`.
    
-   `Enabled`
    
    Whether `Credential` is enabled or not.
    
-   `Status`
    
    Information regarding status of the `Credential`, e.g. the reason for being disabled. Should normally be one of the defined values in the `CredentialStatusEnum` type.
    

To provide more information, the device may include the following optional fields:

-   `UserToken`
    
    Identifies the `User` of the `Credential`. For security, privacy and possibly other reasons this is optional.
    
-   `Description`
    
    Description of the `Credential`.
    
-   `ValidFrom`
    
    When `Credential` starts to be valid. If null, the credential has no restriction on when it starts to be valid (valid from whenever).
    
-   `ValidTo`
    
    When `Credential` stops to be valid. If null, the credential has no restriction on when it stops to be valid (valid forever).
    

#### CredentialStatusEnum data structure

The status of the credential, e.g. reason for being disabled etc. This value should be used as the `Reason` field in certain events.

The following values are available:

-   `NotActivated`
    
    Credential is not activated yet (BACNET has Unassigned and not\_provisioned).
    
-   `Enabled`
    
    Credential is enabled, this is the only state in which access can be granted.
    
-   `Disabled`
    
    Credential is disabled for unknown reason.
    
-   `LockedOut`
    
    Credential is locked out.
    
-   `Lost`
    
    Credential is reported as lost.
    
-   `Stolen`
    
    Credential is reported as stolen.
    
-   `Damaged`
    
    Credential is reported as damaged.
    
-   `Destroyed`
    
    Credential is reported as destroyed.
    
-   `Inactive`
    
    Credential is disabled due to inactivity.
    
-   `MaxDays`
    
    Credential is disabled due to being used maximum number of days.
    
-   `MaxUses`
    
    Credential is disabled due to being used maximum number of times.
    
-   `Expired`
    
    Credential has expired.
    

#### Credential data structure

The `Credential` data structure for the `AccessController` items.

The `Credential` contains information needed to authenticate a user and a list of references to `AccessProfile` that determines what this credential is authorized to do.

`AttributeList` is a list of names or name=value pairs. The following standard Attributes exist: `ExtendedTime`

A number of these datastructures is stored within the servce and managed using the set/get/remove credential API functions.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `Credential`.
    
-   `Enabled`
    
    Whether `Credential` is enabled or not.
    
-   `Status`
    
    Information regarding status of the `Credential`, e.g. the reason for being disabled. Should normally be one of the defined values in the `CredentialStatusEnum` type.
    
-   `IdData`
    
    The identification data for the credential.
    
-   `Attribute`
    
    Attributes associated with the credential.
    
-   `AuthenticationProfile`
    
    Overrides `AuthenticationProfile` items specified in an `AccessProfile` or `AccessPolicy` if it is set.
    
-   `CredentialAccessProfile`
    
    `AccessProfile` items associated with the credential.
    

To provide more information, the device may include the following optional fields:

-   `UserToken`
    
    Identifies the `User` of the `Credential`. For security, privacy and possibly other reasons this is optional.
    
-   `Description`
    
    Description of the `Credential`
    
-   `ValidFrom`
    
    When `Credential` starts to be valid. If null, the credential has no restriction on when it starts to be valid (valid from whenever).
    
-   `ValidTo`
    
    When `Credential` stops to be valid. If null, the credential has no restriction on when it stops to be valid (valid forever).
    

#### IdData data structure

`IdData` contains a single identification/authentication name and the value. A list of these are stored in each `Credential`. The `IdPoint` service sends a number of these as `SimpleItem` name/nalue pairs in the `Data` section.

The following fields are available:

-   `Name`
    
    Name of the field (called `IdField` in other types.)
    
-   `Value`
    
    The value to match against.
    

#### CredentialAccessProfile data structure

Used by the `Credential` to reference one `AccessProfile`, and allowing `ValidFrom` and `ValidTo` to be further restricted compared to what is in the `AccessProfile`.

The following fields are available:

-   `AccessProfile`
    
    Reference to `AccessProfile`.
    

To provide more information, the device may include the following optional fields:

-   `ValidFrom`
    
    Optional `ValidFrom` that may limit the time period for the `AccessProfile`, if null no additional restriction.
    
-   `ValidTo`
    
    Optional `ValidTo` that may limit the time period for the `AccessProfile`, if null no additional restriction.
    

#### AuthenticationProfile datatype

The `AuthenticationProfile` data structure defines what `IdFactor` items are required at certain schedules.

`AuthenticationProfile` items are referenced by the `AccessPoint` but can be overridden in the `AccessProfile` and in the `Credential`.

#### AuthenticationProfileInfo data structure

Information about an `AuthenticationProfile`.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AuthenticationProfile`.
    
-   `Name`
    
    Name of the `AuthenticationProfile`.
    
-   `Description`
    
    Description of the `AuthenticationProfile`.
    

#### AuthenticationProfile data structure

The `AuthenticationProfile` holds the authentication requirements.

A number of these data structures is stored within the service and managed using the set, get and remove `AuthenticationProfile` API functions.

By default the device MUST have at least the following predefined authentication profiles, although they can be modified using the API:

-   `CardOnly`
    
    Requiring only the `IdDataName` "`Card`".
    
-   `PINOnly`
    
    Requiring only the `IdDataName` "`PIN`".
    
-   `CardPlusPIN`
    
    Requiring the `IdDataName` items "`Card`" and "`PIN`".
    

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AuthenticationProfile`.
    
-   `Name`
    
    Name of the `AuthenticationProfile`.
    
-   `Description`
    
    Description of the `AuthenticationProfile`
    
-   `Schedule`
    
    The `Schedule` items that determine when the `AuthenticationProfile` is applicable.
    
-   `IdFactor`
    
    The `IdFactor` items needed to authenticate.
    

To provide more information, the device may include the following optional field:

-   `Extension`
    
    Extension
    

#### IdMatchOperator data structure

An `IdMatchOperator` determines the way a `Request IdData Value` field in `Request` and other conditions should be evaluated/treated. ONVIF defines a number of mandatory operators, some optional and device vendors may create new ones. The available `IdMatchOperator` items are returned in the `ServiceCapabilities`.

The following fields are available:

-   `Name`
    
    Name of the `IdMatchOperator`.
    
-   `Description`
    
    Description of the operator.
    

#### IdFactor data structure

An `IdFactor` contains the `Name` of a the `IdData` and the `IdMatchOperator` to use. The available `IdMatchOperator` items are available in the `ServiceCapabilities`. The following fields are available:

-   `IdDataName`
    
    The `Name` of an `IdData` field to check.
    
-   `IdMatchOperatorName`
    
    A `Name` of an existing `IdMatchOperator`.
    
-   `OperatorValue`
    
    Info/config for certain operators, typically empty.
    

#### Attributes

`Attributes` is a generic structure that can be added to various data structures, and can be used by clients/management systems for various reasons.

Some standardised attributes exists, which have a defined meaning. The supported attributes that has a special meaning shall be returned by the `GetStandardAttributeList` and `GetVendorAttributeList` methods.

#### Attribute data structure

`Attribute` contains a `Name` and an optional `Value` and type.

The following fields are available:

-   `Name`
    
    Name of attribute
    

To provide more information, the device may include the following optional fields:

-   `type`
    
    Type of the `Attribute`. int, bool or string.
    
-   `Value`
    
    Value of attribute.
    

#### AccessProfile datatype

An `AccessProfile` contains a number of `AccessPolicy` items that reference `AccessPoint` items and contains the authorization conditions such as schedules.

#### AccessProfileInfo data structure

Information about an `AccessProfile`.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AccessProfile`.
    
-   `Name`
    
    Name of the `AccessProfile`.
    
-   `Description`
    
    Description of the `AccessProfile`.
    

#### AccessProfile data structure

The `AccessProfile` data structure for the `AccessController`.

The `AccessProfile` determine what resources that can be accessed and when by containing references to `AccessPolicy` items. It also contains information on what `AuthenticationProfile` items that apply.

A number of these data structures is stored within the service and managed using set, get and remove `AccessProfile` API functions.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AccessProfile`.
    
-   `Name`
    
    Name of the `AccessProfile`.
    
-   `Description`
    
    Description of the `AccessProfile`.
    
-   `Schedule`
    
    The `Schedule` items that determine when the `AccessProfile` is applicable and access to the resources is allowed if the requirements in the `AuthenticationProfile` items etc. are fulfilled.
    
-   `AuthenticationProfile`
    
    The authentication profiles for this `AccessProfile`. This list overrides the list in the `AccessPoint`, so it is typically empty. If one of the authentication profiles in the list is fulfilled access is granted to the resources.
    
-   `Attribute`
    
    Attributes associated with the `AccessProfile`.
    
-   `AccessPolicy`
    
    List of `AccessPolicy` that are allowed.
    
-   `Enabled`
    
    If this `AccessProfile` is enabled or not.
    

To provide more information, the device may include the following optional fields:

-   `ValidFrom`
    
    When `AccessProfile` starts to be valid. If null, no restriction on start time.
    
-   `ValidTo`
    
    When `AccessProfile` stops to be valid. If null, no restriction on stop time.
    

#### AccessPolicy data structure

The `AccessPolicy` data structure defines the authentication and authorization requirements for a `Resource` and is a used by the `AccessProfile` data structure. Multiple `AccessPolicy` items may reference the same `Resource` and have different authentication and authorization requirements.

The following fields are available:

-   `AuthorizationProfile`
    
    List of `AuthorizationProfile` items that apply to this policy.
    
-   `Attribute`
    
    Optional `Attribute` list that is applicable for the `AccessPolicy`.
    
-   `Schedule`
    
    `Schedule` items when authorized by this `AccessPolicy` if the other conditions is met.
    
-   `AccessPoint`
    
    Reference to the `AccessPoint` this `AccessPolicy` is applicable for.
    

#### AuthorizationProfile datatype

`AuthorizationProfile` is a placeholder for future extensions where additional authorizations rules and conditions can be specified.

#### AuthorizationProfileInfo data structure

Information about an `AuthorizationProfile`.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AuthorizationProfile`.
    
-   `Name`
    
    Name of the `AuthorizationProfile`.
    
-   `Description`
    
    Description of the `AuthorizationProfile`.
    

#### RuleOperator data structure

A `RuleOperator` determines the way a `Request IdData Value` field in `Request` and other conditions should be evaluated/treated.

ONVIF defines a number of mandatory operators, some optional and device vendors may create new ones.

The available `RuleOperator` items are returned by the `GetRuleOperators` method.

The following fields are available:

-   `Name`
    
    Name of the `RuleOperator`.
    
-   `Description`
    
    Description of the operator.
    

#### Rule data structure

An `Rule` contains the `Name` of the `Rule` which should be the same as the `IdData` in a `Request` (and in the `Credential`) and the `RuleOperator` to use.

The available `RuleOperator` items are returned by the `GetRuleOperators` method.

The following fields are available:

-   `Name`
    
    The name of the `Rule`.
    
-   `OperatorValue`
    
    Values for certain operators.
    
-   `OperatorName`
    
    A `Name` of an existing `RuleOperator`.
    

#### AuthorizationProfile data structure

The `AuthorizationProfile` holds the authorization requirements.

A number of these data structures is stored within the service and managed using the set, get and remove `AuthorizationProfile` API functions.

The following fields are available:

-   `token`
    
    A service-unique identifier of the `AuthorizationProfile`.
    
-   `Name`
    
    Name of the `AuthorizationProfile`.
    
-   `Description`
    
    Description of the `AuthorizationProfile`.
    
-   `Schedule`
    
    The `Schedule` items that determine when the `AuthorizationProfile` is applicable.
    
-   `Rule`
    
    Additional rules needed to authorize.
    

To provide more information, the device may include the following optional field:

-   `Extension`
    
    Future extension.
    

### Attribute operations

The attributes are assigned in various data structures, but for a client to know what attributes that are available and have special meaning, a couple of operations is defined.

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### GetStandardAttributeList command

Returns a list of attributes and their value type supported by the service. ONVIF mandates the following attributes:

-   `ExtendedTimeFlag`
    
    If extended times should be used in `AccessDoor`.
    
-   `IdFactorOverride=string`
    
    overrides `AuthenticationProfile`.  
      
    `IdFactor`, string should be in the form `IdDataName=RuleOperatorName` E.g. `IdFactorOverride=PIN=DontCare`
    

Other attributes that perhaps should be standardized (but not mandatory):

-   `EscortRequired`
    
    If the holder of the `Credential` requires escort, or if a `Resource` referenced by an `AccessProfile` requires escort.
    
-   `EscortNotRequired`
    
    If the holder of the `Credential` does not require escort.
    
-   `Escort`
    
    The holder of the credential is an escort.
    

GetStandardAttributeList Command

-   Name: `GetStandardAttributeList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetStandardAttributeListRequest` | This message shall be empty. |
| `GetStandardAttributeListResponse` | This message contains:  
  
\- `Attribute`: List of supported standardized `Attribute` items`pt:Attribute Attribute [0][unbounded]` |

#### GetVendorAttributeList command

This function shall return the vendor specific attributes supported.

GetVendorAttributeList Command

-   Name: `GetVendorAttributeList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetVendorAttributeListRequest` | This message shall be empty. |
| `GetVendorAttributeListResponse` | This message contains:  
  
\- `Attribute`: List of supported vendor specific attributes.  
  
`pt:Attribute Attribute [0][unbounded]` |

### Extended access operations

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### VerifyRequest command

Perform a validation of the request, and return the result, but does not perform any action.

VerifyRequest Command

-   Name: `VerifyRequest`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `VerifyRequestRequest` | This message contains:  
  
\- `Token`: The `AccessController` to send request to.:  
\- `IdData`: The id data, typically including entries for card and PIN.:  
\- `SourceToken`: Where the request comes from.:  
\- `TargetToken`: The `Resource` the subject identified by `IdField` items and/or PIN want access to.:  
\- `Action`: The desired action on the resource. If missing "`Access`" should be assumed.:  
\- `Environment`: Additional information.  
  
`pt:ReferenceToken Token [1][1]`  
`pacsaxis:IdData IdData [0][unbounded]`  
`pt:ReferenceToken SourceToken [0][1]`  
`pt:ReferenceToken TargetToken [0][1]`  
`xs:string Action [0][1]`  
`pacsaxis:NameValue Environment [0][unbounded]` |
| `VerifyRequestResponse` | This message contains:  
  
\- `AccessGranted`: True if access is granted, false if denied.:  
\- `Reason`: Reason for denial.  
  
`xs:boolean AccessGranted [1][1]`  
`xs:string Reason [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessController` is not found. |

#### NameValue data structure

Generic structure containing a name/value pair.

The following fields are available:

-   `Name`
    
    Name
    
-   `Value`
    
    Value
    

#### RequestAccess command

Request access to the specified `Resource` with the given `IdField` items.

RequestAccess Command

-   Name: `RequestAccess`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `RequestAccessRequest` | This message contains:  
  
\- `Token`: The `AccessController` to send request to.:  
\- `IdData`: The id data, typically including entries for card and PIN.:  
\- `SourceToken`: Where the request comes from.:  
\- `TargetToken`: The `Resource` the subject identified by `IdField` items and/or PIN want access to.:  
\- `Action`: The desired action on the resource. If missing "`Access`" should be assumed.:  
\- `Environment`: Additional information.  
  
`pt:ReferenceToken Token [1][1]`  
`pacsaxis:IdData IdData [0][unbounded]`  
`pt:ReferenceToken SourceToken [0][1]`  
`pt:ReferenceToken TargetToken [0][1]`  
`xs:string Action [0][1]`  
`pacsaxis:NameValue Environment [0][unbounded]` |
| `RequestAccessResponse` | This message contains:  
  
\- `AccessGranted`: True if access is granted, false if denied.:  
\- `Reason`: Reason for denial.  
  
`xs:boolean AccessGranted [1][1]`  
`xs:string Reason [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessController` is not found. |

### Credential operations

These operations are used to manage the `Credential` database.

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### GetCredentialInfoList command

This operation requests a list of all `CredentialInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

This function must be available if the `GetCredentialListSupported` service capability is true.

GetCredentialInfoList Command

-   Name: `GetCredentialInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetCredentialInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetCredentialInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `CredentialInfo`: List of `CredentialInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:CredentialInfo CredentialInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetCredentialInfo command

This operation requests a list of `CredentialInfo` items matching the given tokens.

This method shall be supported if the `GetCredential` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetCredentialInfo Command

-   Name: `GetCredentialInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetCredentialInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `CredentialInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetCredentialInfoResponse` | This message contains:  
  
\- `CredentialInfo`: List of `CredentialInfo` items.  
  
`pacsaxis:CredentialInfo CredentialInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### EnableCredential command

This operation shall enable a credential.

This function must be available if the `DisableCredential` service capability is true.

EnableCredential Command

-   Name: `EnableCredential`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `EnableCredentialRequest` | This message contains:  
  
\- `Token`: The `Credential` to enable.  
  
`pt:ReferenceToken Token [1][1]` |
| `EnableCredentialResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### DisableCredential command

This operation shall disable a credential.

This function must be available if the `DisableCredential` service capability is true.

DisableCredential Command

-   Name: `DisableCredential`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `DisableCredentialRequest` | This message contains:  
  
\- `Token`: The `Credential` to disable.:  
\- `Status`: Optional status to set about the reason to disable the credential. If missing "`Disabled`" should be assumed.  
  
`pt:ReferenceToken Token [1][1]`  
`pacsaxis:CredentialStatusEnum Status [0][1]` |
| `DisableCredentialResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

#### GetCredentialList command

This operation requests a list of all `Credential` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

This function must be available if the `GetCredential` service capability is true.

info

This could be a security risk.

GetCredentialList Command

-   Name: `GetCredentialList`
-   Access Class: READ\_SYSTEM\_SECRET

| Message name | Description |
| --- | --- |
| `GetCredentialListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetCredentialListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `CredentialInfo`: List of `CredentialInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:CredentialInfo CredentialInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetCredential command

This operation requests a list of `Credential` items matching the given tokens.

This method shall be supported if the `GetCredential` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

info

This could be a security risk.

GetCredential Command

-   Name: `GetCredential`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetCredentialRequest` | This message contains:  
  
\- `Token`: Tokens of `Credential` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetCredentialResponse` | This message contains:  
  
\- `Credential`: List of `Credential` items.  
  
`pacsaxis:Credential Credential [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetCredential command

Add/update a list of `Credential` items.

If `Credential` items with the specified tokens already exist, they shall be updated. If not, they shall be added.

If the `Token` field of any Credential item is empty, the service shall allocate a token for the `Credential`.

All tokens shall be returned in the response.

SetCredential Command

-   Name: `SetCredential`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetCredentialRequest` | This message contains:  
  
\- `Credential`: The `Credential` items to add/update.  
  
`pacsaxis:Credential Credential [1][unbounded]` |
| `SetCredentialResponse` | This message contains:  
  
\- `Credential`: List of `Credential` items.  
  
`pacsaxis:Credential Credential [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidCredentialFault` | Invalid credential. |

#### RemoveCredential command

Remove the specified `Credential` items.

RemoveCredential Command

-   Name: `RemoveCredential`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveCredentialRequest` | This message contains:  
  
\- `Token`: Tokens of the `Credential` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveCredentialResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `Credential` is not found. |

### AccessProfile operations

These operations are used to manage `AccessProfile` entities.

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### GetAccessProfileInfoList command

This operation requests a list of all `AccessProfileInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

This function is mandatory.

GetAccessProfileInfoList Command

-   Name: `GetAccessProfileInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessProfileInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessProfileInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessProfileInfo`: List of `AccessProfileInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessProfileInfo AccessProfileInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessProfileInfo command

This operation requests a list of `AccessProfileInfo` items matching the given tokens.

This method shall be supported if the `GetAccessProfile` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessProfileInfo Command

-   Name: `GetAccessProfileInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAccessProfileInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessProfileInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessProfileInfoResponse` | This message contains:  
  
\- `AccessProfileInfo`: List of `AccessProfileInfo` items.  
  
`pacsaxis:AccessProfileInfo AccessProfileInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### GetAccessProfileList command

This operation requests a list of all of `AccessProfile` items provided by the device. This function shall be implemented if the `GetAccessProfile` service capability is true.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAccessProfileList Command

-   Name: `GetAccessProfileList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessProfileListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessProfileListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessProfile`: List of `AccessProfile` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessProfile AccessProfile [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAccessProfile command

This operation requests a list of `AccessProfile` items matching the given tokens.

This method shall be supported if the `GetAccessProfile` service capability is true. At least one token shall be specified.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAccessProfile Command

-   Name: `GetAccessProfile`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessProfileRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessProfile` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessProfileResponse` | This message contains:  
  
\- `AccessProfile`: List of `AccessProfile` items.  
  
`pacsaxis:AccessProfile AccessProfile [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetAccessProfile command

Add/update a list of `AccessProfile` items.

If `AccessProfile` items with the specified tokens already exist, they will be updated. If not, they shall be added.

If the `Token` field of any `AccessProfile` is empty, the service shall allocate a token for the `AccessProfile`.

All tokens shall be returned in the response.

SetAccessProfile Command

-   Name: `SetAccessProfile`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAccessProfileRequest` | This message contains:  
  
\- `AccessProfile`: The `AccessProfile` items to add/update.  
  
`pacsaxis:AccessProfile AccessProfile [1][unbounded]` |
| `SetAccessProfileResponse` | This message contains:  
  
\- `Token`: Tokens of the added/updated `AccessProfile` items.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidAccessProfileFault` |  |

#### RemoveAccessProfile command

Remove the specified `AccessProfile` items.

RemoveAccessProfile Command

-   Name: `RemoveAccessProfile`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAccessProfileRequest` | This message contains:  
  
\- `Token`: Tokens of the `AccessProfile` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveAccessProfileResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessProfile` is not found. |

### AuthenticationProfile operations

tac = [http://www.onvif.org/ver10/accesscontrol/wsdl](http://www.onvif.org/ver10/accesscontrol/wsdl)

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

Use authentication profile operations to manage `AuthenticationProfile` and `AuthenticationProfileInfo` items.

| Command | Description |
| --- | --- |
| `tac:GetAuthenticationProfileInfoList` | Get all `AuthenticationProfileInfo` items. |
| `tac:GetAuthenticationProfileInfo` | Get selected `AuthenticationProfileInfo` items. |
| `tac:GetAuthenticationProfileList` | Get all `AuthenticationProfile` items. |
| `tac:GetAuthenticationProfile` | Get selected `AuthenticationProfile` items. |
| `tac:SetAuthenticationProfile` | Add or update selected `AuthenticationProfile` items. |
| `tac:RemoveAuthenticationProfile` | Remove selected `AuthenticationProfile` items. |
| `pacsaxis:GetIdMatchOperators` | Get all `IdMatchOperator` items. |
| `pacsaxis:GetRuleOperators` | Get all `RuleOperator` items. |

#### GetAuthenticationProfileInfoList command

This operation requests a list of all `AuthenticationProfileInfo` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAuthenticationProfileInfoList Command

-   Name: `tac:GetAuthenticationProfileInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAuthenticationProfileInfoListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAuthenticationProfileInfoListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AuthenticationProfileInfo`: List of `AuthenticationProfileInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`tac:AuthenticationProfileInfo AuthenticationProfileInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAuthenticationProfileInfo command

This operation requests a list of `AuthenticationProfileInfo` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens. The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAuthenticationProfileInfo Command

-   Name: `tac:GetAuthenticationProfileInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetAuthenticationProfileInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `AuthenticationProfileInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAuthenticationProfileInfoResponse` | This message contains:  
  
\- `AuthenticationProfileInfo`: List of `AuthenticationProfileInfo` items.  
  
`tac:AuthenticationProfileInfo AuthenticationProfileInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### GetAuthenticationProfileList command

This operation requests a list of all `AuthenticationProfile` items provided by the device. An ONVIF compliant device which provides the Access Control service shall implement this method.

A call to this method shall return a `StartReference` when not all data is returned and more data is available. The reference shall be valid for retrieving the next set of data. See section [Retrieving system configuration](#retrieving-system-configuration).

The number of items returned shall not be greater than `Limit` parameter.

GetAuthenticationProfileList Command

-   Name: `tac:GetAuthenticationProfileList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAuthenticationProfileListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, less than one or higher than what the device supports, the number of items is determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAuthenticationProfileListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AuthenticationProfile`: List of `AuthenticationProfile` items.  
  
`xs:string NextStartReference [0][1]`  
`tac:AuthenticationProfile AuthenticationProfile [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client needs to start fetching from the beginning. |

#### GetAuthenticationProfile command

This operation requests a list of `AuthenticationProfile` items matching the given tokens.

An ONVIF compliant device which provides Access Control service shall implement this method.

The device shall ignore tokens it cannot resolve and shall return an empty list if there are no items matching specified tokens. The device shall not return a fault in this case.

If the number of requested items is greater than `MaxLimit`, a `TooManyItems` fault shall be returned.

GetAuthenticationProfile Command

-   Name: `tac:GetAuthenticationProfile`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAuthenticationProfileRequest` | This message contains:  
  
\- `Token`: Tokens of `AuthenticationProfile` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAuthenticationProfileResponse` | This message contains:  
  
\- `AuthenticationProfile`: List of `AuthenticationProfile` items.  
  
`tac:AuthenticationProfile AuthenticationProfile [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetAuthenticationProfile command

Set (adds or modifies) the supplied list of `AuthenticationProfile` items to the internal storage/database. If the token attribute is empty, a new unique token will be generated by the service. All supplied and generated tokens are returned.

SetAuthenticationProfile Command

-   Name: `tac:SetAuthenticationProfile`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAuthenticationProfileRequest` | This message contains:  
  
\- `AuthenticationProfile`: List of `AuthenticationProfile` items to set.  
  
`tac:AuthenticationProfile AuthenticationProfile [1][unbounded]` |
| `SetAuthenticationProfileResponse` | This message contains:  
  
\- `Token`: List of supplied and generated tokens`pt:ReferenceToken Token [0][unbounded]` |

#### RemoveAuthenticationProfile command

Remove the specified `AuthenticationProfile` items.

RemoveAuthenticationProfile Command

-   Name: `tac:RemoveAuthenticationProfile`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAuthenticationProfileRequest` | This message contains:  
  
\- `Token`: List of tokens for the `AuthenticationProfile` items to remove If list is empty, no profiles will be removed.  
  
`pt:ReferenceToken Token [0][unbounded]` |
| `RemoveAuthenticationProfileResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AuthenticationProfile` is not found. |

#### GetIdMatchOperators command

Returns the `IdMatchOperator` items supported by the service.

ONVIF mandates the following IdMatchOperators: `IdDataEqual`, `OperatorValueEqual`, `RemoteValidationEvent` .

-   `IdDataEqual`
    
    The `IdData` value in the request should be equal to the one in the `Credential.IdFields`. `result = (Request[IdDataName] == Credential.IdFields[IdDataName])`
    
-   `OperatorValueEqual`
    
    The `IdData` value in the request must have the same value as the `OperatorValue result = (Request[IdDataName] == OperatorValue)`. The `OperatorValueEqual` operator is typically used for REX requests, and `OperatorValue = "Active"` and `IdDataName = "REX"`
    
-   `RemoteValidationEvent`
    
    An `AccessControl/Request/ExternalConfirmation` event is sent and an external entity will do what ever action is needed.
    

ONVIF recommends the following IdMatchOperators: `RemoteValidationRequest` (if `ServiceCapabilities.RemoteService` is true) .

ONVIF reserves the following IdMatchOperators for future use: `MatchPhoto`, `MatchFingerprint`, `MatchIris`, `MatchVoice`, `VerifySignature`.

GetIdMatchOperators Command

-   Name: `pacsaxis:GetIdMatchOperators`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdMatchOperatorsRequest` | This message shall be empty. |
| `GetIdMatchOperatorsResponse` | This message contains:  
  
\- `IdMatchOperator`: List of supported `IdMatchOperator` items.  
  
`pacsaxis:IdMatchOperator IdMatchOperator [0][unbounded]` |

#### GetRuleOperators command

Returns the `RuleOperator` items supported by the service.

ONVIF mandates the following RuleOperators: `Authenticate`, `RequestEqual`, `OperatorValueEqual`, `RemoteValidationEvent`.

ONVIF recommends the following RuleOperators: `CredentialAttributeEqual`, `AccessProfileAttributeEqual`, `RemoteValidationRequest` (if `ServiceCapabilities.RemoteService` is true).

-   `Authenticate`
    
    Perform positive authentication according to what the `AuthenticationProfileList` specifies.
    
-   `RequestActionEqual`
    
    The `RequestAction` must match `OperatorValue[0] result = (Request.Action == Operatorvalue[0])`
    
-   `OperatorValueEqual`
    
    The `IdData` value in the request with the name `OperatorValue[0]` must have the same value as the `OperatorValue[1]` `result = (Request[[OperatorValue[0]] == OperatorValue[1])`. The `OperatorValueEqual` operator is typically used for REX requests, and `OperatorValue = "Active"` and `IdDataName = "REX"`.
    
-   `CredentialAttributeEqual`
    
    There must be one `Attribute` in the `Credential` that have the same Name as `OperatorValue[0]` and `Value` as `OperatorValue[1]` if that is specified.
    
-   `RemoteValidationEvent`
    
    An `AccessControl/Request/Authorization/Credential` event is sent and an external entity will do what ever action is needed.
    

If `ServiceCapabilities.RemoteService` is true the following must be supported:

-   `RemoteValidationRequest`
    
    The `RemoteService` referenced by the `OperatorValue` is queried with a`tac:ValidateRequest(Request, ..) call. [result, Reason] = RemoteService[OperatorValue].ValidateRequest(Request)`Request = Event notification `Source`, and `Data` fields.
    

GetRuleOperators Command

-   Name: `pacsaxis:GetRuleOperators`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetRuleOperatorsRequest` | This message shall be empty. |
| `GetRuleOperatorsResponse` | This message contains:  
  
\- `RuleOperator`: List of supported `RuleOperator` items.  
  
`pacsaxis:RuleOperator RuleOperator [0][unbounded]` |

### Access control management system

The PACSAxis service extends the Onvif PACS service so it is a full featured Access Control Management System (ACMS). It adds the concept of Users and Areas and a number of functions to access the database.

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### AccessControllerConfiguration data structure

The device and hardware configuration for an `AccessController`.

The following fields are available:

-   `token`
    
    `AccessController` Id to use for set, remove and usage.
    
-   `DeviceUUID`
    
    What device the `AccessController` is on.
    
-   `Configuration`
    
    Configuration for the `AccessController`.
    

#### MatchOperator data structure

Enum that specifies matching comparison operators. `Subset` and `Intersection` are for matching lists. `Subset` requires that all the items in the specified list must exist in the list in the matching object. `Intersection` requires that at least one of the items in the specified list must exist in the list of the matching object.

The following values are available:

-   `Equal`
-   `NotEqual`
-   `Subset`
-   `Intersection`

#### MatchRule data structure

A single rule for matching entity instances, specifying field name and operator to use when matching field value to existing entities in the system.

The following fields are available:

-   `Field`
    -   `Operator`

#### CredentialStatistics data structure

Statistics related to `Credential` items.

The following fields are available:

-   `NumberOfCredentials`
    
    Number of `Credential` items in the system.
    
-   `NumberOfDisabledCredentials`
    
    Number of disabled `Credential` items in the system.
    

#### GetAccessControllerConfigurationList command

This operation requests a list of all of `AccessControllerConfiguration` items provided by the device. An ONVIF compliant device which provides the Door Control service shall implement this method.

The returned list shall start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different `StartReference` parameters at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference` can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls, and may be changed by device in each call.

The number of items returned shall not be greater than `Limit` parameter. If `Limit` parameter is not specified by the client, the device shall assume it unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

GetAccessControllerConfigurationList Command

-   Name: `GetAccessControllerConfigurationList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessControllerConfigurationListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAccessControllerConfigurationListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AccessControllerConfiguration`: List of `AccessControllerConfiguration` items.  
  
`xs:string NextStartReference [0][1]`  
`pacsaxis:AccessControllerConfiguration AccessControllerConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client need to start fetching from the beginning. |

#### GetAccessControllerConfiguration command

This operation request a list of `AccessControllerConfiguration` items matching the given tokens.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned

GetAccessControllerConfiguration Command

-   Name: `GetAccessControllerConfiguration`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAccessControllerConfigurationRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessControllerConfiguration` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetAccessControllerConfigurationResponse` | This message contains:  
  
\- `AccessControllerConfiguration`: List of `AccessControllerConfiguration` items.  
  
`pacsaxis:AccessControllerConfiguration AccessControllerConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetAccessControllerConfiguration command

Add/update a list of `AccessControllerConfiguration` items.

If `AccessController` items with the specified tokens already exist, they will be updated. If not, they will be added.

If the `Token` field of any `AccessController` is empty, the service will allocate a token for the `AccessController`. All tokens are returned in the response.

SetAccessControllerConfiguration Command

-   Name: `SetAccessControllerConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAccessControllerConfigurationRequest` | This message contains:  
  
\- `AccessControllerConfiguration`: The `AccessControllerConfiguration` items to add/update.  
  
`pacsaxis:AccessControllerConfiguration AccessControllerConfiguration [1][unbounded]` |
| `SetAccessControllerConfigurationResponse` | This message contains:  
  
\- `Token`: The tokens of the added/updated `AccessController` items.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` |  |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotAllowed` |  |

#### RemoveAccessControllerConfiguration command

Remove the specified `AccessControllerConfiguration` items.

RemoveAccessControllerConfiguration Command

-   Name: `RemoveAccessControllerConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveAccessControllerConfigurationRequest` | This message contains:  
  
\- `Token`: Tokens of `AccessControllerConfiguration` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveAccessControllerConfigurationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `AccessController` not found. |

#### GetCredentialStatistics command

Get statistics related to the `Credential` items in the system.

GetCredentialStatistics Command

-   Name: `GetCredentialStatistics`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetCredentialStatisticsRequest` | This message shall be empty. |
| `GetCredentialStatisticsResponse` | This message contains:  
  
\- `CredentialStatistics`:`pacsaxis:CredentialStatistics CredentialStatistics [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:None` |  |

#### GetMasterDBState command

Returns the current state of the `MasterDB`.

GetMasterDBState Command

-   Name: `GetMasterDBState`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetMasterDBStateRequest` | This message shall be empty. |
| `GetMasterDBStateResponse` | This message contains:  
  
\- `NbrTotalPages`: Number of total pages in the database.:  
\- `NbrFreePages`: Number of free pages in the database.:  
\- `SizeOnDisk`: Number of bytes the database occupies on disk.  
  
`xs:int NbrTotalPages [1][1]`  
`xs:int NbrFreePages [1][1]`  
`xs:int SizeOnDisk [1][1]` |

#### ReOpenMasterDB command

Reopens the `MasterDB`, optionally: \* deleting the current database \* opening the new one in a specified path and \* enabling encryption with a specific key.

ReOpenMasterDB Command

-   Name: `ReOpenMasterDB`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `ReOpenMasterDBRequest` | This message shall be empty. |
| `ReOpenMasterDBResponse` | This message contains:  
  
\- `NbrTotalPages`: Number of total pages in the database.:  
\- `NbrFreePages`: Number of free pages in the database.:  
\- `SizeOnDisk`: Number of bytes the database occupies on disk.  
  
`xs:int NbrTotalPages [1][1]`  
`xs:int NbrFreePages [1][1]`  
`xs:int SizeOnDisk [1][1]` |

### Anti-passback

pacsaxis = [http://www.axis.com/vapix/ws/pacs](http://www.axis.com/vapix/ws/pacs)

#### ResetAntipassbackViolation command

Reset anti-passback for the specified credential(s). If the credential is currently not in anti-passback violation, nothing happens.

-   Name: `ResetAntipassbackViolation`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `ResetAntipassbackViolationRequest` | This message contains:  
  
\- `CredentialToken`: Token of Credential`pt:ReferenceToken CredentialToken [1][1]` |
| `ResetAntipassbackViolationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:NotFound` | Credential token |

#### ResetAllAntipassbackViolations command

Reset anti-passback for all credentials.

-   Name: `ResetAllAntipassbackViolations`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `ResetAllAntipassbackViolationsRequest` | This message shall be empty. |
| `ResetAllAntipassbackViolationsResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal`  
`ter:None` |  |

**AntipassbackData**

Anti-passback data describing one entry for `GetAntipassbackData` and `SetAntipassbackData`.

The following fields are available:

-   `CredentialToken`: Credential
-   `PassOkThreshold`: Anti-passback timer value (in seconds)
-   `CurrentArea`: Current area token
-   `ByTime`: Used to indicate `AntiPassbackMode`. False means Logical, True means TimedLogical.
-   `Violation`: Used to indicate whether monitoring has resulted in one or more violations.

#### GetAntipassbackDataList command

This operation requests a list of all of `AntipassbackData` items provided by the device. An ONVIF Profile A compliant device which provides the DoorControl service shall implement this method.

The returned list shall start with the item specified by a `StartReference`parameter. If not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference`is a device-internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different `StartReferences` at the same time, and these must live for a reasonable time so that clients are able to fetch complete datasets. An ONVIF-compliant client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference`can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference`shall be used as the `StartReference`parameter in successive calls, and may be changed by the device in each call.

The number of items returned shall not be greater than the `Limit`parameter. If `Limit` is not specified by the client, the device shall assume it to be unbounded. The number of returned elements is determined by the device and may be less than requested if the device has limited resources.

-   Name: `GetAntipassbackDataList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetAntipassbackDataListRequest` | This message contains:  
  
\- `Limit`: Maximum number of entries to return. If not specified, or greater than the device supports, the number of items shall be determined by the device.:  
\- `StartReference`: Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetAntipassbackDataListResponse` | This message contains:  
  
\- `NextStartReference`: `StartReference` to use in next call to get the following items. If absent, no more items to get.:  
\- `AntipassbackData`: List of `AntipassbackData` items.  
  
`xs:string NextStartReference [0][1]` `pacsaxis:AntipassbackData AntipassbackData [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal`  
`ter:InvalidStartReference` | **StartReference** is invalid or has timed out. Client needs to start fetching from the beginning. |

#### SetAntipassbackData command

-   Name: `SetAntipassbackData`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetAntipassbackDataRequest` | This message contains:  
  
\- `AntipassbackData`: List of `AntipassbackData` to set`pacsaxis:AntipassbackData AntipassbackData [1][unbounded]` |
| `SetAntipassbackDataResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:None` |  |