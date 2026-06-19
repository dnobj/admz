"""ADR-0039: the gate only persists relearned auth for self-healing families.

Edge devices (VAPIX) relearn scheme/auth on the wire and the gate persists the
corrected profile. A server target (e.g. ACS Pro, PR2) authenticates per
connection and returns ``self_heals() == False`` — the gate must NOT rewrite its
stored auth even if a result carried a ``learned_auth`` payload.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from admz.operations import run_execution_tail


class _Op:
    def to_executor_dict(self):
        return {}


class _Catalog:
    def get_operation(self, family, operation_id):
        return _Op()


class _Registry:
    def __init__(self):
        self.updated = []

    def device_exists(self, device_id):
        return True

    def get_device_info(self, device_id):
        return {"auth": {"scheme": "http"}}

    def get_credentials(self, device_id):
        return {"username": "u", "password": "p"}

    def update_device_info(self, device_id, info):
        self.updated.append((device_id, info))


class _Exec:
    def __init__(self, heals: bool):
        self._heals = heals

    def self_heals(self) -> bool:
        return self._heals

    async def execute(self, *a, **k):
        return SimpleNamespace(
            learned_auth={"scheme": "https", "auth_method": "basic"}
        )


def _run(heals: bool):
    reg = _Registry()
    asyncio.new_event_loop().run_until_complete(
        run_execution_tail(
            device_id="cam",
            operation_id="op",
            family="vapix",
            params={},
            catalog=_Catalog(),
            registry=reg,
            executors={"vapix": _Exec(heals)},
        )
    )
    return reg.updated


def test_self_healing_family_persists_learned_auth():
    updated = _run(True)
    assert updated == [
        ("cam", {"auth": {"scheme": "https", "auth_method": "basic"}})
    ]


def test_non_self_healing_family_skips_persist():
    assert _run(False) == []


def test_base_default_and_vapix_self_heal():
    from admz.executor.vapix import VapixExecutor

    # BaseExecutor.self_heals() defaults True (historical single-family
    # behavior); VAPIX inherits it.
    assert VapixExecutor().self_heals() is True
