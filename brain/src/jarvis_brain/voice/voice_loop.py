"""Continuous voice-to-voice interaction loop with concurrent command capture and sequential execution."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from jarvis_brain.observability.logging import get_logger
from jarvis_brain.observability.metrics import TurnMetrics, metrics_collector
from jarvis_brain.voice.command_queue import command_queue
from jarvis_brain.voice.speech_input import speech_input_manager
from jarvis_brain.voice.state import WorkerState, voice_state_manager
from jarvis_brain.voice.tts_kokoro import tts_service

logger = get_logger("voice_loop")


class VoiceLoop:
    """Manages the agent execution worker processing queued commands sequentially."""

    def __init__(self, reverberation_delay: float = 0.3) -> None:
        self.reverberation_delay = reverberation_delay
        self._is_running = False
        self._shutdown_event = asyncio.Event()

    async def run(self, brain: Optional[Any] = None) -> None:
        """Run the sequential agent worker loop until cancelled or shutdown."""
        from jarvis_brain.agent.graph import jarvis_brain

        active_brain = brain or jarvis_brain
        self._is_running = True
        self._shutdown_event.clear()
        voice_state_manager.set_worker_state(WorkerState.IDLE)
        logger.info("Voice worker started (concurrent wake capture enabled, sequential execution).")

        try:
            while self._is_running and not self._shutdown_event.is_set():
                # 1. Wait for next finalized user command from the FIFO queue
                try:
                    command = await speech_input_manager.get_next_command()
                except asyncio.CancelledError:
                    break

                if not command or not command.command_text.strip():
                    continue

                clean_text = command.command_text.strip()
                logger.info(
                    "Worker processing command [%s] on thread [%s]: '%s'",
                    command.command_id,
                    command.thread_id,
                    clean_text,
                )
                t_turn_start = time.time()

                # State: PROCESSING
                # Note: Microphone listening remains active during LLM/MCP processing
                # to allow concurrent capture of subsequent commands into the queue!
                voice_state_manager.set_worker_state(WorkerState.PROCESSING)

                try:
                    # 2. Reason using compiled LangGraph brain (complete non-streaming response)
                    t_llm_start = time.time()
                    spoken_response = await active_brain.respond(clean_text, thread_id=command.thread_id)
                    llm_duration = time.time() - t_llm_start

                    # 3. State: SPEAKING
                    # Microphone is paused during TTS playback (half-duplex to prevent acoustic self-triggering)
                    voice_state_manager.set_worker_state(WorkerState.SPEAKING)
                    speech_input_manager.pause_listening()

                    t_tts_start = time.time()
                    # Plays complete assembled waveform without gaps
                    await tts_service.speak_async(spoken_response)
                    tts_duration = time.time() - t_tts_start

                    # 4. Check for pending queue overflow notice
                    if command_queue.has_pending_overflow_notice:
                        overflow_msg = "My command queue is full right now. Please wait a moment."
                        logger.info("Speaking queue overflow notice...")
                        await tts_service.speak_async(overflow_msg)
                        command_queue.clear_overflow_notice()

                    command_queue.mark_processed(command)

                except Exception as exc:
                    logger.error("Error during command processing [%s]: %s", command.command_id, exc, exc_info=True)
                    voice_state_manager.set_worker_state(WorkerState.RECOVERING)
                    speech_input_manager.pause_listening()

                    # Friendly fallback spoken notification
                    try:
                        await tts_service.speak_async("I ran into an issue processing that. Could you say that again?")
                    except Exception:
                        pass
                finally:
                    # 5. Clear stale acoustic reverberation and resume listening
                    if self.reverberation_delay > 0:
                        await asyncio.sleep(self.reverberation_delay)
                    speech_input_manager.resume_listening()
                    logger.info("Resumed microphone listening for wake word.")

                    # Update worker state
                    next_worker_state = WorkerState.QUEUED if command_queue.qsize > 0 else WorkerState.IDLE
                    voice_state_manager.set_worker_state(next_worker_state)

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Voice loop cancelled.")
        finally:
            self._is_running = False
            voice_state_manager.set_worker_state(WorkerState.STOPPED)
            logger.info("Voice loop stopped.")

    def stop(self) -> None:
        """Signal the voice loop to terminate."""
        self._is_running = False
        self._shutdown_event.set()


# Singleton loop instance
voice_loop = VoiceLoop()
