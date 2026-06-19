"""ADMZ MCP tool registry — per-domain Tool definitions.

Phase 9 introduces this package to chip away at ``admz/mcp/server.py``
(3,500 lines as of Phase 8). Each submodule owns the MCP ``Tool``
declarations for one logical domain. The server imports
``ALL_TOOLS`` from here and concatenates with whatever is still
inlined in ``server.py``.

Migration is intentionally **partial**. The dispatch table (the
``elif name == ...:`` chain in ``server.py``) and the private
method implementations stay on ``ADMZMCPServer`` until a real
second consumer (REST surface, chatbot direct path) needs them.
This package is just the schema declarations — moving them out
shrinks the server file without touching call semantics.

Domains migrated in Phase 9:

  - :mod:`knowledge`   — query_knowledge, check_api_support
  - :mod:`firmware`    — download_firmware, import_firmware,
                         list_cached_firmware
  - :mod:`schedules`   — create/list/update/delete/run_snapshot_schedule
  - :mod:`fleet`       — get_fleet_settings, set_fleet_setting
  - :mod:`provision`   — provision_device

Remaining domains (devices, credentials, catalog, executor, plans,
snapshot, discovery, temp_credentials) stay inlined in
``server.py`` for future commits to migrate. The pattern is
deliberately copy-paste-friendly so the rest fall out cheaply.
"""

from typing import List

from mcp.types import Tool

from admz.mcp.tools import (
    audit,
    firmware,
    fleet,
    knowledge,
    provision,
    recovery,
    schedules,
    tasks,
)

# Order is deliberate: same grouping as the original list_tools()
# emitted, so an LLM that consumed the old ordering sees no
# behavioral change.
MIGRATED_TOOLS: List[Tool] = (
    knowledge.TOOLS
    + schedules.TOOLS
    + fleet.TOOLS
    + provision.TOOLS
    + recovery.TOOLS
    + tasks.TOOLS
    + audit.TOOLS
    + firmware.TOOLS
)

__all__ = ["MIGRATED_TOOLS"]
