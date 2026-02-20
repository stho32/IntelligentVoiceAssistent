"""Tests for WakeWordDetector (OpenWakeWord mocked)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sprachassistent.audio.wake_word import WakeWordDetector


@pytest.fixture()
def mock_oww():
    """Mock the OpenWakeWord Model class."""
    with patch("sprachassistent.audio.wake_word.Model") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.predict.return_value = {"computer_v2": 0.0}
        mock_model_cls.return_value = mock_model
        yield mock_model


def test_init_creates_model_with_onnx(mock_oww):
    """Detector creates an ONNX model with the given path."""
    from sprachassistent.audio.wake_word import Model

    WakeWordDetector(model_path="models/computer_v2.onnx", threshold=0.5)
    Model.assert_called_once_with(
        wakeword_models=["models/computer_v2.onnx"],
        inference_framework="onnx",
    )


def test_process_bytes_below_threshold(mock_oww):
    """Returns False when score is below threshold."""
    detector = WakeWordDetector("models/computer_v2.onnx", threshold=0.5)
    mock_oww.predict.return_value = {"computer_v2": 0.3}

    result = detector.process(b"\x00" * 2560)  # 1280 int16 samples
    assert result is False


def test_process_above_threshold(mock_oww):
    """Returns True when score meets threshold."""
    detector = WakeWordDetector("models/computer_v2.onnx", threshold=0.5)
    mock_oww.predict.return_value = {"computer_v2": 0.8}

    result = detector.process(b"\x00" * 2560)
    assert result is True


def test_process_numpy_array(mock_oww):
    """Accepts numpy int16 array directly."""
    detector = WakeWordDetector("models/computer_v2.onnx", threshold=0.5)
    mock_oww.predict.return_value = {"computer_v2": 0.9}

    audio = np.zeros(1280, dtype=np.int16)
    result = detector.process(audio)
    assert result is True
    # Verify numpy array was passed (not converted from bytes)
    call_args = mock_oww.predict.call_args[0][0]
    assert isinstance(call_args, np.ndarray)


def test_reset_clears_model(mock_oww):
    """reset() delegates to the model's reset."""
    detector = WakeWordDetector("models/computer_v2.onnx")
    detector.reset()
    mock_oww.reset.assert_called_once()


def test_threshold_boundary(mock_oww):
    """Score exactly at threshold triggers detection."""
    detector = WakeWordDetector("models/computer_v2.onnx", threshold=0.5)
    mock_oww.predict.return_value = {"computer_v2": 0.5}

    assert detector.process(b"\x00" * 2560) is True
