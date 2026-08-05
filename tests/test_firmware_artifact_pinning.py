"""GH #188 part 2: firmware artifacts are pinned at entry and verified at the read.

#325 gated the *door* into the firmware cache. This records what came through
it, so a file that changes afterwards is caught before its bytes reach a device.

**What this is, and what the tests must never claim it is.** Trust on first use.
It detects **substitution after entry** and nothing else — a malicious file
imported on day one is pinned as authentic. What stops a genuinely malicious
firmware image flashing is the device's own mandatory signature check (VAPIX
`422`), which belongs to the device. `test_pinned_is_not_the_same_state_as_upstream_verified`
exists so the two claims cannot be collapsed by a later tidy-up.

**Placement is the point.** Containment is checked in `_open_and_send`'s caller
~160 lines before `open()`, and the human approval happens before the executor
is entered at all. A digest verified at either moment describes a file that
could differ from the one uploaded, so the check sits at the read and the bytes
verified *are* the bytes sent — the same object.

**The vacuity shape.** "a tampered artifact is refused" is trivially green if
nothing is ever uploaded, and "the digest matches" is trivially green if the
digest is computed from the same re-read as the check. So: every refusal is
paired with an unmodified artifact that *does* upload, the recorded digest is
asserted against an independently-computed one, and
`test_the_digest_is_of_the_bytes_written_not_a_later_reread` plants a different
file after the write to prove the record describes what was written.

No test downloads real firmware — every artifact is bytes written into
`tmp_path`, and `ADMZ_HOME` is redirected.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from admz.firmware import pinning
from admz.firmware.pinning import (
    SOURCE_ADOPTED,
    SOURCE_DOWNLOAD,
    SOURCE_IMPORT,
    STATE_PINNED,
    STATE_UNPINNED,
    STATE_UPSTREAM_VERIFIED,
    ArtifactStore,
    FirmwareIntegrityError,
)

FW = b"\x00fimage-shaped bytes, not real firmware" * 512


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "home" / "admz.db"))
    yield tmp_path


@pytest.fixture
def store(tmp_path):
    return ArtifactStore(db_path=str(tmp_path / "pins.db"))


@pytest.fixture
def artifact(tmp_path):
    p = tmp_path / "P3245-V_11_11_181.bin"
    p.write_bytes(FW)
    return p


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the store -------------------------------------------------------------


def test_record_and_read_back(store, artifact):
    pinning.record_entry(artifact, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)

    rec = ArtifactStore(db_path=store._db_path).get(artifact.name)
    assert rec is not None, "the record did not survive a new store instance"
    assert rec["sha256"] == _sha(FW)
    assert rec["state"] == STATE_PINNED
    assert rec["source"] == SOURCE_IMPORT
    assert rec["size_bytes"] == len(FW)


def test_no_io_in_the_constructor(tmp_path):
    target = tmp_path / "nested" / "late.db"
    s = ArtifactStore(db_path=str(target))
    assert not target.exists(), "the constructor did I/O"
    s.get("anything.bin")
    assert target.exists()


def test_the_default_path_resolves_at_call_time(tmp_path, monkeypatch):
    """#258, on the default path — a store built before ADMZ_DB_PATH changes
    must honour the new value."""
    s = ArtifactStore()
    later = tmp_path / "moved" / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(later))
    s.get("anything.bin")
    assert later.exists()
    assert s._db_path == str(later)


# --- verify at the read ----------------------------------------------------


def test_matching_bytes_verify(store, artifact):
    pinning.record_entry(artifact, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)

    state, digest = pinning.verify_bytes(artifact, FW, store=store)

    assert state == STATE_PINNED
    assert digest == _sha(FW)
    assert store.get(artifact.name)["last_verified"] is not None


def test_substituted_bytes_are_refused(store, artifact):
    """THE #188 part-2 defect: a file swapped after it entered the cache."""
    pinning.record_entry(artifact, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)

    tampered = FW.replace(b"fimage", b"EVILxx", 1)
    assert tampered != FW, "control: the tampered bytes must actually differ"

    with pytest.raises(FirmwareIntegrityError) as e:
        pinning.verify_bytes(artifact, tampered, store=store)

    msg = str(e.value)
    assert "DO NOT flash" in msg
    assert "Re-import or re-download" in msg, "no recovery action offered"
    assert "treat this host as suspect" in msg, (
        "an operator mid-window needs to know this may be compromise")


def test_a_size_change_alone_is_caught(store, artifact):
    """Truncation is substitution too."""
    pinning.record_entry(artifact, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)
    with pytest.raises(FirmwareIntegrityError):
        pinning.verify_bytes(artifact, FW[:-1], store=store)


