"""Speech recording with Voice Activity Detection (VAD).

Records audio after wake-word activation until silence is detected,
using silero-vad-lite for speech/silence classification.
"""

import array

import numpy as np
from silero_vad_lite import SileroVAD


class SpeechRecorder:
    """Records speech from audio chunks with VAD-based endpoint detection.

    Accumulates audio while speech is detected and stops after a
    configurable silence duration.

    Args:
        sample_rate: Audio sample rate in Hz.
        vad_threshold: Speech probability threshold (0.0-1.0).
        silence_duration_sec: Seconds of silence to end recording.
        max_duration_sec: Maximum recording duration in seconds.
    """

    VAD_FRAME_SIZE = 512  # 32ms at 16kHz

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        silence_duration_sec: float = 1.5,
        max_duration_sec: float = 30.0,
    ):
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self.silence_duration_sec = silence_duration_sec
        self.max_duration_sec = max_duration_sec

        self._vad = SileroVAD(sample_rate)
        self._audio_buffer: list[bytes] = []
        self._silence_frames = 0
        self._total_frames = 0
        self._recording = False

    @property
    def _silence_frame_limit(self) -> int:
        """Number of VAD frames that constitute silence duration."""
        frame_duration = self.VAD_FRAME_SIZE / self.sample_rate
        return int(self.silence_duration_sec / frame_duration)

    @property
    def _max_frame_limit(self) -> int:
        """Maximum number of VAD frames for max duration."""
        frame_duration = self.VAD_FRAME_SIZE / self.sample_rate
        return int(self.max_duration_sec / frame_duration)

    def start(self) -> None:
        """Start a new recording session."""
        self._audio_buffer = []
        self._silence_frames = 0
        self._total_frames = 0
        self._recording = True
        self._vad = SileroVAD(self.sample_rate)

    def process_chunk(self, audio_chunk: bytes) -> bool:
        """Process an audio chunk and check if recording should continue.

        The chunk is split into VAD-sized frames (512 samples) for
        speech detection. All audio is accumulated regardless of speech status.

        Args:
            audio_chunk: Raw PCM audio (int16, mono).

        Returns:
            True if recording should continue, False if done (silence or max duration).
        """
        if not self._recording:
            return False

        self._audio_buffer.append(audio_chunk)

        # Convert int16 bytes to float32 for VAD
        int16_array = np.frombuffer(audio_chunk, dtype=np.int16)
        float32_array = int16_array.astype(np.float32) / 32768.0

        # Process in VAD-sized frames
        offset = 0
        while offset + self.VAD_FRAME_SIZE <= len(float32_array):
            frame = float32_array[offset : offset + self.VAD_FRAME_SIZE]
            vad_data = array.array("f", frame.tobytes())
            speech_prob = self._vad.process(vad_data)

            if speech_prob >= self.vad_threshold:
                self._silence_frames = 0
            else:
                self._silence_frames += 1

            self._total_frames += 1
            offset += self.VAD_FRAME_SIZE

            # Check stop conditions
            if self._silence_frames >= self._silence_frame_limit:
                self._recording = False
                return False
            if self._total_frames >= self._max_frame_limit:
                self._recording = False
                return False

        return True

    def get_audio(self) -> bytes:
        """Get the complete recorded audio as raw PCM bytes (int16)."""
        return b"".join(self._audio_buffer)

    @property
    def is_recording(self) -> bool:
        """Whether the recorder is currently active."""
        return self._recording
