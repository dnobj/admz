"""
FastAPI application for ADMZ - Axis Device Management Zone.

Provides both REST API and Web UI for managing Axis device credentials.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from admz.factory import create_device_registry
from admz.api.routes import devices, web

# Initialize FastAPI app
app = FastAPI(
    title="ADMZ - Axis Device Management Zone",
    description="Secure credential management for Axis devices",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
template_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"

# Create directories if they don't exist
template_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(template_dir))

# Mount static files
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize device registry
# This will be created per-request or via dependency injection
# For now, we'll create a global instance
registry = None


@app.on_event("startup")
async def startup_event():
    """Initialize registry on startup."""
    global registry
    registry = create_device_registry()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    pass


# Include routers
app.include_router(devices.router, prefix="/api", tags=["devices"])
app.include_router(web.router, tags=["web"])


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "admz",
        "version": "1.0.0",
    }


@app.get("/api/health", tags=["health"])
async def api_health_check():
    """API health check endpoint."""
    registry_status = "connected" if registry else "not_initialized"
    return {
        "status": "healthy",
        "service": "admz-api",
        "version": "1.0.0",
        "registry": registry_status,
    }
