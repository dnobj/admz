from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class ImageFacet(SimpleParamFacet):
    NAME = "image"
    PREFIX = "root.Image."
    RESTORE_ORDER = 30
