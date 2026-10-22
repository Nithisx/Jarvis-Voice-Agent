"""Session and conversation thread management."""

from __future__ import annotations

from typing import Any, Optional
from langchain_core.messages import BaseMessage, SystemMessage

from jarvis_brain.config import get_config
from jarvis_brain.observability.logging import get_logger

logger = get_logger("memory.session")


class SessionManager:
    """Manages thread IDs and message-history bounds for multi-turn sessions."""

    def __init__(self, default_thread_id: Optional[str] = None) -> None:
        self._default_thread_id = default_thread_id

    @property
    def current_thread_id(self) -> str:
        if self._default_thread_id:
            return self._default_thread_id
        return get_config().thread_id

    def set_thread_id(self, thread_id: str) -> None:
        self._default_thread_id = thread_id
        logger.info("Switched active conversation thread to '%s'", thread_id)

    @staticmethod
    def trim_history(messages: list[BaseMessage], max_messages: int = 20) -> list[BaseMessage]:
        """Keep system message and bounded recent messages to prevent context overflow."""
        if not messages or len(messages) <= max_messages:
            return messages

        # Preserve SystemMessage if present at start
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_msgs = [m for m in messages if not isinstance(m, SystemMessage)]

        # Keep last (max_messages - len(system_msgs)) messages
        keep_count = max(2, max_messages - len(system_msgs))
        trimmed_non_system = non_system_msgs[-keep_count:]

        return system_msgs + trimmed_non_system


# Singleton session manager
session_manager = SessionManager()

