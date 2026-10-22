"""Unit tests for SpeechInputManager with local wake-word gating and silence endpointing."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from jarvis_brain.voice.command_queue import command_queue
from jarvis_brain.voice.speech_input import SpeechInputManager
from jarvis_brain.voice.state import MicGateState, voice_state_manager


def test_speech_input_pause_and_resume():
    """Verify mute/unmute calls down to the underlying STT service and manages gate state."""
    manager = SpeechInputManager()
    mock_stt = MagicMock()
    manager._stt_service = mock_stt

    manager.pause_listening()
    mock_stt.mute.assert_called_with(True)
    assert voice_state_manager.gate_state == MicGateState.MUTED_FOR_PLAYBACK

    manager.resume_listening()
    mock_stt.mute.assert_called_with(False)
    assert voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD


def test_audio_energy_detection_updates_speech_time():
    """Verify physical audio frame energy updates the last speech timestamp."""
    manager = SpeechInputManager()
    manager._last_speech_time = 100.0

    with patch("time.time", return_value=150.0):
        # Above threshold (0.015)
        manager._on_audio_activity_callback(0.05)
        assert manager._last_speech_time == 150.0

        # Below threshold
        manager._on_audio_activity_callback(0.005)
        # Should remain 150.0
        assert manager._last_speech_time == 150.0


def test_partial_transcript_detects_wake_word():
    """Verify provisional partials transition gate to CAPTURING_COMMAND without duplicating text."""
    manager = SpeechInputManager()
    voice_state_manager.set_gate_state(MicGateState.LISTENING_FOR_WAKE_WORD)

    # Cumulative partial updates
    manager._on_partial_transcript_callback("Hey")
    assert voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD

    manager._on_partial_transcript_callback("Hey Jarvis")
    assert voice_state_manager.gate_state == MicGateState.CAPTURING_COMMAND

    manager._on_partial_transcript_callback("Hey Jarvis, create a note")
    assert voice_state_manager.gate_state == MicGateState.CAPTURING_COMMAND
    assert manager._current_partial == "Hey Jarvis, create a note"


@pytest.mark.asyncio
async def test_endpoint_monitor_enqueues_after_silence():
    """Verify 3 seconds of continuous silence finalizes the command and enqueues it."""
    manager = SpeechInputManager()
    manager._is_active = True
    voice_state_manager.set_gate_state(MicGateState.CAPTURING_COMMAND)

    manager._committed_segments = ["Hey Jarvis, create a note to buy milk."]
    manager._current_partial = ""
    # Set speech time to 3.5 seconds in the past
    manager._last_speech_time = time.time() - 3.5

    # Run one step of monitor logic
    monitor_coro = manager._endpoint_monitor_loop()
    task = asyncio.create_task(monitor_coro)
    await asyncio.sleep(0.1)

    manager._is_active = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Command should now be in command_queue
    assert command_queue.qsize >= 1
    cmd = await command_queue.get()
    assert cmd.command_text == "Create a note to buy milk."
    assert voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD
