# Deploying ADMZ on Windows with Windows Authentication

This guide walks through deploying ADMZ on Windows Server (or Windows
10/11) with **Windows Integrated Authentication (IWA)** in front of
the FastAPI app via **IIS as a reverse proxy**. Result: browser users
sign in transparently via their existing Windows session; programmatic
agents use API keys.

> **Audience.** Ops engineers comfortable with IIS, AD service accounts,
> and Python web app deployment on Windows.

## Topology

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

## Prerequisites

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
nssm install ADMZ "C:\admz\.venv\Scripts\python.exe" "-m admz api --host 127.0.0.1 --port 4242"
nssm set ADMZ AppDirectory "C:\admz"
nssm set ADMZ AppEnvironmentExtra `
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

| File | Default path | What |
|---|---|---|
| Encrypted device registry | `C:\Users\<svc-account>\.admz\admz.db` | Devices, accounts, capture sessions, confirm sessions, fleet settings, **API keys**, **audit log** — one SQLite file, WAL mode |
| Fernet key | `C:\Users\<svc-account>\.admz\admz.key` | Encrypts `admz.db` account passwords |
| Config repo | `C:\Users\<svc-account>\.admz\config-repo\` | Git working tree for snapshots |
| Schedules | `C:\Users\<svc-account>\.admz\schedules.json` | Recurring snapshot definitions |
| Firmware cache | `C:\Users\<svc-account>\.admz\firmware\` | Cached firmware binaries |

**Backup:** `admz.db` and `admz.key` MUST be backed up together — the
DB without the key is useless. See README §Backup.

## See also

- [ADR-0021: Windows IWA via reverse proxy](specification/decisions/0021-windows-iwa-via-reverse-proxy.md)
- [ADR-0022: API keys for agents](specification/decisions/0022-api-keys-for-agents.md)
- [ADR-0023: LDAP group enrichment](specification/decisions/0023-ldap-group-enrichment.md)
- [Requirements: authentication](specification/requirements/authentication.md)
