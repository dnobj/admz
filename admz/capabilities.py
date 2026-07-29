"""Advanced capability switches — one declared registry (GH #132).

ADMZ has always had a handful of powerful, dangerous, or privileged-install
switches, each invented separately: an env var here, a fleet setting there, a
bespoke truthiness parse in every one. Nothing anywhere answered the operator's
question — *"what non-default powers is this installation running with?"* —
without reading source.

This module is that answer. :data:`CAPABILITIES` is **one table** you read top to
bottom to know the whole truth, in the same spirit as
``PROTECTED_SETTING_KEYS``.

**It declares; it does not enforce.** Per the issue's explicit non-goals and the
Master resolutions in ``docs/plans/advanced-switches.md``, this is *not* a
security boundary — anyone who can set an environment variable or edit
``fleet_settings`` already owns the machine. The registry prevents **accidents**
and makes **state legible**. It never removes a confirmation gate (ADR-0034); at
most a capability changes *who may satisfy* a gate, never *whether* one exists.

**Slice 2 made the declaration load-bearing.** Every migrated call site now
delegates here — :func:`is_active` is *the* read path, so there is exactly one
truthiness parse in the codebase and the registry can no longer disagree with
the code it describes. Two consequences worth stating plainly:

* :func:`truthy` (``{"1","true","yes","on"}``) replaced three different parses.
  For the values anyone actually uses (``1`` / unset) nothing changes. One
  exotic value changed meaning on purpose: ``ADMZ_DISABLE_ONBOARDING_PROBES=0``
  used to mean **on** (``onboarding.py`` tested a bare ``if os.getenv(...)``,
  so any non-empty string was true) and now means **off**. Nobody sets a
  disable flag to ``0`` intending to disable; the plan records it as a fix.
  Symmetrically ``ADMZ_EVENT_INGEST=true`` used to mean **off** (``== "1"``)
  and now means **on**.
* ``survey.contributor`` gained its ``ADMZ_SURVEY_MODE`` env alias in the same
  commit as its call-site delegation — the first moment declaring it stopped
  being a lie — so it is now ``("env", "setting")`` like the other privileged
  rows. The setting stays authoritative when the env var is unset.

**Leaf-light by design.** Import time pulls in stdlib only; ``fleet_settings``
and ``audit`` are imported lazily *inside* functions, the discipline documented
at ``admz/modules/contract.py`` and used at ``admz/modules/acs_pro/config.py``.
The stdio MCP subprocess, the ``operations`` layer, and the nav builder all have
to be able to ask "is this on?" without dragging in FastAPI or an executor.

Plan: ``docs/plans/advanced-switches.md``. ADR-0052 (slice 3).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Truthiness — ONE parse, everywhere
# ---------------------------------------------------------------------------

#: The only accepted "on" spellings. Exported so slice 2's call sites can adopt
#: it verbatim instead of inventing a fourth parse.
TRUTHY_VALUES: frozenset = frozenset({"1", "true", "yes", "on"})


def truthy(raw: object) -> bool:
    """True iff ``raw`` spells one of :data:`TRUTHY_VALUES` (case-insensitive).

    ``None``, ``""``, ``"0"``, ``"false"``, and ``"maybe"`` are all False. Note
    that ``"0"`` being False is the *point*: the pre-registry
    ``if os.getenv(...)`` idiom treated any non-empty string as True, so
    ``ADMZ_DISABLE_ONBOARDING_PROBES=0`` meant **enabled**.
    """
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in TRUTHY_VALUES


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

#: Danger classes — five, deliberately few.
#:
#: ``dev-only``        never appropriate outside development
#: ``dangerous``       writes outside ADMZ's normal gated write paths
#: ``privileged``      legitimate, but a privileged install profile
#: ``test-suppressor`` turns *off* production behaviour for determinism
#: ``internal``        ADMZ sets it for its own subprocesses; not operator-facing
DANGER_CLASSES: Tuple[str, ...] = (
    "dev-only",
    "dangerous",
    "privileged",
    "test-suppressor",
    "internal",
)

#: Classes that are fine to see on a production install. ``privileged`` is on
#: this list because a survey/ingest install is a legitimate deployment profile
#: — it earns an amber chip, not a WARNING. Everything else is loud.
_PRODUCTION_APPROPRIATE_CLASSES: Tuple[str, ...] = ("privileged", "internal")


@dataclass(frozen=True)
class Capability:
    """One declared advanced capability.

    ``env_var`` / ``setting_key`` are the **existing** names, unchanged — the
    registry documents what is already there rather than renaming anything.
    """

    id: str                              # "dev.auto_approve" — dotted, stable, the audit key
    title: str                           # "Dev auto-approver"
    description: str                     # one operator-readable sentence
    danger: str                          # one of DANGER_CLASSES
    production_appropriate: bool         # False → startup WARNING + red chip when active
    enable_via: Tuple[str, ...]          # ("env",) | ("env", "setting") | ("setting",)
    env_var: str = ""                    # required iff "env" in enable_via
    setting_key: str = ""                # required iff "setting" in enable_via
    companion_env: Tuple[str, ...] = ()  # credentials/inputs — documented, not declared
    since: str = ""                      # ADR / issue provenance
    notes: str = ""                      # why it exists; what breaks if you leave it on


CAPABILITIES: Tuple[Capability, ...] = (
    Capability(
        id="dev.auto_approve",
        title="Dev auto-approver",
        description=(
            "Lets the unattended approver in tools/dev_auto_approve.py complete "
            "url_* confirmation gates that are meant for a human, so end-to-end "
            "tests can run without one."
        ),
        danger="dev-only",
        production_appropriate=False,
        enable_via=("env",),
        env_var="ADMZ_DEV_AUTO_APPROVE",
        companion_env=("ADMZ_DEV_API_KEY", "ADMZ_DEV_CONFIRM_PASSWORD"),
        since="docs/DEV_AUTO_APPROVE.md",
        notes=(
            "The gate still fires — this only changes WHO may satisfy it "
            "(ADR-0034 is untouched). The approver posts to the real endpoint "
            "exactly as a browser does, so the server cannot tell the "
            "difference; the registry's job is to make sure nobody is "
            "surprised by that. Never appropriate in production."
        ),
    ),
    Capability(
        id="dev.test_auth",
        title="Test auth mode",
        description=(
            "Resolves any otherwise-unauthenticated request to a fixed "
            "synthetic principal (test\\agent by default), so an unattended "
            "agent can drive a staging instance without a human sign-in."
        ),
        danger="dev-only",
        production_appropriate=False,
        enable_via=("env",),
        env_var="ADMZ_TEST_AUTH",
        companion_env=("ADMZ_TEST_AUTH_USER", "ADMZ_TEST_AUTH_GROUPS"),
        since="#140",
        notes=(
            "Exists because windows-local (ADR-0035 Negotiate SSO) cannot be "
            "completed headlessly, and ADMZ_AUTH_BACKEND=none is not a "
            "substitute: the anonymous principal is refused by every "
            "require_authenticated_principal surface. This yields a real "
            "principal instead. It never softens a confirmation gate — "
            "ADR-0034 applies in full; it changes WHO the caller is, never "
            "whether approval is required. The synthetic principal is in the "
            "reveal groups by default (ADMZ_TEST_AUTH_GROUPS overrides, and "
            "an empty value gives it none), so it can read plaintext device "
            "credentials — which is why admz/__main__.py refuses to start the "
            "server at all when this is active and the bind address is not "
            "loopback, with no override."
        ),
    ),
    Capability(
        id="test.no_onboarding_probes",
        title="Onboarding probes suppressed",
        description=(
            "Skips the network probes onboarding runs against a newly added "
            "device; every add returns credentials_needed instead."
        ),
        danger="test-suppressor",
        production_appropriate=False,
        enable_via=("env",),
        env_var="ADMZ_DISABLE_ONBOARDING_PROBES",
        since="#101",
        notes=(
            "Set by tests/conftest.py so unit tests never probe whatever LAN "
            "the test box sits on. On a real install it silently disables "
            "automatic credential resolution."
        ),
    ),
    Capability(
        id="test.no_github_push",
        title="GitHub App push suppressed",
        description=(
            "Short-circuits installation-token minting so config-repo pushes "
            "never authenticate or reach GitHub."
        ),
        danger="test-suppressor",
        production_appropriate=False,
        enable_via=("env",),
        env_var="ADMZ_DISABLE_GITHUB_APP_PUSH",
        since="ADR-0045",
        notes=(
            "Set by tests/conftest.py so a developer's *connected* box does "
            "not mint a real token mid-test. On a real install, config backups "
            "silently stop reaching the remote."
        ),
    ),
    Capability(
        id="runtime.no_scheduler",
        title="Subprocess scheduler suppression",
        description=(
            "Tells an MCP process not to start a SnapshotScheduler because the "
            "parent uvicorn process already owns one."
        ),
        danger="internal",
        production_appropriate=True,
        enable_via=("env",),
        env_var="ADMZ_MCP_NO_SCHEDULER",
        since="review-2026-06-10 H-1",
        notes=(
            "ADMZ sets this for its own pool subprocesses "
            "(chatbot/mcp_pool.py, chatbot/voice.py), never an operator. "
            "Declared so 'why didn't my schedule fire?' is answerable from "
            "diagnostics; it never chips and is never offered as a toggle."
        ),
    ),
    Capability(
        id="acs.firebird_read",
        title="ACS Firebird direct reads",
        description=(
            "Reads named action-rule firings straight out of ACS Pro's "
            "embedded Firebird database instead of the supported API."
        ),
        danger="privileged",
        production_appropriate=True,
        enable_via=("env", "setting"),
        env_var="ADMZ_ACS_FIREBIRD",
        setting_key="acs_firebird_enabled",
        since="ADR-0041",
        notes=(
            "Unsupported, version-specific schema — an ACS upgrade can change "
            "it without notice. Read-only; requires the Firebird client "
            "library and a readable copy of the DB."
        ),
    ),
    Capability(
        id="events.device_ingest",
        title="Device event ingest",
        description=(
            "Opens device-direct VAPIX WebSockets fleet-wide and persists the "
            "matching events."
        ),
        danger="privileged",
        production_appropriate=True,
        enable_via=("env", "setting"),
        env_var="ADMZ_EVENT_INGEST",
        setting_key="event_ingest_enabled",
        since="ADR-0041",
        notes=(
            "A background loop that contacts every watched device. Must stay "
            "stoppable at runtime, which is why it is settings-enablable and "
            "not env-only."
        ),
    ),
    Capability(
        id="events.acs_poll",
        title="ACS action-rule poller",
        description=(
            "Polls the ACS Pro recorded-event log for action-rule firings "
            "(ACS has no push API)."
        ),
        danger="privileged",
        production_appropriate=True,
        enable_via=("env", "setting"),
        env_var="ADMZ_ACS_EVENT_INGEST",
        setting_key="acs_event_ingest_enabled",
        since="ADR-0041",
        notes=(
            "Also requires the ACS Pro module to be connected; the poller "
            "checks that itself."
        ),
    ),
    Capability(
        id="survey.contributor",
        title="Survey / contributor mode",
        description=(
            "Surveys devices for undocumented API/rule knowledge and opens "
            "redacted pull requests against the upstream atlas repo."
        ),
        danger="privileged",
        production_appropriate=True,
        enable_via=("env", "setting"),
        env_var="ADMZ_SURVEY_MODE",
        setting_key="survey_mode_enabled",
        since="ADR-0030",
        notes=(
            "A privileged install profile: a background loop that contacts "
            "devices and pushes to GitHub under a stored PAT. The setting is "
            "the authoritative knob and the one /settings/survey writes; "
            "ADMZ_SURVEY_MODE is an additive env alias (slice 2) so a "
            "locked-down privileged install can force it on without a "
            "writable settings row."
        ),
    ),
    Capability(
        id="acs.rule_write",
        title="ACS action-rule writing",
        description=(
            "Creates and edits ACS Pro action rules by writing directly to the "
            "embedded Firebird database."
        ),
        danger="dangerous",
        production_appropriate=False,
        enable_via=("env",),
        env_var="ADMZ_ACS_RULE_WRITE",
        since="#131",
        notes=(
            "DECLARED, NOT YET IMPLEMENTED — #131 builds it and this row is "
            "what it registers against. Direct writes to an unsupported, "
            "version-specific schema that ACS itself caches: corruption is a "
            "realistic outcome. Env-only by design, so it can never be a "
            "click in a browser."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Everything else: ordinary config, and names that only look like env vars
# ---------------------------------------------------------------------------

#: ``ADMZ_*`` environment variables that are deliberately **not** capabilities:
#: paths, timeouts, credentials, model names, deployment posture. Listed
#: explicitly so the drift guard in ``tests/test_advanced_capabilities.py``
#: fails until a newly added env var has been consciously classified. A
#: registry that silently goes stale is worse than no registry.
#:
#: Three of these get re-raised as capability candidates often enough to be
#: worth naming here: ``ADMZ_AUTH_BACKEND=none`` and
#: ``ADMZ_AUTH_INSECURE_BIND_OK`` already emit their own dedicated startup
#: WARNINGs and are deployment *posture*, not switches — registering them would
#: leave every dev box permanently chipped and train operators to ignore the
#: chip. ``ADMZ_VERIFY_SSL`` defaults to False, so turning it *on* raises
#: safety; a capability it is not.
ORDINARY_CONFIG: Tuple[str, ...] = (
    "ADMZ_ALLOWED_ORIGINS",
    "ADMZ_AUTH_BACKEND",
    "ADMZ_AUTH_INSECURE_BIND_OK",
    "ADMZ_AUTH_REMOTE_USER_HEADER",
    "ADMZ_AUTH_TRUSTED_PROXIES",
    "ADMZ_AUTO_PUSH",
    "ADMZ_BASE_URL",
    "ADMZ_CATALOG_PATH",
    "ADMZ_CHAT_EVENT_TIMEOUT_SECONDS",
    "ADMZ_CHAT_MAX_TOOL_RESULT_CHARS",
    "ADMZ_CONFIG_REPO_PATH",
    "ADMZ_CONFIG_REPO_REMOTE",
    "ADMZ_DB_PATH",
    "ADMZ_GEMINI_API_KEY",
    "ADMZ_GEMINI_DEFAULT_MODEL",
    "ADMZ_GEMINI_EMPTY_RETRIES",
    "ADMZ_GEMINI_EMPTY_RETRY_THINKING_BUDGET",
    "ADMZ_GEMINI_MANUAL_TOOL_LOOP",
    "ADMZ_GEMINI_MAX_TOOL_ITERATIONS",
    "ADMZ_GEMINI_RETRY_BASE_DELAY",
    "ADMZ_GEMINI_RETRY_MAX_ATTEMPTS",
    "ADMZ_GEMINI_THINKING_BUDGET",
    "ADMZ_GH_TOKEN",
    "ADMZ_GIT_AUTHOR_EMAIL",
    "ADMZ_GIT_AUTHOR_NAME",
    "ADMZ_GIT_LOCAL_TIMEOUT_SECONDS",
    "ADMZ_GIT_NETWORK_TIMEOUT_SECONDS",
    "ADMZ_HEALTH_INTERVAL_SECONDS",
    "ADMZ_HEALTH_TIMEOUT_SECONDS",
    "ADMZ_HOME",
    "ADMZ_KEY_PATH",
    "ADMZ_LDAP_BASE_DN",
    "ADMZ_LDAP_BIND_PASSWORD",
    "ADMZ_LDAP_BIND_USER",
    "ADMZ_LDAP_ENABLED",
    "ADMZ_LDAP_GROUP_CACHE_TTL",
    "ADMZ_LDAP_SERVER",
    "ADMZ_LOG_FORMAT",
    "ADMZ_LOG_LEVEL",
    "ADMZ_MCP_POOL_IDLE_SECONDS",
    "ADMZ_PORT",
    "ADMZ_PRINCIPAL_DISPLAY_NAME",
    "ADMZ_PRINCIPAL_DOMAIN",
    "ADMZ_PRINCIPAL_GROUPS",
    "ADMZ_PRINCIPAL_NAME",
    "ADMZ_PRINCIPAL_SOURCE",
    "ADMZ_REPO_PATH_ROOT",
    "ADMZ_REVEAL_GROUPS",
    "ADMZ_SESSION_COOKIE_SECURE",
    "ADMZ_SESSION_TTL_SECONDS",
    "ADMZ_SNAPSHOT_FLEET_CONCURRENCY",
    "ADMZ_SSO_NEGOTIATE",
    "ADMZ_SURVEY_OUT",
    "ADMZ_SURVEY_WORK",
    "ADMZ_VAPIX_RETRIES",
    "ADMZ_VERIFY_SSL",
)

#: ``ADMZ_*`` identifiers that appear in source but are **not** environment
#: variables at all, so the drift guard can tell "unclassified" from
#: "not applicable" instead of quietly mislabelling them as config.
NOT_ENV_VARS: Tuple[str, ...] = (
    "ADMZ_VERSION",        # import alias in admz/survey/runner.py
    "ADMZ_WEBHOOK_PATH",   # module constant in admz/demos/inference/observability.py
    "ADMZ_PRINCIPAL_",     # docstring prefix in admz/session_store.py
)


# ---------------------------------------------------------------------------
# Errors — only :func:`set_enabled` raises; every read path answers False
# ---------------------------------------------------------------------------


class CapabilityError(Exception):
    """Base class for the two things a capability *write* can refuse."""


class UnknownCapability(CapabilityError):
    """No such capability id. Reads return False for these; writes refuse."""


class NotToggleable(CapabilityError):
    """The capability is ``("env",)`` — env-only, by design.

    ``dev-only``, ``dangerous``, ``test-suppressor`` and ``internal``
    capabilities are deliberately not runtime-toggleable, so enabling one is an
    act by somebody with service control on the box rather than a click in a
    browser. The message names the env var and says a restart is needed,
    because that is what the operator actually has to do next.
    """


# ---------------------------------------------------------------------------
# Lookup + read predicates
# ---------------------------------------------------------------------------

_BY_ID: Dict[str, Capability] = {c.id: c for c in CAPABILITIES}

# Unknown ids are a programming error, not an operator one — log each once so a
# typo is visible without a log flood from a per-request call site.
_WARNED_UNKNOWN: Set[str] = set()


@dataclass(frozen=True)
class ActiveCapability:
    """A capability that is currently on, and where that came from."""

    capability: Capability
    source: str  # "env" | "setting"

    @property
    def id(self) -> str:
        return self.capability.id


def get(cap_id: str) -> Optional[Capability]:
    """The declared :class:`Capability`, or None for an unknown id."""
    return _BY_ID.get(cap_id)


def all_capabilities() -> Tuple[Capability, ...]:
    """The whole declaration table."""
    return CAPABILITIES


def _settings():
    # Lazy import — this module must stay importable in the leaf/MCP context.
    from admz.fleet_settings import fleet_settings

    return fleet_settings


def _unknown(cap_id: str) -> None:
    if cap_id not in _WARNED_UNKNOWN:
        _WARNED_UNKNOWN.add(cap_id)
        logger.warning("unknown advanced capability id: %r", cap_id)


def source_of(cap_id: str) -> str:
    """Where ``cap_id`` is currently enabled from: ``"env"``, ``"setting"``, or
    ``""`` when it is off (or unknown).

    Env is checked **first** — a setting can never turn off an env-forced
    capability. That matches ``events/config.py`` exactly, which is the shape
    this generalizes rather than invents.
    """
    cap = _BY_ID.get(cap_id)
    if cap is None:
        _unknown(cap_id)
        return ""
    if "env" in cap.enable_via and cap.env_var and truthy(os.environ.get(cap.env_var)):
        return "env"
    if "setting" in cap.enable_via and cap.setting_key:
        try:
            if truthy(_settings().get(cap.setting_key)):
                return "setting"
        except Exception:  # noqa: BLE001 — config must never break a request
            logger.debug(
                "capability %s: settings read failed, falling back to env only",
                cap_id, exc_info=True,
            )
    return ""


def is_active(cap_id: str) -> bool:
    """True iff ``cap_id`` is currently enabled. Unknown ids are False."""
    return bool(source_of(cap_id))


def active_capabilities() -> List[ActiveCapability]:
    """Every currently-enabled capability, in declaration order."""
    out: List[ActiveCapability] = []
    for cap in CAPABILITIES:
        src = source_of(cap.id)
        if src:
            out.append(ActiveCapability(capability=cap, source=src))
    return out


def active_ids() -> List[str]:
    """Ids of the currently-enabled capabilities — what ``/api/health`` reports.

    Ids only, never values: the point is to answer "what mode was this running
    in?" without leaking a setting name or a credential.
    """
    return [a.id for a in active_capabilities()]


# ---------------------------------------------------------------------------
# The write path — privileged capabilities only, always audited
# ---------------------------------------------------------------------------


def is_toggleable(cap_id: str) -> bool:
    """Whether ``cap_id`` can be flipped at runtime (i.e. has a setting).

    False for every ``dev-only`` / ``dangerous`` / ``test-suppressor`` /
    ``internal`` capability — those need an env var and a service restart, so
    the advanced page renders them as read-only facts rather than controls.
    """
    cap = _BY_ID.get(cap_id)
    return bool(cap and "setting" in cap.enable_via and cap.setting_key)


def set_enabled(
    cap_id: str,
    on: bool,
    principal: object = None,
    *,
    reason: str = "",
) -> str:
    """Turn a settings-enablable capability on or off, and audit who did it.

    Returns the capability's :func:`source_of` **after** the write, so a caller
    can tell the operator the one surprising outcome: disabling the setting on
    an install where the env var also forces the capability on leaves it
    active, and the returned source is still ``"env"``.

    Raises :class:`UnknownCapability` for an id that is not declared and
    :class:`NotToggleable` for an env-only one — the two cases the REST layer
    turns into 404 and 409 respectively.

    The audit row is written after the store write, not before, so a row can
    never claim a change that did not land. It is deliberately *not* wrapped in
    ``try/except``: the read paths must never break a request, but an
    unauditable privileged toggle should fail loudly rather than happen
    silently.
    """
    cap = _BY_ID.get(cap_id)
    if cap is None:
        raise UnknownCapability(f"unknown advanced capability: {cap_id!r}")
    if "setting" not in cap.enable_via or not cap.setting_key:
        raise NotToggleable(
            f"{cap.id} is enabled by environment variable only. Set "
            f"{cap.env_var}=1 on the ADMZ service and restart it; it is "
            f"deliberately not toggleable at runtime because it is "
            f"class '{cap.danger}'."
        )

    _settings().set(cap.setting_key, "true" if on else "false")
    source = source_of(cap.id)

    from admz.audit import record_event

    record_event(
        principal,
        "capability.enable" if on else "capability.disable",
        resource=f"capability:{cap.id}",
        details={
            "title": cap.title,
            "danger": cap.danger,
            "setting_key": cap.setting_key,
            "reason": reason,
            # Post-write truth, not what was asked for: an env-forced
            # capability stays on however the setting is written.
            "source": source,
            "active": bool(source),
        },
    )
    return source


# ---------------------------------------------------------------------------
# Startup honesty
# ---------------------------------------------------------------------------


def startup_lines() -> List[Tuple[int, str]]:
    """``(loglevel, message)`` pairs for the boot banner — **data, not log calls**.

    The API process logs them on ``admz.security``, the MCP process logs them to
    stderr, and the CLI prints them under its banner. Returning data keeps all
    three honest and makes the behaviour trivially testable.

    Exactly one INFO line when nothing is active; otherwise one INFO summary
    plus one WARNING per active capability that is not production-appropriate.
    """
    act = active_capabilities()
    if not act:
        return [(logging.INFO, "advanced capabilities: none")]

    summary = ", ".join(f"{a.id} (via {a.source})" for a in act)
    lines: List[Tuple[int, str]] = [
        (logging.INFO, f"advanced capabilities active: {summary}")
    ]
    for a in act:
        cap = a.capability
        if cap.production_appropriate:
            continue
        knob = cap.env_var if a.source == "env" else cap.setting_key
        lines.append((
            logging.WARNING,
            f"ADVANCED CAPABILITY ACTIVE: {cap.id} [{cap.danger}] "
            f"enabled via {a.source} ({knob}) — {cap.description} "
            f"This is not appropriate for a production installation.",
        ))
    return lines


def log_startup_lines(log: Optional[logging.Logger] = None) -> None:
    """Emit :func:`startup_lines` on ``log`` (default ``admz.security``)."""
    target = log if log is not None else logging.getLogger("admz.security")
    for level, message in startup_lines():
        target.log(level, message)


# Once per process — the "boot" in "once-per-boot audit row".
_BOOT_AUDIT_DONE = False


def _boot_auditable(cap: Capability) -> bool:
    """Whether ``cap`` being active at boot is worth a persistent audit row.

    Loud capabilities are, with one deliberate exception: ``test-suppressor``.

    A suppressor being active is a **test-harness artifact**, not a power an
    operator granted the installation — it is set by ``tests/conftest.py``
    before any app exists, and the audit trail exists to record what powers an
    install is running with, not that a unit-test process booted. The three
    other loudness channels (the startup WARNING, ``/api/health``, and slice 2's
    red chip) still cover suppressors in full, so nothing an operator needs is
    lost; only the persistent row is dropped.

    This also removes a real hazard rather than a cosmetic one. Every store in
    ADMZ binds its DB path at import, so a test that does not isolate
    ``ADMZ_HOME`` writes to the operator's real database — the project's
    standing test-isolation lesson. A boot-time writer that fires under the two
    suite-wide suppressors would have polluted the real audit log on every
    pytest run. With suppressors excluded, no test in the suite can reach it.

    Expressed as an *exclusion* rather than an allow-list on purpose: a danger
    class added later is audited by default, which is the right failure
    direction for an audit trail.
    """
    return not cap.production_appropriate and cap.danger != "test-suppressor"


def record_boot_audit() -> None:
    """Write the once-per-boot ``capability.active`` audit rows.

    An env-enabled capability **cannot** be audited at enable-time: there is no
    event and no actor. Saying that plainly matters — the audit answer for an
    env capability is "it was on at boot", not "alice turned it on". So each
    active capability that passes :func:`_boot_auditable` gets one row
    attributed to ``system`` at startup. (Slice 2 adds the attributed
    ``capability.enable``/``capability.disable`` rows for settings toggles.)

    Called by the API lifespan only. The MCP pool spawns one subprocess per
    principal, so it logs the same lines but deliberately writes no rows —
    otherwise a chatty console would fill the audit log with boot notices.

    Idempotent per process and never raises: diagnostics must not break startup.
    """
    global _BOOT_AUDIT_DONE
    if _BOOT_AUDIT_DONE:
        return
    _BOOT_AUDIT_DONE = True

    loud = [a for a in active_capabilities() if _boot_auditable(a.capability)]
    if not loud:
        return
    try:
        from types import SimpleNamespace

        from admz.audit import record_event

        principal = SimpleNamespace(name="system", source="startup")
        for a in loud:
            record_event(
                principal,
                "capability.active",
                resource=f"capability:{a.id}",
                details={
                    "title": a.capability.title,
                    "danger": a.capability.danger,
                    "source": a.source,
                    "note": (
                        "on at boot — an env-enabled capability has no "
                        "enable-time actor to attribute"
                    ),
                },
            )
    except Exception:  # noqa: BLE001 — audit must never block startup
        logger.debug("capability boot audit failed", exc_info=True)
