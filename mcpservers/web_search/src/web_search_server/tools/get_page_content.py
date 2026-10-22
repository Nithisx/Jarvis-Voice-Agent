"""Tool handler for get_page_content."""

from __future__ import annotations

from typing import Any, Optional

from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.schemas import GetPageContentInput

_DEFAULT_PROVIDER = TavilyProvider()


async def handle_get_page_content(
    url: str,
    max_characters: int = 12000,
    provider: Optional[TavilyProvider] = None,
) -> dict[str, Any]:
    """Retrieve content from a specific web page using Tavily extraction."""
    validated = GetPageContentInput(
        url=url,
        max_characters=max_characters,
    )

    active_provider = provider or _DEFAULT_PROVIDER
    resp = await active_provider.get_page_content(
        url=validated.url,
        max_characters=validated.max_characters,
    )
    return resp.model_dump()

