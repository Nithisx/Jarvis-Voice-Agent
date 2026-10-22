"""Tool handler for retrieving daily learning summary."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.vocabulary_repository import VocabularyRepository
from notes_server.schemas import GetDailySummaryInput


async def handle_get_daily_summary(
    date: Optional[str] = None,
    timezone: str = "Asia/Kolkata",
) -> dict[str, Any]:
    """Retrieve notes and vocabulary learned during a local calendar day, grouped by category."""
    validated = GetDailySummaryInput(date=date, timezone=timezone)

    async with db_manager.connection() as conn:
        summary = await VocabularyRepository.get_daily_summary(
            conn=conn,
            target_date_str=validated.date,
            tz_name=validated.timezone,
        )
        return {
            "success": True,
            "daily_summary": summary,
        }

