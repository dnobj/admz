"""Tests for the route-inventory helper itself.

The helper exists because two security assertions were passing against an empty
set (#223). A helper whose *own* failure mode is silence would just relocate the
defect, so the anti-vacuity guards are tested here directly.
"""

import pytest
from fastapi import APIRouter, FastAPI

from tests.route_inventory import assert_mounted, assert_not_mounted, mounted_paths


def _app():
    app = FastAPI()

    @app.get("/health")
    def health():  # pragma: no cover - never called
        ...

    devices = APIRouter()

    @devices.get("/devices")
    def listing():  # pragma: no cover - never called
        ...

    nested = APIRouter()

    @nested.get("/drift")
    def drift():  # pragma: no cover - never called
        ...

    devices.include_router(nested, prefix="/snapshot")
    app.include_router(devices, prefix="/api")
    return app


class _BlindApp:
    """Stands in for the old broken enumerator: a route table we cannot read."""

    routes: list = []


def test_resolves_prefixes_through_include_router():
    paths = mounted_paths(_app())
    assert "/api/devices" in paths
    assert "/health" in paths


def test_resolves_nested_include_router_prefixes():
    assert "/api/snapshot/drift" in mounted_paths(_app())


def test_real_app_table_is_visible():
    """The canary must be reachable on the actual ADMZ app, on whatever
    FastAPI the current environment resolved."""
    from admz.api.main import app
    paths = mounted_paths(app)
    assert len(paths) > 50, f"only found {len(paths)} routes - enumerator is blind"
    assert "/api/devices" in paths


def test_absent_path_passes():
    assert_not_mounted(_app(), "/api/devices/{device_id}/credentials")


def test_present_path_is_reported_as_mounted():
    assert_mounted(_app(), "/api/devices")


def test_negative_assertion_refuses_a_blind_route_table():
    """The load-bearing guard: absence must not be inferable from blindness."""
    with pytest.raises(AssertionError):
        assert_not_mounted(_BlindApp(), "/api/devices/{device_id}/credentials")


def test_positive_assertion_refuses_a_blind_route_table():
    with pytest.raises(AssertionError):
        assert_mounted(_BlindApp(), "/api/devices")


def test_negative_assertion_refuses_a_table_missing_included_routes():
    """A table with only bare @app.get routes is still blind to include_router,
    which is exactly the FastAPI >= 0.130 failure. It must not satisfy a
    negative assertion."""
    bare = FastAPI()

    @bare.get("/health")
    def health():  # pragma: no cover - never called
        ...

    with pytest.raises(AssertionError):
        assert_not_mounted(bare, "/api/devices/{device_id}/credentials")


def test_mounted_path_actually_catches_a_present_route():
    """Sanity: if the credential endpoint DID exist, the assertion must fail."""
    app = _app()
    leak = APIRouter()

    @leak.get("/devices/{device_id}/credentials")
    def creds(device_id: str):  # pragma: no cover - never called
        ...

    app.include_router(leak, prefix="/api")
    with pytest.raises(AssertionError):
        assert_not_mounted(app, "/api/devices/{device_id}/credentials")
