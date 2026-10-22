"""Speech-to-text service using Moonshine Voice Tiny Streaming."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from moonshine_voice import MicTranscriber, ModelArch

# Tiny Streaming model architecture ID
MODEL_ARCH = 2
LANGUAGE = "en"

stop_event = threading.Event()


class SpeechToTextService:
    """Service providing speech recognition via Moonshine Tiny Streaming."""

    def __init__(self, model_arch: int = MODEL_ARCH, language: str = LANGUAGE) -> None:
        self.model_arch = model_arch
        self.language = language
        self._mic: Optional[MicTranscriber] = None
        self._is_loaded: bool = False
        self._is_running: bool = False
        self._on_final_callback: Optional[Callable[[str], None]] = None
        self._on_partial_callback: Optional[Callable[[str], None]] = None
        self._lock = threading.Lock()

    def _handle_partial(self, text: str) -> None:
        if self._on_partial_callback:
            try:
                self._on_partial_callback(text)
            except Exception:
                pass

    def _handle_final(self, line: Any) -> None:
        transcript = ""
        if hasattr(line, "text"):
            transcript = line.text.strip()
        elif isinstance(line, str):
            transcript = line.strip()

        if transcript and self._on_final_callback:
            try:
                self._on_final_callback(transcript)
            except Exception:
                pass

    def load(self) -> None:
        """Load Moonshine model into memory."""
        with self._lock:
            if not self._is_loaded:
                self._mic = (
                    MicTranscriber()
                    .language(self.language)
                    .model_arch(self.model_arch)
                    .on_text(self._handle_partial)
                    .on_line(self._handle_final)
                )
                self._mic.load()
                self._is_loaded = True

    def start(
        self,
        on_final: Callable[[str], None],
        on_partial: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Start listening to microphone input."""
        self._on_final_callback = on_final
        self._on_partial_callback = on_partial

        if not self._is_loaded:
            self.load()

        with self._lock:
            if not self._is_running and self._mic:
                self._mic.start()
                self._is_running = True

    def mute(self, is_muted: bool = True) -> None:
        """Mute or unmute microphone to avoid feedback during TTS playback."""
        with self._lock:
            if self._mic and hasattr(self._mic, "mute"):
                try:
                    self._mic.mute(is_muted)
                except Exception:
                    pass

    def stop(self) -> None:
        """Stop microphone capture."""
        with self._lock:
            if self._is_running and self._mic:
                try:
                    self._mic.stop()
                except Exception:
                    pass
                self._is_running = False

    def close(self) -> None:
        """Clean up audio streams and resources."""
        self.stop()
        with self._lock:
            if self._mic and hasattr(self._mic, "close"):
                try:
                    self._mic.close()
                except Exception:
                    pass
            self._mic = None
            self._is_loaded = False


# Backward-compatible standalone CLI functions
def on_partial(text: str) -> None:
    """Display live transcription while speaking."""
    print(f"\rListening: {text:<100}", end="", flush=True)


def on_final(line: Any) -> None:
    """Receive a completed utterance for the JARVIS agent."""
    transcript = line.text.strip() if hasattr(line, "text") else str(line).strip()
    if not transcript:
        return
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] You: {transcript}")
    print("Listening...", flush=True)


def main() -> None:
    print("=" * 55)
    print("        JARVIS - LOCAL SPEECH RECOGNITION")
    print("        Moonshine Tiny Streaming")
    print("=" * 55)

    stt = SpeechToTextService(model_arch=MODEL_ARCH, language=LANGUAGE)
    try:
        print("\nLoading model...")
        stt.load()
        print("Model loaded successfully.")
        stt.start(on_final=on_final, on_partial=on_partial)
        print("Listening to your microphone. Press Ctrl+C to stop.\n")

        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping JARVIS...")
    finally:
        stop_event.set()
        stt.close()
        print("Speech recognition stopped.")


if __name__ == "__main__":
    main()
