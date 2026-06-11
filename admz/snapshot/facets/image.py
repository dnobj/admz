from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class ImageFacet(SimpleParamFacet):
    NAME = "image"
    PREFIX = "root.Image."
    RESTORE_ORDER = 30
    # Verified live on AXIS OS 12 (P3288-LVE): the device answers 401 —
    # admin accounts lack write rights — for the factory/structural
    # params that define sensor wiring: each channel's Source/Type and
    # the channel count. ('*' matches one dot-segment.)
    RESTORE_EXCLUDE = ("I*.Source", "I*.Type", "NbrOfConfigs")
