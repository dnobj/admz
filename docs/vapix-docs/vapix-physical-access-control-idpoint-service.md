---
title: IdPoint service
url: "https://developer.axis.com/vapix/physical-access-control/idpoint-service/"
category: vapix
subcategory: physical-access-control
sha256: 546c926936ff4fb51485cf58b80c17c403aaeecbd17fc04ffeabf4e3081434f4
scraped_at: "2026-01-09T15:21:44.972Z"
page_height: 61331
---

# IdPoint service

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## IdPoint service guide

The IdPoint service is used for management of IdPoints. An IdPoint is a representation of a physical device where a user can input identification information. For example:

-   Card readers
-   Keypads
-   Biometric sensors

The diagram shows the data types that are used by the IdPoint Service.

![IdPoint Data Types](/assets/images/idpoint-service.t10068094-9f17f6b8845aa558f51e3e0f3ed5e191.png)

### Setting up an IdPoint

A functioning IdPoint consists of two parts:

-   `IdPoint` — The abstract representation in the system
-   `IdPointConfiguration` — The hardware configuration bound to the IdPoint

These two structures are connected by giving them the same `token`. These structures can be added or removed in any order. When only one of them exists, the IdPoint service will not do anything with the data until the complementary structure is set.

### Creating the IdPoint

Creating an abstract `IdPoint` is straight-forward. The token returned can be used to set the `IdPointConfiguration` later. Note that the opposite order is also possible. Alternatively, it is possible to use predefined tokens.

Request

```bash
{    "axtid:SetIdPoint": {        "IdPoint": \[            {                "token": "idpoint1",                "Name": "Name1",                "Area": "Area1",                "MinPINSize": 4,                "MaxPINSize": 4,                "EndOfPIN": "#",                "HeartbeatInterval": "PT10M",                "Location": "Loc1",                "Timeout": "PT3S",                "Action": "Action1",                "Description": "Desc1"            }        \]    }}
```

Request

```bash
<axtid:SetIdPoint>    <axtid:IdPoint token="token">        <axtid:Action>Action1</axtid:Action>        <axtid:Area>Area1</axtid:Area>        <axtid:Description>Desc1</axtid:Description>        <axtid:EndOfPin>#</axtid:EndOfPin>        <axtid:HeartbeatInterval>PT10M</axtid:HeartbeatInterval>        <axtid:Location>Loc1</axtid:Location>        <axtid:MaxPINSize>4</axtid:MaxPINSize>        <axtid:MinPINSize>4</axtid:MinPINSize>        <axtid:Name>Name1</axtid:Name>        <axtid:Timeout>PT3S</axtid:Timeout>    </axtid:IdPoint></axtid:SetIdPoint>
```

### Configuring reader hardware

Hardware configuration of the IdPoint is done in the `IdPointConfiguration` structure. It consists of `token`, `DeviceUUID`, `Configuration` and `IdDataConfiguration`. These configuration fields are described in turn below

#### DeviceUUID

