"""One-shot migration scripts for ADMZ data-model evolution.

Each migration is a pure function on a :class:`DeviceRegistry`:
* Idempotent — re-running is a no-op (or a partial replay of any
  rows that were missed last time).
* Returns a dict summarizing what it did (counts of rows touched,
  any per-row errors). The CLI wrapper in ``admz/__main__.py
  maintenance migrate`` pretty-prints or JSON-dumps the result.
* Takes ``dry_run=True`` for "tell me what you'd do" mode.

Migrations are NOT versioned; they're additive + idempotent so an
operator can re-run the latest one whenever they need to and any
new rows that haven't been backfilled get caught up.
"""

from admz.migrations.hierarchy_backfill import migrate_hierarchy_backfill

__all__ = [
    "migrate_hierarchy_backfill",
]
