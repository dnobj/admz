from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class NetworkFacet(SimpleParamFacet):
    NAME = "network"
    PREFIX = "root.Network."
    # Network changes can disconnect the device — apply last.
    RESTORE_ORDER = 90
    # Not settable on the device (verified live, AXIS OS 12 / P3288):
    #  * runtime state — live interface (eth0.*: actual addresses, MAC),
    #    learned routes (Routing.*), dot1x auth status, ZeroConf's
    #    assigned link-local address/mask;
    #  * structural/derived constants — Interface SystemDevice mapping,
    #    DHCP.VendorClass (model+firmware string), RTP group count,
    #    hardware-negotiated PoE power/class, the fixed QoS class
    #    descriptions;
    #  * DHCP-managed resolver settings — Resolver.NameServer*/Search
    #    answer 401 while Resolver.ObtainFromDHCP=yes. State-dependent:
    #    on a static-DNS device they WOULD be writable, but a single
    #    exclude list can't express that — revisit if a fleet needs
    #    static-DNS restore.
    # The static-config equivalents (IPAddress, DefaultRouter, HostName,
    # ...) restore normally. Single-NIC assumption: I0 entries.
    RESTORE_EXCLUDE = (
        "eth0.",
        "Routing.",
        "Resolver.NameServer",
        "Resolver.Search",
        "Interface.I0.dot1x.Status",
        "Interface.I0.SystemDevice",
        "DHCP.VendorClass",
        "RTP.NbrOfRTPGroups",
        "LLDP.POE.MaxPower",
        "LLDP.POE.PoeClass",
        "QoS.Class*.Desc",
        "ZeroConf.IPAddress",
        "ZeroConf.SubnetMask",
    )
