"""Tiny HTTP recipient for live-testing device notification rules.

Run this on the ADMZ host, point an Axis `notification.http` (or `send_*`)
action rule at it, and every delivery is printed here — method, path, query,
client IP, headers, decoded Basic-auth **login/password**, and body. That lets
you confirm end-to-end that a device actually delivers a notification AND that
the recipient credentials captured via ADMZ's secure form arrived intact.

    python tools/rule_notify_listener.py            # listen on 0.0.0.0:8099
    python tools/rule_notify_listener.py --port 9000

It binds to 0.0.0.0 so a camera on the LAN can reach it, and prints the exact
recipient URL to use. Always returns 200 OK.

LAB/TEST ONLY. It echoes the credentials it receives to the console on purpose
(that is the whole point of the test) — do not expose it to an untrusted
network, and use a throwaway test password, never a real one. On Windows you may
get a Firewall prompt the first time a LAN device connects; allow it (Private
networks) so the camera can reach the port.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_COUNT = 0


def _local_ip() -> str:
    """Best-effort primary LAN IP (no traffic actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _decode_basic(auth_header: str) -> str:
    """Turn 'Basic base64(user:pass)' into 'user:pass' (or a note)."""
    if not auth_header:
        return "(none — recipient sent no credentials)"
    parts = auth_header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "basic":
        try:
            return base64.b64decode(parts[1]).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return f"(unparseable Basic value: {parts[1]!r})"
    return f"({auth_header})"  # Digest / Bearer / etc. — show raw scheme


CHALLENGE = False  # set by --challenge: 401 unauthenticated requests so the
                   # sender retries WITH Basic credentials (they aren't sent
                   # preemptively).


class _Handler(BaseHTTPRequestHandler):
    # Silence the default per-request access log; we print our own.
    def log_message(self, *args):  # noqa: D401
        return

    def _dump(self, method: str) -> None:
        global _COUNT
        _COUNT += 1
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        auth = self.headers.get("Authorization", "")
        now = datetime.datetime.now().strftime("%H:%M:%S")
        line = "=" * 72

        # If challenge mode is on and no credentials were sent, reply 401 so the
        # client retries with Basic auth. Log it but keep it brief.
        if CHALLENGE and not auth:
            print(f"\n{line}\n#{_COUNT}  {now}  {method} {self.path}"
                  f"   from {self.client_address[0]}"
                  f"\n  -> 401 challenge (no credentials yet; awaiting retry)",
                  flush=True)
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="admz-test"')
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"auth required\n")
            return

        print(f"\n{line}\n#{_COUNT}  {now}  {method} {self.path}"
              f"   from {self.client_address[0]}")
        print(f"  AUTH: {_decode_basic(auth)}")
        print("  HEADERS:")
        for k, v in self.headers.items():
            print(f"    {k}: {v}")
        if body:
            shown = body.decode("utf-8", "replace")
            print(f"  BODY ({len(body)} bytes):\n    "
                  + shown.replace("\n", "\n    "))
        else:
            print("  BODY: (empty)")
        print(line, flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ADMZ notify listener OK\n")

    def do_GET(self):
        self._dump("GET")

    def do_POST(self):
        self._dump("POST")

    def do_PUT(self):
        self._dump("PUT")


def main() -> None:
    ap = argparse.ArgumentParser(description="HTTP recipient for notification-rule testing")
    ap.add_argument("--host", default="0.0.0.0", help="bind address (default 0.0.0.0)")
    ap.add_argument("--port", type=int, default=8099, help="port (default 8099)")
    ap.add_argument("--challenge", action="store_true",
                    help="401 unauthenticated requests so the sender retries "
                         "with Basic credentials (proves the recipient creds).")
    args = ap.parse_args()

    global CHALLENGE
    CHALLENGE = args.challenge
    ip = _local_ip()
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print("ADMZ notification-rule listener")
    print(f"  listening on {args.host}:{args.port}")
    print(f"  give this URL as the recipient:  http://{ip}:{args.port}/notify")
    print("  (Ctrl-C to stop; waiting for deliveries...)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
