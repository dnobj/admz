---
title: Param API
url: "https://developer.axis.com/vapix/device-configuration/param-api/"
category: vapix
subcategory: device-configuration
sha256: 55c3d95693e7559f557f9747c2abcfa2ad750a79eb4001795af9f787733695e3
scraped_at: "2026-01-09T15:18:58.161Z"
page_height: 12509
---

# Param API

The VAPIX® Param API enables users to read, export, and import `/axis-cgi/param.cgi` parameters. It has a dynamic structure that is updated during runtime and is based on the `/axis-cgi/param.cgi` content. This document focuses on API usage and how the `/axis-cgi/param.cgi` parameters are mapped into the API.

## Overview

This API is based on the **Device Configuration API** framework. For guidance on how to use these APIs, please refer to [Device Configuration APIs](/vapix/device-configuration/device-configuration-apis/).

warning

This API is in **BETA** stage. The API is provided for testing purposes and is subject to backward-incompatible changes, including modifications to functionality, behavior, and availability. Please don't use in production environment.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

### Mapping parameters & parameter groups to properties and entities

This API is dynamically structured at runtime and based on the `/axis-cgi/param.cgi` parameters. Changes to parameters, such as removal, addition, or modification of parameters or parameter groups, can be used to restructure the API.

#### Parameters

Parameters in `/axis-cgi/param.cgi` map to string-type properties in the API structure, since all parameter values are strings in `/axis-cgi/param.cgi`.

```bash
/axis-cgi/admin/param.cgi?action=listdefinitions&group=root.HTTPS&listformat=xmlschema<group name="root">    <group name="HTTPS">        <parameter name="Enabled" value="yes" securityLevel="7706" niceName="Enabled">            <type>                <bool true="yes" false="no" />            </type>        </parameter>    </group></group>
```

The above example shows a parameter definition in `/axis-cgi/param.cgi`. The parameter `Enabled` maps to a string typed property with the same name. The `securityLevel` defines the operation types and access rights. Writable parameters are tagged as export/import properties. Below is the corresponding mapping.

```bash
Simplified sample from the API definition:root\_entity:    entities:        HTTPS:            properties:                Enabled:                    data\_type: string                    export\_import: true                    operations:                        get:                            access\_rights: \["viewer", "operator", "admin"\]
```

A get request to the root entity will result in the following response sample:

```bash
{    "data": {        "HTTPS": {            "Enabled": "yes"        }    }}
```

#### Groups

Non-dynamic parameter groups map to singleton entities in the API structure. Non-dynamic groups have a single instance and contains sub-parameters and sub-groups. Sub-parameters map to sub-properties and sub-groups map to sub-entities. Dynamic groups are described further down in the next section. The following example shows the group `root.Brand` and its parameters:

```bash
/axis-cgi/admin/param.cgi?action=list&group=root.Brandroot.Brand.Brand=AXISroot.Brand.ProdFullName=AXIS P5655-E PTZ Dome Network Cameraroot.Brand.ProdNbr=P5655-Eroot.Brand.ProdShortName=AXIS P5655-Eroot.Brand.ProdType=PTZ Dome Network Cameraroot.Brand.ProdVariant=root.Brand.WebURL=http://www.axis.com
```

The mapping of the above example would be like the following simplified API structure:

```bash
Simplified sample from the API model:root\_entity:    entities:        Brand:            properties:                Brand: { ... }                ProdFullName: { ... }                ProdNbr: { ... }                ProdShortName: { ... }                ProdType: { ... }                ProdVariant: { ... }                WebURL: { ... }
```

A get request to the root entity will result in the following response sample:

```bash
{    "data": {        "Brand": {            "Brand": "AXIS",            "ProdFullName": "AXIS MyExampleDevice",            "ProdNbr": "ExampleDevice",            "ProdShortName": "Example",            "ProdType": "ExampleType",            "ProdVariant": "",            "WebURL": "http://www.axis.com"        }    }}
```

#### Dynamic groups

Dynamic groups have multiple instances that hold sub-parameters and sub-groups. They can be identified from the parameter path. The instances of dynamic groups are named with the capitalized initial group letter followed by a number. The following example shows the instances of the dynamic group `IOPort` and its sub-parameters and sub-groups:

