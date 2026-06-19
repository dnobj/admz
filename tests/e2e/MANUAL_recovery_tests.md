# Manual test plan — factory-defaulted device handling

Covers the parts of the `needs_setup` / deferred-recovery feature (PR #70/#71)
that the automated E2E suite can't safely or fully assert: the **UI rendering**
and the **real destructive re-provision** (which mutates a device).

The automated coverage lives in `test_22_recovery_rest.py` (REST lifecycle +
gates, no cost) and `test_23_recovery_chat.py` (chat intent-capture, Gemini cost).
Run those first: `pytest tests/e2e/test_22_recovery_rest.py tests/e2e/test_23_recovery_chat.py --run-e2e`.

Prereqs: server on :4242 (`.venv`, `ADMZ_AUTH_BACKEND=windows-local`), the health
monitor **enabled** (Settings → it is the trigger evaluator), and a factory-
defaulted device in inventory (the lab Q3538-SLVE `B8A44F661A2F` @ 192.168.1.238).

| # | Step | Expected |
|---|------|----------|
| **A. Detection (read-only, safe)** | | |
| A1 | Open **Devices**; find the factory-defaulted device | Amber **"Needs setup"** badge (NOT red "Auth failed") |
| A2 | The roster status counts / filters | A `needs_setup` group exists; the device is in it |
| A3 | Open the device detail page → drift card | Says *"factory-defaulted (needs provisioning) — recover or decommission"*, not a wall of "removed" fields |
| **B. Recovery card UI (safe — queue + cancel only)** | | |
| B1 | On a `needs_setup` device detail page | Amber banner: *"This device is factory-defaulted… Queue a re-provision below, or decommission it."* |
| B2 | Click **Queue re-provision** | Success message; the pending list shows *"⏳ reprovision · …expires in 24h"* with a **Cancel** button |
| B3 | Reload the page | The pending action is still listed (persisted, cross-process) |
| B4 | Click **Cancel** on the pending action | It disappears from the list |
| B5 | The **decommission** link in the banner | Triggers the existing Delete-device flow (its own confirm) — *don't confirm unless you intend to delete* |
| **C. Chat intent-capture (Gemini cost)** | | |
| C1 | Chat: "I want to factory reset device `<id>`" | Agent ASKS the follow-up (re-provision / remove / leave) before proceeding; gates the reset itself |
| C2 | Chat: "Queue a re-provision for `<online id>` when it comes back" | Agent calls `queue_device_recovery`, confirms it's armed (then cancel it: "cancel that recovery") |
| C3 | Chat: "What recovery actions are pending?" | Agent calls `list_device_recovery`, reports the queued one |
| **D. Real re-provision (DESTRUCTIVE — needs go-ahead + the live device)** | | |
| D1 | With the Q3538 in `needs_setup`, click **Queue re-provision** (or chat-queue it) | Pending action armed |
| D2 | Wait for the next health sweep (~60s) with the monitor enabled | Sweep fires the pending action **once**; audit log shows it attributed to the approver + "deferred-trigger" |
| D3 | Re-check the device health | Flips `needs_setup` → `online`; an admin account now exists (created from the fleet default password — never displayed) |
| D4 | Re-run the queue (fire-once check) | The fired action is gone; it does **not** fire again |
| D5 | Audit/event log | No device password anywhere in the payloads |

> D is the one path the automated suite deliberately skips — it creates an admin
> account on real hardware. Only run it with an explicit go-ahead on a device you
> intend to recover.
