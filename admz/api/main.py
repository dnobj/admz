"""
FastAPI application for ADMZ - Axis Device Management Zone.

Provides REST API + Web UI for the full ADMZ surface, mirroring the
MCP server: device registry, credential capture, network discovery,
catalog query/execution, multi-step plans, configuration snapshot/
restore/diff/drift, and scheduled snapshots.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admz.api.context import init_context
from admz.api.routes import (
    capture,
    catalog,
    devices,
    discovery,
    plans,
    schedules,
    snapshot,
    web,
)
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

app = FastAPI(
    title="ADMZ - Axis Device Management Zone",
    description=(
        "Device management, credential storage, and configuration-as-code "
        "for Axis network devices."
    ),
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

# Capture and web UI — no /api prefix because they are user-facing
app.include_router(capture.router, tags=["capture"])
app.include_router(web.router, tags=["web"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "admz", "version": "2.0.0"}


@app.get("/api/health", tags=["health"])
async def api_health_check():
    return {
        "status": "healthy",
        "service": "admz-api",
        "version": "2.0.0",
        "registry": "connected" if registry else "not_initialized",
    }
