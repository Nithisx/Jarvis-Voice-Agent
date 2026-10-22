"""Voice layer package exports."""

from jarvis_brain.voice.audio_output import AudioOutputPlayer, audio_player
from jarvis_brain.voice.greeting import get_startup_greeting
from jarvis_brain.voice.speech_formatter import clean_for_speech, split_into_sentences
from jarvis_brain.voice.speech_input import SpeechInputManager, speech_input_manager
from jarvis_brain.voice.tts_kokoro import KokoroTTSService, tts_service
from jarvis_brain.voice.voice_loop import VoiceLoop, voice_loop

__all__ = [
    "AudioOutputPlayer",
    "audio_player",
    "get_startup_greeting",
    "clean_for_speech",
    "split_into_sentences",
    "SpeechInputManager",
    "speech_input_manager",
    "KokoroTTSService",
    "tts_service",
    "VoiceLoop",
    "voice_loop",
]

