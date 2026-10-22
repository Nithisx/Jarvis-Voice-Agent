"""Unit tests for full-response Kokoro speech synthesis and continuous playback."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from jarvis_brain.voice.tts_kokoro import KokoroTTSService


def test_synthesize_full_waveform_concatenation():
    """Verify multiple sentence chunks are assembled into a single contiguous 1D array."""
    service = KokoroTTSService()
    service._is_loaded = True

    chunk1 = np.ones(12000, dtype=np.float32) * 0.5
    chunk2 = np.ones(12000, dtype=np.float32) * 0.3

    with patch.object(service, "synthesize", side_effect=[[chunk1], [chunk2]]):
        full_audio = service.synthesize_full_waveform("First sentence. Second sentence.")
        assert isinstance(full_audio, np.ndarray)
        assert full_audio.ndim == 1
        assert len(full_audio) == 24000
        assert np.array_equal(full_audio[:12000], chunk1)
        assert np.array_equal(full_audio[12000:], chunk2)


def test_synthesize_full_waveform_empty():
    """Verify empty text produces an empty 1D float32 array without calling generator."""
    service = KokoroTTSService()
    service._is_loaded = True
    full_audio = service.synthesize_full_waveform("")
    assert len(full_audio) == 0
    assert full_audio.dtype == np.float32


def test_speak_plays_single_continuous_waveform():
    """Verify speak invokes audio_player.play exactly once with the complete assembled waveform."""
    service = KokoroTTSService()
    service._is_loaded = True

    assembled_chunk = np.ones(48000, dtype=np.float32) * 0.2
    with patch.object(service, "synthesize_full_waveform", return_value=assembled_chunk), \
         patch("jarvis_brain.voice.tts_kokoro.audio_player.play") as mock_play:

        events = []
        def on_start():
            events.append("started")
        def on_done():
            events.append("done")

        service.speak("This is a complete two sentence test. It should play smoothly.", on_start=on_start, on_done=on_done)

        # audio_player.play called once with all 48000 samples (2 seconds of audio)
        mock_play.assert_called_once_with(assembled_chunk, sample_rate=24000)
        assert events == ["started", "done"]


def test_amplitude_normalization_guard():
    """Verify audio exceeding 1.0 peak amplitude is gently normalized to prevent clipping."""
    service = KokoroTTSService()
    service._is_loaded = True

    loud_chunk = np.array([0.5, 1.5, -2.0, 0.8], dtype=np.float32)
    with patch.object(service, "synthesize", return_value=[loud_chunk]):
        normalized = service.synthesize_full_waveform("Loud sound.")
        assert np.max(np.abs(normalized)) <= 1.0

