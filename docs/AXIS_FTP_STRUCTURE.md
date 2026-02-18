# Axis Public FTP Directory Structure

Reference document for the Axis firmware distribution site at `https://www.axis.com/ftp/pub_soft/`.

**Server:** Apache/2.4.66 (Debian) on www.axis.com:80
**Crawled:** 2026-02-15
**Authentication:** `ver.txt` files are public; `.bin` firmware downloads redirect to axis.com login (OAuth 2.0 + PKCE via AWS Cognito). An Axis account is required.

---

## Root Directory (`/ftp/pub_soft/`)

26 directories + 1 file (`Thumbs.db`, 46K, 2016-05-16):

| Directory | Last Modified | Purpose |
|-----------|---------------|---------|
| `MPQT/` | 2026-01-15 | **Camera/encoder firmware** (655+ models) |
| `PACS/` | 2025-09-26 | **Access control / intercom / speaker firmware** (57 models) |
| `AXIS_Audio_Manager_Pro/` | 2025-10-22 | Audio management software (43 versions, 3.1.2 - 5.0.38) |
| `IPInstaller/` | 2022-10-05 | Legacy IP installer (1998-1999 era) |
| `access_srv/` | 2015-03-07 | Legacy access server (9010 models, 2004-era) |
| `applications/` | 2025-01-15 | ACAP analytics apps (38 apps) + NVR + support tools |
| `audio_clips/` | 2018-11-20 | `audio_clips.zip` (240K) |
| `axis_recorder_toolbox/` | 2026-01-21 | Recorder toolbox (versions 2.0 - 3.10.2) |
| `bw/` | 2025-11-16 | Body-worn camera system (firmware, docs, integrations) |
| `cam_srv/` | 2026-02-11 | VMS/software suite (ACS, ADM, Camera Station, Genetec, legacy firmware) |
| `cd_srv/` | 2020-05-18 | Legacy CD server |
| `dev_board/` | 2007-04-03 | Development board files (2007-era) |
| `hd_srv/` | 1999-09-21 | Legacy HD server (1999-era) |
| `ibm_prd/` | 2015-03-07 | IBM product files |
| `ipjumpstarter/` | 2021-10-11 | IP JumpStarter utility (versions 1.00, 1.20) |
| `plugin_autodesk_revit/` | 2025-12-22 | Autodesk Revit plugin (login-gated) |
| `plugin_cra_iberia/` | 2019-01-10 | CRA Iberia plugin |
| `prodhelp/` | 2011-10-03 | Product help files |
| `prt_srv/` | 2015-03-06 | Legacy print server |
| `pubtool/` | 2024-06-25 | Publishing tool (boxdesc, SBOMs, uploads) |
| `remote_support/` | 2025-11-25 | Remote support tools (AnyDesk, TeamViewer) |
| `scan_srv/` | 2007-09-07 | Legacy scan server |
| `system_design_tools/` | 2023-02-07 | Acoustical simulation + Visio coverage shapes |
| `thinwzrd/` | 2026-02-12 | ThinWizard (`boxdesc.xml` 1.0M + `software/`) |
| `toolset_bluebeam_revu/` | 2025-11-28 | Bluebeam Revu toolset (likely login-gated) |
| `utility/` | 2022-04-05 | Utilities (JP, MM_O, tcpmon) |

---

## MPQT/ -- Camera & Encoder Firmware

**URL:** `https://www.axis.com/ftp/pub_soft/MPQT/`
**Model count:** 655+ model folders (681 with firmware available as of 2026-02-15)

### Organization

Flat directory with one folder per model, named exactly as the model (e.g., `P3245-V/`, `M3086-V/`, `Q6075-E/`).

Naming conventions:
- Underscores replace spaces (e.g., `Companion_Dome_V`)
- `Mk_II` / `Mk_III` suffixes for hardware revisions
- Special prefixes: `ExCam_`, `XFQ`, `XPQ`

### Model Series

