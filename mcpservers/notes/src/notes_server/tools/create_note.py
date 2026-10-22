"""Tool handler for creating notes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.exceptions import NotesMCPError, ValidationError
from notes_server.repositories.notes_repository import NotesRepository
from notes_server.schemas import CreateNoteInput


async def handle_create_note(
    title: str,
    content: str,
    category: str = "general",
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
    example: Optional[str] = None,
    learned_at: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new note with persistent categorization and tags."""
    parsed_learned_at: Optional[datetime] = None
    if learned_at:
        try:
            parsed_learned_at = datetime.fromisoformat(learned_at)
        except ValueError as exc:
            raise ValidationError(f"Invalid ISO timestamp for learned_at: '{learned_at}'") from exc

    validated = CreateNoteInput(
        title=title,
        content=content,
        category=category,  # type: ignore[arg-type]
        tags=tags or [],
        source=source,
        example=example,
        learned_at=parsed_learned_at,
    )

    async with db_manager.connection() as conn:
        record = await NotesRepository.create_note(
            conn=conn,
            title=validated.title,
            content=validated.content,
            category=validated.category,
            tags=validated.tags,
            source=validated.source,
            example=validated.example,
            learned_at=validated.learned_at,
        )
        return {
            "success": True,
            "message": f"Note '{validated.title}' created successfully.",
            "id": record["id"],
            "note": record,
        }

