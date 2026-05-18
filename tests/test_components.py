"""Tests for the shared component-builder (Phase 3B)."""

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.components import Components, build_components


@pytest.fixture
def registry(tmp_path):
    return SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )


class TestBuildComponents:
    """build_components(registry) returns a coherent stack of orchestration
    objects with the same registry/catalog/executors shared across them."""

    def test_returns_components_bundle(self, registry, tmp_path):
        comp = build_components(
            registry,
            config_repo_path=str(tmp_path / "config-repo"),
            schedule_path=str(tmp_path / "schedules.json"),
        )
        assert isinstance(comp, Components)

    def test_registry_is_shared(self, registry, tmp_path):
        comp = build_components(
            registry,
            config_repo_path=str(tmp_path / "config-repo"),
            schedule_path=str(tmp_path / "schedules.json"),
        )
        # PlanEngine, SnapshotEngine, RestoreBuilder all hold the same
        # registry reference
        assert comp.registry is registry
        assert comp.plan_engine.registry is registry
        assert comp.snapshot_engine.registry is registry
        assert comp.restore_builder.registry is registry

    def test_catalog_is_shared(self, registry, tmp_path):
        comp = build_components(
            registry,
            config_repo_path=str(tmp_path / "config-repo"),
            schedule_path=str(tmp_path / "schedules.json"),
        )
        # CatalogLoader is built once and threaded through
        assert comp.plan_engine.catalog is comp.catalog
        assert comp.snapshot_engine.catalog is comp.catalog
        assert comp.restore_builder.catalog is comp.catalog

    def test_executors_are_shared(self, registry, tmp_path):
        comp = build_components(
            registry,
            config_repo_path=str(tmp_path / "config-repo"),
            schedule_path=str(tmp_path / "schedules.json"),
        )
        assert comp.plan_engine.executors is comp.executors
        assert comp.snapshot_engine.executors is comp.executors

    def test_git_repo_is_shared_across_snapshot_stack(self, registry, tmp_path):
        comp = build_components(
            registry,
            config_repo_path=str(tmp_path / "config-repo"),
            schedule_path=str(tmp_path / "schedules.json"),
        )
        # All three components expose the underlying repo as `.git`
        # (legacy attribute name); they all reference the same instance.
        assert comp.snapshot_engine.git is comp.git_repo
        assert comp.restore_builder.git is comp.git_repo
        assert comp.drift_detector.git is comp.git_repo

    def test_paths_override_env_defaults(self, registry, tmp_path, monkeypatch):
        # Explicit args win over env vars
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", "/should-not-be-used")
        custom_repo = str(tmp_path / "custom-repo")
        comp = build_components(
            registry,
            config_repo_path=custom_repo,
            schedule_path=str(tmp_path / "schedules.json"),
        )
        assert comp.git_repo.repo_path == custom_repo or str(
            comp.git_repo.repo_path
        ) == custom_repo


class TestAppContextDelegatesToBuilder:
    """AppContext is a thin wrapper around Components — it must preserve
    the legacy attribute surface (ctx.registry, ctx.catalog, etc.)."""

    def test_legacy_attributes_present(self, registry, tmp_path, monkeypatch):
        # Redirect ALL the file paths AppContext touches into tmp_path
        admz_dir = tmp_path / ".admz"
        admz_dir.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))

        from admz.api.context import AppContext
        ctx = AppContext(registry)
        # Every attribute that route code reads must still work
        assert ctx.registry is registry
        assert ctx.catalog is not None
        assert ctx.resolver is not None
        assert ctx.executors is not None
        assert ctx.plan_engine is not None
        assert ctx.git_repo is not None
        assert ctx.snapshot_engine is not None
        assert ctx.restore_builder is not None
        assert ctx.drift_detector is not None
        assert ctx.scheduler is not None
