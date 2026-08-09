# Deploying ADMZ on Windows

ADMZ ships as a **Shawl-supervised Windows service** authenticating with the
**`windows-local`** backend (ADR-0033) plus in-process **Negotiate SSO**
(ADR-0035), storing its data under **`ADMZ_HOME`** (ADR-0042). No IIS, no
reverse proxy, no domain required. That is the deployment described in Part 1,
and it is what production runs.

Part 2 documents the **IIS reverse-proxy / IWA** topology (ADR-0021). It is
still supported and is the right answer when an organisation requires IWA
terminated at IIS — but it is the alternative, not the default.

> **This document used to say the opposite.** Until GH #173 the numbered
> procedure was the IIS/NSSM path and the `windows-local` service was an
> "Alternative" 240 lines down: ADR-0033/0035/0042 each added their material
> without demoting the procedure they superseded. Two of that procedure's
> defects were wrong under *every* deployment model and are fixed below — an
> interpreter path that does not exist, and a service environment with no
> `ADMZ_HOME`, which silently sends the instance to `~/.admz` under whatever
> account the service runs as — **a separate database and a separate Fernet key
> from the one being backed up**. (An earlier draft of this note said it gives
> you a second *service*; Windows service names are case-insensitive, so
> `nssm install ADMZ` alongside the existing `admz` normally fails outright. The
> damaging case is the quieter one: any instance started under a different
> account, or with the old service replaced, silently builds its own store.)

> **Audience.** Ops engineers comfortable with Windows services and Python
> deployment. Part 2 additionally assumes IIS and AD.

---

# Part 1 — The standard deployment (Shawl + `windows-local`)

## What you get

Browser users reach ADMZ on port 4242, are redirected to `/login`, and can
**"Continue as the signed-in Windows user"** — SSO handled in-process by Windows
SSPI, no IIS. Group membership comes from the logon token, so a member of the
local `Administrators` group passes the credential-reveal gate with no LDAP.
Agents use `Authorization: Bearer admz_<key>`.

## Topology (standard)

```
Browser / agent
  - browser: Negotiate SSO, or the /login form
  - agent:   Authorization: Bearer admz_<...>
        |
        |  HTTP(S) :4242
        v
admz service  (Shawl -> python -m admz api)
  - windows-local + in-process SSPI
  - LocalSystem, delayed-auto start, auto-restart
  - ADMZ_HOME=C:\ProgramData\admz
```

## Prerequisites (standard)

1. **Windows 10/11 or Windows Server 2019+.** Domain membership optional — on a
   workgroup, Negotiate SSO falls back to NTLM (KL-AUTH-004/008).
