"""Tests for WakeWordDetector (OpenWakeWord mocked)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sprachassistent.audio.wake_word import WakeWordDetector

MODEL_NAME = "hey_jarvis"


@pytest.fixture()
def mock_oww():
    """Mock the OpenWakeWord Model class."""
    with patch("sprachassistent.audio.wake_word.Model") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.predict.return_value = {MODEL_NAME: 0.0}
        mock_model_cls.return_value = mock_model
        yield mock_model


def test_init_creates_model_with_onnx(mock_oww):
    """Detector creates an ONNX model with the given name."""
    from sprachassistent.audio.wake_word import Model

    WakeWordDetector(model_path=MODEL_NAME, threshold=0.5)
    Model.assert_called_once_with(
        wakeword_models=[MODEL_NAME],
        inference_framework="onnx",
    )


def test_process_bytes_below_threshold(mock_oww):
    """Returns False when score is below threshold."""
    detector = WakeWordDetector(MODEL_NAME, threshold=0.5)
    mock_oww.predict.return_value = {MODEL_NAME: 0.3}

    result = detector.process(b"\x00" * 2560)  # 1280 int16 samples
    assert result is False


def test_process_above_threshold(mock_oww):
    """Returns True when score meets threshold."""
    detector = WakeWordDetector(MODEL_NAME, threshold=0.5)
    mock_oww.predict.return_value = {MODEL_NAME: 0.8}

    result = detector.process(b"\x00" * 2560)
    assert result is True


def test_process_numpy_array(mock_oww):
    """Accepts numpy int16 array directly."""
    detector = WakeWordDetector(MODEL_NAME, threshold=0.5)
    mock_oww.predict.return_value = {MODEL_NAME: 0.9}

    audio = np.zeros(1280, dtype=np.int16)
    result = detector.process(audio)
    assert result is True
    # Verify numpy array was passed (not converted from bytes)
    call_args = mock_oww.predict.call_args[0][0]
    assert isinstance(call_args, np.ndarray)


def test_reset_clears_model(mock_oww):
    """reset() delegates to the model's reset."""
    detector = WakeWordDetector(MODEL_NAME)
    detector.reset()
    mock_oww.reset.assert_called_once()


def test_threshold_boundary(mock_oww):
    """Score exactly at threshold triggers detection."""
    detector = WakeWordDetector(MODEL_NAME, threshold=0.5)
    mock_oww.predict.return_value = {MODEL_NAME: 0.5}

    assert detector.process(b"\x00" * 2560) is True


def test_file_path_model(mock_oww, tmp_path):
    """Detector uses filename stem as model name for .onnx files."""
    onnx_file = tmp_path / "my_model.onnx"
    onnx_file.write_bytes(b"fake")

    mock_oww.predict.return_value = {"my_model": 0.9}
    detector = WakeWordDetector(str(onnx_file), threshold=0.5)

    assert detector._model_name == "my_model"
    assert detector.process(b"\x00" * 2560) is True
