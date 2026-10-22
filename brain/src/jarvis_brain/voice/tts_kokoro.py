"""Local Kokoro-82M Text-to-Speech service using KPipeline."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Iterator, Optional

import numpy as np

from jarvis_brain.config import get_config
from jarvis_brain.exceptions import TTSError
from jarvis_brain.observability.logging import get_logger
from jarvis_brain.voice.audio_output import audio_player
from jarvis_brain.voice.speech_formatter import clean_for_speech, split_into_sentences

logger = get_logger("tts_kokoro")


class KokoroTTSService:
    """Manages the local Kokoro-82M TTS model and incremental audio synthesis."""

    def __init__(
        self,
        lang_code: str = "a",
        voice: str = "af_heart",
        speed: float = 1.0,
        device: str = "cpu",
    ) -> None:
        self.lang_code = lang_code
        self.default_voice = voice
        self.default_speed = speed
        self.device = device
        self._pipeline: Any = None
        self._is_loaded = False
        self._lock = threading.Lock()

    def load(self) -> None:
        """Load Kokoro-82M pipeline and weights into memory."""
        with self._lock:
            if not self._is_loaded:
                logger.info(
                    "Loading Kokoro-82M TTS pipeline (lang=%s, voice=%s, device=%s)...",
                    self.lang_code,
                    self.default_voice,
                    self.device,
                )
                try:
                    from kokoro import KPipeline
                    self._pipeline = KPipeline(
                        lang_code=self.lang_code,
                        device=self.device,
                    )
                    self._is_loaded = True
                    logger.info("Kokoro-82M TTS pipeline loaded successfully.")
                except Exception as exc:
                    logger.error("Failed to load Kokoro-82M pipeline: %s", exc)
                    raise TTSError(f"Kokoro-82M initialization failed: {exc}") from exc

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> list[np.ndarray]:
        """Synthesize text into a list of 1D numpy audio waveforms (24kHz)."""
        if not self._is_loaded:
            self.load()

        cleaned = clean_for_speech(text)
        if not cleaned:
            return []

        active_voice = voice or self.default_voice
        active_speed = speed or self.default_speed

        audio_segments: list[np.ndarray] = []
        try:
            generator = self._pipeline(
                cleaned,
                voice=active_voice,
                speed=active_speed,
                split_pattern=r"\n+",
            )
            for res in generator:
                if hasattr(res, "audio") and res.audio is not None:
                    arr = res.audio
                    if hasattr(arr, "cpu"):
                        arr = arr.cpu().numpy()
                    elif not isinstance(arr, np.ndarray):
                        arr = np.array(arr, dtype=np.float32)
                    audio_segments.append(arr)
        except Exception as exc:
            logger.error("Kokoro synthesis error: %s", exc)
            raise TTSError(f"Speech synthesis error: {exc}") from exc

        return audio_segments

    async def synthesize_async(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> list[np.ndarray]:
        """Asynchronously synthesize text without blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.synthesize,
            text,
            voice,
            speed,
        )

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        on_start: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        """Clean, synthesize, and incrementally play text through the speaker."""
        sentences = split_into_sentences(text)
        if not sentences:
            return

        if on_start:
            try:
                on_start()
            except Exception:
                pass

        try:
            for sentence in sentences:
                segments = self.synthesize(sentence, voice=voice, speed=speed)
                for segment in segments:
                    audio_player.play(segment, sample_rate=24000)
        finally:
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

    async def speak_async(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        on_start: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        """Asynchronously speak text without blocking the main event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self.speak,
            text,
            voice,
            speed,
            on_start,
            on_done,
        )


# Singleton instance
tts_service = KokoroTTSService()