```bash
/axis-cgi/admin/param.cgi?action=list&group=root.IOPORTroot.IOPort.I0.Configurable=yesroot.IOPort.I0.Direction=inputroot.IOPort.I0.Usage=root.IOPort.I0.Input.Name=Port 1root.IOPort.I0.Input.Trig=closedroot.IOPort.I0.Output.Active=closedroot.IOPort.I0.Output.Button=noneroot.IOPort.I0.Output.DelayTime=0root.IOPort.I0.Output.Mode=bistableroot.IOPort.I0.Output.Name=Port 1root.IOPort.I0.Output.PulseTime=0root.IOPort.I1.Configurable=yesroot.IOPort.I1.Direction=inputroot.IOPort.I1.Usage=root.IOPort.I1.Input.Name=Port 2root.IOPort.I1.Input.Trig=closedroot.IOPort.I1.Output.Active=closedroot.IOPort.I1.Output.Button=noneroot.IOPort.I1.Output.DelayTime=0root.IOPort.I1.Output.Mode=bistableroot.IOPort.I1.Output.Name=Port 2root.IOPort.I1.Output.PulseTime=0
```

Dynamic groups maps to entity collections in the API structure. The same name is used and followed by a `Collection` suffix. Sub-parameters and sub-groups are added to the entity collection. Additionally, a key property is added for `instance` identification. This key property is named `groupId`. The mapping of the above example would be like the following simplified API structure:

```bash
Simplified sample from the API model:root\_entity:entities:    IOPortCollection:        collection: map        key\_property: groupId        properties:            groupId:                data\_type: string            Configurable: { ... }            Direction: { ... }            Usage: { ... }        entities:            Input:                properties:                    Name: { ... }                    Trig: { ... }            Output:                properties:                    Active: { ... }                    Button: { ... }                    DelayTime: { ... }                    Mode: { ... }                    Name: { ... }                    PulseTime: { ... }
```

A `get` request to the root entity results in the following response sample:

```bash
{    "data": {        "IOPortCollection": \[            {                "Configurable": "yes",                "Direction": "input",                "groupId": "I0",                "Input": {                    "Name": "Input 1",                    "Trig": "closed"                },                "Output": {                    "Active": "closed",                    "Button": "none",                    "DelayTime": "0",                    "Mode": "bistable",                    "Name": "Output 1",                    "PulseTime": "0"                },                "Usage": ""            },            {                "Configurable": "yes",                "Direction": "input",                "groupId": "I1",                "Input": {                    "Name": "Input 2",                    "Trig": "closed"                },                "Output": {                    "Active": "closed",                    "Button": "none",                    "DelayTime": "0",                    "Mode": "bistable",                    "Name": "Output 2",                    "PulseTime": "0"                },                "Usage": ""            }        \]    }}
```

#### Dynamic and static groups

Some groups are dynamic and contains 'instances' with parameters and sub-groups. They can also be non-dynamic with parameters and sub-groups at the level of the group itself. The following example shows a case like this:

```bash
/axis-cgi/admin/param.cgi?action=list&group=root.Audioroot.Audio.DSCP=0root.Audio.DuplexMode=fullroot.Audio.MaxListeners=20root.Audio.MaxTransmitters=1root.Audio.NbrOfConfigs=1root.Audio.ReceiverBuffer=120root.Audio.ReceiverTimeout=1000root.Audio.A0.Enabled=noroot.Audio.A0.HTTPMessageType=singlepartroot.Audio.A0.Name=root.Audio.A0.NbrOfChannels=1root.Audio.A0.Source=0
```

In this example the `Audio` group is both a dynamic and a non-dynamic group, and maps to the following simplified API structure:

```bash
Simplified sample from the API model:root\_entity:    entities:        AudioCollection:            collection: map            key\_property: groupId            properties:                groupId:                    data\_type: string                Enabled: { ... }                HTTPMessageType: { ... }                Name: { ... }                NbrOfChannels: { ... }                Source: { ... }        Audio:            properties:                DSCP: { ... }                DuplexMode: { ... }                MaxListeners: { ... }                MaxTransmitters: { ... }                NbrOfConfigs: { ... }                ReceiverBuffer: { ... }                ReceiverTimeout: { ... }
```

