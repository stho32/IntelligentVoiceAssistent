"""Tests for configuration loading."""

import os
from pathlib import Path

import pytest
import yaml

from sprachassistent.config import load_config


@pytest.fixture()
def config_file(tmp_path):
    """Create a temporary config file."""
    config = {
        "wake_word": {
            "engine": "openwakeword",
            "model_path": "models/computer_v2.onnx",
            "threshold": 0.5,
        },
        "stt": {"provider": "openai", "model": "whisper-1", "language": "de"},
        "ai": {
            "backend": "claude-code",
            "working_directory": "~/Projekte/Training2",
        },
        "tts": {"provider": "openai", "model": "tts-1", "voice": "onyx"},
        "audio": {"sample_rate": 16000, "channels": 1},
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


def test_load_config_returns_dict(config_file):
    """Config loads as a dictionary."""
    config = load_config(config_file)
    assert isinstance(config, dict)


def test_load_config_has_all_sections(config_file):
    """Config contains all expected top-level sections."""
    config = load_config(config_file)
    for section in ("wake_word", "stt", "ai", "tts", "audio"):
        assert section in config, f"Missing section: {section}"


def test_load_config_expands_home(config_file):
    """~ in paths is expanded to the home directory."""
    config = load_config(config_file)
    working_dir = config["ai"]["working_directory"]
    assert "~" not in working_dir
    assert working_dir.startswith(os.path.expanduser("~"))


def test_load_config_missing_file():
    """Loading a nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_load_default_config():
    """The default config.yaml can be loaded."""
    config = load_config()
    assert "wake_word" in config
    assert config["wake_word"]["engine"] == "openwakeword"
