"""Safety tests for tool authorization and argument validation policies."""

import pytest

from jarvis_brain.agent.policies import PolicyViolationError, validate_tool_call_request


def test_reject_unauthorized_tool():
    """Verify tool calls to unregistered tools are rejected."""
    allowed = {"search_web", "find_notes"}
    with pytest.raises(PolicyViolationError) as exc_info:
        validate_tool_call_request("delete_database", {}, allowed)
    assert "Unauthorized tool call" in str(exc_info.value)


def test_allow_registered_tool():
    """Verify registered tools with valid arguments pass validation."""
    allowed = {"search_web", "find_notes"}
    # Should not raise
    validate_tool_call_request("search_web", {"query": "English idioms"}, allowed)


def test_reject_oversized_arguments():
    """Verify oversized arguments (context stuffing / buffer attacks) are rejected."""
    allowed = {"search_web"}
    oversized_query = "a" * 25000
    with pytest.raises(PolicyViolationError) as exc_info:
        validate_tool_call_request("search_web", {"query": oversized_query}, allowed)
    assert "exceeds maximum allowed length" in str(exc_info.value)

