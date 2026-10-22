"""Conditional routing logic for the LangGraph agent graph."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage
from jarvis_brain.agent.state import AgentState
from jarvis_brain.config import get_config
from jarvis_brain.observability.logging import get_logger

logger = get_logger("routing")


def should_continue(state: AgentState) -> Literal["tools", "format_response", "__end__"]:
    """Determine whether to route to MCP tools, format response, or terminate."""
    messages = state.get("messages", [])
    if not messages:
        return "__end__"

    last_message = messages[-1]
    step_count = state.get("step_count", 0)
    config = get_config()

    # Check for tool call requests from the model
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        if step_count >= config.max_tool_steps:
            logger.warning(
                "Max tool steps limit (%d) reached for turn %s. Terminating tool loop.",
                config.max_tool_steps,
                state.get("turn_id", "unknown"),
            )
            return "format_response"
        return "tools"

    return "format_response"

