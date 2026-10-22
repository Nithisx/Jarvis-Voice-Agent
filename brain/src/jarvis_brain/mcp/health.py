"""Health checking utilities for connected MCP servers."""

from __future__ import annotations

from typing import Any
from jarvis_brain.observability.logging import get_logger

logger = get_logger("mcp.health")


async def check_server_health(client_manager: Any) -> dict[str, Any]:
    """Check availability and tool counts of all registered MCP servers."""
    results: dict[str, Any] = {}
    for server_name in client_manager.server_names:
        try:
            tools = await client_manager.get_server_tools(server_name)
            results[server_name] = {
                "healthy": True,
                "tool_count": len(tools),
                "tools": [t.name for t in tools],
            }
        except Exception as exc:
            logger.warning("Health probe failed for server '%s': %s", server_name, exc)
            results[server_name] = {
                "healthy": False,
                "error": str(exc),
            }
    return results

