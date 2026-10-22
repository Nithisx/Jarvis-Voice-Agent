"""Unit tests for Kokoro TTS service."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from jarvis_brain.voice.tts_kokoro import KokoroTTSService


def test_kokoro_service_init():
    """Verify default initialization parameters."""
    service = KokoroTTSService(lang_code="a", voice="af_bella", speed=1.1, device="cpu")
    assert service.lang_code == "a"
    assert service.default_voice == "af_bella"
    assert service.default_speed == 1.1
    assert service.device == "cpu"
    assert service._is_loaded is False


def test_synthesize_empty_string():
    """Verify empty string returns empty audio list without calling pipeline."""
    service = KokoroTTSService()
    service._is_loaded = True
    service._pipeline = MagicMock()
    result = service.synthesize("")
    assert result == []
    service._pipeline.assert_not_called()


def test_synthesize_with_mock_pipeline():
    """Verify synthesize formats and calls the underlying generator."""
    service = KokoroTTSService()
    service._is_loaded = True

    mock_chunk = MagicMock()
    mock_chunk.audio = np.zeros(24000, dtype=np.float32)

    service._pipeline = MagicMock(return_value=[mock_chunk])

    segments = service.synthesize("Hello world")
    assert len(segments) == 1
    assert isinstance(segments[0], np.ndarray)
    assert len(segments[0]) == 24000


@pytest.mark.asyncio
async def test_speak_async_invokes_player():
    """Verify speak_async delegates synthesis and triggers player."""
    service = KokoroTTSService()
    service._is_loaded = True

    mock_chunk = MagicMock()
    mock_chunk.audio = np.zeros(24000, dtype=np.float32)
    service._pipeline = MagicMock(return_value=[mock_chunk])

    with patch("jarvis_brain.voice.tts_kokoro.audio_player.play") as mock_play:
        await service.speak_async("Hello there! How are you?")
        assert mock_play.called

