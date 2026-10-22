"""Audio output and playback management using sounddevice."""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

from jarvis_brain.exceptions import AudioOutputError
from jarvis_brain.observability.logging import get_logger

logger = get_logger("audio_output")


class AudioOutputPlayer:
    """Manages sequential, thread-safe audio playback over sounddevice."""

    def __init__(self, default_sample_rate: int = 24000) -> None:
        self.default_sample_rate = default_sample_rate
        self._lock = threading.Lock()
        self._is_playing = False
        self._stop_event = threading.Event()

    def play(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> None:
        """Synchronously play an audio waveform (1D numpy array) without overlap."""
        sr = sample_rate or self.default_sample_rate
        if audio_data is None or len(audio_data) == 0:
            return

        with self._lock:
            self._stop_event.clear()
            self._is_playing = True
            try:
                # Ensure float32 normalized format
                if audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)

                sd.play(audio_data, samplerate=sr)
                # Wait until playback is finished or stop requested
                sd.wait()
            except Exception as exc:
                logger.error("Audio playback error: %s", exc)
                raise AudioOutputError(f"Playback failed: {exc}") from exc
            finally:
                self._is_playing = False

    async def play_async(self, audio_data: np.ndarray, sample_rate: Optional[int] = None) -> None:
        """Asynchronously play audio on a worker thread to keep the event loop responsive."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.play, audio_data, sample_rate)

    def stop(self) -> None:
        """Immediately stop currently playing audio."""
        self._stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing


# Singleton audio player
audio_player = AudioOutputPlayer()

