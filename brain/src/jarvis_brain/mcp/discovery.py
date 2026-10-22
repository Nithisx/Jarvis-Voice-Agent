"""Tool discovery and adapter converting MCP tools to LangChain BaseTools."""

from __future__ import annotations

import json
from typing import Any, Callable, Coroutine, Optional

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

from jarvis_brain.agent.policies import sanitize_untrusted_content
from jarvis_brain.observability.logging import get_logger

logger = get_logger("mcp.discovery")


class MCPToolAdapter(BaseTool):
    """LangChain BaseTool adapter that routes invocations to an MCP ClientSession."""
    name: str
    description: str
    server_name: str
    call_fn: Any  # Async callable (name: str, arguments: dict) -> str

    def _run(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("MCP tools only support asynchronous execution (_arun).")

    async def _arun(self, **kwargs: Any) -> str:
        logger.info("Executing MCP tool [%s:%s] with arguments: %s", self.server_name, self.name, list(kwargs.keys()))
        try:
            result_str = await self.call_fn(self.name, kwargs)
            # If from web_search, sanitize output to protect against prompt injection
            if self.server_name == "web_search":
                result_str = sanitize_untrusted_content(result_str, source="web_search")
            return result_str
        except Exception as exc:
            logger.error("Error executing MCP tool [%s:%s]: %s", self.server_name, self.name, exc)
            return f"Error executing tool '{self.name}': {exc}"


def create_langchain_tool_from_mcp(
    mcp_tool: Any,
    server_name: str,
    call_coroutine: Callable[[str, dict[str, Any]], Coroutine[Any, Any, str]],
) -> BaseTool:
    """Convert an MCP protocol Tool object into a LangChain BaseTool."""
    tool_name = mcp_tool.name
    tool_desc = mcp_tool.description or f"MCP tool '{tool_name}' on server '{server_name}'"

    return MCPToolAdapter(
        name=tool_name,
        description=tool_desc,
        server_name=server_name,
        call_fn=call_coroutine,
    )

