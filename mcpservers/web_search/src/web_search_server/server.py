"""Web Search MCP Server implementation.

Provides the MCP protocol interface over stdio, registers web search and vocabulary
tools, and manages clean diagnostic logging.
"""

from __future__ import annotations

import asyncio
import logging
import sys

# Windows selector loop compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    from mcp.server.mcpserver import MCPServer  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp 1.x

from web_search_server.config import get_masked_api_key, get_settings
from web_search_server.tools import register_all_tools


def configure_logging() -> None:
    """Direct all diagnostic and operational logs to stderr.

    CRITICAL: Never write unstructured text to stdout, as stdout is dedicated
    exclusively to MCP JSON-RPC protocol frames.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [web-search-mcp] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)


def create_server() -> MCPServer:
    """Create and configure the Web Search MCPServer instance."""
    server = MCPServer("WebSearch")
    register_all_tools(server)
    return server


async def run_server() -> None:
    """Run the Web Search MCP Server with graceful lifecycle management."""
    configure_logging()
    logger = logging.getLogger("web_search_server")
    logger.info("Starting Web Search MCP Server (Tavily)...")
    logger.info("Tavily API key loaded: %s", get_masked_api_key())

    # Pre-validate settings at startup
    get_settings()

    server = create_server()

    try:
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
        logger.info("Web Search MCP Server shut down cleanly.")


def main() -> None:
    """CLI entry point for running the Web Search MCP Server."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

