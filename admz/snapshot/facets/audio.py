from admz.snapshot.facets.base import SimpleParamFacet, register_facet


@register_facet
class AudioFacet(SimpleParamFacet):
    """Audio configuration — input gain/encoding (``root.AudioSource.*``),
    output/volume (``root.AudioOutput.*``), and general audio
    (``root.Audio.*``). This is where the input-gain drift blind spot lived:
    a user lowered ``root.AudioSource.A0.InputGain`` and drift saw nothing
    because no facet claimed it.

    ``PREFIX="root.Audio"`` (no trailing dot) intentionally claims the whole
    audio family in one category. Applies to all VAPIX devices like the other
    param facets — a device with no audio params just yields an empty facet
    (natural device-dependence), so no gating is needed.
    """

    NAME = "audio"
    PREFIX = "root.Audio"
    RESTORE_ORDER = 50
    # Curated live from the lab; start empty (drift-capture first, restore
    # once we've confirmed which audio keys 401 on write).
    RESTORE_EXCLUDE = ()
