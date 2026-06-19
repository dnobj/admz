"""ADMZ platform modules (ADR-0038).

ADMZ is a **platform** (auth/audit, the confirmation gate, the unified task
store, the chatbot host, the web shell) plus one or more **modules**, each
packaging a manageable domain behind the same uniform contract: executors
(keyed by catalog family), MCP tools, REST routers, a nav section, and a
system-prompt section. Module #1 is ``devices`` (Axis edge devices via VAPIX);
module #2 (PR2) is ``acs_pro`` (Axis Camera Station Pro).

This package re-exports only the leaf-light contract types. It deliberately
does NOT import any concrete module or the registry, so ``import
admz.modules.contract`` stays leaf-light (see test_modules_import_isolation).
"""

from admz.modules.contract import (  # noqa: F401
    Module,
    NavItem,
    NavSection,
    ToolSpec,
)
