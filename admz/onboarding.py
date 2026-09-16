"""Post-add credential onboarding — get a newly registered device to a
working credential without a password ever entering LLM context or a
caller's response.

Resolution order (first hit wins):

1. **Stored credentials verify** — the device already has a working
   ``default`` account: nothing to do.
2. **Factory-defaulted** (unauthenticated ``systemready`` says
   ``needsetup=yes``): provision **two** accounts via
   :func:`admz.provisioning.provision_factory_default` — ``root`` from the
   fleet root password, then ADMZ's own ``admz`` account — and store
   only ``admz`` (FR-CRED-014, ADR-0068). The fleet ``default_password`` is an
   entry credential and is still never written to a device (FR-CRED-007).
3. **The fleet root password, or an entry credential, authenticates** — the
   fleet root password is asked first (ADR-0068, as amended 2026-09-16): ADMZ
   uses that one-time access to create its own ``admz`` account and stores
   *that*. The credential it came in on is never stored for the device.
4. **Neither**: the caller must ask the operator — chat/MCP callers create a
   credential-capture session (the chat console renders it as an inline
   secure-form widget); the web form links to the capture page.

Every outcome dict carries ``status`` plus caller-safe metadata only —
NEVER a password. Shared by the MCP ``register_device``/``onboard_device``
tools and the REST device-create/onboard routes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from admz.fleet_settings import fleet_settings
from admz.provisioning import OWN_ACCOUNT_USERNAME

logger = logging.getLogger(__name__)

# Kill switch for environments where the onboarding probes must not touch
# the network (the unit-test suite sets it; the probes would otherwise hit
# whatever LAN the test box sits on). Callers still get a well-formed
# credentials_needed outcome.
#
# The switch is declared as the ``test.no_onboarding_probes`` advanced
# capability (GH #132) and read through the registry, which is the only place
# ADMZ parses truthiness. The constant stays as documentation of the env var's
# name — it is what the registry declares and what tests/conftest.py sets.
_DISABLE_ENV = "ADMZ_DISABLE_ONBOARDING_PROBES"
_DISABLE_CAPABILITY = "test.no_onboarding_probes"

# ``RECOVERY_ACCOUNT_ID`` / ``_keep_recovery_account`` are RETIRED (ADR-0068).
#
# In-place adoption used to stash the pre-adoption credential under a per-device
# ``recovery`` account, because `store_provisioned_creds` replaces `default` and
# for an ADMZ-generated password that stash was the only surviving copy. Under
# ADR-0068 a root credential is never stored per device, so the stash is exactly
# what the invariant forbids.
#
# The resolution removes the thing being preserved rather than the preservation:
# where ADMZ generated the password itself, root is ROTATED to the fleet
# root password, so the old secret is *invalidated, not lost* and there is
# nothing left to keep. Where a human supplied it, root is left completely alone
# — it is theirs, it exists outside ADMZ, and that is the case ADR-0061's
# "never rotate the account you came in on" was actually protecting.


# Statuses (stable API for callers/tests):
ALREADY_CREDENTIALED = "already_credentialed"
PROVISIONED = "provisioned"
PROVISION_FAILED = "provision_failed"
#: RETIRED as an outcome by ADR-0068 — nothing returns this any more.
#:
#: It meant "the admz write failed, so ADMZ stored the entry credential
#: instead". The entry pair's username defaults to ``root``
#: (``entry_credentials.py``), so storing it is precisely the per-device root
#: credential ADR-0068 forbids — the owner's *"not as a fallback"*. The
#: constants stay defined so nothing importing them breaks; the status is no
#: longer produced. :data:`OWN_ACCOUNT_FAILED` is what that case returns now,
#: and it stores nothing.
ENTRY_CREDENTIALS_SAVED = "fleet_credentials_saved"
FLEET_CREDENTIALS_SAVED = ENTRY_CREDENTIALS_SAVED
#: ADR-0068 decision 4: a credential worked, ADMZ's own account write did not,
#: and **nothing was stored**. The device reads ``no_credentials`` — amber, in
#: the attention bucket, not demo-ready — which is the honest projection of what
#: happened. Recovery is the fleet root password.
#:
#: Named ``OWN_ACCOUNT_FAILED`` to pair with :data:`OWN_ACCOUNT_CREATED`, and
#: deliberately **not** given an ``ADMZ_``-prefixed spelling: the capability
#: drift scanner reads any upper-case ``ADMZ_`` token anywhere in ``admz/`` as
#: an **environment variable** and demands it be classified in
#: ``admz/capabilities.py``
#: (``tests/test_advanced_capabilities.py::TestDriftGuard``). Classifying it
#: would have been the wrong fix — this is a status string, not an env var — so
#: the name stops impersonating one instead. Note the scanner is a plain token
#: scan, so even writing the rejected spelling out in a comment trips it; that
#: is why this says what the shape was rather than giving the example.
OWN_ACCOUNT_FAILED = "admz_account_failed"
#: ADR-0068: ``fleet_root_password`` is unset, so provisioning refused and wrote
#: NOTHING. The alternatives were storing root (forbidden) or generating and
#: discarding it (a device nobody can log into). Same naming rule as above.
NO_ROOT_PASSWORD_CONFIGURED = "root_password_not_configured"

# --- why CREDENTIALS_NEEDED happened (FR-CRED-014, ADR-0068) ----------------
#
# `CREDENTIALS_NEEDED` is returned for four unrelated reasons, and only ONE of
# them means "ask the operator for the device's root password": the entry list
# was tried and the device refused all of it. Offering a root-adopt form for a
# device that is not answering, or that was never probed, is a promise ADMZ
# cannot keep — the submit would fail at the TCP preflight after the operator
# had already typed a password.
#
# A machine-readable field, beside the prose `reason`, because `reason` is
# operator-facing copy and WILL be reworded. Matching on it would break
# silently, which is how a caller ends up minting the wrong kind of session.
# One producer (this module), three consumers (the REST device route, the MCP
# onboard handler, and the approval executor).
#: Every entry credential was put to the device and refused. The ONLY code that
#: may open a root-adopt prompt.
REASON_ENTRY_EXHAUSTED = "entry_exhausted"
#: The device did not answer — TCP preflight failed, or it stopped answering
#: mid-pass. Nothing to prompt for yet.
REASON_UNREACHABLE = "unreachable"
#: No credential was put to the device at all: probes disabled, or no
#: executor/catalog. ADMZ does not know what the device would accept.
REASON_NOT_PROBED = "not_probed"
#: The device is not in the registry, or the registry could not be read.
REASON_LOOKUP_FAILED = "lookup_failed"
#: Nothing to try: the entry list is empty, or the prompt-always posture holds.
#: Distinct from `entry_exhausted` — the device refused nothing because it was
#: asked nothing, so a prompt is the right answer but not because of a refusal.
REASON_NO_ENTRY_CREDENTIALS = "no_entry_credentials"
#: The good path: ADMZ created and stored its own per-device account.
OWN_ACCOUNT_CREATED = "admz_account_created"
CREDENTIALS_NEEDED = "credentials_needed"
#: ADR-0059. The device is factory-defaulted, so onboarding is about to create
#: a root admin account on it — and nobody has approved that yet. The dict also
#: carries the standard blocked envelope (``confirm_token``, ``confirm_url``,
#: …), so a caller can surface the approval link without knowing anything about
#: this module. Fail-closed: a caller that ignores the status sees "not
#: provisioned", which is safe.
APPROVAL_REQUIRED = "approval_required"

#: The actions whose approval covers provisioning here. Named explicitly rather
#: than asking "is anything approved?" — approval for X is not approval for Y,
#: which is the finding that came out of slice 1's review.
_APPROVAL_ACTIONS = ("start_demo_survey", "register_discovered_device",
                     "provision_device_credentials")


def _with_survey(result: Dict[str, Any]) -> Dict[str, Any]:
    """Queue a capability survey on a SUCCESS exit (FR-KNW-012: survey on
    add). Applied only to exits where ADMZ has working credentials — never to
    gated/failed exits, and never as a side effect of a gate firing. For
    ``already_credentialed`` (which fires on every re-onboard of a healthy
    device) the queue is first-sight only: a device with capability rows has
    been surveyed or audited already."""
    status = result.get("status")
    device_id = result.get("device_id") or ""
    if not device_id:
        return result
    from admz.device_capabilities import capability_store, enqueue_capability_survey

    # ENTRY_CREDENTIALS_SAVED is deliberately absent (ADR-0068): it is no longer
    # a success, and no longer produced at all.
    if status in (PROVISIONED, OWN_ACCOUNT_CREATED):
        enqueue_capability_survey(
            device_id, reason=f"onboarded ({status})", approved_by="system:onboarding",
        )
    elif status == ALREADY_CREDENTIALED:
        try:
            first_sight = not capability_store.list(device_id)
        except Exception:  # noqa: BLE001
            first_sight = False
        if first_sight:
            enqueue_capability_survey(
                device_id, reason="first sight with working credentials",
                approved_by="system:onboarding",
            )
    return result


async def onboard_device_credentials(
    *,
    device_id: str,
    registry: Any,
    catalog: Any,
    executors: Any,
    timeout_seconds: float = 10.0,
    adopt: bool = False,
) -> Dict[str, Any]:
    """Resolve initial credentials for ``device_id``. Never raises for
    device-side problems; returns a ``status`` dict (see module docstring).
    Passwords are read from fleet settings / written to the registry only —
    they never appear in the returned dict."""
    from admz.fleet.health import (
        _confirm_credentials,
        _persist_probe_marker,
        _tcp_probe,
    )
    from admz.fleet.systemready import read_systemready
    # `store_provisioned_creds` is deliberately NOT imported: the only call site
    # in this module was the retired entry-credential fallback (ADR-0068). The
    # only thing that stores a credential here now is
    # `adopt_with_admz_account`, and what it stores is always `admz`.
    from admz.provisioning import provision_factory_default

    # NOTE (GH #132): this used to be a bare ``if os.getenv(...)``, so ANY
    # non-empty value enabled the suppressor — ``=0`` meant "probes off". The
    # registry's shared parse accepts {1,true,yes,on} only, so ``=0`` now means
    # what it reads like. conftest.py sets "1", so the suite is unaffected.
    from admz import capabilities

    if capabilities.is_active(_DISABLE_CAPABILITY):
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason_code": REASON_NOT_PROBED,
                "reason": "onboarding probes disabled in this environment"}

    try:
        device_info = registry.get_device_info(device_id)
    except Exception as exc:  # noqa: BLE001 - unknown device
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason_code": REASON_LOOKUP_FAILED,
                "reason": f"device lookup failed: {exc}"}

    executor = (executors or {}).get("vapix")
    if executor is None or catalog is None:
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason_code": REASON_NOT_PROBED,
                "reason": "vapix executor/catalog unavailable"}

    probe_info = {**device_info, "device_id": device_id}

    # Fast preflight: don't spend executor timeouts on a device that isn't
    # even accepting TCP (typo'd host, powered off, wrong subnet). Capture
    # remains available — storing credentials doesn't need the device up.
    host = device_info.get("host") or device_info.get("ip_address") or ""
    if host:
        up = await _tcp_probe(host, 80, 1.5)
        if up is None:
            up = await _tcp_probe(host, 443, 1.5)
        if up is None:
            return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                    "reason_code": REASON_UNREACHABLE,
                    "reason": f"device at {host} is not reachable"}

    # ---- 1. Stored credentials already work? -----------------------------
    stored: Optional[Dict[str, Any]] = None
    # Did the device REFUSE the stored credential just now? The entry loop
    # below must not spend two more failed authentications on a pair it has
    # already answered (#475, ADR-0065). `ok` cannot carry this: the loop
    # rebinds it on its first iteration.
    #
    # A refusal only. `None` means the device did not answer, which says
    # nothing about the credential — skipping on that would drop a pair that
    # might work.
    stored_rejected = False
    try:
        stored = registry.get_credentials(device_id)
    except Exception:  # noqa: BLE001 - no account yet
        stored = None
    if stored and stored.get("password"):
        ok, _facts, learned = await _confirm_credentials(
            catalog=catalog, executor=executor, device_info=probe_info,
            device_id=device_id, credentials=stored,
            timeout_seconds=timeout_seconds, strict=True,
        )
        stored_rejected = ok is False
        if ok is True:
            if learned:
                _persist_probe_marker(registry, device_id, device_info, learned)
            if not adopt or stored.get("username") == OWN_ACCOUNT_USERNAME:
                return _with_survey(
                    {"status": ALREADY_CREDENTIALED, "device_id": device_id})

            # ---- 1b. Adopt in place (ADR-0061, #411) -----------------------
            #
            # The stored credential works and is not ADMZ's own account, and the
            # caller asked for adoption. Use it exactly as step 3 uses an entry
            # credential: create `admz`, gated at the same decision point with
            # the same approval. This is how a device registered before
            # ADR-0061 gets its own account WITHOUT being removed and re-added
            # -- which matters because some stored passwords are ADMZ-generated
            # and exist nowhere else; a wipe would lose them.
            #
            # Explicit opt-in, never a side effect: every other caller of this
            # function (register paths, health-triggered re-onboarding) still
            # gets ALREADY_CREDENTIALED here. Creating accounts on live devices
            # because something re-ran onboarding is a decision, not a
            # consequence.
            from admz.approval_context import is_approved_for

            if not is_approved_for(*_APPROVAL_ACTIONS):
                from admz.audit import record_event
                from admz.discovery.gated import gate_scan_write

                env = gate_scan_write(
                    "provision_device_credentials", device_id,
                    {"device_id": device_id, "host": host},
                    reason=(
                        f"Device '{device_id}' at {host} is managed with a stored "
                        f"'{stored.get('username')}' credential. Approving creates "
                        "ADMZ's own 'admz' admin account on it and switches to that."
                        + (" That stored password was generated by ADMZ, so "
                           "'{}' is then reset to the fleet root password — a "
                           "value you know, which is what makes the device "
                           "recoverable by hand.".format(
                               stored.get("username"))
                           if stored.get("generated_by_admz") else
                           " Your existing credential is left exactly as it is.")
                    ),
                )
                record_event(
                    None, "provision.gated", resource=f"device:{device_id}",
                    details={"host": host, "reason": "adopt-existing",
                             "stored_username": stored.get("username")},
                )
                return {**env, "status": APPROVAL_REQUIRED, "device_id": device_id}

            from admz.provisioning import adopt_with_admz_account

            reach = dict(device_info)
            if learned:
                reach.update(learned)
            result = await adopt_with_admz_account(
                catalog, executors, registry,
                device_id=device_id, host=host,
                entry={"username": stored["username"], "password": stored["password"]},
                device_info=reach,
            )
            if result.get("success"):
                # ADR-0068 §8, and the order matters: `admz` is created FIRST,
                # then root is rotated. Rotating first would invalidate the very
                # credential needed to authenticate the add-user call. This way
                # a rotation that fails leaves a device ADMZ can still reach.
                #
                # Only where ADMZ generated the stored password itself: that
                # value exists nowhere else, so rotating it to the operator-known
                # fleet root password strictly improves recoverability. A
                # human-supplied credential is never touched.
                rotated = None
                if stored.get("generated_by_admz"):
                    from admz.provisioning import rotate_root_to_break_glass

                    rotated, rot_error = await rotate_root_to_break_glass(
                        catalog, executors, host=host,
                        entry={"username": stored["username"],
                               "password": stored["password"]},
                        device_info=reach,
                    )
                    if rotated is False:
                        logger.warning(
                            "device %s: adopted onto admz, but resetting '%s' to "
                            "the fleet root password failed: %s — that "
                            "account still holds an ADMZ-generated password no "
                            "human knows", device_id, stored.get("username"),
                            rot_error,
                        )
                return _with_survey(
                    {"status": OWN_ACCOUNT_CREATED, "device_id": device_id,
                     "username": result["username"],
                     "entry_username": stored.get("username"),
                     "adopted_in_place": True,
                     "root_rotated_to_break_glass": rotated})
            # The stored credential still works and is untouched; say why the
            # switch did not happen rather than pretending it did.
            logger.warning("device %s: adopt-in-place could not create the admz "
                           "account: %s", device_id, result.get("error"))
            return _with_survey(
                {"status": ALREADY_CREDENTIALED, "device_id": device_id,
                 "admz_account_error": result.get("error")})
        # Rejected or indeterminate: fall through — a stale stored password
        # is exactly what the fleet-pair try below may repair.

    # ---- 2. Factory-defaulted → provision with a generated password -------
    ready = await read_systemready(
        catalog, executor, probe_info,
        stored or {"username": "", "password": ""},
    )
    if ready and ready.get("needsetup"):
        host = device_info.get("host") or device_info.get("ip_address")

        # ADR-0059: THE GATE. This is the provisioning decision point — the
        # next call creates a root admin account on a device. Everything up to
        # here has been reads (TCP probe, registry lookup, credential confirm,
        # systemready), so raising the widget now costs an unreachable or
        # already-credentialed device nothing; they returned earlier.
        #
        # The gate lives here rather than at the entry points because whether
        # provisioning will happen is not knowable without contacting the
        # device — `read_systemready` above is what decides it. A gate at
        # function entry would fire on every device add, which is the outcome
        # ADR-0059 is explicitly avoiding.
        from admz.approval_context import is_approved_for

        if not is_approved_for(*_APPROVAL_ACTIONS):
            from admz.audit import record_event
            from admz.discovery.gated import gate_scan_write

            env = gate_scan_write(
                "provision_device_credentials", device_id,
                # Device id + host only. NOT the device's advertised metadata:
                # on a factory-defaulted unit that is an unauthenticated claim
                # (#193), and it adds nothing to "may ADMZ create a root
                # account here?".
                {"device_id": device_id, "host": host},
                reason=(
                    f"Device '{device_id}' at {host} is factory-defaulted. "
                    "Approving creates TWO admin accounts on it: 'root', set to "
                    "the fleet root password you configured, and "
                    "then ADMZ's own 'admz' account with a generated password. "
                    "Only the 'admz' password is stored — the root password is "
                    "never kept per device."
                ),
            )
            record_event(
                None, "provision.gated", resource=f"device:{device_id}",
                details={"host": host, "reason": "needsetup"},
            )
            return {**env, "status": APPROVAL_REQUIRED, "device_id": device_id}

        result = await provision_factory_default(
            catalog, executors, registry,
            device_id=device_id, host=host,
        )
        if result.get("success"):
            # Device, host and password SOURCE — never the password (#199
            # item 2, and the same rule #351/#355 reinforced: an audit row is
            # attribution, not a second copy of a secret). `approved_action`
            # names which approval authorised it.
            from admz.approval_context import approved_action, approved_token
            from admz.audit import record_event

            record_event(
                None, "provision.approved", resource=f"device:{device_id}",
                details={
                    "host": host,
                    "username": result.get("username"),
                    "password_source": result.get("password_source"),
                    # ADR-0068: which root password was written, by SOURCE only.
                    "root_username": result.get("root_username"),
                    "root_password_source": result.get("root_password_source"),
                    "under_approval": approved_action(),
                    "confirm_token": approved_token(),
                },
            )
            return _with_survey({
                "status": PROVISIONED, "device_id": device_id,
                "username": result.get("username"),
                "password_source": result.get("password_source"),
                "root_username": result.get("root_username"),
                "root_password_source": result.get("root_password_source"),
            })
        # ADR-0068 gave this branch outcomes a bare PROVISION_FAILED cannot
        # express — an unset fleet root password (nothing written at all) and a
        # root-set-but-admz-failed device (nothing stored). Pass the specific
        # status through so the operator is told which; `operations.py`'s
        # `ok = status == PROVISIONED` keeps reporting all of them as failures.
        return {"status": result.get("status") or PROVISION_FAILED,
                "device_id": device_id,
                "error": result.get("error"),
                "root_set": result.get("root_set"),
                "root_password_source": result.get("root_password_source")}

    # ---- 3. Fleet root password, entry credentials, then ADMZ's own account -
    #
    # ADR-0061 / FR-CRED-011. This step used to try ONE fleet pair and, on
    # success, store that pair as the device's ongoing credential — so a single
    # shared password became the standing key to every device onboarded this
    # way. Now the list gets ADMZ *in*, and ADMZ creates its own account to
    # stay in. The fleet root password is asked first when one is set (ADR-0068,
    # as amended 2026-09-16): it is on every device ADMZ provisioned.
    #
    # The credential ADMZ came in on is never removed or rotated. After a
    # database loss every generated password is gone and it is the way back.
    from admz import entry_credentials as _entry
    from admz.provisioning import adopt_with_admz_account

    # Bounded: attempt_order() returns the fleet root attempt plus at most
    # MAX_ATTEMPTS_PER_PASS entries (ADR-0064 slice C), so this loop costs at
    # most (1 + 3) x two ops (8); with step 1's check of a stale stored
    # credential above it, one pass is at most 10 operations / 20 sends
    # (FR-CRED-013). A pair step 1 saw refused
    # is skipped here rather than asked twice (#475, ADR-0065) — the maximum
    # is unchanged, but no pair is ever put to the device to AUTHENTICATE
    # twice in one pass. Step 2's systemready read still carries `stored`
    # (#479): auth-free by design, but not forced off the way the health
    # sweep forces it.
    candidates = _entry.attempt_order()
    if not candidates:
        reason = ("no entry credentials configured"
                  if not _entry.prompt_always() else
                  "this installation stores no entry credentials by policy")
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason_code": REASON_NO_ENTRY_CREDENTIALS, "reason": reason}

    if not candidates[0].fleet_root:
        reason = "every entry credential was rejected by the device"
    elif len(candidates) == 1:
        reason = "the fleet root password was rejected by the device"
    else:
        reason = ("the fleet root password and every entry credential were "
                  "rejected by the device")
    reason_code = REASON_ENTRY_EXHAUSTED
    for cred in candidates:
        if stored_rejected and (cred.username, cred.password) == (
                (stored or {}).get("username"), (stored or {}).get("password")):
            # Step 1 asked this exact pair and the device refused it. Asking
            # again costs two more failed authentications and cannot answer
            # differently (#475, ADR-0065).
            continue
        pair = {"username": cred.username, "password": cred.password}
        # strict: only an authenticated 2xx proves the pair — saving on a
        # lenient "not rejected" once stored a bad password (P3408, 2026-07-02).
        # A 2xx from the corroborating param.cgi read counts (GH #149): strict
        # rejects *non-auth* answers as proof, and that is real proof.
        ok, facts, learned = await _confirm_credentials(
            catalog=catalog, executor=executor, device_info=probe_info,
            device_id=device_id, credentials=pair,
            timeout_seconds=timeout_seconds, strict=True,
        )
        if ok is not True:
            if ok is None:
                # Unreachable, not rejected. Trying the rest would be N more
                # timeouts against a device that is not answering.
                reason = "device did not answer the credential check"
                # NOT `entry_exhausted`: the device refused nothing, it went
                # quiet. A root-adopt prompt here would fail at the preflight
                # after the operator had already typed their password.
                reason_code = REASON_UNREACHABLE
                break
            continue

        # This credential works. Persist what we learned about REACHING the
        # device before anything else — the health monitor reads it, and a
        # device whose profile is missing reports auth_failed while a working
        # credential sits in the store (observed on the A1210, 2026-08-17).
        if learned:
            _persist_probe_marker(registry, device_id, device_info, learned)
        if facts:
            changed = {k: v for k, v in facts.items()
                       if v and str(device_info.get(k) or "") != str(v)}
            if changed:
                try:
                    registry.update_device_info(device_id, changed)
                except Exception:  # noqa: BLE001 - best effort
                    pass

        # THE GATE, second decision point (ADR-0059 shape, ADR-0061 case).
        # The next call creates a root admin account on a device that is NOT
        # factory-defaulted — it already has an owner, and this adds ADMZ's
        # account beside theirs. Same approval as step 2, not a second one: an
        # operator who approved "onboard this device" approved ADMZ setting up
        # its own access, and prompting again for the same decision is the gate
        # fatigue ADR-0034 warns about. Placed here rather than before the loop
        # because until a credential works there is nothing to gate — an add
        # that falls through to capture must not raise a widget for an account
        # write that never happens.
        from admz.approval_context import is_approved_for

        if not is_approved_for(*_APPROVAL_ACTIONS):
            from admz.audit import record_event
            from admz.discovery.gated import gate_scan_write

            env = gate_scan_write(
                "provision_device_credentials", device_id,
                {"device_id": device_id, "host": host},
                reason=(
                    f"Device '{device_id}' at {host} accepted the fleet root "
                    f"password (as '{cred.username}'). Approving creates ADMZ's "
                    "own 'admz' admin account on it; root keeps that password."
                    if cred.fleet_root else
                    f"Device '{device_id}' at {host} accepted an entry credential "
                    f"({cred.username}). Approving creates ADMZ's own 'admz' admin "
                    "account on it; the entry credential is left in place."
                ),
            )
            record_event(
                None, "provision.gated", resource=f"device:{device_id}",
                details={"host": host, "reason": "adopt",
                         "entry_username": cred.username,
                         "via_fleet_root": cred.fleet_root},
            )
            return {**env, "status": APPROVAL_REQUIRED, "device_id": device_id}

        # Reach the device the way the probe just did. `learned` carries the
        # scheme/auth the successful attempt discovered; without it the account
        # write would guess again and could fail on a device the very same
        # credential just read.
        reach = dict(device_info)
        if learned:
            reach.update(learned)
        result = await adopt_with_admz_account(
            catalog, executors, registry,
            device_id=device_id, host=host, entry=pair, device_info=reach,
        )
        if result.get("success"):
            return _with_survey(
                {"status": OWN_ACCOUNT_CREATED, "device_id": device_id,
                 "username": result["username"],
                 "entry_username": cred.username,
                 "via_fleet_root": cred.fleet_root})

        # Creating the account failed and the entry credential works — and ADMZ
        # STORES NOTHING (ADR-0068 decision 4).
        #
        # This used to store the entry pair "rather than lose the device". That
        # pair's username defaults to `root`, so it was the per-device root
        # credential the invariant now forbids: the operator's entry credential
        # is not ADMZ's to keep. It reverses a written trade — "a managed device
        # on a shared credential beats an unmanaged one" — deliberately.
        #
        # The device therefore reads `no_credentials`: amber, attention bucket,
        # not demo-ready. That is the honest projection, and the way back in is
        # the credential that just worked: the operator's entry credential, or
        # the fleet root password.
        logger.warning(
            "device %s: %s authenticates but creating the admz account "
            "failed: %s — nothing stored (ADR-0068); the device has no usable "
            "stored credential", device_id,
            ("the fleet root password" if cred.fleet_root
             else f"entry credential '{cred.username}'"),
            result.get("error"),
        )
        return {"status": OWN_ACCOUNT_FAILED, "device_id": device_id,
                "entry_username": cred.username,
                "via_fleet_root": cred.fleet_root,
                "admz_account_error": result.get("error")}

    return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
            "reason_code": reason_code, "reason": reason}
