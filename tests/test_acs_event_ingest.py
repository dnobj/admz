"""ACS Pro action-rule poller — normalize + identity-gated firing (ADR-0041/0057).

Firing is gated on **store identity**, never on a timestamp (ADR-0057), so every
test here fixes its timestamps in the fake and none of them read the wall clock,
sleep, or spawn a thread — windows-latest is the authoritative CI leg.
"""

from __future__ import annotations

import asyncio
import logging


def _run(coro):
    return asyncio.run(coro)


def _det(id_, ts, cam="c1", name="Lobby", end=None):
    """One ``search_detections`` 'Action Rule' row (its normalized shape)."""
    return {"ts": ts, "end": end, "type": "Action Rule",
            "camera_id": cam, "device_name": name, "data": {"Id": id_}}


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_maps_to_canonical_store_record():
    from admz.events.acs_ingest import normalize_acs_action_rule
    rec = normalize_acs_action_rule(_det(40, "2026-06-11T18:57:35.5861971Z", name="Lobby"))
    assert rec["source"] == "acs"
    assert rec["type"] == "ACS/ActionRule"
    assert rec["device_id"] == "c1" and rec["device_name"] == "Lobby"
    assert rec["data"]["category"] == "action_rule"
    assert rec["data"]["topic"] == "ACS/ActionRule"
    assert rec["data"]["event_id"] == 40
    assert rec["data"]["rule_name"] is None        # ACS firings are anonymous
    assert rec["data"]["ts_parsed"] is True
    assert rec["ts_ms"] > 0
    assert rec["id"]
    # stable / deterministic id (dedup across polls)
    assert normalize_acs_action_rule(_det(40, "2026-06-11T18:57:35.5861971Z")).__class__


def test_parse_ms_tolerates_7digit_fraction_and_Z():
    from admz.events.acs_ingest import _parse_ms
    a = _parse_ms("2026-06-11T18:57:35.5861971Z")   # 7 fractional digits + Z
    b = _parse_ms("2026-06-11T18:57:35Z")           # no fraction
    assert a > 0 and b > 0 and a > b
    assert _parse_ms(None) == 0
    assert _parse_ms("not-a-time") == 0


def test_normalize_falls_back_to_poll_time_on_unparseable_ts():
    """ADR-0057: ts_ms=0 sorts last and the first retention sweep reaps the row
    (``DELETE ... WHERE ts_ms < cutoff``), so an unparseable stamp gets poll time
    and a flag — never 0. The id hashes the RAW string, so dedup is unaffected."""
    from admz.events.acs_ingest import normalize_acs_action_rule
    plain = normalize_acs_action_rule(_det(7, "not-a-time"))
    assert plain["ts_ms"] > 0                    # NOT 0 → survives retention
    assert plain["data"]["ts_parsed"] is False
    assert plain["ts"] == "not-a-time"           # raw value preserved verbatim
    # Deterministic fallback, and the id is stable across polls despite it.
    a = normalize_acs_action_rule(_det(7, "not-a-time"), now_ms=1_700_000_000_000)
    b = normalize_acs_action_rule(_det(7, "not-a-time"), now_ms=1_700_000_999_000)
    assert a["ts_ms"] == 1_700_000_000_000 and b["ts_ms"] == 1_700_000_999_000
    assert b["id"] == a["id"]


# ── poller ───────────────────────────────────────────────────────────────────
class _Store:
    def __init__(self):
        self.rows = []

    def append(self, rec):
        if any(r["id"] == rec["id"] for r in self.rows):
            return False                            # dedup like EventStore
        self.rows.append(rec)
        return True


class _FlakyStore(_Store):
    """``append`` fails for the first ``fail_times`` calls exactly the way the real
    one does on a swallowed ``sqlite3.Error``: returns False (indistinguishable
    from a duplicate) and bumps ``append_errors``."""

    def __init__(self, fail_times=0):
        super().__init__()
        self.fail_times = fail_times
        self.append_errors = 0

    def append(self, rec):
        if self.fail_times > 0:
            self.fail_times -= 1
            self.append_errors += 1
            return False
        return super().append(rec)


def _recorder():
    fired = []

    async def on_event(rec):
        fired.append(rec)
    return fired, on_event


