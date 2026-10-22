"""Tests for find_vocabulary tool and candidate extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError as PydanticValidationError

from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.tools.find_vocabulary import handle_find_vocabulary


@pytest.mark.asyncio
async def test_find_vocabulary_success(mock_provider: TavilyProvider):
    """Verify vocabulary discovery returns structured, source-grounded items."""
    resp = await handle_find_vocabulary(
        topic="negotiation and diplomacy",
        level="intermediate",
        count=2,
        include_idioms=True,
        include_phrasal_verbs=True,
        context="business meetings",
        provider=mock_provider,
    )

    assert resp["success"] is True
    assert resp["topic"] == "negotiation and diplomacy"
    assert resp["level"] == "intermediate"
    assert len(resp["items"]) <= 2

    for item in resp["items"]:
        assert item["word"]
        assert item["meaning"]
        assert item["example_sentence"]
        assert item["source_url"].startswith("http")
        assert item["difficulty"] == "intermediate"
        assert "Estimated" in item["difficulty_note"]


@pytest.mark.asyncio
async def test_find_vocabulary_snippet_parsing(mock_tavily_client: AsyncMock):
    """Verify dictionary-style definition extraction from search snippets."""
    mock_tavily_client.search.return_value = {
        "results": [
            {
                "title": "Business Idioms - Cambridge",
                "url": "https://dictionary.cambridge.org/idioms/business",
                "content": "Break the ice: to make people feel more relaxed in a social situation. He told a joke to break the ice.",
                "score": 0.9,
            }
        ]
    }
    provider = TavilyProvider(client=mock_tavily_client)

    resp = await handle_find_vocabulary(
        topic="networking",
        count=1,
        provider=provider,
    )

    assert resp["success"] is True
    assert len(resp["items"]) == 1
    item = resp["items"][0]
    assert "break the ice" in item["word"].lower()
    assert "relaxed" in item["meaning"].lower()
    assert item["source_url"] == "https://dictionary.cambridge.org/idioms/business"


@pytest.mark.asyncio
async def test_find_vocabulary_invalid_inputs(mock_provider: TavilyProvider):
    """Verify validation on empty topic or count out of range."""
    # Empty topic
    with pytest.raises(PydanticValidationError):
        await handle_find_vocabulary(topic="   ", provider=mock_provider)

    # Count > 10
    with pytest.raises(PydanticValidationError):
        await handle_find_vocabulary(topic="greetings", count=25, provider=mock_provider)

    # Invalid level
    with pytest.raises(PydanticValidationError):
        await handle_find_vocabulary(topic="greetings", level="mastery_expert", provider=mock_provider)

