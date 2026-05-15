---
title: Intercom service
url: "https://developer.axis.com/vapix/intercom/intercom-service/"
category: vapix
subcategory: intercom
sha256: 700df23caf919d1c8679032f4a8548614184445dc7e0d5372bd93c9f3dedefa2
scraped_at: "2026-01-09T15:19:13.973Z"
page_height: 95112
---

# Intercom service

The Intercom service API showcases the different ways to configure and manage the core functionality of the intercom devices.

## Overview

The intercom service provides the API endpoint `/vapix/intercom` as well as the websockets endpoints `ws://` and `wss://` at `/vapix/intercomws`. The websocket endpoint can be used to both issue API commands and to initiate event notifications in the JSON format.

The intercom service includes the following methods:

-   Configure the access control integration protocol to request access to any compatible device. This can be done by using either OSDP, Wiegand or VAPIX reader connection.
-   Enabling card types.
-   Allowing third-party integrators to configure and control card data processing using the access control integration protocol.
-   Configuring the user interface behavior and API to control the feedback.

The intercom service also defines a number of events for real-time monitoring:

-   Card swipe events using `tns1:Device/tnsaxis:Intercom/RFID`
-   PIN entry events using `tns1:Device/tnsaxis:Intercom/KeyPin`
-   Aggregated call state events.

Non normative enums are used to describe possible values and their meaning, together with capabilities listing the supported values on a particular product or device software.

### Identification

-   **Property**: `Properties.API.Intercom.Intercom="yes"`
-   **Property**: `Properties.API.Intercom.Version="1.1"`
-   **API Discovery**: `id=intercom-api`
-   **API Discovery**: `id=intercom-reader` (for products with a reader)

### Terminology

| Term | Description |
| --- | --- |
| AccessPoint | Represents a reader or reader-door mapping. |
| ACU | Access Control Unit, i.e. external access control device or door controller, such as AXIS A1001 and AXIS A1601. |
| RFID | Radio Frequency IDentification. The radio technology used in cards, tags and fobs for identification. |
| Mask | Used together with readers to disable/filter data from being used with the configured access control integration protocol. |
| MIFARE® | A brand named RFID-based solution for storing credential information on smart cards and keyfobs (RFC tags). |
| MIFARE® DESFire® | A brand named RFID-based solution for storing credential information on smart cards and keyfobs (RFC tags). |
| Non-normative Enum | An Enum whose values are used as strings to enable future extensions. The type documents the possible values and their meaning, but a capability indicates the supported values, and an ID string type is used instead of the actual enum type when appropriate. |
| OSDP | Open Supervised Device Protocol. A protocol on top of a 2-wire RS-485 used between the access control system (ACU) and a reader. |
| PIN | Personal Identification Number. The number used to authenticate a user, commonly used with an RFID card. |
| Tag | Another term for a smartcard or keyfob used to store credential information. |
| Wiegand | A protocol widely used in access control systems between a reader and controller (ACU). |

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

The majority of examples uses pseudocode to illustrate the intended flow of requests to the Intercom API service, while returning data is shown in JavaScript Object Notation (JSON).

### Syntax

API calls can be encoded in either JSON or the key-value format referred to as "simple". Multiple JSON formats are supported, such as JSONRPC 2.0 and Google JSON API.

**JSON**

The original raw JSON format has the following form:

Request ver. 1

```bash
{  "<function>": {    <arguments>  }}
```

This JSON request can also be made by putting the function-method in the URL: `/vapix/intercom/<function>`:

Request ver. 2

```bash
{  <arguments>}
```

Response

```bash
{  <result>}
```

**JSONRPC 2.0**

The JSONRPC 2.0 format has the following form:

Request

```bash
{  "jsonrpc": "2.0",  "method": "<function>",  "params": {    <arguments>  },  "id": <id>}
```

Response

```bash
{  "jsonrpc": "2.0",  "result": {    <result>  },  "id": <id>}
```

**Google JSON API**

The Google JSON API has a similar structure to JSONRPC 2.0, but uses different parameters. For example, `"jsonrpc": "2.0"` is replaced by `"apiVersion":`, `"result"` is changed to `"data"` and `"id"` is replaced by `"context"`.

Request

```bash
{  "apiVersion": "1.0",  "method": "<function>",  "params": {    <arguments>  },  "context": <id>}
```

Response

```bash
{  "apiVersion": "1.0",  "data": {    <result>  },  "context": <id>}
```

**Simple**

The so called "simple" format flattens the structure to `key=value` strings, where each level in a structure is separated by an underscore `_` when encoding the key.

-   Boolean values are encoded as either `true` or `false`, while the NULL value is encoded as `null`.
-   String values are URL-encoded and may start and end with quotation marks.
-   Array keys are encoded as `_index_` starting from 0.

Character sets are neither converted nor validated by the intercom service, but `UTF-8` should be used to ensure compatibility with most system.

### Simple cURL example

This example shows a couple of configurations requested via cURL.

**cURL JSON**

Request

```bash
$ curl --digest "http://root:pass@192.168.0.90/vapix/intercom" -s -d '{"GetConfiguration":{}}'> {>   "Configuration": {>     "Version": "1.0",>     "CallTriggersEnabled": true,>     "CallByNumbersEnabled": true,>     "DefaultCallByNumberSIPAccountId": "",>     "CardReaderConfiguration": {>       "Protocol": "None",>       "CardTypes": \[ "MIFARE\_Classic",.. \],>       "WiegandConfiguration": {>         "nbrOfLEDPins": 0,>         "beeper": false,>         "beeperPin": "I3",>         "LED1Pin": "I1",>         "LED2Pin": "I2",>         "LEDColor0": "red",>         "LEDColor1": "green",>         "LEDColor00": "off",>         "LEDColor01": "green",>         "LEDColor10": "red",>         "LEDColor11": "amber",>         "keypressFormat": "FourBit">       },>       "OSDPConfiguration": {>         "OSDPAddress": 0>       }>     }>   }> }
```

**cURL Simple**

Request

```bash
$ curl --digest "http://root:pass@192.168.0.90/vapix/intercom?format=simple&action=GetConfiguration"# or$ curl --digest "http://root:pass@192.168.0.90/vapix/intercom/GetConfiguration?format=simple"> Configuration\_Version="1.0"> Configuration\_CallTriggersEnabled=true> Configuration\_CallByNumbersEnabled=true> Configuration\_CardReaderConfiguration\_Protocol="None"> Configuration\_CardReaderConfiguration\_CardTypes\_0="EM4X02"> Configuration\_CardReaderConfiguration\_CardTypes\_1="HITAG\_1\_S"> Configuration\_CardReaderConfiguration\_CardTypes\_2="HITAG\_2"> Configuration\_CardReaderConfiguration\_CardTypes\_3="EM4X50"> Configuration\_CardReaderConfiguration\_CardTypes\_4="ISOFDX\_B"> Configuration\_CardReaderConfiguration\_CardTypes\_5="HID\_PROX"> Configuration\_CardReaderConfiguration\_CardTypes\_6="AWID"> Configuration\_CardReaderConfiguration\_CardTypes\_7="MIFARE\_Classic"> Configuration\_CardReaderConfiguration\_CardTypes\_8="ISO15693"> Configuration\_CardReaderConfiguration\_CardTypes\_9="HID\_ICLASS"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_nbrOfLEDPins=0> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_beeper=false> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_beeperPin="I3"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LED1Pin="I1"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LED2Pin="I2"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor0="red"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor1="green"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor00="off"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor01="green"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor10="red"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_LEDColor11="amber"> Configuration\_CardReaderConfiguration\_WiegandConfiguration\_keypressFormat="FourBit"> Configuration\_CardReaderConfiguration\_OSDPConfiguration\_OSDPAddress=0> ...
```

### Errors

A faulty request, such as missing required information or containing parameters the service doesn’t recognize will always return an error response, typically done with an `HTTP 400 Bad request` code unless the fault was over a websocket connection.

The error response also contains additional information. Typical `FaultCodes` for this API might be `ter:TagMismatch`, `ter:InvalidArgVal` or `ter:InvalidArgs`.

TagMismatch error

```bash
{    "Fault": "env:Sender",    "FaultCode": "ter:TagMismatch",    "FaultSubCode": null,    "FaultReason": "Tag mismatch",    "FaultMsg": "JSON parse error: axdsapi:CardReaderConfiguration - Unhandled field: 'WrongField' at pos 66 {WrongField.."}
```

Simple format error

```bash
Fault="env:Sender"FaultCode="ter:TagMismatch"FaultSubCode=nullFaultReason="Tag mismatch"FaultMsg="JSON parse error: axdsapi:CardReaderConfiguration - Unhandled field: 'WrongField' at pos 66 {WrongField.."
```

JSON formatted InvalidArgVal error

```bash
{    "Fault": "env:Sender",    "FaultCode": "ter:InvalidArgVal",    "FaultSubCode": null,    "FaultReason": "Invalid argument",    "FaultMsg": "BeeperVolume should be <= 100"}
```

Google JSON formatted InvalidArgVal error

```bash
{    "apiVersion": "1.0",    "context": "context1602748757.259225",    "error": {        "code": -32700,        "message": "BeeperVolume should be <= 100",        "errors": \[            {                "domain": "env:Sender",                "reason": "Invalid argument",                "message": "BeeperVolume should be <= 100",                "location": "ter:InvalidArgVal"            }        \]    }}
```

JSONRPC2.0 formatted InvalidArgVal error

```bash
{    "jsonrpc": "2.0",    "error": {        "code": -32700,        "message": "BeeperVolume should be <= 100",        "data": {            "Fault": "env:Sender",            "FaultCode": "ter:InvalidArgVal",            "FaultSubCode": null,            "FaultReason": "Invalid argument",            "FaultMsg": "BeeperVolume should be <= 100"        }    },    "id": "id1602750260"}
```

### Configure reader integration protocols

Use this example to build the RFID reader together with an external Access control system. Please note that you need to configure which protocol to use if the controller doesn’t connect to the device and subscribes to integration events on its own.

The following code showcase two different ways to configure the OSDP reader integration protocol:

```bash
{  get\_response = intercom.GetConfiguration()  config = get\_response\['CardReaderConfiguration'\]  config\['Protocol'\] = 'OSDP'  intercom.UpdateConfiguration(CardReaderConfiguration=config)}
```

```bash
{    "UpdateConfiguration": {        "Configuration": {            "CardReaderConfiguration": {                "Protocol": "OSDP"            }        }    }}
```

### Configure card types

Use this example to configure the card types by setting the `CardTypes` list in the `CardReaderConfiguration`. This should contain the desired card formats. Card formats not used by a site should be disabled, both from a security and performance perspective.

To find out what Card types that are supported on your device, you need to check `GetSupportedTagTypes` or `GetServiceCapabilities`.

