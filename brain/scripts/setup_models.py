"""Model setup and pre-warming script for JARVIS.

Pre-downloads and verifies:
1. Moonshine Tiny Streaming speech-to-text model.
2. Kokoro-82M text-to-speech pipeline.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root and brain/src to path
project_root = Path(__file__).resolve().parent.parent.parent
brain_src = project_root / "brain" / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(brain_src))


def setup_kokoro() -> bool:
    """Prewarm Kokoro TTS model on CPU."""
    print("=" * 60)
    print("Setting up Kokoro-82M Text-to-Speech (CPU)...")
    print("=" * 60)
    start_time = time.perf_counter()
    try:
        from kokoro import KPipeline

        pipeline = KPipeline(lang_code="a", device="cpu")
        print("  - KPipeline initialized successfully.")

        test_phrase = "System check complete. Speech generation is fully operational."
        generator = pipeline(test_phrase, voice="af_bella", speed=1.0)
        chunks = list(generator)
        if not chunks:
            print("  [FAIL] No audio chunks generated.")
            return False

        sample_rate = 24000
        total_samples = sum(len(c.audio) if hasattr(c, "audio") else len(c[-1]) for c in chunks)
        duration_s = total_samples / sample_rate
        elapsed = time.perf_counter() - start_time
        print(f"  [PASS] Kokoro ready! Synthesized {duration_s:.2f}s audio in {elapsed:.2f}s.")
        return True
    except Exception as exc:
        print(f"  [FAIL] Kokoro setup failed: {exc}")
        return False


def setup_moonshine() -> bool:
    """Prewarm Moonshine STT model."""
    print("\n" + "=" * 60)
    print("Setting up Moonshine Speech-to-Text...")
    print("=" * 60)
    start_time = time.perf_counter()
    try:
        from Speach2text import SpeechToTextService

        stt = SpeechToTextService()
        stt.load()
        elapsed = time.perf_counter() - start_time
        print(f"  [PASS] Moonshine ready! Loaded in {elapsed:.2f}s.")
        return True
    except Exception as exc:
        print(f"  [FAIL] Moonshine setup failed: {exc}")
        return False


def main() -> None:
    """Run model setup."""
    print("Pre-warming JARVIS local AI models...\n")
    kokoro_ok = setup_kokoro()
    moonshine_ok = setup_moonshine()

    print("\n" + "=" * 60)
    if kokoro_ok and moonshine_ok:
        print("ALL LOCAL MODELS PRE-WARMED AND READY FOR USE.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("MODEL SETUP COMPLETED WITH ERRORS. Check output above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

