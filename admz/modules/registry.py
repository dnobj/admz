"""Module registry — discovers and merges the platform's modules (ADR-0039).

Leaf-light: imports only stdlib + the contract. ``discover()`` performs an
*explicit, ordered* import of each module's ``get_module()`` at call time (no
entry-point magic), so importing this file does not import any module — and
thus no executor, catalog, or FastAPI (enforced by
test_modules_import_isolation).

Built once by ``components.build_components`` and stored on the ``Components``
bundle, so the MCP server (tools), the web layer (nav), and the chatbot host
(prompt sections) all read the same registered set without a global singleton.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from admz.modules.contract import Module, NavSection, ToolSpec


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: List[Module] = []

    def register_module(self, module: Module) -> None:
        if any(m.id == module.id for m in self._modules):
            raise ValueError(f"module '{module.id}' already registered")
        self._modules.append(module)

    def get_modules(self) -> List[Module]:
        return list(self._modules)

    def get_module(self, module_id: str) -> Optional[Module]:
        for m in self._modules:
            if m.id == module_id:
                return m
        return None

    def discover(self) -> "ModuleRegistry":
        """Register every built-in module in a fixed, explicit order.

        Order matters: it determines nav section order and MCP tool order
        (asserted by the list_tools snapshot). Devices is module #1.
        """
        from admz.modules import devices

        self.register_module(devices.get_module())
        # ADR-0040: ACS Pro (module #2). Always registered; its visible surface
        # (nav/tools/prompt) self-gates on the acs_pro enable flag, so it's
        # inert until the operator connects a server.
        from admz.modules import acs_pro

        self.register_module(acs_pro.get_module())
        return self

    # ---- merge helpers (used by MCP / REST / chatbot surfaces) ----------
    def executors_for_all(self) -> Dict[str, Any]:
        """Merge every module's executors into one ``{family: executor}`` map."""
        merged: Dict[str, Any] = {}
        for m in self._modules:
            merged.update(m.executors())
        return merged

    def tool_specs_all(self) -> List[ToolSpec]:
        """Every module's MCP tool specs, in registration order."""
        specs: List[ToolSpec] = []
        for m in self._modules:
            specs.extend(m.mcp_tools())
        return specs

    def routers_all(self) -> List[Any]:
        """Every module's ``(router, prefix)`` pairs, in registration order."""
        out: List[Any] = []
        for m in self._modules:
            out.extend(m.routers())
        return out

    def nav_sections_all(self, ctx: Any = None) -> List[NavSection]:
        """Every module's non-empty nav section, in registration order."""
        out: List[NavSection] = []
        for m in self._modules:
            section = m.nav_section(ctx)
            if section is not None:
                out.append(section)
        return out

    def prompt_sections_all(self, ctx: Any = None) -> List[str]:
        """Every module's non-empty system-prompt fragment."""
        out: List[str] = []
        for m in self._modules:
            frag = m.build_prompt_section(ctx)
            if frag:
                out.append(frag)
        return out

    def task_handlers_all(self) -> Dict[str, Any]:
        """Merge every module's unified-task action handlers (ADR-0037)."""
        merged: Dict[str, Any] = {}
        for m in self._modules:
            merged.update(m.task_handlers())
        return merged

    def self_heals(self, family: str) -> bool:
        """Whether the module owning ``family`` relearns auth on the wire.

        Unknown families default to False (a non-self-healing target), which is
        the safe choice for server targets like ACS Pro.
        """
        for m in self._modules:
            if m.family == family:
                return m.self_heals()
        return False
