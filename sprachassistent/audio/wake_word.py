"""Wake-word detection using OpenWakeWord with ONNX inference.

Listens for the keyword "Jarvis" and signals activation.
"""

from pathlib import Path

import numpy as np
from openwakeword.model import Model

from sprachassistent.exceptions import WakeWordError
from sprachassistent.utils.logging import get_logger

log = get_logger("audio.wake_word")


class WakeWordDetector:
    """Detects the wake word in audio frames.

    Uses OpenWakeWord with built-in or custom ONNX models.

    Args:
        model_path: Path to a custom .onnx file, OR a built-in model name
            (e.g., "hey_jarvis", "alexa").
        threshold: Detection threshold (0.0-1.0). Higher = fewer false positives.
    """

    def __init__(self, model_path: str | Path, threshold: float = 0.5):
        self.threshold = threshold
        model_str = str(model_path)

        # Determine if this is a file path or a built-in model name
        is_file = Path(model_str).suffix == ".onnx" and Path(model_str).exists()

        try:
            self._model = Model(
                wakeword_models=[model_str],
                inference_framework="onnx",
            )
        except Exception as e:
            raise WakeWordError(f"Failed to load wake-word model: {e}") from e

        # Derive model name for prediction lookup
        if is_file:
            self._model_name = Path(model_str).stem
        else:
            self._model_name = model_str

        log.info("Wake-word detector loaded: %s (threshold=%.2f)", self._model_name, threshold)

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
        if score > 0.05:
            log.debug("Wake word score: %.3f (keys: %s)", score, list(predictions.keys()))
        return score >= self.threshold

    def reset(self) -> None:
        """Clear prediction and audio buffers for next detection cycle."""
        self._model.reset()
