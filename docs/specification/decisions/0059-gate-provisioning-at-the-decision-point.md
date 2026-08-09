# ADR-0059 — Gate provisioning at the decision point, not at the entry points

**Status:** **Accepted** — adopted by the owner 2026-08-07, implemented 2026-08-09
in three slices (PRs #361 marker, #363 gate, #364 this). Supersedes the
*"Why the gate is here and not on `provision_factory_default`"* section of
[`admz/discovery/gated.py`](../../../admz/discovery/gated.py), which is rewritten
rather than deleted — see the amendment below.

> ### Amendment on implementation (2026-08-09): the entry-point gates were NOT retired
>
> The build plan said slice 3 would remove the two `discovery/gated.py` call
> sites "now that the chokepoint covers them". **That instruction was wrong and
> was not carried out.**
>
> The chokepoint covers *provisioning*. It does not cover what those two gates
> actually approve now: the survey gate approves a **blast radius** (scan this
> subnet), which cannot be expressed at the chokepoint because by then the scan
> has already happened; and `register_discovered_device` approves a **registry
> write** for a device the model discovered rather than a human named.
>
> Worse, removing the survey gate would have been actively harmful. Approving it
> is what runs the survey inside the approved context, and `create_task` copies
> that context into the background run — so one approval covers every device the
> survey provisions. Ungated, the survey would run unapproved and the chokepoint
> would fire **per device**, from a background task, with nobody on the page.
> One approval becomes N widgets nobody sees — precisely the failure the
> "Approved context" section below exists to prevent. The plan generalised
> "retire the entry points" from this ADR's argument without re-checking it
> against that section.
>
> What the three slices actually changed: provisioning is gated at the decision
> point, so `register_device` and `onboard_device` — previously ungated paths to
> a root account — now gate, and the register/onboard asymmetry is gone. The two
> pre-existing gates remain, doing a narrower and still-necessary job.
**Relates to:** ADR-0034 (one human gate; risk → level), GH #199 (the survey
provisioning gap this continues), GH #299 (the entry-point gate this revises),
GH #313 (the sibling gap this does **not** close — see *Why #313's refutation
does not apply*).

## Context

### What #299 decided, and why it was right

#299 gated the two discovery-driven provisioning paths. Its reasoning is
recorded in `admz/discovery/gated.py:10-27` and is worth quoting, because the
decision below revises it rather than dismisses it:

> Gating the provisioning step would make every caller inherit it, which sounds
> strictly better and is not. Three callers reach it legitimately and must not
> be held:
>
> * `tasks/handlers.py::_run_reprovision` — the deferred **scheduled** recovery
>   task. Nothing can approve a widget on the scheduler's behalf, so a gate
>   there does not delay the write, it fails it. This one is decisive.
> * `api/routes/devices.py::_run_onboarding` — an operator adding one device
>   they typed the address of. The intent is already explicit and singular.
> * `mcp/server.py::_register_device` — the same shape, one named device.
>
> What those three have in common is that the *device* is chosen before the
> call. What the two gated callers have in common is that the device set is
> chosen by a **scan**, so the operator approves a blast radius rather than a
> device.

That distinction — **the device is chosen before the call, versus chosen by a
scan** — is correct reasoning about a human caller. A person who types
`192.168.1.64` has already exercised the judgement a gate exists to obtain. A
person who asks for a subnet sweep has not, because they cannot know what the
sweep will find.

### Where it collapses

It does not hold for an LLM caller, and the reason is a capability the model has
that a human at a keyboard does not exercise in the same breath:

**The model can call `discover_network_devices` — an ungated read — and then
name what it just found.** The set is still chosen by a scan; it is simply
chosen by the *same actor* who then makes the "explicit, singular" call one turn
later. The two categories are not distinguishable at the call site, because
"chosen before the call" was always a proxy for "a human decided", and for an
autonomous caller that proxy fails.

The proof is in the current gate table: `register_discovered_device` is gated,
and `register_device` — which reaches the same write, on a device the model may
have discovered a moment earlier — is not.

**This is not a rebuke of #299.** #299 shipped a real gate where none existed,
its classification was sound for the caller it had in mind, and the entry-point
placement was the correct minimal change at the time. What has changed is not
the code but the recognition that one of its two categories is not well-defined
for the model.

### The four callers

`onboard_device_credentials` is the **provisioning decision point**: for a
factory-defaulted unit it calls `provision_factory_default`
(`admz/onboarding.py:133-137`), which issues `pwdgrp.cgi:add-user`,
`group=root`, `auth_method="none"` — a real admin account on a real device.

