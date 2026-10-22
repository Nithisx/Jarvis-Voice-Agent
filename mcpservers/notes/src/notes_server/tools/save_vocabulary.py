"""Tool handler for saving vocabulary entries with duplicate detection."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository
from notes_server.schemas import SaveVocabularyInput


async def handle_save_vocabulary(
    word: str,
    meaning: str,
    example_sentence: Optional[str] = None,
    synonyms: Optional[list[str]] = None,
    word_type: Optional[str] = None,
    pronunciation: Optional[str] = None,
    source_context: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> dict[str, Any]:
    """Save a vocabulary item with normalized case-insensitive duplicate detection."""
    validated = SaveVocabularyInput(
        word=word,
        meaning=meaning,
        example_sentence=example_sentence,
        synonyms=synonyms or [],
        word_type=word_type,
        pronunciation=pronunciation,
        source_context=source_context,
        difficulty=difficulty,  # type: ignore[arg-type]
    )

    async with db_manager.connection() as conn:
        result = await VocabularyRepository.save_vocabulary(
            conn=conn,
            word=validated.word,
            meaning=validated.meaning,
            example_sentence=validated.example_sentence,
            synonyms=validated.synonyms,
            word_type=validated.word_type,
            pronunciation=validated.pronunciation,
            source_context=validated.source_context,
            difficulty=validated.difficulty,
        )
        return {
            "success": True,
            **result,
        }

