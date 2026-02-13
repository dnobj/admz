---
title: Network settings
url: "https://developer.axis.com/vapix/network-video/network-settings/"
category: vapix
subcategory: network-video
sha256: c2609811d3b086377f18a091e9d8e7c40536b07cef5bc0495156d14f880eb989
scraped_at: "2026-01-09T15:20:19.522Z"
page_height: 28669
---

# Network settings

This section lists network parameters.

## Prerequisites
### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **AXIS OS**: 5.00 and later.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Parameters
### Network

Network interface settings. The parameters in this group (as opposed to the subgroups of this group) are static network settings. If the `Network.BootProto=dhcp` these parameters may not be in use. Check the read-only parameters in the subgroups to retrieve actual network settings in use by the Axis product.

Network

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `BootProto` | `dhcp` | `dhcp` `none` | admin: read, write | Enable/disable dynamic IP address assignment to the Axis product.`dhcp`\= Enable dynamic IP address assignment to the Axis product. `none` = Disable dynamic IP address assignment to the Axis product. |
| `IPAddress` | `192.168.0.90` | An IP address | admin: read, write | The IP Address of the Axis product on the network. |
| `SubnetMask` | `255.255.255.0` | An IP address | admin: read, write | The subnet mask. |
| `Broadcast` | `192.168.0.255` | An IP address | admin: read, write | Broadcast address. Used to send information to several recipients simultaneously. |
| `DefaultRouter` | `192.168.0.1` | An IP address | admin: read, write | Default router/gateway used for connecting devices attached to different networks and network segments. |
| `HostName` | `axis-<serial number>` | A host name | admin: read, write | The name of the Axis product on the network, usually the same as the `DNSname`. |
| `DNSServer1` | `0.0.0.0` | An IP address | admin: read, write | Primary Domain Name System server. |
| `DNSServer2` | `0.0.0.0` | An IP address | admin: read, write | Secondary Domain Name System server. |
| `DomainName` |  | A domain name | admin: read, write | The name of the domain to which the Axis product belongs. |

### Network.ARPPingIPAddress

Enable/disable whether it is possible to set the IP address of the Axis product with ARP/Ping.

Network.ARPPingIPAddress

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read, write | Enable/disable ARP/Ping IP address setting.`yes`\= Enable ARP/Ping IP address setting. `no` = Disable ARP/Ping IP address setting. |

### Network.Bonjour

Enable/disable Bonjour and set the name to be displayed in Bonjour-clients.

Network.Bonjour

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read write | Enable/disable Bonjour.`yes` = Enable Bonjour. `no` = Disable Bonjour. |
| `FriendlyName` | `<product name> - <serial number>` | A string | admin: read write | The name of the Axis product. |

### Network.DNSUpdate

Dynamic Updates in the Domain Name System according to RFC 2136.

Please note that updating the DNS name will require a sequence of VAPIX commands described below. This will initiate a new DNS name update from your Axis device to the DNS server, however issuing only an update of the `Network.DNSUpdate.DNSName` is not enough to trigger a new DNS update request.

**Step 1**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Network.DNSUpdate.DNSName=axistest.r2d2.lab"
```

```bash
GET /axis-cgi/param.cgi?action=update&Network.DNSUpdate.DNSName=axistest.r2d2.labHost: <servername>
```

**Step 2**

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/dnsupdate.cgi?add=axistest.r2d2.lab&hdgen=yes"
```

```bash
GET /axis-cgi/dnsupdate.cgi?add=axistest.r2d2.lab&hdgen=yesHost: <servername>
```

