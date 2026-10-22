"""Tests for search_web tool and Tavily provider search operations."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError as PydanticValidationError
from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError, TimeoutError as TavilyTimeoutErr

from web_search_server.exceptions import (
    TavilyAuthError,
    TavilyRateLimitError,
    TavilyTimeoutError,
    ValidationError,
)
from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.tools.search_web import handle_search_web


@pytest.mark.asyncio
async def test_search_web_success(mock_provider: TavilyProvider):
    """Verify successful search returns structured results."""
    resp = await handle_search_web(
        query="learning English idioms",
        search_depth="basic",
        topic="general",
        max_results=2,
        provider=mock_provider,
    )

    assert resp["success"] is True
    assert resp["total_results"] == 2
    assert len(resp["results"]) == 2
    first_item = resp["results"][0]
    assert first_item["title"] == "Cambridge Dictionary: Serendipity"
    assert first_item["url"].startswith("https://")
    assert "Serendipity" in first_item["content"]
    assert first_item["score"] == 0.95


@pytest.mark.asyncio
async def test_search_web_empty_results(mock_tavily_client: AsyncMock):
    """Verify empty search results return a clean, helpful message."""
    mock_tavily_client.search.return_value = {"query": "nonexistent terms", "results": []}
    provider = TavilyProvider(client=mock_tavily_client)

    resp = await handle_search_web(
        query="nonexistent terms",
        provider=provider,
    )

    assert resp["success"] is True
    assert resp["total_results"] == 0
    assert resp["results"] == []
    assert "No relevant search results found" in resp["message"]


@pytest.mark.asyncio
async def test_search_web_bounds_max_results(mock_tavily_client: AsyncMock):
    """Verify max_results is bounded to maximum 10."""
    provider = TavilyProvider(client=mock_tavily_client)

    # Calling with max_results=50 should fail validation
    with pytest.raises(PydanticValidationError):
        await handle_search_web(
            query="test query",
            max_results=50,
            provider=provider,
        )


@pytest.mark.asyncio
async def test_search_web_invalid_inputs(mock_provider: TavilyProvider):
    """Verify validation errors on empty query or invalid enum parameters."""
    # Empty query
    with pytest.raises(PydanticValidationError):
        await handle_search_web(query="   ", provider=mock_provider)

    # Invalid search_depth
    with pytest.raises(PydanticValidationError):
        await handle_search_web(query="valid query", search_depth="super_deep", provider=mock_provider)

    # Invalid topic
    with pytest.raises(PydanticValidationError):
        await handle_search_web(query="valid query", topic="finance_invalid", provider=mock_provider)


@pytest.mark.asyncio
async def test_search_web_authentication_error(mock_tavily_client: AsyncMock):
    """Verify InvalidAPIKeyError maps to TavilyAuthError without exposing credentials."""
    mock_tavily_client.search.side_effect = InvalidAPIKeyError("Invalid API key provided: tvly-secret-12345")
    provider = TavilyProvider(client=mock_tavily_client)

    with pytest.raises(TavilyAuthError) as exc_info:
        await handle_search_web(query="test", provider=provider)

    # Ensure secret is not in the raised exception message
    assert "tvly-secret-12345" not in str(exc_info.value)
    assert "authentication failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_search_web_rate_limit_error(mock_tavily_client: AsyncMock):
    """Verify UsageLimitExceededError maps to TavilyRateLimitError."""
    mock_tavily_client.search.side_effect = UsageLimitExceededError("Monthly credit limit exceeded.")
    provider = TavilyProvider(client=mock_tavily_client)

    with pytest.raises(TavilyRateLimitError):
        await handle_search_web(query="test", provider=provider)


@pytest.mark.asyncio
async def test_search_web_timeout_error(mock_tavily_client: AsyncMock):
    """Verify timeout exception maps to TavilyTimeoutError."""
    mock_tavily_client.search.side_effect = TavilyTimeoutErr("Request timed out.")
    provider = TavilyProvider(client=mock_tavily_client)

    with pytest.raises(TavilyTimeoutError):
        await handle_search_web(query="test", provider=provider)

