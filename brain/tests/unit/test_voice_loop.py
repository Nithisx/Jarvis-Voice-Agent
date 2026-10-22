"""Unit tests for the voice-to-voice interaction loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_brain.voice.command_queue import VoiceCommand
from jarvis_brain.voice.state import WorkerState, voice_state_manager
from jarvis_brain.voice.voice_loop import VoiceLoop


@pytest.mark.asyncio
async def test_voice_loop_single_turn():
    """Verify voice loop executes command, pauses mic only during playback, speaks assembled audio, and resumes mic."""
    loop = VoiceLoop()
    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(return_value="Why did the chicken cross the road?")

    cmd = VoiceCommand(
        command_id="cmd_test_1",
        command_text="Tell me a joke",
        captured_at=100.0,
        enqueued_at=100.0,
        thread_id="test_thread",
    )

    with patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts, \
         patch("jarvis_brain.voice.voice_loop.command_queue") as mock_queue:

        # Queue one command then stop
        mock_stt.get_next_command = AsyncMock(side_effect=[cmd, asyncio.CancelledError()])
        mock_tts.speak_async = AsyncMock()
        mock_queue.has_pending_overflow_notice = False
        mock_queue.qsize = 0

        try:
            await loop.run(brain=mock_brain)
        except asyncio.CancelledError:
            pass

        # Verify LLM response
        mock_brain.respond.assert_called_with("Tell me a joke", thread_id="test_thread")

        # Verify mic was paused during playback
        assert mock_stt.pause_listening.called
        mock_tts.speak_async.assert_called_with("Why did the chicken cross the road?")
        assert mock_stt.resume_listening.called
        mock_queue.mark_processed.assert_called_with(cmd)


@pytest.mark.asyncio
async def test_voice_loop_recovers_from_error():
    """Verify voice loop speaks fallback message and resumes microphone on unexpected error without crash."""
    loop = VoiceLoop()
    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(side_effect=RuntimeError("API error"))

    cmd = VoiceCommand(
        command_id="cmd_crash",
        command_text="Crash now",
        captured_at=100.0,
        enqueued_at=100.0,
        thread_id="test_thread",
    )

    with patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts, \
         patch("jarvis_brain.voice.voice_loop.command_queue") as mock_queue:

        mock_stt.get_next_command = AsyncMock(side_effect=[cmd, asyncio.CancelledError()])
        mock_tts.speak_async = AsyncMock()
        mock_queue.qsize = 0

        try:
            await loop.run(brain=mock_brain)
        except asyncio.CancelledError:
            pass

        # Fallback speech spoken
        mock_tts.speak_async.assert_called_with("I ran into an issue processing that. Could you say that again?")
        # Microphone resumed
        assert mock_stt.resume_listening.called
