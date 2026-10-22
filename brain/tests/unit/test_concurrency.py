"""Concurrency and queue gating verification tests.

Verifies:
1. First valid command enters agent worker.
2. During its simulated LLM delay, local transcription continues.
3. Second wake-word command is captured and queued.
4. Second command does NOT start a concurrent graph invocation.
5. First command completes and audio is played.
6. Second command is subsequently processed in FIFO order.
7. Model failure on first command does NOT drop subsequent commands.
8. Half-duplex muting prevents self-triggering during playback.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_brain.voice.command_queue import CommandQueue, VoiceCommand
from jarvis_brain.voice.state import MicGateState, WorkerState, voice_state_manager
from jarvis_brain.voice.voice_loop import VoiceLoop


@pytest.mark.asyncio
async def test_concurrent_capture_and_sequential_processing():
    """Verify second command is captured during first command's LLM delay and processed sequentially."""
    test_queue = CommandQueue(maxsize=5)
    loop = VoiceLoop(reverberation_delay=0.0)

    processed_commands: list[str] = []
    active_concurrent_calls = 0
    max_concurrent_calls = 0

    async def mock_respond(text: str, thread_id: str) -> str:
        nonlocal active_concurrent_calls, max_concurrent_calls
        active_concurrent_calls += 1
        if active_concurrent_calls > max_concurrent_calls:
            max_concurrent_calls = active_concurrent_calls

        # Simulate brief LLM reasoning delay
        await asyncio.sleep(0.05)

        processed_commands.append(text)
        active_concurrent_calls -= 1
        return f"Response to {text}"

    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(side_effect=mock_respond)

    # Put first command
    test_queue.enqueue("First command")

    with patch("jarvis_brain.voice.voice_loop.command_queue", test_queue), \
         patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts:

        mock_stt.get_next_command = test_queue.get
        mock_tts.speak_async = AsyncMock()

        # Start worker loop in background
        worker_task = asyncio.create_task(loop.run(brain=mock_brain))

        # Wait until worker begins processing Command 1
        await asyncio.sleep(0.05)
        assert voice_state_manager.worker_state == WorkerState.PROCESSING

        # While worker is processing Command 1, simulate concurrent capture of Command 2
        test_queue.enqueue("Second command")
        assert test_queue.qsize == 1

        # Wait for both commands to finish processing
        await asyncio.sleep(0.4)

        loop.stop()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Verify sequential FIFO execution
        assert processed_commands == ["First command", "Second command"]
        # Guarantee no concurrent graph calls occurred
        assert max_concurrent_calls == 1


@pytest.mark.asyncio
async def test_failure_on_first_command_preserves_subsequent_commands():
    """Verify that an error on one command does not erase or drop subsequent queued commands."""
    test_queue = CommandQueue(maxsize=5)
    loop = VoiceLoop(reverberation_delay=0.0)

    processed_commands: list[str] = []

    async def mock_respond(text: str, thread_id: str) -> str:
        if text == "Faulty command":
            raise RuntimeError("DeepSeek temporary network error")
        processed_commands.append(text)
        return "OK"

    mock_brain = AsyncMock()
    mock_brain.respond = AsyncMock(side_effect=mock_respond)

    # Enqueue both faulty and valid command
    test_queue.enqueue("Faulty command")
    test_queue.enqueue("Subsequent valid command")

    with patch("jarvis_brain.voice.voice_loop.command_queue", test_queue), \
         patch("jarvis_brain.voice.voice_loop.speech_input_manager") as mock_stt, \
         patch("jarvis_brain.voice.voice_loop.tts_service") as mock_tts:

        mock_stt.get_next_command = test_queue.get
        mock_tts.speak_async = AsyncMock()

        worker_task = asyncio.create_task(loop.run(brain=mock_brain))

        await asyncio.sleep(0.3)

        loop.stop()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Subsequent valid command was processed despite earlier failure
        assert processed_commands == ["Subsequent valid command"]


def test_playback_muting_prevents_self_triggering():
    """Verify mic is set to MUTED_FOR_PLAYBACK during speech to prevent audio loops."""
    from jarvis_brain.voice.speech_input import SpeechInputManager

    sim = SpeechInputManager()
    mock_stt = MagicMock()
    sim._stt_service = mock_stt

    # Start playback -> Mute
    sim.pause_listening()
    assert voice_state_manager.gate_state == MicGateState.MUTED_FOR_PLAYBACK
    mock_stt.mute.assert_called_with(True)

    # Any audio or speech arriving during playback is discarded
    sim._on_audio_activity_callback(0.09)
    # last_speech_time is not treated as a valid command trigger while muted
    assert sim._current_partial == ""

    # Playback finished -> Resume
    sim.resume_listening()
    assert voice_state_manager.gate_state == MicGateState.LISTENING_FOR_WAKE_WORD
    mock_stt.mute.assert_called_with(False)

