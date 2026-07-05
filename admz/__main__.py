#!/usr/bin/env python3
"""
ADMZ CLI entry point.

Supports both FastAPI server and MCP server modes.

Usage:
    python -m admz api [--host 127.0.0.1] [--port 4242]  # Start FastAPI server
    python -m admz mcp                                    # Start MCP server
    python -m admz --help                                 # Show help
"""

import argparse
import asyncio
import os
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ADMZ (Axis Device Manager) - Device credential management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # API server command
    api_parser = subparsers.add_parser(
        "api",
        help="Start FastAPI REST API server",
    )
    api_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "Host to bind to (default: 127.0.0.1 — localhost only). "
            "Pass 0.0.0.0 explicitly to expose on all interfaces. "
            "Phase 4 added auth (see ADMZ_AUTH_BACKEND): under the "
            "default 'none' backend, every request is anonymous and "
            "five destructive endpoints refuse it; under 'windows' or "
            "'composite' the startup bind-safety check refuses to bind "
            "to anything other than localhost without a trusted reverse "
            "proxy in front. Override via ADMZ_AUTH_INSECURE_BIND_OK=true."
        ),
    )
    api_parser.add_argument(
        "--port",
        type=int,
        default=4242,
        help="Port to bind to (default: 4242)",
    )
    api_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    # MCP server command
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Start MCP (Model Context Protocol) server",
    )

    # Discovery command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover devices on the local network",
    )
    discover_parser.add_argument(
        "--timeout", type=float, default=5.0,
        help="Per-protocol timeout in seconds (default: 5.0)",
    )
    discover_parser.add_argument(
        "--axis-only", action="store_true",
        help="Only show Axis devices",
    )
    discover_parser.add_argument(
        "--subnet", type=str, default=None,
        help="Subnet for ARP scan (CIDR, e.g. 192.168.1.0/24)",
    )
    discover_parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    discover_parser.add_argument(
        "--no-mdns", action="store_true",
        help="Disable mDNS discovery",
    )
    discover_parser.add_argument(
        "--no-ssdp", action="store_true",
        help="Disable SSDP discovery",
    )
    discover_parser.add_argument(
        "--no-onvif", action="store_true",
        help="Disable ONVIF discovery",
    )
    discover_parser.add_argument(
        "--no-arp", action="store_true",
        help="Disable ARP scanning",
    )
    discover_parser.add_argument(
        "--enable-ping", action="store_true",
        help="Enable ping sweep (disabled by default)",
    )
    discover_parser.add_argument(
        "--no-http", action="store_true",
        help="Disable HTTP/VAPIX probing",
    )
    discover_parser.add_argument(
        "--no-snmp", action="store_true",
        help="Disable SNMP enrichment",
    )
    discover_parser.add_argument(
        "--snmp-community", type=str, default="public",
        help="SNMP community string (default: public)",
    )

    # API-key management command
    apikey_parser = subparsers.add_parser(
        "api-key",
        help="Manage API keys for programmatic clients",
    )
    apikey_sub = apikey_parser.add_subparsers(
        dest="apikey_command", help="API-key subcommand"
    )

    apikey_create = apikey_sub.add_parser(
        "create",
        help="Mint a new API key (the plaintext is shown ONCE)",
    )
    apikey_create.add_argument(
        "--name", required=True,
        help="Human-readable display name (e.g. 'nightly-bot')",
    )
    apikey_create.add_argument(
        "--created-by", default=None,
        help="Audit label for the creator (defaults to OS username + ':cli')",
    )
    apikey_create.add_argument(
        "--expires-in-days", type=int, default=None,
        help="Optional expiry in days from now",
    )

    apikey_list = apikey_sub.add_parser(
        "list", help="List API keys"
    )
    apikey_list.add_argument(
        "--include-revoked", action="store_true",
        help="Include revoked keys in the output",
    )
    apikey_list.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of a human-readable table",
    )

    apikey_revoke = apikey_sub.add_parser(
        "revoke", help="Revoke an API key by id"
    )
    apikey_revoke.add_argument("id", type=int, help="The key's numeric id")

    # Snapshot-repo maintenance command (Phase 6)
    maint_parser = subparsers.add_parser(
        "maintenance",
        help="Snapshot-repo maintenance (size report + git gc)",
    )
    maint_sub = maint_parser.add_subparsers(
        dest="maint_command", help="Maintenance subcommand"
    )
    maint_stats = maint_sub.add_parser(
        "stats", help="Print repo disk usage and commit count"
    )
    maint_stats.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    maint_gc = maint_sub.add_parser(
        "gc",
        help="Pack loose git objects (non-destructive; never drops commits)",
    )
    maint_gc.add_argument(
        "--aggressive", action="store_true",
        help="Slower but tighter pack (--aggressive). Run weekly at most.",
    )
    maint_gc.add_argument(
        "--json", action="store_true", help="Output as JSON",
    )
    maint_migrate = maint_sub.add_parser(
        "migrate",
        help=(
            "Backfill the hierarchy on existing devices: assigns every "
            "device lacking org_id/site_id to the default Org/Site. "
            "Idempotent — safe to re-run."
        ),
    )
    maint_migrate.add_argument(
        "--dry-run", action="store_true",
        help="Print what would change without writing.",
    )
    maint_migrate.add_argument(
        "--json", action="store_true", help="Output as JSON",
    )

    args = parser.parse_args()

    if args.command == "api":
        run_api_server(args)
    elif args.command == "mcp":
        run_mcp_server()
    elif args.command == "api-key":
        run_api_key(args)
    elif args.command == "discover":
        run_discover(args)
    elif args.command == "maintenance":
        run_maintenance(args)
    else:
        parser.print_help()
        sys.exit(1)


