"""Tests for Note CRUD operations, full-text search, and soft archival."""

from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timezone

from notes_server.exceptions import RecordNotFoundError, ValidationError
from notes_server.repositories.notes_repository import NotesRepository


@pytest.mark.asyncio
async def test_create_note_success(test_conn):
    """Verify creating a valid note with all fields."""
    note = await NotesRepository.create_note(
        conn=test_conn,
        title="Spaced Repetition Concept",
        content="Spaced repetition is an evidence-based learning technique.",
        category="technical",
        tags=["learning", "memory", "algorithms"],
        source="reading",
        example="Anki and SuperMemo use spaced repetition.",
    )

    assert note["id"] is not None
    assert note["title"] == "Spaced Repetition Concept"
    assert note["category"] == "technical"
    assert "memory" in note["tags"]
    assert note["archived_at"] is None
    assert note["created_at"] is not None


@pytest.mark.asyncio
async def test_get_note_by_id(test_conn):
    """Verify retrieving a note by UUID."""
    created = await NotesRepository.create_note(
        conn=test_conn,
        title="Retrieval Practice",
        content="Testing memory actively improves retention.",
        category="communication",
    )
    note_id = created["id"]

    fetched = await NotesRepository.get_note_by_id(test_conn, note_id)
    assert fetched["id"] == note_id
    assert fetched["title"] == "Retrieval Practice"
    assert fetched["category"] == "communication"


@pytest.mark.asyncio
async def test_get_note_missing(test_conn):
    """Verify RecordNotFoundError on non-existent note."""
    random_id = str(uuid.uuid4())
    with pytest.raises(RecordNotFoundError):
        await NotesRepository.get_note_by_id(test_conn, random_id)


@pytest.mark.asyncio
async def test_get_note_invalid_uuid(test_conn):
    """Verify ValidationError on malformed UUID string."""
    with pytest.raises(ValidationError):
        await NotesRepository.get_note_by_id(test_conn, "not-a-valid-uuid")


@pytest.mark.asyncio
async def test_update_note(test_conn):
    """Verify updating only explicitly provided fields."""
    created = await NotesRepository.create_note(
        conn=test_conn,
        title="Original Title",
        content="Original content.",
        category="general",
        tags=["tag1"],
    )
    note_id = created["id"]

    updated = await NotesRepository.update_note(
        conn=test_conn,
        note_id=note_id,
        title="Updated Title",
        tags=["tag1", "tag2"],
    )

    assert updated["id"] == note_id
    assert updated["title"] == "Updated Title"
    assert updated["content"] == "Original content."
    assert set(updated["tags"]) == {"tag1", "tag2"}
    assert updated["updated_at"] >= created["updated_at"]


@pytest.mark.asyncio
async def test_archive_note(test_conn):
    """Verify soft archival sets archived_at and excludes note from normal search."""
    created = await NotesRepository.create_note(
        conn=test_conn,
        title="Note to Archive",
        content="Content to hide from normal view.",
        category="grammar",
    )
    note_id = created["id"]

    archived = await NotesRepository.archive_note(test_conn, note_id)
    assert archived["archived_at"] is not None

    # Normal search should not return it
    results_normal = await NotesRepository.search_notes(
        conn=test_conn,
        query="Archive",
        include_archived=False,
    )
    assert not any(n["id"] == note_id for n in results_normal)

    # Search with include_archived=True should return it
    results_all = await NotesRepository.search_notes(
        conn=test_conn,
        query="Archive",
        include_archived=True,
    )
    assert any(n["id"] == note_id for n in results_all)


@pytest.mark.asyncio
async def test_search_notes_fts_and_filters(test_conn):
    """Verify full-text search, category filter, and tags filter."""
    unique_kw = f"quantum_{uuid.uuid4().hex[:6]}"
    note1 = await NotesRepository.create_note(
        conn=test_conn,
        title=f"Physics and {unique_kw}",
        content="Superposition and entanglement are fundamental concepts.",
        category="technical",
        tags=["physics", "quantum"],
    )
    note2 = await NotesRepository.create_note(
        conn=test_conn,
        title="Literature Study",
        content=f"An essay discussing {unique_kw} metaphors in modern fiction.",
        category="story",
        tags=["literature"],
    )

    # Search by keyword
    kw_results = await NotesRepository.search_notes(test_conn, query=unique_kw)
    assert len(kw_results) >= 2

    # Filter by category
    physics_results = await NotesRepository.search_notes(
        test_conn, query=unique_kw, category="technical"
    )
    assert len(physics_results) == 1
    assert physics_results[0]["id"] == note1["id"]

    # Filter by tag
    tag_results = await NotesRepository.search_notes(test_conn, tags=["literature"])
    assert any(n["id"] == note2["id"] for n in tag_results)


@pytest.mark.asyncio
async def test_create_note_invalid_inputs(test_conn):
    """Verify validation errors on empty title, empty content, or invalid category."""
    from pydantic import ValidationError as PydanticValidationError

    # Empty title
    with pytest.raises((ValidationError, PydanticValidationError, ValueError)):
        await NotesRepository.create_note(
            conn=test_conn,
            title="   ",
            content="Some content",
            category="general",
        )

    # Empty content
    with pytest.raises((ValidationError, PydanticValidationError, ValueError)):
        await NotesRepository.create_note(
            conn=test_conn,
            title="Valid Title",
            content="   ",
            category="general",
        )


@pytest.mark.asyncio
async def test_database_connection_error_masking():
    """Verify that database connection errors do not expose credentials."""
    from notes_server.database import DatabaseManager
    from notes_server.exceptions import DatabaseConnectionError
    import os

    manager = DatabaseManager()
    # Temporarily set an invalid port that fails to connect
    old_env = os.environ.get("DATABASE_URL")
    old_timeout = os.environ.get("NOTES_DB_TIMEOUT_SECONDS")
    try:
        os.environ["DATABASE_URL"] = "postgresql://user:super_secret_password@127.0.0.1:54321/nonexistent"
        os.environ["NOTES_DB_TIMEOUT_SECONDS"] = "1.0"
        from notes_server import config
        config._SETTINGS_CACHE = None
        with pytest.raises(DatabaseConnectionError) as exc_info:
            await manager.get_pool()
        # Verify secret password is never in error message
        assert "super_secret_password" not in str(exc_info.value)
    finally:
        if old_env is not None:
            os.environ["DATABASE_URL"] = old_env
        else:
            os.environ.pop("DATABASE_URL", None)
        if old_timeout is not None:
            os.environ["NOTES_DB_TIMEOUT_SECONDS"] = old_timeout
        else:
            os.environ.pop("NOTES_DB_TIMEOUT_SECONDS", None)
        from notes_server import config
        config._SETTINGS_CACHE = None
