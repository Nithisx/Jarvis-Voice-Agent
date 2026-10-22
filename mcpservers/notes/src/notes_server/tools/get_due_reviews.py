"""Tool handler for retrieving due revision prompts for active recall."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository
from notes_server.schemas import GetDueReviewsInput


async def handle_get_due_reviews(
    limit: int = 10,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """Retrieve due and overdue items formatted as active-recall quiz prompts.

    Note: Answers and definitions are intentionally omitted to test recall.
    """
    validated = GetDueReviewsInput(limit=limit, category=category)

    async with db_manager.connection() as conn:
        due_items = await VocabularyRepository.get_due_reviews(
            conn=conn,
            limit=validated.limit,
            category=validated.category,
        )
        return {
            "success": True,
            "total_due": len(due_items),
            "due_reviews": due_items,
            "instructions": (
                "For active recall: present the prompt or word to the user without revealing "
                "the meaning. Collect their answer and call submit_review with their self-reported rating."
            ),
        }

