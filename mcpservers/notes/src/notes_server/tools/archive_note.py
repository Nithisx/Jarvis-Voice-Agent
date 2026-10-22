"""Tool handler for soft-archiving a note."""

from __future__ import annotations

from typing import Any

from notes_server.database import db_manager
from notes_server.repositories.notes_repository import NotesRepository


async def handle_archive_note(note_id: str) -> dict[str, Any]:
    """Soft-archive a note by setting archived_at timestamp."""
    async with db_manager.connection() as conn:
        archived = await NotesRepository.archive_note(conn, note_id)
        return {
            "success": True,
            "message": f"Note '{note_id}' archived successfully.",
            "id": archived["id"],
            "archived_at": archived.get("archived_at"),
            "note": archived,
        }

