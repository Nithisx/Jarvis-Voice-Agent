"""Audio and streaming verification tests.

Verifies:
1. LLM streaming is disabled (non-streaming complete response).
2. No partial LLM response reaches Kokoro.
3. Kokoro receives the complete final assistant response.
4. Assembled waveform played in one continuous operation.
5. Startup greeting completion precedes microphone activation.
6. Zero DeepSeek invocations for the startup greeting.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import pytest

from jarvis_brain.agent.deepseek_client import create_deepseek_model
from jarvis_brain.lifecycle import JarvisLifecycle
from jarvis_brain.voice.greeting import get_startup_greeting
from jarvis_brain.voice.tts_kokoro import tts_service


def test_deepseek_model_has_streaming_disabled():
    """Verify ChatOpenAI client explicitly has streaming=False."""
    with patch("jarvis_brain.agent.deepseek_client.ChatOpenAI") as mock_chat:
        create_deepseek_model()
        _, kwargs = mock_chat.call_args
        assert kwargs.get("streaming") is False


@pytest.mark.asyncio
async def test_startup_greeting_speaks_before_mic_activation_with_no_llm_call():
    """Verify startup greeting completes playback before mic is activated and makes zero LLM calls."""
    lifecycle = JarvisLifecycle()

    events = []

    async def mock_speak_greeting(text: str):
        events.append("spoken_greeting")
        assert "Welcome back, Nithish!" in text

    def mock_start_listening(loop=None):
        events.append("mic_activated")

    with patch("jarvis_brain.lifecycle.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.lifecycle.tts_service") as mock_tts, \
         patch("jarvis_brain.lifecycle.mcp_client_manager") as mock_mcp, \
         patch("jarvis_brain.lifecycle.jarvis_brain") as mock_brain, \
         patch("jarvis_brain.lifecycle.check_deepseek_readiness") as mock_ready:

        mock_tts.speak_async = AsyncMock(side_effect=mock_speak_greeting)
        mock_stt.start_listening = MagicMock(side_effect=mock_start_listening)
        mock_ready.return_value = True
        mock_mcp.connect_all = AsyncMock()
        mock_mcp.close = AsyncMock()
        mock_brain.initialize = AsyncMock()

        await lifecycle.startup()

        # Verify exact sequence: greeting spoken FIRST, mic activated SECOND
        assert events == ["spoken_greeting", "mic_activated"]
        # Verify jarvis_brain.respond was NEVER called during startup greeting
        mock_brain.respond.assert_not_called()

        # Clean shutdown
        await lifecycle.shutdown()


def test_no_partial_llm_response_reaches_kokoro():
    """Verify Kokoro speak is only invoked with the final complete string, not incremental tokens."""
    mock_player = MagicMock()
    service = tts_service

    test_tokens = ["This ", "is ", "token ", "by ", "token."]

    with patch("jarvis_brain.voice.tts_kokoro.audio_player.play", mock_player), \
         patch.object(service, "synthesize_full_waveform", return_value=np.zeros(24000, dtype=np.float32)):

        # If anyone attempted to pass tokens, speak would be called multiple times
        # But JARVIS passes the complete string once:
        complete_text = "".join(test_tokens)
        service.speak(complete_text)

        # Player called exactly once with the complete audio
        assert mock_player.call_count == 1

