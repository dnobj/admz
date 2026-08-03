"""Route-table introspection for route-inventory tests.

Why this module exists
----------------------
Tests used to enumerate mounted paths with::

    paths = {r.path for r in app.routes if hasattr(r, "path")}

That idiom is correct only while ``include_router()`` splices its routes
directly into ``app.routes``. FastAPI >= 0.130 instead leaves a single
``_IncludedRouter`` wrapper per ``include_router()`` call, and that wrapper has
**neither** ``.path`` **nor** ``.routes`` -- it holds ``original_router`` plus an
``include_context`` carrying the prefix.

ADMZ mounts essentially everything through ``include_router`` (27 calls in
``admz/api/main.py`` plus the dynamic module loop), so under the new FastAPI the
comprehension above collapses to just the handful of bare ``@app.get`` routes.
Unguarded, that raises ``AttributeError``; with the ``hasattr`` guard it degrades
*silently* to a near-empty set -- which makes any **negative** assertion
("this path is not mounted") pass against nothing at all.

So: flatten properly, and always assert the set is non-empty before asserting an
absence. ``assert_mounted``/``assert_not_mounted`` below exist so no caller has to
remember that.
"""

from __future__ import annotations

from typing import Any, Iterable, Set

_MAX_DEPTH = 20

#: A path that is only reachable via ``include_router()``. Used to prove the
#: flattener actually descended into the wrappers rather than merely finding the
#: few bare ``@app.get`` routes declared directly in ``admz/api/main.py``.
_CANARY = "/api/devices"


def mounted_paths(app: Any) -> Set[str]:
    """Every fully-qualified path mounted on ``app``, prefixes resolved.

    Works on both the pre- and post-0.130 FastAPI router layouts, so it is safe
    while ``requirements.txt`` still admits a range.
    """
    paths: Set[str] = set()

    def walk(routes: Iterable[Any], prefix: str, depth: int) -> None:
        if depth > _MAX_DEPTH:  # pragma: no cover - cycle guard
            raise RuntimeError("route tree deeper than %d; possible cycle" % _MAX_DEPTH)
        for route in routes:
            # FastAPI >= 0.130: an include_router() wrapper. Recurse through the
            # router it wraps, carrying the accumulated prefix.
            inner = getattr(route, "original_router", None)
            if inner is not None:
                ctx = getattr(route, "include_context", None)
                walk(inner.routes, prefix + getattr(ctx, "prefix", ""), depth + 1)
                continue

            path = getattr(route, "path", None)
            if isinstance(path, str):
                paths.add(prefix + path)

            # Starlette Mount / sub-application: children are relative to it.
            sub = getattr(route, "routes", None)
            if sub and not isinstance(route, type):
                walk(sub, prefix + (path or ""), depth + 1)

    walk(app.routes, "", 0)
    return paths


def assert_mounted(app: Any, path: str) -> None:
    """Assert ``path`` is mounted."""
    paths = mounted_paths(app)
    assert paths, "route table introspection returned nothing - see tests/route_inventory.py"
    assert path in paths, f"{path!r} is not mounted"


def assert_not_mounted(app: Any, path: str) -> None:
    """Assert ``path`` is NOT mounted, and that we could actually see the table.

    The emptiness guard is the load-bearing half. Without it this assertion is
    satisfied by a broken enumerator just as happily as by an absent route.
    """
    paths = mounted_paths(app)
    assert paths, "route table introspection returned nothing - see tests/route_inventory.py"
    # Canary. It must be a route reached *through* include_router() -- a bare
    # @app.get route (e.g. /health) would still be found by a flattener that
    # never descended into a single wrapper, so it would not prove anything.
    assert _CANARY in paths, (
        f"route table introspection is not seeing include_router() routes "
        f"({_CANARY} missing) - a negative assertion here would be vacuous"
    )
    assert path not in paths, f"{path!r} is mounted but must not be"