def _build(monkeypatch, fake_search, enabled=True, store=None):
    import admz.events.config as cfg
    import admz.modules.acs_pro.events as acs_events

    monkeypatch.setattr(cfg, "acs_event_ingest_enabled", lambda: enabled)
    monkeypatch.setattr(acs_events, "search_detections", fake_search)
    from admz.events.acs_ingest import AcsActionRulePoller
    return AcsActionRulePoller(catalog=None, executors={},
                               store=store if store is not None else _Store(),
                               on_event=None)


def _poller(monkeypatch, events, enabled=True, store=None, more=False):
    """Single fixed page, returned on every poll."""
    async def fake_search(catalog, executors, **kw):
        return {"success": True, "events": list(events), "more": more}
    return _build(monkeypatch, fake_search, enabled=enabled, store=store)


def _paged_poller(monkeypatch, pages, enabled=True, store=None):
    """``pages[i]`` is the result of poll i; the last page repeats once exhausted.

    Each entry is a list of rows, or ``{"events": [...], "more": bool}``.
    """
    calls = {"n": 0}

    async def fake_search(catalog, executors, **kw):
        page = pages[min(calls["n"], len(pages) - 1)]
        calls["n"] += 1
        if isinstance(page, dict):
            return {"success": True, "events": list(page.get("events") or []),
                    "more": bool(page.get("more"))}
        return {"success": True, "events": list(page), "more": False}

    return _build(monkeypatch, fake_search, enabled=enabled, store=store)


# ── the headline: identity, not time ─────────────────────────────────────────
def test_late_arriving_firing_still_fires(monkeypatch):
    """GH #210. A firing that reaches ADMZ *after* a newer one — ACS delivered it
    late, or a truncated page withheld it — used to be stored and never fired: it
    appeared in the Activity feed while its detection provably never ran."""
    newer = _det(1, "2026-06-21T10:00:59.0Z")
    older = _det(2, "2026-06-21T10:00:30.0Z")       # older, arrives one poll later
    p = _paged_poller(monkeypatch, [[newer], [newer, older]])
    fired, p.on_event = _recorder()
    p._seeded = True                                 # past the seeding poll

    assert _run(p.poll_once())["fired"] == 1         # `newer` fires
    assert _run(p.poll_once())["fired"] == 1         # `older` fires despite being older
    assert [f["data"]["event_id"] for f in fired] == [1, 2]
    assert len(p.store.rows) == 2                    # and `newer` did not re-fire


def test_equal_millisecond_firings_both_fire(monkeypatch):
    """Two firings in the same millisecond, split across polls. The old strict
    `>` comparison dropped the second; identity does not care."""
    a = _det(1, "2026-06-21T10:00:00.000Z")
    b = _det(2, "2026-06-21T10:00:00.000Z")          # identical stamp, different id
    p = _paged_poller(monkeypatch, [[a], [a, b]])
    fired, p.on_event = _recorder()
    p._seeded = True

    _run(p.poll_once())
    _run(p.poll_once())
    assert [f["data"]["event_id"] for f in fired] == [1, 2]


def test_fires_regardless_of_clock_skew_in_either_direction(monkeypatch):
    """ADR-0057: no clock is consulted on the fire path. The old mark was seeded
    from the ADMZ host clock and compared against ACS server stamps, so an ACS
    clock behind ours produced a silent dead window and one ahead of ours poisoned
    the mark. Both of these are far from any plausible local clock."""
    # Seed through the real path with a plausibly-"now" row, so the watermark this
    # replaced would sit at 2026 — otherwise the skew cases prove nothing.
    seed = _det(0, "2026-06-21T10:00:00.0Z")
    behind = _det(1, "2019-01-01T00:00:00.0Z")       # far in the past
    ahead = _det(2, "2099-01-01T00:00:00.0Z")        # far in the future
    pages = [[seed], [seed, behind, ahead], [seed, behind, ahead]]
    p = _paged_poller(monkeypatch, pages)
    fired, p.on_event = _recorder()

    assert _run(p.poll_once())["fired"] == 0         # seeding poll
    _run(p.poll_once())                              # BOTH skewed firings fire
    _run(p.poll_once())                              # third poll must add nothing
    assert [f["data"]["event_id"] for f in fired] == [1, 2]


