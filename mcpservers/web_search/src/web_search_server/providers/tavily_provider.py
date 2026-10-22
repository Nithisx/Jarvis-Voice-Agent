"""Tavily search provider integration for the Web Search MCP Server."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx
from tavily import AsyncTavilyClient
from tavily.errors import (
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    TimeoutError as TavilyTimeoutErr,
    UsageLimitExceededError,
)

from web_search_server.config import get_settings
from web_search_server.exceptions import (
    TavilyAuthError,
    TavilyProviderError,
    TavilyRateLimitError,
    TavilyTimeoutError,
    ValidationError,
)
from web_search_server.schemas import (
    DifficultyLevel,
    PageContentResponse,
    SearchResultItem,
    SearchWebResponse,
    VocabularyItem,
    validate_public_http_url,
)

logger = logging.getLogger("web_search_server.provider")


class TavilyProvider:
    """Encapsulates all communication with the Tavily Search and Extraction API."""

    def __init__(self, client: Optional[AsyncTavilyClient] = None) -> None:
        self._client: Optional[AsyncTavilyClient] = client

    def _get_client(self) -> AsyncTavilyClient:
        """Lazily initialize the AsyncTavilyClient only when needed."""
        if self._client is None:
            settings = get_settings()
            self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        return self._client

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        topic: str = "general",
        max_results: int = 5,
        time_range: Optional[str] = None,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        include_raw_content: bool = False,
    ) -> SearchWebResponse:
        """Execute a web search through Tavily with bounded results and error mapping."""
        client = self._get_client()
        settings = get_settings()

        bounded_max_results = max(1, min(max_results, settings.max_results_limit))

        kwargs: dict[str, Any] = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": bounded_max_results,
            "include_raw_content": "markdown" if include_raw_content else False,
            "timeout": settings.timeout_seconds,
        }

        if time_range:
            kwargs["time_range"] = time_range
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        try:
            raw_response = await client.search(**kwargs)
        except (InvalidAPIKeyError, MissingAPIKeyError) as exc:
            logger.error("Tavily authentication error encountered.")
            raise TavilyAuthError("Tavily authentication failed. Please verify TAVILY_API_KEY in the root .env.") from exc
        except UsageLimitExceededError as exc:
            logger.error("Tavily quota limit exceeded.")
            raise TavilyRateLimitError("Tavily search rate limit or account credit quota exceeded.") from exc
        except (TavilyTimeoutErr, httpx.TimeoutException) as exc:
            logger.error("Tavily request timed out.")
            raise TavilyTimeoutError("Tavily search request timed out.") from exc
        except BadRequestError as exc:
            logger.warning("Tavily bad request: %s", exc)
            raise ValidationError(f"Invalid search request parameters: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected Tavily provider error: %s", exc)
            raise TavilyProviderError(f"Tavily search error: {exc}") from exc

        raw_results = raw_response.get("results", [])
        items: list[SearchResultItem] = []

        for r in raw_results[:bounded_max_results]:
            url = r.get("url", "")
            title = r.get("title", "Untitled")
            content = r.get("content", "")
            pub_date = r.get("published_date")
            score = r.get("score")
            raw_content = r.get("raw_content") if include_raw_content else None

            items.append(
                SearchResultItem(
                    title=title,
                    url=url,
                    content=content,
                    published_date=pub_date,
                    score=float(score) if score is not None else None,
                    raw_content=raw_content,
                )
            )

        message = None
        if not items:
            message = f"No relevant search results found for query: '{query}'."

        return SearchWebResponse(
            success=True,
            query=query,
            total_results=len(items),
            results=items,
            message=message,
        )

    async def get_page_content(
        self,
        url: str,
        max_characters: int = 12000,
    ) -> PageContentResponse:
        """Extract web page content using Tavily's extraction API, enforcing length limits."""
        validated_url = validate_public_http_url(url)
        client = self._get_client()
        settings = get_settings()

        try:
            extract_resp = await client.extract(
                urls=[validated_url],
                format="markdown",
                timeout=settings.timeout_seconds,
            )
        except (InvalidAPIKeyError, MissingAPIKeyError) as exc:
            logger.error("Tavily extraction authentication failed.")
            raise TavilyAuthError("Tavily authentication failed during page content extraction.") from exc
        except UsageLimitExceededError as exc:
            logger.error("Tavily quota exceeded during extraction.")
            raise TavilyRateLimitError("Tavily extraction quota exceeded.") from exc
        except (TavilyTimeoutErr, httpx.TimeoutException) as exc:
            logger.error("Tavily extraction timed out for url: %s", validated_url)
            raise TavilyTimeoutError(f"Tavily page extraction timed out for {validated_url}.") from exc
        except Exception as exc:
            logger.error("Tavily extraction error: %s", exc)
            raise TavilyProviderError(f"Failed to extract page content from {validated_url}: {exc}") from exc

        results = extract_resp.get("results", [])
        failed_results = extract_resp.get("failed_results", [])

        if failed_results and not results:
            err_msg = failed_results[0].get("error", "Unknown extraction error")
            raise TavilyProviderError(f"Could not extract content from '{validated_url}': {err_msg}")

        if not results:
            raise TavilyProviderError(f"No content could be extracted from '{validated_url}'.")

        first_res = results[0]
        raw_text = first_res.get("raw_content") or ""
        canonical_url = first_res.get("url") or validated_url

        # Check content truncation bounds
        truncated = False
        if len(raw_text) > max_characters:
            content = raw_text[:max_characters]
            truncated = True
        else:
            content = raw_text

        return PageContentResponse(
            success=True,
            url=validated_url,
            canonical_url=canonical_url,
            title=first_res.get("title"),
            content=content,
            character_count=len(content),
            truncated=truncated,
            retrieval_metadata={
                "source": "tavily_extract",
                "format": "markdown",
                "raw_length": len(raw_text),
                "is_truncated": truncated,
            },
        )

    async def find_vocabulary(
        self,
        topic: str,
        level: DifficultyLevel = "intermediate",
        count: int = 5,
        include_idioms: bool = True,
        include_phrasal_verbs: bool = True,
        context: Optional[str] = None,
    ) -> list[VocabularyItem]:
        """Discover English vocabulary, idioms, and phrases grounded in web sources."""
        # Formulate a targeted search query for English learning resources
        qualifiers = ["vocabulary", "meaning", "definition", "examples"]
        if include_idioms:
            qualifiers.append("idioms")
        if include_phrasal_verbs:
            qualifiers.append("phrasal verbs")

        query_parts = [f"English {', '.join(qualifiers)} for '{topic}'"]
        if context:
            query_parts.append(f"in context of {context}")
        query_parts.append(f"{level} level")

        search_query = " ".join(query_parts)

        # Prioritize high-quality dictionary and educational domains
        educational_domains = [
            "dictionary.cambridge.org",
            "merriam-webster.com",
            "oxfordlearnersdictionaries.com",
            "collinsdictionary.com",
            "bbc.co.uk",
            "vocabulary.com",
            "thoughtco.com",
        ]

        # First attempt search with preferred domains
        search_resp = await self.search(
            query=search_query,
            search_depth="advanced",
            topic="general",
            max_results=min(10, count * 2),
            include_domains=educational_domains,
        )

        # If few results returned from restricted domains, search broadly
        if search_resp.total_results < count:
            broad_resp = await self.search(
                query=search_query,
                search_depth="advanced",
                topic="general",
                max_results=min(10, count * 2),
            )
            existing_urls = {r.url for r in search_resp.results}
            for r in broad_resp.results:
                if r.url not in existing_urls:
                    search_resp.results.append(r)

        items: list[VocabularyItem] = []

        # Parse retrieved snippets into structured candidate vocabulary items
        for res in search_resp.results:
            if len(items) >= count:
                break

            parsed_items = self._extract_vocab_from_snippet(
                title=res.title,
                snippet=res.content,
                source_url=res.url,
                level=level,
            )
            for item in parsed_items:
                if len(items) >= count:
                    break
                # Deduplicate by word
                if not any(it.word.lower() == item.word.lower() for it in items):
                    items.append(item)

        # If snippet parsing didn't find enough structured items, create source-grounded candidates
        if len(items) < count:
            for res in search_resp.results:
                if len(items) >= count:
                    break
                if any(it.source_url == res.url for it in items):
                    continue

                # Derive clean phrase from title or snippet
                clean_title = re.sub(r"\s*[-|:].*$", "", res.title).strip()
                if clean_title and len(clean_title.split()) <= 4:
                    word = clean_title
                else:
                    word = f"{topic.title()} Expression"

                meaning = res.content.strip()
                if len(meaning) > 250:
                    meaning = meaning[:247] + "..."

                items.append(
                    VocabularyItem(
                        word=word,
                        word_type="phrase" if " " in word else "noun",
                        meaning=meaning,
                        example_sentence=f"Usage in {topic}: See reference in retrieved context.",
                        synonyms=[],
                        source_url=res.url,
                        difficulty=level,
                        difficulty_note=f"Estimated {level} level based on query context",
                        example_source_type="source_grounded",
                    )
                )

        return items[:count]

    @staticmethod
    def _extract_vocab_from_snippet(
        title: str,
        snippet: str,
        source_url: str,
        level: str,
    ) -> list[VocabularyItem]:
        """Extract vocabulary candidates from search result title and snippet."""
        extracted: list[VocabularyItem] = []

        # Common dictionary pattern: "Word: Meaning. Example" or "Word - Meaning"
        pattern = r"(?:^|\n)(?:\d+\.\s*)?([A-Za-z\s'-]{2,30})\s*(?::|—|-)\s*([^.\n]+(?:\.[^.\n]+)?)"
        matches = re.findall(pattern, snippet)

        for word, meaning in matches:
            word = word.strip()
            meaning = meaning.strip()
            if len(word.split()) > 5 or len(meaning) < 5:
                continue

            extracted.append(
                VocabularyItem(
                    word=word,
                    word_type="idiom" if len(word.split()) > 1 else "vocabulary",
                    meaning=meaning,
                    example_sentence=f"In practice: {meaning}",
                    synonyms=[],
                    source_url=source_url,
                    difficulty=level,
                    difficulty_note=f"Estimated {level} level based on search context",
                    example_source_type="source_grounded",
                )
            )

        return extracted

