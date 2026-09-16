"""Drift triage — classify every drifted field, deterministically (ADR-0070 §1).

**ANNOTATE, NEVER SUPPRESS** — the contract ``attribution.py`` set (ADR-0056).
This module only *adds* keys: ``field["triage"]`` on each drifted row, and
``triage_context``, ``summary_by_class`` and ``highest_importance`` on the
report. It never removes a row and never touches ``bucket``, ``has_drift`` or
``revertable``. Per ADR-0055 a case-only change is still drift; triage labels
it ``cosmetic``, it does not hide it.

Code classifies; the model narrates and proposes. The rule table below is the
whole of ADMZ's knowledge about which differences matter. It is a Python tuple
so it can be edited without prompt surgery. The atlas has no per-parameter
volatility metadata today; when it grows some, the rows that state Axis facts
move there and this table keeps the rows that state ADMZ policy.

First match wins, and **the order carries the judgement**:

* identity sits above ``added_key``, so a new admin account is high even
  though it "appeared";
* ``runtime_state`` sits above network configuration, so a DHCP re-lease is
  not a security alarm;
* ``read_only`` sits below the security rules, so a change ADMZ cannot write
  back still reads high when it is a security change.

One refinement to ADR-0070's table: two ``service_config`` triggers — an
action rule, and an application started or stopped — are evaluated *above*
``read_only``. Both facets are read-only for restore by design (their writes
are deferred, not impossible), so below ``read_only`` those triggers could
never fire and every rule edit would read "low, accept or ignore".

Keys are matched on the canonical key with the ignore list's semantics
(``ignore.matches_any``: case-insensitive; a ``*`` glob crosses dots; a plain
pattern is exact-or-child), so an operator reads both lists the same way.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from admz.snapshot.ignore import matches_any

logger = logging.getLogger(__name__)

MISSING = "<missing>"

#: Lowest first — ``highest_importance`` is the maximum by this order.
IMPORTANCE_ORDER = ("none", "low", "medium", "high")

#: Recommendation tokens, as the model receives them.
ACCEPT = "accept"
IGNORE = "ignore"
ASK = "ask"
REPAIR = "repair"
NONE = "none"
ADOPT_OR_REVERT = "adopt_or_revert"
ACCEPT_OR_IGNORE = "accept_or_ignore"
REVERT_UNLESS_EXPLAINED = "revert_unless_explained"


@dataclass
class TriageContext:
    """Report-level facts every row is read against.

    ``firmware_changed`` is true only when the firmware at the baseline and at
    the observation are both known and differ — read from git, not remembered.
    """

    baseline_firmware: Optional[str] = None
    live_firmware: Optional[str] = None
    firmware_changed: bool = False
    #: ``{"accepted_at", "accepted_by", "note"}`` from ``BASELINE.yaml`` when it
    #: describes the baseline this report was diffed against.
    last_accept: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_firmware": self.baseline_firmware,
            "live_firmware": self.live_firmware,
            "firmware_changed": self.firmware_changed,
            "last_accept": dict(self.last_accept) if self.last_accept else None,
        }


@dataclass(frozen=True)
class _Row:
    """The parts of a drifted field the rules read."""

    key: str
    facet: str
    path: str
    expected: str
    actual: str
    bucket: str
    revertable: Optional[bool]

    @classmethod
    def of(cls, fld: Mapping[str, Any]) -> "_Row":
        facet = str(fld.get("facet") or "")
        path = str(fld.get("path") or "")
        key = fld.get("canonical_key") or f"{facet}:{path}"
        revertable = fld.get("revertable")
        return cls(
            key=str(key),
            facet=facet,
            path=path,
            expected=str(fld.get("expected")),
            actual=str(fld.get("actual")),
            bucket=str(fld.get("bucket") or "unclaimed"),
            revertable=revertable if isinstance(revertable, bool) else None,
        )

    @property
    def appeared(self) -> bool:
        return self.expected == MISSING

    @property
    def vanished(self) -> bool:
        return self.actual == MISSING

    def app_field(self, *names: str) -> bool:
        """True for an ``applications`` row whose last path segment is one of
        ``names`` (``<App>.status``, ``<App>.version``, ...)."""
        if self.facet != "applications":
            return False
        return self.path.rsplit(".", 1)[-1].lower() in names


# --------------------------------------------------------------------------- #
# Predicates
# --------------------------------------------------------------------------- #
_IDENTITY_KEYS = ("users:*", "root.Properties.API.HTTP.AdminAccess*")


def _identity_account(r: _Row, ctx: TriageContext) -> bool:
    return matches_any(r.key, list(_IDENTITY_KEYS))


def _app_installed_or_removed(r: _Row, ctx: TriageContext) -> bool:
    return r.app_field("status") and (r.appeared or r.vanished)


def _fold(value: str) -> str:
    return " ".join(value.split()).casefold()


def _same_number(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _cosmetic(r: _Row, ctx: TriageContext) -> bool:
    """Both sides present and equal after case-fold and whitespace collapse,
    or equal as numbers (KL-DRF-001)."""
    if r.appeared or r.vanished:
        return False
    return _fold(r.expected) == _fold(r.actual) or _same_number(r.expected, r.actual)


_FIRMWARE_KEYS = (
    "root.Properties.*",
    "*FirmwareManagement*",
    "*.Version",
    "*.Build",
    "root.Brand.*",
)


def _firmware_key(r: _Row, ctx: TriageContext) -> bool:
    # Applications are read by their own rules below: an app's version moving
    # is firmware-managed only when the firmware moved with it.
    return r.facet != "applications" and matches_any(r.key, list(_FIRMWARE_KEYS))


def _app_changed_with_firmware(r: _Row, ctx: TriageContext) -> bool:
    return ctx.firmware_changed and r.app_field("version", "signature")


def _appeared_with_firmware(r: _Row, ctx: TriageContext) -> bool:
    return ctx.firmware_changed and r.appeared


def _added(r: _Row, ctx: TriageContext) -> bool:
    return r.appeared


_RUNTIME_KEYS = (
    "root.Network.eth0.*",
    "root.Network.Routing.*",
    "root.Network.ZeroConf.*",
    "root.Network.DHCP.VendorClass",
    "root.Network.UPnP.FriendlyName",
    "root.Network.Bonjour.FriendlyName",
    "root.Network.Interface.*.dot1x.Status",
    "root.Time.ServerDate",
    "root.Time.ServerTime",
)
_NETWORK_PREFIX = "root.Network."


def _network_runtime_excluded(key: str) -> bool:
    """The network facet's own list of values the device, not the operator,
    controls (``NetworkFacet.RESTORE_EXCLUDE``), read with the facet's own
    matcher so the two can never disagree."""
    if not key.lower().startswith(_NETWORK_PREFIX.lower()):
        return False
    from admz.snapshot.facets.base import _matches_exclude
    from admz.snapshot.facets.network import NetworkFacet

    short = key[len(_NETWORK_PREFIX):]
    return any(_matches_exclude(short, p) for p in NetworkFacet.RESTORE_EXCLUDE)


def _runtime_state(r: _Row, ctx: TriageContext) -> bool:
    if any(seg.lower().startswith("volatile") for seg in r.key.split(".")):
        return True
    return matches_any(r.key, list(_RUNTIME_KEYS)) or _network_runtime_excluded(r.key)


_SECURITY_CONFIG_KEYS = (
    "root.Network.*",
    "root.HTTPS.*",
    "root.RemoteService.*",
    "root.SNMP.*",
    "root.RemoteSyslog.*",
    "root.SSH.*",
    "root.System.*Access*",
)


def _security_config(r: _Row, ctx: TriageContext) -> bool:
    return matches_any(r.key, list(_SECURITY_CONFIG_KEYS))


def _action_rule(r: _Row, ctx: TriageContext) -> bool:
    return r.facet == "action_rules"


def _app_run_state(r: _Row, ctx: TriageContext) -> bool:
    return r.app_field("status") and not (r.appeared or r.vanished)


def _read_only(r: _Row, ctx: TriageContext) -> bool:
    return r.revertable is False


_SERVICE_KEYS = (
    "root.Image.*",
    "root.StreamProfile.*",
    "root.Audio*",
    "root.Event.*",
    "root.IOPort.*",
    "root.Input.*",
    "root.Output.*",
    "root.Time.*",
    "root.PTZ.*",
    "root.Recording*",
    "root.Storage.*",
    "root.Motion*",
    "root.Overlay*",
)
_SERVICE_FACETS = frozenset({
    "ntp", "time_api", "sip", "event_mqtt_bridge", "event_schedules",
})


def _service_config(r: _Row, ctx: TriageContext) -> bool:
    return r.facet in _SERVICE_FACETS or matches_any(r.key, list(_SERVICE_KEYS))


def _always(r: _Row, ctx: TriageContext) -> bool:
    return True


def _bucket(name: str) -> Callable[[_Row, TriageContext], bool]:
    def test(r: _Row, ctx: TriageContext) -> bool:
        return r.bucket == name
    return test


def _fw_change(ctx: TriageContext) -> str:
    return f"{ctx.baseline_firmware} → {ctx.live_firmware}"


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    id: str
    cls: str
    importance: str
    recommendation: str
    test: Callable[[_Row, TriageContext], bool]
    why: Callable[[_Row, TriageContext], str]


def _say(text: str) -> Callable[[_Row, TriageContext], str]:
    return lambda r, ctx: text


RULES: tuple = (
    Rule("demo.set", "demo_set", "none", NONE, _bucket("demo_set"),
         _say("an active demo set this deliberately (ADR-0047); it is not drift")),
    Rule("demo.broken", "demo_broken", "high", REPAIR, _bucket("demo_broken"),
         _say("an active demo owns this key and the device no longer matches the demo")),
    Rule("demo.candidate", "demo_candidate", "medium", ADOPT_OR_REVERT,
         _bucket("candidate"),
         _say("the live value matches an inactive demo's config")),
    Rule("identity.account", "security_sensitive", "high", REVERT_UNLESS_EXPLAINED,
         _identity_account,
         _say("an account or admin-access setting changed")),
    Rule("identity.app_installed_or_removed", "security_sensitive", "high",
         REVERT_UNLESS_EXPLAINED, _app_installed_or_removed,
         lambda r, ctx: ("an application was installed" if r.appeared
                         else "an application was removed")),
    Rule("cosmetic.case_or_number", "cosmetic", "low", ACCEPT, _cosmetic,
         _say("only letter case, spacing or number formatting differs")),
    Rule("firmware.key", "firmware_managed", "low", ACCEPT, _firmware_key,
         _say("a value the firmware reports, not an operator setting")),
    Rule("firmware.app_with_upgrade", "firmware_managed", "low", ACCEPT,
         _app_changed_with_firmware,
         lambda r, ctx: ("the application changed along with the firmware "
                         f"({_fw_change(ctx)})")),
    Rule("firmware.appeared_with_upgrade", "firmware_managed", "low", ACCEPT,
         _appeared_with_firmware,
         lambda r, ctx: f"appeared after the firmware changed ({_fw_change(ctx)})"),
    Rule("added.key", "added_key", "low", ACCEPT, _added,
         _say("not in the baseline; the device added it")),
    Rule("runtime.state", "runtime_state", "low", IGNORE, _runtime_state,
         _say("runtime state the device or the network manages, not configuration")),
    Rule("security.config", "security_sensitive", "high", REVERT_UNLESS_EXPLAINED,
         _security_config,
         _say("network, remote-access or system-access configuration changed")),
    Rule("service.action_rule", "service_config", "medium", ASK, _action_rule,
         _say("an event action rule changed")),
    Rule("service.app_run_state", "service_config", "medium", ASK, _app_run_state,
         lambda r, ctx: f"an application went from {r.expected} to {r.actual}"),
    Rule("read_only.not_revertable", "read_only", "low", ACCEPT_OR_IGNORE, _read_only,
         _say("ADMZ cannot write this back; accept it or exclude it from tracking")),
    Rule("service.config", "service_config", "medium", ASK, _service_config,
         _say("changes how the device captures, streams, records or reacts")),
    Rule("uncategorized", "uncategorized", "medium", ASK, _always,
         _say("no triage rule covers this key")),
)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def classify_field(
    fld: Mapping[str, Any], context: Optional[TriageContext] = None,
) -> Dict[str, str]:
    """The triage label for one drifted-field dict. Raises only on a bug."""
    ctx = context or TriageContext()
    row = _Row.of(fld)
    for rule in RULES:
        if rule.test(row, ctx):
            return {
                "class": rule.cls,
                "importance": rule.importance,
                "recommendation": rule.recommendation,
                "why": rule.why(row, ctx),
                "rule": rule.id,
            }
    raise AssertionError("the last triage rule matches everything")


def _rank(importance: str) -> int:
    try:
        return IMPORTANCE_ORDER.index(importance)
    except ValueError:
        return 0


def highest_importance(labels: Iterable[Mapping[str, Any]]) -> str:
    best = "none"
    for label in labels:
        if _rank(label.get("importance", "none")) > _rank(best):
            best = label["importance"]
    return best


def summarize_by_class(labels: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``{class: {count, importance, recommendation}}``, most important class
    first, then the most common."""
    counts: Dict[str, Dict[str, Any]] = {}
    for label in labels:
        entry = counts.setdefault(label["class"], {
            "count": 0,
            "importance": label["importance"],
            "recommendation": label["recommendation"],
        })
        entry["count"] += 1
    ordered = sorted(
        counts.items(),
        key=lambda kv: (-_rank(kv[1]["importance"]), -kv[1]["count"], kv[0]),
    )
    return dict(ordered)