| Series | Range | Product Type |
|--------|-------|-------------|
| C | C1710, C1720 | Speakers (newer models) |
| Companion | 360_P, Bullet_LE, Cube, Dome, Eye, Recorder | Consumer line |
| D | D1110 - D8308 | Dome, fixed, modular cameras |
| F | F34, F41, F44, F9104-B - FA54 | Modular/pin-hole cameras |
| M | M1004-W - M7116 | Fixed domes, mini-domes, encoders |
| P | P1126-Z - P9117-PV | Fixed box, bullets, PTZ, panoramic, encoders |
| Q | Q1602 - Q8752-E | Professional cameras, thermal, PTZ, multi-sensor |
| S | S3008, S3016, S4000 | Network switches/recorders |
| SR | SR | System recorder |
| T | T8412 - T8705 | Network switches/media converters |
| V | V5914 - V5938 | PTZ cameras |
| W | W400, W401 | Body-worn cameras |

### Directory Structure Per Model

```
P3245-V/
    9_80_3_10/          # Version folders (underscores = dots)
    9_80_3_11/
    ...
    9_80_132/
    10_12_130/
    10_12_262/
    ...
    11_11_148/
    11_11_160/
    11_11_169/
    11_11_176/
    11_11_181/
    latest/             # Always present, latest version
```

### File Layout: `latest/` Folder

| File | Size | Description |
|------|------|-------------|
| `{MODEL}.bin` | 60-100M | Firmware binary (no version in name) |
| `ver.txt` | ~9 bytes | Version string (e.g., `11.11.181`) |
| `howtoupgrade.txt` | 7.1K | Generic upgrade instructions |
| `thirdpartysoftwarelicenses_{MODEL}.html` | 2.4M | License file |

### File Layout: Versioned Folder (e.g., `11_11_181/`)

| File | Size | Description |
|------|------|-------------|
| `{MODEL}_{VERSION}.bin` | 60-100M | Firmware binary (version in name) |
| `{MODEL}_{VERSION}_sbom.cyclonedx.json` | 1.3M | CycloneDX SBOM (newer releases only) |
| `{MODEL}_{VERSION}_thirdpartysoftwarelicenses.html` | 2.4M | License file |
| `howtoupgrade.txt` | 7.1K | Upgrade instructions |

LTS track versions may use `.txt` instead of `.html` for the license file.

### Version Numbering

- **LTS tracks:** 9.80.x, 10.12.x (long-term support)
- **Active tracks:** 11.x, 12.x
- Folder names use underscores: `11_11_181` = version `11.11.181`
- Typically 3 segments: `major.minor.patch`

---

## PACS/ -- Access Control, Intercoms, Speakers, Recorders

**URL:** `https://www.axis.com/ftp/pub_soft/PACS/`
**Model count:** 57 model folders

### Organization

Same flat model-per-folder pattern as MPQT. Identical directory conventions and file layout.

### Model List by Category

**A-series (Access Controllers & I/O) -- 20 models:**

| Folder | Product Type | Notes |
|--------|-------------|-------|
| `A1001/` | Network Door Controller | Legacy, versions 1.30-1.65 |
| `A1210/` | Network Door Controller | |
| `A1210-B/` | Network Door Controller | |
| `A1601/` | Network Door Controller | |
| `A1610/` | Network Door Controller | Active, up to 12.8.55.1 |
| `A1610-B/` | Network Door Controller | |
| `A1710/` | Network Door Controller | |
| `A1810/` | Network Door Controller | |
| `A4020-E/` | Network Reader | |
| `A4120-E/` | Network Reader | Small: 113K bin |
| `A4612/` | Network Reader | |
| `A8004-VE/` | Network Video Door Station | |
| `A8105-E/` | Network Video Door Station | |
| `A8207-VE/` | Network Video Door Station | Versions 1.85 - 12.x |
| `A8207-VE_Mk_II/` | Network Video Door Station Mk II | |
| `A9161/` | Network I/O Relay Module | Versions 1.10-1.84 |
| `A9188/` | Network I/O Relay Module | |
| `A9188-VE/` | Network I/O Relay Module | |
| `A9210/` | Network I/O Relay Module | |
| `A9910/` | Network Module | |

**C-series (Network Audio) -- 18 models:**

