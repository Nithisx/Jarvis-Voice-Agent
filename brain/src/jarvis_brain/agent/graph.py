"""LangGraph StateGraph compiler and execution engine for JARVIS."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional, Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from jarvis_brain.agent.deepseek_client import create_deepseek_model
from jarvis_brain.agent.nodes import (
    create_reasoning_node,
    create_tools_node,
    format_response_node,
)
from jarvis_brain.agent.prompts import JARVIS_SYSTEM_PROMPT
from jarvis_brain.agent.routing import should_continue
from jarvis_brain.agent.state import AgentState
from jarvis_brain.config import get_config
from jarvis_brain.exceptions import JarvisError
from jarvis_brain.memory.checkpointer import checkpointer_manager
from jarvis_brain.observability.logging import get_logger
from jarvis_brain.observability.metrics import TurnMetrics, metrics_collector

logger = get_logger("graph")


def build_jarvis_graph(
    tools: Sequence[BaseTool],
    checkpointer: Optional[BaseCheckpointSaver] = None,
    custom_model: Optional[Any] = None,
) -> Any:
    """Build and compile the LangGraph execution graph."""
    model = custom_model or create_deepseek_model(tools=tools)

    reasoning_node = create_reasoning_node(model)
    tools_node = create_tools_node(tools)

    builder = StateGraph(AgentState)

    builder.add_node("reasoning", reasoning_node)
    builder.add_node("tools", tools_node)
    builder.add_node("format_response", format_response_node)

    builder.add_edge(START, "reasoning")
    builder.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "tools": "tools",
            "format_response": "format_response",
            "__end__": END,
        },
    )
    # Loop from tools back to reasoning
    builder.add_edge("tools", "reasoning")
    builder.add_edge("format_response", END)

    compiled = builder.compile(checkpointer=checkpointer)
    logger.info("JARVIS LangGraph compiled successfully.")
    return compiled


class JarvisBrain:
    """High-level runner managing the compiled LangGraph agent."""

    def __init__(self) -> None:
        self._graph: Any = None
        self._tools: list[BaseTool] = []

    async def initialize(
        self,
        tools: Optional[list[BaseTool]] = None,
        force_in_memory_checkpoint: bool = False,
        custom_model: Optional[Any] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ) -> None:
        """Initialize tools, checkpointer, and compile the graph."""
        if tools is not None:
            self._tools = tools
        else:
            from jarvis_brain.mcp.client_manager import mcp_client_manager
            self._tools = mcp_client_manager.get_tools()

        if checkpointer is not None:
            active_checkpointer = checkpointer
        elif force_in_memory_checkpoint:
            active_checkpointer = await checkpointer_manager.get_checkpointer(force_in_memory=True)
        else:
            active_checkpointer = await checkpointer_manager.get_checkpointer()

        self._graph = build_jarvis_graph(
            tools=self._tools,
            checkpointer=active_checkpointer,
            custom_model=custom_model,
        )

    async def respond(
        self,
        message: str,
        thread_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Execute the LangGraph application for a user utterance and return the spoken response."""
        if self._graph is None:
            raise JarvisError("JarvisBrain is not initialized. Call initialize() first.")

        config = get_config()
        active_thread = session_id or thread_id or config.thread_id
        turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        t_start = time.time()

        logger.info("Executing LangGraph turn [%s] on thread [%s]: '%s'", turn_id, active_thread, message)

        initial_state: dict[str, Any] = {
            "messages": [HumanMessage(content=message)],
            "step_count": 0,
            "turn_id": turn_id,
            "final_speech_text": None,
        }

        run_config = {
            "configurable": {"thread_id": active_thread},
        }

        final_output = await self._graph.ainvoke(initial_state, config=run_config)
        duration = time.time() - t_start

        spoken_text = final_output.get("final_speech_text") or "I understand."

        # Record turn metrics
        turn_metrics = TurnMetrics(
            turn_id=turn_id,
            user_transcript=message,
            llm_duration_sec=duration,
            total_latency_sec=duration,
        )
        metrics_collector.record_turn(turn_metrics)

        return spoken_text


# Singleton brain instance
jarvis_brain = JarvisBrain()
