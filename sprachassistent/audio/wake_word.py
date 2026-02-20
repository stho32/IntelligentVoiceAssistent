"""Wake-word detection using OpenWakeWord with ONNX inference.

Listens for the keyword "Computer" and signals activation.
"""

from pathlib import Path

import numpy as np
from openwakeword.model import Model


class WakeWordDetector:
    """Detects the wake word "Computer" in audio frames.

    Uses OpenWakeWord with a custom ONNX model for detection.

    Args:
        model_path: Path to the .onnx wake-word model file.
        threshold: Detection threshold (0.0-1.0). Higher = fewer false positives.
    """

    def __init__(self, model_path: str | Path, threshold: float = 0.5):
        self.model_path = str(model_path)
        self.threshold = threshold
        self._model_name: str | None = None
        self._model = Model(
            wakeword_models=[self.model_path],
            inference_framework="onnx",
        )
        # Derive model name from filename (e.g. "computer_v2")
        self._model_name = Path(self.model_path).stem

    def process(self, audio_frame: bytes | np.ndarray) -> bool:
        """Process one audio frame and check for wake word.

        Args:
            audio_frame: Raw PCM audio data (int16, 16kHz, mono).
                Either bytes or numpy int16 array. Optimal size: 1280 samples (80ms).

        Returns:
            True if the wake word was detected above the threshold.
        """
        if isinstance(audio_frame, bytes):
            audio_frame = np.frombuffer(audio_frame, dtype=np.int16)

        predictions = self._model.predict(audio_frame)
        score = predictions.get(self._model_name, 0.0)
        return score >= self.threshold

    def reset(self) -> None:
        """Clear prediction and audio buffers for next detection cycle."""
        self._model.reset()
