"""LangGraph nodes for reasoning, tool execution, and response formatting."""

from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from jarvis_brain.agent.policies import validate_tool_call_request
from jarvis_brain.agent.prompts import JARVIS_SYSTEM_PROMPT
from jarvis_brain.agent.state import AgentState
from jarvis_brain.memory.session_manager import session_manager
from jarvis_brain.observability.logging import get_logger
from jarvis_brain.voice.speech_formatter import clean_for_speech

logger = get_logger("nodes")


def create_reasoning_node(model: Any) -> Any:
    """Create the DeepSeek reasoning node that decides whether to respond directly or invoke tools."""

    async def reasoning_node(state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        step_count = state.get("step_count", 0)

        # Ensure SystemMessage is at the start
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=JARVIS_SYSTEM_PROMPT)] + messages

        # Trim conversation history to prevent context overflow
        trimmed_messages = session_manager.trim_history(messages)

        logger.info("Invoking DeepSeek reasoning node (step %d)...", step_count)
        response = await model.ainvoke(trimmed_messages)

        return {
            "messages": [response],
            "step_count": step_count + 1,
        }

    return reasoning_node


def create_tools_node(tools: Sequence[BaseTool]) -> Any:
    """Create the tool execution node executing validated MCP tools."""
    tools_by_name = {t.name: t for t in tools}
    allowed_tool_names = set(tools_by_name.keys())

    async def tools_node(state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        if not tool_calls:
            return {}

        tool_messages: list[ToolMessage] = []
        for tc in tool_calls:
            tool_name = tc.get("name")
            tool_args = tc.get("args", {})
            call_id = tc.get("id", "call_default")

            logger.info("Processing tool call [%s] (id=%s)...", tool_name, call_id)

            try:
                # Security policy check
                validate_tool_call_request(tool_name, tool_args, allowed_tool_names)
                tool = tools_by_name[tool_name]
                result = await tool.ainvoke(tool_args)
            except Exception as exc:
                logger.error("Tool execution failed for [%s]: %s", tool_name, exc)
                result = f"Error: Tool '{tool_name}' failed with: {exc}"

            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    name=tool_name,
                    tool_call_id=call_id,
                )
            )

        return {"messages": tool_messages}

    return tools_node


def format_response_node(state: AgentState) -> dict[str, Any]:
    """Extract and format the final spoken text from the last assistant message."""
    messages = state.get("messages", [])
    raw_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            raw_content = str(msg.content)
            break

    spoken_text = clean_for_speech(raw_content)
    logger.info("Final spoken response formatted: '%s'", spoken_text[:100] + "..." if len(spoken_text) > 100 else spoken_text)

    return {"final_speech_text": spoken_text}

