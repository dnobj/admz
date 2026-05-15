---
title: Device Configuration APIs
url: "https://developer.axis.com/vapix/device-configuration/device-configuration-apis/"
category: vapix
subcategory: device-configuration
sha256: 1effb484ceb9290be29ee728a4eaf95d16a50167a6e2afb77925b91b5deb53c3
scraped_at: "2026-01-09T15:18:44.205Z"
page_height: 35332
---

# Device Configuration APIs

Axis devices are provided with a large range of APIs to interact with. These APIs are designed with different approaches depending on their functionality and purpose. Starting with AXIS OS 11.8 and onward, Axis devices are provided with a new type of APIs for device administration (control and configuration) called Device Configuration APIs (DCA). These APIs are designed with a model-driven API development framework to create standardized APIs with a common look and feel.

This documentation will give an overview of how to understand and use DCAs. As mentioned above, DCAs are based on a model-driven API framework and described with an API definition language to express their structure and behavior.

-   The [API definition](#api-definition) section explains how the API definitions should be interpreted.
-   The [REST API](#rest-api) section explains how the API definitions are mapped to a JSON-based RESTful protocol.
-   The [Discovery](#discovery) section explains how clients and users can check available APIs and get information about them from the devices.

note

The Device Config API framework reached its `released` state with AXIS OS version 12.3. APIs utilizing this framework have their own maturity levels. This means that APIs that have not reached their `released` state are still under development and are subject to breaking changes and should not be used in production environments until they become `released`.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## API definition

The main goal of DCAs are to create APIs with similar look and feel that are easy to understand and use. To achieve this, DCAs are designed with a model-driven approach where the API structure and behavior are defined with an API description language explained in this section.

The definitions of APIs supported by a device are provided by the discovery module described in the [Discovery](#discovery) section.

The API definitions are provided in the JSON format. They contain some basic API information and the API structure. The APIs are organized with a hierarchical structure that uses entity, property, and action elements as shown in the example below.

Entity elements are containers for other elements used to structure a hierarchy. Entities can have properties, actions, and sub-entities.

-   Entities can either be singleton entities or entity collections.
-   Singleton entities represent a single entity instance, whereas entity collections represent a collection of repeating entities.
-   Properties are objects that refer to a piece of data.
-   Entities and properties have standard operations such as `SET`, `GET`, `ADD`, and `REMOVE`.
-   Action elements perform a task when triggered and can contain both input and output data.
-   An API always has a top root entity.

```bash
foo.v1 (Root Entity)|---subEntity (Entity)|   |--property1 (Property)|   |--property2 (Property)|   |--action1 (Action)|---subEntityCollection (Entity Collection)|   |--property1 (Property)|   |--property2 (Property)|   |--action1 (Action)|---property1 (Property)|---property2 (Property)|---action1 (Action)
```

## Top level structure

The APIs are defined in JSON format. The following JSON data shows the **top level** structure of an API definition.

```bash
{  "id": <string>,  "version": <string>,  "name": <string>,  "state": <string>,  "short\_description": <string>,  "description": <string>,  "export\_import": <boolean>,  "root\_entity": <object>,  "data\_types": <object>}
```

| JSON object/property | Description |
| --- | --- |
| `id=<string>` | The API identifier. |
| `version=<string>` | The full version of the API. Released APIs use **x.y.z** format, beta APIs use **x.0.0-beta.y**, and alpha APIs use **x.0.0-alpha.y**. |
| `name=<string>` | The user-friendly API name. |
| `state=<string>` | The API State. Can be **alpha**, **beta**, or **released**. |
| `short_description=<string>` | A short API description. |
| `export_import <boolean>` | If set to `true`, the API supports exporting and importing of configuration data. Defaults to `false`. |
| `root_entity=<object>` | This property is the object that describes the root entity, the top node of the API tree structure. The content of this object is described in the [Entity Definition](#entity-definition) section below. |
| `data_types=<object>` | Contains the API-specific data type definitions. Each data type is defined as a separate JSON property where the property name is the data type name. The type definition format is explained in the [Data Type Definition](#data-type-definition) section. |

note

`Export/Import` feature is a beta feature and is not enabled by default. Toggle the `Device Config Import/Export` feature flag to enable this feature. This feature was introduced with firmware version **12.5**.

### Entity Definition

Entities are used as containers for other property, entity, and action objects that create the API hierarchy. The following table describes the **entity** JSON object format:

```bash
"<entity name>": {  "short\_description": <string>,  "collection": <string enum>,  "key\_property": <string>,  "dynamic\_support": <boolean>,  "properties": {    "property1": <property object>,    "propertyN": <property object>  },  "entities": {    "entity1": <entity object>,    "entityN": <entity object>  },  "actions": {    "action1": <entity object>,    "actionN": <entity object>  },  "operations: {    "get": {},    "set": {      "fields": {        "optional": <array of fields>      }    },    "add": {      "roles": <array of roles>,      "fields": {        "required": <array of fields>,        "optional": <array of fields>      }    },    "remove": {        "roles": <array of roles>    }  }}
```

| JSON object/property | Description |
| --- | --- |
| `short_description=<string>` | A short entity description. |
| `collection=<string enum>` | Specifies if the entity is a singleton or a collection entity. The value is set to "**singleton**" for singleton and "**map**" for collection entities. |
| `key_property=<boolean>` | Specifies the key property that is only available for collection entities. The value contains the name of the property within the entity used to identify the items in the collection. |
| `dynamic_support=<boolean>` | Specifies if the entity is dynamically supported. If `true`, there will be another runtime meta property indicating if the entity is supported. The name of the meta property is `{entity name}_supported`. If the meta property is `false` the entity value will be `null`. |
| `properties` | Contains properties belonging to the entity. |
| `properties.<NAME>` | Each property of the entity is defined as a separate object. The structure of a property definition is explained below. |
| `actions` | Contains actions belonging to the entity. |
| `actions.<NAME>` | Each action of the entity is defined as a separate object. The structure of an action definition is explained below. |
| `entities` | This object contains sub-entities belonging to the entity. |
| `entities.<NAME>` | Each sub-entity is defined as a separate object. The structure of an entity definition is explained in this table. |
| `operations` | Specifies the operations that can be performed on the entity/entity collection. |
| `operations.get` | Specifies if the entity is gettable. If an entity has gettable properties/entities, the entity itself will become gettable. |
| `operations.set` | Specifies if the entity is settable. |
| `operations.set.fields.optional` | List of fields that can be used when setting the entity. |
| `operations.add` | Specifies if entities can be added to an entity collection. This operation is only available for collection entities. |
| `operations.add.roles` | List of roles that can perform the add operation. |
| `operations.add.fields.optional` | List of optional fields that can be used when adding an entity to a collection. |
| `operations.add.fields.required` | List of required fields that must be provided when adding an entity to a collection. |
| `operations.remove` | Specifies if entities can be deleted from an entity collection. This operation is only available for collection entities. |
| `operations.remove.roles` | List of roles that can perform the remove operation. |

## Property Definition

Properties are objects representing a piece of information. This information can be read-only, write-only, or read-write depending on the operations defined on the property. The following table describes the **property** JSON object format:

```bash
"<property name>": {  "short\_description": <string>,  "data\_type": <string>,  "nullable": <boolean>,  "dynamic\_support": <boolean>,  "export\_import": <boolean>,  "dynamic\_range\_constraints": <boolean>,  "dynamic\_value\_constraints": <boolean>,  "operations": {    "get": {      "roles": <array of roles>    },    "set": {      "roles": <array of roles>    }  }}
```

| JSON object/property | Description |
| --- | --- |
| `short_description=<string>` | A short property description. |
| `data_type=<string>` | The data type of the property. It defines the data format used for the SET and GET operations. The type can be either a built-in or API-specific defined type. Built-in types are string, integer, number, and boolean. API-specific types are part of the API definition, and described in the [Data Type Definition](#data-type-definition) section. |
| `nullable=<boolean>` | Specifies if the value can be null. |
| `dynamic_support=<boolean>` | Specifies if the property has dynamic support. If true, there will be another meta property indicating if the property is supported. The name of the meta property is `{property name}_supported`. If the meta property is false, the property value will be null and can't be set. |
| `export_import <boolean>` | If set to `true`, the property is part of import/export data. Secret information such as passwords will be excluded from exported data but can be included in the import data. |
| `dynamic_value_constraints=<boolean>` | Specifies if the property has dynamic value support. If true, there will be a meta property named `{property name}_values` with a list of valid values. The value of this meta property can be updated at runtime. |
| `dynamic_range_constraints =<boolean>` | Specifies is the property has dynamic range support. If true, there will be a meta property name `{property name}_ranges` with a list of range couples. The value of this meta property can be updated at runtime. |
| `operations=<object>` | This object contains supported operations by the property. |
| `operations.get=<object>` | Specifies if the GET operation is supported. The GET operation makes the property readable. |
| `operations.get.roles=<object>` | A list of roles that can perform the GET operation. The value can be a combination of **admin**, **operator**, and **viewer**. |
| `operations.set=<object>` | Specifies if the SET operation is supported. The SET operation makes the property writable. |
| `operations.set.roles=<string list>` | A list of roles that can perform the SET operation. The value can be a combination of **admin**, **operator**, and **viewer**. |

### Action Definition

Actions are objects that can be triggered to perform a specific task. The following table describes the **action** JSON object format:

```bash
"<action name>": {  "short\_description": <string>,  "request\_data\_type": <string>,  "response\_data-type": <string>,  "operations": {    "trigger": {      "roles": <array of role strings>    }  }}
```

| JSON object/property | Description |
| --- | --- |
| `short_description` | A short action description. |
| `request_data_type` | The data type of the input value provided in the action request. It can be a built-in or API- specific data type. |
| `response_data_type` | The data type of the output value returned in the action response. It can be a built-in or API-specific data type. |
| `operations` | Contains operations supported by the action. Only trigger operation is supported. |
| `operations.trigger` | Specifies if the TRIGGER operation is supported. TRIGGER operation makes the action callable. |
| `operations.trigger.roles` | A list of roles that can trigger the action. The value can be a combination of **admin**, **operator**, and **viewer**. |

### Data Type Definition
#### String

String data types are defined with the following JSON format:

```bash
"<type name>": {  "type": "string",  "minLength": <minimum length>,  "maxLength": <maximum length>,  "format": "data-time | time | date",  "pattern": "<regular expression>",  "enum": \["<value1>", "<value2>", ...\],  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to "**string**" for string types. |
| `minLength` _Optional_ | The minimum string length. |
| `maxLength` _Optional_ | The maximum string length. |
| `format` _Optional_ | The string format. Can be **"date-time"**, **"time"**, or **"date"**. |
| `pattern` _Optional_ | Regular expression (JavaScript (ECMA 262)) for string validation. |
| `enum` _Optional_ | Lists valid values. |
| `description` | A short data type description. |

#### Integer

Integer data types are defined with the following JSON format:

```bash
"<type name>": {  "type": "integer",  "minimum": <minimum value>,  "maximum": <maximum value>,  "enum": \[<int value1>, <int value2>, ...\],  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to **"integer"** for integer types. |
| `minimum` _Optional_ | The minimum integer value. |
| `maximum` _Optional_ | The maximum integer value. |
| `enum` _Optional_ | Lists of valid values. |
| `description` | A short data type description. |

#### Number

Number data types are used to define floating numbers, and are defined with the following JSON format:

```bash
"<type name>": {  "type": "number",  "minimum": <minimum value>,  "maximum": <maximum value>,  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to **"number"** for floating number types. |
| `minimum` _Optional_ | The minimum value. |
| `maximum` _Optional_ | The maximum value. |
| `description` | A short data type description. |

#### Boolean

Boolean data types are defined with the following JSON format:

```bash
"<type name>": {  "type": "boolean",  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to **"boolean"** for boolean types. |
| `description` | A short data type description. |

#### Array

Array data types are defined with the following JSON format:

```bash
"<type name>": {  "type": "array",  "items": {    "type": "<type name of array elements>",    "nullable": <boolean>  },  "minItems": <integer>,  "maxItems": <integer>,  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to "**array**" for array types. |
| `items.type` | The data type of the items this array can contain. |
| `items.nullable` | Specifies if this array can contain null values. |
| `minItems` _Optional_ | The minimum number of items this array can contain. |
| `maxItems` _Optional_ | The maximum number of items this array can contain. |
| `description` | A short data type description. |

#### Complex

Complex data types define data structures with fields, they are defined with the following JSON format:

```bash
"<type name>": {  "type": "object",  "fields":{    "<field name 1>": {      "type": "<type of the field>",      "nullable": <boolean>,      "description": "<description of the field>"    },    "<field name 2>": {...},    "<field name 3>": {...},    ...  },  "description": "<description of the type>"}
```

| JSON property | Description |
| --- | --- |
| `type` | This property is set to "**object**" for complex data types. |
| `fields` | Contains the fields of the complex type. |
| `fields.<field name>` | Specifies a field of the complex type. Each field is defined with a separate sub-property. |
| `fields.<field name>.type` | The field data type. |
| `fields.<field name>.nullable` | Specifies if the field can contain a null value. |
| `fields.<field name>.description` | A short description of the field. |
| `description` | A short data type description. |

### Object path

Each object (entity, property, and action) defined in an API can be identified with an object path. This path is used when referring to an object defined in the API structures. The path consists of object names separated with dots (.). The first two segments are always the API ID and version like `foo.v1`. They always point to the root entity of an API.

Items in an entity collection are identified by appending a key value encapsulated within `['']` to the entity name like `foo.v1.users['user1']`.

Here is a list of possible path combinations based on the given API example:

```bash
foo.v1 (Root Entity)|---users (Entity Collection)|   |---comment (Property)|   |---password (Property)|   |---username (Property)|---service (Entity)    |---enabled (Property)    |---restart (Action)foo.v1foo.v1.users (addressing the collection)foo.v1.users\['user1'\] (addressing an item in the collection)foo.v1.users\['user1'\].commentfoo.v1.users\['user1'\].passwordfoo.v1.users\['user1'\].usernamefoo.v1.servicefoo.v1.service.enabledfoo.v1.service.restart
```

### Operations

Operations define the possible interaction types with the APIs and its objects. How these operations are mapped to the network protocol are described in the [REST API Mapping](#rest-api) section. The following list describes the available operations.

-   `Get`: This operation is used to read the values of properties and entities. This operation can be used at property, entity, API, or device level.
    
-   `Set`: This operation is used to update the values of properties and entities.
    
-   `Add`: This operation is used to add a new entity instance to an entity collection.
    
-   `Remove`: This operation is used to delete an entity instance from an entity collection.
    
-   `Trigger`: This operation is used to execute an action defined in the API.
    
-   `Export`: This operation is used to export configuration data from an API. This data can later be used to import back. This operation can be used at API or device level.
    
-   `Import`: This operation is used to import API configuration data at both API- or device level. The import operation can be performed with partial data and, depending on the options, either the current values or default values can be used for the missing data.
    

## REST API

APIs are described with an API definition language that doesn't contain any information about the actual protocol and are exposed as REST APIs. Entities, properties, actions, and their operations are systematically mapped to URL endpoints and HTTP methods.

The device provides an OpenAPI specification and a rendered UI for each API. This specification contains the whole REST API mapping. The location of this specification and how to view it is described in the [Discovery](#discovery) section.

All APIs can be accessed securely with **TLS** support (HTTPS) and should be the preferred choice.

### URL Structure and Object Mapping

All APIs are located under `/config/rest/` endpoint with their own root URL. The API ID and major version are used to specify the starting point mapped to `/config/rest/<API_ID>/v<MAJOR_VER>[alpha | beta]`, where API\_ID is the API ID and MAJOR\_VER is the major version of the API. Released APIs have no suffixes, whereas alpha and beta state APIs have `alpha` and `beta` suffixes after the API major version.

**Examples**

```bash
https://my.device/config/rest/foo1/v1https://my.device/config/rest/foo2/v1alphahttps://my.device/config/rest/foo3/v1betahttp://my.device/config/rest/foo4/v2
```

**Root entity mapping**

The root entity is a singleton entity and is mapped to the API starting point `/config/rest/<API_ID>/v<MAJOR_VER>[alpha | beta]`.

```bash
http://my.device/config/rest/foo/v1http://my.device/config/rest/foo2/v1alphahttp://my.device/config/rest/foo3/v1beta
```

**Singleton entity mapping**

Singleton entities are mapped to a subpath segment below its parent entity path.

```bash
foo.v1.parentEntity.childEntityhttp://my.device/config/rest/foo/v1/parentEntity/childEntity
```

**Collection entity mapping**

Collection entities are mapped to a subpath segment below its parent entity path.

```bash
foo.v1.parentEntity.collectionEntityhttp://my.device/config/rest/foo/v1/parentEntity/collectionEntity
```

Items inside collection entities are mapped with the key value of the instance below the entity collection path.

```bash
foo.v1.parentEntity.collectionEntity\['item1'\]http://my.device/config/rest/foo/v1/parentEntity/collectionEntity/item1
```

**Property mapping**

Properties are mapped to a subpath segment below its parent entity path.

```bash
foo.v1.parentEntity.childEntity.somePropertyhttp://my.device/config/rest/foo/v1/parentEntity/childEntity/someProperty
```

**Action mapping**

Actions are mapped to a subpath segment below its parent entity path.

```bash
foo.v1.parentEntity.doSomethinghttp://my.device/config/rest/foo/v1/parentEntity/doSomething
```

**Global endpoints**

The following endpoints are API independent global endpoints:

_Global `get` endpoint_

Use the following endpoint to get all available API contents with a single request: `http://my.device/config/rest/$all`

_Global `export` endpoint_

Use the following endpoint to export data from all available APIs with a single request: `http://my.device/config/rest/$export`

_Global `import` endpoint_

Use the following endpoint to import data to multiple APIs with a single request: `http://my.device/config/rest/$import`

Object paths are converted to URLs by replacing the separator dot (`.`) and `['` `']` with `/`.

The following example lists all possible path combinations based on the given API structure:

```bash
foo.v1 (Root Entity)|---users (Entity Collection)|   |---comment (Property)|   |---password (Property)|   |---username (Property)|---service (Entity)    |---enabled (Property)    |---restart (Action)
```

```bash
foo.v1 -> /config/rest/foo/v1foo.v1.users -> /config/rest/foo/v1/usersfoo.v1.users\['user1'\] -> /config/rest/foo/v1/users/user1foo.v1.users\['user1'\].comment -> /config/rest/foo/v1/users/user1/commentfoo.v1.users\['user1'\].password -> /config/rest/foo/v1/users/user1/passwordfoo.v1.users\['user1'\].username -> /config/rest/foo/v1/users/user1/usernamefoo.v1.service -> /config/rest/foo/v1/servicefoo.v1.service.enabled -> /config/rest/foo/v1/service/enabledfoo.v1.service.restart -> /config/rest/foo/v1/service/restart
```

### Operation mapping

Operations are mapped to HTTP methods. Possible operations and their mappings are given below with request-response examples.

Examples given for the operations further below are using the following API structure:

```bash
foo.v1 (Root Entity)|---users (Entity Collection)|   |---comment (Property)|   |---password (Property)|   |---username (Property)|---service (Entity)    |---enabled (Property)    |---portNumber (Property)    |---restart (Action)
```

**Get a property**

The **get** operation for a property is mapped to the HTTP GET on the property endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/service/enabled"
```

```bash
GET /config/rest/foo/v1/service/enabledHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": true}
```

**Set a property**

The **set** operation for a property is mapped to the HTTP PATCH method on the property endpoint.

warning

AXIS OS versions 11.10 and prior use HTTP PUT instead of HTTP PATCH.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/foo/v1/users/user1/password" \\  --data '{  "data": : "!my-new-password!"}'
```

```bash
PATCH /config/rest/foo/v1/users/user1/passwordHost: <servername>Content-Type: application/json{  "data": : "!my-new-password!"}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

**Get an entity**

The **get** operation for a singleton entity is mapped to the HTTP GET method on the entity endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/service"
```

```bash
GET /config/rest/foo/v1/serviceHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "enabled": true,    "portNumber": 30001  }}
```

**Set an entity**

The **set** operation for a singleton entity is mapped to the HTTP PATCH method on the entity endpoint.

warning

AXIS OS versions 11.10 and prior use HTTP PUT instead of HTTP PATCH.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/foo/v1/service" \\  --data '{  "data": {    "enabled": true,    "portNumber": 30008  }}'
```

```bash
PATCH /config/rest/foo/v1/serviceHost: <servername>Content-Type: application/json{  "data": {    "enabled": true,    "portNumber": 30008  }}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

**Get all entity instances from an entity collection**

The **get** operation for an entity collection is mapped to the HTTP GET method on the entity collection endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/users"
```

```bash
GET /config/rest/foo/v1/usersHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": \[    {      "username": "username1",      "comment": "comment1"    },    {      "username": "username2",      "comment": "comment2"    }  \]}
```

**Get an entity instance from an entity collection**

The **get** operation for an entity instance in a collection is mapped to the HTTP GET method on the entity instance endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/users/user1"
```

```bash
GET /config/rest/foo/v1/users/user1Host: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    {      "username": "username1",      "comment": "comment1"    }  }}
```

**Set an entity instance in an entity collection**

The **set** operation for an entity instance in a collection is mapped to the HTTP PATCH method on the entity instance endpoint.

warning

AXIS OS versions 11.10 and prior use HTTP PUT instead of HTTP PATCH.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/foo/v1/users/user1" \\  --data '{  "data": {    "username": "username1",    "comment": "comment1"  }}'
```

```bash
PATCH /config/rest/foo/v1/users/user1Host: <servername>Content-Type: application/json{  "data": {    "username": "username1",    "comment": "comment1"  }}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

**Add an entity instance to an entity collection**

The **add** operation for an entity collection is mapped to the HTTP POST method on the entity collection endpoint.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/foo/v1/users" \\  --data '{  "data": {    "username": "username1",    "password": "!new-user-password!",    "comment": "some user comment"  }}'
```

```bash
POST /config/rest/foo/v1/usersHost: <servername>Content-Type: application/json{  "data": {    "username": "username1",    "password": "!new-user-password!",    "comment": "some user comment"  }}
```

Response:

```bash
201 OKContent-Type: application/json{  "status": "success"}
```

**Delete an entity instance from an entity collection**

The **remove** operation for an entity collection is mapped to the HTTP DELETE method on the entity instance endpoint.

-   curl
-   HTTP

```bash
curl --request DELETE \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/users/user1"
```

```bash
DELETE /config/rest/foo/v1/users/user1Host: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

**Trigger an action**

The **trigger** operation for an action is mapped to the HTTP POST method on the action endpoint.

warning

AXIS OS versions 11.10 and prior use HTTP PUT instead of HTTP POST.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/foo/v1/service/restart" \\  --data '{  "data": {}}'
```

```bash
POST /config/rest/foo/v1/service/restartHost: <servername>Content-Type: application/json{  "data": {}}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {}}
```

**Get API data**

The **get** operation for the root entity is mapped to the HTTP GET method on the API root endpoint. This request returns all data belonging to the API recursively.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1"
```

```bash
GET /config/rest/foo/v1Host: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "users":\[      {        "username": "username1",        "comment": "comment1"      },      {        "username": "username2",        "comment": "comment2"      }    \],    "service":{      "enabled": true,      "portNumber": 30001    }  }}
```

**Get data of all APIs**

The **get** operation for all APIs is mapped to the HTTP GET method on endpoint `/config/rest/$all`. This request returns data belonging to all APIs recursively.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/$all"
```

```bash
GET /config/rest/$allHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "ssh.v1":{...},    "param.v2":{...},    "cert.v1":{...}  }}
```

**Export API data**

If supported, the **export** operation for an API is mapped to the HTTP GET method on a special API root endpoint.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/foo/v1/$export"
```

```bash
GET /config/rest/foo/v1/$exportHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "users" : \[      "username": "username1",      "comment": "comment1"    \]  }}
```

note

Note that some properties tagged with `export_import: true` can be left out of the exported data. These properties can be "secrets" (such as passwords) that are possible to import but are not suitable to be included in exported data.

**Export all APIs**

Device level **export** operation is mapped to the HTTP GET method on `/config/rest/$export` endpoint. This operation returns `export` data from all APIs with a single request.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/config/rest/$export"
```

```bash
GET /config/rest/$exportHost: <servername>
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success",  "data": {    "foo.v1":{...},    "time.v2":{...},    "param.v2":{...},    ...  }}
```

**Import API data**

If supported, the `import` operation for an API is mapped to the HTTP PATCH method on a special API root endpoint. Any property tagged with `export_import: true` can be included in the request data provided as part of this operation. The `importType` option can be used to select the values for missing data. If `"merge"` is used existing API values will be kept. If `"default"` is used the API will be reset and default values will be used for missing data.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/param/foo/v1/$import" \\  --data '{  "data": {    "users" : \[      {        "username": "username1",        "comment": "comment1",        "password": "importedPassword"      }    \]  },  "options" : {    "importType": "merge"  }}'
```

```bash
PATCH /config/rest/param/foo/v1/$importHost: <servername>Content-Type: application/json{  "data": {    "users" : \[      {        "username": "username1",        "comment": "comment1",        "password": "importedPassword"      }    \]  },  "options" : {    "importType": "merge"  }}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

**Import multiple API data**

Device level **import** operation is mapped to the HTTP PATCH method on `/config/rest/$import` endpoint. This operation can be used to import data to multiple APIs with a single request. Refer to **Import API data** above for the details of `importType` option.

-   curl
-   HTTP

```bash
curl --request PATCH \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/config/rest/$import" \\  --data '{  "data": {    "foo.v1":{...},    "time.v2":{...},    "param.v2":{...},    ...  },  "options" : {    "importType": "merge"  }}'
```

```bash
PATCH /config/rest/$importHost: <servername>Content-Type: application/json{  "data": {    "foo.v1":{...},    "time.v2":{...},    "param.v2":{...},    ...  },  "options" : {    "importType": "merge"  }}
```

Response:

```bash
200 OKContent-Type: application/json{  "status": "success"}
```

#### Error handling

Client requests can fail for many reasons, such as validation, access rights, resource limitation, etc. If a request fails, a failure response with standard HTTP error status code and message will be returned. The payload will include a common error data structure in JSON format with a separate error code and a human-readable message.

The HTTP error response looks like this:

```bash
HTTP/1.1 <HTTP ERROR STATUS CODE> <HTTP ERROR STATUS MESSAGE>Content-Type: application/json{  "status": "error",  "error": {    "code": <integer error code>,    "message": "<user friendly error message>"  }}
```

## Discovery

As part of the DCA framework, devices are provided with a discovery module that can be used to get the available APIs and detailed information about them.

`/config/discover` is the entry point to the discovery module which provides all available information.

The following example shows how to get the discovery root document:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  http://my.device.com/config/discover
```

```bash
GET /config/discoverHOST: my.device.com
```

Response:

```bash
200 OKContent-Type: application/json{  "framework\_version":"1.0.0",  "apis":{...}}
```

`/config/discover/apis` endpoint provides a list of available APIs and details about them.

The following example shows how to get all available APIs and the details about them:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  http://my.device.com/config/discover/apis
```

```bash
GET /config/discover/apisHOST: my.device.com
```

Response:

```bash
200 OKContent-Type: application/json{  "ssh": {    "v1": {      "doc": "/config/discover/apis/ssh/v1/doc.md",      "doc\_html": "/config/web-ui/cu-doc.html?md-doc-loc=/config/discover/apis/ssh/v1/doc.md",      "model": "/config/discover/apis/ssh/v1/model.json",      "rest\_api": "/config/rest/ssh/v1beta",      "rest\_openapi": "/config/discover/apis/ssh/v1/openapi.json",      "rest\_ui": "/config/web-ui/swagger-ui/?url=/config/discover/apis/ssh/v1/openapi.json",      "state": "beta",      "version": "1.0.0-beta.1"    },    "v2": {...},    ...  },  "cert": {    "v1": {      "doc": "/config/discover/apis/cert/v1/doc.md",      "doc\_html": "/config/web-ui/cu-doc.html?md-doc-loc=/config/discover/apis/cert/v1/doc.md",      "model": "/config/discover/apis/cert/v1/model.json",      "rest\_api": "/config/rest/cert/v1beta",      "rest\_openapi": "/config/discover/apis/cert/v1/openapi.json",      "rest\_ui": "/config/web-ui/swagger-ui/?url=/config/discover/apis/cert/v1/openapi.json",      "state": "beta",      "version": "1.0.0-beta.1"    },    "v2": {...},    ...  },  ...}
```

Each API is identified by its ID and major version. In the previous example, ssh and cert APIs had single major versions. It is possible to have multiple major versions of an API at the same time.

`/config/discover/apis/<API_ID>` provides a list of all available major versions of the same API, where `<API_ID>` it the API ID.

The following example shows how to get all the available versions of a specific API:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  http://my.device.com/config/discover/apis/ssh
```

```bash
GET /config/discover/apis/sshHOST: my.device.com
```

Response:

```bash
200 OKContent-Type: application/json{  "ssh": {    "v1": {...},    "v2": {...},    ...  }}
```

`/config/discover/apis/<API_ID>/v<MAJOR_VERSION>` provides information of a specific API version, where `<API_ID>` it the API ID and `<MAJOR_VERSION>` is the major version of the API.

The following example shows how to get a specific version of an API:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  http://my.device.com/config/discover/apis/ssh/v1
```

```bash
GET /config/discover/apis/ssh/v1HOST: my.device.com
```

Response:

```bash
200 OKContent-Type: application/json{  "doc": "/config/discover/apis/ssh/v1/doc.md",  "doc\_html": "/config/web-ui/cu-doc.html?md-doc-loc=/config/discover/apis/ssh/v1/doc.md",  "model": "/config/discover/apis/ssh/v1/model.json",  "rest\_api": "/config/rest/ssh/v1beta",  "rest\_openapi": "/config/discover/apis/ssh/v1/openapi.json",  "rest\_ui": "/config/web-ui/swagger-ui/?url=/config/discover/apis/ssh/v1/openapi.json",  "state": "beta",  "version": "1.0.0-beta.1"}
```

The following table describes the API JSON object used in the previous examples:

| JSON property | Description |
| --- | --- |
| `model` | A link to the API definition. The content format of this file is described in the[API definition](#api-definition) section. |
| `version` | The full API version. Follows the Semantic Versioning format, where released APIs use `x.y.z` format, beta APIs use `x.0.0-beta.y`, and alpha APIs use `x.0.0-alpha.y`. |
| `state` | The API state . Can be alpha, beta or released. |
| `doc` | Link to the API documentation, presented in the Markdown format. This file contains simplified documentation of the API. |
| `doc_html` | Location for the rendered API documentation. |
| `rest_api` | API endpoint. This is the location of the root entity of the API. |
| `rest_openapi` | The OpenAPI specification for the API. This specification describes all the available endpoints, the methods, and the request/response payloads. |
| `rest_ui` | Location of the UI that renders the corresponding OpenAPI specification. This UI can be used as a supporting tool to interact with the API. |