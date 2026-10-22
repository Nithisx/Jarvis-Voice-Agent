"""Integration tests for DeepSeek client integration."""

import os
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, HumanMessage

from jarvis_brain.agent.deepseek_client import check_deepseek_readiness, create_deepseek_model
from jarvis_brain.config import get_config


def test_create_deepseek_model_parameters():
    """Verify DeepSeek ChatOpenAI model is initialized with correct base URL and parameters."""
    with patch.dict(os.environ, {"DeepSeek_api": "sk-mock-key"}):
        model = create_deepseek_model(temperature=0.3)
        assert model.openai_api_base == "https://api.deepseek.com"
        assert model.temperature == 0.3


@pytest.mark.asyncio
async def test_deepseek_readiness_mocked():
    """Verify check_deepseek_readiness with mocked model invocation."""
    with patch("jarvis_brain.agent.deepseek_client.ChatOpenAI") as mock_chat_cls:
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="pong")
        mock_chat_cls.return_value = mock_model

        ready = await check_deepseek_readiness()
        assert ready is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deepseek_live_call():
    """Live integration test against DeepSeek API if LIVE_TEST=1 is configured."""
    if os.environ.get("LIVE_TEST") != "1":
        pytest.skip("Skipping live DeepSeek call. Set LIVE_TEST=1 to run.")

    config = get_config()
    if not config.has_deepseek_key():
        pytest.skip("No DeepSeek API key configured.")

    ready = await check_deepseek_readiness()
    assert ready is True
