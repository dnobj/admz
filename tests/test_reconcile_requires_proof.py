"""A device is repointed only by a host that can prove it is the device (#193).

`reconcile_device_ips` used to write `{"host": new_ip}` unconditionally, keyed
on a MAC taken from an **unauthenticated mDNS TXT record**
(`mdns_discovery.py:359`, parsed from a raw multicast UDP packet — nothing signs
it). ADMZ's `device_id` *is* the normalized MAC, so an attacker on the segment
needed only to assert a MAC that was already registered. The old code said so in
its own comment: `by_mac.setdefault(mac, ip)  # first responder for a MAC wins`.

The harm is not the stale row. Once a **credentialed** device points at an
attacker-controlled host, every later operation — a health probe, a snapshot, an
operator action — authenticates to them.

**Why a serial match would not have worked.** `serial_number` on a discovered
device comes from the *same forgeable sources* as the MAC: the mDNS TXT record
(`mdns_discovery.py:381`), SSDP (`ssdp_discovery.py:199`) and an unauthenticated
HTTP probe (`http_probe.py:223`). Whoever forges one forges the other in the
same packet.

So the proof is an authenticated request with the device's **own stored
credentials**, in `strict=True` mode where only a genuine authenticated 2xx
counts. That is the one thing an attacker at the new address cannot produce
without already holding the credential.

**Vacuity note.** "the device is not repointed" is trivially green if nothing is
ever repointed — which would silently break the real DHCP-move feature this
module exists for. `TestAGenuineMoveStillWorks` runs first and pins the I8016
scenario the module was written for.

**No packets.** The autouse fixture below makes real discovery impossible from
this module. Learned in #199/#312, where a mutation check removed a guard and
the test then performed the very ARP sweep it was meant to prevent.
"""

from __future__ import annotations

import asyncio
import inspect

import httpx
from types import SimpleNamespace as NS

import pytest

