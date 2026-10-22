"""End-to-end voice pipeline simulation test."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from jarvis_brain.agent.graph import jarvis_brain
from jarvis_brain.voice.tts_kokoro import tts_service


@pytest.mark.asyncio
async def test_simulated_voice_pipeline_flow():
    """Verify simulated utterance flows through agent reasoning to spoken audio generation."""

    # Mock DeepSeek model response
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(
        content="The word serendipity refers to an unexpected and fortunate discovery."
    )

    with patch("jarvis_brain.agent.graph.create_deepseek_model", return_value=mock_model), \
         patch("jarvis_brain.voice.audio_output.audio_player.play") as mock_play:

        # Initialize the graph
        await jarvis_brain.initialize(force_in_memory_checkpoint=True, tools=[])

        # Step 1: User speaks
        user_utterance = "What does serendipity mean?"

        # Step 2: Agent reasons
        response_text = await jarvis_brain.respond(user_utterance, session_id="test_session")
        assert "serendipity" in response_text
        assert "fortunate discovery" in response_text

        # Step 3: Kokoro speaks response
        await tts_service.speak_async(response_text)
        assert mock_play.called