def _check_bind_safety(host: str) -> None:
    """Refuse to start with a permissive bind address when the auth
    backend trusts a forwarded REMOTE_USER header.

    ADMZ trusts ``REMOTE_USER`` only when the request reaches uvicorn
    from a configured trusted-proxy IP. If uvicorn binds to anything
    other than localhost, an attacker on the network could connect
    directly and spoof the header, bypassing auth entirely. The
    reverse-proxy backend mitigates this with a trusted_proxies check,
    but a misconfiguration there is silent. This check makes it loud.

    The override is intentional and rare — set
    ``ADMZ_AUTH_INSECURE_BIND_OK=true`` only if you have an unusual
    network setup (e.g. listening on a private internal NIC reachable
    only by the reverse proxy).
    """
    backend = (os.getenv("ADMZ_AUTH_BACKEND", "none") or "none").lower()
    if backend not in ("windows", "composite"):
        return  # API-key or NoAuth modes don't trust forwarded headers
    if host in ("127.0.0.1", "::1", "localhost"):
        return
    if os.getenv("ADMZ_AUTH_INSECURE_BIND_OK", "").lower() in ("1", "true", "yes"):
        print(
            f"WARNING: ADMZ_AUTH_BACKEND={backend} with --host {host} — "
            "header-spoofing risk acknowledged via ADMZ_AUTH_INSECURE_BIND_OK.",
            file=sys.stderr,
        )
        return
    print(
        f"\nRefusing to start with ADMZ_AUTH_BACKEND={backend} and "
        f"--host {host}.\n\n"
        "The reverse-proxy auth backend trusts a forwarded REMOTE_USER "
        "header. If uvicorn is reachable from anywhere besides localhost, "
        "an attacker can spoof the header and bypass authentication.\n\n"
        "Fix one of:\n"
        "  1. Bind uvicorn to 127.0.0.1 (the secure default) and put a "
        "reverse proxy in front of it.\n"
        "  2. If you have an unusual network setup that's genuinely "
        "safe, set ADMZ_AUTH_INSECURE_BIND_OK=true to override.\n"
        "  3. Switch to a different auth backend (e.g. ADMZ_AUTH_BACKEND=api-key) "
        "that doesn't rely on forwarded headers.\n",
        file=sys.stderr,
    )
    sys.exit(2)


