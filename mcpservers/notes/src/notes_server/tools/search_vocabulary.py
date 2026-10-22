"""Tool handler for searching vocabulary entries."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository
from notes_server.schemas import SearchVocabularyInput


async def handle_search_vocabulary(
    query: Optional[str] = None,
    difficulty: Optional[str] = None,
    word_type: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search vocabulary across word, meaning, synonyms, and context with pagination."""
    validated = SearchVocabularyInput(
        query=query,
        difficulty=difficulty,  # type: ignore[arg-type]
        word_type=word_type,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    async with db_manager.connection() as conn:
        records = await VocabularyRepository.search_vocabulary(
            conn=conn,
            query=validated.query,
            difficulty=validated.difficulty,
            word_type=validated.word_type,
            include_archived=validated.include_archived,
            limit=validated.limit,
            offset=validated.offset,
        )
        return {
            "success": True,
            "total_matches": len(records),
            "limit": validated.limit,
            "offset": validated.offset,
            "vocabulary": records,
        }

