"""LangGraph state checkpointer management with PostgreSQL and InMemory backends."""

from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from jarvis_brain.config import get_config, get_masked_db_url
from jarvis_brain.exceptions import StateError
from jarvis_brain.observability.logging import get_logger

logger = get_logger("memory.checkpointer")


class CheckpointerManager:
    """Manages the lifecycle of LangGraph state checkpointers."""

    def __init__(self) -> None:
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._context_manager: Any = None

    async def get_checkpointer(self, force_in_memory: bool = False) -> BaseCheckpointSaver:
        """Get or initialize the configured checkpointer instance."""
        if self._checkpointer is not None:
            return self._checkpointer

        config = get_config()

        if force_in_memory or config.checkpointer_type == "memory" or not config.database_url:
            logger.info("Initializing in-memory conversation checkpointer.")
            self._checkpointer = MemorySaver()
            return self._checkpointer

        # PostgreSQL-backed checkpointer
        logger.info(
            "Connecting to PostgreSQL checkpointer (%s)...",
            get_masked_db_url(),
        )
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            # AsyncPostgresSaver.from_conn_string returns an async context manager
            self._context_manager = AsyncPostgresSaver.from_conn_string(config.database_url)
            self._checkpointer = await self._context_manager.__aenter__()
            await self._checkpointer.setup()
            logger.info("PostgreSQL conversation checkpointer initialized and tables verified successfully.")
            return self._checkpointer
        except Exception as exc:
            logger.warning(
                "Failed to connect to PostgreSQL checkpointer (%s). Falling back to in-memory checkpointer.",
                exc,
            )
            self._checkpointer = MemorySaver()
            return self._checkpointer

    async def close(self) -> None:
        """Close persistent database checkpointer connections."""
        if self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning("Error closing checkpointer context: %s", exc)
            self._context_manager = None
        self._checkpointer = None
        logger.info("Checkpointer closed cleanly.")


# Singleton checkpointer manager
checkpointer_manager = CheckpointerManager()
