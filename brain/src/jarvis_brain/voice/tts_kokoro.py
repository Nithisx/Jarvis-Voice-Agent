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

    def synthesize_full_waveform(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> np.ndarray:
        """Synthesize the complete response text and assemble into a single continuous 1D waveform.

        Avoids artificial sentence gaps by performing full synthesis before playback.
        """
        if not self._is_loaded:
            self.load()

        cleaned = clean_for_speech(text)
        if not cleaned:
            return np.zeros(0, dtype=np.float32)

        config = get_config()
        if len(cleaned) > config.max_response_chars:
            logger.warning(
                "Response length (%d chars) exceeds max_response_chars (%d). Synthesizing full text in memory.",
                len(cleaned),
                config.max_response_chars,
            )

        # Split into natural sentences for Kokoro generation, then concatenate all chunks
        sentences = split_into_sentences(cleaned)
        if not sentences:
            sentences = [cleaned]

        all_segments: list[np.ndarray] = []
        for sentence in sentences:
            segments = self.synthesize(sentence, voice=voice, speed=speed)
            for seg in segments:
                if seg is not None and len(seg) > 0:
                    arr = seg.astype(np.float32).flatten()
                    all_segments.append(arr)

        if not all_segments:
            return np.zeros(0, dtype=np.float32)

        # Assemble and concatenate all compatible waveforms into one continuous audio track
        full_audio = np.concatenate(all_segments, axis=0)

        # Gentle normalization / clipping to ensure strictly valid audio amplitudes [-1.0, 1.0]
        max_val = np.max(np.abs(full_audio)) if len(full_audio) > 0 else 0.0
        if max_val > 1.0:
            full_audio = full_audio / max_val

        return full_audio.astype(np.float32)

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        on_start: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        """Synthesize the complete response before playing, ensuring smooth gapless playback."""
        full_audio = self.synthesize_full_waveform(text, voice=voice, speed=speed)
        if len(full_audio) == 0:
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass
            return

        # Playback begins ONLY after 100% of the audio is synthesized
        if on_start:
            try:
                on_start()
            except Exception:
                pass

        try:
            # One continuous playback operation for the fully assembled waveform
            audio_player.play(full_audio, sample_rate=24000)
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
