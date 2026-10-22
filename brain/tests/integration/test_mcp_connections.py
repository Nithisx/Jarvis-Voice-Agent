"""Integration test for MCP client manager connecting to Notes and Web Search servers."""

import asyncio
import sys
import pytest

from jarvis_brain.mcp.client_manager import mcp_client_manager


@pytest.mark.asyncio
async def test_mcp_servers_connection_and_discovery():
    """Verify both Notes and Web Search MCP servers launch over stdio and expose their tools."""
    try:
        await mcp_client_manager.connect_all()
        tools = mcp_client_manager.get_all_tools()

        assert len(tools) >= 14  # 11 notes tools + 3 web search tools

        tool_names = {t.name for t in tools}

        # Notes tools
        assert "create_note" in tool_names
        assert "search_notes" in tool_names
        assert "save_vocabulary" in tool_names

        # Web search tools
        assert "search_web" in tool_names
        assert "get_page_content" in tool_names
        assert "find_vocabulary" in tool_names

    finally:
        await mcp_client_manager.close()