def annotate_triage(
    summary: Dict[str, Any], *, context: Optional[TriageContext] = None,
) -> Dict[str, Any]:
    """Add the triage keys to a drift summary. Mutates and returns it.

    Every label is computed before anything is written, so a rule that raises
    leaves the report exactly as it was — no row half-labelled. Triage is a
    reading aid and drift is not: a failure logs and returns the report.
    """
    try:
        ctx = context or TriageContext()
        fields = summary.get("drifted_fields") or []
        labels = [classify_field(fld, ctx) for fld in fields]
        by_class = summarize_by_class(labels)
        highest = highest_importance(labels)
        ctx_dict = ctx.to_dict()
    except Exception as e:  # noqa: BLE001 — see docstring
        logger.warning(
            "drift triage failed for %s (report left unannotated): %s",
            summary.get("device_id"), e,
        )
        return summary
    for fld, label in zip(fields, labels):
        fld["triage"] = label
    summary["triage_context"] = ctx_dict
    summary["summary_by_class"] = by_class
    summary["highest_importance"] = highest
    return summary


# --------------------------------------------------------------------------- #
# The one piece of I/O: the firmware and accept facts, read from git
# --------------------------------------------------------------------------- #
def _read_yaml(git_repo: Any, path: str, ref: str) -> Optional[Dict[str, Any]]:
    import yaml

    text = git_repo.get_file(path, ref)
    if not text:
        return None
    doc = yaml.safe_load(text)
    return doc if isinstance(doc, dict) else None


