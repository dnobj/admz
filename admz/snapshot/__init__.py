"""
Configuration snapshot, restore, drift detection, and scheduling.

The snapshot module backs up device configurations to a git repository,
treating git as the source of truth for configuration state.

Main pieces:

- :class:`admz.snapshot.engine.SnapshotEngine` — reads device via catalog
  operations, normalizes through facet adapters, commits to git.
- :class:`admz.snapshot.restore.RestoreBuilder` — reads YAML from any git
  ref and builds an execution plan.
- :class:`admz.snapshot.drift.DriftDetector` — compares live device state
  against git HEAD.
- :class:`admz.snapshot.scheduler.SnapshotScheduler` — recurring snapshots
  on configurable intervals.
- :class:`admz.snapshot.git_repo.GitRepo` — thin wrapper over a local git
  repository.
- :mod:`admz.snapshot.facets` — pluggable per-facet adapters
  (image, network, time, stream_profiles, users, events).

See :doc:`docs/EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md` for the full design.
"""
