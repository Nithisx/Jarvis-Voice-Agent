"""Tool handler for updating an existing note."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.notes_repository import NotesRepository
from notes_server.schemas import UpdateNoteInput


async def handle_update_note(
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
    example: Optional[str] = None,
) -> dict[str, Any]:
    """Update explicitly supplied fields of an existing note."""
    validated = UpdateNoteInput(
        note_id=note_id,
        title=title,
        content=content,
        category=category,  # type: ignore[arg-type]
        tags=tags,
        source=source,
        example=example,
    )

    async with db_manager.connection() as conn:
        updated = await NotesRepository.update_note(
            conn=conn,
            note_id=validated.note_id,
            title=validated.title,
            content=validated.content,
            category=validated.category,
            tags=validated.tags,
            source=validated.source,
            example=validated.example,
        )
        return {
            "success": True,
            "message": f"Note '{note_id}' updated successfully.",
            "id": updated["id"],
            "note": updated,
        }

