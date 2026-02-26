"""Integration tests for voice + chat combined operation."""

import queue
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.chat.message import AssistantMessage, InputType, MessageSource
from sprachassistent.main import create_components, run_loop


def _make_config():
    """Create a minimal test config."""
    return {
        "wake_word": {"model_path": "models/test.onnx", "threshold": 0.5},
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1280,
            "vad_threshold": 0.5,
            "silence_threshold_sec": 1.5,
            "max_recording_sec": 30,
        },
        "stt": {"model": "whisper-1", "language": "de"},
        "ai": {
            "backend": "claude-code",
            "working_directory": "/tmp/test",
            "system_prompt_path": "ai/prompts/system.md",
        },
        "tts": {"model": "tts-1", "voice": "onyx", "speed": 1.0},
    }


def _make_mock_components():
    """Create mock components for the loop."""
    transcriber = MagicMock()
    transcriber.filter_transcript.side_effect = lambda text: text
    return {
        "wake_word": MagicMock(),
        "recorder": MagicMock(),
        "transcriber": transcriber,
        "ai_backend": MagicMock(),
        "tts": MagicMock(),
    }


def test_voice_and_chat_share_ai_backend():
    """Voice and chat messages use the same AI backend instance."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    work_queue = queue.Queue()
    outgoing = queue.Queue()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First: no wake word, but enqueue a chat message on work_queue
            work_queue.put(
                AssistantMessage(
                    source=MessageSource.MATRIX,
                    input_type=InputType.TEXT,
                    content="Chat command",
                    room_id="!room:matrix.org",
                    sender="@user:matrix.org",
                )
            )
            return False
        if call_count == 2:
            # Second: wake word detected for voice
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Voice command"
    components["ai_backend"].ask.return_value = "Response"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            matrix_outgoing=outgoing,
            work_queue=work_queue,
        )

    # AI backend should have been called twice: once for chat, once for voice
    assert components["ai_backend"].ask.call_count == 2
    calls = [c[0][0] for c in components["ai_backend"].ask.call_args_list]
    assert any("[Chat-Nachricht" in c for c in calls)
    assert any("Voice command" in c for c in calls)


def test_chat_waits_during_voice_pipeline():
    """Chat messages queue up while the voice pipeline is running."""
    components = _make_mock_components()
    mic = MagicMock()
    player = MagicMock()
    ui = MagicMock()

    work_queue = queue.Queue()
    outgoing = queue.Queue()

    call_count = 0

    def wake_word_side_effect(chunk):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Immediately detect wake word (voice takes priority)
            # Add a chat message that should wait in the queue
            work_queue.put(
                AssistantMessage(
                    source=MessageSource.MATRIX,
                    input_type=InputType.TEXT,
                    content="Queued chat",
                    room_id="!room:matrix.org",
                    sender="@user:matrix.org",
                )
            )
            return True
        raise KeyboardInterrupt

    components["wake_word"].process.side_effect = wake_word_side_effect
    components["recorder"].process_chunk.return_value = False
    components["recorder"].get_audio.return_value = b"\x00" * 3200
    components["transcriber"].transcribe.return_value = "Voice input"
    components["ai_backend"].ask.return_value = "Response"

    with pytest.raises(KeyboardInterrupt):
        run_loop(
            components,
            mic,
            player,
            ui,
            matrix_outgoing=outgoing,
            work_queue=work_queue,
        )

    # Both voice and chat should have been processed
    assert components["ai_backend"].ask.call_count == 2


@patch("sprachassistent.main.WakeWordDetector")
@patch("sprachassistent.main.SpeechRecorder")
@patch("sprachassistent.main.WhisperTranscriber")
@patch("sprachassistent.main.ClaudeCodeBackend")
@patch("sprachassistent.main.OpenAITextToSpeech")
def test_chat_only_skips_audio_components(mock_tts, mock_ai, mock_stt, mock_rec, mock_ww):
    """In chat-only mode, no audio components are created."""
    config = _make_config()
    components = create_components(config, chat_only=True)

    assert "ai_backend" in components
    assert "wake_word" not in components
    assert "recorder" not in components
    assert "transcriber" not in components
    assert "tts" not in components

    # Audio-related constructors should not have been called
    mock_ww.assert_not_called()
    mock_rec.assert_not_called()
    mock_stt.assert_not_called()
    mock_tts.assert_not_called()