A `get` request to the root entity will result in the following response sample:

```bash
{    "data": {        "Audio": {            "DSCP": "0",            "DuplexMode": "full",            "MaxListeners": "20",            "MaxTransmitters": "1",            "NbrOfConfigs": "1",            "ReceiverBuffer": "120",            "ReceiverTimeout": "2500"        },        "AudioCollection": \[            {                "groupId": "A0",                "Enabled": "no",                "HTTPMessageType": "singlepart",                "Name": "",                "NbrOfChannels": "1",                "Source": "0"            }        \]    }}
```

## Use cases

Refer to this sample model when using the upcoming API use cases.

```bash
root\_entity:    entities:        AudioCollection:            collection: map            key\_property: groupId            properties:                groupId:                    data\_type: string                    export\_import: true                    operations:                        get:                            access\_rights: \["viewer", "admin"\]                Enabled:                    data\_type: string                    export\_import: true                    operations:                        get:                            access\_rights: \["viewer", "admin"\]    Audio:        properties:            DSCP:                data\_type: string                export\_import: true                operations:                    get:                        access\_rights: \["viewer", "admin"\]            MaxListeners:                data\_type: string                operations:                    get:                        access\_rights: \["viewer", "admin"\]
```

### Get parameters

The `get` operation can be used to retrieve both a single parameter or a group with its parameters and sub-groups recursively. Only readable parameters are returned.

Example of retrieving a single parameter:

```bash
{    "request": {        "operation": "GET",        "path": "param.v2.Audio.MaxListeners"    },    "response": {        "status": "success",        "data": "5"    }}
```

Group retrieval example:

```bash
{    "request": {        "operation": "GET",        "path": "param.v2.Audio"    },    "response": {        "status": "success",        "data": {            "DSCP": 0,            "MaxListeners": "5"        }    }}
```

### Export parameters

Writable parameters are mapped as export/import properties. These properties are marked with `export_import:true` in the API definition and can be retrieved by performing an export request.

Data export example for the sample API:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/param/v2beta/$export"
```

```bash
GET /config/rest/param/v2beta/$exportHost: <servername>
```

```bash
200 OKContent-Type: application/json{    "status": "success",    "data": {        "Audio": {            "DSCP": 0        },        "AudioCollection": \[            {                "groupId": "0",                "Enabled": "yes"            }        \]    }}
```

Note that `MaxListeners` is missing from the exported data. This is because it does not have `export_import: true`, since it is not a writable parameter.

### Import parameters

Use an import request to set properties tagged as import/export. The import request can handle multiple properties in one request. A common use case is to import all or some settings exported from a device to another device.

All given properties in the import request will be applied. Those that fail will be reported in the warning section of the response. Import type has no effect on this API, only the provided properties will be updated for both default and merge `importType` options.

Parameters belonging to dynamic groups are handled differently compared to `/axis-cgi/param.cgi`. The dynamic group instances must exist before they can be updated with `/axis-cgi/param.cgi`. This API automates this process and creates the dynamic groups before setting the values.

Import data example:

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/param/v2beta/$import" \\  --data '{    "data": {        "Audio": {            "DSCP": 0        },        "AudioCollection": \[            {                "groupId": "0",                "Enabled": "no"            },            {                "groupId": "1",                "Enabled": "yes"            }        \]    }}'
```

```bash
PATCH /config/rest/param/v2beta/$importHost: <servername>Content-Type: application/json{    "data": {        "Audio": {            "DSCP": 0        },        "AudioCollection": \[            {                "groupId": "0",                "Enabled": "no"            },            {                "groupId": "1",                "Enabled": "yes"            }        \]    }}
```

```bash
200 OKContent-Type: application/json{    "status": "success"}
```

## API definition
### Structure

```bash
param.v2 (Root Entity)
```

### Entities

**param.v2 {#param.v2}**

-   Description: Root entity containing param.cgi parameters.
-   Type: Singleton
-   Operations
    -   Get
-   Attributes
    -   Dynamic Support: No

_Properties_ This entity has no properties.

_Actions_ This entity has no actions.