def test_an_unrecorded_artifact_is_adopted_not_refused(store, artifact):
    """A cache full of pre-#188 files must not brick a working install.

    Adoption is TOFU and is recorded as such — `source='adopted'` exists so
    nothing can later mistake "we wrote down what was already there" for
    "we verified it".
    """
    state, digest = pinning.verify_bytes(artifact, FW, store=store)

    assert state == STATE_UNPINNED, "an adopted artifact must not read as pinned"
    rec = store.get(artifact.name)
    assert rec["source"] == SOURCE_ADOPTED
    assert rec["sha256"] == digest


def test_adoption_protects_the_next_read(store, artifact):
    """Adoption is only worth doing if it makes the *following* read safe."""
    pinning.verify_bytes(artifact, FW, store=store)          # adopt

    with pytest.raises(FirmwareIntegrityError):
        pinning.verify_bytes(artifact, FW + b"tail", store=store)


def test_re_import_replaces_the_pin(store, artifact):
    """Deliberately re-importing the same filename is a new artifact, and its
    new digest is what later reads must match — not a permanent lock to the
    first bytes ever seen."""
    pinning.record_entry(artifact, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)
    newer = FW + b"v2"
    pinning.record_entry(artifact, _sha(newer), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=store)

    state, _ = pinning.verify_bytes(artifact, newer, store=store)
    assert state == STATE_PINNED


# --- the two states stay distinct ------------------------------------------


def test_pinned_is_not_the_same_state_as_upstream_verified():
    """Collapsing these is the overclaim. `pinned` means "we recorded what we
    received"; `upstream_verified` means "Axis published a digest and it
    matched". Only the second says anything about provenance."""
    assert STATE_PINNED != STATE_UPSTREAM_VERIFIED
    assert STATE_UNPINNED not in (STATE_PINNED, STATE_UPSTREAM_VERIFIED)


def test_upstream_verified_survives_a_round_trip(store, artifact):
    pinning.record_entry(artifact, _sha(FW), state=STATE_UPSTREAM_VERIFIED,
                         source=SOURCE_DOWNLOAD, store=store)
    state, _ = pinning.verify_bytes(artifact, FW, store=store)
    assert state == STATE_UPSTREAM_VERIFIED


# --- hashed as written, not re-read ---------------------------------------


def test_the_digest_is_of_the_bytes_written_not_a_later_reread(tmp_path):
    """The property the whole design rests on.

    `record_entry` is handed a digest the *writer* computed. If anything
    re-derived it from the file instead, planting different bytes after the
    write would produce a record that matches the plant — and the substitution
    would be invisible.
    """
    dest = tmp_path / "X.bin"
    dest.write_bytes(FW)
    s = ArtifactStore(db_path=str(tmp_path / "p.db"))

    pinning.record_entry(dest, _sha(FW), state=STATE_PINNED,
                         source=SOURCE_IMPORT, store=s)

    dest.write_bytes(b"substituted")          # the attacker, after the write

    assert s.get("X.bin")["sha256"] == _sha(FW), (
        "the record followed the file instead of the written bytes")
    with pytest.raises(FirmwareIntegrityError):
        pinning.verify_bytes(dest, b"substituted", store=s)


@pytest.mark.asyncio
async def test_the_import_does_not_re_read_the_destination_to_hash_it(
    tmp_path, monkeypatch,
):
    """`hash_file` must not be reachable from the import path.

    Mutation testing found this: swapping the write-time hasher for
    `hash_file(dest)` killed no test, because in a quiet test the file has not
    changed between write and re-read so both produce the same digest. The
    difference only shows under the race the design exists to defeat — so the
    property is asserted structurally instead. `hash_file` exists solely for
    *adoption*, where there are no write-time bytes by definition.
    """
    from admz.firmware import downloader

    def _forbidden(*a, **k):
        raise AssertionError(
            "the import path re-read the destination to hash it; it must hash "
            "the bytes it wrote")

    monkeypatch.setattr(pinning, "hash_file", _forbidden)

    src = tmp_path / "Downloads"
    src.mkdir()
    (src / "P3245-V_11_11_181.bin").write_bytes(FW)

    result = await downloader.import_firmware_files(str(src))
    assert result.imported, f"nothing imported: {result.skipped} {result.errors}"


