"""Deferred recovery action handlers, registered with the AppContext at startup.

Handlers run a PRE-AUTHORIZED follow-up when the health-monitor sweep fires a
pending action (see ``admz/fleet/pending_actions.py``). Today: ``reprovision``
— when a device comes back factory-defaulted, create its admin account from the
fleet default password. (``reprovision_and_restore`` — auto-restore the baseline
afterward — is a follow-up.) Removal is handled immediately at queue time (it
doesn't need the device back), so it isn't a deferred handler.

SECURITY: these run only for actions the operator approved up front (the queue
route requires an authenticated principal), with no new gate at fire time.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

ACTION_REPROVISION = "reprovision"


def register_recovery_handlers(ctx: Any) -> None:
    """Register the deferred recovery handlers, closing over the AppContext."""
    from admz.fleet.pending_actions import register_pending_handler
    from admz.provisioning import provision_factory_default

    async def _reprovision(action: Dict[str, Any], device_id: str) -> None:
        info = ctx.registry.get_device_info(device_id)
        host = info.get("host") or info.get("ip_address")
        if not host:
            raise ValueError(f"device {device_id} has no host to provision")
        result = await provision_factory_default(
            ctx.catalog, ctx.executors, ctx.registry,
            device_id=device_id, host=host,
            username=(action or {}).get("username", "root"),
        )
        if not result.get("success"):
            raise RuntimeError(result.get("error") or "provision failed")
        logger.info("deferred reprovision succeeded for %s", device_id)

    register_pending_handler(ACTION_REPROVISION, _reprovision)