| # | caller | reachable by | gated today? |
|---|---|---|---|
| 1 | `mcp/server.py:2157` `_onboard_device` ← MCP tool `onboard_device` (`dispatch.py:408`) | **model** | **no** |
| 2 | `mcp/server.py:2157` via `_register_device` ← MCP tool `register_device` (`dispatch.py:407`) | **model** | **no** |
| 3 | `api/routes/devices.py:167` `_run_onboarding` ← `POST /api/devices`, `POST /api/devices/{id}/onboard` | operator (REST) | **no** |
| 4 | `demos/inference/collect.py:427` — the deep survey | operator/model | yes, at the route (#299) |
| 5 | `operations.py:808` — the approval executor | post-approval | n/a — it *is* the approval |

Three ungated, two of them model-reachable. A gate that covers rows 4 and 5 but
not 1–3 is not a gate on provisioning; it is a gate on two of the five ways to
reach provisioning.

## Decision

**Move the gate from the entry points to `onboard_device_credentials`, the
function that decides to provision.**

`provision_factory_default` itself stays **deliberately ungated**, exactly as
`discovery/gated.py` argues — see the next section.

### What the operator actually notices

**Only a factory-defaulted device triggers the gate. Ordinary device adds are
unaffected.** This is the narrow reading, and it is correct — but the mechanism
matters, because it constrains where the check may be placed.

There is no predicate that can be consulted up front. Whether provisioning will
happen is **not knowable without contacting the device**: it is decided at
`onboarding.py:133` by `read_systemready(...)` returning `needsetup`, i.e. by a
live probe. So the gate must sit **inside the function immediately before
`provision_factory_default`**, not at its entry. A gate at the entry *would*
fire on every add, which is the outcome to avoid.

By the time control reaches that branch, four things have happened and **all of
them are reads**:

1. a TCP probe of `:80` then `:443` (`onboarding.py:102-104`),
2. a registry credential lookup (local),
3. `_confirm_credentials` — an authenticated read, only if credentials exist,
4. `read_systemready` — an unauthenticated read.

Nothing has been written to the device. Gating at that point is therefore safe
and costs an unreachable or already-credentialed device nothing.

Concretely, these paths **never** gate:

- stored credentials already work → `ALREADY_CREDENTIALED` (`onboarding.py:124`)
- the device is not reachable → `CREDENTIALS_NEEDED` (`onboarding.py:106`)
- the fleet credential pair works, or capture is needed → steps 3–4

Only `needsetup=yes` gates — which is precisely the case that creates a root
account.

**The honest cost.** `onboard_device_credentials` returns a status dict and
never raises. A gate makes it able to return a new terminal status (an
approval-required envelope) that its five callers do not currently switch on. A
caller that ignores the new status treats it as "not provisioned" — which is
**fail-closed and therefore safe**, but reads as a confusing "credentials
needed" to the operator. Each caller must be updated to surface the approval
link. That is a smaller version of the same "callers must remember" problem this
ADR is trying to escape, and it should be recorded rather than glossed: the
implementation is not one line.

### Approved context: how an already-approved caller avoids re-gating

Rows 4 and 5 above are already approved and must not be gated again. Row 5 would
loop forever; row 4 would raise one widget **per device**, N times, inside an
approval the operator has already given.

Two shapes were considered.

#### (a) An explicit parameter — rejected

```python
async def onboard_device_credentials(*, device_id, registry, catalog,
                                     executors, approved_by=None):
    ...
    if ready and ready.get("needsetup"):
        if approved_by is None:
            return gate_scan_write(...)      # blocked envelope
```

**Its redeeming property, stated honestly: it fails closed.** Forgetting the
kwarg gates something that was already approved — annoying, and safe. Opening a
hole requires actively passing a value you invented, which is a different and
much more visible kind of mistake.

Rejected anyway, because it is the *"callers must be careful"* shape, and the
failure this ADR exists to correct — a gate that covers some call sites and not
others — is a **remembering** failure. A mechanism whose correctness depends on
each caller remembering something is the wrong instrument for that problem.

#### (b) A context variable — chosen

```python
# admz/approval_context.py
_APPROVED: ContextVar[str | None] = ContextVar("admz_approved_action",
                                              default=None)

@contextmanager
def approved(action: str):
    token = _APPROVED.set(action)
    try:
        yield
    finally:
        _APPROVED.reset(token)      # load-bearing — see below

def is_approved() -> bool:
    return _APPROVED.get() is not None
```

`operations.execute_approved_session` wraps the approved executor in
`with approved(action):`; `onboard_device_credentials` consults `is_approved()`
at the provisioning branch. No caller has to remember anything.

The property that makes this work for the survey: **`asyncio.create_task` copies
the current context**, so the background survey task started inside the approval
inherits it for the task's whole life. That is the correct semantics — the
operator approved *that survey*, including every device it provisions.

> **The `try/finally` is load-bearing, and this is what a reviewer must check.**
> A token that is set and never reset marks every later call on that task
> approved — the gate silently stops existing, and nothing fails or logs. This
> is a **fail-open** failure mode, which is the one property (a) does not have,
> and it is the price of not requiring callers to remember.
>
> It therefore needs a test asserting `is_approved()` is `False` after
> `execute_approved_session` returns, **including on the exception path**, and
> `_APPROVED` must never be `set()` anywhere outside the context manager.

## Contrast: when the chokepoint move is cheap (#164)

> **Added 2026-08-05 with #164. This does not change the decision above, which
> remains Proposed and unruled-on — it records the boundary condition that
> makes the decision above expensive, by showing a case where it is not.**

#164 is the same family: a four-part gate enforced in one route
(`POST /api/capabilities/{cap_id}`), while `fleet_settings.set()` stayed public
and four other routes wrote the same declared capability keys directly. The
obvious fix is the one this ADR argues for — move the check to where the write
happens.

There it was **cheap**, and shipped the same day. The difference is one
structural fact:

**When the chokepoint sits BELOW the approval boundary you need no context
token. When it IS the approval boundary, you do.**

- #164's chokepoint is `capabilities.set_enabled`. It enforces toggleability
  and writes the audit row; the *ceremony* (reveal-group membership, typed
  capability id, mandatory reason) lives in the route above it. So
  `operations.py::_action_set_event_ingest` — an ADR-0034 approval executor,
  structurally the twin of row 5 in the table above — simply **calls
  `set_enabled`** and inherits the audit without re-triggering anything.
- This ADR's chokepoint is `onboard_device_credentials`, which **is** the gate.
  An approved caller passing through it raises a second widget for work the
  operator already approved, which is why the `ContextVar` is needed here and
  nowhere in #164.

The practical test when this pattern recurs: *does an already-approved caller
have to pass through the proposed chokepoint, and does that chokepoint decide
whether to gate?* Two yeses mean an approved-context notion is unavoidable. One
yes means the approved caller can just use the sanctioned function, and the
move costs nothing.

## Why #313's refutation does not apply

[GH #313](https://github.com/dnobj/admz/issues/313) proposed, as its option 2,
making **`_execute_on_host`** consult the catalog risk so direct callers cannot
bypass a classification. That was refuted, correctly:

- `_execute_on_host` is the generic VAPIX helper. Gating it would also gate the
  temp-account **cleanup** path (`mcp/dispatch.py:394 _cleanup_temp_credentials`),
  making an orphaned-account problem worse — a cleanup that needs approval is a
  cleanup that does not happen.
- It would give `provisioning.py` a *second* gate on top of the one #299 already
  applies at the caller.
- And the scheduler objection stands: nothing can approve a widget on the
  scheduled reprovision task's behalf.

`onboard_device_credentials` sits **above** `_execute_on_host` and **below** the
entry points, and both refutations miss it:

1. **The scheduler does not route through it.** `tasks/handlers.py:216,225` —
   `_run_reprovision` imports and calls `provision_factory_default` *directly*.
   Gating `onboard_device_credentials` leaves the scheduled recovery task
   untouched. This is the specific fact #299 got wrong, and it is what makes
   this decision available now.
2. **Temp-credential cleanup does not route through it either.** Cleanup belongs
   to the `create_temp_credentials` flow, a separate path
   (`api/routes/devices.py:151` says so in writing).

So `provision_factory_default` remains ungated for exactly the reasons
`discovery/gated.py` gives, and the gate moves one level *above* it — to the
only function of the two that the scheduler avoids.

**This ADR does not close #313.** `_create_temp_credentials` creates a device
account without routing through `onboard_device_credentials` at all, so it is
untouched by this decision and still needs its own answer.

## Consequences

**Positive**

- One chokepoint. The register/onboard asymmetry cannot recur, because there is
  no longer a set of entry points to keep in step.
- The classification problem disappears: nothing has to decide whether a caller
  "chose the device before the call", a judgement that was never well-defined
  for an autonomous caller.
- Narrower in practice than the gate it replaces for ordinary use — an
  already-credentialed or unreachable device never sees a widget.

**Negative**

- The REST "add device" flow gains a gate on the factory-default branch. An
  operator adding a boxed-fresh camera now approves the root-account creation.
  That is a real operator-facing cost and the main reason this is a decision
  rather than a fix.
- Five callers must learn a new terminal status. Fail-closed if they do not, but
  confusing until they do.
- A new global concept (`approval_context`) with a fail-open failure mode,
  guarded only by a `try/finally` and the tests named above.

**Neutral / to verify at implementation**

- Whether the blocked envelope should carry the device id alone or the discovered
  metadata as well.
- Whether `_register_device` and `onboard_device` should *additionally* surface
  the approval link in their own return shape, or simply pass the envelope up.
- The audit row for an approved provisioning should name the device and the
  password *source*, never the password — the #199 item-2 precedent.