from admz.discovery.reconcile import normalize_mac, reconcile_device_ips


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No test here may emit mDNS, ARP or an HTTP probe.

    A guard test must never rely on the guard it is testing in order to stay
    harmless — mutating the guard away must make a test FAIL, not make it
    transmit.
    """
    def _blocked(*a, **kw):
        raise AssertionError(
            "a test in this module attempted real network discovery. Stub the "
            "path explicitly; never rely on verification to prevent it.")

    for target in (
        "admz.discovery.arp_scanner.ARPScanner._scapy_scan",
        "admz.discovery.arp_scanner.ARPScanner._arp_table_fallback",
        "admz.discovery.orchestrator.discover_devices",
    ):
        monkeypatch.setattr(target, _blocked, raising=False)


class _Disc:
    def __init__(self, mac, ip):
        self.mac_address = mac
        self.ip_address = ip


_NO_CREDS = object()   # distinct from None, which meant "use the default"


class _Registry:
    def __init__(self, devices, creds=_NO_CREDS):
        self._devices = devices
        self.updates: list = []
        self._creds = ({"username": "root", "password": "hunter2"}
                       if creds is _NO_CREDS else creds)

    def list_devices(self):
        return self._devices

    def get_credentials(self, device_id, account_id="default", requester=None):
        if not self._creds:
            from admz.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"no account for {device_id}")
        return dict(self._creds)

    def update_device_info(self, device_id, updates):
        self.updates.append((device_id, updates))
        for d in self._devices:
            if d["device_id"] == device_id:
                d.update(updates)


def _run(reg, discovered, *, verdict=True, principal=None, **kw):
    """Drive the real `reconcile_device_ips` with `_confirm_credentials`
    stubbed to a chosen verdict — True / False / None, the helper's real
    tri-state. Nothing touches a network."""
    async def _confirm(**kwargs):
        return verdict, {}, None

    import admz.fleet.health as H
    orig = H._confirm_credentials
    H._confirm_credentials = _confirm
    try:
        return asyncio.run(reconcile_device_ips(
            reg, discovered, catalog=object(), executors={"vapix": object()},
            principal=principal, **kw))
    finally:
        H._confirm_credentials = orig


MOVED = [_Disc("B8:A4:4F:0C:5B:32", "192.168.1.208")]
REGISTERED = lambda: [{"device_id": "B8A44F0C5B32", "host": "192.168.1.207"}]  # noqa: E731


# ── the anti-vacuity guard ───────────────────────────────────────────────────
class TestAGenuineMoveStillWorks:
    def test_the_i8016_scenario_is_still_corrected(self):
        """FIRST. The real case this module exists for: DHCP moved the I8016
        from .207 to .208. If verification broke it, every refusal test below
        would pass for free while the feature was dead."""
        reg = _Registry(REGISTERED())
        changes = _run(reg, MOVED, verdict=True)
        assert changes == [{"device_id": "B8A44F0C5B32",
                            "old_host": "192.168.1.207",
                            "new_ip": "192.168.1.208", "applied": True}]
        assert reg.updates == [("B8A44F0C5B32", {"host": "192.168.1.208"})]

    def test_a_device_already_at_the_right_ip_is_untouched(self):
        reg = _Registry([{"device_id": "B8A44F0C5B32", "host": "192.168.1.208"}])
        assert _run(reg, MOVED, verdict=True) == []
        assert reg.updates == []


# ── the attack ───────────────────────────────────────────────────────────────
class TestAnUnprovenClaimantIsRefused:
    def test_a_host_that_cannot_authenticate_does_not_move_the_device(self):
        """THE defect. The claimant asserts a registered MAC over mDNS and the
        registry followed it. Now it must authenticate as that device first."""
        reg = _Registry(REGISTERED())
        changes = _run(reg, MOVED, verdict=False)
        assert reg.updates == [], "a credentialed device was repointed unverified"
        assert changes[0]["applied"] is False
        assert "rejected this device's credentials" in changes[0]["reason"]
        assert reg._devices[0]["host"] == "192.168.1.207", "the row must not move"

    def test_an_indeterminate_probe_refuses_rather_than_assumes(self):
        """`_confirm_credentials` is tri-state; `None` means "could not tell".
        Fail closed: a stale registry row is a nuisance, a credentialed device
        pointed at an attacker is a credential disclosure."""
        reg = _Registry(REGISTERED())
        changes = _run(reg, MOVED, verdict=None)
        assert reg.updates == []
        assert changes[0]["applied"] is False
        assert "indeterminate" in changes[0]["reason"]

    def test_a_device_with_no_stored_credentials_is_refused(self):
        """Nothing to prove with. Refusing is still right — an uncredentialed
        device repointed at an attacker becomes the target of the NEXT
        onboarding, which sends the fleet default password (#185)."""
        reg = _Registry(REGISTERED(), creds=None)
        changes = _run(reg, MOVED, verdict=True)
        assert reg.updates == []
        assert "no stored credentials" in changes[0]["reason"]

    def test_no_executor_refuses_rather_than_writing_blind(self):
        """The verification is not optional. Without a way to run it the write
        does not happen — it does not silently fall back to the old behaviour."""
        reg = _Registry(REGISTERED())
        changes = asyncio.run(reconcile_device_ips(reg, MOVED))  # no catalog
        assert reg.updates == []
        assert changes[0]["applied"] is False
        assert "no catalog/executor" in changes[0]["reason"]

    def test_the_probe_is_STRICT_not_lenient(self):
        """The single most load-bearing argument, and mutating it away broke no
        test until this existed.

        `_confirm_credentials` defaults to **lenient**, where "the device
        answers some other way" counts as True — a non-auth error does not
        implicate the password, which is right for health monitoring and
        catastrophic here: a hostile host returning HTTP 500 would "prove" it
        is the device. Only `strict=True` requires a genuine authenticated 2xx.
        """
        seen: dict = {}

        async def _capture(**kwargs):
            seen.update(kwargs)
            return True, {}, None

        import admz.fleet.health as H
        orig = H._confirm_credentials
        H._confirm_credentials = _capture
        try:
            asyncio.run(reconcile_device_ips(
                _Registry(REGISTERED()), MOVED,
                catalog=object(), executors={"vapix": object()}))
        finally:
            H._confirm_credentials = orig

        assert seen.get("strict") is True, (
            "the identity probe runs in LENIENT mode — a host that merely "
            "answers would pass as the device")
        # And it must probe the NEW address, not the one already on record.
        assert seen["device_info"]["host"] == "192.168.1.208"
        assert seen["device_id"] == "B8A44F0C5B32"

    def test_a_probe_that_raises_is_not_a_proof(self):
        reg = _Registry(REGISTERED())

        async def _boom(**kwargs):
            raise RuntimeError("connection reset")

        import admz.fleet.health as H
        orig = H._confirm_credentials
        H._confirm_credentials = _boom
        try:
            changes = asyncio.run(reconcile_device_ips(
                reg, MOVED, catalog=object(), executors={"vapix": object()}))
        finally:
            H._confirm_credentials = orig
        assert reg.updates == []
        assert "identity probe failed" in changes[0]["reason"]


# ── the audit ────────────────────────────────────────────────────────────────
class TestEveryOutcomeIsAudited:
    def _rows(self, monkeypatch):
        seen: list = []
        import admz.audit as A
        monkeypatch.setattr(A, "record_event",
                            lambda *a, **k: seen.append((a, k)))
        return seen

    def test_an_applied_change_names_both_addresses(self, monkeypatch):
        """Before this there were ZERO audit rows on an address change, so a
        credentialed device could move with no record at all."""
        seen = self._rows(monkeypatch)
        _run(_Registry(REGISTERED()), MOVED, verdict=True,
             principal=NS(name="AXIS\\dnich", source="windows-local"))
        actions = [a[1] for a, _ in seen]
        assert "device.address_reconciled" in actions
        details = [k["details"] for _, k in seen if k.get("details")][0]
        assert details["old_host"] == "192.168.1.207"
        assert details["new_host"] == "192.168.1.208"
        assert details["mac"] == "B8A44F0C5B32"

    def test_a_refusal_is_audited_too(self, monkeypatch):
        """A refused rewrite is the interesting one — it is what an attempt
        looks like. Recording only successes would hide exactly that."""
        seen = self._rows(monkeypatch)
        _run(_Registry(REGISTERED()), MOVED, verdict=False)
        actions = [a[1] for a, _ in seen]
        assert "device.address_reconcile_refused" in actions
        kw = [k for _, k in seen][0]
        assert kw["success"] is False and kw["error_message"]
        assert kw["details"]["claimed_ip"] == "192.168.1.208"

    def test_the_principal_is_carried_not_invented(self, monkeypatch):
        """#285: `record_event`'s first argument must be a principal or None."""
        seen = self._rows(monkeypatch)
        p = NS(name="AXIS\\dnich", source="windows-local")
        _run(_Registry(REGISTERED()), MOVED, verdict=True, principal=p)
        assert seen[0][0][0] is p


# ── placement ────────────────────────────────────────────────────────────────
class TestTheCheckIsAtTheChokepoint:
    def test_verification_lives_in_reconcile_not_the_mcp_tool(self):
        """The module's own contract says "the MCP/REST/CLI surfaces run
        discovery and call in here". Today only MCP does — but a check at the
        one entry point is a check the next surface does not inherit, which is
        the shape #299/#313 kept re-learning."""
        src = inspect.getsource(reconcile_device_ips)
        assert "_identity_proven" in src
        from admz.mcp.server import ADMZMCPServer
        tool = inspect.getsource(ADMZMCPServer._reconcile_device_addresses)
        assert "_confirm_credentials" not in tool, (
            "the proof was inlined into the MCP tool; a REST or CLI caller "
            "would not inherit it")

    def test_the_mcp_tool_supplies_what_the_proof_needs(self):
        from admz.mcp.server import ADMZMCPServer
        src = inspect.getsource(ADMZMCPServer._reconcile_device_addresses)
        assert "catalog=" in src and "executors=" in src and "principal=" in src

    def test_the_tool_description_no_longer_calls_itself_read_only(self):
        """`"Read-only except for correcting the stored host"` is where the gap
        became invisible — that clause described the entire attack."""
        import pathlib
        src = pathlib.Path("admz/mcp/server.py").read_text(encoding="utf-8")
        i = src.index('name="reconcile_device_addresses"')
        block = src[i:i + 1200]
        assert "Read-only except for correcting" not in block
        assert "WRITES to the registry" in block


# ── the cross-module invariant this fix rests on ─────────────────────────────
class TestThisDependsOnTheBasicDowngradeRefusal:
    """`reconcile` is only safe while `vapix` refuses Basic over plaintext.

    **Why a reconcile test asserts something about the executor.** The identity
    proof above deliberately sends the device's stored credentials to an address
    chosen by an *unauthenticated mDNS claim*. That is the mechanism, not an
    oversight — it is safe because HTTP Digest never puts the password on the
    wire, and because `executor/vapix.py` refuses to relearn Basic on a
    plaintext channel (GH #171 / PR #292).

    Relax that branch and this file's fix silently becomes a **plaintext
    credential disclosure**: the claimant answers `401 WWW-Authenticate: Basic`,
    the executor retries with `httpx.BasicAuth` — which sends
    `Authorization: Basic base64(user:pass)` preemptively — and the password
    crosses in the clear to whoever won the race.

    `test_executor_self_healing.py` already pins the executor's own behaviour,
    and that is the right home for it. This exists for a different reason: so a
    revert fails **here**, in the file named for the dependent feature, and the
    person relaxing the branch is told *which caller they just broke* rather
    than only that an executor test went red. The invariant was prose-only —
    a PR body and a handoff — until this test existed.

    Deliberately not asserting on source text: this drives the real request
    path through a mock transport and checks what actually reached the wire, so
    a refactor that preserves the behaviour keeps it green.
    """

    def _recording_device(self):
        """A host that 401s with a Basic challenge until Basic arrives —
        exactly what an attacker at the new address would do."""
        seen: list = []

        def handler(request):
            seen.append(request.headers.get("authorization"))
            if (request.headers.get("authorization") or "").startswith("Basic "):
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(401,
                                  headers={"WWW-Authenticate": 'Basic realm="x"'})
        return handler, seen

    async def _probe(self, handler, scheme, port):
        from admz.executor.models import ExecutionRequest
        from admz.executor.vapix import VapixExecutor

        exe = VapixExecutor(timeout=2.0, retries=0,
                            transport=httpx.MockTransport(handler))
        return await exe._send_self_healing(
            request=ExecutionRequest(
                method="POST", path="/axis-cgi/systemready.cgi",
                json_body={"apiVersion": "1.0", "method": "systemReady"}),
            host="192.0.2.1",
            device={"auth": {scheme: "digest", "scheme": scheme},
                    "device_id": "DEV"},
            credentials={"username": "root", "password": "pw"},
            scheme=scheme, port=port, timeout=2.0,
        )

    def test_a_hostile_basic_challenge_over_http_spends_no_password(self):
        """THE invariant. If this fails, do not merge — the identity probe in
        `reconcile.py` is handing the password to an unverified host."""
        handler, seen = self._recording_device()
        resp, learned = asyncio.run(self._probe(handler, "http", 80))

        basic = [a for a in seen if a and a.startswith("Basic ")]
        assert basic == [], (
            "a Basic credential reached the wire over plaintext http. "
            "reconcile.py's identity probe sends credentials to an address "
            "asserted by an unauthenticated mDNS claim and is only safe while "
            "this refusal holds (GH #171/#292, GH #193)")
        assert learned is None, "a plaintext Basic downgrade was persisted"

    def test_and_not_because_nothing_was_sent(self):
        """Anti-vacuity, the same control the executor's own test uses: "no
        Basic on the wire" is trivially true for a test that makes no request.
        Exactly one attempt must have happened, and it must be the Digest one."""
        handler, seen = self._recording_device()
        asyncio.run(self._probe(handler, "http", 80))
        assert len(seen) == 1, f"expected exactly the digest attempt, saw {seen!r}"

    def test_the_rule_does_not_over_fire_on_tls(self):
        """The refusal is narrow on purpose — the same challenge over HTTPS is
        legitimate and must still relearn. A test that passed by refusing
        everything would be pinning the wrong invariant."""
        handler, seen = self._recording_device()
        resp, learned = asyncio.run(self._probe(handler, "https", 443))
        assert [a for a in seen if a and a.startswith("Basic ")], (
            "Basic over TLS was refused too — the guard is over-firing")
        assert resp.status_code == 200


def test_normalize_mac_is_unchanged():
    for raw, expected in (("B8:A4:4F:0C:5B:32", "B8A44F0C5B32"),
                          ("b8-a4-4f-0c-5b-32", "B8A44F0C5B32"),
                          ("", ""), (None, "")):
        assert normalize_mac(raw) == expected