@pytest.mark.asyncio
async def test_the_executor_reads_the_artifact_exactly_once(tmp_path, monkeypatch):
    """Verifying a re-read instead of the sent bytes reopens the window.

    Also found by mutation testing, and undetectable by content alone for the
    same reason. Counting reads catches it directly: a second read is a second
    moment at which the file could differ.
    """
    import httpx

    from admz.executor.vapix import VapixExecutor
    from admz.paths import firmware_dir

    fw_dir = Path(firmware_dir())
    fw_dir.mkdir(parents=True, exist_ok=True)
    art = fw_dir / "P3245-V_11_11_181.bin"
    art.write_bytes(FW)
    pinning.record_entry(art, _sha(FW), state=STATE_PINNED, source=SOURCE_IMPORT)

    reads = {"n": 0}
    real = Path.read_bytes

    def counting(self, *a, **k):
        if self.name == art.name:
            reads["n"] += 1
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_bytes", counting)

    exe = VapixExecutor(timeout=2.0, retries=0, transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"ok": True})))
    op = {
        "id": "firmwaremanagement.cgi:upgrade",
        "_endpoint": "/axis-cgi/firmwaremanagement.cgi",
        "method": "POST",
        "request": {"content_type": "multipart/form-data",
                    "body": {"fileData": "{firmware_file}"}},
        "response": {"format": "json"},
    }
    await exe.execute(op, {"device_id": "cam-01", "host": "192.0.2.1"},
                      {"username": "root", "password": "pw"},
                      {"firmware_file": str(art)})

    assert reads["n"] == 1, (
        f"the artifact was read {reads['n']} times; the bytes verified must be "
        "the bytes sent, which means reading once")


# --- opportunistic upstream verification ----------------------------------


