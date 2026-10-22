"""Tests for MCP server tool registration and tool handler invocations."""

from __future__ import annotations

import uuid
import pytest

from notes_server.server import create_server
from notes_server.tools import (
    handle_archive_note,
    handle_create_note,
    handle_get_daily_summary,
    handle_get_due_reviews,
    handle_get_learning_stats,
    handle_get_note,
    handle_save_vocabulary,
    handle_search_notes,
    handle_search_vocabulary,
    handle_submit_review,
    handle_update_note,
)


@pytest.mark.asyncio
async def test_mcp_server_lists_all_11_tools():
    """Verify that all 11 required MCP tools are registered."""
    server = create_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "create_note",
        "get_note",
        "search_notes",
        "update_note",
        "archive_note",
        "save_vocabulary",
        "search_vocabulary",
        "get_due_reviews",
        "submit_review",
        "get_daily_summary",
        "get_learning_stats",
    }

    assert expected_tools == tool_names
    assert len(tools) == 11


@pytest.mark.asyncio
async def test_mcp_tool_end_to_end_workflow(isolated_schema):
    """Verify full tool execution lifecycle using tool handlers."""
    # 1. create_note
    note_res = await handle_create_note(
        title="MCP Architecture",
        content="Model Context Protocol standardizes LLM context access.",
        category="technical",
        tags=["mcp", "architecture"],
    )
    assert note_res["success"] is True
    note_id = note_res["id"]

    # 2. get_note
    get_res = await handle_get_note(note_id=note_id)
    assert get_res["success"] is True
    assert get_res["note"]["title"] == "MCP Architecture"

    # 3. search_notes
    search_res = await handle_search_notes(query="Protocol", category="technical")
    assert search_res["success"] is True
    assert any(n["id"] == note_id for n in search_res["notes"])

    # 4. update_note
    update_res = await handle_update_note(note_id=note_id, title="MCP Protocol Standards")
    assert update_res["success"] is True
    assert update_res["note"]["title"] == "MCP Protocol Standards"

    # 5. archive_note
    archive_res = await handle_archive_note(note_id=note_id)
    assert archive_res["success"] is True
    assert archive_res["archived_at"] is not None

    # 6. save_vocabulary
    word_name = f"Paragon_{uuid.uuid4().hex[:4]}"
    vocab_res = await handle_save_vocabulary(
        word=word_name,
        meaning="A person or thing regarded as a perfect example of a particular quality.",
        difficulty="advanced",
    )
    assert vocab_res["success"] is True
    assert vocab_res["is_duplicate"] is False
    vocab_id = vocab_res["id"]

    # 7. search_vocabulary
    vsearch_res = await handle_search_vocabulary(query=word_name)
    assert vsearch_res["success"] is True
    assert len(vsearch_res["vocabulary"]) == 1

    # 8. get_due_reviews
    due_res = await handle_get_due_reviews(limit=5)
    assert due_res["success"] is True
    assert "due_reviews" in due_res

    # 9. submit_review
    submit_res = await handle_submit_review(
        item_id=vocab_id,
        rating=2,
        response_text="Model of perfection",
    )
    assert submit_res["success"] is True
    assert submit_res["rating"] == 2

    # 10. get_daily_summary
    daily_res = await handle_get_daily_summary(timezone="Asia/Kolkata")
    assert daily_res["success"] is True
    assert "daily_summary" in daily_res

    # 11. get_learning_stats
    stats_res = await handle_get_learning_stats()
    assert stats_res["success"] is True
    assert "learning_stats" in stats_res


@pytest.mark.asyncio
async def test_mcp_call_tool_via_server_instance(isolated_schema):
    """Verify tool execution via the MCPServer.call_tool() interface."""
    server = create_server()
    res = await server.call_tool(
        "create_note",
        {
            "title": "FastMCP Direct Call Test",
            "content": "Testing direct tool invocation through the MCPServer instance.",
            "category": "technical",
        },
    )
    assert getattr(res, "is_error", False) is False
    content = res[0] if isinstance(res, tuple) else getattr(res, "content", [])
    assert len(content) > 0


@pytest.mark.asyncio
async def test_tool_input_validation_errors():
    """Verify tool handlers properly validate malformed inputs."""
    from pydantic import ValidationError as PydanticValidationError

    # 1. Invalid category
    with pytest.raises(PydanticValidationError):
        await handle_create_note(
            title="Invalid Category Note",
            content="Testing validation",
            category="invalid_category_name",
        )

    # 2. Empty title
    with pytest.raises(PydanticValidationError):
        await handle_create_note(
            title="   ",
            content="Testing validation",
        )

    # 3. Invalid rating for review (> 3)
    with pytest.raises(PydanticValidationError):
        await handle_submit_review(
            item_id=str(uuid.uuid4()),
            rating=5,
        )

    # 4. Invalid date format for summary
    with pytest.raises(Exception):
        await handle_get_daily_summary(
            date="not-a-valid-date",
        )

