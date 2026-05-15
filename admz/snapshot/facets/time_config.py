from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class TimeFacet(SimpleParamFacet):
    NAME = "time"
    PREFIX = "root.Time."
    RESTORE_ORDER = 20
