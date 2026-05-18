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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admz.api.context import init_context
from admz.api.routes import (
    capture,
    catalog,
    confirm,
    devices,
    discovery,
    plans,
    schedules,
    snapshot,
    web,
)
from admz import __version__
from admz.factory import create_device_registry


# Module-level registry alias, for backward compatibility with routes
# that historically imported `registry` from this module.
registry = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize context + start scheduler on startup; clean up on shutdown."""
    global registry
    registry = create_device_registry()
    ctx = init_context(registry)
    await ctx.scheduler.start()
    try:
        yield
    finally:
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
# Defaults to localhost-only on both ports we typically use (4242 dev, 8000
# legacy). Wildcard "*" is still supported but explicitly opt-in — never the
# default. Setting allow_credentials=True with "*" is rejected by browsers
# per the CORS spec anyway.
_default_origins = (
    "http://localhost:4242,http://127.0.0.1:4242,"
    "http://localhost:8000,http://127.0.0.1:8000"
)
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

template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"
template_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(template_dir))
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Routers — the JSON API surface
app.include_router(devices.router, prefix="/api", tags=["devices"])
app.include_router(catalog.router, prefix="/api", tags=["catalog"])
app.include_router(plans.router, prefix="/api", tags=["plans"])
app.include_router(snapshot.router, prefix="/api", tags=["snapshot"])
app.include_router(discovery.router, prefix="/api", tags=["discovery"])
app.include_router(schedules.router, prefix="/api", tags=["schedules"])

# Capture, confirm, and web UI — no /api prefix because they are user-facing
app.include_router(capture.router, tags=["capture"])
app.include_router(confirm.router, tags=["confirm"])
app.include_router(web.router, tags=["web"])


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
            },
        )
    return {
        "status": "healthy",
        "service": "admz-api",
        "version": __version__,
        "registry": "connected",
    }
