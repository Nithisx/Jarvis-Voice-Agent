"""Continuous voice-to-voice interaction loop for JARVIS."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from jarvis_brain.observability.logging import get_logger
from jarvis_brain.observability.metrics import TurnMetrics, metrics_collector
from jarvis_brain.voice.speech_input import speech_input_manager
from jarvis_brain.voice.tts_kokoro import tts_service

logger = get_logger("voice_loop")


class VoiceLoop:
    """Manages the full-duplex/half-duplex continuous voice interaction loop."""

    def __init__(self) -> None:
        self._is_running = False
        self._shutdown_event = asyncio.Event()

    async def run(self, brain: Optional[Any] = None) -> None:
        """Run the continuous voice loop until cancelled or shutdown."""
        from jarvis_brain.agent.graph import jarvis_brain

        active_brain = brain or jarvis_brain
        self._is_running = True
        self._shutdown_event.clear()
        logger.info("Voice-to-voice interaction loop started.")

        try:
            while self._is_running and not self._shutdown_event.is_set():
                # 1. Wait for next finalized user utterance
                try:
                    transcript = await speech_input_manager.get_next_utterance()
                except asyncio.CancelledError:
                    break

                if not transcript or not transcript.strip():
                    continue

                clean_text = transcript.strip()
                logger.info("Processing utterance: '%s'", clean_text)
                t_turn_start = time.time()

                # 2. Pause microphone to prevent acoustic feedback during processing & speech
                speech_input_manager.pause_listening()

                try:
                    # 3. Reason using compiled LangGraph brain
                    t_llm_start = time.time()
                    spoken_response = await active_brain.respond(clean_text)
                    llm_duration = time.time() - t_llm_start

                    # 4. Synthesize and speak response aloud using local Kokoro-82M
                    t_tts_start = time.time()
                    await tts_service.speak_async(spoken_response)
                    tts_duration = time.time() - t_tts_start

                except Exception as exc:
                    logger.error("Error during voice turn: %s", exc, exc_info=True)
                    # Friendly fallback spoken notification
                    try:
                        await tts_service.speak_async("I ran into an issue processing that. Could you say that again?")
                    except Exception:
                        pass
                finally:
                    # 5. Clear stale events and resume listening
                    # Short grace period for speaker room reverberation to settle
                    await asyncio.sleep(0.3)
                    speech_input_manager.resume_listening()
                    logger.info("Resumed microphone listening.")

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Voice loop cancelled.")
        finally:
            self._is_running = False
            logger.info("Voice loop stopped.")

    def stop(self) -> None:
        """Signal the voice loop to terminate."""
        self._is_running = False
        self._shutdown_event.set()


# Singleton loop instance
voice_loop = VoiceLoop()