def _clean(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _firmware_at(git_repo: Any, device_id: str, sha: Optional[str]) -> Optional[str]:
    if not sha:
        return None
    doc = _read_yaml(git_repo, f"fleet/{device_id}/device.yaml", str(sha))
    return _clean((doc or {}).get("firmware_version"))


def report_context(
    summary: Mapping[str, Any], *, git_repo: Any, device_info: Mapping[str, Any],
) -> TriageContext:
    """The firmware at the baseline and at the observation, and the last
    accept note — best-effort, never raises.

    The engine writes ``firmware_version`` into ``fleet/<id>/device.yaml`` on
    every capture, so ``device.yaml`` at ``baseline_sha`` against the same file
    at ``observed_sha`` says whether the firmware moved. The registry is only
    the fallback for the live side, which it describes by construction.
    """
    ctx = TriageContext()
    try:
        device_id = str(summary.get("device_id") or device_info.get("device_id") or "")
        if device_id:
            from admz.validators import validate_identifier

            validate_identifier(device_id, "device_id")
        baseline_sha = summary.get("baseline_sha")
        observed_sha = summary.get("observed_sha")
        if git_repo is not None and device_id:
            ctx.baseline_firmware = _firmware_at(git_repo, device_id, baseline_sha)
            ctx.live_firmware = _firmware_at(git_repo, device_id, observed_sha)
        if ctx.live_firmware is None:
            ctx.live_firmware = _clean(device_info.get("firmware_version"))
        ctx.firmware_changed = bool(
            ctx.baseline_firmware and ctx.live_firmware
            and ctx.baseline_firmware != ctx.live_firmware
        )
        if git_repo is not None and device_id and baseline_sha:
            doc = _read_yaml(git_repo, f"fleet/{device_id}/BASELINE.yaml", "HEAD")
            if doc and doc.get("baseline_sha") == baseline_sha:
                ctx.last_accept = {
                    "accepted_at": doc.get("accepted_at"),
                    "accepted_by": doc.get("accepted_by"),
                    "note": doc.get("note"),
                }
    except Exception as e:  # noqa: BLE001 — context is a nicety
        logger.debug("triage context unavailable: %s", e)
    return ctx
