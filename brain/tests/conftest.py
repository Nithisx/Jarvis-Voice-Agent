"""Pytest configuration and common fixtures for JARVIS tests."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

# Ensure project root and brain/src are on sys.path
TESTS_DIR = Path(__file__).resolve().parent
BRAIN_DIR = TESTS_DIR.parent
PROJECT_ROOT = BRAIN_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BRAIN_DIR / "src"))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_deepseek_response():
    """Factory fixture for mocked ChatOpenAI responses."""
    from langchain_core.messages import AIMessage

    def _make(content: str = "Hello! How can I help you today?", tool_calls: list | None = None):
        msg = AIMessage(content=content)
        if tool_calls:
            msg.tool_calls = tool_calls
        return msg

    return _make

