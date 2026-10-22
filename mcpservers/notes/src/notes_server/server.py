"""Notes MCP Server implementation.

Provides the MCP protocol interface over stdio, registers the 11 knowledge
tools, and manages clean database connection lifecycles.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

# On Windows, psycopg async operations require WindowsSelectorEventLoopPolicy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Backward and forward compatibility for MCP SDK versions
try:
    from mcp.server.mcpserver import MCPServer  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp 1.x

from notes_server.config import get_masked_db_url, get_settings
from notes_server.database import db_manager
from notes_server.tools import register_all_tools


def configure_logging() -> None:
    """Direct all diagnostic and operational logs to stderr.

    CRITICAL: Never write unstructured text to stdout, as stdout is dedicated
    exclusively to MCP JSON-RPC protocol frames.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)

    # Format logs cleanly for stderr
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [notes-mcp] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing stdout handlers if present
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)


def create_server() -> MCPServer:
    """Create and configure the Notes MCPServer instance."""
    server = MCPServer("Notes")
    register_all_tools(server)
    return server


async def run_server() -> None:
    """Run the Notes MCP Server with graceful lifecycle management."""
    configure_logging()
    logger = logging.getLogger("notes_server")
    logger.info("Starting Notes MCP Server...")
    logger.info("Using PostgreSQL at: %s", get_masked_db_url())

    server = create_server()

    try:
        # Run stdio transport loop
        if hasattr(server, "run_stdio_async"):
            await server.run_stdio_async()
        else:
            server.run(transport="stdio")
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown signal received.")
    except Exception as exc:
        logger.error("Server execution error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Cleaning up database pool...")
        await db_manager.close()
        logger.info("Notes MCP Server shut down cleanly.")


def main() -> None:
    """CLI entry point for running the Notes MCP Server."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

