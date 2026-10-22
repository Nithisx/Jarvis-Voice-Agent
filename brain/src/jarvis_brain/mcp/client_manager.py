"""Manages long-lived MCP client sessions, tool discovery, and lifecycle."""

from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Optional

from langchain_core.tools import BaseTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from jarvis_brain.exceptions import MCPConnectionError, MCPToolExecutionError
from jarvis_brain.mcp.config_loader import MCPServerConfig, load_mcp_servers_config
from jarvis_brain.mcp.discovery import create_langchain_tool_from_mcp
from jarvis_brain.observability.logging import get_logger

logger = get_logger("mcp.manager")


class MCPClientManager:
    """Manages stdio client sessions and tool discovery for all registered MCP servers."""

    def __init__(self, configs: Optional[dict[str, MCPServerConfig]] = None) -> None:
        self.configs = configs or load_mcp_servers_config()
        self._exit_stack: Optional[AsyncExitStack] = None
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[BaseTool] = []
        self._lock = asyncio.Lock()
        self._is_connected = False

    @property
    def server_names(self) -> list[str]:
        return list(self.configs.keys())

    async def connect_all(self) -> None:
        """Launch and connect to all enabled MCP servers over stdio."""
        async with self._lock:
            if self._is_connected:
                return

            self._exit_stack = AsyncExitStack()
            self._sessions.clear()
            self._tools.clear()

            logger.info("Connecting to %d configured MCP server(s)...", len(self.configs))

            for name, cfg in self.configs.items():
                logger.info("Initializing connection to MCP server [%s] via stdio...", name)
                params = StdioServerParameters(
                    command=cfg.command,
                    args=cfg.args,
                    env=cfg.env,
                    cwd=str(cfg.working_dir),
                )

                try:
                    read_stream, write_stream = await self._exit_stack.enter_async_context(
                        stdio_client(params)
                    )
                    session = await self._exit_stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    await session.initialize()
                    self._sessions[name] = session

                    # Discover registered tools
                    tools_resp = await session.list_tools()
                    mcp_tools = tools_resp.tools
                    logger.info("Discovered %d tool(s) from MCP server [%s].", len(mcp_tools), name)

                    # Create call wrapper for this server's session
                    for t in mcp_tools:
                        call_wrapper = self._create_call_wrapper(session, name)
                        lc_tool = create_langchain_tool_from_mcp(t, name, call_wrapper)
                        self._tools.append(lc_tool)

                except Exception as exc:
                    logger.error("Failed to connect to MCP server [%s]: %s", name, exc)
                    await self._exit_stack.aclose()
                    self._exit_stack = None
                    self._sessions.clear()
                    self._tools.clear()
                    raise MCPConnectionError(f"Could not connect to MCP server '{name}': {exc}") from exc

            self._is_connected = True
            logger.info("All MCP servers successfully connected. Total tools: %d", len(self._tools))

    def _create_call_wrapper(self, session: ClientSession, server_name: str) -> Any:
        async def _call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> str:
            try:
                res = await session.call_tool(tool_name, arguments)
                texts: list[str] = []
                for item in res.content:
                    if hasattr(item, "text"):
                        texts.append(item.text)
                    elif isinstance(item, str):
                        texts.append(item)
                    else:
                        texts.append(str(item))

                return "\n".join(texts) if texts else "Tool executed successfully with empty response."
            except Exception as exc:
                logger.error("Failed executing tool [%s:%s]: %s", server_name, tool_name, exc)
                raise MCPToolExecutionError(f"Tool execution failed on server '{server_name}': {exc}") from exc

        return _call_mcp_tool

    def get_tools(self) -> list[BaseTool]:
        """Return all discovered LangChain BaseTool instances."""
        return self._tools

    def get_all_tools(self) -> list[BaseTool]:
        """Alias for get_tools returning all registered LangChain BaseTool instances."""
        return self._tools

    async def get_server_tools(self, server_name: str) -> list[Any]:
        """Fetch raw MCP tools for a specific server."""
        session = self._sessions.get(server_name)
        if not session:
            raise MCPConnectionError(f"Server '{server_name}' is not connected.")
        res = await session.list_tools()
        return res.tools

    async def close(self) -> None:
        """Gracefully terminate all MCP client sessions and child processes."""
        async with self._lock:
            if self._exit_stack:
                logger.info("Closing all MCP server sessions and child processes...")
                try:
                    await self._exit_stack.aclose()
                except Exception as exc:
                    logger.warning("Error during MCP exit stack close: %s", exc)
                self._exit_stack = None
            self._sessions.clear()
            self._tools.clear()
            self._is_connected = False
            logger.info("All MCP client sessions closed.")


# Singleton manager
mcp_client_manager = MCPClientManager()
