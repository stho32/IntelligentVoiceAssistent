"""Tests for WhisperTranscriber (OpenAI API mocked)."""

import io
import wave
from unittest.mock import MagicMock

import numpy as np
import pytest

from sprachassistent.stt.whisper_api import WhisperTranscriber, _pcm_to_wav


@pytest.fixture()
def mock_openai():
    """Mock OpenAI client."""
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.text = "Hallo Welt"
    mock_client.audio.transcriptions.create.return_value = mock_result
    return mock_client


def test_transcribe_returns_text(mock_openai):
    """Transcription returns the API text response."""
    transcriber = WhisperTranscriber(client=mock_openai)
    pcm = np.zeros(16000, dtype=np.int16).tobytes()  # 1 second of silence

    result = transcriber.transcribe(pcm)
    assert result == "Hallo Welt"


def test_transcribe_calls_api(mock_openai):
    """Transcription calls the API with correct parameters."""
    transcriber = WhisperTranscriber(model="whisper-1", language="de", client=mock_openai)
    pcm = np.zeros(16000, dtype=np.int16).tobytes()

    transcriber.transcribe(pcm)

    call_kwargs = mock_openai.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["language"] == "de"
    # file should be a BytesIO with .name
    assert hasattr(call_kwargs["file"], "name")
    assert call_kwargs["file"].name == "audio.wav"


def test_transcribe_empty_audio(mock_openai):
    """Transcribing empty audio raises ValueError."""
    transcriber = WhisperTranscriber(client=mock_openai)
    with pytest.raises(ValueError, match="No audio data"):
        transcriber.transcribe(b"")


def test_pcm_to_wav_creates_valid_wav():
    """_pcm_to_wav produces a valid WAV file."""
    pcm = np.zeros(16000, dtype=np.int16).tobytes()
    buf = _pcm_to_wav(pcm, sample_rate=16000, channels=1, sample_width=2)

    assert isinstance(buf, io.BytesIO)
    assert buf.name == "audio.wav"

    # Verify it's a valid WAV
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


def test_transcribe_api_error(mock_openai):
    """API errors propagate as exceptions."""
    mock_openai.audio.transcriptions.create.side_effect = RuntimeError("API error")
    transcriber = WhisperTranscriber(client=mock_openai)
    pcm = np.zeros(16000, dtype=np.int16).tobytes()

    with pytest.raises(RuntimeError, match="API error"):
        transcriber.transcribe(pcm)
