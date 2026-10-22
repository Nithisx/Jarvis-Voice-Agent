"""Tool handler for retrieving learning statistics and recall trends."""

from __future__ import annotations

from typing import Any

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository


async def handle_get_learning_stats() -> dict[str, Any]:
    """Retrieve learning statistics, active/archived counts, due reviews, and recall trends."""
    async with db_manager.connection() as conn:
        stats = await VocabularyRepository.get_learning_stats(conn)
        return {
            "success": True,
            "learning_stats": stats,
        }