# ── the startup contract (ADR-0041) ──────────────────────────────────────────
def test_first_poll_seeds_the_feed_and_fires_nothing(monkeypatch):
    """The constraint that killed the naive `if inserted:` fix: on first enablement
    the store is empty, so identity alone would fire the whole lookback window —
    including pre-authorized service-affecting actions."""
    history = [_det(1, "2026-06-21T09:00:00.0Z"), _det(2, "2026-06-21T09:30:00.0Z"),
               _det(3, "2026-06-21T09:45:00.0Z")]
    fresh = _det(4, "2026-06-21T10:00:00.0Z")
    p = _paged_poller(monkeypatch, [history, history + [fresh]])
    fired, p.on_event = _recorder()

    # Behavioural assert FIRST, so a regression fails here rather than on the
    # private-attribute check below (which would be red for the wrong reason).
    assert _run(p.poll_once())["fired"] == 0         # seeding poll fires NOTHING
    assert len(p.store.rows) == 3                    # ...but the feed is seeded
    assert p._seeded is True

    assert _run(p.poll_once())["fired"] == 1         # only the genuinely new one
    assert [f["data"]["event_id"] for f in fired] == [4]


def test_a_failed_poll_does_not_consume_the_seeding_window(monkeypatch):
    """`_seeded` flips on the first *successful* poll. If the first poll errors,
    the next one must still seed rather than fire the backlog."""
    import admz.events.config as cfg
    import admz.modules.acs_pro.events as acs_events
    monkeypatch.setattr(cfg, "acs_event_ingest_enabled", lambda: True)
    calls = {"n": 0}

    async def fake_search(catalog, executors, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"success": False, "message": "acs boom"}
        return {"success": True, "events": [_det(1, "2026-06-21T09:00:00.0Z")]}

    monkeypatch.setattr(acs_events, "search_detections", fake_search)
    from admz.events.acs_ingest import AcsActionRulePoller
    p = AcsActionRulePoller(catalog=None, executors={}, store=_Store())
    fired, p.on_event = _recorder()

    assert _run(p.poll_once())["fired"] == 0         # the poll itself failed
    assert _run(p.poll_once())["fired"] == 0         # so THIS is the seeding poll
    assert fired == []
    assert p._seeded is True                         # ...and only now is it seeded


def test_restart_does_not_refire_the_window(monkeypatch):
    """A new poller over the SAME store — the durable dedup — fires nothing for
    rows already in the feed, without consulting any clock."""
    rows = [_det(1, "2026-06-21T10:00:00.0Z"), _det(2, "2026-06-21T10:01:00.0Z")]
    store = _Store()
    first = _paged_poller(monkeypatch, [rows], store=store)
    first._seeded = True
    _run(first.poll_once())
    assert len(store.rows) == 2

    restarted = _paged_poller(monkeypatch, [rows], store=store)
    fired, restarted.on_event = _recorder()
    assert _run(restarted.poll_once())["fired"] == 0
    assert fired == [] and len(store.rows) == 2
    assert restarted._seeded is True


def test_second_poll_does_not_refire_or_duplicate(monkeypatch):
    p = _poller(monkeypatch, [_det(2, "2026-06-21T12:00:00.0Z")])
    fired, p.on_event = _recorder()
    p._seeded = True

    _run(p.poll_once())                              # fires once + appends
    _run(p.poll_once())                              # same event → no refire
    assert len(fired) == 1
    assert len(p.store.rows) == 1                    # dedup on id


# ── the store-error retry buffer ─────────────────────────────────────────────
def test_a_failed_append_does_not_consume_the_fire(monkeypatch):
    """`append` returns False for a duplicate AND for a swallowed sqlite error.
    Because every poll re-fetches the whole window, the firing retries on the next
    poll — which is exactly why this must NOT be disambiguated with a seen-set
    (that would defeat the retry and reintroduce #209's defect class)."""
    row = _det(1, "2026-06-21T10:00:00.0Z")
    store = _FlakyStore(fail_times=1)                # poll 1's append is lost
    p = _paged_poller(monkeypatch, [[row]], store=store)
    fired, p.on_event = _recorder()
    p._seeded = True

    assert _run(p.poll_once())["fired"] == 0         # append failed → no fire
    assert p.store_error_polls == 1                  # ...and it is not silent
    assert _run(p.poll_once())["fired"] == 1         # retried within the window
    assert [f["data"]["event_id"] for f in fired] == [1]


# ── unparseable timestamps + truncation ──────────────────────────────────────
def test_unparseable_timestamp_fires_and_is_counted(monkeypatch):
    p = _paged_poller(monkeypatch, [[_det(9, "not-a-time")]])
    fired, p.on_event = _recorder()
    p._seeded = True

    assert _run(p.poll_once())["fired"] == 1         # fired, not silently skipped
    assert p.unparsed_ts == 1
    rec = p.store.rows[0]
    assert rec["ts_ms"] > 0 and rec["data"]["ts_parsed"] is False
    assert rec["ts"] == "not-a-time"
    _run(p.poll_once())                              # stable id → dedups, no refire
    assert len(fired) == 1 and len(p.store.rows) == 1
    # An unparseable stamp must not pollute the skew reading.
    assert p.newest_event_ts_ms == 0
    assert p.status()["apparent_skew_ms"] is None


