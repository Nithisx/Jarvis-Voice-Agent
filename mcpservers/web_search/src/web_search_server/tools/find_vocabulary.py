"""Tool handler for find_vocabulary."""

from __future__ import annotations

from typing import Any, Optional

from web_search_server.providers.tavily_provider import TavilyProvider
from web_search_server.schemas import FindVocabularyInput, FindVocabularyResponse

_DEFAULT_PROVIDER = TavilyProvider()


async def handle_find_vocabulary(
    topic: str,
    level: str = "intermediate",
    count: int = 5,
    include_idioms: bool = True,
    include_phrasal_verbs: bool = True,
    context: Optional[str] = None,
    provider: Optional[TavilyProvider] = None,
) -> dict[str, Any]:
    """Find useful English vocabulary, expressions, and idioms for communication learning."""
    validated = FindVocabularyInput(
        topic=topic,
        level=level,  # type: ignore[arg-type]
        count=count,
        include_idioms=include_idioms,
        include_phrasal_verbs=include_phrasal_verbs,
        context=context,
    )

    active_provider = provider or _DEFAULT_PROVIDER
    items = await active_provider.find_vocabulary(
        topic=validated.topic,
        level=validated.level,
        count=validated.count,
        include_idioms=validated.include_idioms,
        include_phrasal_verbs=validated.include_phrasal_verbs,
        context=validated.context,
    )

    response = FindVocabularyResponse(
        success=True,
        topic=validated.topic,
        level=validated.level,
        count=len(items),
        items=items,
    )
    return response.model_dump()

