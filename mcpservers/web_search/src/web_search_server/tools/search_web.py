"""Tool handler for search_web."""

from __future__ import annotations

from typing import Any, Optional

from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.schemas import SearchWebInput

_DEFAULT_PROVIDER = TavilyProvider()


async def handle_search_web(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    max_results: int = 5,
    time_range: Optional[str] = None,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
    include_raw_content: bool = False,
    provider: Optional[TavilyProvider] = None,
) -> dict[str, Any]:
    """Search the internet using Tavily and return relevant results."""
    validated = SearchWebInput(
        query=query,
        search_depth=search_depth,  # type: ignore[arg-type]
        topic=topic,  # type: ignore[arg-type]
        max_results=max_results,
        time_range=time_range,  # type: ignore[arg-type]
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        include_raw_content=include_raw_content,
    )

    active_provider = provider or _DEFAULT_PROVIDER
    resp = await active_provider.search(
        query=validated.query,
        search_depth=validated.search_depth,
        topic=validated.topic,
        max_results=validated.max_results,
        time_range=validated.time_range,
        include_domains=validated.include_domains,
        exclude_domains=validated.exclude_domains,
        include_raw_content=validated.include_raw_content,
    )
    return resp.model_dump()