| Folder | Product Type | Notes |
|--------|-------------|-------|
| `C1004-E/` | Network Cabinet Speaker | 70+ version dirs |
| `C1110-E/` | Network Ceiling Speaker | |
| `C1111-E/` | Network Ceiling Speaker | |
| `C1210-E/` | Network Ceiling Speaker | |
| `C1211-E/` | Network Ceiling Speaker | |
| `C1310-E/` | Network Pendant Speaker | 58 version dirs |
| `C1310-E_Mk_II/` | Network Pendant Speaker Mk II | |
| `C1410/` | Network Mini Speaker | |
| `C1410_Mk_II/` | Network Mini Speaker Mk II | |
| `C1510/` | Network Ceiling Speaker | |
| `C1511/` | Network Ceiling Speaker | |
| `C1610-VE/` | Network Sound Projector | |
| `C2005/` | Network Ceiling Speaker | Many version dirs |
| `C3003-E/` | Network Horn Speaker | |
| `C6110/` | Network Paging Console | Versions 12.0-12.8 |
| `C8033/` | Network Audio Bridge | |
| `C8110/` | Network Audio Amplifier | |
| `C8210/` | Network Audio Amplifier | 71 version dirs |

**I-series (Intercoms) -- 7 models:**

| Folder | Product Type | Notes |
|--------|-------------|-------|
| `I5304/` | Network Intercom | Single version 2.49.0 |
| `I7010-VE/` | Network Video Intercom | |
| `I7010-VE_Safety/` | Network Video Intercom Safety | |
| `I7020/` | Network Video Intercom | |
| `I8016-LVE/` | Network Video Intercom | 26 version dirs (10.0 - 12.7) |
| `I8116-E/` | Network Video Intercom | Versions 11.6 - 12.7 |
| `I8307-VE/` | Network Video Intercom | |

**S-series (Network Recorders) -- 8 models:**

| Folder | Product Type | Notes |
|--------|-------------|-------|
| `S2208/` | Network Video Recorder | 4 versions (1.1.0-1.2.2) |
| `S2208_Mk_II/` | Network Video Recorder Mk II | |
| `S2212/` | Network Video Recorder | |
| `S2212_Mk_II/` | Network Video Recorder Mk II | |
| `S2216/` | Network Video Recorder | |
| `S2216_Mk_II/` | Network Video Recorder Mk II | |
| `S2224/` | Network Video Recorder | |
| `S2224_Mk_II/` | Network Video Recorder Mk II | |

**Other -- 2 models:**

| Folder | Product Type | Notes |
|--------|-------------|-------|
| `TA1101-B/` | Temperature Alarm | Single version 1.0.38, 95K bin |
| `XC1311/` | Explosion-Protected Speaker | Versions 11.11-12.8 |

### PACS-Specific Notes

- Some A-series controllers include `{MODEL}_{VER}_release_notes.txt` in versioned folders
- Oldest models (A1001) include `.bin.sha256` checksum files (65 bytes)
- PACS version folders often have a 4th version segment (e.g., `10_12_310_1` = `10.12.310.1`)
- Firmware sizes range from 95K (TA1101-B) to 104M (I8016-LVE)

### Version Numbering in PACS

- **Legacy:** `1.x` (A1001: 1.30-1.65, A9161: 1.10-1.84, C1004-E: 1.25-1.97)
- **LTS:** `9.80.x.y` or `10.12.x.y`
- **Active:** `11.x.y`, `12.x.y`
- **Custom:** `2.49.0` (I5304), `1.0.38` (TA1101-B), `1.1.x`/`1.2.x` (S2208)

---

## Other Notable Directories

### `bw/` -- Body Worn Camera System

```
bw/
    ACAP/               Body Worn Live Self-hosted Server ACAP
    ACS5/               ACS 5 integration
    ACS6/               ACS 6 integration
    BWL/                Body Worn Live docs (PDFs)
    BWM_Pro/            Body Worn Manager Pro
    Manuals/            Documentation
    SR/                 System Recorder firmware
        12_5_75/
        12_5_76/
        Upgrade-to-this-trampoline-from-pre-11-11/
```

Body-worn system recorder firmware is here, not in MPQT. Body-worn cameras (W400, W401) are in MPQT.

### `cam_srv/` -- VMS & Software Suite

100+ directories including:
- `cam_station/`, `cam_station_pro/` -- AXIS Camera Station
- `axis_device_management/` -- AXIS Device Manager
- `ACS_Android/`, `ACS_iOS/` -- Mobile clients
- `ADM_Pilot/` -- ADM Pilot
- `accelerator_genetec/` -- Genetec integration plugins
- `cam_200p/` through `cam_2490/` -- Legacy camera firmware (1999-2014 era)

