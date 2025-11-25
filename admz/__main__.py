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

    args = parser.parse_args()

    if args.command == "api":
        run_api_server(args)
    elif args.command == "mcp":
        run_mcp_server()
    else:
        parser.print_help()
        sys.exit(1)


def run_api_server(args):
    """Run FastAPI REST API server."""
    try:
        import uvicorn
        from admz.api.app import app
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
        "admz.api.app:app",
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


if __name__ == "__main__":
    main()
