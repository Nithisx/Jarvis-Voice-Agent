"""Explicit state model for JARVIS voice assistant.

Separates microphone wake-word gating state from agent processing and TTS playback,
allowing concurrent command capture while an earlier request is being processed.
"""

from __future__ import annotations

import enum
import threading
from typing import Callable, Optional

from jarvis_brain.observability.logging import get_logger

logger = get_logger("voice.state")


class MicGateState(str, enum.Enum):
    """States of the microphone listening and wake-word gating pipeline."""
    LISTENING_FOR_WAKE_WORD = "LISTENING_FOR_WAKE_WORD"
    CAPTURING_COMMAND = "CAPTURING_COMMAND"
    MUTED_FOR_PLAYBACK = "MUTED_FOR_PLAYBACK"
    STOPPING = "STOPPING"


class WorkerState(str, enum.Enum):
    """States of the agent worker, LangGraph execution, and TTS playback."""
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class VoiceStateManager:
    """Thread-safe coordinator for the voice assistant's concurrent states."""

    def __init__(self) -> None:
        self._gate_state = MicGateState.LISTENING_FOR_WAKE_WORD
        self._worker_state = WorkerState.IDLE
        self._lock = threading.Lock()
        self._listeners: list[Callable[[MicGateState, WorkerState], None]] = []

    @property
    def gate_state(self) -> MicGateState:
        with self._lock:
            return self._gate_state

    @property
    def worker_state(self) -> WorkerState:
        with self._lock:
            return self._worker_state

    def set_gate_state(self, new_state: MicGateState) -> None:
        with self._lock:
            if self._gate_state != new_state:
                logger.info("Mic Gate transition: %s -> %s", self._gate_state.value, new_state.value)
                self._gate_state = new_state
                self._notify()

    def set_worker_state(self, new_state: WorkerState) -> None:
        with self._lock:
            if self._worker_state != new_state:
                logger.info("Worker transition: %s -> %s", self._worker_state.value, new_state.value)
                self._worker_state = new_state
                self._notify()

    def add_listener(self, callback: Callable[[MicGateState, WorkerState], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener(self._gate_state, self._worker_state)
            except Exception:
                pass


# Singleton state manager
voice_state_manager = VoiceStateManager()

