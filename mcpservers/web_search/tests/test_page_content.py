"""Tests for get_page_content tool and URL security validations."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError as PydanticValidationError

from web_search_server.exceptions import TavilyProviderError, ValidationError
from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.tools.get_page_content import handle_get_page_content


@pytest.mark.asyncio
async def test_get_page_content_success(mock_provider: TavilyProvider):
    """Verify extracting content from a valid public URL."""
    resp = await handle_get_page_content(
        url="https://en.wikipedia.org/wiki/Spaced_repetition",
        max_characters=5000,
        provider=mock_provider,
    )

    assert resp["success"] is True
    assert resp["url"] == "https://en.wikipedia.org/wiki/Spaced_repetition"
    assert "Spaced repetition" in resp["content"]
    assert resp["truncated"] is False
    assert resp["character_count"] > 0


@pytest.mark.asyncio
async def test_get_page_content_truncation(mock_tavily_client: AsyncMock):
    """Verify max_characters limits the returned text and marks truncated=True."""
    long_text = "A" * 1500
    mock_tavily_client.extract.return_value = {
        "results": [{"url": "https://example.com/article", "raw_content": long_text}],
        "failed_results": [],
    }
    provider = TavilyProvider(client=mock_tavily_client)

    resp = await handle_get_page_content(
        url="https://example.com/article",
        max_characters=500,
        provider=provider,
    )

    assert resp["success"] is True
    assert resp["character_count"] == 500
    assert len(resp["content"]) == 500
    assert resp["truncated"] is True


@pytest.mark.asyncio
async def test_get_page_content_rejects_non_http_schemes(mock_provider: TavilyProvider):
    """Verify rejection of file:, javascript:, and other unsupported schemes."""
    invalid_urls = [
        "file:///C:/Windows/System32/drivers/etc/hosts",
        "javascript:alert(1)",
        "ftp://ftp.example.com/file.txt",
        "data:text/plain;base64,SGVsbG8=",
    ]

    for url in invalid_urls:
        with pytest.raises(PydanticValidationError):
            await handle_get_page_content(url=url, provider=mock_provider)


@pytest.mark.asyncio
async def test_get_page_content_rejects_ssrf_and_private_ips(mock_provider: TavilyProvider):
    """Verify strict rejection of localhost, private RFC-1918 subnets, and cloud metadata."""
    forbidden_urls = [
        "http://localhost:8000/api",
        "http://127.0.0.1/admin",
        "http://[::1]/status",
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP metadata
        "http://10.0.0.5/internal",
        "http://192.168.1.100/router",
        "http://172.16.5.10/secrets",
        "http://internal.service.local/db",
    ]

    for url in forbidden_urls:
        with pytest.raises(PydanticValidationError):
            await handle_get_page_content(url=url, provider=mock_provider)


@pytest.mark.asyncio
async def test_get_page_content_extraction_failure(mock_tavily_client: AsyncMock):
    """Verify clear error is returned when page cannot be extracted."""
    mock_tavily_client.extract.return_value = {
        "results": [],
        "failed_results": [{"url": "https://example.com/404", "error": "404 Not Found"}],
    }
    provider = TavilyProvider(client=mock_tavily_client)

    with pytest.raises(TavilyProviderError) as exc_info:
        await handle_get_page_content(
            url="https://example.com/404",
            provider=provider,
        )

    assert "Could not extract content" in str(exc_info.value)

