"""Tests for OpenAITextToSpeech (API and audio output mocked)."""

from unittest.mock import MagicMock

import pytest

from sprachassistent.tts.openai_tts import OpenAITextToSpeech


@pytest.fixture()
def mock_openai():
    """Mock OpenAI client with streaming response."""
    mock_client = MagicMock()

    # Mock streaming response context manager
    mock_response = MagicMock()
    mock_response.iter_bytes.return_value = [b"\x00" * 1024, b"\x00" * 512]
    mock_streaming_ctx = MagicMock()
    mock_streaming_ctx.__enter__ = MagicMock(return_value=mock_response)
    mock_streaming_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.audio.speech.with_streaming_response.create.return_value = mock_streaming_ctx

    # Mock non-streaming response
    mock_sync_response = MagicMock()
    mock_sync_response.content = b"\x00" * 4800
    mock_client.audio.speech.create.return_value = mock_sync_response

    return mock_client


@pytest.fixture()
def mock_player():
    """Mock AudioOutput player."""
    player = MagicMock()
    stream = MagicMock()
    player.open_pcm_stream.return_value = stream
    return {"player": player, "stream": stream}


def test_speak_streams_audio(mock_openai, mock_player):
    """speak() streams PCM chunks to the audio output."""
    tts = OpenAITextToSpeech(client=mock_openai)
    tts.speak("Hallo Welt", player=mock_player["player"])

    # Verify streaming API was called
    mock_openai.audio.speech.with_streaming_response.create.assert_called_once()
    call_kwargs = mock_openai.audio.speech.with_streaming_response.create.call_args.kwargs
    assert call_kwargs["response_format"] == "pcm"
    assert call_kwargs["model"] == "tts-1"
    assert call_kwargs["voice"] == "onyx"

    # Verify audio was written to stream
    assert mock_player["stream"].write.call_count == 2
    mock_player["stream"].close.assert_called_once()


def test_speak_with_provided_player(mock_openai, mock_player):
    """speak() uses provided player without creating its own."""
    tts = OpenAITextToSpeech(client=mock_openai)
    player = mock_player["player"]

    tts.speak("Test", player=player)

    # Should open a PCM stream from the player
    player.open_pcm_stream.assert_called_once()
    # Should not call close on the player (caller owns it)
    player.close.assert_not_called()


def test_speak_empty_text_raises(mock_openai):
    """speak() raises ValueError for empty text."""
    tts = OpenAITextToSpeech(client=mock_openai)
    with pytest.raises(ValueError, match="No text"):
        tts.speak("")


def test_synthesize_returns_bytes(mock_openai):
    """synthesize() returns raw PCM bytes."""
    tts = OpenAITextToSpeech(client=mock_openai)
    result = tts.synthesize("Hallo")

    assert isinstance(result, bytes)
    assert len(result) == 4800
    mock_openai.audio.speech.create.assert_called_once()


def test_synthesize_empty_text_raises(mock_openai):
    """synthesize() raises ValueError for empty text."""
    tts = OpenAITextToSpeech(client=mock_openai)
    with pytest.raises(ValueError, match="No text"):
        tts.synthesize("   ")


def test_api_error_propagates(mock_openai, mock_player):
    """API errors propagate through speak()."""
    mock_openai.audio.speech.with_streaming_response.create.side_effect = RuntimeError("API down")
    tts = OpenAITextToSpeech(client=mock_openai)

    with pytest.raises(RuntimeError, match="API down"):
        tts.speak("Test", player=mock_player["player"])
