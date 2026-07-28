"""
FastAPI application for ADMZ - Axis Device Management Zone.

Provides REST API + Web UI for the full ADMZ surface, mirroring the
MCP server: device registry, credential capture, network discovery,
catalog query/execution, multi-step plans, configuration snapshot/
restore/diff/drift, and scheduled snapshots.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admz.api.context import init_context
from admz.api.routes import (
    api_keys as api_keys_route,
    audit as audit_route,
    auth_web as auth_web_route,
    capture,
    catalog,
    chat as chat_route,
    confirm,
    detections as detections_route,
    demos as demos_route,
    watched_events as watched_events_route,
    devices,
    discovery,
    github_app as github_app_route,
    drift as drift_route,
    events as events_route,
    health as health_route,
    plans,
    rule_capture as rule_capture_route,
    schedules,
    snapshot,
    tasks as tasks_route,
    survey as survey_route,
    voice as voice_route,
    web,
)
from admz import __version__
from admz.auth import auth_middleware
from admz.factory import create_device_registry


# Module-level registry alias, for backward compatibility with routes
# that historically imported `registry` from this module.
registry = None


def _warn_anonymous_auth_backend() -> None:
    """Emit a one-time WARNING when ``ADMZ_AUTH_BACKEND=none`` is active.

    CR-3: under the default backend every request is mapped to the
    synthetic ``anonymous`` principal. That's intentional for local
    dev (and the localhost-only ``--host 127.0.0.1`` default bounds
    exposure) but operators should know that every mutation will be
    attributed to ``anonymous`` in the audit log, and that the most
    destructive endpoints (mint API key, write protected fleet
    settings, delete device, restore device, execute plan) refuse
    the anonymous principal — they require switching the backend
    to ``api-key``, ``windows``, or ``composite``.
    """
    import logging

    backend = (os.getenv("ADMZ_AUTH_BACKEND", "none") or "none").strip().lower()
    if backend != "none":
        return
    logger = logging.getLogger("admz.security")
    logger.warning(
        "ADMZ_AUTH_BACKEND=none — anonymous principal has read + "
        "low-risk-write access to every endpoint. Five destructive "
        "endpoints (mint API key, write protected fleet settings, "
        "delete device, restore device, execute plan) refuse "
        "anonymous and require an API key or Windows IWA. Every "
        "mutation is audit-logged as 'anonymous'. To unblock the "
        "destructive endpoints set ADMZ_AUTH_BACKEND=api-key (and "
        "mint a key) or ADMZ_AUTH_BACKEND=composite (and stand up "
        "Windows IWA behind a reverse proxy)."
    )


def _log_active_capabilities() -> None:
    """Say out loud which advanced capabilities this install is running with.

    GH #132: a log excerpt should answer "what mode was this running in?".
    Exactly one INFO line when nothing is active; one WARNING per active
    capability that is not appropriate for production (the dev auto-approver,
    the test suppressors, direct ACS rule writes). Also writes the
    once-per-boot ``capability.active`` audit rows — an env-enabled capability
    has no enable-time actor to attribute, so "it was on at boot" is the only
    honest audit answer.

    Diagnostics must never break startup, so everything is best-effort.
    """
    import logging

    try:
        from admz import capabilities

        capabilities.log_startup_lines(logging.getLogger("admz.security"))
        capabilities.record_boot_audit()
    except Exception:  # noqa: BLE001 — never block startup on diagnostics
        logging.getLogger(__name__).warning(
            "advanced-capability startup logging failed", exc_info=True
        )


def _advanced_capability_ids() -> list:
    """Ids of the active advanced capabilities, for ``/api/health``.

    Ids only — never a value, never a setting name. Never raises: an
    unreachable settings store must not turn a readiness probe into a 500.
    """
    try:
        from admz import capabilities

        return capabilities.active_ids()
    except Exception:  # noqa: BLE001
        return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize context + start scheduler on startup; clean up on shutdown."""
    global registry
    _warn_anonymous_auth_backend()
    _log_active_capabilities()
    registry = create_device_registry()
    ctx = init_context(registry)

    # One-time migration of the legacy schedules.json + pending_device_actions
    # into the unified tasks table (ADR-0037). Idempotent + non-destructive, so
    # safe to run every startup; the scheduler + sweep read the tasks store.
    try:
        from admz.tasks.migrate import migrate_legacy
        migrate_legacy()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "tasks migration failed", exc_info=True
        )

    # Install the unified task-handler context (reprovision + scheduled handlers)
    # so the health-monitor sweep can fire pre-approved detection tasks.
    try:
        from admz.recovery_actions import register_recovery_handlers
        register_recovery_handlers(ctx)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "task context install failed", exc_info=True
        )

    # Seed shipped default ignore rules (observed network/DHCP churn) into
    # the operator-editable store, once each — idempotent + deletion-safe.
    try:
        from admz.snapshot.ignore import seed_default_rules
        seed_default_rules()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("ignore-rule seeding failed", exc_info=True)

    await ctx.scheduler.start()

    # Device health monitor: opt-in via the health_monitor_enabled
    # fleet setting. .start() is a no-op when the flag is off, so
    # always safe to call here.
    await ctx.health_monitor.start()

    # ADR-0041: live device-event ingest supervisor. Opt-in via the
    # event_ingest_enabled fleet setting; .start() is a no-op when off.
    try:
        await ctx.event_supervisor.start()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("event ingest start failed", exc_info=True)

    # ADR-0041: ACS Pro action-rule poller. Opt-in via acs_event_ingest_enabled
    # (and requires the ACS module connected); .start() is a no-op when off.
    try:
        await ctx.acs_event_poller.start()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("acs event poller start failed", exc_info=True)

    # ADR-0041: ACS Pro Firebird firing poller — named rule firings read from a
    # read-only copy of ACS's embedded DB (no per-rule edit). Opt-in via
    # acs_firebird_enabled + ACS connected + driver/files present; no-op when off.
    try:
        await ctx.acs_firebird_poller.start()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("acs firebird poller start failed", exc_info=True)

    # Phase 7: spin up the per-principal MCP subprocess pool so the
    # first chat turn doesn't pay subprocess-spawn latency.
    from admz.chatbot.mcp_pool import mcp_pool
    await mcp_pool.start()

    try:
        yield
    finally:
        await mcp_pool.stop()
        try:
            await ctx.event_supervisor.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            await ctx.acs_event_poller.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            await ctx.acs_firebird_poller.stop()
        except Exception:  # noqa: BLE001
            pass
        await ctx.health_monitor.stop()
        await ctx.scheduler.stop()
        # Best-effort cleanup; close() is a no-op for backends that
        # don't hold persistent connections, but exists for the few that do.
        close = getattr(registry, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover — defensive
                pass

app = FastAPI(
    title="ADMZ - Axis Device Management Zone",
    description=(
        "Device management, credential storage, and configuration-as-code "
        "for Axis network devices."
    ),
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS — driven by the ADMZ_ALLOWED_ORIGINS env var (comma-separated list).
# Defaults to the documented localhost port (4242). The 8000 entries that
# used to be here as a "legacy" fallback have been removed since the CLI
# now defaults to 4242 too; operators on a non-default port should set
# ADMZ_ALLOWED_ORIGINS to match. Wildcard "*" is still supported but
# explicitly opt-in — never the default. Setting allow_credentials=True
# with "*" is rejected by browsers per the CORS spec anyway.
_default_origins = "http://localhost:4242,http://127.0.0.1:4242"
_origins_raw = os.getenv("ADMZ_ALLOWED_ORIGINS", _default_origins)
_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
_allow_credentials = "*" not in _origins  # browser rejects wildcard + creds

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware — runs after CORS (FastAPI middleware order is
# reverse of add_middleware calls). Resolves a Principal for every
# non-exempt request and stashes it on request.state.principal. With
# ADMZ_AUTH_BACKEND=none (default), everything passes through as the
# synthetic "anonymous" principal — preserving the pre-Phase-4 behavior
# of zero-config local installs and the existing test suite.
app.middleware("http")(auth_middleware)

template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"
template_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)
class _NoCacheStatic(StaticFiles):
    """Serve static assets with ``Cache-Control: no-cache`` so browsers always
    revalidate (cheap 304 via ETag when unchanged) instead of silently serving
    a stale ``chat.js``/CSS from heuristic cache after a deploy."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


if static_dir.exists():
    app.mount("/static", _NoCacheStatic(directory=str(static_dir)), name="static")


# Routers — the JSON API surface
app.include_router(devices.router, prefix="/api", tags=["devices"])
app.include_router(catalog.router, prefix="/api", tags=["catalog"])
app.include_router(plans.router, prefix="/api", tags=["plans"])
app.include_router(snapshot.router, prefix="/api", tags=["snapshot"])
app.include_router(discovery.router, prefix="/api", tags=["discovery"])
app.include_router(schedules.router, prefix="/api", tags=["schedules"])
app.include_router(tasks_route.router, prefix="/api", tags=["tasks"])
app.include_router(api_keys_route.router, prefix="/api", tags=["api-keys"])
app.include_router(audit_route.router, prefix="/api", tags=["audit"])
app.include_router(drift_route.router, prefix="/api", tags=["drift"])
app.include_router(events_route.router, tags=["events"])
app.include_router(detections_route.router, tags=["detections"])
app.include_router(watched_events_route.router, tags=["watched-events"])
# Health routes already include /api in their paths.
app.include_router(health_route.router, tags=["health"])

# Capture, confirm, chatbot, and web UI — no /api prefix because they are user-facing
app.include_router(auth_web_route.router, tags=["auth"])
app.include_router(capture.router, tags=["capture"])
app.include_router(rule_capture_route.router, tags=["capture"])
app.include_router(confirm.router, tags=["confirm"])
app.include_router(chat_route.router, tags=["chat"])
app.include_router(voice_route.router, tags=["voice"])
app.include_router(survey_route.router, tags=["survey"])
# ADR-0046: demos — both /api/demos and the /demos pages live in one router.
app.include_router(demos_route.router, tags=["demos"])
# GitHub App "Connect GitHub" flow — paths already include /api/github.
app.include_router(github_app_route.router, tags=["github"])
app.include_router(web.router, tags=["web"])

# ADR-0039/0040: platform-module routers (e.g. ACS Pro's /api/acs/* + /acs).
# Discovery is a cheap, ordered import; each module's routers() always returns
# its routes (the connect/config endpoints must exist to enable the module),
# while the module self-gates its *visible* surface (nav/tools/prompt).
from admz.modules.registry import ModuleRegistry as _ModuleRegistry  # noqa: E402

for _mod_router, _mod_prefix in _ModuleRegistry().discover().routers_all():
    app.include_router(_mod_router, prefix=_mod_prefix, tags=["modules"])


@app.get("/api/whoami", tags=["auth"])
async def whoami(request: Request):
    """Return the authenticated principal for the current request.

    Useful for the web UI's "Signed in as" indicator and for agents
    wanting to verify their API key is recognized.
    """
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    return {
        "name": principal.name,
        "display_name": principal.display_name,
        "domain": principal.domain,
        "groups": list(principal.groups),
        "source": principal.source,
        "is_anonymous": principal.is_anonymous,
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe. Returns 200 if the process is up; doesn't check deps."""
    return {"status": "healthy", "service": "admz", "version": __version__}


@app.get("/api/health", tags=["health"])
async def api_health_check():
    """Readiness probe. Actively exercises the registry connection."""
    if registry is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "admz-api",
                "version": __version__,
                "registry": "not_initialized",
                "error": "Registry has not been initialized (lifespan not run)",
                "advanced_capabilities": _advanced_capability_ids(),
            },
        )
    try:
        # Actively exercise the registry: list_devices is the cheapest write-free
        # operation that touches the backend.
        registry.list_devices()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "admz-api",
                "version": __version__,
                "registry": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "advanced_capabilities": _advanced_capability_ids(),
            },
        )
    return {
        "status": "healthy",
        "service": "admz-api",
        "version": __version__,
        "registry": "connected",
        # GH #132: ids of the active advanced capabilities, so a curl or a
        # support bundle answers "what mode was this running in?" without auth
        # games. Ids only — never a value.
        "advanced_capabilities": _advanced_capability_ids(),
    }
