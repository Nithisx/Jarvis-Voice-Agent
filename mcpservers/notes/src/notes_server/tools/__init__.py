"""MCP tools module registration for Notes MCP Server."""

from __future__ import annotations

from typing import Any, Callable, Optional

from notes_server.tools.archive_note import handle_archive_note
from notes_server.tools.create_note import handle_create_note
from notes_server.tools.get_daily_summary import handle_get_daily_summary
from notes_server.tools.get_due_reviews import handle_get_due_reviews
from notes_server.tools.get_learning_stats import handle_get_learning_stats
from notes_server.tools.get_note import handle_get_note
from notes_server.tools.save_vocabulary import handle_save_vocabulary
from notes_server.tools.search_notes import handle_search_notes
from notes_server.tools.search_vocabulary import handle_search_vocabulary
from notes_server.tools.submit_review import handle_submit_review
from notes_server.tools.update_note import handle_update_note


def register_all_tools(server: Any) -> None:
    """Register all 11 Notes MCP tools with the MCPServer instance."""

    @server.tool(
        name="create_note",
        description=(
            "Create a new note with persistent categorization, tags, and source metadata. "
            "Supported categories: general, communication, grammar, vocabulary, story, "
            "technical, personal_reflection."
        ),
    )
    async def create_note(
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
        example: Optional[str] = None,
        learned_at: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_create_note(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source=source,
            example=example,
            learned_at=learned_at,
        )

    @server.tool(
        name="get_note",
        description="Retrieve full note details, tags, timestamps, and archive status by note ID (UUID).",
    )
    async def get_note(note_id: str) -> dict[str, Any]:
        return await handle_get_note(note_id=note_id)

    @server.tool(
        name="search_notes",
        description=(
            "Search notes using PostgreSQL full-text search across titles and content, "
            "with optional filtering by category, tags, and archived status. Max limit 100."
        ),
    )
    async def search_notes(
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        include_archived: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await handle_search_notes(
            query=query,
            category=category,
            tags=tags,
            include_archived=include_archived,
            limit=limit,
        )

    @server.tool(
        name="update_note",
        description="Update explicitly supplied fields of an existing active note by its ID.",
    )
    async def update_note(
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
        example: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_update_note(
            note_id=note_id,
            title=title,
            content=content,
            category=category,
            tags=tags,
            source=source,
            example=example,
        )

    @server.tool(
        name="archive_note",
        description="Soft-archive a note by setting archived_at timestamp. Notes are not permanently deleted.",
    )
    async def archive_note(note_id: str) -> dict[str, Any]:
        return await handle_archive_note(note_id=note_id)

    @server.tool(
        name="save_vocabulary",
        description=(
            "Save a vocabulary item with normalized duplicate detection. If the word already "
            "exists, returns the existing record and a duplicate indication. Sets the first review for tomorrow."
        ),
    )
    async def save_vocabulary(
        word: str,
        meaning: str,
        example_sentence: Optional[str] = None,
        synonyms: Optional[list[str]] = None,
        word_type: Optional[str] = None,
        pronunciation: Optional[str] = None,
        source_context: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_save_vocabulary(
            word=word,
            meaning=meaning,
            example_sentence=example_sentence,
            synonyms=synonyms,
            word_type=word_type,
            pronunciation=pronunciation,
            source_context=source_context,
            difficulty=difficulty,
        )

    @server.tool(
        name="search_vocabulary",
        description=(
            "Search vocabulary entries across words, definitions, synonyms, or context. "
            "Supports pagination via limit and offset."
        ),
    )
    async def search_vocabulary(
        query: Optional[str] = None,
        difficulty: Optional[str] = None,
        word_type: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await handle_search_vocabulary(
            query=query,
            difficulty=difficulty,
            word_type=word_type,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="get_due_reviews",
        description=(
            "Retrieve items ready for revision, formatted for active recall. Prioritizes overdue "
            "items, then items due soon. Answers/meanings are hidden to quiz the user."
        ),
    )
    async def get_due_reviews(
        limit: int = 10,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_get_due_reviews(
            limit=limit,
            category=category,
        )

    @server.tool(
        name="submit_review",
        description=(
            "Submit a spaced-repetition recall rating (0: forgot, 1: hard, 2: good, 3: easy). "
            "Updates the review schedule and records history in a single transaction."
        ),
    )
    async def submit_review(
        item_id: str,
        rating: int,
        response_text: Optional[str] = None,
        feedback_notes: Optional[str] = None,
    ) -> dict[str, Any]:
        return await handle_submit_review(
            item_id=item_id,
            rating=rating,
            response_text=response_text,
            feedback_notes=feedback_notes,
        )

    @server.tool(
        name="get_daily_summary",
        description=(
            "Retrieve notes and vocabulary learned during a local calendar day, grouped by category, "
            "with UTC boundary handling. Default timezone is Asia/Kolkata."
        ),
    )
    async def get_daily_summary(
        date: Optional[str] = None,
        timezone: str = "Asia/Kolkata",
    ) -> dict[str, Any]:
        return await handle_get_daily_summary(
            date=date,
            timezone=timezone,
        )

    @server.tool(
        name="get_learning_stats",
        description=(
            "Retrieve learning statistics: total active/archived notes and vocabulary, "
            "due/overdue review counts, recent 7-day activity, and self-reported recall trends."
        ),
    )
    async def get_learning_stats() -> dict[str, Any]:
        return await handle_get_learning_stats()


__all__ = [
    "register_all_tools",
    "handle_create_note",
    "handle_get_note",
    "handle_search_notes",
    "handle_update_note",
    "handle_archive_note",
    "handle_save_vocabulary",
    "handle_search_vocabulary",
    "handle_get_due_reviews",
    "handle_submit_review",
    "handle_get_daily_summary",
    "handle_get_learning_stats",
]

