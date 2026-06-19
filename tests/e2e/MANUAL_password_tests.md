# Manual test plan — device password management

Covers password set / change / rotate routing and the **real device-password
rotation** (which mutates a device's credentials) — the parts the automated
suite can't safely assert. Born from a bug where the chatbot, asked to "set the
password on my C1110", wrongly called `provision_device` (factory-defaulted
recovery only), failed, and mistranslated the auth failure as *"device
unreachable."*

Prereqs: server on `:4242` (`.venv`, `ADMZ_AUTH_BACKEND=windows-local`), at least
one **healthy, managed** device (e.g. the lab AXIS C1110-E `B8A44FB0BDA1`). For
section C you also need a device you are willing to rotate credentials on — **NOT
the audio loaner Q9307-LV**.

Background — how passwords flow in ADMZ (ADR-0009):
- Passwords NEVER enter chat. The **capture flow** (`capture_credentials`)
  hands the operator a one-time out-of-band `/capture/{token}` URL; the password
  goes straight into ADMZ's encrypted registry — not chat, not logs.
- The capture flow updates ADMZ's **stored** credential. Changing the password on
  the **device hardware** is a separate, gated VAPIX op
  (`pwdgrp.cgi:update-user`). `provision_device --force_change` is the one flow
  that does both atomically — but it is for factory-defaulted/provisioning use.

| # | Step | Expected |
|---|------|----------|
| **A. Routing — chat (Gemini cost; safe, nothing on the device changes)** | | |
| A1 | Chat: *"set the password on my C1110"* (a healthy managed device) | Agent routes to the **capture flow** — calls `capture_credentials` and returns an out-of-band `/capture/…` link. It does **NOT** call `provision_device`, and does **NOT** ask for / echo a password in chat. |
| A2 | Inspect the tool card | `capture_credentials` (not `provision_device`); no password text anywhere in the transcript. |
| A3 | (regression) If creds genuinely don't match, the agent's wording | Says *"authentication failed / credentials don't match"* — **never** *"the device is unreachable"* for an online device. |
| A4 | Chat: *"rotate the password on `<needs_setup device>`"* | For a factory-defaulted device it may legitimately mention provisioning/recovery — that's the one case `provision_device` is for. |
| **B. Stored-credential update via capture (safe — registry only, device untouched)** | | |
| B1 | Device detail → account → **Rotate password** | Redirects to the `/capture/{token}` page (out-of-band form). |
| B2 | Submit a new password on the capture page | ADMZ's **stored** credential updates; the token is single-use (re-POST fails). |
| B3 | Note | This updates only ADMZ's record — it does **not** change the device's actual password. Use it to fix a stale stored password, not to change the device. |
| **C. Change the DEVICE's actual password, then revert (DESTRUCTIVE — needs go-ahead + live device)** | | |
| C0 | Pick a safe lab device; confirm ADMZ currently operates it (health **online**, a read op works). Note the current password is held in the registry. | Baseline green. |
| C1 | Change the device password to a temp value via the **atomic** flow: MCP/dev `provision_device(device_id=<id>, force_change=true, password=<TEMP>)` *(run via the dev/API path — not chat, since passing a password in chat is disallowed)* | Result `status: provisioned`, `action_taken: changed_password`; device + registry both now on `<TEMP>`. No password in the response. |
| C2 | Re-run a read op / refresh device info | Succeeds with the new stored password (ADMZ kept itself in sync); health stays **online**. |
| C3 | (optional) `test_device_credentials` with the OLD password | Fails — confirming the device password really changed. |
| C4 | **Revert:** `provision_device(device_id=<id>, force_change=true, password=<ORIGINAL>)` | Back to the original; device + registry synced. |
| C5 | Re-run a read op / refresh | Succeeds with the restored original; health **online**. |
| C6 | Audit / event log for C1–C5 | **No device password** appears in any payload (only `changed_password`/status). |

> Alternative to C1/C4 (gated, two-step): `execute_operation` with
> `pwdgrp.cgi:update-user` (params `username`,`password`) — approve the gate —
> **then** update ADMZ's stored credential to match (`registry.update_account`),
> or ADMZ will lose access. `provision_device --force_change` is preferred
> because it keeps the device and registry in sync in one step.

Safety:
- If a revert (C4) fails, the device is left on `<TEMP>` (which you chose and
  recorded) — just re-run the revert. Do **not** power-cycle blindly.
- Record `<ORIGINAL>` before starting (it is in the registry, but note it).
- Never run this on the audio loaner Q9307-LV.

> **Known gap (follow-up):** there is no single *chat-driven* flow that both
> pushes a new password to the device **and** updates the registry via the
> out-of-band capture mechanism. `provision_device --force_change` is the atomic
> device+registry path but takes the password as a parameter rather than via
> capture. A clean "rotate device password via capture" tool/flow would close
> this — tracked separately.
