"""Shared ACS Pro call helper used by both the MCP tools and the REST routes.

Resolves an ACS op against the catalog and runs it through the ``acs-pro``
executor, returning a uniform ``{success, data|error, status_code}`` envelope.
``run_acs_op`` reads the saved connection (gated on enabled); ``run_acs_op_direct``
takes an explicit server dict so the Settings "Test connection" button can probe
a server *before* it's saved/enabled.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _envelope(result: Any) -> Dict[str, Any]:
    if result.success:
        return {"success": True, "data": result.parsed_data, "status_code": result.status_code}
    return {
        "success": False,
        "error": "AcsError",
        "message": result.error,
        "status_code": result.status_code,
    }


async def run_acs_op_direct(
    catalog: Any,
    executors: Dict[str, Any],
    op_id: str,
    params: Optional[Dict[str, Any]],
    server: Dict[str, Any],
) -> Dict[str, Any]:
    """Run ``op_id`` against an explicit ``server`` dict (host/verify_tls)."""
    executor = executors.get("acs-pro")
    if executor is None:
        return {"success": False, "error": "NoExecutor", "message": "ACS executor unavailable."}
    op = catalog.get_operation("acs-pro", op_id)
    if not op:
        return {"success": False, "error": "OperationNotFound", "message": f"Unknown ACS op {op_id}"}
    result = await executor.execute(op.to_executor_dict(), server, {}, params or {})
    return _envelope(result)


async def run_acs_op(
    catalog: Any,
    executors: Dict[str, Any],
    op_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run ``op_id`` against the saved/enabled ACS server."""
    from admz.modules.acs_pro.config import acs_config, acs_enabled, base_url

    if not acs_enabled():
        return {
            "success": False,
            "error": "ACSNotConfigured",
            "message": "ACS Pro isn't connected. Enable it in Settings → Modules.",
        }
    cfg = acs_config()
    server = {"device_id": "acs-server", "host": base_url(), "verify_tls": cfg["verify_tls"]}
    return await run_acs_op_direct(catalog, executors, op_id, params, server)