class _FakeResp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Stands in for httpx. No network: `.sha256` sidecar content is supplied."""

    def __init__(self, sidecar=None, status=200):
        self._sidecar, self._status = sidecar, status
        self.asked = []

    async def get(self, url, **kw):
        self.asked.append(url)
        if self._sidecar is None:
            return _FakeResp(404)
        return _FakeResp(self._status, self._sidecar)


@pytest.mark.asyncio
async def test_a_published_digest_upgrades_the_state(tmp_path):
    """Axis ships `.bin.sha256` for the oldest PACS models only, so this is the
    minority path — but where it exists it is a real vendor claim and must be
    recorded as one."""
    from admz.firmware.downloader import _pin_downloaded

    art = tmp_path / "A1001_1_65.bin"
    art.write_bytes(FW)
    client = _FakeClient(sidecar=f"{_sha(FW)}  A1001_1_65.bin\n")

    await _pin_downloaded(client, "https://x/A1001_1_65.bin", art, _sha(FW))

    assert client.asked == ["https://x/A1001_1_65.bin.sha256"]
    assert pinning.ArtifactStore().get(art.name)["state"] == STATE_UPSTREAM_VERIFIED


@pytest.mark.asyncio
async def test_no_published_digest_is_the_normal_case_and_pins(tmp_path):
    """A missing sidecar is not a failure — it is what MPQT always does."""
    from admz.firmware.downloader import _pin_downloaded

    art = tmp_path / "P3245-V_11_11_181.bin"
    art.write_bytes(FW)

    await _pin_downloaded(_FakeClient(sidecar=None), "https://x/f.bin",
                          art, _sha(FW))

    rec = pinning.ArtifactStore().get(art.name)
    assert rec["state"] == STATE_PINNED, (
        "no vendor digest was checked, so this cannot claim upstream-verified")
    assert rec["source"] == SOURCE_DOWNLOAD


@pytest.mark.asyncio
async def test_a_mismatched_published_digest_is_refused_and_discarded(tmp_path):
    """The bytes served were not the bytes Axis published. That is not a thing
    to pin — it is a thing to refuse and delete."""
    from admz.firmware.downloader import FirmwareDownloadError, _pin_downloaded

    art = tmp_path / "A1001_1_65.bin"
    art.write_bytes(FW)
    client = _FakeClient(sidecar=_sha(b"entirely different bytes"))

    with pytest.raises(FirmwareDownloadError) as e:
        await _pin_downloaded(client, "https://x/A1001_1_65.bin", art, _sha(FW))

    assert "did not match" in str(e.value).lower() or "does not match" in str(e.value).lower()
    assert not art.exists(), "the mismatched artifact was left on disk"
    assert pinning.ArtifactStore().get(art.name) is None, (
        "a mismatched artifact must not be pinned")


@pytest.mark.asyncio
async def test_a_malformed_sidecar_is_ignored_rather_than_trusted(tmp_path):
    """Anything that is not a 64-char hex digest is not a digest. Treating it
    as one would refuse every download the moment Axis served an error page."""
    from admz.firmware.downloader import _pin_downloaded

    art = tmp_path / "A1001_1_65.bin"
    art.write_bytes(FW)

    await _pin_downloaded(_FakeClient(sidecar="<html>404 not found</html>"),
                          "https://x/f.bin", art, _sha(FW))

    assert pinning.ArtifactStore().get(art.name)["state"] == STATE_PINNED


@pytest.mark.asyncio
async def test_import_pins_what_it_copied(tmp_path, monkeypatch):
    """End to end through the real importer, with no network."""
    from admz.firmware.downloader import import_firmware_files

    src = tmp_path / "Downloads"
    src.mkdir()
    (src / "P3245-V_11_11_181.bin").write_bytes(FW)

    result = await import_firmware_files(str(src))
    assert result.imported, f"nothing imported: {result.skipped} {result.errors}"

    from admz.paths import firmware_dir
    dest = Path(firmware_dir()) / "P3245-V_11_11_181.bin"
    assert dest.read_bytes() == FW, "the copy did not reproduce the bytes"

    rec = pinning.ArtifactStore().get(dest.name)
    assert rec is not None, "the import did not pin what it copied"
    assert rec["sha256"] == _sha(FW)
    assert rec["source"] == SOURCE_IMPORT
    assert rec["state"] == STATE_PINNED, (
        "an import cannot be upstream-verified — nothing was checked against Axis")


# --- the executor verifies at the read ------------------------------------


@pytest.mark.asyncio
async def test_the_executor_refuses_a_tampered_artifact(tmp_path, monkeypatch):
    """The refusal must reach the caller as a clean StepResult, not a stack
    trace filed under 'Unexpected error'."""
    import httpx

    from admz.executor.models import ExecutionRequest
    from admz.executor.vapix import VapixExecutor
    from admz.paths import firmware_dir

    fw_dir = Path(firmware_dir())
    fw_dir.mkdir(parents=True, exist_ok=True)
    art = fw_dir / "P3245-V_11_11_181.bin"
    art.write_bytes(FW)
    pinning.record_entry(art, _sha(FW), state=STATE_PINNED, source=SOURCE_IMPORT)

    art.write_bytes(b"substituted bytes")     # swapped after pinning

    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    exe = VapixExecutor(timeout=2.0, retries=0,
                        transport=httpx.MockTransport(handler))

    # Through the real execute() path, so the `except FirmwareIntegrityError`
    # handler is exercised: a deliberate refusal must come back as a clean
    # StepResult carrying the reason, not as "Unexpected error" behind a stack
    # trace — the same treatment PathParamRejected already gets.
    op = {
        "id": "firmwaremanagement.cgi:upgrade",
        "_endpoint": "/axis-cgi/firmwaremanagement.cgi",
        "method": "POST",
        "request": {
            "content_type": "multipart/form-data",
            "body": {"fileData": "{firmware_file}"},
        },
        "response": {"format": "json"},
    }
    result = await exe.execute(
        op, {"device_id": "cam-01", "host": "192.0.2.1"},
        {"username": "root", "password": "pw"},
        {"firmware_file": str(art)},
    )

    assert result.success is False
    assert "DO NOT flash" in (result.error or ""), (
        f"the refusal reason did not reach the caller: {result.error!r}")
    assert sent == [], "a tampered artifact reached the wire"


@pytest.mark.asyncio
async def test_the_bytes_verified_are_the_bytes_sent(tmp_path):
    """No window: the payload handed to httpx is the object that was verified.

    A streaming implementation could verify the file and then send a different
    one; asserting on what the transport actually received is the only way to
    pin that it cannot.
    """
    import httpx

    from admz.executor.models import ExecutionRequest
    from admz.executor.vapix import VapixExecutor
    from admz.paths import firmware_dir

    fw_dir = Path(firmware_dir())
    fw_dir.mkdir(parents=True, exist_ok=True)
    art = fw_dir / "P3245-V_11_11_181.bin"
    art.write_bytes(FW)
    pinning.record_entry(art, _sha(FW), state=STATE_PINNED, source=SOURCE_IMPORT)

    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    exe = VapixExecutor(timeout=2.0, retries=0,
                        transport=httpx.MockTransport(handler))
    req = ExecutionRequest(
        method="POST", path="/axis-cgi/firmwaremanagement.cgi",
        file_path=str(art), file_field_name="fileData",
    )
    resp = await exe._open_and_send("http", "192.0.2.1", 80, req, None, 2.0)

    assert resp.status_code == 200
    assert FW in seen["body"], "the verified bytes are not what reached the wire"
