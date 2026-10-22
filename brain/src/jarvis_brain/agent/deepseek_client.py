"""DeepSeek OpenAI-compatible chat model client integration for LangGraph."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from jarvis_brain.agent.prompts import JARVIS_SYSTEM_PROMPT
from jarvis_brain.config import get_config, get_masked_deepseek_key
from jarvis_brain.exceptions import (
    DeepSeekAuthError,
    DeepSeekError,
    DeepSeekRateLimitError,
    DeepSeekTimeoutError,
)
from jarvis_brain.observability.logging import get_logger

logger = get_logger("deepseek")


def create_deepseek_model(
    tools: Optional[Sequence[BaseTool]] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Instantiate and configure the ChatOpenAI client targeting DeepSeek's API.

    Uses the official endpoint https://api.deepseek.com with tool binding support.
    """
    config = get_config()

    try:
        temp = temperature if temperature is not None else config.deepseek_temperature
        model = ChatOpenAI(
            model=config.deepseek_model,
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            temperature=temp,
            timeout=config.deepseek_timeout,
            max_retries=2,
        )

        if tools:
            model = model.bind_tools(list(tools))

        return model
    except Exception as exc:
        logger.error("Failed to initialize DeepSeek ChatOpenAI model: %s", exc)
        raise DeepSeekError(f"DeepSeek model initialization failed: {exc}") from exc


async def check_deepseek_readiness() -> bool:
    """Perform a lightweight test invocation to confirm DeepSeek credentials and API access."""
    config = get_config()
    logger.info(
        "Testing DeepSeek API readiness (endpoint: %s, model: %s, key: %s)...",
        config.deepseek_base_url,
        config.deepseek_model,
        get_masked_deepseek_key(),
    )

    try:
        model = ChatOpenAI(
            model=config.deepseek_model,
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            max_tokens=10,
            timeout=10.0,
            max_retries=1,
        )
        test_messages = [HumanMessage(content="Ping")]
        resp = await model.ainvoke(test_messages)
        if resp and resp.content:
            logger.info("DeepSeek API connection verified successfully.")
            return True
        return False
    except Exception as exc:
        err_str = str(exc).lower()
        if "401" in err_str or "auth" in err_str or "api_key" in err_str or "unauthorized" in err_str:
            raise DeepSeekAuthError("DeepSeek API authentication failed. Verify DeepSeek_api in root .env.") from exc
        if "429" in err_str or "rate" in err_str or "quota" in err_str:
            raise DeepSeekRateLimitError("DeepSeek API rate limit or quota exceeded.") from exc
        if "timeout" in err_str or "timed out" in err_str:
            raise DeepSeekTimeoutError("DeepSeek API request timed out.") from exc
        raise DeepSeekError(f"DeepSeek readiness check failed: {exc}") from exc
