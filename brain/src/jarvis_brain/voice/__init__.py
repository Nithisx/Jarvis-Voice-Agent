"""Voice layer package exports."""

from jarvis_brain.voice.audio_output import AudioOutputPlayer, audio_player
from jarvis_brain.voice.command_queue import CommandQueue, VoiceCommand, command_queue
from jarvis_brain.voice.greeting import get_startup_greeting
from jarvis_brain.voice.speech_formatter import clean_for_speech, split_into_sentences
from jarvis_brain.voice.speech_input import SpeechInputManager, speech_input_manager
from jarvis_brain.voice.state import MicGateState, WorkerState, voice_state_manager
from jarvis_brain.voice.tts_kokoro import KokoroTTSService, tts_service
from jarvis_brain.voice.voice_loop import VoiceLoop, voice_loop
from jarvis_brain.voice.wake_word import WakeWordDetector, default_wake_detector

__all__ = [
    "AudioOutputPlayer",
    "audio_player",
    "CommandQueue",
    "command_queue",
    "VoiceCommand",
    "get_startup_greeting",
    "clean_for_speech",
    "split_into_sentences",
    "SpeechInputManager",
    "speech_input_manager",
    "MicGateState",
    "WorkerState",
    "voice_state_manager",
    "KokoroTTSService",
    "tts_service",
    "VoiceLoop",
    "voice_loop",
    "WakeWordDetector",
    "default_wake_detector",
]

