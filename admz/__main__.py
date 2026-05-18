#!/usr/bin/env python3
"""
ADMZ CLI entry point.

Supports both FastAPI server and MCP server modes.

Usage:
    python -m admz api [--host 0.0.0.0] [--port 8000]  # Start FastAPI server
    python -m admz mcp                                  # Start MCP server
    python -m admz --help                               # Show help
"""

import argparse
import asyncio
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
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    api_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
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

    args = parser.parse_args()

    if args.command == "api":
        run_api_server(args)
    elif args.command == "mcp":
        run_mcp_server()
    elif args.command == "discover":
        run_discover(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_api_server(args):
    """Run FastAPI REST API server."""
    from admz.logging_config import configure_logging
    configure_logging()
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
