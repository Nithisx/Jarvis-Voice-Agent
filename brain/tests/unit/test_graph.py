"""Unit tests for LangGraph nodes, routing, and response formatting."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from jarvis_brain.agent.nodes import format_response_node, create_reasoning_node, create_tools_node
from jarvis_brain.agent.routing import should_continue
from jarvis_brain.agent.state import AgentState


def test_routing_with_no_messages():
    """Verify routing gracefully ends when state is empty."""
    state: AgentState = {"messages": [], "step_count": 0}
    decision = should_continue(state)
    assert decision == "__end__"


def test_routing_to_tools():
    """Verify routing selects tools when AIMessage has tool_calls."""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "search_web", "args": {"query": "python"}, "id": "call_1"}],
    )
    state: AgentState = {"messages": [msg], "step_count": 0}
    decision = should_continue(state)
    assert decision == "tools"


def test_routing_to_format_response():
    """Verify routing proceeds to response formatting when no tool calls are present."""
    msg = AIMessage(content="Hello! How are you?")
    state: AgentState = {"messages": [msg], "step_count": 1}
    decision = should_continue(state)
    assert decision == "format_response"


def test_routing_tool_limit_cutoff():
    """Verify routing cuts off tool execution when max_tool_steps is reached."""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "search_web", "args": {"query": "python"}, "id": "call_1"}],
    )
    state: AgentState = {"messages": [msg], "step_count": 6}
    decision = should_continue(state)
    assert decision == "format_response"


@pytest.mark.asyncio
async def test_format_response_node():
    """Verify format_response_node cleans text for speech generation."""
    state: AgentState = {
        "messages": [
            HumanMessage(content="Explain what API means"),
            AIMessage(content="An **API** is an `Application Programming Interface`."),
        ],
        "step_count": 1,
    }
    result = format_response_node(state)
    assert "final_speech_text" in result
    speech_text = result["final_speech_text"]
    assert "**" not in speech_text
    assert "`" not in speech_text
    assert "API" in speech_text


@pytest.mark.asyncio
async def test_tools_node_execution():
    """Verify create_tools_node calls registered tools."""

    @tool
    def sample_tool(query: str) -> str:
        """Sample mock tool."""
        return f"Result for {query}"

    tools_node = create_tools_node([sample_tool])

    ai_msg = AIMessage(
        content="",
        tool_calls=[{"name": "sample_tool", "args": {"query": "test"}, "id": "call_123"}],
    )
    state: AgentState = {"messages": [ai_msg], "step_count": 1}

    result = await tools_node(state)
    tool_messages = result.get("messages", [])
    assert len(tool_messages) == 1
    assert isinstance(tool_messages[0], ToolMessage)
    assert "Result for test" in tool_messages[0].content
