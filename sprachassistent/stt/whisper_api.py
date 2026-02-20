"""OpenAI Whisper API client for speech-to-text.

Sends recorded audio to the Whisper API and returns the transcription.
"""

import io
import wave

from openai import OpenAI


class WhisperTranscriber:
    """Transcribes audio using the OpenAI Whisper API.

    Args:
        model: Whisper model name.
        language: ISO-639-1 language code (e.g., "de").
        client: Optional OpenAI client instance.
    """

    def __init__(
        self,
        model: str = "whisper-1",
        language: str = "de",
        client: OpenAI | None = None,
    ):
        self.model = model
        self.language = language
        self._client = client or OpenAI()

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> str:
        """Transcribe raw PCM audio data to text.

        Converts raw PCM to WAV format in memory, then sends to the API.

        Args:
            audio_data: Raw PCM bytes (int16, little-endian).
            sample_rate: Audio sample rate in Hz.
            channels: Number of audio channels.
            sample_width: Bytes per sample (2 for int16).

        Returns:
            Transcribed text string.

        Raises:
            ValueError: If audio_data is empty.
        """
        if not audio_data:
            raise ValueError("No audio data to transcribe.")

        wav_buffer = _pcm_to_wav(audio_data, sample_rate, channels, sample_width)

        result = self._client.audio.transcriptions.create(
            model=self.model,
            file=wav_buffer,
            language=self.language,
        )
        return result.text


def _pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> io.BytesIO:
    """Convert raw PCM bytes to a WAV file in memory.

    Args:
        pcm_data: Raw PCM audio bytes.
        sample_rate: Sample rate in Hz.
        channels: Number of channels.
        sample_width: Bytes per sample.

    Returns:
        BytesIO buffer containing a valid WAV file.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    buf.seek(0)
    buf.name = "audio.wav"
    return buf