An IdPoint is bound to a specific hardware unit using the `DeviceUUID` field. When setting an IdPointConfiguration with an empty `DeviceUUID`field, the field will be filled in with the UUID of the device to which the request is made. This will bind the configuration to that specific unit. For more information about the UUID field, see [UUID](/vapix/physical-access-control/#uuid).

#### Configuration structure

The `Configuration` data structure describes the common hardware devices connected to the door controller and their connection types, see table. Some of the settings generate new `IoUsers` that can be bound to physical pins using `axisio:SetIoAssignment`, see [I/O assignment service guide](/vapix/physical-access-control/io-assignment-service/#io-assignment-service-guide).

When issuing a call to `SetIdPointConfiguration` without a value for all parameters, one of two things will happen:

-   If a structure with the same token already exists in the database, only the supplied parameters will be replaced.
-   If a structure with the specified token does not exist in the database, any missing parameters will be replaced with default values (the first value in each list of possible values).

Available parameters in the Configuration data structure.

| Parameter | Valid values | Description |
| --- | --- | --- |
| `IdPoint.Reader.Type` | `None`  
`Wiegand`  
`RS-485FD`  
`RS-485HD`  
`TCPIP` | The low-level protocol to use for the connected reader. If the IdPoint only has connected Request to EXit (REX) devices, `None` can be used. Use `RS-485HD` for Aperio readers, see section [Aperio doors](/vapix/physical-access-control/peripherals/#aperio-doors). Use `TCPIP` for Smart Intego readers, see section Smart Intego Doors. |
| `IdPoint.RS-485HD.Protocol` | `None`  
`AADP`  
`OSDP`  
`HADP` | Protocol to use for RS-485FD. Valid when `Reader.Type` is RS-485FD |
| `IdPoint.TCPIP.Protocol` | `SmartIntego` | Protocol to usefor TCPIP. Valid when `Reader.Type` is TCPIP. |
| `IdPoint.TCPIP.Address` | Dotted—decimal number | Address of TCPIP reader/gateway in dotted—decimal format, for example 192.168.123.132 |
| `IdPoint.TCPIP.Port` | Decimal number | Port number of TCPIP reader/gateway in decimal format. Use 2010 for Smart Intego readers. |
| `IdPoint.LED.Type` | `None`  
`SingleLED`  
`DualLED` | Specify the reader’s LED configuration: `None` if reader does not have any LED, `SingleLED` if the reader has one LED (e.g. red or green) or `DualLED` if the reader has two LEDs (e.g. both green and red). |
| `IdPoint.LED.ActiveLevel` | `ActiveLow`  
`ActiveHigh` | Applicable if the reader has LEDs configured by `IdPoint.LED.Type`. Select `ActiveLow` if closed circuit will activate the LEDs. Select `ActiveHigh` if opened circuit will activate the LEDs. |
| `IdPoint.Beeper.Type` | `None`  
`ActiveLow`  
`ActiveHigh` | Specify the reader’s beeper configuration:Select `None` if reader does not have any beeper. Select `ActiveLow` if closed circuit will activate the beeper. Select `ActiveHigh` if opened circuit will activate the beeper. |
| `IdPoint.Tampering.Type` | `None`  
`ActiveLow`  
`ActiveHigh`  
`SupervisedActiveLow`  
`SupervisedActiveHigh` | Specify the reader’s tampering detection:Select `None` if reader does not have any tampering detection. Select `ActiveLow` if closed circuit will trigger the tampering detection. Select `ActiveHigh` if opened circuit will trigger the tampering detection. Select `SupervisedActiveLow` to trigger tampering detection if the target voltage for the supervised low state is reached. Select `SupervisedActiveHigh` to trigger tampering detection if the target voltage for the supervised high state is reached. |
| `IdPoint.Tampering.SupervisedCut` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the cut (open circuit) state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.Tampering.SupervisedShort` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the short circuit state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.Tampering.SupervisedHigh` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the high state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.Tampering.SupervisedLow` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the low state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.REX.Type` | `None`  
`ActiveLow`  
`ActiveHigh`  
`SupervisedActiveLow`  
`SupervisedActiveHigh`  
`RS-485HD` | Specify if one or more REX devices are connected:Select None if no REX device is connected. Select ActiveLow if activating the REX device closes the circuit. Select ActiveHigh if activating the REX device opens the circuit. Select SupervisedActiveLow to trigger tampering detection if the target voltage for the supervised low state is reached. Select SupervisedActiveHigh to trigger tampering detection if the target voltage for the supervised high state is reached. Select RS-485HD if using Aperio doors. |
| `IdPoint.REX.SupervisedCut` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the cut (open circuit) state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.REX.SupervisedShort` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the short circuit state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.REX.SupervisedLow` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the low state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.REX.SupervisedHigh` | mV | Applicable if `IoMode` in `IoAssignment` is set to `supervised`, see section [Assign I/O:s to services](/vapix/physical-access-control/io-assignment-service/#assign-io-to-services). Target voltage (in millivolts) for the high state when using supervised inputs. End of line resistors must be used. |
| `IdPoint.Keypress.Types` | `Auto`  
`4bit`  
`6bitEData`  
`8bit`  
`8bitInvLow`  
`8bitInvHigh`  
`8bitDF750` | Selecting `Auto` here usually works, but if a keypress format is not recognized correctly it may be necessary to set it explicitly. |
| `IdPoint.Hardware.Address` | Hexadecimal number | Applies to both Aperio readers and Smart Intego readers. The reader’s hardware address. A six-digit hexadecimal number for Aperio readers, for example A0B1C2 and a hexadecimal number for Smart Intego readers, for example 0x200. When used to specify the OSDP/HADP reader address, i.e. when the `IdPoint.Hardware.DetectionMode` parameter is set to `Manual`, the hexadecimal number should be between 0 and 7E. Numbers outside of this interval will be interpreted as 0. Note that AXIS A1610 and AXIS A1210 support up to two OSDP readers per port. AXIS A1601 supports one OSDP reader per port. |
| `IdPoint.Hardware.DetectionMode` | `Auto` `Manual` | Applies only to OSDP and HADP readers. If set to `Auto`, the driver will automatically scan all addresses to find the connected reader. If set to `Manual`, the address of the connected reader is specified using the `IdPoint.Hardware.Address` parameter. The default value is `Auto`. The `Auto` mode can be used reliably only when there is only a single reader connected to the port. OSDP multi-drop setups must use the `Manual` mode. |
| `IdPoint.Hardware.Id` | string | Applies to Smart Intego readers. The "phi" string of a Smart Intego reader device. See section Smart Intego doors. |
| `IdPoint.Hub.Hardware.Address` | Hexadecimal number | Applies to Smart Intego readers. The gateway’s device address, for example: 0x100. See section Smart Intego doors. |
| `IdPoint.SecureChannel.KeyToken` | The token | See section [Keystore service guide](/vapix/physical-access-control/keystore-service/#keystore-service-guide) |
| `IdPoint.SecureChannel.KeyType` | `KeyBase`  
`KeyMaster`  
`None` | `KeyBase` is a cryptographic key used to encrypt the communication between the OSDP reader and the controller.  
  
`KeyMaster` is the secure cryptographic channel master key, used with a cUID to generate a unique secure channel base key for each link between a panel and a reader. |
| `IdPoint.Status.BatteryAlarm` | `True`  
`Low`  
`Hardware address` | Applicable if `IsProperty` is `true`,`True` if battery fault is active.  
  
`Low` if battery is not OK.  
  
`Hardware address` of the device with battery alarm. |
| `IdPoint.Status.RadioDisturbance` | `True`  
`Radio disturbance detected`  
`Hardware address` | Applicable if `IsProperty` is `true`,`True` if there is radio disturbance.  
  
`Radio disturbance detected` if radio is not OK.  
  
`Hardware address` of the device with radio disturbance. |
| `IdPoint.Status.SecureChannel` | string | Applicable if `IsProperty` is `true`,Indicates the status of the IdPoint device and is only sent for IdPoint readers using the OSDP protocolHuman readable status of the secure channel. |
| `IdPoint.Status.Device` | TrueFalse | Applicable if `IsProperty` is `true`,`True` if the device responds to communication. |
| `IdPoint.Whitelist.IdData.Name` | string | A credential may contain several `IdData` fields. Valid examples includes `PIN` and `Card`. Which `IdData` field to use for which whitelist purposes must be identified beforehand. This information is then stored in a parameter `IdPoint.Whitelist.IdData.Name` and the default value is `Card`.Note> Parameter only applicable to [SmartIntego doors](/vapix/physical-access-control/peripherals/#smartintego-doors). |

**Implementing mV**

It is recommended that you place a supervised resistor-circuit as close to the monitoring device as possible.

![supervised resistor-circuit](/assets/images/idpoint-service.t10178482-3ed0f3cf639fbe74d9dc5831cb4a920b.svg)

For example, the circuit schema for serial first is used for supervised settings specifically for AXIS A1601 Network Door Controller, with the mV values listed in the first table below.

On the other hand, the circuit schema for parallel first is used for the supervised settings of the mV values, and refers to the column **Parallel 22k 4k7** in the second table below.

![Wiegand connection alternatives](/assets/images/idpoint-service.t10178483-94c89cb676858b6d3159c2bdd7e7ad4a.svg)

This table showcases the mV values for an open collector output with 1k pull-up to 5V (HID RK40) when using `IdPointConfiguration.Tampering`

| Level | Serial 1k | Serial 2k2 | Serial 4k7 | Serial 10k | Parallel 22k 2k7 |
| --- | --- | --- | --- | --- | --- |
| `SupervisedCut` | 2796 | 2796 | 2796 | 2796 | 2796 |
| `SupervisedHigh` | 2517 | 3308 | 3894 | 4132 | 3788 |
| `SupervisedLow` | 331 | 563 | 925 | 1407 | 814 |
| `SupervisedShort` | 0 | 0 | 0 | 0 | 0 |

This table showcases the mV values for a basic switch when using either `IdPointConfiguration.REX` or `DoorConfiguration.Doormonitor`.

| Level | Serial 1k | Serial 2k2 | Serial 4k7 | Serial 10k | Parallel 22k 2k7 |
| --- | --- | --- | --- | --- | --- |
| `SupervisedCut` | 2796 | 2796 | 2796 | 2796 | 2796 |
| `SupervisedHigh` | 449 | 827 | 1336 | 1824 | 1888 |
| `SupervisedLow` | 244 | 487 | 864 | 1359 | 760 |
| `SupervisedShort` | 0 | 0 | 0 | 0 | 0 |

#### Configuring a Wiegand reader

This is a configuration for a Wiegand reader (e.g. HID RK40 with default parameters). It has the following features:

-   Wiegand output
-   A single LED that switches between red and green.
-   The LED turns to green when grounded.
-   A beeper which sounds when grounded.
-   A tampering detection line which indicates tampering when grounded.

```bash
{    "IdPointConfiguration": \[        {            "token": "",            "DeviceUUID": "",            "IdDataConfiguration": \[""\],            "Configuration": \[                { "Name": "IdPoint.Reader.Type", "Value": "Wiegand" },                { "Name": "IdPoint.LED.Type", "Value": "SingleLED" },                { "Name": "IdPoint.LED.ActiveLevel", "Value": "ActiveLow" },                { "Name": "IdPoint.Beeper.Type", "Value": "ActiveLow" },                { "Name": "IdPoint.Tampering.Type", "Value": "ActiveLow" }            \]        }    \]}
```

```bash
<axtid:IdPointConfiguration token="">    <axtid:Configuration>        <axconf:Name>IdPoint.Reader.Type</axconf:Name>        <axconf:Value>Wiegand</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.LED.Type</axconf:Name>        <axconf:Value>SingleLED</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.LED.ActiveLevel</axconf:Name>        <axconf:Value>ActiveLow</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.Beeper.Type</axconf:Name>        <axconf:Value>ActiveLow</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.Tampering.Type</axconf:Name>        <axconf:Value>ActiveLow</axconf:Value>    </axtid:Configuration>    <axtid:DeviceUUID />    <axtid:IdDataConfiguration /></axtid:IdPointConfiguration>
```

Note that `IdDataConfiguration` is set to empty in this request since it will be covered later. Note also that `DeviceUUID` is set to empty here. This will be replaced by the UUID of the device to which the request is made.

Once this configuration has been set together with its corresponding `IdPoint`, some `IoUsers` will exist on the unit to which the request was made. See [I/O assignment service guide](/vapix/physical-access-control/io-assignment-service/#io-assignment-service-guide) for how to assign these to physical pins.

#### Configuring an open supervised device protocol (OSDP) reader

For an OSDP reader, it is only necessary to assign the serial pins since LED, beeper, tampering information etc. is sent using serial commands. Here we are assuming a half-duplex RS485 connection.

```bash
{    "IdPointConfiguration": \[        {            "token": "",            "DeviceUUID": "",            "IdDataConfiguration": \[""\],            "Configuration": \[                { "Name": "IdPoint.Reader.Type", "Value": "RS-485HD" },                { "Name": "IdPoint.RS-485HD.Protocol", "Value": "OSDP" }            \]        }    \]}
```

```bash
<axtid:IdPointConfiguration token="">    <axtid:Configuration>        <axconf:Name>IdPoint.Reader.Type</axconf:Name>        <axconf:Value>RS-485HD</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.RS-485HD.Protocol</axconf:Name>        <axconf:Value>OSDP</axconf:Value>    </axtid:Configuration>    <axtid:DeviceUUID />    <axtid:IdDataConfiguration /></axtid:IdPointConfiguration>
```

The RS-485HD `IoUser` can now be assigned using the I/O Assignment service, see [I/O assignment service](/vapix/physical-access-control/io-assignment-service/).

#### Configuring an open supervised device protocol (OSDP) secure channel reader

Step1: Start by adding a key to the key store, by issuing the following to the `axkey` service:

```bash
{    "axkey:SetEncryptionKey": {        "axkey:EncryptionKey": \[            {                "Name": "My key name",                "Description": "My key description",                "token": "my\_key",                "Key": "00010203040506070809101112131415"            }        \]    }}
```

```bash
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:key="http://www.axis.com/vapix/ws/KeyStore">    <soap:Header />    <soap:Body>        <key:SetEncryptionKey>            <!--1 or more repetitions:-->            <key:EncryptionKey token="my\_key">                <key:Key>00010203040506070809101112131415</key:Key>                <!--Optional:-->                <key:Name>My key name</key:Name>                <!--Optional:-->                <key:Description>My key description</key:Description>            </key:EncryptionKey>        </key:SetEncryptionKey>    </soap:Body></soap:Envelope>
```

Step 2: Continue by configuring an IdPoint. Please refer to the `IdPoint` service for details:

```bash
{    "axtid:SetIdPoint": {        "IdPoint": \[            {                "Name": "My OSDP SC IdPoint",                "Action": "Access",                "token": "osdp\_sc\_idpoint",                "MaxPINSize": 4,                "MinPINSize": 4            }        \]    }}
```

```bash
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:idp="http://www.axis.com/vapix/ws/IdPoint">    <soap:Header />    <soap:Body>        <idp:SetIdPoint>            <!--1 or more repetitions:-->            <idp:IdPoint token="osdp\_sc\_idpoint">                <idp:Name>My OSDP SC IdPoint</idp:Name>                <!--Optional:-->                <idp:Description />                <idp:Location />                <idp:Area />                <!--Optional:-->                <idp:Action>Access</idp:Action>                <!--Optional:-->                <idp:MinPINSize>4</idp:MinPINSize>                <!--Optional:-->                <idp:MaxPINSize>4</idp:MaxPINSize>                <!--Optional:-->                <idp:EndOfPIN />                <idp:Timeout />                <idp:HeartbeatInterval />            </idp:IdPoint>        </idp:SetIdPoint>    </soap:Body></soap:Envelope>
```

Once the IdPoint is set, add an `IdPointConfiguration`, using the same token as in the call to `tid:SetIdPoint`. Note that there are further parameters for `SetIdPointConfiguration` - only those relevant to OSDP secure channel configuration are shown here. Please refer to `IdPoint` Service API for details.

```bash
{    "axtid:SetIdPointConfiguration": {        "IdPointConfiguration": \[            {                "token": "osdp\_sc\_idpoint",                "Configuration": \[                    {                        "Name": "IdPoint.Reader.Type",                        "Value": "RS-485HD"                    },                    {                        "Name": "IdPoint.RS-485HD.Protocol",                        "Value": "OSDP"                    },                    {                        "Name": "IdPoint.SecureChannel.KeyToken",                        "Value": "my\_key"                    },                    {                        "Name": "IdPoint.SecureChannel.KeyType",                        "Value": "KeyBase"                    }                \]            }        \]    }}
```

```bash
<soap:Envelope    xmlns:soap="http://www.w3.org/2003/05/soap-envelope"    xmlns:idp="http://www.axis.com/vapix/ws/IdPoint"    xmlns:con="http://www.axis.com/vapix/ws/Config">    <soap:Header />    <soap:Body>        <idp:SetIdPointConfiguration>            <!--1 or more repetitions:-->            <idp:IdPointConfiguration token="osdp\_sc\_idpoint">                <idp:DeviceUUID />                <!--Zero or more repetitions:-->                <idp:IdDataConfiguration />                <!--Zero or more repetitions:-->                <idp:Configuration>                    <con:Name>IdPoint.Reader.Type</con:Name>                    <con:Value>RS-485HD</con:Value>                </idp:Configuration>                <idp:Configuration>                    <con:Name>IdPoint.RS-485HD.Protocol</con:Name>                    <con:Value>OSDP</con:Value>                </idp:Configuration>                <idp:Configuration>                    <con:Name>IdPoint.SecureChannel.KeyToken</con:Name>                    <con:Value>my\_key</con:Value>                </idp:Configuration>                <idp:Configuration>                    <con:Name>IdPoint.SecureChannel.KeyType</con:Name>                    <con:Value>KeyBase</con:Value>                </idp:Configuration>            </idp:IdPointConfiguration>        </idp:SetIdPointConfiguration>    </soap:Body></soap:Envelope>
```

The `IdPoint` is now configured to use the key with the token `my_key` from the keystore (the value of this key is 00010203040506070809101112131415). We have also specified that we will use this key as a base key (no diversification using cUID). Valid values for KeyType are `KeyBase`, `KeyMaster` or `None`. Once the steps above have been completed, the rest of the setup may be done as usual, to get a working system (IO assignments, doors, access points, credentials and users).

#### Configuring an OSDP reader for a multidrop setup

For a multi-drop setup, each IdPointConfiguration shall be set to manual detection mode and specify the OSDP address of the corresponding reader.

Example for reader with address 0:

```bash
{    "IdPointConfiguration": \[        {            "token": "",            "DeviceUUID": "",            "IdDataConfiguration": \[""\],            "Configuration": \[                {                    "Name": "IdPoint.Reader.Type",                    "Value": "RS-485HD"                },                {                    "Name": "IdPoint.RS-485HD.Protocol",                    "Value": "OSDP"                },                {                    "Name": "IdPoint.Hardware.Address",                    "Value": "0"                },                {                    "Name": "IdPoint.Hardware.DetectionMode",                    "Value": "Manual"                }            \]        }    \]}
```

All IdPointConfigurations shall be assigned to the same serial port to which the readers are connected. See the [I/O assignment service guide](/vapix/physical-access-control/io-assignment-service/#io-assignment-service-guide) on how to assign multiple IoUsers to the same I/O.

Note that AXIS A1610 and AXIS A1210 support up to two OSDP readers per port. AXIS A1601 supports one OSDP reader per port.

#### Configuring a REX device

A REX device can be represented as a standalone `IdPoint` or be added to an `IdPoint` that already has a reader. It is possible to connect an unlimited amount of REX devices to the same `IdPoint` using the I/O Assignment service, see [I/O assignment service guide](/vapix/physical-access-control/io-assignment-service/#io-assignment-service-guide).

Here is an example of an `IdPoint` that contains only a REX device. The REX device is active when the circuit is closed.

```bash
{    "IdPointConfiguration": \[        {            "token": "",            "DeviceUUID": "",            "IdDataConfiguration": \[""\],            "Configuration": \[                { "Name": "IdPoint.Reader.Type", "Value": "None" },                { "Name": "IdPoint.REX.Type", "Value": "ActiveLow" }            \]        }    \]}
```

```bash
<axtid:IdPointConfiguration token="">    <axtid:Configuration>        <axconf:Name>IdPoint.Reader.Type</axconf:Name>        <axconf:Value>None</axconf:Value>    </axtid:Configuration>    <axtid:Configuration>        <axconf:Name>IdPoint.REX.Type</axconf:Name>        <axconf:Value>ActiveLow</axconf:Value>    </axtid:Configuration>    <axtid:DeviceUUID />    <axtid:IdDataConfiguration /></axtid:IdPointConfiguration>
```

When this has been set, a REX `IoUser` has been created for this `IdPoint` that can be assigned to one or more physical pins.

### Setting up access card formats

The `IdDataConfiguration` data structure specifies access card formats. The structure contains a mapping of the access card’s binary data into key/value pairs as well as the binary data’s complete bit length. The mapping describes how to interpret the binary data bits.

Some access card formats are provided by default, for example the Wiegand 26-bit format (H10301). Use `axtid:GetIdDataConfigurationList` to retrieve the list of available configurations.

The `IdPoint/Request/IdData` event is sent when a person swipes his access card. The event contains raw data from the card in the `Card` field and the bit length of the raw data in the `BitCount` field. If the `IdPoint` has no assigned `IdDataConfiguration`, or if no assigned `IdDataConfiguration` matches the bit length, the event contains only the `Card` and `BitCount` fields.

#### IdDataFieldMap data structure {guide-id-data-field-map-data-structure}

The general format for the `IdDataFieldMap` is `<Format>, <Format>, ...<br/><br/>`

where `<Format>` is described in the table below.

Available data field formats

| Format | Meaning | Example |
| --- | --- | --- |
| N | Bit N | 7 |
| M-N | Bit M-N | 13–16 |
| dB...B | Constant binary data | b0110 |
| xX...X | Constant hexadecimal data | xF7D |

All the chunks will then be added together to form the value of the map. The most common case will be to use a single `M-N` format for each `IdDataFieldMap`. The constant data is only useful for adapting to legacy systems.

The table below shows the available encodings.

Available data encodings

| Encoding | Description | Length limit |
| --- | --- | --- |
| BinLE2hex | Little-endian, encoded to lowercase hexadecimal | None |
| BinLEIBO2hex | Inversed byte order Little-endian, encoded to lowercase hexadecimal | None |
| BinBE2hex | Big-endian, encoded to lowercase hexadecimal | None |
| BinBEIBO2hex | Inversed byte order Big-endian, encoded to lowercase hexadecimal | None |
| Bin2Base64 | Base64 encoded | None |
| BinIBO2Base64 | Inversed byte order Base64 encoded | None |
| BinLE2Int | Little-endian, encoded to integer | 64bit |
| BinLEIBO2Int | Inversed byte order Little-endian, encoded to integer | 64bit |
| BinBE2Int | Big-endian, encoded to integer | 64bit |
| BinBEIBO2Int | Inversed byte order Big-endian, encoded to integer | 64bit |

#### IdDataConfiguration example

This section is an example for the H10301 format.

The table shows the data field mapping. Note that the `CardNrHex` is supplied as an example to show that it is possible to use the same bits but with different encodings (compare with `CardNr`).

H10301 data field mapping

| Map | Value | Encoding |
| --- | --- | --- |
| EvenParity | 1 | BinLE2Int |
| FacilityCode | 2–9 | BinLE2Int |
| CardNr | 10–25 | BinLE2Int |
| CardNrHex | 10–25 | BinLE2hex |
| OddParity | 26 | BinLE2Int |

Let us assume that the 26 bits received from the reader are:

`1 0000 0000 0010 0111 1110 0101 1`

This will generate key/value pairs as described in the table below. Note that the complete raw data is always automatically encoded as hexadecimal and supplied in the `Card` field.

Key/Value pairs example

| Name | Value |
| --- | --- |
| Card | 02004fcb |
| EvenParity | 1 |
| FacilityCode | 0 |
| CardNr | 10213 |
| CardNrHex | 27e5 |
| OddParity | 1 |
| BitCount | 26 |

The complete `axtid:SetIdDataConfiguration` request would look like:

Request

```bash
{    "axtid:SetIdDataConfiguration": {        "IdDataConfiguration": \[            {                "token": "",                "InputBitlength": 26,                "Name": "IdDataConfig example",                "IdDataFieldMap": \[                    {                        "Map": "1-26",                        "Name": "FullCard",                        "Encoding": "BinLE2hex"                    },                    {                        "Map": "1",                        "Name": "ParityEven",                        "Encoding": "BinLE2Int"                    },                    {                        "Map": "2-9",                        "Name": "FacilityCode",                        "Encoding": "BinLE2Int"                    },                    {                        "Map": "10-25",                        "Name": "CardNr",                        "Encoding": "BinLE2Int"                    },                    {                        "Map": "10-25",                        "Name": "CardNrHex",                        "Encoding": "BinLE2hex"                    },                    {                        "Map": "26",                        "Name": "ParityOdd",                        "Encoding": "BinLE2Int"                    }                \],                "Description": "Test Description"            }        \]    }}
```

Request

```bash
<axtid:SetIdDataConfiguration>    <axtid:IdDataConfiguration token="">        <axtid:Description>Test Description</axtid:Description>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2hex</axtid:Encoding>            <axtid:Map>1-26</axtid:Map>            <axtid:Name>FullCard</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2Int</axtid:Encoding>            <axtid:Map>1</axtid:Map>            <axtid:Name>ParityEven</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2Int</axtid:Encoding>            <axtid:Map>2-9</axtid:Map>            <axtid:Name>FacilityCode</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2Int</axtid:Encoding>            <axtid:Map>10-25</axtid:Map>            <axtid:Name>CardNr</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2hex</axtid:Encoding>            <axtid:Map>10-25</axtid:Map>            <axtid:Name>CardNrHex</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:IdDataFieldMap>            <axtid:Encoding>BinLE2Int</axtid:Encoding>            <axtid:Map>26</axtid:Map>            <axtid:Name>ParityOdd</axtid:Name>        </axtid:IdDataFieldMap>        <axtid:InputBitlength>26</axtid:InputBitlength>        <axtid:Name>IdDataConfig example</axtid:Name>    </axtid:IdDataConfiguration></axtid:SetIdDataConfiguration>
```

### Getting card data from a reader

To get information about the last swiped card or other type of user token accepted by the reader, use the `axtid:GetLastCredential` API call. This will also be parsed using the `IdDataConfiguration`.

Request

```bash
{    "axtid:GetLastCredential": {        "Token": "idpoint1"    }}
```

Request

```bash
<axtid:GetLastCredential>    <axtid:Token>idpoint1</axtid:Token></axtid:GetLastCredential>
```

Response

```bash
{    "IdData": \[        { "Name": "FullCard", "Value": "02004fcb" },        { "Name": "ParityEven", "Value": "1" },        { "Name": "FacilityCode", "Value": "0" },        { "Name": "CardNr", "Value": "10213" },        { "Name": "CardNrHex", "Value": "27e5" },        { "Name": "ParityOdd", "Value": "1" },        { "Name": "Card", "Value": "02004fcb" },        { "Name": "BitCount", "Value": "26" }    \]}
```

Response

```bash
<axtid:IdData Name="EvenParity" Value="1"></axtid:IdData><axtid:IdData Name="FacilityCode" Value="0"></axtid:IdData><axtid:IdData Name="CardNr" Value="10213"></axtid:IdData><axtid:IdData Name="CardNrHex" Value="27e5"></axtid:IdData><axtid:IdData Name="OddParity" Value="1"></axtid:IdData><axtid:IdData Name="Card" Value="02004fcb"></axtid:IdData><axtid:IdData Name="BitCount" Value="26"></axtid:IdData>
```

The `Card` and `BitCount` fields are always included, also if they are not in the `IdDataConfiguration`.

### Sending activities from a remote device

Axis physical access control products support IP based remote activity input devices such as IP card readers , License Plate Recognition cameras and Wireless sensors via the Indicate Remote Activities API. This provide a way for most IP devices to simulate activities such as presenting credentials or REX (Request to exit) inputs such as Wiegand, OSDP (Open Supervised Device Protocol) or via wireless sensors.

One typical use-case is license plate recognition, where an Axis camera sends the license plate number to the Access Controller, which in turn decides if the vehicle should be granted access. Further examples can be a remote indication of card swipes, PIN inputs or REX button-presses.

Calling the IndicateRemoteActivities API triggers the same type of endpoint events as a user swiping a card against a card reader or pushing a REX button that is directly connected to and configured by the Access Controller.

For each activity, two IdPoint events are sent. The first event is `tns1:IdPoint/tnsaxis:Activity` for all supported activities. Params are mandatory for Activity-type `Card` and `PIN`, but not allowed for `REX`. For Activity-type `PIN` a param named ‘PIN’ is mandatory.

For each activity, two IdPoint events are sent, which are the same amount as for the wired Wiegand/OSDP reader.

The first event is `tns1:IdPoint/tnsaxis:Activity` for all supported activities.

The Reason field for this event is:

-   CardPresented for activity-type `Card`
-   REX for activity-type `REX`
-   CodeEntered for activity-type `PIN`

The second event for each activity is:

-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:IdData` for activity-type `Card`
-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:REX` for activity-type `REX`
-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:PIN` for activity-type `PIN`

**Examples**

For more examples on how to use remote activities, see [Indicating remote activities](/vapix/physical-access-control/peripherals/#indicating-remote-activities).

#### Considerations

A hardware configuration needs to be in place due to the IndicateRemoteActivities-request body requiring a valid IdPoint-token to be able to send the IdPoint events.

For detailed information about configuring the hardware, see AXIS A1001 and AXIS Entry Manager User Manual.

The second step is the access decision that will be triggered by the `tns1:IdPoint/tnsaxis:Request` event.

To get a positive access decision the following criteria need to be met:

1.  The Name/Value pairs of the params in the API request need to match the Name/Value pairs of the `IdData` in a credential and have the same ordering. This credential needs to be associated with an AccessProfile, AccessPoint and IdPoint, that matches the ID and AuthenticationProfile as seen in [Setting the credential](/vapix/physical-access-control/access-control-service/#setting-the-credential).
    
2.  Each Name in the Params of the IndicateRemoteActivities request must match the `IdDataName` in the `IdFactor` list of an AuthenticationProfile that is associated with either the Credential, AccessPoint or AccessProfile mentioned above. For additional information, see [Setting the access point](/vapix/physical-access-control/access-control-service/#setting-the-access-point), [Setting the access profile](/vapix/physical-access-control/access-control-service/#setting-the-access-profile) and [Retrieve default configuration](/vapix/physical-access-control/access-control-service/#retrieve-default-configuration) in the Access Control Service Guide.
    

If a `Card` and a `PIN` is expected from physical access control system all the following parameters are granted access:

-   `IndicateRemoteActivities` (Card) + `IndicateRemoteActivities` (PIN) (Separate API requests)
-   `IndicateRemoteActivities` (Card + PIN) (Same API request)
-   `IndicateRemoteActivities` (PIN + Card) (Same API request)

But this can be denied access:

-   `IndicateRemoteActivities` (PIN) + `IndicateRemoteActivities` (Card) (Separate API requests)

## IdPoint service API

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

The IdPoint service handles identification points (IdPoints or IDP:s), which are typically card readers with keypads for pin code entry, but which could also be biometric readers. A Request-for-Exit button can also be seen as an IdPoint. Multiple physical readers/Identification Points can be handled by a service.

Use `GetIdPointInfoList` to get the list of IdPoints with brief information and capabilities. Use `GetIdPointList` to get the list of IdPoints and their configurations.

The IdPoint service sends events when there is activity, when a card is presented or pin is entered, etc. An Access Controller typically subscribes to these events and takes appropriate actions, e.g. unlocks a door. The `FeedbackMessage` function is used by the Access Controller to give feedback or annunciations to the user.

The way the identification data is to be interpreted and sent is assumed to be configurable in a vendor-specific way. By default, the IdData Name "Card" should be used to send card data as a lower case hex string. Keypad input is sent as IdData Name "PIN" as string, PIN:s can be alfanumeric. REX request is sent as IdData Name "REX" with the value "Active".

The IdPoint generates events with IdData encoded as SimpleItem in the Data: section of the Notification. Additional IdData entries can be configured in a vendor-specific way.

Please refer to the ONVIF Access Control specification for generic operation guidelines and design principles behind ONVIF PACS services family.

### AxisConfig service

See [AxisConfig service](/vapix/physical-access-control/door-control-service/#axisconfig-service).

### Service capabilities

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

An ONVIF compliant device shall provide service capabilities in two ways:

-   With the `GetServices` method of the Device service when `IncludeCapability` is true. Please refer to the ONVIF Core Specification for more details.
-   With the `GetServiceCapabilities` method.

#### Service capabilities data structure

The service capabilities reflect optional functionality of a service. The information is static and does not change during device operation. The following capabilities are available:

-   **SetIdPoint**: True if SetIdPoint and SetIdPointList is supported.

#### GetServiceCapabilitiesCommand

This operation returns the capabilities of the IdPoint service.

An ONVIF compliant device which provides the IdPoint service shall implement this method.

GetServiceCapabilities command

-   Name: `GetServiceCapabilities`
-   Access Class: PRE\_AUTH

| Message name | Description |
| --- | --- |
| `GetServiceCapabilitiesRequest` | This message shall be empty. |
| `GetServiceCapabilitiesResponse` | This message contains:  
  
\- `Capabilities`: The capabilities of the IdPoint service`axtid:ServiceCapabilities Capabilities [1][1]` |

### IdPoint information

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### IdPointInfo data structure

The IdPointInfo type represents the IdPoint as a physical object. The structure contains information and capabilities of a specific idpoint instance. An ONVIF compliant device shall provide the following fields for each IdPoint instance:

-   **Token**: A service-unique identifier of the IdPoint.
-   **Name**: Name of the structure.
-   **Location**: Text description of location of IdPoint.
-   **Area**: The Area the IdPoint is in.
-   **Capabilities**: The capabilities for this IdPoint.

To provide more information, the device may include the following optional field:

-   **Description**: Description of the structure

#### IdPointCapabilities data structure

IdPointCapabilities reflect optional functionality of a particular physical entity. Different IdPoint instances may have different set of capabilities. This information may change during device operation, e.g. if hardware settings are changed. The following capabilities are available:

-   **Configurable**: True if the IdPoint settings can be modified
-   **SupportCard**: True if the IdPoint support reading Card data
-   **SupportPIN**: True if the IdPoint support PIN/keypad entry.
-   **SupportREX**: True if the IdPoint support/has a REX input.
-   **SupportBiometric**: True if the IdPoint support/has some kind of Biometric input.
-   **SupportedMessageTypes**: List of supported mime types for Message in FeedbackMessage function, e.g. text/plain - but may be an empty list.
-   **SupportedGraphicsTypes**: List of supported mime types for Graphics in FeedbackMessage function, e.g. image/jpeg, image/png - but may be an empty list.
-   **SupportedAudioTypes**: List of supported Audio formats in FeedbackMessage function, e.g. audio/basic, audio/mp3
-   **AdditionalCapabilities**: General list of supported features, currently not specified in the specification.

#### GetIdPointInfoList command

This operation requests a list of all of `IdPointInfo` items provided by the device. An ONVIF compliant device which provides the IdPoint service shall implement this method.

The returned list shall start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different StartReferences at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client shall not make any assumptions on StartReference contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference` can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls, and may be changed by device in each call.

The number of items returned shall not be greater than `Limit` parameter. If `Limit` parameter is not specified by the client, the device shall assume it unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

GetIdPointInfoList command

-   Name: `GetIdPointInfoList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetIdPointInfoListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetIdPointInfoListResponse` | This message contains  
  
\- `NextStartReference` `StartReference` to use in next call to get the following items. If absent, no more items to get.  
\- `IdPointInfo` List of `IdPointInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`axtid:IdPointInfo IdPointInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client need to start fetching from the beginning. |

#### GetIdPointInfo command

This operation request a list of `IdPointInfo` items matching the given tokens. An ONVIF-compliant device that provides IdPoint service shall implement this method.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned

GetIdPointInfo command

-   Name: `GetIdPointInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetIdPointInfoRequest` | This message contains:  
  
\- `Token`: Tokens of `IdPointInfo` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetIdPointInfoResponse` | This message contains:  
  
\- `IdPointInfo`: List of `IdPointInfo` items.  
  
`axtid:IdPointInfo IdPointInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgs`  
`ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

### IdPoint configuration

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### IdPoint data structure

The IdPoint type provides the full configuration for an id point.

The following fields are available:

-   **Token**: A service-unique identifier of the IdPoint.
-   **Name**: Name of the structure.
-   **Location**: Text description of location of IdPoint.
-   **Area**: The Area the IdPoint is in.
-   **Timeout**: Timeout between user interactions.
-   **HeartbeatInterval**: The time between heartbeat event updates. A time of 0 means no heartbeat events.

To provide more information, the device may include the following optional fields:

-   **Description**: Description of the structure.
-   **Action**: The default action the IdPoint want to do. If not set, assume "Access".
-   **MinPINSize**: Minimum number of characters in the PIN.
-   **MaxPINSize**: Maximum number of characters in the PIN.
-   **EndOfPIN**: String/character that ends a PIN and trigs sending of PIN.

#### GetIdPointList command

This operation requests a list of all of `IdPoint` items provided by the device. An ONVIF compliant device which provides the IdPoint service shall implement this method.

The returned list shall start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different `StartReference`:s at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference` can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls, and may be changed by device in each call.

The number of items returned shall not be greater than `Limit` parameter. If `Limit` parameter is not specified by the client, the device shall assume it unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

GetIdPointList command

-   Name: `GetIdPointList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetIdPointListResponse` | This message contains  
  
\- `NextStartReference` `StartReference` to use in next call to get the following items. If absent, no more items to get.  
\- `IdPointInfo` List of `IdPointInfo` items.  
  
`xs:string NextStartReference [0][1]`  
`axtid:IdPointInfo IdPointInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client need to start fetching from the beginning. |

#### GetIdPoint command

This operation request a list of `IdPoint` items matching the given tokens. An ONVIF-compliant device that provides IdPoint service shall implement this method.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned

GetIdPoint command

-   Name: `GetIdPoint`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointRequest` | This message contains:  
  
\- `Token`: Tokens of `IdPoint` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetIdPointResponse` | This message contains:  
  
\- `IdPointI`: List of `IdPoint` items.  
  
`axtid:IdPoint IdPoint [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgs`  
`ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetIdPoint command

Set a list of IdPoints. If the specified token in an IdPoint is empty, a new unique token is created by the service. If an IdPoint with the specified token already exist it will be updated. If the token does not exist, a new IdPoint is created. The list of supplied or created tokens is returned.

SetIdPoint command

-   Name: `SetIdPointList`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetIdPointRequest` | This message contains:  
  
\- `IdPoint`: The list of IdPoints to set.  
  
`axtid:IdPoint IdPoint [1][unbounded]` |
| `SetIdPointResponse` | This message contains:  
  
\- `Token`: Tokens of the added/updated IdPoints.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Receiver`  
`ter:ActionNotSupported`  
`ter:NotSupported` | Not allowed to create or modify the IdPoint |
| `env:Sender`  
`ter:InvalidArgs` |  |

#### RemoveIdPoint command

Remove the IdPoints specified by the Tokens.

RemoveIdPoint command

-   Name: `RemoveIdPoint`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveIdPointRequest` | This message contains:  
  
\- `Token`: Token of the IdPoint to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveIdPointResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Receiver`  
`ter:ActionNotSupported`  
`ter:NotSupported` | Not allowed to remove the IdPoint. |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:NotFound` | IdPoint not found. |

#### GetIdPointCapabilities command

GetIdPointCapabilities command

-   Name: `GetIdPointCapabilities`
-   Access Class: READ\_CAPABILITIES

| Message name | Description |
| --- | --- |
| `GetIdPointCapabilitiesRequest` | This message contains:  
  
\- `Token`: Token of the IdPoint to get the capabilities for`pt:ReferenceToken Token [1][1]` |
| `GetIdPointCapabilitiesResponse` | This message contains:  
  
\- `IdPointCapabilities`: The `IdPointCapabilities` matching the specified Token`axtid:IdPointCapabilities IdPointCapabilities [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender`  
`ter:InvalidArgVal`  
`ter:NotFound` | IdPoint not found |

### IdPoint feedback

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### IdPointFeedback data structure

The IdPointFeedback type enumerates the different type of feedback profiles. The actual implementation of these profiles is defined by the vendor and out of scope for ONVIF. Typically InvalidCredential, AccessDenied, Fault, Warning and Alarm would give "negative" feedback involving red LED and buzzer.

The following values are available:

-   **Other**: The feedback mode is specified in some other defined way.
-   **Idle**: Normal state - typically DoorLocked or DoorUnlocked is used instead (if the IdPoint controls a door).
-   **DoorLocked**: Indicates that the Door is locked.
-   **DoorUnlocked**: Indicates that the Door is unlocked.
-   **DoorOpenTooLong**: Indicates that the Door is open too long.
-   **DoorPreAlarmWarning**: Indicates that the Door soon is open too long.
-   **RequirePIN**: PIN (Personal Identification Number/Code) is required.
-   **RequireCard**: Card is required.
-   **Processing**: Processing in progress.
-   **InvalidCredential**: Credential is not valid.
-   **AccessGranted**: Access is granted.
-   **AccessDenied**: Access is denied.
-   **Ok**: Generic Ok indication
-   **Fault**: Generic fault indication
-   **Warning**: Generic Warning indication.
-   **Alarm**: Generic Warning indication.
-   **Custom**: Some custom mode.

#### FeedbackMessage command

Control how the `IdPoint` specified by the `Token` should give feedback.

FeedbackMessage command

-   Name: `FeedbackMessage`
-   Access Class: ACTUATE

| Message name | Description |
| --- | --- |
| `FeedbackMessageRequest` | This message contains:  
  
\- `Token`: Token of the `IdPoint` to control.  
\- `Profile` The `IdPointFeedBack` profile to use.  
\- `OtherProfile` If `Profile=Other`, this field should contain the extended profile information.  
\- `Message` Optional textual feedback message.  
\- `Graphics` Optional graphical message.  
\- `Audio` Optional audio message.  
  
`pt:ReferenceToken Token [1][1]`  
`axtid:IdPointFeedback Profile [1][1]`  
`xs:string OtherProfile [0][1]`  
`xs:string Message [0][1]`  
`tt:BinaryData Graphics [0][1]`  
`tt:BinaryData Audio [0][1]` |
| `FeedbackMessageResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | The specified token is not found. |

### IdPoint hardware configuration

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint%20)

#### IdPointConfiguration data structure

The device and hardware configuration for an IdPoint.

The following fields are available:

-   **Token**: IdPoint Id to use for set, remove and usage.
-   **DeviceUUID**: What device the IdPoint is on.
-   **IdDataConfiguration**: Reference to the IdDataConfigurations to use.
-   **Configuration**: Configuration for the IdPoint.

#### GetIdPointConfigurationList command

This operation requests a list of all of `IdPointConfiguration` items provided by the device. An ONVIF compliant device which provides the DoorControl service shall implement this method.

The returned list shall start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different StartReferences at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference` can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls, and may be changed by device in each call.

The number of items returned shall not be greater than Limit parameter. If Limit parameter is not specified by the client, the device shall assume it unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

GetIdPointConfigurationList command

-   Name: `GetIdPointConfigurationList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointConfigurationListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetIdPointConfigurationListResponse` | This message contains  
  
\- `NextStartReference` `StartReference` to use in next call to get the following items. If absent, no more items to get.  
\- `IdPointConfiguration` List of `IdPointConfiguration` items.  
  
`xs:string NextStartReference [0][1]`  
`axtid:IdPointConfiguration IdPointConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client need to start fetching from the beginning. |

#### GetIdPointConfiguration command

This operation request a list of `IdPointConfiguration` items matching the given tokens. An ONVIF-compliant device that provides IdPoint service shall implement this method.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned.

GetIdPointConfiguration command

-   Name: `GetIdPointConfiguration`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointConfigurationRequest` | This message contains:  
  
\- `Token`: Tokens of `IdPointConfiguration` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetIdPointConfigurationResponse` | This message contains:  
  
\- `IdPointConfiguration`: List of `IdPointConfiguration` items.  
  
`axtid:IdPointConfiguration IdPointConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetIdPointConfiguration command

Add/update a list of `IdPointConfiguration` items, the token in the `IdPointConfiguration` should typically refer to an existing `IdPoint`.

SetIdPointConfiguration command

-   Name: `SetIdPointConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `GeSetIdPointConfigurationRequest` | This message contains:  
  
\- `IdPointConfiguration`: The new versions of the `IdPointConfiguration` items.  
  
`axtid:IdPointConfiguration IdPointConfiguration [1][unbounded]` |
| `GetISetIdPointConfigurationResponse` | This message contains:  
  
\- `Token`: Tokens of the added/updated `IdPointConfiguration` items.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidIdPointConfigurationFault` |  |

#### RemoveIdPointConfiguration command

Remove the `IdPointConfiguration` items specified by the tokens. This is normally not needed, since when removing an `IdPoint`, the configuration is removed as well - although it's possible to create configurations without a corresponding `IdPoint`.

RemoveIdPointConfiguration command

-   Name: `RemoveIdPointConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveIdPointConfigurationRequest` | This message contains:  
  
\- `Token`: Token of the `IdPointConfiguration` items to remove.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveIdPointConfigurationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `IdPointConfiguration` not found. |

#### GetIdPointConfigurationInfo command

Get the `ConfigurationInfo` for a single `IdPoint` specified by the token.

GetIdPointConfigurationInfo command

-   Name: `GetIdPointConfigurationInfo`
-   Access Class: READ\_SYSTEM

| Message name | Description |
| --- | --- |
| `GetIdPointConfigurationInfoRequest` | This message contains:  
  
\- `Token`: Token of the `IdPoint` to get the `ConfigurationInfo` for`pt:ReferenceTokenToken [1][1]` |
| `GetIdPointConfigurationInfoResponse` | This message contains:  
  
\- `ConfigurationInfo`: Configuration info for the specified token`axconf:ConfigurationInfo ConfigurationInfo [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `IdPoint` not found. |

### Reader functions

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### GetLastCredential command

Get the last entered credential on this reader.

GetLastCredential command

-   Name: `GetLastCredential`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetLastCredentialRequest` | This message contains:  
  
\- `Token`: Token of the reader to get from`pt:ReferenceToken Token [1][1]` |
| `GetLastCredentialResponse` | This message contains:  
  
\- `IdData`:`tac:IdData IdData [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:ConfigurationNotFound` | Configuration not found. |

### IdDataConfigurations

An IdDataConfiguration describes how the binary data from a reader shall be parsed into IdData Name/Values.

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### IdDataConfiguration data structure

Specifies a configuration of how to map binary data input from a card reader or keypad to Request event messages.

The following fields are available:

-   **token**: Id used to reference the structure.
-   **Name**: Name of the configuration.
-   **Description**: Description of configuration.
-   **InputBitlength**: The number of bits the input data must have to use this configuration.
-   **IdDataFieldMap**: List of maps.

#### IdDataEncoding data structure

Specifies the different encoding of binary data possible.

The following values are available:

-   **Other**: For extendability, the encoding is specified some other way.
-   **BinLE2hex**: Binary data is encoded as hex-lowercase.
-   **BinBE2hex**: Binary data is encoded as hex-lowercase.
-   **Bin2Base64**: Binary data is encoded as base64.
-   **Bin2String**: Binary ASCII data is encoded as an URL encoded string.
-   **BinLEBCD2String**: Binary Little Endian BCD data is encoded as a numeric string.
-   **BinBEBCD2String**: Binary Big Endian BCD data is encoded as a string-
-   **BinLE2Int**: Binary data is encoded as an integer number, with Little Endian byte order.
-   **BinBE2Int**: Binary data is encoded as an integer number, with Big Endian byte order.
-   **BinLEIBO2hex**: Binary data with inversed byte order is encoded as hex-lowercase.
-   **BinBEIBO2hex**: Binary data with inversed byte order is encoded as hex-lowercase.
-   **BinIBO2Base64**: Binary data with inversed byte order is encoded as base64.
-   **BinIBO2String**: Binary with inversed byte order ASCII data is encoded as an URL encoded string.
-   **BinLEIBO2Int**: Binary data with inversed byte order is encoded as an integer number using Little Endian byte order.
-   **BinBEIBO2Int**: Binary data with inversed byte order encoded as an integer number using Big Endian byte order.

#### IdDataFieldMap data structure {api-id-data-field-map-data-structure}

The configuration for how binary card data read by the IdPoint should be mapped to an IdData name and value.

The following fields are available:

-   **Name**: Name of the IdData field (e.g. UserNbr, SiteCode, FacilityCode).
-   **Map**: Location of the field in the binary carddata (e.g. b0101,10-25,3,5,7,1,2,4,xFEDEBEDA,). First bit is bit 1, that is the first received over e.g. a wiegand port. The symbol 0bBBB (e.g. 0b111) indicates a sequence of constant binary digits BBB. The symbol 0xh..h indicates a constant sequence of hex digits h..h. The hex digits is interpreted with MSB first. The symbol sSSSS indicates a constant string SSSS, if you want the comma character ',' use ,0x2c, which is the ASCII representation of comma.
-   **Encoding**: How the resulting bits is encoded to a Value.

#### GetIdDataConfigurationList command

This operation requests a list of all of `IdDataConfiguration` items provided by the device. An ONVIF compliant device which provides the DoorControl service shall implement this method.

The returned list shall start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device internal identifier used to continue fetching data from the last position, and shall allow a client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different `StartReference`:s at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

An ONVIF compliant client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. Client shall not use the same reference more than once.

For example, the `StartReference` can be incrementing start position number or underlying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls, and may be changed by device in each call.

The number of items returned shall not be greater than `Limit` parameter. If `Limit` parameter is not specified by the client, the device shall assume it unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

GetIdDataConfigurationList command

-   Name: `GetIdDataConfigurationList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdDataConfigurationListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetIdDataConfigurationListResponse` | This message contains  
  
\- `NextStartReference` `StartReference` to use in next call to get the following items. If absent, no more items to get.  
\- `IdPointConfiguration` List of `IdPointConfiguration` items.  
  
`xs:string NextStartReference [0][1]`  
`axtid:IdPointConfiguration IdPointConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidStartReference` | `StartReference` is invalid or has timed out. Client need to start fetching from the beginning. |

#### GetIdDataConfiguration command

This operation request a list of `IdDataConfiguration` items matching the given tokens. An ONVIF-compliant device that provides IdPoint service shall implement this method.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned.

GetIdDataConfiguration command

-   Name: `GetIdDataConfiguration`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdDataConfigurationRequest` | This message contains:  
  
\- `Token`: Tokens of `IdDataConfiguration` items to get.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `GetIdDataConfigurationResponse` | This message contains:  
  
\- `IdDataConfiguration`: List of `IdDataConfiguration` items.  
  
`axtid:IdDataConfiguration IdDataConfiguration [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgs` `ter:TooManyItems` | Too many items were requested, see `MaxLimit` capability. |

#### SetIdDataConfiguration command

Set (adds or modifies) the supplied list of `IdDataConfiguration` items to the internal storage/database. If the token attribute is empty, a new unique token will be generated by the service. All supplied and generated tokens are returned.

SetIdDataConfiguration command

-   Name: `SetIdDataConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `SetIdDataConfigurationRequest` | This message contains:  
  
\- `IdDataConfiguration`: List of `IdDataConfiguration` items to set.  
  
`axtid:IdDataConfiguration IdDataConfiguration [1][unbounded]` |
| `SetIdDataConfigurationResponse` | This message contains:  
  
\- `Token`: List of the supplied and generated tokens.  
  
`pt:ReferenceToken Token [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:InvalidConfigurationFault` |  |

#### RemoveIdDataConfiguration command

Remove the specified `IdDataConfiguration` from storage.

RemoveIdDataConfiguration command

-   Name: `RemoveIdDataConfiguration`
-   Access Class: WRITE\_SYSTEM

| Message name | Description |
| --- | --- |
| `RemoveIdDataConfigurationRequest` | This message contains:  
  
\- `Token`: List of tokens for the `IdDataConfiguration` items to remove If list is empty, no configurations will be removed.  
  
`pt:ReferenceToken Token [1][unbounded]` |
| `RemoveIdDataConfigurationResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` |  |

### Feedback functions

axtid = [http://www.axis.com/vapix/ws/IdPoint](http://www.axis.com/vapix/ws/IdPoint)

#### GetFeedbackMessage command

Get the current feedback message status of an `IdPoint`.

GetFeedbackMessage command

-   Name: `GetFeedbackMessage`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetFeedbackMessageRequest` | This message contains:  
  
\- `Token`: Token of the `IdPoint` to get`pt:ReferenceToken Token [1][1]` |
| `GetFeedbackMessageResponse` | This message contains:  
  
\- `Profile`:`axtid:IdPointFeedback Profile [1][1]` |

| Fault codes | Description |
| --- | --- |
| `env:Sender` `ter:InvalidArgVal` `ter:NotFound` | `IdPoint` not found. |

### Secure Channel functions

**Enumeration: SecureChannel**

The type `SecureChannel` enumerates the different types of states for a secure channel.

The following values are available:

-   **Unknown**: Unknown state
-   **ConnectionLost**: The secure channel has stopped responding to communication
-   **ConnectionEstablished**: A working secure channel is active
-   **NotSupported**: Secure channel is not supported for this IdPoint
-   **NoKey**: No valid key found for this IdPoint

**SecureChannelStatus**

`SecureChannelStatus` reflects the status of Secure Channel for an `IdPoint`. If Secure Channel is configured and working, then Active will be True, otherwise Active will be False, and the Reason field will contain additional status information. The following fields are available:

-   **Active**: True if there is an active secure channel on the IdPoint
-   **Reason**: Status of the secure channel

#### GetSecureChannelStatus Command

Get the current secure channel status for an IdPoint.

-   Name: `GetSecureChannelStatus`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetSecureChannelStatusRequest` | This message contains:  
  
\- `Token`: Token of the IdPoint to getpt:ReferenceToken **Token \[1\]\[1\]** |
| `GetSecureChannelStatusResponse` | This message contains:  
  
\- `SecureChannelStatus`: Status of the specified IdPointaxtid:SecureChannelStatus **SecureChannelStatus \[1\]\[1\]** |

| Fault codes | Description |
| --- | --- |
| env:Senderter:InvalidArgVal ter:NotFound | IdPoint not found |

### WhiteList functions

WhiteList entries are uploaded one by one to their respective locks. The progress of the WhiteList entry upload for one or several locks, or the state of each of the WhiteList entries, can be requested using `axtid:GetIdPointWhiteList`. On a similar note, the progress of the WhiteList entry upload for all locks, or the state of all WhiteList entries, can be requested by using `axtid:GetIdPointWhiteListList`. The response presents all WhiteList entries of each lock and their states. The following states are available:

-   **Active**: An active WhiteList entry has been successfully uploaded to a lock and is currently in use.
-   **Invalid**: An invalid WhiteList entry cannot be uploaded to a lock because its data is not valid.
-   **PendingAdd**: A WhiteList entry that is not currently in use, but is waiting to be uploaded to a lock. Once it has been successfully uploaded, its state is changed to `Active`
-   **PendingRemove**: A WhiteList entry that is currently in use, but is waiting to be removed from a lock.

#### GetIdPointWhiteList command

This operation request a list of IdPointWhiteList items matching the given tokens.

The device shall ignore tokens it cannot resolve and may return an empty list if there are no items matching specified tokens.

If the number of requested items is greater than the max limit supported, a `TooManyItems` fault shall be returned.

-   Name: `GetIdPointWhiteList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointWhiteListRequest` | This message contains:  
  
\- `Token`: Tokens of `IdPointWhiteList` items to get.  
  
`pt: ReferenceToken Token [1][unbounded]` |
| `GetIdPointWhiteListResponse` | This message contains:  
  
\- `IdPointWhiteList`: List of `IdPointWhiteList` items.  
  
`axtid: IdPointWhiteList IdPointWhiteList [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| env: Senderter: InvalidArgster: TooManyItems | Too many items were requested, see `MaxLimit` capability. |

#### GetIdPointWhiteListList command

This operation requests a list of all of the `IdPointWhiteList` items provided by the device.

The returned list should start with the item specified by a `StartReference` parameter. If it is not specified by the client, the device shall return items starting from the beginning of the dataset.

`StartReference` is a device used for internal identifier and is used to fetch data from the last position, allowing the client to iterate over a large dataset in smaller chunks. The device shall be able to handle a reasonable number of different `StartReferences` at the same time and they must live for a reasonable time so that clients are able to fetch complete datasets.

A client shall not make any assumptions on `StartReference` contents and shall always pass the value returned from a previous request to continue fetching data. The client shall not use the same reference more than once.

For example, the `StartReference` can increment the start position number or the underlaying database transaction identifier.

The returned `NextStartReference` shall be used as the `StartReference` parameter in successive calls and may be changed by the device in each call.

The number of items returned shall not be greater than the `Limit` parameter. If the `Limit` parameter is not specified by the client, the device will assume that it is unbounded. The number of returned elements is determined by the device and may be less than requested if the device is limited in its resources.

-   Name: `GetIdPointWhiteListList`
-   Access Class: READ\_SYSTEM\_SENSITIVE

| Message name | Description |
| --- | --- |
| `GetIdPointWhiteListListRequest` | This message contains  
  
\- `Limit` Maximum number of entries to return. If not specified, or the number is higher than what the device supports, the number of items shall be determined by the device.  
\- `StartReference` Start returning entries from this start reference. If not specified, entries shall start from the beginning of the dataset.  
  
`xs:int Limit [0][1]`  
`xs:string StartReference [0][1]` |
| `GetIdPointWhiteListListResponse` | This message contains  
  
\- `NextStartReference` Which`StartReference`to use in the next call in order to get the following items. If absent, there are no more items left to get.  
\- `IdPointWhiteList` "List of IdPointWhiteList items.  
  
`xs:string NextStartReference [0][1]` `axtid:IdPointWhiteList IdPointWhiteList [0][unbounded]` |

| Fault codes | Description |
| --- | --- |
| `env: Sender` `ter: InvalidArgVal` `ter: InvalidStartReference` | `StartReference`is invalid or has timed out. Client need to start fetching from the beginning. |

### Remote activity functions

**NameValue**

Generic construction containing a Name/Value pair.

The following fields are available:

-   **Name**
    
-   **Value**
    

**Activity**

The following fields are available:

-   **Type**: Supported values for `REX`, `Card` and `PIN`
-   **Params**: Custom fields for Request-event. Mandatory for type `Card` and `PIN`, but not allowed for `REX`. For type `PIN` a param named ‘PIN’ is mandatory.

#### IndicateRemoteActivities command

Applies activities for a remote IdPoint. For each activity two IdPoint events are sent.

The first event is `tns1:IdPoint/tnsaxis:Activity` for all supported activities.

The Reason field for this event is:

-   CardPresented for activity-type `Card`
-   REX for activity-type `REX`
-   CodeEntered for activity-type `PIN`

The second event for each activity is:

-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:IdData` for activity-type `Card`
    
-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:REX` for activity-type `REX`
    
-   `tns1:IdPoint/tnsaxis:Request/tnsaxis:PIN` for activity-type `PIN`
    
-   Name: `IndicateRemoteActivities`
    
-   Access Class: ACTUATE
    

| Message name | Description |
| --- | --- |
| `IndicateRemoteActivitiesRequest` | This message contains:  
  
\- `Token`": Token of the IdPoint to indicate activities for.  
\- `Description` Description field added to the events that is sent.  
\- `Activities` Activity array.  
\- `Attributes` Attributes used to extend the API in the future without changing the signature. Not currently in use.  
  
`pt: ReferenceToken TOKEN [1][1]`  
`xs: String Description [0][1]`  
`axtid: ActivityActivities [1][unbounded]`  
`axtid:NameValue Attributes [0][unbounded]` |
| `IndicateRemoteActivitiesResponse` | This message shall be empty. |

| Fault codes | Description |
| --- | --- |
| env: Senderter: InvalidArgValter: NotFound | IdPoint not found. |