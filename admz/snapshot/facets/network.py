from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class NetworkFacet(SimpleParamFacet):
    NAME = "network"
    PREFIX = "root.Network."
    # Network changes can disconnect the device — apply last.
    RESTORE_ORDER = 90
