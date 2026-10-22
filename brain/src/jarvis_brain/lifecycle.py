"""Application lifecycle manager orchestrating initialization, greeting, and shutdown."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

from jarvis_brain.agent.deepseek_client import check_deepseek_readiness
from jarvis_brain.agent.graph import jarvis_brain
from jarvis_brain.config import get_config, get_masked_deepseek_key
from jarvis_brain.exceptions import JarvisError
from jarvis_brain.mcp.client_manager import mcp_client_manager
from jarvis_brain.memory.checkpointer import checkpointer_manager
from jarvis_brain.observability.logging import get_logger, setup_logging
from jarvis_brain.voice.greeting import get_startup_greeting
from jarvis_brain.voice.speech_input import speech_input_manager
from jarvis_brain.voice.tts_kokoro import tts_service
from jarvis_brain.voice.voice_loop import voice_loop

logger = get_logger("lifecycle")


class JarvisLifecycle:
    """Manages the startup sequence, component verification, and shutdown of JARVIS."""

    def __init__(self) -> None:
        self._is_initialized = False
        self._is_running = False

    async def startup(self) -> None:
        """Execute the ordered 14-step startup sequence."""
        # 1. Resolve project root & load config
        config = get_config()

        # 2. Setup logging with secret redaction
        setup_logging(config.log_level)
        logger.info("=" * 60)
        logger.info("             JARVIS VOICE-TO-VOICE ASSISTANT")
        logger.info("=" * 60)
        logger.info("Project Root: %s", config.project_root)
        logger.info("DeepSeek Model: %s (Key: %s)", config.deepseek_model, get_masked_deepseek_key())

        # 3. Preload Moonshine STT model
        logger.info("[1/7] Initializing Moonshine STT Tiny Streaming...")
        speech_input_manager.load()

        # 4. Preload Kokoro-82M TTS model
        logger.info("[2/7] Initializing Kokoro-82M Local TTS Pipeline...")
        tts_service.load()

        # 5. Check DeepSeek readiness if enabled
        if config.readiness_check:
            logger.info("[3/7] Probing DeepSeek API connection...")
            await check_deepseek_readiness()
        else:
            logger.info("[3/7] DeepSeek readiness check skipped by config.")

        # 6. Connect to both MCP servers (Notes & Web Search)
        logger.info("[4/7] Connecting to MCP servers (Notes & Web Search)...")
        await mcp_client_manager.connect_all()

        # 7. Compile LangGraph agent graph & connect checkpointer
        logger.info("[5/7] Compiling LangGraph reasoning engine...")
        await jarvis_brain.initialize()

        self._is_initialized = True
        logger.info("[6/7] All core services verified and ready.")

        # 8. Speak mandatory startup greeting BEFORE microphone is activated
        greeting_text = get_startup_greeting()
        logger.info("[7/7] Speaking startup greeting: '%s'", greeting_text)
        await tts_service.speak_async(greeting_text)

        # 9. Start microphone listener ONLY after greeting has finished playing
        loop = asyncio.get_running_loop()
        speech_input_manager.start_listening(loop=loop)
        logger.info("Microphone listening activated. JARVIS is ready!")

        self._is_running = True

    async def run(self) -> None:
        """Start lifecycle and enter permanent voice loop."""
        await self.startup()
        try:
            await voice_loop.run()
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutdown requested.")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully release all resources, streams, and child processes."""
        if not self._is_running and not self._is_initialized:
            return

        logger.info("Initiating JARVIS shutdown sequence...")
        self._is_running = False

        # Stop voice loop
        voice_loop.stop()

        # Stop microphone capture
        speech_input_manager.close()

        # Close MCP client sessions and subprocesses
        await mcp_client_manager.close()

        # Close checkpointer connections
        await checkpointer_manager.close()

        self._is_initialized = False
        logger.info("JARVIS shut down cleanly.")


# Singleton lifecycle manager
jarvis_lifecycle = JarvisLifecycle()

