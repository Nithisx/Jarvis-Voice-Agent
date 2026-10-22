"""Conversation state definitions for the LangGraph agent."""

from __future__ import annotations

from typing import Annotated, Any, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph conversation state containing conversation history and turn metadata."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    step_count: int
    turn_id: str
    final_speech_text: str | None