Network.DNSUpdate

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DNSName` |  | Fully Qualified Domain Name or host name. | admin: read, write | The name entered here will be associated with the product's IP address in the DNS server. An example of a DNS name is Axisproduct.example.com. |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable dynamic DNS service.`yes` = Enable dynamic DNS service `no` = Disable dynamic DNS service |
| `TTL` | `30` | `0 ... <2^32-1>` | admin: read, write | This value determines how long (in seconds) the reply from the DNS server should be remembered. |

### Network.eth0

Network settings of the first Ethernet interface. Use these parameters to retrieve the network settings actually in use by the Axis product.

Network.eth0

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Broadcast` |  | An IP address (auto generated). | admin: read | Broadcast address. Used to disseminate information to several recipients simultaneously. |
| `IPAddress` |  | An IP address (auto generated). | admin: read operator: read | The IP Address (IPv4) of the Axis product on the network. |
| `MACAddress` | xx:xx:xx:xx:xx:xx([1](#user-content-fn-1)) | A MAC address (auto generated). | admin: read operator: read | MAC address. The unique identity of the Axis product. |
| `SubnetMask` |  | An IP address (auto generated). | admin: read | The subnet mask. |

### Network.eth0.IPv6

Network settings of IPv6 on the first Ethernet interface. Use these parameters to retrieve the network settings actually in use by the Axis product.

Network.eth0.IPv6

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| IPAddresses |  | An IP address (auto generated) | admin: read | The physical addresses of the Axis product on the network. A list of IPv6 addresses, separated by a space. This parameter is read only. |

### Network.Filter

IP address filtering. These parameters are used to only accept connections from certain IP addresses or networks.

Network.Filter

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable IP address filtering.`yes` = Enable IP address filtering. `no` = Disable IP address filtering. |

### Network.Filter.Input

IP addresses filtering for incoming data traffic.

Network.Filter.Input

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Policy` | `allow` | `allow` `deny` | admin: read, write | Allow or deny the addresses access to the Axis product.`allow` = Allow addresses access to the Axis product. `deny` = Deny addresses access to the Axis product. |
| `AcceptAddresses` |  | A string (a space separated list of IP addresses and network addresses in the CIDR notation (IP address/netmask bits)) | admin: read, write | Addresses allowed to pass through the filter. Example: `192.168.0/24` will add all the addresses in the range `192.168.0.0` to `192.168.0.255`. If accessing the Axis product via a proxy server, the proxy server's IP address must be added to the list of allowed addresses. |

### Network.Filter.Log

Enable/disable logging of filtered packages.

Network.Filter.Log

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable logging of filtered packages.`yes` = Enable logging of filtered packages. `no` = Disable logging of filtered packages. |

### Network.HTTP.AuthenticationPolicy

Defines the HTTP, HTTPS and RTSP server authentication capabilities in Axis devices from AXIS OS version 5.70 and higher. By using the parameter `Network.HTTP.AuthenticationPolicy` you can set the authentication capabilities to either `Basic`, `Digest`, `Basic_Digest`, or `Recommended`. Default value is `Recommended`.

| Mode | HTTP server | HTTPS server | RTSP server |
| --- | --- | --- | --- |
| `Basic` | `Basic` | `Basic` | `Basic` |
| `Digest` | `Digest` | `Digest` | `Digest` |
| `Basic_Digest` | `Digest` | `Digest` | `Basic & Digest` |
| `Recommended` | `Digest` | `Basic` | `Digest` |

For RTSP communication, the authentication is performed by default on the RTSP server and controlled via `Network.RTSP.AuthenticateRTSPOverHTTP` if it has been set to `yes`. This option can be disabled and `System.HTTPAuthRTSPOverHTTP` can be used instead to authenticate RTSP requests over HTTP.

### Network.Interface.I0.dot1x

The parameters in this group enables the Axis product to access a network protected by IEEE 802.1X/EAPOL (Extensible Authentication Protocol Over Lan).

Network.Interface.I0.dot1x

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable the Axis product to access a network protected by IEEE 802.1X/EAPOL (Extensible Authentication Protocol Over LAN).`yes` = Enable the Axis product to access a network protected by IEEE 802.1X/EAPOL. `no` = Disable the Axis product to access a network protected by IEEE 802.1X/EAPOL. |
| `EAPOLVersion` | `1` | `1` `2` `3` | admin: read, write | Set the EAPOL version as used in the network switch. |
| `Status` | `Stopped` | `Stopped` `Unauthorized` `Authorized` `UNKNOWN` | admin: read, write | Get the status of the connection to the IEEE 802.1X port.`Stopped` = The 802.1X supplicant is not running. `Unauthorized` = Access to the 802.1X protected network was denied. `Authorized` = Access to the 802.1X protected network was allowed. `UNKNOWN` = The state of the 802.1X supplicant is unknown. |

### Network.Interface.I0.dot1x.EAPTLS

The parameters in this group sets the identity and password to access to a network protected by IEEE 802.1X/EAPOL (Extensible Authentication Protocol Over Lan).

Network.Interface.I0.dot1x.EAPTLS

| Parameters | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Identity` |  | A string | admin: read, write | Set the user identity associated with the certificate. A maximum of 128 characters can be used. |
| `PrivateKeyPassword` |  | A string | admin: read, write | Set the password for your user identity. A maximum of 16 characters can be used. |

### Network.IPv6

Network interface settings for IPv6. The parameters in this group are static network settings. If `AcceptRA=yes` and/or DHCPv6 is used it will probably result in additional configuration. Check the read-only parameters in the other subgroups to retrieve actual network settings in use by the operation system.

Network.IPv6

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read, write operator: read viewer: read | Enable/disable IPv6 in the Axis product.`yes` = Enable IPv6 in the Axis product. `no` = Disable IPv6 in the Axis product. |
| `AcceptRA` | `yes` | `yes` `no` | admin: read, write | Enable/disable IPv6 to accept router advertisements.`yes` = Enable IPv6 to accept router advertisements. `no` = Disable IPv6 to accept router advertisements. |
| `DHCPv6` | `auto` | `auto` `stateful` `stateless` `off` | admin: read, write | Setting for support of DHCPv6.`auto` = Enable DHCPv6 according to the router advertisements. `stateful` = Enable DHCPv6 to set IPv6 configuration as well as DNS servers etc. `stateless` = Enable DHCPv6 only to set DNS servers etc. `off` = Disable DHCPv6 |
| `IPAddress` |  | One or more IPv6 addresses | admin: read, write | A list of manually configured IPv6 addresses, separated by a space. (If no prefix length is included in an IPv6 address, the default value 64 is used) |
| `DefaultRouter` |  | An IPv6 address | admin: read, write | A manually configured IPv6 address of a default router. |

### Network.QoS.Class1

Quality of Service classification. These parameters holds the DSCP value common for the members of a QoS class.

Network.QoS.Class1

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Desc` | Description string | A string | admin: read, write | The description of the QoS class. |
| `DSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint value for the QoS class. |

### Network.QoS.Class2

Quality of Service classification. These parameters holds the DSCP value common for the members of a QoS class.

Network.QoS.Class2

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Desc` | Description string | A string | admin: read, write | The description of the QoS class. |
| `DSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint value for the QoS class. |

### Network.QoS.Class3

Quality of Service classification. These parameters holds the DSCP value common for the members of a QoS class.

Network.QoS.Class3

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Desc` | Description string | A string | admin: read, write | The description of the QoS class. |
| `DSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint value for the QoS class. |

### Network.QoS.Class4

Quality of Service classification. These parameters holds the DSCP value common for the members of a QoS class.

Network.QoS.Class4

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Desc` | Description string | A string | admin: read, write | The description of the QoS class. |
| `DSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint value for the QoS class. |

### Network.Resolver

Enable/disable retrieval of Domain Name System (DNS) settings from DHCP server. The actual DNS settings in use by the Axis product are located in this group.

Network.Resolver

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `NameServerList` |  | Auto generated (Product dependent) | admin: read | A list of IP addresses (both IPv4 and IPv6), separated by a space. |
| `ObtainFromDHCP` | Product dependent. | `yes` `no` | admin: read, write | Specifies if the DNS server should be obtained from a DHCP server. |
| `Search` |  | Auto generated | admin: read | Search list of hostname lookup. This parameter is read only. |
| `NameServer1` |  | Auto generated | admin: read | Name server IPaddress. This parameter is read only. |
| `NameServer2` |  | Auto generated | admin: read | Name server IPaddress. This parameter is read only. |

### Network.Routing

Routing table actually in use by the Axis product.

Network.Routing

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DefaultRouter` |  | A routing table (auto generated). | admin: read | The routing table. |

### Network.Routing.IPv6

Routing table for IPv6 actually in use by the Axis product.

Network.Routing.IPv6

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DefaultRouter` |  | Auto generated | admin: read | A list of default routers for IPv6. This parameter is read only. |

### Network.RTP

Parameters related to multicast RTP.

Network.RTP

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `NbrOfRTPGroups` | Hardware dependent | 1 ... | admin: read operator: read viewer: read | The number of RTP groups. One group for each possible multicast presentation (video source). |
| `StartPort` | `50000` | `1024` ... `65532` | admin: read, write | The RTP port range defines the range of ports from which the video/audio ports are automatically selected. This feature is useful if the product is connected to a NAT router with manually configured port mapping. Each RTP session needs 4 ports, which means 4 ports for each unicast session (audio and video) or 4 ports for the multicast session in total. |
| `EndPort` | `50999` | `1025` ... `65535` | admin: read, write | The RTP port range defines the range of ports from which the video/audio ports are automatically selected. This feature is useful if the product is connected to a NAT router with manually configured port mapping. Each RTP session needs 4 ports, which means 4 ports for each unicast session (audio and video) or 4 ports for the multicast session in total. |
| `VideoDSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint for video QoS. |
| `AudioDSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint for audio QoS. |

### Network.RTP.R#

Parameters related to multicast RTP. One group for each possible multicast presentation (for example video source).

Network.RTP.R#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `VideoAddress` | Auto generated | A multicast IP address. | admin: read, write | The multicast IP address to which the multicast RTP video stream is transmitted. The default value is auto generated based on the serial number of the product. |
| `VideoPort` | `0` | `0`, `1024` ... `65535` | admin: read, write | The port number for the RTP video stream.`0` = The port number is dynamically assigned. |
| `AudioAddress` | Auto generated. | A multicast IP address. | admin: read, write | The IP address to which the multicast RTP audio stream is transmitted. The default value is generated based on the serial number of the product. The parameter is read only in products without audio support.`0.0.0.0` = The audio stream is disabled. |
| `AudioPort` | `0` | `0`, `1024` ... `65535` | admin: read, write | The port number for the RTP audio stream. The parameter is read only in products without audio support.`0` = The port number is dynamically assigned. |
| `TTL` | `5` | `1` ... | admin: read, write | The Time To Live for each UDP packet. This indicates the number of routers/switches that the packet may traverse before being discarded. |

info

The # is replaced with a group number starting from zero, e.g. Network.RTP.R0.

### Network.RTSP

Parameters needed by the RTSP daemon.

Network.RTSP

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read, write | Enable/disable RTSP support. If disabled, only multicast RTP is available for MPEG4/h.264 delivery.`yes` = Enable RTSP support. `no` = Disable RTSP support. |
| `Port` | `554` | `554`, `1024` ... `65535` | admin: read, write operator: read viewer: read | The port number for the RTSP daemon. |
| `Timeout` | `60` | `0` ... | admin: read, write | The keep-alive timeout for the RTSP session specified in seconds.`0` = Disable the keep-alive timeout. |
| `ProtViewer` | `password` | `password` `anonymous` | admin: read, write | Viewer access type.`password` = Password protected access. `anonymous` = Anonymous access. |
| `AuthenticateOverHTTP` | `no` | `yes` `no` | admin: read, write | Configure whether RTSP requests sent over HTTP need to be authenticated.`yes` = RTSP requests sent over HTTP need to be authenticated. `no` = RTSP requests sent over HTTP do not need to be authenticated. |
| `AllowClientTransportSettings` | `no` | `yes` `no` | admin: read, write | Configure whether RTSP transport settings such as a multicast address and a port range should be allowed to be configured by client.`yes` = RTSP transport settings are allowed to be configured by client. `no` = RTSP transport settings are not allowed to be configured by client. |

### Network.UPnP

Enable/disable Universal Plug and Play and set the name to be displayed in UPnP-clients.

Network.UPnP

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read, write | Enables Universal Plug and Play.`yes` = Enable Universal Plug and Play. `no` = Disable Universal Plug and Play. |
| `FriendlyName` | `<product name - <serial number>` | A string | admin: read, write | The UPnP display name. |

### Network.UPnP.NATTraversal

These parameters control NAT traversal functionality. To make the task of port forwarding easier, Axis offers the NAT traversal functionality in many of its network video products. NAT traversal is a technique that can be used to open up routers and firewalls to make devices on a LAN accessible from the Internet.

Network.UPnP.NATTraversal

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enables/disables NAT traversal.`yes` = Enable NAT traversal. `no` = Disable NAT traversal. |
| `Router` |  | An IP address | admin: read, write | If an IP address is entered NAT traversal will be attempted with that router. If none is entered, the server will automatically try to discover a router. |
| `ExternalIPAddress` |  | An IP address | admin: read | The external IP address of the NAT router. This value shall not be configured. It is set by the system itself. |
| `Active` | `no` | `yes` `no` | admin: read, write | This parameter is set to yes if NAT traversal was successful. This value shall not be configured, it is set by the system itself.`yes` = NAT traversal was successful `no` = NAT traversal was not successful |
| `MinPort` | `32768` | `1` ... `65535` | admin: read, write | The first time NAT traversal is enabled, a random port between `MinPort` and `MaxPort` will be selected for the TCP port to map in the router. If port mapping is successful, that port will be used thereafter. The random range can be limited by setting `MinPort` and `MaxPort`. |
| `MaxPort` | `65535` | `1` ... `65535` | admin: read, write | The first time NAT traversal is enabled, a random port between `MinPort` and `MaxPort` will be selected for the TCP port to map in the router. If port mapping is successful, that port will be used thereafter. The random range can be limited by setting `MinPort` and `MaxPort`. |

### Network.VolatileHostName

Enable/disable retrieval of host name from DHCP-server. The host name, actually in use by the Axis product, is located in this group.

Network.VolatileHostName

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `ObtainFromDHCP` | `yes` | `yes` `no` | admin: read, write | Specifies if the host name should be obtained from a DHCP server.`yes` = The host name is obtained from a DHCP server. `no` = The host name is not obtained from a DHCP server. |
| `HostName` |  | Auto generated | admin: read | The host name obtained from a DHCP server. |

### Network.ZeroConf

Enable/disable automatic configuration of link local IP address. The negotiated network settings are located in this group, and are used in parallel with the setting of the Network.eth0 group. That means that both addresses can be used simultaneously.

Network.ZeroConf

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `yes` | `yes` `no` | admin: read, write | Enable/disable zero configuration.  
`yes` = Enable zero configuration.  
`no` = Disable zero configuration. |
| `Fallback` | `no` | `yes` `no` | admin: read, write | Link-local addressing is only activated if DHCP or static addressing fails.  
If `Enabled` = `no`: Link-local addresses are never used and `Fallback` is ignored.  
If `Enabled` = `yes` and `Fallback` = `yes`: Link-local addresses are only used if the primary address configuration mode (either DHCP or static) fails.  
If `Enabled` = `yes` and `Fallback` = `no`: Link-local addresses are always used. |
| `IPAddress` |  | Auto generated | admin: read | The IP address. |
| `SubnetMask` |  | Auto generated | admin: read | The subnet mask. |

### SNMP

info

The SNMP section of this API will be deprecated as of AXIS OS version 13.0 and will no longer receive updates. It is replaced by the Device Configuration [SNMP Configuration API](/vapix/device-configuration/snmp-api/).

SNMP (Simple Network Management Protocol) configuration.

SNMP

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable SNMP.`yes` = Enable SNMP `no` = Disable SNMP |
| `InitialUserPasswd` |  | A string. | admin: write | SNMP V3 initial user password. |
| `InitialUserPasswdSet` | `no` | `yes` `no` | admin: read, write | Set to `yes` if `InitialUserPasswd` is set.`yes` = Enable initial user password. `no` = Disable initial user password. |
| `EngineBoots` |  | `0` ... | admin: read, write | Number of times SNMP has started. |
| `V1` | `no` | `yes` `no` | admin: read, write | Enable/disable SNMP V1.`yes` = Enable SNMP V1. `no` = Disable SNMP V1. |
| `V2c` | `no` | `yes` `no` | admin: read, write | Enable/disable SNMP V2c.`yes` = Enable SNMP V2c. `no` = Disable SNMP V2c. |
| `V3` | `no` | `yes` `no` | admin: read, write | Enable/disable SNMP V3.`yes` = Enable SNMP V3. `no` = Disable SNMP V3. |
| `V1ReadCommunity` | `public` | A string | admin: read, write | The community name used for SNMP V1/V2c read operations. |
| `V1WriteCommunity` | `write` | A string | admin: read, write | The community name used for SNMP V1/V2c write operations. |
| `DSCP` | `0` | `0` ... `63` | admin: read, write | The Differentiated Services Codepoint for SNMP QoS. |
| `TransportProtocol` | `udp` | `udp` `tcp` | admin: read, write | The transport protocol to be used for SNMP traffic. |

### SNMP.Trap

Traps are used by the camera to send messages to a management system for important events or status changes. These settings are used with SNMP v1/v2.

SNMP.Trap

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| Enabled | `no` | `yes` `no` | admin: read, write | Enable disable trap reporting.`yes` = Enable trap reporting. `No` = Disable trap reporting. |

### SNMP.Trap.T#

This parameter group contains a parameter for trap messages.

SNMP.Trap.T#

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Address` |  | An IP address. | admin: read, write | Set the IP address of the management server. |
| `Community` |  | A string. | admin: read, write | Set community to use when sending a trap message to the management system. An SNMP community is the group of devices and management station running SNMP. Community names are used to identify groups. |

### SNMP.Trap.T#.AuthFail

This parameter group contains a parameter for trap message when authentication attempt fails.

SNMP.Trap.T#.AuthFail

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable trap message when an authentication attempt fails.`yes` = Enable trap message when an authentication attempt fails. `No` = Disable trap message when an authentication attempt fails |

### SNMP.Trap.T#.Coldstart

This parameter group contains a parameter for trap message when the camera is rebooted/resarted.

SNMP.Trap.T#.Coldstart

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable trap message when the camera is rebooted/restarted.`yes` = Enable trap message when the camera is rebooted/restarted. `no` = Disable trap message when the camera is rebooted/restarted. |

### SNMP.Trap.T#.LinkUp

This parameter group contains a parameter for a trap message when a link changes from down to up.

SNMP.Trap.T#.LinkUp

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable/disable a trap message when a link changes from down to up.`yes` = Enable a trap message when a link changes from down to up. `no` = Disable a trap message when a link changes from down to up. |

### SNMP.Trap.T#.WarmStart

This parameter group contains a parameter for a trap message when SNMP has started and the configure file has changed, but not the MIB (Management Information Base).

SNMP.Trap.T#.WarmStart

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | Enable /disable a trap message when SNMP has started and the configure file has changed, but not the MIB (Management Information Base).`yes` = Enable a trap message when SNMP has started and the configure file has changed, but not the MIB. `no` = Disable a trap message when SNMP has started and the configure file has changed, but not the MIB. |

### SNMP.NTCIP

This parameter group contains a parameter that can be used to enable and disable NTCIP. Please note that SNMP must be enabled before you can use this parameter.

SNMP.NTCIP

| Parameter | Default values | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `Enabled` | `no` | `yes` `no` | admin: read, write | `yes` = Enables NTCIP. `no` = Disables NTCIP. |

## Footnotes

1.  The MAC address of the Axis product is unique for every single product. The MAC address is the same as the serial number, which can be found on the product's label. [↩](#user-content-fnref-1)