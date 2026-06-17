"""Lock down resolver intent synonyms against the catalog task index.

Bug found in live testing: chat user asked "lets reboot the D4200"
and the LLM said it couldn't find a reboot/restart operation. The
underlying cause was a key mismatch — resolver._INTENT_SYNONYMS
mapped "reboot"/"restart" to ``reboot-device``, but the catalog
``by-task.yaml`` index uses ``restart-device``. The resolver
lookup quietly returned empty, the LLM concluded the operation
didn't exist, and confidently told the user.

These tests parse the synonyms table and the index, and assert
that every synonym target resolves to a real index key. Catches
this class of typo at CI time.
"""

import re
from pathlib import Path

import pytest
import yaml
import axis_api_atlas
import axis_api_atlas.catalog.resolver as _atlas_resolver


# Resolver + catalog data now live in the axis-api-atlas package (ADR-0029);
# this test parses the resolver source + by-task index from there.
RESOLVER_PATH = Path(_atlas_resolver.__file__)
BY_TASK_INDEX = (
    Path(axis_api_atlas.default_data_path()) / "vapix" / "index" / "by-task.yaml"
)


def _extract_synonym_targets() -> set[str]:
    """Parse resolver.py and return every task key referenced in
    _INTENT_SYNONYMS values.

    We use a regex parse rather than importing the module because
    we want to fail loudly if the synonyms drift away from the
    index regardless of whether the module imports cleanly.
    """
    src = RESOLVER_PATH.read_text(encoding="utf-8")
    # Find the _INTENT_SYNONYMS dict literal.
    start_idx = src.find("_INTENT_SYNONYMS")
    if start_idx < 0:
        raise AssertionError("Couldn't find _INTENT_SYNONYMS in resolver.py")
    # Walk to the closing brace at the same depth.
    open_brace = src.find("{", start_idx)
    if open_brace < 0:
        raise AssertionError("Couldn't find opening brace of _INTENT_SYNONYMS")
    depth = 0
    close_brace = -1
    for i in range(open_brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                close_brace = i
                break
    if close_brace < 0:
        raise AssertionError("Couldn't find closing brace of _INTENT_SYNONYMS")
    body = src[open_brace + 1 : close_brace]
    targets: set[str] = set()
    # Inner lists look like:  ["change-resolution"]  or  ["a", "b"]
    for list_match in re.finditer(r"\[([^\[\]]+)\]", body):
        for value in re.findall(
            r"""['"]([^'"]+)['"]""",
            list_match.group(1),
        ):
            targets.add(value)
    return targets


def _load_index_keys() -> set[str]:
    """Load the by-task.yaml index and return the set of task keys."""
    with open(BY_TASK_INDEX) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise AssertionError("by-task.yaml didn't parse as a dict")
    return set(data.keys())


class TestSynonymTargetsResolveToIndexKeys:
    """Every value in resolver._INTENT_SYNONYMS must reference a
    real key in catalog/vapix/index/by-task.yaml. If not, the
    resolver returns empty for that intent and the chatbot
    silently misleads the user."""

    def test_all_synonym_targets_exist_in_index(self):
        targets = _extract_synonym_targets()
        index_keys = _load_index_keys()
        dead = targets - index_keys
        assert not dead, (
            f"Resolver synonyms point at non-existent task keys: "
            f"{sorted(dead)}. Either add the keys to "
            f"catalog/vapix/index/by-task.yaml or fix the synonym "
            f"to point at an existing key."
        )

    def test_reboot_and_restart_resolve_to_restart_device(self):
        """Regression — this is the specific bug found in live testing."""
        # Re-import resolver lazily so the test sees the live module
        # (handy when running this file standalone in dev).
        from axis_api_atlas.catalog.resolver import _INTENT_SYNONYMS
        assert "restart-device" in _INTENT_SYNONYMS["reboot"]
        assert "restart-device" in _INTENT_SYNONYMS["restart"]


class TestFlashResolvesToSirenAndLight:
    """Regression — live testing on a D4200-VE strobe siren.

    Chat user asked "lets make the D4200 flash white for 30 seconds".
    The LLM picked ``findmydevice.cgi:find`` (locate-this-unit) instead
    of ``siren_and_light.cgi:start`` (the strobe-siren API). Root cause:
    the word "flash" had no synonym, and the bare word "device" in
    "flash the device" fell through to the ``*-device`` task keys
    (find-device among them) — so the siren_and_light API was never a
    candidate. These tests pin "flash"-family intents to the
    control-siren task so a strobe siren always sees siren_and_light.
    """

    def _resolver(self):
        from axis_api_atlas.catalog.loader import CatalogLoader
        from axis_api_atlas.catalog.resolver import CatalogResolver
        return CatalogResolver(CatalogLoader(axis_api_atlas.default_data_path()))

    def test_flash_synonyms_include_control_siren(self):
        from axis_api_atlas.catalog.resolver import _INTENT_SYNONYMS
        for key in ("flash", "flash white", "flashing", "strobe light"):
            assert key in _INTENT_SYNONYMS, f"missing synonym key: {key!r}"
            assert "control-siren" in _INTENT_SYNONYMS[key], (
                f"{key!r} should map to control-siren, got "
                f"{_INTENT_SYNONYMS[key]}"
            )

    def test_match_intent_flash_white_surfaces_siren(self):
        r = self._resolver()
        for intent in (
            "flash white",
            "flash white for 30 seconds",
            "make the D4200 flash white",
            "flash the device",
        ):
            keys = r._match_intent(intent, "vapix")
            assert "control-siren" in keys, (
                f"intent {intent!r} should surface control-siren, "
                f"got {keys}"
            )


class TestPtzMotionSynonyms:
    """Regression — e2e coverage found 'pan left' / 'tilt up' / 'point the
    camera' resolved to NOTHING (the ptz-move task only matched on the words
    'ptz'/'move', so 'move the camera' worked but the directional verbs didn't).
    The natural directional verbs now map to ptz-move."""

    def _resolver(self):
        from axis_api_atlas.catalog.loader import CatalogLoader
        from axis_api_atlas.catalog.resolver import CatalogResolver
        return CatalogResolver(CatalogLoader(axis_api_atlas.default_data_path()))

    def test_motion_synonyms_map_to_ptz_move(self):
        from axis_api_atlas.catalog.resolver import _INTENT_SYNONYMS
        for key in ("pan", "pan left", "tilt up", "point the camera",
                    "aim the camera"):
            assert key in _INTENT_SYNONYMS, f"missing synonym key: {key!r}"
            assert "ptz-move" in _INTENT_SYNONYMS[key]

    def test_match_intent_pan_tilt_surface_ptz_move(self):
        r = self._resolver()
        for intent in ("pan left", "pan the camera left", "tilt up",
                       "point the camera down", "aim the camera at the door"):
            keys = r._match_intent(intent, "vapix")
            assert "ptz-move" in keys, (
                f"intent {intent!r} should surface ptz-move, got {keys}"
            )

    def test_bare_tilt_angle_stays_orientation(self):
        # We intentionally did NOT add bare 'tilt'/'point'; 'tilt angle' and
        # 'camera angle' must still resolve to set-orientation, not ptz-move.
        r = self._resolver()
        assert "set-orientation" in r._match_intent("tilt angle", "vapix")

    def test_resolve_surfaces_siren_and_light_start(self):
        """The full resolve() must include siren_and_light.cgi:start
        among the candidate operations for a flash intent — that's the
        operation the LLM needs to actually drive a strobe siren."""
        r = self._resolver()
        res = r.resolve(
            device_id="B8A44FFC2B16",
            intent="flash white for 30 seconds",
            family="vapix",
        )
        op_ids = [o.get("id") for o in res.operations]
        assert "siren_and_light.cgi:start" in op_ids, (
            f"siren_and_light.cgi:start missing from candidates: {op_ids}"
        )

    def test_flash_firmware_still_maps_to_upgrade(self):
        """Guard the disambiguation: adding the bare "flash" synonym
        must not steal the exact phrase "flash firmware" away from the
        firmware-upgrade task."""
        from axis_api_atlas.catalog.resolver import _INTENT_SYNONYMS
        assert _INTENT_SYNONYMS["flash firmware"] == ["upgrade-firmware"]
        r = self._resolver()
        assert r._match_intent("flash firmware", "vapix") == [
            "upgrade-firmware"
        ]


class TestStreamStatusVsProfile:
    """Regression — backward-discoverability probe (the catalog QA sweep).

    Asking "list the currently active video streams" surfaced only
    ``streamprofile.cgi`` (stream *configuration*), never
    ``streamstatus.cgi:getAllStreams`` (the live-stream *status* API). Root
    cause: the greedy bare synonym ``"stream" -> configure-stream-profile``
    substring-matched any query containing "stream", while the stream-status
    synonyms ("stream status", "active streams") didn't match "active *video*
    streams" because "video" is interleaved. Fix: natural-language stream
    phrasings map to stream-status, and a bare "stream" now surfaces BOTH
    tasks so the LLM can disambiguate.
    """

    def _resolver(self):
        from axis_api_atlas.catalog.loader import CatalogLoader
        from axis_api_atlas.catalog.resolver import CatalogResolver
        return CatalogResolver(CatalogLoader(axis_api_atlas.default_data_path()))

    def test_active_video_streams_maps_to_stream_status(self):
        from axis_api_atlas.catalog.resolver import _INTENT_SYNONYMS
        assert "active video streams" in _INTENT_SYNONYMS
        assert _INTENT_SYNONYMS["active video streams"] == ["stream-status"]
        # A bare "stream" must surface stream-status as a co-candidate.
        assert "stream-status" in _INTENT_SYNONYMS["stream"]
        assert "configure-stream-profile" in _INTENT_SYNONYMS["stream"]

    def test_match_intent_surfaces_stream_status(self):
        r = self._resolver()
        for intent in (
            "list the currently active video streams",
            "active video streams",
            "stream status",
            "who is connected to the stream",
        ):
            keys = r._match_intent(intent, "vapix")
            assert "stream-status" in keys, (
                f"intent {intent!r} should surface stream-status, got {keys}"
            )

    def test_resolve_surfaces_streamstatus_getallstreams(self):
        r = self._resolver()
        res = r.resolve(
            device_id="B8A44FD0257C",
            intent="list the currently active video streams",
            family="vapix",
        )
        op_ids = [o.get("id") for o in res.operations]
        assert "streamstatus.cgi:getAllStreams" in op_ids, (
            f"streamstatus.cgi:getAllStreams missing from candidates: {op_ids}"
        )


class TestParseHelpers:
    def test_extract_synonym_targets_finds_known_entries(self):
        targets = _extract_synonym_targets()
        # Sanity: we should see at least these (stable for years).
        assert "change-resolution" in targets
        assert "restart-device" in targets
        assert "factory-reset" in targets

    def test_load_index_keys_finds_known_keys(self):
        keys = _load_index_keys()
        assert "restart-device" in keys
        assert "factory-reset" in keys
        assert "upgrade-firmware" in keys
