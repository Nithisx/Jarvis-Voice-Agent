"""Tool registry for Web Search MCP Server."""

from __future__ import annotations

from typing import Any, Optional

from web_search_server.tools.find_vocabulary import handle_find_vocabulary
from web_search_server.tools.get_page_content import handle_get_page_content
from web_search_server.tools.search_web import handle_search_web


def register_all_tools(server: Any) -> None:
    """Register all 3 Web Search MCP tools with the MCPServer instance."""

    @server.tool(
        name="search_web",
        description=(
            "Search the internet using Tavily to retrieve relevant articles, news, factual information, "
            "and web resources. Supports search depth, domain filtering, and date range limits."
        ),
    )
    async def search_web(
        query: str,
        search_depth: str = "basic",
        topic: str = "general",
        max_results: int = 5,
        time_range: Optional[str] = None,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        return await handle_search_web(
            query=query,
            search_depth=search_depth,
            topic=topic,
            max_results=max_results,
            time_range=time_range,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_raw_content=include_raw_content,
        )

    @server.tool(
        name="get_page_content",
        description=(
            "Retrieve and extract clean text content from a specific web page URL. "
            "Rejects non-HTTP schemes and private network addresses."
        ),
    )
    async def get_page_content(
        url: str,
        max_characters: int = 12000,
    ) -> dict[str, Any]:
        return await handle_get_page_content(
            url=url,
            max_characters=max_characters,
        )

    @server.tool(
        name="find_vocabulary",
        description=(
            "Discover useful English vocabulary words, idioms, phrasal verbs, definitions, "
            "and natural example sentences for communication and learning, grounded in web sources."
        ),
    )
    async def find_vocabulary(
        topic: str,
        level: str = "intermediate",
        count: int = 5,
        include_idioms: bool = True,
        include_phrasal_verbs: bool = True,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_find_vocabulary(
            topic=topic,
            level=level,
            count=count,
            include_idioms=include_idioms,
            include_phrasal_verbs=include_phrasal_verbs,
            context=context,
        )


__all__ = [
    "register_all_tools",
    "handle_search_web",
    "handle_get_page_content",
    "handle_find_vocabulary",
]

