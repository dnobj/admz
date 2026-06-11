from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class TimeFacet(SimpleParamFacet):
    NAME = "time"
    PREFIX = "root.Time."
    RESTORE_ORDER = 20
    # Verified live on AXIS OS 12 (P3288-LVE): param.cgi:update rejects
    # NTP.Server even when written back unchanged — NTP moved to ntp.cgi
    # and the Time.NTP param tree is a read-only mirror. An NTP change is
    # still real, user-visible drift, so it stays serialized; it just
    # can't be reverted through this facet.
    RESTORE_EXCLUDE = ("NTP.",)