def test_truncation_is_surfaced_and_warns_once_per_streak(monkeypatch, caplog):
    row = _det(1, "2026-06-21T10:00:00.0Z")
    p = _paged_poller(monkeypatch, [{"events": [row], "more": True}])
    p._seeded = True

    with caplog.at_level(logging.WARNING, logger="admz.events.acs_ingest"):
        _run(p.poll_once())
        _run(p.poll_once())
        _run(p.poll_once())
    assert p.last_truncated is True
    assert p.truncated_polls == 3                    # counted every poll...
    hits = [r for r in caplog.records if "page cap" in r.getMessage()]
    assert len(hits) == 1                            # ...but warned once


def test_status_exposes_the_adr0057_fields(monkeypatch):
    p = _poller(monkeypatch, [])
    st = p.status()
    for k in ("enabled", "running", "seeded", "last_count", "last_fired",
              "fired_total", "fire_failed_total", "last_error", "newest_event_ts_ms",
              "apparent_skew_ms", "last_truncated", "truncated_polls", "unparsed_ts",
              "store_error_polls"):
        assert k in st
    assert st["apparent_skew_ms"] is None             # no event seen yet


# ── fire_failed_total's meaning (ADR-0058) ───────────────────────────────────
def test_an_injected_on_event_that_raises_is_counted(monkeypatch):
    """The counter exists for injected callbacks — the only thing that can still
    raise here once the evaluator degrades instead of dropping."""
    p = _paged_poller(monkeypatch, [[_det(1, "2026-06-21T10:00:00.0Z")]])
    p._seeded = True

    async def boom(rec):
        raise RuntimeError("injected handler blew up")
    p.on_event = boom

    assert _run(p.poll_once())["fired"] == 0
    assert p.fire_failed_total == 1
    assert p.status()["fire_failed_total"] == 1


def test_the_real_evaluator_cannot_increment_fire_failed_total(monkeypatch):
    """ADR-0058 claims this counter is **structurally** zero on the current wiring.

    That claim is only worth something if something enforces it, so: wire a REAL
    ``DetectionEvaluator`` whose rule store fails *every* read — the worst case
    that used to raise straight through ``evaluate`` — and the firing must still
    be delivered and the counter must stay at zero.
    """
    import sqlite3
    from types import SimpleNamespace

    from admz.events.evaluator import DetectionEvaluator

    class _AlwaysFailingRuleStore:
        version = 1

        def list(self, enabled_only=False):
            raise sqlite3.OperationalError("database is locked")

    ev = DetectionEvaluator(
        registry=SimpleNamespace(get_device_info=lambda d: {"tags": []}),
        store=_AlwaysFailingRuleStore(),
    )
    p = _paged_poller(monkeypatch, [[_det(1, "2026-06-21T10:00:00.0Z")]])
    p.on_event = ev.evaluate
    p._seeded = True

    assert _run(p.poll_once())["fired"] == 1     # the callback returned normally
    assert p.fire_failed_total == 0              # ...so nothing was lost
    assert p.status()["fire_failed_total"] == 0


# ── unchanged gating ─────────────────────────────────────────────────────────
def test_poll_is_noop_when_disabled(monkeypatch):
    p = _poller(monkeypatch, [_det(2, "2026-06-21T12:00:00.0Z")], enabled=False)
    res = _run(p.poll_once())
    assert res["enabled"] is False and res["fired"] == 0
    assert p.store.rows == []


def test_poll_swallows_search_failure(monkeypatch):
    import admz.events.config as cfg
    import admz.modules.acs_pro.events as acs_events
    monkeypatch.setattr(cfg, "acs_event_ingest_enabled", lambda: True)

    async def boom(catalog, executors, **kw):
        raise RuntimeError("acs unreachable")
    monkeypatch.setattr(acs_events, "search_detections", boom)
    from admz.events.acs_ingest import AcsActionRulePoller
    p = AcsActionRulePoller(catalog=None, executors={}, store=_Store())
    res = _run(p.poll_once())                        # must not raise
    assert res["fired"] == 0 and "error" in res
    assert p.last_error
