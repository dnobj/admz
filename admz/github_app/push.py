"""Bridge used by the config-repo push path (``GitRepo._push_auth_env``): hand it
a fresh GitHub App installation token when an App is connected, else nothing.

Kept tiny and defensive — any failure returns ``None`` so the push simply runs
unauthenticated (and, with no valid credentials, fails harmlessly per Part A's
non-blocking guarantee).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def installation_token_for_push() -> Optional[str]:
    """A valid installation access token for the config-repo, or None when no
    GitHub App is connected / the mint fails.

    ``ADMZ_DISABLE_GITHUB_APP_PUSH=1`` short-circuits before any store or network
    access. The connection lives in the machine's secret store, so without this a
    unit test on a developer's connected machine would silently mint a REAL token
    over the network and push differently than on a clean box (same class as
    ``ADMZ_DISABLE_ONBOARDING_PROBES`` — see tests/conftest.py).

    The env var is declared as the ``test.no_github_push`` advanced capability
    (GH #132) and read through the registry, so it shows up in ``/api/health``
    and the startup log like every other non-default power.
    """
    from admz import capabilities

    if capabilities.is_active("test.no_github_push"):
        return None
    from admz.github_app import secrets as s

    if not s.is_connected():
        return None
    from admz.github_app import client as c

    try:
        return c.get_installation_token(
            s.get_app_id(), s.get_private_key(), s.get_installation_id()
        )
    except Exception as exc:  # noqa: BLE001 - best-effort; never break the push
        logger.warning("GitHub App token mint failed (push will be skipped): %s", exc)
        return None
