"""OpenAI Text-to-Speech client with PCM streaming.

Converts text responses to speech and streams audio for
low-latency playback at 24kHz.
"""

import pyaudio
from openai import OpenAI

# OpenAI TTS PCM format: 24kHz, 16-bit, mono
TTS_SAMPLE_RATE = 24000
TTS_CHANNELS = 1
TTS_CHUNK_SIZE = 1024


class OpenAITextToSpeech:
    """Text-to-speech using the OpenAI TTS API with PCM streaming.

    Args:
        model: TTS model name.
        voice: Voice name.
        speed: Speech speed multiplier.
        client: Optional OpenAI client instance.
    """

    def __init__(
        self,
        model: str = "tts-1",
        voice: str = "onyx",
        speed: float = 1.0,
        client: OpenAI | None = None,
    ):
        self.model = model
        self.voice = voice
        self.speed = speed
        self._client = client or OpenAI()

    def speak(self, text: str, pa: pyaudio.PyAudio | None = None) -> None:
        """Convert text to speech and play through speakers.

        Streams PCM audio chunks for low-latency playback.

        Args:
            text: Text to speak.
            pa: Optional PyAudio instance (creates one if not provided).

        Raises:
            ValueError: If text is empty.
        """
        if not text.strip():
            raise ValueError("No text to speak.")

        own_pa = pa is None
        if own_pa:
            pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=TTS_CHANNELS,
            rate=TTS_SAMPLE_RATE,
            output=True,
        )

        try:
            with self._client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="pcm",
                speed=self.speed,
            ) as response:
                for chunk in response.iter_bytes(chunk_size=TTS_CHUNK_SIZE):
                    stream.write(chunk)
        finally:
            stream.stop_stream()
            stream.close()
            if own_pa:
                pa.terminate()

    def synthesize(self, text: str) -> bytes:
        """Convert text to PCM audio bytes without playing.

        Args:
            text: Text to synthesize.

        Returns:
            Raw PCM bytes (24kHz, 16-bit, mono).

        Raises:
            ValueError: If text is empty.
        """
        if not text.strip():
            raise ValueError("No text to synthesize.")

        response = self._client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="pcm",
            speed=self.speed,
        )
        return response.content
