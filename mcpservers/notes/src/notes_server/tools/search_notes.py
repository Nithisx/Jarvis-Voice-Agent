"""Tool handler for searching notes with full-text search, category, and tags."""

from __future__ import annotations

from typing import Any, Optional

from notes_server.database import db_manager
from notes_server.repositories.notes_repository import NotesRepository
from notes_server.schemas import SearchNotesInput


async def handle_search_notes(
    query: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    include_archived: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """Search notes using indexed full-text query, category, tags, and archive status."""
    validated = SearchNotesInput(
        query=query,
        category=category,  # type: ignore[arg-type]
        tags=tags,
        include_archived=include_archived,
        limit=limit,
    )

    async with db_manager.connection() as conn:
        notes = await NotesRepository.search_notes(
            conn=conn,
            query=validated.query,
            category=validated.category,
            tags=validated.tags,
            include_archived=validated.include_archived,
            limit=validated.limit,
        )
        return {
            "success": True,
            "total_matches": len(notes),
            "limit": validated.limit,
            "notes": notes,
        }

