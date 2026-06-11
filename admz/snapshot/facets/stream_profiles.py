from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class StreamProfilesFacet(SimpleParamFacet):
    NAME = "stream_profiles"
    PREFIX = "root.StreamProfile."
    RESTORE_ORDER = 40
    # Capability constant — 401 on write (verified live, AXIS OS 12).
    RESTORE_EXCLUDE = ("MaxGroups",)
