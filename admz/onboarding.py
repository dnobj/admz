"""Post-add credential onboarding — get a newly registered device to a
working credential without a password ever entering LLM context or a
caller's response.

Resolution order (first hit wins):

1. **Stored credentials verify** — the device already has a working
   ``default`` account: nothing to do.
2. **Factory-defaulted** (unauthenticated ``systemready`` says
   ``needsetup=yes``): provision the admin account from fleet settings
   (``default_username``/``default_password``, else a generated password)
   via :func:`admz.provisioning.provision_factory_default`.
3. **Fleet credential pair authenticates**: the device was set up elsewhere
   with the fleet-standard credentials — save them as the device's account,
   entirely server-side.
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

# Statuses (stable API for callers/tests):
ALREADY_CREDENTIALED = "already_credentialed"
PROVISIONED = "provisioned"
PROVISION_FAILED = "provision_failed"
#: Kept as the wire value so existing callers/tests are unaffected; the name
#: now means "adopted on the entry credential", which is the fallback path
#: rather than the good one (ADR-0061).
ENTRY_CREDENTIALS_SAVED = "fleet_credentials_saved"
FLEET_CREDENTIALS_SAVED = ENTRY_CREDENTIALS_SAVED
#: The good path: ADMZ created and stored its own per-device account.
ADMZ_ACCOUNT_CREATED = "admz_account_created"
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


async def onboard_device_credentials(
    *,
    device_id: str,
    registry: Any,
    catalog: Any,
    executors: Any,
    timeout_seconds: float = 10.0,
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
    from admz.provisioning import provision_factory_default, store_provisioned_creds

    # NOTE (GH #132): this used to be a bare ``if os.getenv(...)``, so ANY
    # non-empty value enabled the suppressor — ``=0`` meant "probes off". The
    # registry's shared parse accepts {1,true,yes,on} only, so ``=0`` now means
    # what it reads like. conftest.py sets "1", so the suite is unaffected.
    from admz import capabilities

    if capabilities.is_active(_DISABLE_CAPABILITY):
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason": "onboarding probes disabled in this environment"}

    try:
        device_info = registry.get_device_info(device_id)
    except Exception as exc:  # noqa: BLE001 - unknown device
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason": f"device lookup failed: {exc}"}

    executor = (executors or {}).get("vapix")
    if executor is None or catalog is None:
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
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
                    "reason": f"device at {host} is not reachable"}

    # ---- 1. Stored credentials already work? -----------------------------
    stored: Optional[Dict[str, Any]] = None
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
        if ok is True:
            if learned:
                _persist_probe_marker(registry, device_id, device_info, learned)
            return {"status": ALREADY_CREDENTIALED, "device_id": device_id}
        # Rejected or indeterminate: fall through — a stale stored password
        # is exactly what the fleet-pair try below may repair.

    # ---- 2. Factory-defaulted → provision from fleet settings ------------
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
                    "Approving creates a root admin account on it."
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
                    "under_approval": approved_action(),
                    "confirm_token": approved_token(),
                },
            )
            return {
                "status": PROVISIONED, "device_id": device_id,
                "username": result.get("username"),
                "password_source": result.get("password_source"),
            }
        return {"status": PROVISION_FAILED, "device_id": device_id,
                "error": result.get("error")}

    # ---- 3. Entry credentials, then ADMZ's own account -------------------
    #
    # ADR-0061 / FR-CRED-011. This step used to try ONE fleet pair and, on
    # success, store that pair as the device's ongoing credential — so a single
    # shared password became the standing key to every device onboarded this
    # way. Now the list gets ADMZ *in*, and ADMZ creates its own account to
    # stay in.
    #
    # The entry credential is never removed or rotated. After a database loss
    # every generated password is gone and it is the only way back.
    from admz import entry_credentials as _entry
    from admz.provisioning import adopt_with_admz_account

    candidates = _entry.attempt_order()
    if not candidates:
        reason = ("no entry credentials configured"
                  if not _entry.prompt_always() else
                  "this installation stores no entry credentials by policy")
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id, "reason": reason}

    reason = "every entry credential was rejected by the device"
    for cred in candidates:
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
                    f"Device '{device_id}' at {host} accepted an entry credential "
                    f"({cred.username}). Approving creates ADMZ's own 'admz' admin "
                    "account on it; the entry credential is left in place."
                ),
            )
            record_event(
                None, "provision.gated", resource=f"device:{device_id}",
                details={"host": host, "reason": "adopt",
                         "entry_username": cred.username},
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
            return {"status": ADMZ_ACCOUNT_CREATED, "device_id": device_id,
                    "username": result["username"],
                    "entry_username": cred.username}

        # Creating the account failed but the entry credential works. Store it
        # rather than lose the device: a managed device on a shared credential
        # is worse than one on its own, and much better than an unmanaged one.
        # The status says which happened so nobody reads it as the good path.
        store_provisioned_creds(
            registry, device_id, cred.username, cred.password,
            purpose="Entry credential verified at onboarding; admz account not created",
        )
        logger.warning(
            "device %s adopted on its entry credential — creating the admz "
            "account failed: %s", device_id, result.get("error"),
        )
        return {"status": ENTRY_CREDENTIALS_SAVED, "device_id": device_id,
                "username": cred.username,
                "admz_account_error": result.get("error")}

    return {"status": CREDENTIALS_NEEDED, "device_id": device_id, "reason": reason}
