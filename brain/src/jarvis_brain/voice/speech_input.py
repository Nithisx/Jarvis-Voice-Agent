"""Speech input manager bridging Moonshine STT to local wake-word gating and command queue."""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from jarvis_brain.config import find_project_root, get_config
from jarvis_brain.exceptions import STTError
from jarvis_brain.observability.logging import get_logger
from jarvis_brain.voice.command_queue import VoiceCommand, command_queue
from jarvis_brain.voice.state import MicGateState, voice_state_manager
from jarvis_brain.voice.wake_word import WakeWordDetector, default_wake_detector

logger = get_logger("speech_input")


class SpeechInputManager:
    """Manages Moonshine STT listening, local wake-word gating, and 3-second endpointing."""

    def __init__(self) -> None:
        self._stt_service: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_active = False
        self._lock = threading.Lock()

        # Wake word detector
        self._wake_detector: WakeWordDetector = default_wake_detector

        # Rolling turn buffer
        self._committed_segments: list[str] = []
        self._current_partial: str = ""
        self._last_speech_time: float = 0.0

        # Background monitor task
        self._monitor_task: Optional[asyncio.Task] = None

    def _get_stt_service(self) -> Any:
        if self._stt_service is None:
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
                self._wake_detector = WakeWordDetector(config.wake_phrases)
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

    def _on_audio_activity_callback(self, rms: float) -> None:
        """Audio callback measuring physical microphone frame energy."""
        config = get_config()
        if rms >= config.energy_threshold:
            # Physical voice activity detected in audio frame
            with self._lock:
                self._last_speech_time = time.time()

    def _on_partial_transcript_callback(self, text: str) -> None:
        """Called by Moonshine with in-progress live transcript updates."""
        clean_partial = text.strip()
        if not clean_partial:
            return

        # ── Live transcript feedback on terminal ──
        gate = voice_state_manager.gate_state.name
        print(f"\r🎙️  [{gate}] Hearing: {clean_partial:<80}", end="", flush=True)

        with self._lock:
            self._current_partial = clean_partial
            self._last_speech_time = time.time()

            # Check for wake word in accumulated speech
            full_provisional = " ".join(self._committed_segments + [self._current_partial]).strip()
            if self._wake_detector.has_wake_word(full_provisional):
                if voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD:
                    voice_state_manager.set_gate_state(MicGateState.CAPTURING_COMMAND)
                    print()  # newline after the partial line
                    logger.info("Wake word provisionally detected in partial: '%s'", full_provisional)

    def _on_final_transcript_callback(self, text: str) -> None:
        """Called by Moonshine when an utterance segment is committed."""
        clean_final = text.strip()
        if not clean_final:
            return

        # ── Committed segment feedback on terminal ──
        gate = voice_state_manager.gate_state.name
        print(f"\n✅  [{gate}] Committed: {clean_final}")

        with self._lock:
            self._committed_segments.append(clean_final)
            self._current_partial = ""
            self._last_speech_time = time.time()

            full_committed = " ".join(self._committed_segments).strip()
            if self._wake_detector.has_wake_word(full_committed):
                if voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD:
                    voice_state_manager.set_gate_state(MicGateState.CAPTURING_COMMAND)
                    logger.info("Wake word confirmed in committed segment: '%s'", full_committed)

    async def _endpoint_monitor_loop(self) -> None:
        """Continuous background monitor evaluating the 3-second silence endpoint."""
        config = get_config()
        silence_timeout = config.silence_timeout_seconds

        while self._is_active:
            await asyncio.sleep(0.05)

            with self._lock:
                # Do not evaluate endpoint while muted for playback
                if voice_state_manager.gate_state == MicGateState.MUTED_FOR_PLAYBACK:
                    continue

                now = time.time()
                elapsed_silence = now - self._last_speech_time if self._last_speech_time > 0 else 0.0
                has_content = bool(self._committed_segments or self._current_partial)

                if not has_content:
                    continue

                # Case 1: Active command capture with >= 3.0 seconds of continuous silence
                if voice_state_manager.gate_state == MicGateState.CAPTURING_COMMAND:
                    if elapsed_silence >= silence_timeout:
                        # 3 seconds of actual silence have elapsed
                        full_text = " ".join(self._committed_segments).strip()
                        if self._current_partial:
                            full_text = f"{full_text} {self._current_partial}".strip()

                        logger.info(
                            "Silence endpoint reached (%.1fs). Evaluating candidate: '%s'",
                            elapsed_silence,
                            full_text,
                        )

                        # Extract clean command, stripping wake phrase and preceding noise
                        extracted = self._wake_detector.extract_command(full_text)
                        if extracted:
                            print(f"\n📤  Command enqueued: '{extracted}'")
                            logger.info("Valid command extracted: '%s'", extracted)
                            command_queue.enqueue(extracted)
                        else:
                            print(f"\n⚠️  Wake word only, no command found: '{full_text}'")
                            logger.info(
                                "Turn discarded locally: wake word present but no command followed ('%s'). Zero LLM calls.",
                                full_text,
                            )

                        # Reset turn buffer and return gate state
                        self._committed_segments.clear()
                        self._current_partial = ""
                        self._last_speech_time = 0.0
                        voice_state_manager.set_gate_state(MicGateState.LISTENING_FOR_WAKE_WORD)

                # Case 2: Listening for wake word, speech occurred without wake word
                elif voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD:
                    if elapsed_silence >= silence_timeout:
                        # Discard background / unrelated speech locally without calling LLM
                        unrelated = " ".join(self._committed_segments).strip()
                        if self._current_partial:
                            unrelated = f"{unrelated} {self._current_partial}".strip()

                        if unrelated:
                            print(f"\n🚫  Discarded (no wake word): '{unrelated}'")
                            logger.info("Discarded speech without wake word ('%s'). Zero LLM calls.", unrelated)

                        self._committed_segments.clear()
                        self._current_partial = ""
                        self._last_speech_time = 0.0

    def start_listening(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start microphone transcription and endpoint monitor."""
        self._loop = loop or asyncio.get_event_loop()
        stt = self._get_stt_service()
        logger.info("Starting microphone listener with local wake-word gate...")
        stt.start(
            on_final=self._on_final_transcript_callback,
            on_partial=self._on_partial_transcript_callback,
            on_audio_activity=self._on_audio_activity_callback,
        )
        self._is_active = True
        voice_state_manager.set_gate_state(MicGateState.LISTENING_FOR_WAKE_WORD)

        # Start asynchronous endpoint monitor
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = self._loop.create_task(self._endpoint_monitor_loop())

        logger.info("Microphone listener active and monitoring for 'Hey Jarvis' / 'Jarvis'.")

    def pause_listening(self) -> None:
        """Mute microphone during TTS response playback to prevent audio feedback."""
        with self._lock:
            voice_state_manager.set_gate_state(MicGateState.MUTED_FOR_PLAYBACK)
            self._current_partial = ""
        if self._stt_service:
            self._stt_service.mute(True)

    def resume_listening(self) -> None:
        """Unmute microphone after playback completes and clear stale reverberation events."""
        with self._lock:
            self._committed_segments.clear()
            self._current_partial = ""
            self._last_speech_time = 0.0
            voice_state_manager.set_gate_state(MicGateState.LISTENING_FOR_WAKE_WORD)

        if self._stt_service:
            self._stt_service.mute(False)

    async def get_next_command(self) -> VoiceCommand:
        """Await the next validated, finalized user command from the FIFO queue."""
        return await command_queue.get()

    async def get_next_utterance(self) -> str:
        """Backward-compatible helper returning the command text."""
        cmd = await self.get_next_command()
        return cmd.command_text

    def stop(self) -> None:
        """Stop listening and clean up."""
        self._is_active = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None
        if self._stt_service:
            self._stt_service.stop()

    def close(self) -> None:
        """Release all microphone streams and resources."""
        self.stop()
        if self._stt_service:
            self._stt_service.close()
            self._stt_service = None
        self._is_active = False


# Singleton instance
speech_input_manager = SpeechInputManager()
