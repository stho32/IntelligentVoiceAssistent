"""OpenAI Whisper API client for speech-to-text.

Sends recorded audio to the Whisper API and returns the transcription.
"""

import io
import re
import wave

from openai import OpenAI

from sprachassistent.exceptions import TranscriptionError
from sprachassistent.utils.logging import get_logger

log = get_logger("stt.whisper")


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
        filter_phrases: list[str] | tuple[str, ...] = (),
    ):
        self.model = model
        self.language = language
        self._client = client or OpenAI()
        self._filter_phrases = list(filter_phrases)

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

        duration = len(audio_data) / (sample_rate * sample_width * channels)
        log.info("Transcribing %.1fs of audio...", duration)

        wav_buffer = _pcm_to_wav(audio_data, sample_rate, channels, sample_width)

        try:
            result = self._client.audio.transcriptions.create(
                model=self.model,
                file=wav_buffer,
                language=self.language,
            )
        except Exception as e:
            raise TranscriptionError(f"Whisper API error: {e}") from e

        log.info("Transcription: %s", result.text)
        return result.text

    def transcribe_file(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        """Transcribe an audio file (OGG, MP3, WAV, M4A etc.) to text.

        Sends the file bytes directly to the Whisper API without PCM conversion.

        Args:
            audio_bytes: Raw file bytes (any format Whisper accepts).
            filename: Filename hint for MIME type detection.

        Returns:
            Transcribed text string.

        Raises:
            ValueError: If audio_bytes is empty.
            TranscriptionError: If the API call fails.
        """
        if not audio_bytes:
            raise ValueError("No audio data to transcribe.")

        log.info("Transcribing file '%s' (%d bytes)...", filename, len(audio_bytes))

        buf = io.BytesIO(audio_bytes)
        buf.name = filename

        try:
            result = self._client.audio.transcriptions.create(
                model=self.model,
                file=buf,
                language=self.language,
            )
        except Exception as e:
            raise TranscriptionError(f"Whisper API error: {e}") from e

        log.info("Transcription: %s", result.text)
        return result.text

    def filter_transcript(self, text: str) -> str:
        """Remove known hallucination phrases and normalise whitespace.

        Args:
            text: Raw transcription text.

        Returns:
            Cleaned text (may be empty after filtering).
        """
        for phrase in self._filter_phrases:
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        # Collapse multiple spaces and strip
        text = re.sub(r"\s+", " ", text).strip()
        return text


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
