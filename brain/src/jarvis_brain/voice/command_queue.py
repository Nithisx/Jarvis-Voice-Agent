"""Bounded FIFO command queue for multi-turn command capture and sequential execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis_brain.config import get_config
from jarvis_brain.observability.logging import get_logger
from jarvis_brain.voice.state import WorkerState, voice_state_manager

logger = get_logger("command_queue")


@dataclass
class VoiceCommand:
    """Represents a validated, finalized user voice command."""
    command_id: str
    command_text: str
    captured_at: float
    enqueued_at: float
    thread_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class CommandQueue:
    """Bounded FIFO queue managing command ingestion and diagnostic metrics."""

    def __init__(self, maxsize: Optional[int] = None) -> None:
        self.maxsize = maxsize or get_config().command_queue_max_size
        self._queue: asyncio.Queue[VoiceCommand] = asyncio.Queue(maxsize=self.maxsize)
        self._total_enqueued = 0
        self._total_processed = 0
        self._total_overflows = 0
        self._has_pending_overflow_notice = False

    @property
    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def has_pending_overflow_notice(self) -> bool:
        return self._has_pending_overflow_notice

    def clear_overflow_notice(self) -> None:
        self._has_pending_overflow_notice = False

    def enqueue(self, text: str, thread_id: Optional[str] = None) -> Optional[VoiceCommand]:
        """Attempt to enqueue a command in a non-blocking manner.

        Returns the VoiceCommand if accepted, or None if the queue was full.
        """
        config = get_config()
        active_thread = thread_id or config.thread_id
        cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
        now = time.time()

        cmd = VoiceCommand(
            command_id=cmd_id,
            command_text=text,
            captured_at=now,
            enqueued_at=now,
            thread_id=active_thread,
        )

        try:
            self._queue.put_nowait(cmd)
            self._total_enqueued += 1
            logger.info(
                "Command [%s] enqueued: '%s' (Queue depth: %d/%d)",
                cmd_id,
                text,
                self.qsize,
                self.maxsize,
            )
            # If worker is idle, show QUEUED
            if voice_state_manager.worker_state == WorkerState.IDLE:
                voice_state_manager.set_worker_state(WorkerState.QUEUED)
            return cmd
        except asyncio.QueueFull:
            self._total_overflows += 1
            self._has_pending_overflow_notice = True
            logger.warning(
                "Command queue full (capacity %d). Dropped command [%s]: '%s'",
                self.maxsize,
                cmd_id,
                text,
            )
            return None

    async def get(self) -> VoiceCommand:
        """Wait for and retrieve the next FIFO command."""
        cmd = await self._queue.get()
        return cmd

    def mark_processed(self, cmd: VoiceCommand) -> None:
        """Mark a command as successfully completed."""
        self._total_processed += 1
        wait_time = time.time() - cmd.enqueued_at
        logger.info(
            "Command [%s] completed in worker (Wait in queue: %.2fs, Remaining in queue: %d)",
            cmd.command_id,
            wait_time,
            self.qsize,
        )

    def get_metrics(self) -> dict[str, Any]:
        """Return structured diagnostic metrics for the command queue."""
        return {
            "current_depth": self.qsize,
            "max_capacity": self.maxsize,
            "total_enqueued": self._total_enqueued,
            "total_processed": self._total_processed,
            "total_overflows": self._total_overflows,
        }


# Singleton queue instance
command_queue = CommandQueue()

