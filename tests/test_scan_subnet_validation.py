"""A scan subnet is validated before it reaches scapy (#199).

`ArpScanner._scapy_scan` does `ARP(pdst=subnet)` with whatever string it was
handed, and that string is **model-supplied free text** on two of the five
paths. The confirmation gate added in #299 makes the scan *deliberate*; it does
nothing about what is in the string. A `/8` is 16,777,214 ARP packets — a
network flood, not a scan.

`ipaddress.ip_network` was already imported one function away, in
`arp_scanner._parse_arp_table` — but only to **filter results**, and it swallows
`ValueError`, so it never validated anything.

**Where the check lives is the point.** It is enforced in
`discovery.orchestrator.discover_devices`, the one function all five callers
funnel through (REST `/discovery/scan`, the demo-inference survey, two MCP
tools, and the CLI). Validating at the five call sites is how the sixth gets
missed — which is exactly what happened to #299's gate, whose entry-point
enforcement this branch found to be bypassable. `TestEveryCallerInheritsIt` is
the test of that claim, and it is the reason for this shape.

**Vacuity note.** "the subnet is rejected" is trivially green if every subnet is
rejected — which would break discovery entirely while looking like a security
win. `TestAValidSubnetStillScans` runs first and pins the accepting cases,
including the auto-detect `None` default that most callers actually use.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import pathlib

import pytest

from admz.validators import MIN_SCAN_PREFIXLEN, validate_scan_subnet


@pytest.fixture(autouse=True)
def _no_packets_ever(monkeypatch):
    """Make a real ARP sweep impossible from this module, unconditionally.

    Learned the hard way: the first version of this file proved the guard by
    calling `discover_devices(subnet="10.0.0.0/8")` and expecting `ValueError`.
    Mutating the guard away did not make that test fail — it made it **run**,
    and a 16.7-million-host ARP sweep started from the test suite and had to be
    killed. `timeout=` is no protection, because `srp` transmits every packet
    before it waits.

    The individual tests stub their own call paths, which is what makes them
    meaningful. This is the backstop for the *next* test someone adds here: a
    guard test must never rely on the guard it is testing in order to stay
    harmless.
    """
    def _blocked(*a, **kw):
        raise AssertionError(
            "a test in this module attempted a real ARP scan. Stub the "
            "discovery path explicitly — never rely on validation to prevent "
            "it, because the mutation check removes exactly that.")

    monkeypatch.setattr("admz.discovery.arp_scanner.ARPScanner._scapy_scan",
                        _blocked, raising=False)
    monkeypatch.setattr("admz.discovery.arp_scanner.ARPScanner._arp_table_fallback",
                        _blocked, raising=False)


# ── the anti-vacuity guard ───────────────────────────────────────────────────
class TestAValidSubnetStillScans:
    def test_none_passes_through_untouched(self):
        """FIRST. `None` means "auto-detect the local /24" and is the default
        for every caller. If this were rejected, discovery would be dead and
        every rejection test below would still pass."""
        assert validate_scan_subnet(None) is None

    @pytest.mark.parametrize("value,expected", [
        ("192.168.1.0/24", "192.168.1.0/24"),
        ("10.20.0.0/16", "10.20.0.0/16"),      # exactly at the limit
        ("172.16.5.0/24", "172.16.5.0/24"),
        ("192.168.1.0/32", "192.168.1.0/32"),  # a single host is fine
    ])
    def test_ordinary_subnets_are_accepted(self, value, expected):
        assert validate_scan_subnet(value) == expected

    def test_a_host_address_is_normalised_not_rejected(self):
        """An operator naming a host on the target network is being helpful,
        not wrong — `strict=False`."""
        assert validate_scan_subnet("192.168.1.42/24") == "192.168.1.0/24"

    def test_surrounding_whitespace_is_tolerated(self):
        assert validate_scan_subnet("  192.168.1.0/24  ") == "192.168.1.0/24"


# ── what must be refused ─────────────────────────────────────────────────────
class TestTooWideIsRefused:
    def test_a_slash_8_is_rejected(self):
        """THE case this exists for: 16.7 million hosts."""
        with pytest.raises(ValueError) as exc:
            validate_scan_subnet("10.0.0.0/8")
        msg = str(exc.value)
        assert "16,777,214" in msg, "the error must say how big the ask was"
        assert f"/{MIN_SCAN_PREFIXLEN}" in msg, "and what the limit is"

    def test_it_rejects_rather_than_clamping(self):
        """Deliberate. Silently scanning a narrower range would report
        "no devices found" for addresses never probed — indistinguishable from
        a clean result, which is the worse failure."""
        with pytest.raises(ValueError):
            validate_scan_subnet("10.0.0.0/12")
        src = inspect.getsource(validate_scan_subnet)
        assert "raise ValueError" in src
        assert "MIN_SCAN_PREFIXLEN" in src

    def test_the_boundary_is_inclusive(self):
        """/16 passes, /15 does not — pinned so a later tweak is deliberate."""
        assert validate_scan_subnet("10.0.0.0/16") == "10.0.0.0/16"
        with pytest.raises(ValueError):
            validate_scan_subnet("10.0.0.0/15")


class TestMalformedIsRefused:
    @pytest.mark.parametrize("bad", [
        "not-cidr", "192.168.1.0/33", "999.1.1.1/24", "192.168.1.0/",
        "", "   ", "192.168.1.0 /24", "; rm -rf /",
    ])
    def test_garbage_is_rejected(self, bad):
        with pytest.raises(ValueError):
            validate_scan_subnet(bad)

    def test_a_non_string_is_rejected(self):
        for bad in (24, ["192.168.1.0/24"], {"subnet": "x"}, object()):
            with pytest.raises(ValueError):
                validate_scan_subnet(bad)

    def test_ipv6_is_rejected_with_the_reason(self):
        """ARP is IPv4-only; there is no v6 equivalent ADMZ implements. Without
        this, `ip_network` accepts it happily and scapy gets nonsense."""
        with pytest.raises(ValueError) as exc:
            validate_scan_subnet("fd00::/64")
        assert "IPv4-only" in str(exc.value)

    def test_the_error_names_the_offending_value(self):
        """An operator retyping a subnet needs to see what was parsed."""
        with pytest.raises(ValueError) as exc:
            validate_scan_subnet("192.168.1.0/99")
        assert "192.168.1.0/99" in str(exc.value)


# ── the placement claim ──────────────────────────────────────────────────────
class TestEveryCallerInheritsIt:
    """The reason the check is at the chokepoint and not at five call sites."""

    def test_the_chokepoint_rejects_BEFORE_constructing_a_scanner(
            self, monkeypatch):
        """Asserts the *ordering*, and never touches the network.

        An earlier version of this test simply called
        `discover_devices(subnet="10.0.0.0/8")` and expected `ValueError`. With
        the guard mutated away it did not raise — it **ran the 16.7-million-host
        ARP sweep for real**, from the test suite, and had to be killed. That is
        the strongest evidence the guard is load-bearing, and it is also a
        test-design bug: a mutation check must not perform the dangerous act to
        prove the guard prevents it. `timeout=` does not help, because `srp`
        transmits every packet before it waits.

        So the orchestrator is stubbed. If validation ever moves *after*
        construction, `built` flips and this fails — without a packet leaving
        the machine, on any machine, including CI.
        """
        from admz.discovery import discover_devices, orchestrator

        built: list = []

        class _NeverRuns:
            def __init__(self, *a, **kw):
                built.append(kw.get("subnet"))

            async def run(self, *a, **kw):
                raise AssertionError("a scan was started for a rejected subnet")

        monkeypatch.setattr(orchestrator, "DiscoveryOrchestrator", _NeverRuns)
        with pytest.raises(ValueError):
            asyncio.run(discover_devices(subnet="10.0.0.0/8", timeout=0.01))
        assert built == [], (
            "the subnet was rejected only after a scanner had been built — "
            "validation must precede construction, not follow it")

    def test_the_stub_would_have_caught_a_real_scan(self, monkeypatch):
        """Anti-vacuity for the test above: prove the stub is actually wired in
        and would notice, by driving a VALID subnet through the same path."""
        from admz.discovery import discover_devices, orchestrator

        built: list = []

        class _NeverRuns:
            def __init__(self, *a, **kw):
                built.append(kw.get("subnet"))

            async def run(self, *a, **kw):
                return []

        monkeypatch.setattr(orchestrator, "DiscoveryOrchestrator", _NeverRuns)
        asyncio.run(discover_devices(subnet="192.168.1.0/24", timeout=0.01))
        assert built == ["192.168.1.0/24"], (
            "the stub was never constructed, so the assertion above proves "
            "nothing")

    def test_discover_devices_calls_the_validator(self):
        """Structural: if someone removes the call, the runtime test above goes
        red — but this says *why* it went red."""
        from admz.discovery import orchestrator
        src = inspect.getsource(orchestrator.discover_devices)
        assert "validate_scan_subnet(subnet)" in src

    def test_no_caller_bypasses_the_chokepoint(self):
        """Every subnet-passing caller must go through `discover_devices`. A
        direct `ArpScanner(subnet=...)` or `DiscoveryOrchestrator(subnet=...)`
        outside the discovery package would skip validation entirely."""
        offenders = []
        for path in sorted(pathlib.Path("admz").rglob("*.py")):
            if path.parts[:2] == ("admz", "discovery"):
                continue          # the package's own internals are downstream
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(
                    node.func, "attr", None)
                if name not in ("ARPScanner", "ArpScanner",
                                "DiscoveryOrchestrator"):
                    continue
                if any(k.arg == "subnet" for k in node.keywords):
                    offenders.append(f"{path}:{node.lineno} -> {name}(subnet=…)")
        assert not offenders, (
            "these construct a scanner with a subnet directly, bypassing "
            "`discover_devices` and therefore the validation:\n  "
            + "\n  ".join(offenders))


# ── the boundaries translate rather than 500 ─────────────────────────────────
class TestBoundariesReportTheReason:
    def test_the_mcp_tool_returns_the_reason_not_a_traceback(self, monkeypatch):
        """The model has to be able to correct the subnet; a traceback tells it
        nothing actionable and it retries the same value.

        `run_network_discovery` is stubbed for the same reason as the
        chokepoint test above: without it, mutating the limit away turns this
        test into a real 16.7-million-host sweep. A test must not depend on the
        guard it is testing to stay harmless.
        """
        from admz.mcp import server as server_mod
        from admz.mcp.server import ADMZMCPServer

        async def _never(**kwargs):
            raise AssertionError(
                f"a real scan was started for {kwargs.get('subnet')!r}")
        monkeypatch.setattr(server_mod, "run_network_discovery", _never)

        srv = ADMZMCPServer.__new__(ADMZMCPServer)
        out = asyncio.run(srv._discover_network_devices({"subnet": "10.0.0.0/8"}))
        assert out["success"] is False
        assert "16,777,214" in out["error"]

    def test_the_rest_scan_route_translates_to_400(self):
        from admz.api.routes import discovery as route_mod
        src = inspect.getsource(route_mod.scan_network)
        assert "validate_scan_subnet" in src and "status_code=400" in src

    def test_the_survey_route_validates_BEFORE_the_gate(self):
        """Ordering matters: the survey runs in the background, so an invalid
        subnet would otherwise be approved by the operator and fail minutes
        later inside the run, where nobody is looking."""
        from admz.api.routes import demos as route_mod
        src = inspect.getsource(route_mod.start_inference_run)
        assert "validate_scan_subnet" in src and "gate_scan_write" in src
        assert src.index("validate_scan_subnet") < src.index("gate_scan_write"), (
            "the subnet is validated after the approval widget is raised — an "
            "operator would approve a survey that cannot run")
