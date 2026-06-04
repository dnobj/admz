"""Backward discoverability probe.

For each high-value VAPIX capability, ask the live Console (identify-don't-
execute phrasing) which operation to use, and check whether the correct
API/CGI surfaces in the answer. Clears chat history between probes so each
is independent. Prints a scorecard and dumps full responses for triage.

Usage: python tools/discoverability_probe.py [base_url]
"""
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4242"

# (label, query, [expected substrings — ANY match = pass])
PROBES = [
    ("device-info", "Which VAPIX operation returns an Axis device's model, serial number and firmware version? Name the operation ID; do not run it.", ["basicdeviceinfo"]),
    ("firmware-status", "Which VAPIX operation reports the firmware version or firmware status of an Axis device? Just name the operation ID.", ["firmwaremanagement", "basicdeviceinfo"]),
    ("system-ready", "Which VAPIX operation tells me whether an Axis device has finished booting and is ready? Name the operation ID only.", ["systemready"]),
    ("stream-status", "Which VAPIX operation lists the currently active video streams on an Axis camera? Name the operation ID only.", ["streamstatus"]),
    ("get-time", "Which VAPIX operation returns the current date and time on an Axis device? Name the operation ID only.", ["date.cgi", "root.time", "param.cgi", "time/"]),
    ("change-resolution", "Which VAPIX operation changes the video resolution on an Axis camera? Name the operation ID only.", ["param.cgi", "root.image"]),
    ("add-user", "Which VAPIX operation adds a new user account on an Axis device? Name the operation ID only.", ["pwdgrp"]),
    ("ir-light", "On an Axis camera with an IR illuminator, which VAPIX operation turns the IR light on? Name the operation ID only.", ["lightcontrol"]),
    ("status-led", "Which VAPIX operation controls the status LED indicator on an Axis device? Name the operation ID only.", ["ledcontrol"]),
    ("locate-device", "Which VAPIX operation makes an Axis device flash and/or beep so I can physically locate it? Name the operation ID only.", ["findmydevice"]),
    ("text-overlay", "Which VAPIX operation adds a text overlay onto an Axis camera's video image? Name the operation ID only.", ["dynamicoverlay"]),
    ("ntp", "Which VAPIX operation configures the NTP time server on an Axis device? Name the operation ID only.", ["ntp.cgi", "param.cgi", "root.time"]),
    ("day-night", "Which VAPIX operation switches an Axis camera between day and night (IR-cut filter) mode? Name the operation ID only.", ["daynight"]),
    ("play-clip", "On an Axis network speaker, which VAPIX operation plays a stored audio clip? Name the operation ID only.", ["mediaclip", "audio"]),
    ("ptz-move", "Which VAPIX operation pans and tilts a PTZ Axis camera? Name the operation ID only.", ["ptz"]),
    ("siren-flash", "On an AXIS D4200-VE strobe siren, which VAPIX operation makes it flash white for a few seconds? Name the operation ID only.", ["siren_and_light", "siren and light", "siren-and-light"]),
    ("snapshot", "Which VAPIX operation grabs a single still JPEG snapshot from an Axis camera? Name the operation ID only.", ["jpg", "image.cgi"]),
    ("system-logs", "Which VAPIX operation retrieves the system log from an Axis device? Name the operation ID only.", ["systemlog", "serverreport", "server report"]),
    ("reboot", "Which VAPIX operation reboots or restarts an Axis device? Name the operation ID only; do not run it.", ["restart.cgi", "firmwaremanagement", "reboot"]),
]


def _post(path, data, as_json=False, timeout=120):
    if as_json:
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json"}
    else:
        body = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in data.items()).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def probe(query):
    try:
        _post("/chat/clear", {}, timeout=30)
    except Exception:
        pass
    raw = _post("/api/chat", {"message": query}, as_json=True, timeout=150)
    d = json.loads(raw)
    return d.get("response") or d.get("answer") or ""


def main():
    results = []
    dump = []
    for label, query, expected in PROBES:
        t0 = time.time()
        try:
            resp = probe(query)
        except Exception as e:
            resp = f"<ERROR: {e}>"
        low = resp.lower()
        hit = next((e for e in expected if e.lower() in low), None)
        ok = hit is not None
        results.append((label, ok, hit, expected))
        dump.append({"label": label, "ok": ok, "hit": hit, "expected": expected,
                     "query": query, "response": resp})
        dt = time.time() - t0
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:18} {f'({hit})' if hit else '-- expected: ' + '/'.join(expected)}  ({dt:.0f}s)")
        sys.stdout.flush()

    npass = sum(1 for _, ok, _, _ in results if ok)
    print(f"\nSCORE: {npass}/{len(results)} surfaced the expected API")
    print("FAILURES:", ", ".join(l for l, ok, _, _ in results if not ok) or "none")
    with open("tools/discoverability_results.json", "w") as f:
        json.dump(dump, f, indent=2)
    print("full responses -> tools/discoverability_results.json")


if __name__ == "__main__":
    import urllib.parse  # noqa
    main()