2. **Python 3.8+** and a virtualenv holding ADMZ and its dependencies.
3. **[Shawl](https://github.com/mtkennerly/shawl)** on the box, to wrap the
   Python process as a service.
4. **An elevated PowerShell** — registering a service and setting a machine-wide
   environment variable both require it.

## Step 1 — Get the two paths right

These are the two things the old procedure got wrong, so they come first.

| | Value | Why it matters |
|---|---|---|
| Interpreter | `<checkout>\.venv\Scripts\python.exe` | The venv **inside** the checkout. On this project's host the checkout is `C:\admz\admz`, so it is `C:\admz\admz\.venv\Scripts\python.exe` — `C:\admz\` is the worktree *parent*, one level up. |
| `ADMZ_HOME` | `C:\ProgramData\admz` | **Set it explicitly.** Unset, `admz/paths.py` defaults to `~/.admz` under whatever account the service runs as, and the instance silently builds a fresh `admz.db` and `admz.key` there. |

A wrong interpreter path fails loudly. A missing `ADMZ_HOME` does not — which is
why it is the more dangerous of the two.

## Step 2 — Run the setup script

```powershell
# From an ELEVATED PowerShell:
cd C:\admz
.\setup-admz-service.ps1
```

It migrates an existing `~/.admz` to `C:\ProgramData\admz`; ACLs that directory
(without it, `ADMZ_HOME` is readable by all local users); fixes git ownership for
SYSTEM (`safe.directory`); updates the Org `repo_path` in the DB; sets the
machine-wide `ADMZ_HOME`; and registers the `admz` service through Shawl —
LocalSystem, delayed-auto start, auto-restart, rotating logs.

> **The script is not in this repository.** It lives beside the checkout as
> `C:\admz\setup-admz-service.ps1` on the deployment host and is not
> version-controlled (GH #377). Step 3 is what it does, so a host without it can
> still be brought up by hand.

## Step 3 — Or do it by hand

```powershell
# ELEVATED. Adjust the checkout path to yours.
$py = "C:\admz\admz\.venv\Scripts\python.exe"
$dataDir = "C:\ProgramData\admz"

New-Item -ItemType Directory -Force $dataDir | Out-Null

# Machine-wide, so the service and an interactive admin agree on these.
# ADMZ_AUTH_BACKEND is NOT optional: unset, admz/auth.py defaults to `none`
# and the service comes up ANONYMOUS -- no /login, no SSO, no gate on who
# you are. It is the single most important line in this block.
[Environment]::SetEnvironmentVariable("ADMZ_HOME", $dataDir, "Machine")
[Environment]::SetEnvironmentVariable("ADMZ_AUTH_BACKEND", "windows-local", "Machine")

# Only SYSTEM and Administrators may read the secrets directory.
# *S-1-5-32-544 is the built-in Administrators SID -- the NAME is localised and
# the command fails on a non-English Windows.
icacls $dataDir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F"

# --system, NOT --global (ADR-0054): --global writes the *interactive admin's*
# .gitconfig, and the service runs as LocalSystem, which never reads it.
git config --system --add safe.directory C:/admz/admz

shawl add --name admz --restart --log-dir "$dataDir\logs" -- $py -m admz api --host 127.0.0.1 --port 4242
sc.exe config admz start= delayed-auto
sc.exe start admz
```

**On the bind address.** `127.0.0.1` above is the safe default: the session
cookie is plaintext over HTTP, so a LAN bind exposes it (KL-AUTH-006). To serve
other machines, put TLS in front and set `ADMZ_SESSION_COOKIE_SECURE=1` before
widening the bind. Note that `_check_bind_safety` (`admz/__main__.py`) refuses a
non-loopback bind for the `windows` and `composite` backends but **not** for
`windows-local` — so nothing stops you; the judgement is yours.

`/grant:r` replaces the ACEs of the trustees it names and leaves any other
explicit ACEs in place, so on a directory migrated from `~/.admz` check what
survived: `icacls $dataDir`.

`admz.key` is hardened by the code on creation regardless of who creates it
(#207, ADR-0010), so the highest-value secret is protected even if the ACL step
is skipped. Nothing else in `ADMZ_HOME` is.

## Step 4 — Verify

```powershell
Invoke-RestMethod http://localhost:4242/api/health

# The service itself: running, LocalSystem, delayed-auto, right interpreter.
Get-CimInstance Win32_Service -Filter "Name='admz'" |
    Select-Object State, StartMode, StartName, PathName

# The environment it will actually inherit.
[Environment]::GetEnvironmentVariable("ADMZ_HOME", "Machine")
[Environment]::GetEnvironmentVariable("ADMZ_AUTH_BACKEND", "Machine")   # windows-local

# Authentication is really on: this must be 401 or a redirect to /login,
# NOT a 200. A 200 means the service is anonymous (see Step 3).
try { Invoke-WebRequest http://localhost:4242/api/devices -MaximumRedirection 0 }
catch { $_.Exception.Response.StatusCode.value__ }

# The secrets directory is not world-readable.
icacls C:\ProgramData\admz
```

The `/api/devices` check is the one worth keeping: `/api/health` bypasses auth
by design, so it returns 200 on a correctly configured *and* on a completely
anonymous instance. It cannot tell you the deployment worked.

**Use the `localhost` name, not `127.0.0.1`.** Literal IPs are never in the
Local Intranet zone, so Edge/Chrome prompt for credentials instead of signing you
in silently. For a LAN hostname, add the site to the Local Intranet zone; Firefox
needs `network.negotiate-auth.trusted-uris`. Disable the SSO button with
`ADMZ_SSO_NEGOTIATE=0`.

**Serve on 127.0.0.1, or front with TLS and set `ADMZ_SESSION_COOKIE_SECURE=1`**
— otherwise the session cookie travels over plaintext HTTP (KL-AUTH-006).

Voice and chat ride the same session: the cookie travels with the WebSocket
upgrade, so the signed-in identity flows into MCP tool calls and audit rows.

Logins are rate-limited (form 5/min/IP; SSO has a roomier bucket for its
handshake legs) and audited (`auth.login`, with a `method: form|negotiate`
detail). The password is used only for the `LogonUserW` call and is never
stored; SSO never sees one at all.

## Step 5 — Mint an API key for an agent

```powershell
C:\admz\admz\.venv\Scripts\python.exe -m admz api-key create --name nightly-snapshot-bot
```

The plaintext key is shown **once** — copy it then; only its hash is stored.

Unattended lab tooling (e.g. `tools/dev_auto_approve.py`) reads its key from
`ADMZ_DEV_API_KEY`.

## Changing the service later

Stopping and starting `admz` does not need elevation; **changing its
configuration does**. `sc.exe config` also fails on this service's long
`binPath` with error `1639` (invalid command line) — use
`Invoke-CimMethod -MethodName Change`, which passes the string as a parameter
rather than a command line.

## ACS Pro note

The ACS connection authenticates as the service's Windows identity. If the ACS
server does not authorize SYSTEM/Administrators, set the service Log On to a
local account that ACS does authorize.

---

# Part 2 — Alternative: IIS reverse proxy with IWA (ADR-0021)

Use this when the organisation requires Windows Integrated Authentication
terminated at IIS. It is supported and ADR-0021 was never withdrawn — but Part 1
is the default, and none of the following is needed for it.

## Topology (IIS)

```
┌────────────────────────────┐
│ Browser / agent            │
│ • Browsers send Negotiate  │
│   (Kerberos / NTLM)        │
│ • Agents send              │
│   Authorization: Bearer    │
│   admz_<...>               │
└─────────────┬──────────────┘
              │ HTTPS :443
              ▼
┌────────────────────────────┐
│ IIS                        │
│ • Windows Authentication   │
│ • Anonymous DISABLED       │
│ • URL Rewrite + ARR        │
│ • Sets REMOTE_USER         │
│ • TLS termination          │
└─────────────┬──────────────┘
              │ HTTP :4242 (localhost only)
              ▼
┌────────────────────────────┐
│ uvicorn / ADMZ FastAPI     │
│ • Binds 127.0.0.1:4242     │
│ • Reads REMOTE_USER        │
│ • LDAP group enrichment    │
│ • Audit log                │
└────────────────────────────┘
```

## Prerequisites (IIS)

1. **Windows Server 2019+** (or Windows 10/11 Pro/Enterprise for dev).
2. **IIS** with these role services enabled:
   - Web Server → Common HTTP Features → Static Content, Default Document
   - Web Server → Security → **Windows Authentication**
   - Web Server → Security → Request Filtering
   - Management Tools → IIS Management Console
3. **URL Rewrite module** — download from
   <https://www.iis.net/downloads/microsoft/url-rewrite>.
4. **Application Request Routing (ARR) module** — download from
   <https://www.iis.net/downloads/microsoft/application-request-routing>.
5. **Python 3.8+** with the ADMZ package installed (see main README).
6. **Domain membership** (recommended) for Kerberos; workgroup hosts fall
   back to NTLM, which works but is weaker.

## Step 1 — Install ADMZ as a Windows service

We use **NSSM (Non-Sucking Service Manager)** to wrap uvicorn as a Windows
service. Alternatives include `sc create`, `pywin32`'s service framework,
or `HttpPlatformHandler` (covered briefly at the end).

```powershell
# Install NSSM (chocolatey example)
choco install nssm

# Create a low-privilege local user to run ADMZ under, OR use a
# domain service account that the operator team owns.
# (Service accounts with strong passwords are preferred for production.)

# Install the service. Replace paths and the account as needed.
nssm install ADMZ "C:\admz\admz\.venv\Scripts\python.exe" "-m admz api --host 127.0.0.1 --port 4242"
nssm set ADMZ AppDirectory "C:\admz\admz"
nssm set ADMZ AppEnvironmentExtra `
    "ADMZ_HOME=C:\\ProgramData\\admz" `
    "ADMZ_AUTH_BACKEND=composite" `
    "ADMZ_BASE_URL=https://admz.example.com" `
    "ADMZ_LDAP_ENABLED=true" `
    "ADMZ_LDAP_SERVER=ldap://dc.example.com" `
    "ADMZ_LDAP_BASE_DN=DC=example,DC=com" `
    "ADMZ_LDAP_BIND_USER=CN=svc-admz,OU=Service Accounts,DC=example,DC=com" `
    "ADMZ_LDAP_BIND_PASSWORD=<bind-account-password>" `
    "ADMZ_LOG_LEVEL=INFO"

# Run under a specific account (replace DOMAIN\svc-admz)
nssm set ADMZ ObjectName "DOMAIN\svc-admz" "<account-password>"

# Start
nssm start ADMZ
```

> ⚠️ **Bind to `127.0.0.1` only.** ADMZ trusts the `REMOTE_USER` header
> only when the request originates from a trusted-proxy IP (default:
> `127.0.0.1`, `::1`). If uvicorn were reachable from the network,
> anyone could spoof the header and bypass auth. The `--host 127.0.0.1`
> default is intentional. The `_check_bind_safety` startup check
> refuses to launch with a permissive bind when an IWA-trusting backend
> is selected.

Verify uvicorn is up:

```powershell
curl http://127.0.0.1:4242/health
# {"status":"healthy","service":"admz","version":"2.0.0"}
```

## Step 2 — Configure IIS

### 2a. Create the site

In IIS Manager:

1. **Sites → Add Website**
   - Site name: `admz`
   - Physical path: `C:\inetpub\wwwroot\admz` (create the folder; it
     only holds `web.config`, no static content)
   - Binding: `https`, port `443`, hostname `admz.example.com`, with
     a TLS certificate (use AD CS, public CA, or a wildcard cert).

### 2b. Enable Windows Authentication

In the new site:

1. **Authentication** feature → Disable **Anonymous Authentication**.
2. **Authentication** feature → Enable **Windows Authentication**.
3. Right-click Windows Authentication → **Providers** → ensure
   **Negotiate** is listed first (Kerberos), then **NTLM**.

### 2c. web.config — URL Rewrite to uvicorn

Place this at `C:\inetpub\wwwroot\admz\web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <!-- Allow forwarding the REMOTE_USER server variable to the
         backend via the X-Remote-User header (URL Rewrite needs
         this explicit allowance). -->
    <rewrite>
      <allowedServerVariables>
        <add name="HTTP_REMOTE_USER" />
      </allowedServerVariables>
      <rules>
        <rule name="ADMZ reverse proxy" stopProcessing="true">
          <match url=".*" />
          <serverVariables>
            <!-- Forward the authenticated username to uvicorn. -->
            <set name="HTTP_REMOTE_USER" value="{REMOTE_USER}" />
          </serverVariables>
          <action type="Rewrite" url="http://127.0.0.1:4242/{R:0}" />
        </rule>
      </rules>
    </rewrite>

    <!-- Recommended security headers (defense in depth). -->
    <httpProtocol>
      <customHeaders>
        <add name="Strict-Transport-Security"
             value="max-age=31536000; includeSubDomains" />
        <add name="X-Content-Type-Options" value="nosniff" />
        <add name="X-Frame-Options" value="DENY" />
      </customHeaders>
    </httpProtocol>
  </system.webServer>
</configuration>
```

### 2d. Enable ARR's reverse-proxy mode

ARR ships with reverse-proxy support disabled. Enable it once per IIS
host:

1. In IIS Manager, click the **server node** (top of the tree, your
   machine name).
2. Double-click **Application Request Routing Cache**.
3. In the right pane: **Server Proxy Settings...**
4. Check **Enable proxy**. Save.

Without this step, the URL Rewrite rule above silently fails to
forward — you'll get 404s from IIS instead of responses from uvicorn.

## Step 3 — Tell ADMZ about the proxy

ADMZ reads the username from `REMOTE_USER` by default. The web.config
above sets `HTTP_REMOTE_USER`, which arrives at uvicorn as the
`REMOTE_USER` request header (the `HTTP_` prefix is the IIS convention;
uvicorn drops it). No `ADMZ_AUTH_REMOTE_USER_HEADER` override needed.

If your IIS setup uses a different header (some templates use
`X-Forwarded-User`), set:

```powershell
nssm set ADMZ AppEnvironmentExtra +ADMZ_AUTH_REMOTE_USER_HEADER=X-Forwarded-User
```

## Step 4 — Verify

```powershell
# As a domain user, in PowerShell (sends Negotiate creds):
Invoke-WebRequest https://admz.example.com/api/whoami -UseDefaultCredentials | Select-Object -ExpandProperty Content
# {"name": "EXAMPLE\\alice", "display_name": "alice", ...
#  "source": "windows", "groups": ["Admins", "Operators"], "is_anonymous": false}

# Without creds:
curl https://admz.example.com/api/whoami
# HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Negotiate, NTLM
```

Browser test: open `https://admz.example.com/` in a domain-joined browser
on a domain-joined host. IE/Edge/Chrome on Windows will SSO. The web UI
should show "Signed in as alice" in the nav bar.

## Step 5 — Mint an API key for an agent

```powershell
# On the ADMZ host, as a logged-in operator:
cd C:\admz
python -m admz api-key create --name "nightly-snapshot-bot"
#
# API key created (id=1, name='nightly-snapshot-bot')
# Created by: DOMAIN\alice:cli
#
#   ┌─────────────────────────────────────────────────────────
#   │ admz_aB1c2D3e4F5g6H7i8J9k0L1m2N3o4P5q6R7s8T9u0V1w2X3y4Z
#   └─────────────────────────────────────────────────────────
#
# This is the ONLY time the plaintext will be shown.
# Copy it now and store it where your agent can read it.
```

Give the agent the key. It calls ADMZ via:

```bash
curl https://admz.example.com/api/devices \
    -H "Authorization: Bearer admz_aB1c2D3e..."
```

## Where `windows-local` fits

The `windows-local` + Shawl deployment is **Part 1** of this document, not an
alternative to the IIS path. The contrast that matters here:

| | Part 1 (`windows-local`) | Part 2 (IIS + IWA) |
|---|---|---|
| Who authenticates | ADMZ, via `LogonUserW` and in-process SSPI | IIS, which sets `REMOTE_USER` |
| Groups from | the Windows logon token | LDAP enrichment (ADR-0023) |
| Needs a domain | no (workgroup falls back to NTLM) | effectively yes |
| Needs IIS | no | yes |
| `ADMZ_AUTH_BACKEND` | `windows-local` | `composite` |

Both accept `Authorization: Bearer admz_<key>` from agents, unchanged.

## Health probes

IIS and load balancers should probe `https://admz.example.com/health`
(or `/api/health`). Both bypass auth. `/api/health` is the more
informative probe — it actually exercises the registry connection.

## Common pitfalls

| Symptom | Likely cause |
|---|---|
| 401 from `/api/whoami` even with creds | ARR proxy not enabled (Step 2d). Check IIS logs. |
| 401 from `/api/whoami` with `"Request did not originate from a trusted reverse proxy"` | uvicorn is reachable from outside localhost. Bind to 127.0.0.1 (Step 1) or override with `ADMZ_AUTH_TRUSTED_PROXIES`. |
| `REMOTE_USER` empty at uvicorn | `<allowedServerVariables>` missing from web.config. |
| Browser shows credential prompt repeatedly | SPN missing for the service account, or Kerberos delegation misconfigured. Falls back to NTLM if available; check IIS Authentication providers. |
| Workgroup host, no AD groups | Expected — `ADMZ_LDAP_ENABLED=false`. Auth still works via NTLM but `Principal.groups` is empty. |
| Capture/confirm URLs point at `localhost:8000` | `ADMZ_BASE_URL` not set. The MCP server warns about this on startup. Set to `https://admz.example.com`. |

## Alternative: HttpPlatformHandler instead of NSSM

IIS's `HttpPlatformHandler` can run uvicorn as a child of the IIS
worker process. Simpler in some ways (one less service to manage) but
couples ADMZ's lifecycle to IIS recycles. Configuration sketch:

```xml
<system.webServer>
  <handlers>
    <add name="httpPlatformHandler" path="*" verb="*"
         modules="httpPlatformHandler" resourceType="Unspecified" />
  </handlers>
  <httpPlatform processPath="C:\admz\.venv\Scripts\python.exe"
                arguments="-m admz api --host 127.0.0.1 --port %HTTP_PLATFORM_PORT%"
                stdoutLogEnabled="true"
                stdoutLogFile=".\logs\admz">
    <environmentVariables>
      <environmentVariable name="ADMZ_AUTH_BACKEND" value="composite" />
      <environmentVariable name="ADMZ_BASE_URL" value="https://admz.example.com" />
      <!-- ...rest of the env vars... -->
    </environmentVariables>
  </httpPlatform>
</system.webServer>
```

If you go this route you can drop the NSSM step entirely; otherwise
keep them separate. The reverse-proxy / Windows Authentication
configuration is the same in both topologies.

## Where state lives

All state lives under **`ADMZ_HOME`** (ADR-0042). The default is the launching
user's `~/.admz` (dev installs); **server deployments should set
`ADMZ_HOME=C:\ProgramData\admz`** so the data is machine-level and the service
can run as LocalSystem — no user profile, no service password. The specific
overrides (`ADMZ_DB_PATH`, `ADMZ_KEY_PATH`, `ADMZ_CONFIG_REPO_PATH`,
`ADMZ_REPO_PATH_ROOT`) still win over `ADMZ_HOME` when set.

For every other `ADMZ_*` variable — and in particular for the ones that turn a
guarantee off — see **[`ENVIRONMENT.md`](ENVIRONMENT.md)**. Note especially
that `ADMZ_AUTO_PUSH` defaults **ON**, so an instance built from this guide
alone will push its config repo to the configured origin.

| File | Path (under `ADMZ_HOME`) | What |
|---|---|---|
| Encrypted device registry | `admz.db` | Devices, accounts, capture sessions, confirm sessions, fleet settings, **API keys**, **audit log** — one SQLite file, WAL mode |
| Fernet key | `admz.key` | Encrypts `admz.db` account passwords |
| Config repo | `config-repo\` | Git working tree for snapshots (default Org) |
| Org repos | `repos\<org_id>\` | Git working trees for additional Orgs |
| Legacy schedules | `schedules.json` | Pre-ADR-0037 recurring snapshots (migrated to the DB) |
| Firmware cache | `firmware\` | Cached firmware binaries (also the upload allow-list root) |
| Dev agent key | `dev-api-key.txt` | Dev/e2e Bearer key (plaintext lives ONLY here) |

**Security:** on a shared server, ACL `ADMZ_HOME` to SYSTEM + Administrators
only — it holds the Fernet key and API keys, and `C:\ProgramData` grants all
Users read by default. `setup-admz-service.ps1` does this, and **the
application code deliberately does not** (#250, ADR-0042): it cannot know the
operator account to grant, and a non-elevated administrator's UAC-filtered
token does not carry `BUILTIN\Administrators`, so a code-authored ACL would
lock the operator out of their own data directory. Running ADMZ on Windows
without that script leaves `ADMZ_HOME` readable by all local users.

The `admz.key` file *is* hardened by the code, on creation, regardless of who
creates it (#207, ADR-0010) — so the highest-value secret is protected even on
a host where the setup script was never run.

**Service deployment (Shawl):** `setup-admz-service.ps1` migrates an existing
`~/.admz` to `C:\ProgramData\admz`, fixes git ownership for SYSTEM
(`safe.directory`), updates the Org `repo_path` in the DB, sets the machine-wide
`ADMZ_HOME`, and registers the `admz` service via the Shawl wrapper
(LocalSystem, delayed-auto start, auto-restart, rotating logs). ACS Pro note:
the ACS connection authenticates as the service's Windows identity — if the ACS
server doesn't authorize SYSTEM/Administrators, set the service Log On to a
local account that ACS authorizes.

**Backup:** `admz.db` and `admz.key` MUST be backed up together — the
DB without the key is useless. See README §Backup.

## See also

**The standard deployment (Part 1):**

- [ADR-0033: windows-local authentication](specification/decisions/0033-windows-local-credential-auth.md)
- [ADR-0035: in-process Negotiate SSO](specification/decisions/0035-negotiate-sso-login.md)
- [ADR-0042: ADMZ_HOME and the Windows service](specification/decisions/0042-machine-level-data-directory.md)
- [ADR-0054: dev/prod tree and venv split](specification/decisions/0054-separate-production-tree-and-venv.md)

**The IIS alternative (Part 2):**

- [ADR-0021: Windows IWA via reverse proxy](specification/decisions/0021-windows-iwa-via-reverse-proxy.md)
- [ADR-0022: API keys for agents](specification/decisions/0022-api-keys-for-agents.md)
- [ADR-0023: LDAP group enrichment](specification/decisions/0023-ldap-group-enrichment.md)
- [Requirements: authentication](specification/requirements/authentication.md)
