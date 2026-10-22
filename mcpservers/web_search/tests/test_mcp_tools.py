"""Tests for MCP server tool registration, invocation, and missing configuration."""

from __future__ import annotations

import os
import pytest

from web_search_server.config import clear_settings_cache, get_settings
from web_search_server.exceptions import ConfigurationError
from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.server import create_server
from web_search_server.tools import search_web as sw_mod
from web_search_server.tools import get_page_content as gpc_mod
from web_search_server.tools import find_vocabulary as fv_mod


@pytest.mark.asyncio
async def test_mcp_server_registers_all_three_tools():
    """Verify all 3 required tools are registered with MCPServer."""
    server = create_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {"search_web", "get_page_content", "find_vocabulary"}
    assert expected_tools == tool_names
    assert len(tools) == 3


@pytest.mark.asyncio
async def test_mcp_call_tool_via_server(mock_provider: TavilyProvider):
    """Verify tool invocation through MCPServer.call_tool()."""
    # Temporarily patch default provider
    orig_sw = sw_mod._DEFAULT_PROVIDER
    orig_gpc = gpc_mod._DEFAULT_PROVIDER
    orig_fv = fv_mod._DEFAULT_PROVIDER

    sw_mod._DEFAULT_PROVIDER = mock_provider
    gpc_mod._DEFAULT_PROVIDER = mock_provider
    fv_mod._DEFAULT_PROVIDER = mock_provider

    try:
        server = create_server()

        # 1. search_web
        res_search = await server.call_tool("search_web", {"query": "English idioms", "max_results": 2})
        assert getattr(res_search, "is_error", False) is False
        assert res_search is not None

        # 2. get_page_content
        res_extract = await server.call_tool(
            "get_page_content",
            {"url": "https://en.wikipedia.org/wiki/Spaced_repetition", "max_characters": 1000},
        )
        assert getattr(res_extract, "is_error", False) is False
        assert res_extract is not None

        # 3. find_vocabulary
        res_vocab = await server.call_tool("find_vocabulary", {"topic": "leadership", "count": 2})
        assert getattr(res_vocab, "is_error", False) is False
        assert res_vocab is not None
    finally:
        sw_mod._DEFAULT_PROVIDER = orig_sw
        gpc_mod._DEFAULT_PROVIDER = orig_gpc
        fv_mod._DEFAULT_PROVIDER = orig_fv


def test_missing_api_key_raises_clear_error():
    """Verify missing API key fails with ConfigurationError without leaking details."""
    clear_settings_cache()
    old_key = os.environ.pop("TAVILY_API_KEY", None)
    old_key_lower = os.environ.pop("tavily_api_key", None)
    # Also temporarily point WEB_SEARCH_ENV_FILE to nonexistent path
    os.environ["WEB_SEARCH_ENV_FILE"] = "nonexistent.env"

    try:
        with pytest.raises(ConfigurationError) as exc_info:
            get_settings()
        err_msg = str(exc_info.value)
        assert "Missing required Tavily API key" in err_msg
        assert "TAVILY_API_KEY" in err_msg
    finally:
        os.environ.pop("WEB_SEARCH_ENV_FILE", None)
        clear_settings_cache()
        if old_key:
            os.environ["TAVILY_API_KEY"] = old_key
        if old_key_lower:
            os.environ["tavily_api_key"] = old_key_lower


@pytest.mark.skipif(
    os.environ.get("RUN_TAVILY_INTEGRATION_TESTS") != "1",
    reason="Live integration tests disabled by default to prevent credit consumption.",
)
@pytest.mark.asyncio
async def test_live_tavily_integration():
    """Optional live integration test running only when RUN_TAVILY_INTEGRATION_TESTS=1."""
    from web_search_server.config import find_root_env_file, parse_env_file
    from tavily import AsyncTavilyClient

    root_env = find_root_env_file()
    if not root_env:
        pytest.skip("Root .env not found.")
    parsed = parse_env_file(root_env)
    real_key = parsed.get("TAVILY_API_KEY") or parsed.get("tavily_api_key")
    if not real_key or real_key.startswith("tvly-test-mock"):
        pytest.skip("Valid live TAVILY_API_KEY not configured in root .env.")

    client = AsyncTavilyClient(api_key=real_key)
    provider = TavilyProvider(client=client)
    resp = await provider.search(query="Python programming language", max_results=2)
    assert resp.success is True
    assert len(resp.results) > 0