See [Enumeration: CardTypeNames](#enumeration-cardtypenames) enum for a list of possible values.

The following code is used to check for supported cards and configure the Card types:

```bash
{  supported\_cards = intercom.GetSupportedTagTypes()  config = intercom.GetConfiguration()  enabledcards = config.CardReaderConfiguration.CardTypes  // Remove all LowFrequency cards from enabledcards list:  for cardtype in supported\_cards {    if (cardtype.Category == 'LowFrequency') {      enabledcards.remove(cardtype.Name)    }  }  // Set the modified list of enabled CardTypes  config.CardReaderConfiguration.CardTypes = enabledcards  intercom.UpdateConfiguration(config)}
```

The following codes showcases how you can change the card types. Both uses the `UpdateConfiguration` method, while the second one also includes the use of an URL:

```bash
POST to /vapix/intercom{  "UpdateConfiguration": {    "Configuration": {      "CardReaderConfiguration": {        "CardTypes": \["MIFARE\_Classic"\]      }    }  }}
```

```bash
POST to /vapix/intercom/UpdateConfiguration{  "Configuration": {    "CardReaderConfiguration": {      "CardTypes": \["MIFARE\_Classic"\]    }  }}
```

### Configure PIN setting

Use this example to change the Pin settings and timeout. To do this, you need to call the `UpdateConfiguration` method and include the fields you wish to modify.

Configure the PIN settings

```bash
{// Start with an empty config object:  config = {}  config.CardReaderConfiguration = {}  config.CardReaderConfiguration.PinConfiguration = {}// Only update these fields:  config.CardReaderConfiguration.PinConfiguration.pinLength = 6  config.CardReaderConfiguration.PinConfiguration.pinTimeout = 20  intercom.UpdateConfiguration(config)}
```

Change the PIN length and timeout

```bash
{    "UpdateConfiguration": {        "Configuration": {            "CardReaderConfiguration": {                "PinConfiguration": {                    "pinLength": 6,                    "pinTimeout": 20                }            }        }    }}
```

### Third party integration

Use this example to configure your device so that a third party application can validate a card swipe before the card data gets sent over a configured reader protocol.

This involves:

-   Configuring the device to mask the internal reader. This is done by issuing a `UpdateConfiguration` or `RegisterReader` call.
-   Subscribing to the RFID events and calling `GetLastTag` and `GetLastKeySequence` to retrieve sensitive data.
-   Calling the `InjectTag`, `InjectKeySequence` and `SetUiFeedback` methods.

The following code showcases how to validate the RFID data before sending it to a controller:

```bash
setup()  {    if (fixed) {      config = {}      config.CardReaderConfiguration.RegisteredReaderConfiguration.ReaderIds = \["ADP"\]      config.CardReaderConfiguration.RegisteredReaderConfiguration.Policy = "Fixed"      intercom.UpdateConfiguration(config)    }    else    {      Timeout = intercom.RegisterReader(Readerid="ADP", DisableInternalReader = true, UnmaskIfLost = false)    }    // Subscribe to events, using RTSP metadata streaming, ONVIF PullPoint subscription or    // events in JSON over websocket:    // Using websocket endpoint /vapix/intercomws:    device.websocket.connect("/vapix/intercomws")    // Subscribe to event topics and functions: Send axev:subscribe with style = "ttMessage",    // topics=\["Device/Intercom/RFID", "Device/Intercom/KeyPin"\],    // functions = \["axev:notify", "axdsapi:SetUiFeedback"\]    device.websocket.send('{      "apiVersion": "1.0",      "method": "axev:subscribe",      "params": {        "style": "ttMessage",        "functions": \[          "axev:notify",          "axdsapi:SetUiFeedback"        \],        "topics": \["Device\\/Intercom\\/RFID", "Device\\/Intercom\\/KeyPin"\]      },      "id": "firstsubscribe"    }')    device.websocket.on\_message\_handler = handle\_websocket\_message  }  handle\_websocket\_message(json\_msg)  {    msg = json2object(json\_msg)    if (msg.method == 'axev:notify')    {      for notification in msg.params.notifications {        if (notification.topic == "tns1:Device/tnsaxis:Intercom/RFID") {        // Only process if Source with name Source is Internal        source = SimpleItem\_lookup(notification.data.Source.SimpleItem, "Source")        if (source == "Internal") {          UID = SimpleItem\_lookup(notification.data.Data.SimpleItem, "UID")          // Take snapshot, lookup UID on own database or whatever is needed          result = partner\_validation(UID)          // result is expected to contain a combination of InjectTag, InjectKey and feedback          if (result.injecttag) {            // Card is valid, call InjectTag, based on the notification, possibly with a prefix.            BitCount = SimpleItem\_lookup (notification.data.Data.SimpleItem, "BitCount")            // Possibly prefix the UID with additional hex data, e.g. 0xFACE            if (result.prefix != "") {              UID = result.prefix + UID              BitCount = BitCount + strlen(result.prefix)\*4            }            send\_InjectTag("ADP", UID, BitCount)          }          if (result.injectkey != '') {            // injectkey should end with # to make it a PIN code, or C to issue a call.            send\_InjectKeySequence("ADP", result.injectkey)          }          if (result.feedback) {            // Send some feedback, e.g. 'AccessDenied'            send\_feedback(result.feedback)          }        }      }    }  }}send\_InjectTag(external\_readerid, UID, BitCount){  device.websocket.send('{    "apiVersion": "1.0",    "method": "InjectTag",    "params": {      "Tag": {        "TagUid": "' + UID + '",        "BitCount": ' + BitCount + ',        "ReaderId": "' + external\_readerid + '"      }    },    "id": "clientInjectTag"  }')}send\_InjectKeySequence(source, keys){  device.websocket.send('{    "apiVersion": "1.0",    "method": "InjectKeySequence",    "params": {      "KeySequence": "' + keys + '",      "Source": "' + source + '"    },    "id": "clientInjectKeySequence"  }')}send\_feedback(feedback){  device.websocket.send('{    "apiVersion": "1.0",    "method": "SetUiFeedback",    "params": {      "highlevelFeedbacks": \['+feedback+'\]    },    "id": "clientSetUiFeedback"  }')}
```

By using `UpdateConfiguration`, you will be able to change `RegisteredReaderConfiguration` with Google JSON:

```bash
POST to /vapix/intercom (or send to ws://ip/vapix/intercomws){  "apiVersion": "1.0",  "method": "UpdateConfiguration",  "params": {    "Configuration": {      "CardReaderConfiguration": {        "RegisteredReaderConfiguration": {          "ReaderIds": \["ADP"\],          "Policy": "Fixed"        }      }    }  },  "context": "updateRegisteredReaderConfig"}
```

By using this code, you will be able to use the RFID event notification over a websocket:

```bash
{    "apiVersion": "1.0",    "method": "axev:notify",    "params": {        "notifications": \[            {                "topic": "tns1:Device\\/tnsaxis:Intercom\\/RFID",                "timestamp": "2020-10-04T11:30:08.885643Z",                "data": {                    "Source": {                        "SimpleItem": \[                            {                                "Name": "Source",                                "Value": "Internal"                            }                        \]                    },                    "Data": {                        "SimpleItem": \[                            {                                "Name": "UIDFormat",                                "Value": "Raw"                            },                            {                                "Name": "TagType",                                "Value": "MIFARE\_Classic"                            },                            {                                "Name": "BitCount",                                "Value": "32"                            },                            {                                "Name": "UID",                                "Value": "C0DE1234"                            }                        \]                    }                }            }        \]    }}
```

## API specifications
### Common data types

**Id**

Identifies a structure.

Base type: String (`maxLength=64, minLength=0`)

**Name**

The type used for names of logical and/or physical entities.

Base type: String (`maxLength=64, minLength=0`)

**Attribute**

An attribute containing a name and a value.

```bash
{    "Name": "anAttributeName",    "Value": "anAttributeValue"}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The attribute name. |
| `Value` | String | The value of the attribute. |

**AttributeInfo**

Contains the attribute description.

```bash
{    "Name": "anAttributeName",    "Value": "anAttributeValue",    "Type": "string"}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The attribute name. |
| `Value` | String | The attribute value. |
| `Type` | String | The attribute type (bool = boolean, int = integer, string) |

### Card reader specific types
#### CardType

Description of a card type. See [Service capabilities](#service-capabilities) for a complete list of cards supported by the products.

```bash
{  "Name": "MIFARE\_Classic",  "DisplayName": "MIFARE Classic",  "Category": "HighFrequency",  "DataSources": \[ "CSN", "Data",.. \]}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | Id | The card type identifier. See [Enumeration: CardTypeNames](#enumeration-cardtypenames) for possible values. |
| `DisplayName` | Id | The UI-friendly name. |
| `Category` | Id | The category. See [Enumeration: CardTypeCategory](#enumeration-cardtypecategory) for possible values. |
| `DataSources` | Id array | The list of data sources that are supported. See [Enumeration: CardDataSources](#enumeration-carddatasources) for possible values. |

#### Enumeration: CardTypeCategory

The different categories a `CardType` may have.

| Value | Description |
| --- | --- |
| `HighFrequency` | 13.56 MHz card type |
| `LowFrequency` | 125 kHz card type |

#### Enumeration: CardTypeNames

The known card types.

See [ServiceCapabilities](#servicecapabilities) or use `GetSupportedTagTypes` for a list of card types your device supports.

| Value | Description |
| --- | --- |
| `EM4X02` | EM4x02 |
| `HITAG_1_S` | HITAG 1/HITAG S |
| `HITAG_2` | HITAG 2 |
| `EM4X50` | EM4x50 |
| `T55X7` | T55x7 |
| `ISOFDX_B` | ISO FDX-B |
| `EM4026` | EM4026 |
| `HITAG_U` | HITAG U |
| `EM4305` | EM4305 |
| `HID_PROX` | HID Prox |
| `ISOHDX_TIRIS` | ISO HDX TIRIS |
| `COTAG` | Cotag |
| `IOPROX` | ioProx |
| `INDALA` | Indala |
| `NEXWATCH` | NexWatch |
| `AWID` | AWID |
| `GPROX` | G-Prox |
| `PYRAMID` | Pyramid |
| `KERI` | Keri |
| `DEISTER` | Deister |
| `CARDAX` | Cardax |
| `NEDAP` | Nedap |
| `PAC` | PAC |
| `IDTECK` | IDTECK |
| `ULTRAPROX` | ULTRAPROX |
| `ICT` | ICT |
| `ISONAS` | ISONAS |
| `MIFARE` | Generic MIFARE® |
| `MIFARE_Classic` | MIFARE Classic® |
| `MIFARE_DESFire` | MIFARE® DESFire® |
| `MIFARE_Plus` | MIFARE Plus® |
| `MIFARE_Ultralight` | MIFARE Ultralight® |
| `ISO14443B` | ISO 14443-B |
| `ISO15693` | ISO 15693 |
| `LEGIC` | LEGIC |
| `HID_ICLASS` | HID iClass |
| `FELICA` | FeliCa |
| `SRX` | SRX |
| `NFC_P2P` | NFC P2P |
| `BLE` | Bluetooth Low Energy |
| `TOPAZ` | TOPAZ |
| `CTS` | CTS |

#### Enumeration: KeypressOutputFormat

The possible values that describes how the PIN is formatted when it is sent to the access control device.

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `FourBit` | PIN "1234" becomes 0x1 0x2 0x3 0x4 on the wire. |
| `EightBitZeroPadded` | PIN "1234" becomes 0x01 0x02 0x03 0x04 on the wire. |
| `EightBitInvertPadded` | PIN "1234" becomes 0xE1 0xD2 0xC3 0xB4 on the wire. |
| `Wiegand26` | PIN is encoded in Wiegand26 format with an 8 bit facility code and a 16 bit ID. |
| `Wiegand34` | PIN is encoded in Wiegand34 format with a 16 bit facility code and a 16 bit ID. |
| `Wiegand37` | PIN is encoded in Wiegand37 format (H10302) with a 35 bit data ID. |
| `Wiegand37FacilityCode` | PIN is encoded in Wiegand37 format (H10304) with a 16 bit facility code and a 19 bit ID. |

#### Enumeration: CardOutputFormat

The possible values that describes how card data is formatted when it is sent to the access control device.

See [Service capabilities](#service-capabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `Raw` | The card data is transmitted as is. |
| `Wiegand26` | The card data is encoded in Wiegand26 format with an 8 bit facility code and a 16 bit ID. |
| `Wiegand34` | The card data is encoded in Wiegand34 format with a 16 bit facility code and a 16 bit ID. |
| `Wiegand37` | The card data is encoded in Wiegand37 format (H10302) with a 35 bit data ID. |
| `Wiegand37FacilityCode` | The card data is encoded in Wiegand37 format (H10304) with a 16 bit facility code and a 19 bit ID. |
| `Custom` | Use the `OutputFormatConfiguration` option as described in [CustomOutputFormatConfiguration](#customoutputformatconfiguration). |

#### Enumeration: FacilityCodeOverrideMode

The possible modes of overriding the facility code.

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `Auto` | Overrides will not be performed and creates a facility code from the input data auto detection: Either use the card’s original facility code or forge it from excess bits of a card number. This is the default option. |
| `Optional` | Uses the facility code from the input data, otherwise overrides with a configured value (optional). |
| `Override` | Always overrides with a specified `FacilityCode`. |

#### Enumeration: ParityType

The possible parity bit types.

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `None` | Parity bit does not exist. |
| `Even` | The parity bit is even. |
| `Odd` | The parity bit is odd. |
| `Fix0` | The parity bit is always zero. |
| `Fix1` | The parity bit is always one. |

#### CustomOutputFormatConfiguration

Defines the custom parameters for when the `cardFormat` is "Custom". This part defines the format if no other value in the `CardOutputFormat` can be used.

```bash
{    "facilityCodeSize": 8,    "cardNumberSize": 16,    "startParity": "Even",    "startParityBits": 12,    "stopParity": "Odd",    "stopParityBits": 12}
```

| Field | Type | Description |
| --- | --- | --- |
| `facilityCodeSize` | Integer | The size of the facility code. |
| `cardNumberSize` | Integer | The size of the card number. |
| `startParity` | Id | The start parity bit type. See [Enumeration: ParityType](#enumeration-paritytype) for possible values. Default value is `None`.See `SupportedParityType` in [ServiceCapabilities](#servicecapabilities) for values supported by your product. |
| `startParityBits` | Integer | The number of data bits used to calculate the start parity, counted from the first data bit. |
| `stopParity` | Id | The stop parity bit type. See [Enumeration: ParityType](#enumeration-paritytype) for possible values. Default value is `None`.See `SupportedParityType` in [ServiceCapabilities](#servicecapabilities) for values supported by your product. |
| `stopParityBits` | Integer | The number of data bits used to calculate the stop parity, counted backwards from the last data bit. |

#### OutputFormatConfiguration

Defines how the card data is configured and sent to the output.

See [ServiceCapabilities](#servicecapabilities) for values supported by `cardFormat` and `cardFacilityCodeOverrideMode`.

```bash
{  "cardFormat": "Raw",  "cardFacilityCodeOverrideMode": "Auto",  "cardFacilityCode": 0,  "Custom": {    CustomOutputFormatConfiguration  }}
```

| Field | Type | Description |
| --- | --- | --- |
| `cardFormat` | Id | How the card data is formatted. See [Enumeration: CardOutputFormat](#enumeration-cardoutputformat) for possible values. See `SupportedCardOutputFormat` in [ServiceCapabilities](#servicecapabilities) for supported values. The default value is `Raw`, which means that all fields that follows after this one is disregarded. |
| `cardFacilityCodeOverrideMode` | Id | See [Enumeration: FacilityCodeOverrideMode](#enumeration-facilitycodeoverridemode) for supported values. Default value is `Auto`. See `SupportedFacilityCodeOverrideMode` in [ServiceCapabilities](#servicecapabilities) for supported values. |
| `cardFacilityCode` | Integer | The facility code to override the card in cases where the override mode is set to either Optional or Override. The maximum value depends on the card format that is selected: 255 for **Wiegand26 (8 bits)**, 65535 for **Wiegand34** and **Wiegand37FacilityCode (16 bits)**. |
| `Custom` | See [CustomOutputFormatConfiguration](#customoutputformatconfiguration) | The custom parameters in cases were `cardFormat` is "Custom". |

#### Enumeration: IOPinName

The possible names for the general IO pins.

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `I1` | I/O 1 |
| `I2` | I/O 2 |
| `I3` | I/O 3 |
| `I4` | I/O 4 |

#### Enumeration: AccesscontrolIntegrationProtocol

The different ways that the device can communicate with an access control system.

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `None` | No protocol selected. |
| `IPAccess` | VAPIX Reader over IP, see [Enumeration: IPIntegrationProtocol](#enumeration-ipintegrationprotocol) for more information. |
| `OSDP` | OSDP over RS485. |
| `Wiegand` | Wiegand. |

#### Enumeration: ColorName

The different color strings that may be supported by your device.

Colors may also be specified in #RRGGBB format for arbitrary color (if supported by the device).

See [ServiceCapabilities](#servicecapabilities) for values supported by your product.

| Value | Description |
| --- | --- |
| `off` | Off |
| `red` | Red |
| `green` | Green |
| `blue` | Blue |
| `amber` | Amber |
| `cyan` | Cyan |
| `magenta` | Magenta |
| `white` | White |

#### WiegandConfiguration

Defines the configuration used for the Wiegand output to change the LED and beeper. All fields are optional and will keep their existing value if nothing is set.

```bash
{    "nbrOfLEDPins": 3,    "beeper": true,    "beeperPin": "I1",    "LED1Pin": "I2",    "LED2Pin": "I3",    "pulseWidth": 40,    "pulseInterval": 2000,    "frameInterval": 25000,    "LEDColorDefault": "off",    "LEDColor0": "red",    "LEDColor1": "green",    "LEDColor00": "off",    "LEDColor01": "red",    "LEDColor10": "green",    "LEDColor11": "amber",    "keypressFormat": "FourBit",    "keypressFacilityCode": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `nbrOfLEDPins` | Integer | The number of LED control pins that is connected to the access control system. 0, 1 or 2 are supported. |
| `beeper` | Boolean | True if a beeper control line is connected to the device. |
| `beeperPin` | Id | The I/O input pin that the beeper is connected to. See [Enumeration: IOPinName](#enumeration-iopinname) for additional information. |
| `LED1Pin` | Id | The I/O input pin that the LED1 is connected to (normally green or red/green). See [Enumeration: IOPinName](#enumeration-iopinname) for additional information. |
| `LED2Pin` | Id | The I/O input pin that the LED2 is connected to (normally red). See [Enumeration: IOPinName](#enumeration-iopinname) for additional information. |
| `pulseWidth` | Integer | The time of the data pulse, measured in µs. `Min: 20, Max: 100, Default: 40`. |
| `pulseInterval` | Integer | The time between data pulses, measured in µs. `Min: 200, Max: 20000, Default: 2000`. |
| `frameInterval` | Integer | The minimum time between data transfers, measured in µs. `Min: 20000, Max: 1000000, Default: 25000`. |
| `LEDColorDefault` | Id | The color that is shown if no wires are connected (i.e. `nbrOfLEDPins=0`). See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor0` | Id | The color when 1 LED control wire is connected and the state is 0, typically red. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor1` | Id | The color when 1 LED control wire is connected and the state is 1, typically green. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor00` | Id | The color when 2 LED control wires are connected and the state is 00, typically off. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor01` | Id | The color when 2 LED control wires are connected and the state is 01, (LED1 is 1 and LED2 is 0), typically red. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor10` | Id | The color when 2 LED control wires are connected and the state is 10, (LED1 is 0 and LED2 is 1), typically green. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `LEDColor11` | Id | The color when 2 LED control wires are connected and the state is 11, (LED1 is 1 and LED2 is 1), typically amber. See [Enumeration: ColorName](#enumeration-colorname) for accepted colors or use #RRGGBB format for arbitrary colors. |
| `keypressFormat` | Id | The PIN code format. See [Enumeration: KeypressOutputFormat](#enumeration-keypressoutputformat) and [Service capabilities](#service-capabilities) for additional information and supported values. Default value is `FourBit`. |
| `keypressFacilityCode` | Integer | The facility code to override the PIN code (default is 0). Maximum value depends on the keypress format: 255 for Wiegand26 (8 bits), 65535 for Wiegand34 and Wiegand37FacilityCode (16 bits). |

#### OSDPConfiguration

Defines the configuration options for the Open Supervised Device Protocol (OSDP).

```bash
{    "OSDPAddress": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `OSDPAddress` | Integer | The OSDP PD address (i.e. client). Min=0, Max=126, Default=0. |

#### PinConfiguration

Defines the configuration options for PIN length and timeout. The PIN configuration should match the one set in the Access Control Unit.

```bash
{    "pinLength": 4,    "pinTimeout": 10}
```

| Field | Type | Description |
| --- | --- | --- |
| `pinLength` | Integer | The number of digits in the PIN code. Min=0 (PIN is disabled), Max=32, Default=4. This parameter should match the Access control unit configuration. |
| `pinTimeout` | Integer | The number of seconds that should pass before the device goes back to idle mode when no PIN is received. Min=1, Max=60, Default=10. This parameter should match the Access control unit configuration. |

#### RequestAccessConfiguration

Defines the configuration options for the Axis Request Access protocol. The name is derived from Target and Source unless present in the AccessPoint. See [IPAccessConfiguration](#ipaccessconfiguration) for additional information.

```bash
{    "Name": "Door - Reader Entrance A8207",    "Id": "e6608ad31a480904f9646e936cc8e86a",    "Address": "a1601.example.com",    "AccessControllerToken": "Axis-00408c184be0+AccessController",    "SourceToken": "Axis-00408c184be0:1581679815.571711000",    "TargetToken": "Axis-00408c184be0:1581679815.080670000",    "AccessPointToken": "Axis-00408c184be0:1581679823.844035000"}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The Nicename of the Access point. |
| `Id` | String | The internal ID of the `RequestAccess` (Access point) configuration. |
| `Address` | String | The address used to access the correct controller. |
| `AccessControllerToken` | String | The access controller token that should be accessed. |
| `SourceToken` | String | The source token that should be used (Reader / IdPoint). |
| `TargetToken` | String | The target token that should be used (Door). |
| `AccessPointToken` | String | The AccessPoint token that should be used. |

#### Enumeration: IPIntegrationProtocol

The supported IP integration protocols. See [IPAccessConfiguration](#ipaccessconfiguration) for additional information.

| Value | Description |
| --- | --- |
| `None` | No protocol is selected. |
| `RequestAccess` | Axis RequestAccess. |
| `RemoteActivity` | Axis Indicated RemoteActivity. |

#### Enumeration: IPAccessScheme

The supported IP integration transport protocols.

| Value | Description |
| --- | --- |
| `https` | Encrypted HTTP. |
| `http` | Unencrypted HTTP. |

#### IPAccessConfiguration

Configuration options for IP based access control integration. See [IP Access configuration](#ip-access-configuration) for additional information.

```bash
{  "Scheme": "https",  "Address": "a1601.example.com",  "Username": "a8207userOnA1601",  "Password": "a8207passwordOnA1601",  "VerifyCertificate": true,  "IPProtocol": "RemoteActivity",  "RequestAccessConfiguration": {    RequestAccessConfiguration  }}
```

| Field | Type | Description |
| --- | --- | --- |
| `Scheme` | String | The scheme that should be used (optional). See [Enumeration: IPAccessScheme](#enumeration-ipaccessscheme) for additional information. |
| `Address` | String | The address that access the controller. A typical address is `hostname[:port]`. |
| `Username` | String | The username. |
| `Password` | String | The password. |
| `VerifyCertificate` | Boolean | An option to disable the certificate verification. Default value is true. |
| `IPProtocol` | String | The protocol that should be used (optional). See [Enumeration: IPIntegrationProtocol](#enumeration-ipintegrationprotocol) for additional information. |
| `RequestAccessConfiguration` | [RequestAccessConfiguration](#requestaccessconfiguration) | The protocol specific configuration. |

#### CompatibilityConfiguration

Contains the card reader compatibility options, which makes it possible to extend the configuration options without changing the configuration structures.

```bash
{  "CompatibilityConfigs": \[    {      Attribute    },..  \]}
```

| Field | Type | Description |
| --- | --- | --- |
| `CompatibilityConfigs` | Attribute array | A list of compatibility configuration values. See [ServiceCapabilities](#servicecapabilities) for additional information. |

#### CardReaderConfiguration

Configurations for the card reader functionality, such as the integration protocol, what card types to enable, etc. All fields are optional, meaning that their current value will be kept unless specified in a `SetConfiguration` or `UpdateConfiguration` request.

```bash
{  "Protocol": "Wiegand",  "CardTypes": \[    "EM4X02",    ..  \],  "WiegandConfiguration": {    WiegandConfiguration  },  "OSDPConfiguration": {    OSDPConfiguration  },  "PinConfiguration": {    PinConfiguration  },  "IPAccessConfiguration": {    IPAccessConfiguration  },  "CompatibilityConfiguration": {    CompatibilityConfiguration  },  "CardDataConfigs": \[    {      "CardDataConfig    },    ..  \],  "RegisteredReaderConfiguration": {    RegisteredReaderConfiguration  },  "OutputFormat": {    OutputFormatConfiguration  },  "SensitiveRFIDEventEnabled": false,  "SensitivePINEventEnabled": false}
```

| Field | Type | Description |
| --- | --- | --- |
| `Protocol` | Id | The protocol that should be used. See [Enumeration: AccesscontrolIntegrationProtocol](#enumeration-accesscontrolintegrationprotocol) for additional information. |
| `CardTypes` | Id array | A list of card types that should be accepted. See [Enumeration: CardTypeNames](#enumeration-cardtypenames) for capabilities and possible values. |
| `WiegandConfiguration` | [WiegandConfiguration](#wiegandconfiguration) | The Wiegand configuration. |
| `OSDPConfiguration` | [OSDPConfiguration](#osdpconfiguration) | The OSDP configuration. |
| `PinConfiguration` | [PinConfiguration](#pinconfiguration) | The PIN configuration. |
| `IPAccessConfiguration` | [IPAccessConfiguration](#ipaccessconfiguration) | The `IPAccessConfiguration`. |
| `CompatibilityConfiguration` | [CompatibilityConfiguration](#compatibilityconfiguration) | Compatibility flags. |
| `CardDataConfigs` | [CardDataConfig](#carddataconfig) array | Lists different ways to extract `CardData` (optional). |
| `RegisteredReaderConfiguration` | [RegisteredReaderConfiguration](#registeredreaderconfiguration) | Specifies how the clients (typically an application or 3rd party solutions) are allowed to use `InjectTag`. |
| `OutputFormat` | [OutputFormatConfiguration](#outputformatconfiguration) | Specifies how the card data should be formatted. |
| `SensitiveRFIDEventEnabled` | Boolean | True if the actual UID and card number is present in events. |
| `SensitivePINEventEnabled` | Boolean | True if the actual PIN is present in events. |

#### TagUidType

The type used for the UID of a tag.

Base type: String (`maxLength=64, minLength=0`)

#### TagPresentedInfo

Describes the tag together with the metadata.

```bash
{    "TagUid": "CA4DDA7A",    "BitCount": 32,    "TagType": "MIFARE\_Classic",    "ReaderId": "Internal",    "Age": 1,    "FacilityCode": "",    "CardNumber": "",    "Format": "Raw",    "Masked": true}
```

| Field | Type | Description |
| --- | --- | --- |
| `TagUid` | TagUidType | The UID of the tag. ASCII encoded hex value (32 bytes max). Data is right justified. |
| `BitCount` | Integer | The number of bits in TagUid. |
| `TagType` | Id | Identifies the tag type, e.g. `MIFARE_Classic`. See [Enumeration: CardTypeNames](#enumeration-cardtypenames) for additional information. |
| `ReaderId` | Id | The ID of the reader. "Internal" is the default name for the built-in reader, but this can be set with an `InjectTag` call. |
| `Age` | Integer | How much time has passed since the tag was presented, measured in seconds. |
| `FacilityCode` | Id | The facility code in decimals. Should be less than 64 bit number. Null or "" means that the facility code is unavailable. |
| `CardNumber` | Id | The card number in decimals. Should be less than 64 bit number. Null or "" means that the card number is unavailable. |
| `Format` | Id | The detected card data format. Default value is Raw. See `CardOutputFormat` and `SupportedCardOutputFormat` in [ServiceCapabilities](#servicecapabilities) for supported values. |
| `Masked` | Boolean | True if the reader is masked. Default value is false. |

#### CardData

Defines the structure that holds the data chunk extracted from an RFID card.

Uses:

-   Returns the value of the [GetCardData](#getcarddata) function.
-   Parameter of the [InjectTag](#injecttag) function.

```bash
{    "name": "string",    "bitCount": 0,    "byteCount": 0,    "data": "hexBinary"}
```

| Field | Type | Description |
| --- | --- | --- |
| `name` | String | The name of the data chunk, copied from the corresponding configuration. See [CardDataConfig](#carddataconfig). |
| `bitCount` | Integer | The number of valuable data bits, its size not necessarily rounded to whole bytes. The valuable data is left-justified. |
| `byteCount` | Integer | The number of bytes that holds this data chunk (`bitCount <= byteCount * 8` |
| `data` | hexBinary | The data chunk. |

#### Enumeration: CardDataSources

Defines the possible data sources. All card types supports CSN (Card serial number), but other sources may be possible depending on the card type.

| Value | Description |
| --- | --- |
| `CSN` | Uses Card serial number (CSN) as the input. |
| `SecureId` | Uses the secure ID as the input, e.g. iClass PAC bits or MIFARE DESFire SecureId when configured for Random Id. |
| `Data` | Uses data retrieved as the input. |

#### CardDataConfig

Defines a configuration describing how to extract a specific data chunk from an RFID card. It contains both addresses required to find the data and the credentials to access them. Please note that credentials are sensitive data and should be handled with care.

Uses:

-   A [CardReaderConfiguration](#cardreaderconfiguration) field specifying pre-defined ways to extract data.
-   A [GetCardData](#getcarddata) parameter allowing data extracting with no pre-configuration and without storing sensitive credentials in [CardReaderConfiguration](#cardreaderconfiguration).

```bash
{  "name": "referring",  "cardType": "EM4X02",  "datSource": "CSN",  "enabled": true,  "required": true,  "useAsUid": true,  "offsetByte": 0,  "lengthInBytes": 0,  "offsetBits": 0,  "lengthInBits": 0,  "attributes": \[    {      "Attribute    },    ..  \],  "DESFireEncryption": {    DESFireEncryption  },  "MifareClassicEncryption": {    MifareClassicEncryption  },  "MifareULEncryption": {    MifareULEncryption  }}
```

| Field | Type | Description |
| --- | --- | --- |
| `name` | Id | A unique identifier for this configuration, typically referring to the meaning of a specific data chunk. Examples include face template, fingerprint, employee\_id, etc. The [CardData](#carddata) structure which contains the extracted data will also be identified by this name. |
| `cardType` | Id | The card type this configuration is valid for. See [Enumeration: CardTypeNames](#enumeration-cardtypenames). |
| `dataSource` | Id | The data source that should be used. See [Enumeration: CardDataSources](#enumeration-carddatasources) (default value is `CSN`. |
| `enabled` | Boolean | True if `CardDataConfig` is enabled. A disabled config is still part of the configuration, but will not be used for data extraction. |
| `required` | Boolean | If true and extracting data failed, the call will fail and the swipe be ignored. If false, a failed extraction will not include the data chunk in the response. Typically used in combination with `useAsUid` |
| `useAsUid` | Boolean | If true the extracted data is used to replace the original UID. If there are more `CardDataConfigs` with this setting, the data chunks will be joined (concatenated). |
| `offsetByte` | Integer | Optional offset (default value is 0). |
| `lengthInBytes` | Integer | Optional number of bytes to read (default 0 = all). |
| `offsetBits` | Integer | Optional offset in bits (default value is 0). |
| `lengthInBits` | Integer | Optional number of bits to read (default 0 = all). If both bytes and bits are specified, they will sum up (bytes\*8+bits). |
| `attributes` | Attribute array | List of additional config for future use. |
| `DESFireEncryption` | [DESFireEncryption](#desfireencryption) | MIFARE DESFire specific credentials and addressing. Only used if `cardType=MIFARE_DESFire`. |
| `MifareClassicEncryption` | [MifareClassicEncryption](#mifareclassicencryption) | MIFARE Classic specific credentials and addressing. Only used if `cardType=MIFARE_Classic`. |
| `MifareULEncryption` | [MifareULEncryption](#mifareulencryption) | MIFARE Ultralight specific credentials and addressing. Only used if `cardType=MIFARE_Ultralight`. |

#### Key

Key used for encryption. Typically provided as hexadecimal values.

Base type: `String ()`

#### Enumeration: KeyFormat

The format of a key. Some keys need to be protected (encrypted) and not exposed in plaintext to the user in order to protect sensitive key material.

| Value | Description |
| --- | --- |
| `Plaintext` | Key is provided in plain hexadecimal format. |
| `Protected` | Key is provided in protected hexadecimal format. |

#### Enumeration: DESFireKeyType

The key and authentication types for MIFARE DESFire.

| Value | Description |
| --- | --- |
| `Compatible_3DES` | DES/3DES in Compatible mode. |
| `EV1_3DES` | DES/3DES in EV1 mode, |
| `EV1_3K3DES` | 3Key 3DES in EV1 mode. |
| `EV1_AES` | AES in EV1 mode. |

#### Enumeration: DESFireCommMode

The different communication modes for a file in a MIFARE DESFire card.

| Value | Description |
| --- | --- |
| `Auto` | Will be deduced from file settings when reading. |
| `Plain` | Plain data. |
| `Plain_MACed` | Plain data with MAC check. |
| `Encrypted` | Encrypted. |

#### DESFireEncryption

MIFARE DESFire specific credentials and addressing configuration. Credentials are used to access the data. Addressing is used to point out the data location within the card.

Uses:

-   A field of [CardDataConfig](#carddataconfig). Only used if cardType=MIFARE\_DESFire

```bash
{    "AID": "hexBinary",    "keyFormat": "Plaintext",    "key": "Key",    "keyType": "Compatible\_3DES",    "commMode": "Auto",    "keyNbr": 0,    "fileNbr": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `AID` | hexBinary | MIFARE DESFire application ID, with a 3 bytes Little endian first. Common for credentials and addressing. |
| `keyFormat` | [Enumeration: KeyFormat](#enumeration-keyformat) | Format of the key. See [Enumeration: KeyFormat](#enumeration-keyformat) for additional information. |
| `key` | Key | MIFARE DESFire key. 16 bytes for 3DES and AES, 24 bytes for 3K3DES. Used as credential. |
| `keyType` | [Enumeration: DESFireKeyType](#enumeration-desfirekeytype) | The MIFARE DESFire key type. Used as credential. |
| `commMode` | [Enumeration: DESFireCommMode](#enumeration-desfirecommmode) | The MIFARE DESFire communication mode. Used as credential. |
| `keyNbr` | Integer | Key number 0–13, 0 is the main key. Used as credential. |
| `fileNbr` | Integer | MIFARE DESFire file number 0–31. Used as addressing. |

#### MifareClassicEncryption

MIFARE Classic specific credentials and addressing configuration. The credentials are used to access the data, addressing to point out the data location within the card.

Uses:

-   A field of [CardDataConfig](#carddataconfig) that is only used if `cardType=MIFARE_Classic`.
-   The total offset depends on the startSector, startBlock and offset.
-   For a MIFARE Classic card, sectors 0–31 have 4 blocks, while sectors 32–39 have 16 blocks each available only on 4 K cards.
-   Each block is 16 bytes.
-   The total offset must be less than 4096 bytes and total offset + length can only be up to 4096 bytes.

```bash
{    "keyAFormat": "Plaintext",    "keyA": "Key",    "keyBFormat": "Plaintext",    "keyB": "Key",    "startSector": 0,    "startBlock": 0,    "skipLastBlockInSector": true}
```

| Field | Type | Description |
| --- | --- | --- |
| `keyAFormat` | KeyFormat | Format of keyA. See [Enumeration: KeyFormat](#enumeration-keyformat) for additional information. |
| `keyA` | Key | MIFARE Key A, 6 bytes. Used as credential. |
| `keyBFormat` | KeyFormat | Format of keyB. See [Enumeration: KeyFormat](#enumeration-keyformat) for additional information. |
| `keyB` | Key | MIFARE Key B, 6 bytes. Used as credential. |
| `startSector` | Integer | Optional start for sectors 0–39. Default value is 0. Used as addressing. |
| `startBlock` | Integer | Optional start for blocks 0–15. Default value is 0. Used as addressing. |
| `skipLastBlockInSector` | Boolean | Skips the last block of the sector. Used as addressing. |

#### MifareULEncryption

MIFARE Ultralight specific credentials configuration only for Ultralight C. Credentials are used to access the data. No addressing is necessary, since the UL uses one single continuous block of data.

```bash
{    "keyFormat": "Plaintext",    "key": "Key"}
```

| Field | Type | Description |
| --- | --- | --- |
| `keyFormat` | KeyFormat | The key format. See [Enumeration: KeyFormat](#enumeration-keyformat) for additional information. |
| `key` | Key | Optional 16 byte key for MIFARE Ultralight C. Used as credential, but only for Ultralight C. |

#### Enumeration: RegisteredReaderPolicy

The possible policy values that control masking of newly registered readers.

| Value | Description |
| --- | --- |
| `Fixed` | Ignores masking so that only defined `ReaderIds` in the `RegisteredReaderConfiguration` are allowed to send an `InjectTag` to the Access control. |
| `Auto` | The default value that accepts the masking request provided by the application readers. Masking is provided in the `RegisterReader` call. |

#### RegisteredReaderConfiguration

Specifies how the clients (usually an application or third party solution) are allowed to use the InjectTag.

```bash
{  "ReaderIds": \[ "Internal",.. \],  "Policy": "Auto"}
```

| Field | Type | Description |
| --- | --- | --- |
| `ReaderIds` | Id array | Lists the readers that are allowed to send an `InjectTag` to the access control integration using Protocol. The default value is `Internal`. This can only be done when Policy is Fixed. See [Enumeration: RegisteredReaderPolicy](#enumeration-registeredreaderpolicy) for additional information. |
| `Policy` | Id | The policy that should be used. See [Enumeration: RegisteredReaderPolicy](#enumeration-registeredreaderpolicy) for additional information. |

#### Enumeration: IntercomReaderIds

Defines the reserved reader ID:s provided by the device.

| Value | Description |
| --- | --- |
| `Internal` | The built-in reader. |

#### ReaderIdWithMask

Shows if the reader is masked or not.

```bash
{    "readerId": "Internal",    "isMasked": true}
```

| Field | Type | Description |
| --- | --- | --- |
| `readerId` | Id | The ID of the reader that can be both the ID for a third-party integration or Internal (see [Enumeration: IntercomReaderIds](#enumeration-intercomreaderids)). |
| `isMasked` | Boolean | True if the reader is masked so that card data is not sent using the configured protocol. |

#### CallButtonConfiguration

Configurations of the call button functionality.

```bash
{    "callButtonKeyTrigger": "C",    "suppressionTimeout": 2,    "suppressionMode": "Timeout"}
```

| Field | Type | Description |
| --- | --- | --- |
| `callButtonKeyTrigger` | String | The call button, represented by the letter ‘C‘ in the API. |
| `suppressionTimeout` | Integer | The number of seconds that the call button should be suppressed. Default: `1`. |
| `suppressionMode` | String | See [Enumeration: SuppressionMode](#enumeration-suppressionmode). |

#### Enumeration: SuppressionMode

| Value | Description |
| --- | --- |
| `None` | The call button is always available to end the call. |
| `Timeout` | The call button is only available to end the call after a specified period has passed. |
| `NeverHangUp` | The call button is disabled to end the call. Only the recipient can end the call. |

### Service capabilities

The `GetServiceCapabilities` call can be used to retrieve the capabilities of a service, such as extensions and product specific capabilities and implementation methods.

#### IntegerValidator

Assigns min/max values to an integer, allowing client side validation of the user input.

```bash
{    "Name": "pinLength",    "Min": 0,    "Max": 32}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | Id | Identifies the integer in the configuration. |
| `Min` | Integer | Minimum value of the integer. |
| `Max` | Integer | Maximum value of the integer. |

#### Enumeration: CompatibilityFlag

The available `CompatibilityConfig` names used in `Attribute` and `AttributeInfo` for the [CompatibilityConfiguration](#compatibilityconfiguration) and [ServiceCapabilities](#servicecapabilities).

| Value | Description |
| --- | --- |
| `ByteReversal` | Reverses the byte order for UUID (all card types and bit lengths). |
| `Max32bit` | Uses maximum 32 bits of the UUID (all card types and bit lengths). |

#### ServiceCapabilities

Reflects the optional, static functionality of a service that won’t change when a device is active.

```bash
{  "Version": "string",  "Call": true,  "DTMFEvent": true,  "CallButton": true,  "CallKeypad": true,  "PinKeypad": true,  "Reader": true,  "uiLeds": \[    {      UiLed    },    ..  \],  "AccesscontrolIntegrationProtocols": \[    "None",    "IPAccess",    "OSDP",    "Wiegand",    ..  \],  "SupportedCards": \[    {      CardType    },    ..  \],  "SupportedIOPins": \[    "I1",    ..  \],  "SupportedColorNames": \[    "off",    ..  \],  "IntegerValidators": \[    {      IntegerValidator    },    ..  \],  "CompatibilityConfigs": \[    {      AttributeInfo    },    ..  \],  "SupportedKeypressOutputFormatWiegand": \[    "FourBit",    ..  \],  "SupportedCardOutputFormat": \[    "Raw",    ..  \],  "SupportedFacilityCodeOverrideMode": \[    "Auto",    ..  \],  "SupportedParityType": \[    "None",    ..  \],  "SupportedCallButtonIdleBehavior": \[    "Automatic",    ..  \],  "SupportedDefaultContactSorting": \[    "SortByFirstName",    ..  \],  "SupportedDefaultNameFormat": \[    "FirstNameFirst",    ..  \]}
```

| Field | Type | Description |
| --- | --- | --- |
| `Version` | String | The service version. |
| `Call` | Boolean | True if Call is supported. |
| `DTMFEvent` | Boolean | True if DTMFEvent operations are supported. |
| `CallButton` | Boolean | True if Callbutton is available. |
| `CallKeypad` | Boolean | True if a keypad is available for calling. |
| `PinKeypad` | Boolean | True if a keypad is available for PIN entry. |
| `Reader` | Boolean | True if your device has a reader. |
| `uiLeds` | UiLed array | Lists all LED-lights available on your system. |
| `AccesscontrolIntegrationProtocols` | Id array | Lists the communication protocols with supported access controller. See [Enumeration: AccesscontrolIntegrationProtocol](#enumeration-accesscontrolintegrationprotocol) for possible values. |
| `SupportedCards` | CardType array | Lists supported card types. |
| `SupportedIOPins` | Id array | Lists supported I/O pins. See [Enumeration: IOPinName](#enumeration-iopinname) for possible values. |
| `SupportedColorNames` | Id array | Lists supported color names. See [Enumeration: ColorName](#enumeration-colorname) for possible values. |
| `IntegerValidators` | IntegerValidator array | Lists limits for integer configuration fields. |
| `CompatibilityConfigs` | AttributeInfo array | Lists supported compatibility configuration values. See [Enumeration: CompatibilityFlag](#enumeration-compatibilityflag) for possible values. |
| `SupportedKeypressOutputFormatWiegand` | Id array | Lists the supported keypress formats for wiegand. See [Enumeration: KeypressOutputFormat](#enumeration-keypressoutputformat) for possible values. |
| `SupportedCardOutputFormat` | Id array | Lists the supported card formats. See [Enumeration: CardOutputFormat](#enumeration-cardoutputformat) for possible values. |
| `SupportedFacilityCodeOverrideMode` | Id array | Lists the supported facility code override modes. See [Enumeration: FacilityCodeOverrideMode](#enumeration-facilitycodeoverridemode) for possible values. |
| `SupportedParityType` | Id array | Lists the supported parity types. See [Enumeration: ParityType](#enumeration-paritytype) for possible values. |
| `SupportedCallButtonIdleBehavior` | Id array | Lists the supported call button idle behavior. See [Enumeration: CallButtonIdleBehavior](#enumeration-callbuttonidlebehavior) for possible values. |
| `SupportedDefaultContactSorting` | Id array | Lists the supported values for default contact sorting. See [Enumeration: DefaultContactSorting](#enumeration-defaultcontactsorting) for possible values. |
| `SupportedDefaultNameFormat` | Id array | Lists the supported default name format values. See [Enumeration: DefaultNameFormat](#enumeration-defaultnameformat) for possible values. |

#### GetServiceCapabilities

This operation returns the capabilities of the service.

**Request**

```bash
{}
```

**Response**

```bash
{  "Capabilities": {    ServiceCapabilities  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Capabilities` | `ServiceCapabilities` | The capability response message. Contains the requested Intercom service capabilities. |

## Configuration

The configuration options for the overall functionality are managed through the Configuration data structure. This can be retrieved by using either a `GetConfiguration` command or using the RESTful `GET` operation of the configuration resource using `GET` `/vapix/intercom/Configuration`.

To modify the configuration, use the `UpdateConfiguration` command, or the RESTful approach with a `POST` or `PUT` to `/vapix/intercom/Configuration`. It is possible to update selected parts of the configuration with the `UpdateConfiguration` command by only setting the fields that should be changed. Omitted fields will keep their values.

### Configuration types
#### Configuration

This command is used to configure an entity for the intercom functionality. An optional field not set by `SetConfiguration` will keep its current value.

```bash
{  "Version": "string",  "CallTriggersEnabled": true,  "CallByNumbersEnabled": true,  "DefaultContactSorting": "SortByFirstName",  "DefaultNameFormat": "FirstNameFirst",  "DefaultCallByNumberSIPAccountId": "Id",  "AudioclipVolume": 100,  "BeeperVolume": 80,  "PresenceTimeout": 12,  "CardReaderConfiguration": {    CardReaderConfiguration  },  "CallButtonConfigurations": \[{    CallButtonConfiguration  }\],  "CallButtonIdleBehavior": "Automatic"}
```

| Field | Type | Description |
| --- | --- | --- |
| `Version` | String | The configuration version. |
| `CallTriggersEnabled` | Boolean | True if the processing triggers in the `PhonebookEntries` are enabled. |
| `CallByNumbersEnabled` | Boolean | True if calls to dialed numbers that does not match any `CallRule` is enabled. |
| `DefaultContactSorting` | [Enumeration: DefaultContactSorting](#enumeration-defaultcontactsorting) | The default method when sorting contacts. |
| `DefaultNameFormat` | [Enumeration: DefaultNameFormat](#enumeration-defaultnameformat) | The default format for the contact names. |
| `DefaultCallByNumberSIPAccountId` | Id | The default SIPAccount used by `CallByNumber` (optional). |
| `AudioclipVolume` | Integer | The volume for the built-in audio files (button presses, calling, ringing, etc.) `Min: 0, Max: 1000, Default: 100`. |
| `BeeperVolume` | Integer | The volume for the beeper (Wiegand and OSDP) feedback. `Min: 0, Max: 100, Default: 80`. |
| `PresenceTimeout` | Integer | The time (in seconds) before user presence is timed out. `Min: 2, Max: 86400, Default: 12`. |
| `CardReaderConfiguration` | [CardReaderConfiguration](#cardreaderconfiguration) | The card reader related configurations. |
| `CallButtonConfigurations` | [CallButtonConfigurations](#callbuttonconfiguration) | The call button related configurations. |
| `CallButtonIdleBehavior` | Id | The idle behavior for the call button. See [Enumeration: CallButtonIdleBehavior](#enumeration-callbuttonidlebehavior) and [ServiceCapabilities](#servicecapabilities) for possible and supported values. |

#### Enumeration: `DefaultContactSorting`

The default method for sorting contacts.

| Value | Description |
| --- | --- |
| `SortByFirstName` | Sorts the contacts alphabetically according to their first names. |
| `SortByLastName` | Sorts the contacts alphabetically according to their last names. |

#### Enumeration: `DefaultNameFormat`

The default format for the contact names.

| Value | Description |
| --- | --- |
| `FirstNameFirst` | Name entries will be formatted according to `FirstName` + " " + `LastName`. |
| `LastNameFirst` | Name entries will be formatted according to `LastName` + ", " + `FirstName`. |

#### `SetConfiguration`

This method is used to set the general configuration for the intercom.

**Request**

```bash
{  "Configuration": {    Configuration  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Configuration` | Configuration | The configuration that should be set. |

**Response**

```bash
{}
```

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |

#### `UpdateConfiguration`

This method is used to update the general configuration. Optional fields not present in the request will keep their current values.

**Request**

```bash
{  "Configuration": {    Configuration  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Configuration` | Configuration | The configuration that should be set. |

**Response**

```bash
{}
```

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |

#### `GetConfiguration`

This method is used to request the full configuration for the intercom.

**Request**

```bash
{  "includeImageFile": (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `includeImageFile` | Boolean | If set to true, all `imageFile` fields will be included in the response (optional). |

**Response**

```bash
{  "Configuration": {    Configuration  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Configuration` | Configuration | Configuration structure. |

#### `Configuration`

This method implements the REST API for the device configuration and handles both `GET`, `SET` and `REMOVE`.

-   Use `GET /vapix/intercom/Configuration` to fetch the configuration.
-   Use `POST /vapix/intercom/Configuration` to initiate the `UpdateConfiguration`.
-   Use `PUT /vapix/intercom/Configuration` to initiate the `SetConfiguration`.

**Request**

```bash
{  "includeImageFile": (optional),  "Configuration": {    Configuration  } (optional),  "imageFile": {    ImageFile  } (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `includeImageFile` | Boolean | If set to true, all `imageFile` fields will be included in the response (optional). |
| `Configuration` | Configuration | The configuration that should be set. |
| `imageFile` | ImageFile | The image file that should be used to update an image. |

**Response**

```bash
{  "Configuration": {    Configuration  } (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Configuration` | Configuration | The configuration structure. |

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |

### Server report
#### CallButtonInformation

Summarizes the call button configuration.

```bash
{    "VMSCallEnabled": true,    "NumberOfRecipients": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `VMSCallEnabled` | Boolean | The current status of the `CallButtonVMS`. |
| `NumberOfRecipients` | Integer | The number of contacts for the call button. |

#### ContactsInformation

Summarizes the contact configuration.

```bash
{    "NumberOfContacts": 0,    "NumberOfOrganizations": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `NumberOfContacts` | Integer | The total number of contacts. |
| `NumberOfOrganizations` | Integer | The total number of organizations. |

### GetServerReport

This method is used when you want to return the safe and desired parts of the server report.

**Request**

```bash
{}
```

**Response**

```bash
{  "Configuration": {    Configuration  },  "DiscardedFields": \[    "",    ...  \],  "CallButtonInformation": {    CallButtonInformation  }(optional),  "ContactsInformation": {    ContactsInformation  }  (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Configuration` | Configuration | A structure containing the configuration fields. |
| `DiscardedFields` | String array | The configuration fields discarded due to containing sensitive data. |
| `CallButtonInformation` | CallButtonInformation | The call button information. |
| `ContactsInformation` | ContactsInformation | The contact information. |

### Card reader configuration and operation

Here is a summary of supported card reader operations:

-   `GetCardReaderConfiguration` - Alternative operation to `GetConfiguration` when only the `CardReaderConfiguration` part is needed.
-   `GetSupportedTagTypes` - Retrieve a list of tag types supported by the reader. This operation is also available with `GetServiceCapabilities`.
-   `GetDefaultTagTypes` - Retrieve a list with the default enabled card types.
-   `GetLastTag` - Retrieve the UID of the last presented tag.
-   `InjectTag` - Simulates presenting an RFID tag, which is useful when you are integrating with a third party application and acts as a filter and/or transforms the tag information.
-   `RegisterReader` - Registers either an external or application reader to be used when processing tags. Makes it possible to mask the internal reader, i.e. a tag from a normal card swipe will not be sent using the configured integration protocol.
-   `UnregisterReader` - Unregisters either an external or application reader to be used when processing tags.
-   `KeepAliveReader` - Extends a registration.
-   `GetCurrentReaders` - Exposes the currently available readers.

#### GetCardReaderConfiguration

This method is used when you want to send out a request for the full configuration.

**Request**

```bash
{}
```

**Response**

```bash
{  "CardReaderConfiguration": {    CardReaderConfiguration  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `CardReaderConfiguration` | CardReaderConfiguration | The configuration structure. |

#### GetSupportedTagTypes

This method is used when you want to retrieve a list of tag types supported by the reader.

**Request**

```bash
{}
```

**Response**

```bash
{  "CardTypes": \[    {      CardType    },    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `CardTypes` | CardType array | The supported tag types. |

#### GetDefaultTagTypes

This method is used when you want to retrieve a list of card types enabled by default.

**Request**

```bash
{}
```

**Response**

```bash
{  "CardTypes": \[    "",    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `CardTypes` | Id array | The default card types. |

#### GetLastTag

This method is used when you want to retrieve the UID of the last tag that was presented.

**Request**

```bash
{  "ReaderId": "" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `ReaderId` | Id | Optional reader ID that the last tag should be retrieved from. The last tag will be retrieved if this parameter is not specified. |

**Response**

```bash
{  "Tag": {    TagPresentedInfo  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Tag` | TagPresentedInfo | The UID of the tag last seen. |

**Error codes**

| Code | Description |
| --- | --- |
| `ter:NotFound` | No tag with the specified reader ID was found. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The method is not supported. |

#### GetTag

This method is used when you want to retrieve the UID of either the last presented tag or one recently presented that optionally matches the specified timestamp taken from the Device/Intercom/RFID event notification. If neither `ReaderId` nor `timestamp` is specified, the last tag will be returned

**Request**

```bash
{  "ReaderId": "" (optional),  "timestamp": "" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `ReaderId` | Id | Optional reader ID that the last tag should be retrieved from. The last tag will be retrieved If this parameter is not specified. |
| `timestamp` | String | A timestamp of the tag taken from the Device/Intercom/RFID event notification. Providing the timestamp assures that the data corresponds to the event received. |

**Response**

```bash
{  "Tag": {    TagPresentedInfo  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Tag` | TagPresentedInfo | The UID of the matching the input parameters. |

**Error codes**

| Code | Description |
| --- | --- |
| \--- | \--- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | No tag with the specified reader ID and timestamp was found. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The method is not supported. |

#### InjectTag

This method is used when you want to simulate presenting an RFID tag to the intercom reader. If the internal reader has been masked, it is recommended to make sure that the `ReaderId` is no longer **Internal** in the supplied tag.

**Request**

```bash
{  "Tag": {    TagPresentedInfo  },  "CardData": \[    {      CardData    },    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Tag` | TagPresentedInfo | The tag to inject. |
| `CardData` | CardData array | Card data that should be injected. |

**Response**

```bash
{}
```

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |
| `env:Receiver` `ter:ActionNotSupported` `ter:NotSupported` | The method is not supported. |

#### RegisterReader

This method is used when you want to register an external application reader that can be used to process tags. This makes it possible to mask the internal reader so a tag from a normal card swipe don’t use a configured integration protocol.

**Request**

```bash
{  "ReaderId": "",  "DisableInternalReader": (optional),  "MaskedReaderIds": \[    "<Id>",    ...  \],  "UnmaskIfLost": (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `ReaderId` | Id | The ID of the external reader. |
| `DisableInternalReader` | Boolean | If this parameter exists and is true all internal readers will be added to `MaskedReaderIds` automatically (optional). |
| `MaskedReaderIds` | Id array | The reader ID for internal and external application readers that should be masked. Masked readers are not allowed to send credentials to the Access control, but the data will still be available as an RFID event. Default value doesn’t mask anything and the values for the internal reader Ids can be found in `IntercomReaderIds` enum. |
| `UnmaskIfLost` | Boolean | If true the masked readers specified above will be released when the timeout expires (optional). The default value is false. |

**Response**

```bash
{  "Timeout": <int>}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Timeout` | Integer | The timeout, measured in seconds, until the registration expires. |

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |
| `env:Receiver` `ter:Action` `ter:Failure` | The operation failed. |

#### UnregisterReader

This method is used when you want to un-register either an external reader or an application reader from being used to process tags.

**Request**

```bash
{    "ReaderId": "<Id>"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `ReaderId` | Id | The ID of the external reader. |

**Response**

```bash
{}
```

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of input. |

#### KeepAliveReader

This method is used when you want to extend the timeout given in the `RegisterReader` call. An error will be returned if no call was made for the `ReaderId` or if it had already timed out.

**Request**

```bash
{    "ReaderId": "<Id>"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `ReaderId` | Id | The ID of the external reader. |

**Response**

```bash
{  "Timeout": <int>}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Timeout` | Integer | Timeout in seconds until this registration expires. |

**Error codes**

| Code | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` | The request contains an invalid argument. |
| `env:Sender` `ter:InvalidArgs` | The request is missing something or has an invalid combination of inputs. |

#### GetCurrentReaders

This method is used when you want to expose currently available readers.

**Request**

```bash
{}
```

**Response**

```bash
{  "Readers": \[    {      ReaderIdWithMask    },    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Readers` | ReaderIdWithMask array | The array of strings with the available `ReaderIds` together with a masked flag. |

### IP Access configuration

The [IPAccessConfiguration](#ipaccessconfiguration) and [RequestAccessConfiguration](#requestaccessconfiguration) structures in the [CardReaderConfiguration](#cardreaderconfiguration) are used when `IPAccess` is selected as the [Enumeration: AccesscontrolIntegrationProtocol](#enumeration-accesscontrolintegrationprotocol).

The [Enumeration: IPIntegrationProtocol](#enumeration-ipintegrationprotocol) (IPProtocol) field in the [IPAccessConfiguration](#ipaccessconfiguration) defines the protocol to use. If using `RequestAccess` or `RemoteActivity`, an outbound connection to the access controller is established by using the configuration found in [RequestAccessConfiguration](#requestaccessconfiguration).

With `RequestAccess`, your device uses a HTTP(s) request to the Access control service providing card and PIN information. The response contains an `AccessGranted` value and `Reason` used to provide feedback from the device.

With `RemoteActivity`, your device creates and keeps a websocket connection to the IdPoint service of the controller. Through the connection, the device sends card and PIN information and receives notifications regarding feedback. The benefit of `RemoteActivity` is that access controller can provide feedback anytime, whereas `RequestAccess` only provides feedback for operations initiated by your device.

The [ProbeIPAccessConfiguration](#probeipaccessconfiguration) and [UpdateIPAccessConfiguration](#updateipaccessconfiguration) functions can be used to set up integrations with door controllers. [Enumeration: IPIntegrationProtocol](#enumeration-ipintegrationprotocol) (IPProtocol) in [IPAccessConfiguration](#ipaccessconfiguration) will be determined based on the capabilities detected in the controller when these functions are used.

**Enumeration: ProbeIPAccessStatus**

The status of a [ProbeIPAccessConfiguration](#probeipaccessconfiguration) request. Please note that this may be extended in the future.

| Value | Description |
| --- | --- |
| `OK` | Everything is OK. |
| `NoAccessPoints` | Connection is OK, but could not find any access points. |
| `UnknownError` | Unknown error. |
| `ConnectionError` | Failed to connect to the specified address and scheme. |
| `AuthenticationError` | Failed to authenticate. |
| `CertificateError` | Failed to validate the certificate. |

#### IPAccessOption

This structure is returned as a response to [ProbeIPAccessConfiguration](#probeipaccessconfiguration).

```bash
{    "Name": "Door - Reader Entrance A8207",    "Id": "e6608ad31a480904f9646e936cc8e86a",    "IPProtocol": "RemoteActivity"}
```

| Field | Type | Description |
| --- | --- | --- |
| `Name` | String | The door name visible to the user. |
| `Id` | String | The internal ID of the `RequestAccess` configuration. |
| `IPProtocol` | String | The detected protocol. See [Enumeration: IPIntegrationProtocol](#enumeration-ipintegrationprotocol) for additional information. |

#### ProbeIPAccessConfiguration

Probe an IP based access controller and return a list of selectable configurations. Please note that any current configuration will be overridden by the specified input parameters. Also, the ID of the desired `IPAccessOption` should be supplied to `UpdateIPAccessConfiguration`.

Request

```bash
{  "IPAccessConfiguration": {    IPAccessConfiguration (optional)  }}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `IPAccessConfiguration` | IPAccessConfiguration | The `IPAccessConfiguration` |

Response

```bash
{  "Status": "<string>",  "StatusText": "<string>" (optional),  "IPAccessOptions": \[{    IPAccessOption  }, ...\],  "SuggestedId": "<string>" (optional),  "CurrentName": "<string>" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Status` | String | The status of the probe request. See **Enumeration: ProbeIPAccessStatus** in [IP Access configuration](#ip-access-configuration) for additional information. |
| `StatusText` | String | Textual status related to `Status`. |
| `IPAccessOptions` | IPAccessOption array | A list of options. |
| `SuggestedId` | String | A configuration ID that matches the current configuration. No match will be found if it gets omitted. |
| `CurrentName` | String | The name of the current configuration that can be used as a hint if `SuggestedId` is not present. |

#### UpdateIPAccessConfiguration

Update the `IPAccessConfiguration` based on the selected `IPAccessOption` in the response from a previous `ProbeIPAccessConfiguration`.

Request

```bash
{    "Id": "<string>"}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Id` | String | The ID from an [IPAccessOption](#ipaccessoption) previously returned by [ProbeIPAccessConfiguration](#probeipaccessconfiguration) |

Response

```bash
{  "IPAccessConfiguration": {    IPAccessConfiguration  } (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `IPAccessConfiguration` | IPAccessConfiguration | The resulting configuration. |

#### GetCardData

Get data stored on tags that support storage. You are able to specify the names of one or more configs already pre-loaded under `CardReaderConfiguration/CardDataConfigs`, or supply an ad-hoc `CardDataConfig` to be used without storing.

**Request**

```bash
{  "DataConfigNames": \[    "<Id>",    ...  \],  "CardDataConfigs": \[    {      CardDataConfig    },    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `DataConfigNames` | Id array | Array of names that matches the names under `CardReaderConfiguration/CardDataConfigs` |
| `CardDataConfigs` | `CardDataConfig` array | Ad-hoc configurations that should be used. |

**Response**

```bash
{  "CardData": \[    {      CardData    },    ...  \]}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `CardData` | `CardData` array | The data read from a card. Multiple fields are returned and identified by the name of the corresponding config. Can be either Ad-hoc or pre-loaded. |

### Keypress functions

Key presses can be monitored by using the `Device/Intercom/KeyPin` event in [Third party integration](#third-party-integration), or pulled with [GetLastKeySequence](#getlastkeysequence).

The event will only contain the actual key sequence if `CardReaderConfiguration.SensitivePINEventEnabled` is true, otherwise `GetLastKeySequence` must be used to retrieve it.

A `KeySequence` can be simulated by using `InjectKeySequence`. This can also be used with third-party integrations to provide a PIN number, such as validating a face instead of forcing the user to enter a PIN code.

The keypad on an intercom can be used both to place calls and to enter a PIN by operating in different modes. For example, if the intercom is not in PIN mode, the `#` key must be pressed to end the PIN entry.

The Call button, represented by the letter ‘C‘ in the API, should be pressed when you want to make a call.

**Keypress types**

**Enumeration: PinSourceType**

The reserved identifiers used in the source field of an `InjectKeySequence` call and for the `KeyPin` event.

| Value | Description |
| --- | --- |
| `Internal` | Used by internal intercom components. |
| `Unknown` | Used when no other source is provided. |

#### GetLastKeySequence

This method is used when you want to retrieve a string containing the latest key sequence. The sequence is automatically reset when new keys are entered after a complete sequence. A sequence is completed by `#` or the call button ('C') or when the number of digits match the configured pin length when in PIN mode. The optional timestamp should be taken from the Device/Intercom/KeyPin event notification and must be an exact match. Providing the timestamp assures that you get the data corresponding to the event received, or a not found error if another sequence has already been presented. If no timestamp is specified, the last key sequence of the specified source will be returned. If neither source or timestamp is specified, the last key sequence will be returned.

**Request**

```bash
{  "Source": "<string>" (optional),  "timestamp": "<string>" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Source` | String | An optional identifier of the source to retrieve the key sequence from. If not specified, the last source of key sequence will be used. See **Enumeration: PinSourceType** in [Keypress functions](#keypress-functions) for identifiers already reserved for internal use. |
| `timestamp` | String | The timestamp of the key sequence taken from the Device/Intercom/KeyPin event notification. Providing the timestamp assures that the data corresponds to the event received, but is not mandatory. |

**Response**

```bash
{  "KeySequence": "<string>",  "Source": "<string>" (optional),  "timestamp": "<string>" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `KeySequence` | String | The key sequence. |
| `Source` | String | The source of this key sequence. |
| `timestamp` | String | The timestamp of this key sequence. |

#### InjectKeySequence

This method is used when you want to simulate key presses.

Depending on the `KeyPadState` (see `tns1:Device/tnsaxis:Intercom/KeypadState` event), the sequence must be ended with a `C` to make a call or `#` to process the key sequence as a PIN.

No ending `#` is required when the state is `KSM_PIN_MODE`. The same state is automatically entered after a card swipe if Wiegand or OSDP has been configured, or if the `SetUiFeedback` call is used together with `RequirePIN` or `PINPadRequest` as `highlevelFeedbacks`.

**Request**

```bash
{  "KeySequence": "<string>",  "Source": "" (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `KeySequence` | String | The key sequence. |
| `Source` | String | Identifies the component that posted the `InjectKeySequence` call. See **Enumeration: PinSourceType** in [Keypress functions](#keypress-functions) for identifiers already reserved for internal use. |

**Response**

```bash
{}
```

## Feedback functions

Contains the different kinds of feedback commands that the UI components can present.

### Feedback types
#### Enumeration: UIHighLevelFeedback

This table describes the feedback that can be received. Please note that this may be extended in the future.

| Value | Description |
| --- | --- |
| `LowlevelControl` | LED and/or audio feedback, typically over Wiegand or OSDP. |
| `AccessGranted` | The access controller signals that access is granted. |
| `AccessDenied` | The access controller signals that access is denied. |
| `EarlyRFID` | Indicates the act of presenting a tag. |
| `PINPadRequest` | Indicates that the user is requested to enter a PIN. |
| `PINPadCancel` | Indicates that the user canceled entering a PIN. |
| `Other` | The feedback mode is specified in some other defined way. |
| `Idle` | The normal state, typically `DoorLocked` or `DoorUnlocked` is used when the device controls a door. |
| `DoorLocked` | Indicates that the door is locked. |
| `DoorUnlocked` | Indicates that the door is unlocked. |
| `DoorOpenTooLong` | Indicates that the door has been open for too long. |
| `DoorPreAlarmWarning` | Indicates that the door is about to have been open too long. |
| `RequirePIN` | PIN (Personal Identification Number) code required. |
| `RequireCard` | A card is required. |
| `Processing` | Processing in progress. |
| `InvalidCredential` | Credential is not valid. |
| `AccessGrantedAndRequire` | Access granted with further identification possible. |
| `Ok` | Generic Ok indication. |
| `Fault` | Generic Fault indication. |
| `Warning` | Generic Warning indication. |
| `Alarm` | Generic Alarm indication. |
| `Custom` | The custom mode. |
| `Progress` | Indicates whether progress has been made. |
| `AuthenticationFailed` | The authentication process failed. |
| `RequireInteraction` | Additional interaction required. |

#### Enumeration: RunStyleType

Defines the supported types of run style.

| Value | Description |
| --- | --- |
| `oneshot` | The feedback is processed once and then removed. |
| `permanent` | The feedback is processed over and over again. |

#### Enumeration: TargetLedType

The name of the LED types that the `UiLedFeedback` should be applied to.

| Value | Description |
| --- | --- |
| `backlight` | The backlight for the keypad. |
| `callButton` | The call button. |
| `stripe` | Mainly used for access control feedback. |
| `statusDoor` | The door status indicator. |
| `statusCall` | The calling status indicator. |
| `statusSpeak` | The speak/active call status indicator. |

#### Enumeration: LedControlType

The control type for the different LEDs.

| Value | Description |
| --- | --- |
| `none` | None. |
| `onoff` | Simple on/off switch. |
| `pwm` | PWM (Pulse Width Modulation) LED. |
| `rgb` | RGB LED. |
| `rgbpwm` | PWM RGB LED. |

#### Enumeration: CallButtonIdleBehavior

Describes the possible idle behavior value for the call button.

See `SupportedCallButtonIdleBehavior` in [ServiceCapabilities](#servicecapabilities) for values supported by your device.

| Value | Description |
| --- | --- |
| `Automatic` | The visualization specified in the configuration file `etc/sysconfig/dsui.conf`. |
| `Off` | Visualization switched off. |
| `On` | Visualization switched on. |

#### UiLed

Lists information about the LEDs available on the device.

```bash
{    "ledId": "stripe",    "ledType": "rgbpwm"}
```

| Field | Type | Description |
| --- | --- | --- |
| `ledId` | [Enumeration: TargetLedType](#enumeration-targetledtype) | The name of the LED. |
| `ledType` | [Enumeration: LedControlType](#enumeration-ledcontroltype) | How the LED is controlled. |

#### Enumeration: FeedbackSourceType

The identifiers used in the source field of the `SetUIFeedback` call.

| Value | Description |
| --- | --- |
| `Internal` | Used by the internal components of the intercom. |
| `ExternalOSDP` | Used by the externally connected OSDP reader. |

#### UiLedFeedback

Blinks a LED for a duration of time or during a loop.

See [Enumeration: ColorName](#enumeration-colorname) if the returned value is textual.

If the value is in hexadecimal (#RRGGBB) it will be interpreted as Monochrome vs RGB:

-   If monochrome, only the LSB is effective.
-   If RGB, 1st LSB corresponds to blue, 2nd LSB corresponds to green and 3rd LSB corresponds to red.
-   MSB is not used.

Another possible value can be retrieved from PWM vs regular:

-   If PWM, all values between 0-255 are valid.
-   For non-PWM, 0 = off, 1-255 = on.

```bash
{    "led": "backlight",    "runStyle": "oneshot",    "durationOnMillisec": 0,    "durationOffMillisec": 0,    "valueOn": "off",    "valueOff": "off",    "loops": 0,    "handled": true}
```

| Field | Type | Description |
| --- | --- | --- |
| `led` | String | The LED name. See [Enumeration: TargetLedType](#enumeration-targetledtype). |
| `runStyle` | String | The running style. See [Enumeration: RunStyleType](#enumeration-runstyletype). |
| `durationOnMillisec` | Integer | Duration for the ON state. |
| `durationOffMillisec` | Integer | Duration for the OFF state. |
| `valueOn` | String | Value for the ON state. See [Enumeration: ColorName](#enumeration-colorname). |
| `valueOff` | String | Value for the OFF state. See [Enumeration: ColorName](#enumeration-colorname). |
| `loops` | Integer | The number of loops that should be run. |
| `handled` | Boolean | Initially `FALSE`. Used to mark that this particular feedback has already been displayed. |

#### UiAudioFeedback

Signals either a beeper sound or an audio file to play.

```bash
{    "durationOnMillisec": 0,    "durationOffMillisec": 0,    "loops": 0,    "handled": true,    "file": "string"}
```

| Field | Type | Description |
| --- | --- | --- |
| `durationOnMillisec` | Integer | The duration for the ON state. |
| `durationOffMillisec` | Integer | The duration for the OFF state. |
| `loops` | Integer | The number of loops that should be run. |
| `handled` | Boolean | Initially `FALSE`. Used to mark that this particular feedback has already been handled. |
| `file` | String | The audio file that should be played. |

#### UiGraphicFeedback

Describes the graphic sent to the device to be presented to the user.

```bash
{    "image": "string",    "durationMillisec": 0}
```

| Field | Type | Description |
| --- | --- | --- |
| `image` | String | The path to image or base64 encoded data url format. |
| `durationMillisec` | Integer | The duration for the image. |

### SetUiFeedback

Sets the behavior for the user interface feedback.

**Request**

```bash
{  "highlevelFeedbacks": \[    "<string>",    ...  \],  "ledFeedbacks": \[    {      UiLedFeedback    }    ...  \],  "audioFeedback": {    UiAudioFeedback  } (optional),  "source": "<string>",  "text": "<string>" (optional),  "attributes": \[    {      Attribute    },    ...  \],  "graphicFeedback": {    UiGraphicFeedback  } (optional)}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `highlevelFeedbacks` | String array | Lists of high level feedbacks to set. See [Enumeration: UIHighLevelFeedback](#enumeration-uihighlevelfeedback) for defined values. |
| `ledFeedbacks` | UILedFeedback array | Lists of LED feedbacks to set. |
| `audioFeedback` | UIAudioFeedback | The audio feedback. |
| `source` | String | An arbitrary identifier on the component that posts the feedback call. See [Enumeration: FeedbackSourceType](#enumeration-feedbacksourcetype) for reserved identifiers. |
| `text` | String | Text to display or speak. |
| `attributes` | Attribute array | List of attributes for additional information and future extensions. |
| `graphicFeedback` | UIGraphicFeedback | The graphic feedback that should be set. |

**Response**

```bash
{  "Result": <boolean>}
```

| Parameter | Type | Description |
| --- | --- | --- |
| `Result` | Boolean | The result of the operation. |

## Websocket functions

The following types and functions are intended to be used over websockets to subscribe to notifications and do efficient API calls.

The service supports websocket on the `/vapix/intercomws` endpoint. All RPC functions in this API can be used over a websocket, preferably in the Google JSON or JSONRPC2.0 format.

The methods and types in the Intercom service include the namespace prefix `axdsapi`, which must be used when subscribing to function notifications. Subscribing to events over the websocket is done with the `axev:subscribe` call. This will generally supply a list of event topics as well as a list of functions, the latter of which also must include the `axev:notify` function.

To list all possible events, the function `axev:getSupported` should be used, while event notifications must be sent as an `axev:notify` method call.

**axev:subscribe example**

```bash
{    "apiVersion": "1.0",    "method": "axev:subscribe",    "params": {        "style": "ttMessage",        "functions": \["axev:notify", "axdsapi:UpdateConfiguration", "axdsapi:SetUiFeedback"\],        "topics": \["Device\\/Intercom\\/RFID", "Device\\/Intercom\\/KeyPin"\]    },    "id": "firstsubscribe"}
```

**RFID event notification over websocket**

```bash
{    "apiVersion": "1.0",    "method": "axev:notify",    "params": {        "notifications": \[            {                "topic": "tns1:Device\\/tnsaxis:Intercom\\/RFID",                "timestamp": "2020-10-04T11:30:08.885643Z",                "data": {                    "Source": {                        "SimpleItem": \[                            {                                "Name": "Source",                                "Value": "Internal"                            }                        \]                    },                    "Data": {                        "SimpleItem": \[                            {                                "Name": "UIDFormat",                                "Value": "Raw"                            },                            {                                "Name": "TagType",                                "Value": "MIFARE\_Classic"                            },                            {                                "Name": "BitCount",                                "Value": "32"                            },                            {                                "Name": "UID",                                "Value": "C0DE1234"                            }                        \]                    }                }            }        \]    }}
```

### Limitations

All types have an upper limit of 100 entities/type and while the Intercom service itself cannot enforce this limitation, exceeding it may cause unexpected behavior.

## Notification topics
### Reader notification topics
#### tns1:Device/tnsaxis:Intercom/RFID event

This event is used to provide information about a detected RFID card.

The UID and card numbers are sent in plaintext if `CardReaderConfiguration.SensitiveRFIDEventEnabled` is true, otherwise they are sent as empty strings. If `CardReaderConfiguration.SensitiveRFIDEventEnabled` is false, you should use the `GetLastTag` method to retrieve the card information.

The `Masked` field will be true whenever the event comes from a masked reader, and should therefore not be used for final access decisions by an access control system. The data from a masked reader is not sent over the configured access control integration protocol (VAPIX reader, OSDP or Wiegand) and only available as an event for 3rd party integrations.

Whenever a RFID tag is detected, the device will provide the following events:

Topic: tns1:Device/tnsaxis:Intercom/RFID

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="Source" Type="xs:string" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="UIDFormat" Type="xs:string" />        <tt:SimpleItemDescription Name="TagType" Type="xs:string" />        <tt:SimpleItemDescription Name="TagSubType" Type="xs:string" />        <tt:SimpleItemDescription Name="UID" Type="xs:string" />        <tt:SimpleItemDescription Name="BitCount" Type="xs:int" />        <tt:SimpleItemDescription Name="CardNumber" Type="xs:int" />        <tt:SimpleItemDescription Name="CardNumberBitCount" Type="xs:int" />        <tt:SimpleItemDescription Name="FacilityCode" Type="xs:int" />        <tt:SimpleItemDescription Name="FacilityCodeBitCount" Type="xs:int" />        <tt:SimpleItemDescription Name="Masked" Type="xs:boolean" />    </tt:Data></tt:MessageDescription>
```

| Field name | Type | Description |
| --- | --- | --- |
| `Source/Source` | String | The source of events, such as the Reader Id. Generally **Internal**, unless `InjectTag` is used. |
| `Data/UIDFormat` | String | The format of the UID. See [Enumeration: CardOutputFormat](#enumeration-cardoutputformat) for additional information. |
| `Data/TagType` | String | The type of card/tag. |
| `Data/TagSubType` | String | The card sub type, such as Classic1k, Classic4k, DESFire or Ultralight. |
| `Data/UID` | String | ASCII hex representation of the tag UID if `SensitiveRFIDEventEnabled` is true. The value will be empty otherwise. |
| `Data/BitCount` | Integer | The number of bits in the UID. |
| `Data/CardNumber` | Integer | The decimal representation of the card number. |
| `Data/CardNumberBitCount` | Integer | The number of bits in the `CardNumber`. |
| `Data/FacilityCode` | Integer | The decimal representation of the facility code. |
| `Data/FacilityCodeBitCount` | Integer | The number of bits in the `FacilityCode`. |
| `Data/Masked` | Boolean | True if the reader is masked. |

### User interface notification topics
#### tns1:Device/tnsaxis:Intercom/MainState event

This event provides information about Main States machine transitions.

**Enumeration: MainState**

The values for the MainState:

| Value | Description |
| --- | --- |
| `MSM_IDLE` | Idle, waiting for input. |
| `MSM_KEYING` | Key input in progress. |
| `MSM_CONVERSATION` | Conversation in progress. |

This event provides information about Main States machine transitions.

Whenever there is a transition from one to another main state, the device provides the following events:

Topic: tns1:Device/tnsaxis:Intercom/MainState

```bash
<tt:MessageDescription IsProperty="true">    <tt:Source>        <tt:SimpleItemDescription Name="Source" Type="xs:string" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="State" Type="xs:string" />        <tt:SimpleItemDescription Name="Presence" Type="xs:int" />    </tt:Data></tt:MessageDescription>
```

| Field name | Type | Description |
| --- | --- | --- |
| `Source/Source` | String | The source of events, generally **Internal**. |
| `Data/State` | String | The state, as shown in the table above. |
| `Data/Presence` | Integer | Presence flag. Value=1 when a presence is detected, value=0 otherwise. |

#### tns1:Device/tnsaxis:Intercom/KeyPin event

This event informs the subscribing client about the input key PIN value.

Whenever the key PIN is entered it is published as an event. The key PIN is terminated with `#` in cases when it is not completed as per the configuration in the reader and will be sent in plaintext if `CardReaderConfiguration.SensitiveKeyPinEventEnabled` is true or otherwise as the value of an empty string `""`. If `CardReaderConfiguration.SensitiveKeyPinEventEnabled` is false you should use the `GetLastKeySequence` method to fetch the PIN.

Topic: tns1:Device/tnsaxis:Intercom/KeyPin

```bash
<tt:MessageDescription IsProperty="false">    <tt:Source>        <tt:SimpleItemDescription Name="Source" Type="xs:string" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="KeyPin" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

| Field name | Type | Description |
| --- | --- | --- |
| `Source/Source` | String (optional) | A component identifier for the input that published `KeyPin`(optional). See **Enumeration: PinSourceType** in [Keypress functions](#keypress-functions) for identifiers already reserved for internal use. |
| `Data/KeyPin` | String | The key PIN digits value, either with or without the `#` terminator. If `CardReaderConfiguration.SensitiveKeyPinEventEnabled` is false, value is empty. |

#### tns1:Device/tnsaxis:Intercom/KeypadState event

This event will provide you with the information about the different keypad state transitions.

**Enumeration: KeypadState**

The keypad state can have the following values:

| Value | Description |
| --- | --- |
| `KSM_IDLE` | The idle state, no keypress was detected. |
| `KSM_PIN_MODE` | PIN code expected and will be processed when the configured number of digits are pressed. |
| `KSM_MIXED_MODE` | Mixed mode, where a key sequence must be ended with `#` for a PIN code or the call button (C) to place a call. |

When there is a transition from one state to another, the device will provide the following event:

Topic: tns1:Device/tnsaxis:Intercom/KeypadState

```bash
<tt:MessageDescription IsProperty="true">    <tt:Source>        <tt:SimpleItemDescription Name="Source" Type="xs:string" />    </tt:Source>    <tt:Data>        <tt:SimpleItemDescription Name="State" Type="xs:string" />    </tt:Data></tt:MessageDescription>
```

| Field name | Type | Description |
| --- | --- | --- |
| `Source/Source` | String | The event source, typically `Internal`. |
| `Data/State` | String | The Keypad state. See **Enumeration: KeypadState** above. |