"""Org/Site membership rules (ADR-0032).

One predicate, deliberately in its own module rather than in either caller.
``routes/web.py`` scopes the device roster and ``api/templating.py`` counts
devices for the nav; both answer "is this device in the active site?", and
until GH #427 they answered it differently:

* the roster kept a device whose ``site_id`` was NULL (falsy short-circuit)
* the nav dropped it (strict ``==``)

Same registry, 5 in the sidebar and 11 on the page, with nothing on screen to
say which was right. A rule stated twice is a rule that will be stated two ways.

The data-layer fix is that ``add_device`` now assigns a site and a startup
backfill heals older rows, so a NULL should not occur. This predicate is what
happens when one does anyway: a device with no site is treated as belonging to
the site you are looking at, because an unassigned device is a gap in ADMZ's own
records rather than a device that lives somewhere else — and hiding it would
make it unmanageable rather than merely miscounted.
"""

from __future__ import annotations

from typing import Optional


def device_is_in_site(device_site_id: Optional[str], active_site_id: Optional[str]) -> bool:
    """Whether a device should be shown/counted under ``active_site_id``.

    * No active site (no hierarchy at all) → everything is in scope.
    * Device has no site → in scope, and see the module docstring for why.
    * Otherwise → exact membership.
    """
    if not active_site_id:
        return True
    if not device_site_id:
        return True
    return device_site_id == active_site_id
