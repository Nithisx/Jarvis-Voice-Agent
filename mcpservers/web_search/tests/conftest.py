"""Pytest configuration and shared mocks for Web Search MCP Server tests."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

# On Windows, ensure selector loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
SRC_DIR = PACKAGE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from web_search_server.config import clear_settings_cache
from web_search_server.providers.tavily_provider import TavilyProvider


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-wide event loop for async tests."""
    if sys.platform == "win32":
        policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        loop = policy.new_event_loop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def ensure_test_env():
    """Ensure a safe mock API key is available in tests by default."""
    clear_settings_cache()
    old_key = os.environ.get("TAVILY_API_KEY")
    os.environ["TAVILY_API_KEY"] = "tvly-test-mock-api-key-123456789"
    yield
    clear_settings_cache()
    if old_key is not None:
        os.environ["TAVILY_API_KEY"] = old_key
    else:
        os.environ.pop("TAVILY_API_KEY", None)


@pytest.fixture
def mock_tavily_client() -> AsyncMock:
    """Create a fully mocked AsyncTavilyClient to prevent live API calls."""
    client = AsyncMock()
    # Default search response
    client.search = AsyncMock(
        return_value={
            "query": "test query",
            "results": [
                {
                    "title": "Cambridge Dictionary: Serendipity",
                    "url": "https://dictionary.cambridge.org/dictionary/english/serendipity",
                    "content": "Serendipity: the fact of finding valuable or agreeable things not sought for.",
                    "score": 0.95,
                    "published_date": "2026-01-15",
                },
                {
                    "title": "Merriam-Webster Vocabulary",
                    "url": "https://www.merriam-webster.com/dictionary/lucid",
                    "content": "Lucid: clearly expressed or easy to understand. She gave a lucid presentation.",
                    "score": 0.88,
                    "published_date": "2026-02-10",
                },
            ],
        }
    )
    # Default extract response
    client.extract = AsyncMock(
        return_value={
            "results": [
                {
                    "url": "https://en.wikipedia.org/wiki/Spaced_repetition",
                    "title": "Spaced repetition - Wikipedia",
                    "raw_content": "# Spaced repetition\n\nSpaced repetition is an evidence-based learning technique that incorporates increasing intervals of time between subsequent review of previously learned material.",
                }
            ],
            "failed_results": [],
        }
    )
    return client


@pytest.fixture
def mock_provider(mock_tavily_client: AsyncMock) -> TavilyProvider:
    """Return a TavilyProvider instance backed by the mock client."""
    return TavilyProvider(client=mock_tavily_client)

