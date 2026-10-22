"""Tool handler for retrieving a note by ID."""

from __future__ import annotations

from typing import Any

from notes_server.database import db_manager
from notes_server.repositories.notes_repository import NotesRepository


async def handle_get_note(note_id: str) -> dict[str, Any]:
    """Retrieve full note details, tags, timestamps, and archive status by ID."""
    async with db_manager.connection() as conn:
        record = await NotesRepository.get_note_by_id(conn, note_id)
        return {
            "success": True,
            "id": record["id"],
            "note": record,
        }

