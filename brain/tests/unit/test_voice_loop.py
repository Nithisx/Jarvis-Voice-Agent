"""Unit tests for the voice-to-voice interaction loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_brain.voice.voice_loop import VoiceLoop


@pytest.mark.asyncio
async def test_voice_loop_single_turn():
    """Verify that voice loop pauses mic, generates response, speaks, and resumes mic."""
    loop = VoiceLoop()
    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(return_value="Why did the chicken cross the road?")

    with patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts:

        # Queue one utterance then stop
        mock_stt.get_next_utterance = AsyncMock(side_effect=["Tell me a joke", asyncio.CancelledError()])
        mock_tts.speak_async = AsyncMock()

        try:
            await loop.run(brain=mock_brain)
        except asyncio.CancelledError:
            pass

        # Check turn lifecycle sequence
        assert mock_stt.pause_listening.called
        mock_brain.respond.assert_called_with("Tell me a joke")
        mock_tts.speak_async.assert_called_with("Why did the chicken cross the road?")
        assert mock_stt.resume_listening.called


@pytest.mark.asyncio
async def test_voice_loop_recovers_from_error():
    """Verify voice loop speaks fallback message and resumes microphone on unexpected error."""
    loop = VoiceLoop()
    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(side_effect=RuntimeError("API error"))

    with patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts:

        mock_stt.get_next_utterance = AsyncMock(side_effect=["Crash now", asyncio.CancelledError()])
        mock_tts.speak_async = AsyncMock()

        try:
            await loop.run(brain=mock_brain)
        except asyncio.CancelledError:
            pass

        # Fallback speech spoken
        mock_tts.speak_async.assert_called_with("I ran into an issue processing that. Could you say that again?")
        # Microphone resumed
        assert mock_stt.resume_listening.called
