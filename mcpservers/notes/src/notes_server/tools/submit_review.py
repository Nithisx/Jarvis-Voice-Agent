"""Tool handler for submitting spaced-repetition review ratings."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository
from notes_server.schemas import SubmitReviewInput


async def handle_submit_review(
    item_id: str,
    rating: int,
    response_text: Optional[str] = None,
    feedback_notes: Optional[str] = None,
) -> dict[str, Any]:
    """Submit a spaced-repetition review rating (0-3) and calculate next review date.

    Rating scale:
    - 0: Forgot completely (retry in 10 minutes)
    - 1: Remembered with substantial difficulty (retry in 1 day)
    - 2: Remembered with some effort (moderate interval increase)
    - 3: Remembered easily (substantial interval increase)
    """
    validated = SubmitReviewInput(
        item_id=item_id,
        rating=rating,
        response_text=response_text,
        feedback_notes=feedback_notes,
    )

    async with db_manager.connection() as conn:
        result = await VocabularyRepository.submit_review(
            conn=conn,
            item_id=validated.item_id,
            rating=validated.rating,
            response_text=validated.response_text,
            feedback_notes=validated.feedback_notes,
        )
        return {
            "success": True,
            "message": f"Review saved. Rating {rating} recorded.",
            **result,
        }