def run_api_key(args):
    """Manage API keys from the CLI.

    The CLI is intended for operators with shell access to the ADMZ
    host — typically the same person who runs ``python -m admz api``.
    For routine key management by an authenticated web user, the
    REST endpoints under ``/api/api-keys`` are the right surface.
    """
    import getpass
    import json as json_mod
    import time
    from datetime import datetime

    sub = getattr(args, "apikey_command", None)
    if not sub:
        print(
            "Usage: python -m admz api-key {create,list,revoke} ...",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from admz.api_keys import ApiKeyStore
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    store = ApiKeyStore()

    if sub == "create":
        created_by = args.created_by or f"{getpass.getuser()}:cli"
        expires_at = None
        if args.expires_in_days is not None:
            expires_at = time.time() + (args.expires_in_days * 86400)
        try:
            created = store.create(
                display_name=args.name,
                created_by=created_by,
                expires_at=expires_at,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"\nAPI key created (id={created.record.id}, name={args.name!r})")
        print(f"Created by: {created_by}")
        if expires_at:
            print(f"Expires:    {datetime.fromtimestamp(expires_at).isoformat()}")
        print("\n  ┌─────────────────────────────────────────────────────────")
        print(f"  │ {created.plaintext}")
        print("  └─────────────────────────────────────────────────────────\n")
        print("This is the ONLY time the plaintext will be shown.")
        print("Copy it now and store it where your agent can read it.")
        return

    if sub == "list":
        keys = store.list(include_revoked=args.include_revoked)
        if args.json:
            print(json_mod.dumps([
                {
                    "id": k.id,
                    "display_name": k.display_name,
                    "created_by": k.created_by,
                    "created_at": k.created_at,
                    "expires_at": k.expires_at,
                    "last_used_at": k.last_used_at,
                    "revoked": k.revoked,
                }
                for k in keys
            ], indent=2))
            return

        if not keys:
            print("(no API keys)")
            return

        header = f"{'ID':<5} {'NAME':<30} {'CREATED BY':<30} {'LAST USED':<20} {'STATE'}"
        print(header)
        print("-" * len(header))
        for k in keys:
            last_used = (
                datetime.fromtimestamp(k.last_used_at).isoformat(timespec="seconds")
                if k.last_used_at else "never"
            )
            state = "revoked" if k.revoked else (
                "expired" if k.is_expired else "active"
            )
            name = (k.display_name[:27] + "...") if len(k.display_name) > 30 else k.display_name
            cb = (k.created_by[:27] + "...") if len(k.created_by) > 30 else k.created_by
            print(f"{k.id:<5} {name:<30} {cb:<30} {last_used:<20} {state}")
        return

    if sub == "revoke":
        if store.revoke(args.id):
            print(f"Revoked API key {args.id}.")
        else:
            print(
                f"API key {args.id} not found or already revoked.",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    print(f"Unknown api-key subcommand: {sub}", file=sys.stderr)
    sys.exit(1)


def run_api_server(args):
    """Run FastAPI REST API server."""
    import os  # noqa: F811 — re-import in case caller didn't
    from admz.logging_config import configure_logging
    configure_logging()

    _check_bind_safety(args.host)

    # Propagate the live bind address to the MCP subprocess so the
    # capture/confirm URLs the LLM hands the user point at the actual
    # running server. Without this, the MCP-side default of
    # http://localhost:4242 is used — which is right for the common
    # case but wrong if the operator binds to a non-default port.
    # Only set when not already configured (operator-supplied
    # ADMZ_BASE_URL — e.g. the public IIS URL — wins).
    if not os.getenv("ADMZ_BASE_URL"):
        host_for_url = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
        os.environ["ADMZ_BASE_URL"] = f"http://{host_for_url}:{args.port}"

    try:
        import uvicorn
        from admz.api.main import app
    except ImportError as e:
        print(
            f"Error: Missing dependencies for API server: {e}\n"
            "Install with: pip install uvicorn fastapi",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting ADMZ API server on {args.host}:{args.port}")
    print(f"API documentation: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "admz.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def run_mcp_server():
    """Run MCP server."""
    try:
        from admz.mcp.server import main as mcp_main
    except ImportError as e:
        print(
            f"Error: Missing dependencies for MCP server: {e}\n"
            "Install with: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Starting ADMZ MCP server...", file=sys.stderr)
    print("MCP server ready for connections", file=sys.stderr)

    try:
        asyncio.run(mcp_main())
    except KeyboardInterrupt:
        print("\nMCP server stopped", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_maintenance(args):
    """Snapshot-repo maintenance — stats + optional gc."""
    from admz.snapshot.git_repo import GitRepo
    from admz.snapshot.maintenance import (
        get_repo_stats,
        run_gc,
    )

    from admz.paths import config_repo_dir
    repo_path = str(config_repo_dir())

    if args.maint_command == "stats" or args.maint_command is None:
        try:
            repo = GitRepo(repo_path)
        except Exception as exc:
            print(f"Error: cannot open repo {repo_path}: {exc}", file=sys.stderr)
            sys.exit(1)
        stats = get_repo_stats(repo)
        if args.maint_command == "stats" and getattr(args, "json", False):
            import json as _json
            print(_json.dumps(stats.to_dict(), indent=2))
        else:
            print(f"Repo:       {stats.repo_path}")
            print(f"Total:      {stats.total_mb:.2f} MB")
            print(f"  .git:     {stats.git_mb:.2f} MB")
            print(
                f"  fleet:    {stats.fleet_bytes / (1024 * 1024):.2f} MB"
            )
            print(f"Commits:    {stats.commit_count}")
            if stats.oldest_commit_iso:
                print(f"Oldest:     {stats.oldest_commit_iso}")
            if stats.newest_commit_iso:
                print(f"Newest:     {stats.newest_commit_iso}")
        return

    if args.maint_command == "gc":
        try:
            repo = GitRepo(repo_path)
        except Exception as exc:
            print(f"Error: cannot open repo {repo_path}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(
            f"Running git gc{'(aggressive)' if args.aggressive else ''} on {repo_path}…"
        )
        result = run_gc(repo, aggressive=args.aggressive)
        if args.json:
            import json as _json
            print(_json.dumps(result.to_dict(), indent=2))
        elif result.ran:
            print(
                f"Done. {result.before_bytes / (1024*1024):.2f} MB → "
                f"{result.after_bytes / (1024*1024):.2f} MB "
                f"(saved {result.saved_mb:.2f} MB)"
            )
        else:
            print(f"gc did not run: {result.error}", file=sys.stderr)
            sys.exit(1)
        return

    if args.maint_command == "migrate":
        from admz.migrations import migrate_hierarchy_backfill
        from admz.factory import create_device_registry

        registry = create_device_registry()
        # Ensure the default Org/Site/Group rows exist before
        # backfilling devices into them.
        from admz.components import _bootstrap_default_hierarchy
        from admz.paths import config_repo_dir
        _bootstrap_default_hierarchy(registry, str(config_repo_dir()))

        result = migrate_hierarchy_backfill(
            registry, dry_run=args.dry_run,
        )

        if args.json:
            import json as _json
            print(_json.dumps(result, indent=2))
        else:
            mode = "DRY-RUN — no changes" if args.dry_run else "applied"
            print(f"Hierarchy backfill ({mode}):")
            print(f"  devices total:          {result['devices_total']}")
            print(f"  already migrated:       {result['already_migrated']}")
            print(f"  backfilled:             {result['backfilled']}")
            print(f"  primary-group assigned: {result['primary_assigned']}")
        return

    print(
        "Unknown maintenance subcommand. Try 'stats', 'gc', or 'migrate'.",
        file=sys.stderr,
    )
    sys.exit(1)


def run_discover(args):
    """Run network device discovery."""
    try:
        from admz.discovery import discover_devices
    except ImportError as e:
        print(
            f"Error: Missing dependencies for discovery: {e}\n"
            "Install with: pip install zeroconf",
            file=sys.stderr,
        )
        sys.exit(1)

    devices = asyncio.run(
        discover_devices(
            timeout=args.timeout,
            axis_only=args.axis_only,
            subnet=args.subnet,
            enable_mdns=not args.no_mdns,
            enable_ssdp=not args.no_ssdp,
            enable_onvif=not args.no_onvif,
            enable_arp=not args.no_arp,
            enable_ping=args.enable_ping,
            enable_http_probe=not args.no_http,
            enable_snmp=not args.no_snmp,
            snmp_community=args.snmp_community,
        )
    )

    if args.json:
        import json
        print(json.dumps([d.to_registry_dict() for d in devices], indent=2))
    else:
        if not devices:
            print("No devices found.")
            return

        # Print human-readable table
        header = f"{'IP Address':<17} {'MAC Address':<19} {'Model':<20} {'Type':<12} {'Protocols'}"
        print(header)
        print("-" * len(header))
        for d in devices:
            ip = d.ip_address or ""
            mac = d.mac_address or ""
            model = d.model or ""
            dtype = d.device_type.value
            protocols = ", ".join(p.value for p in d.discovered_by)
            # Truncate long model names
            if len(model) > 20:
                model = model[:17] + "..."
            print(f"{ip:<17} {mac:<19} {model:<20} {dtype:<12} {protocols}")

        print(f"\n{len(devices)} device(s) found.")


if __name__ == "__main__":
    main()
