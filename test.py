
import time
import threading
from datetime import datetime

from moonshine_voice import MicTranscriber

# Tiny Streaming model architecture ID
MODEL_ARCH = 2
LANGUAGE = "en"

stop_event = threading.Event()


def on_partial(text):
    """Display live transcription while speaking."""
    print(f"\rListening: {text:<100}", end="", flush=True)


def on_final(line):
    """Receive a completed utterance for the JARVIS agent."""
    transcript = line.text.strip()

    if not transcript:
        return

    timestamp = datetime.now().strftime("%H:%M:%S")

    print(f"\n[{timestamp}] You: {transcript}")

    # TODO: Send transcript to your JARVIS agent here.
    # Example:
    # send_to_jarvis_backend(transcript)

    print("Listening...", flush=True)


def main():
    print("=" * 55)
    print("        JARVIS - LOCAL SPEECH RECOGNITION")
    print("        Moonshine Tiny Streaming")
    print("=" * 55)

    mic = (
        MicTranscriber()
        .language(LANGUAGE)
        .model_arch(MODEL_ARCH)
        .on_text(on_partial)
        .on_line(on_final)
    )

    try:
        print("\nLoading model...")
        mic.load()
        print("Model loaded successfully.")

        with mic:
            mic.start()
            print("Listening to your microphone. Press Ctrl+C to stop.\n")

            while not stop_event.is_set():
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping JARVIS...")

    finally:
        stop_event.set()
        try:
            mic.stop()
        except Exception:
            pass

        print("Speech recognition stopped.")


if __name__ == "__main__":
    main()