### `applications/ACAP/` -- Analytics Applications

38 ACAP apps including: Object Analytics, License Plate Verifier, Face Detector, People Counter, Loitering Guard, Motion Guard, Barcode Reader, Perimeter Defender, and more.

### `AXIS_Audio_Manager_Pro/`

43 version directories (3.1.2 - 5.0.38). Unusual pattern: `latest/` plus numbered `latest1/` through `latest17/`.

### `axis_recorder_toolbox/`

Versions 2.0 - 3.10.2 with a `latest/` folder.

---

## MPQT vs PACS Comparison

| Aspect | MPQT | PACS |
|--------|------|------|
| `latest/` subfolder | Always present | Always present |
| `ver.txt` in `latest/` | Yes | Yes |
| `ver.txt` format | Dot-separated (e.g., `11.11.181`) | Dot-separated (e.g., `12.8.55.1`) |
| Firmware extension | `.bin` | `.bin` |
| `latest/` bin naming | `{MODEL}.bin` | `{MODEL}.bin` |
| Versioned bin naming | `{MODEL}_{VERSION}.bin` | `{MODEL}_{VERSION}.bin` |
| SBOM file | `{MODEL}_{VER}_sbom.cyclonedx.json` (newer) | Same (newer releases) |
| License file ext | `.html` or `.txt` | `.html` or `.txt` |
| SHA-256 checksum | Not observed | Present for oldest models (A1001) |
| Release notes | Not in versioned folders | Some models have `_release_notes.txt` |
| `howtoupgrade.txt` | In root + versioned folders | In versioned folders + some latest/ |
| Version segments | Typically 3 (`11.11.181`) | 3 or 4 (`10.12.310.1` or `12.7.53`) |
| Firmware sizes | 60M-99M typical | 95K - 104M |

**Key finding:** MPQT and PACS use identical structural conventions. The same download logic works for both -- only the base URL differs.

---

## Model Prefix Routing

Used by ADMZ to determine which FTP base to try first:

| Prefix | FTP Location | Product Type |
|--------|-------------|-------------|
| `A` | PACS | Access controllers, door stations, I/O modules |
| `C1` | PACS | Speakers, amplifiers, audio (except C1710/C1720 in MPQT) |
| `I` | PACS | Intercoms |
| `S2` | PACS | Network video recorders |
| `TA` | PACS | Temperature alarms |
| `XC` | PACS | Explosion-protected speakers |
| All others | MPQT | Cameras, encoders, switches, PTZ, thermal, etc. |

Both locations are always tried as fallback. See `admz/firmware/downloader.py` for implementation.

---

## URL Patterns

### Version Check (public, no auth)
```
https://www.axis.com/ftp/pub_soft/{MPQT|PACS}/{MODEL}/latest/ver.txt
```

### Firmware Download (requires Axis account)

Latest version:
```
https://www.axis.com/ftp/pub_soft/{MPQT|PACS}/{MODEL}/latest/{MODEL}.bin
```

Specific version:
```
https://www.axis.com/ftp/pub_soft/{MPQT|PACS}/{MODEL}/{VER_UNDERSCORED}/{MODEL}_{VER_UNDERSCORED}.bin
```

Examples:
```
# Check latest version for P3245-V
GET https://www.axis.com/ftp/pub_soft/MPQT/P3245-V/latest/ver.txt
-> "11.11.181"

# Download latest P3245-V firmware (auth required)
GET https://www.axis.com/ftp/pub_soft/MPQT/P3245-V/latest/P3245-V.bin
-> 302 redirect to /my-axis/login

# Check latest I8016-LVE version
GET https://www.axis.com/ftp/pub_soft/PACS/I8016-LVE/latest/ver.txt
-> "12.7.53"
```

---

## Authentication Details

Firmware `.bin` downloads require an Axis account. The server returns a 302 redirect:

```
302 Found
Location: https://www.axis.com/my-axis/login?axis_destination=...
```

The `axis_destination` parameter encodes a license acceptance page URL, which then redirects to the actual download. The login flow uses OAuth 2.0 with PKCE through AWS Cognito (`eu.login.connect.axis.com`).

Automated download is not feasible -- users must download via browser while logged into axis.com.
