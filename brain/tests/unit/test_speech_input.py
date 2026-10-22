"""Unit tests for speech input manager."""

import asyncio
from unittest.mock import MagicMock

import pytest

from jarvis_brain.voice.speech_input import SpeechInputManager


def test_speech_input_deduplication():
    """Verify identical immediate utterances are deduplicated to avoid double processing."""
    manager = SpeechInputManager()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    manager._loop = mock_loop

    # First callback
    manager._on_final_transcript_callback("What is the meaning of serendipity?")
    assert mock_loop.call_soon_threadsafe.call_count == 1

    # Immediate duplicate callback
    manager._on_final_transcript_callback("What is the meaning of serendipity?")
    # Count should still be 1
    assert mock_loop.call_soon_threadsafe.call_count == 1

    # New distinct utterance
    manager._on_final_transcript_callback("Tell me more.")
    assert mock_loop.call_soon_threadsafe.call_count == 2


def test_speech_input_empty_strings():
    """Verify empty or whitespace strings are ignored."""
    manager = SpeechInputManager()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    manager._loop = mock_loop

    manager._on_final_transcript_callback("")
    manager._on_final_transcript_callback("    \n  ")
    assert mock_loop.call_soon_threadsafe.call_count == 0


def test_speech_input_pause_and_resume():
    """Verify mute/unmute calls down to the underlying STT service."""
    manager = SpeechInputManager()
    mock_stt = MagicMock()
    manager._stt_service = mock_stt

    manager.pause_listening()
    mock_stt.mute.assert_called_with(True)

    manager.resume_listening()
    mock_stt.mute.assert_called_with(False)

