"""The module contract (ADR-0039).

A *module* packages one manageable domain (edge devices, ACS Pro, …) behind a
small, uniform surface the platform composes. The platform calls each module's
factories and merges the results:

  * ``executors()``            → ``{family: BaseExecutor}`` for the gate spine
  * ``mcp_tools()``            → ``[ToolSpec]`` (schema + free-function handler)
  * ``routers()``              → ``[(APIRouter, prefix)]``
  * ``nav_section(ctx)``       → a ``NavSection`` for the sidebar (or None)
  * ``build_prompt_section(ctx)`` → a system-prompt fragment (or "")
  * ``task_handlers()``        → unified-task action handlers (ADR-0037), merged
    at startup by ``admz.tasks.handlers.install_module_task_handlers``. A module
    may add an action type; it may not replace a built-in (GH #172).
  * ``self_heals()``           → whether the family relearns auth on the wire

This file imports ONLY stdlib + typing, so the stdio MCP subprocess and the
leaf-light ``operations`` layer can import the contract/registry without
dragging in FastAPI, the catalog package, or any executor (enforced by
test_modules_import_isolation). Concrete types (BaseExecutor, mcp.types.Tool,
APIRouter) are referenced structurally or under TYPE_CHECKING only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

if TYPE_CHECKING:  # pragma: no cover — hints only, never imported at runtime
    from admz.executor.base import BaseExecutor


# A tool handler is a free async function ``(ToolCtx, args) -> result dict``.
# Decoupling the handler from the bound ``server._method`` is what makes the
# MCP handler relocation (P4) clean.
ToolHandler = Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool: its schema + a free-function handler.

    ``tool`` is an ``mcp.types.Tool`` held loosely (typed ``Any``) so importing
    the contract doesn't import the ``mcp`` package; only ``tool.name`` is read
    by the registry/dispatcher.
    """

    tool: Any
    handler: ToolHandler


@dataclass(frozen=True)
class NavItem:
    """One sidebar entry. ``key`` matches the template's ``nav_active`` marker.

    ``children`` holds an optional sub-nav (e.g. the tag list under Devices).
    """

    key: str
    label: str
    href: str
    icon: str = ""
    children: Tuple["NavItem", ...] = ()


@dataclass(frozen=True)
class NavSection:
    """A divider-separated group of nav items.

    ``title`` is an optional header; an empty title renders no header/divider
    (used by the pinned platform "Core" section).
    """

    id: str
    title: str = ""
    items: Tuple[NavItem, ...] = ()


# ---- factory defaults (no-ops) — a module overrides only what it provides ----
def _empty_executors() -> Dict[str, "BaseExecutor"]:
    return {}


def _empty_tools() -> List[ToolSpec]:
    return []


def _empty_routers() -> List[Tuple[Any, str]]:
    return []


def _no_nav(ctx: Any = None) -> Optional[NavSection]:
    return None


def _empty_prompt(ctx: Any = None) -> str:
    return ""


def _empty_task_handlers() -> Dict[str, Any]:
    return {}


def _self_heals_default() -> bool:
    return False


@dataclass(frozen=True)
class Module:
    """A pluggable platform module.

    The factories are callables (not bound results) so the platform controls
    *when* the heavy bits are constructed — importing a module declares its
    contract; calling ``executors()`` is what actually builds the executor.
    """

    id: str
    family: str
    title: str
    catalog_family: str = ""
    executors: Callable[[], Dict[str, "BaseExecutor"]] = _empty_executors
    mcp_tools: Callable[[], List[ToolSpec]] = _empty_tools
    routers: Callable[[], List[Tuple[Any, str]]] = _empty_routers
    nav_section: Callable[[Any], Optional[NavSection]] = _no_nav
    build_prompt_section: Callable[[Any], str] = _empty_prompt
    task_handlers: Callable[[], Dict[str, Any]] = _empty_task_handlers
    self_heals: Callable[[], bool] = _self_heals_default

    def resolved_catalog_family(self) -> str:
        """The catalog family this module resolves ops against."""
        return self.catalog_family or self.family
