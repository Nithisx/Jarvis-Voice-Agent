"""Speech input manager bridging Moonshine STT to the asyncio transcript queue."""

from __future__ import annotations

import asyncio
import threading
import sys
from pathlib import Path
from typing import Callable, Optional

from jarvis_brain.config import find_project_root, get_config
from jarvis_brain.exceptions import STTError
from jarvis_brain.observability.logging import get_logger

logger = get_logger("speech_input")


class SpeechInputManager:
    """Manages Moonshine STT listening and queues finalized transcripts for processing."""

    def __init__(self) -> None:
        self._stt_service: Any = None
        self._transcript_queue: asyncio.Queue[str] = asyncio.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_active = False
        self._last_transcript = ""
        self._lock = threading.Lock()

    def _get_stt_service(self) -> Any:
        if self._stt_service is None:
            # Import from root Speach2text.py
            root = find_project_root()
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))

            try:
                from Speach2text import SpeechToTextService
                config = get_config()
                self._stt_service = SpeechToTextService(
                    model_arch=config.stt_model_arch,
                    language=config.stt_language,
                )
            except Exception as exc:
                logger.error("Failed to import or initialize SpeechToTextService: %s", exc)
                raise STTError(f"Moonshine STT initialization failed: {exc}") from exc
        return self._stt_service

    def load(self) -> None:
        """Preload the Moonshine Tiny Streaming model."""
        stt = self._get_stt_service()
        logger.info("Preloading Moonshine STT model...")
        stt.load()
        logger.info("Moonshine STT model preloaded successfully.")

    def _on_final_transcript_callback(self, text: str) -> None:
        """Thread-safe callback invoked by Moonshine when an utterance is finalized."""
        clean_text = text.strip()
        if not clean_text:
            return

        with self._lock:
            # Deduplicate immediate identical transcripts
            if clean_text == self._last_transcript:
                return
            self._last_transcript = clean_text

        logger.info("User utterance captured: '%s'", clean_text)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._transcript_queue.put_nowait, clean_text)

    def start_listening(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start microphone transcription."""
        self._loop = loop or asyncio.get_event_loop()
        stt = self._get_stt_service()
        logger.info("Starting microphone listener...")
        stt.start(on_final=self._on_final_transcript_callback)
        self._is_active = True
        logger.info("Microphone listener active.")

    def pause_listening(self) -> None:
        """Mute microphone during TTS response playback to prevent audio feedback."""
        if self._stt_service:
            self._stt_service.mute(True)

    def resume_listening(self) -> None:
        """Unmute microphone after playback completes."""
        with self._lock:
            # Clear last transcript to avoid stale state
            self._last_transcript = ""
        if self._stt_service:
            self._stt_service.mute(False)

    async def get_next_utterance(self) -> str:
        """Await the next finalized user transcript from the queue."""
        return await self._transcript_queue.get()

    def stop(self) -> None:
        """Stop listening and clean up."""
        if self._stt_service:
            self._stt_service.stop()
            self._is_active = False

    def close(self) -> None:
        """Release all microphone streams and resources."""
        if self._stt_service:
            self._stt_service.close()
            self._stt_service = None
            self._is_active = False


# Singleton instance
speech_input_manager = SpeechInputManager()

