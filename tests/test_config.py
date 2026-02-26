"""Tests for configuration loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sprachassistent.config import load_config
from sprachassistent.exceptions import ConfigError


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
    with patch.dict("os.environ", {"MATRIX_PASSWORD": "test"}):
        config = load_config()
    assert "wake_word" in config
    assert config["wake_word"]["engine"] == "openwakeword"


# --- Matrix config tests ---


def _base_config(**overrides):
    """Create a minimal valid config dict with optional overrides."""
    cfg = {
        "wake_word": {"model_path": "models/test.onnx"},
        "ai": {"working_directory": "/tmp/test"},
    }
    cfg.update(overrides)
    return cfg


@pytest.fixture()
def matrix_config_file(tmp_path):
    """Create a config file with a valid matrix section."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "access_token": "syt_test",
            "room_id": "!room:matrix.org",
            "allowed_users": ["@user:matrix.org"],
            "store_path": "~/matrix_store",
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


def test_matrix_store_path_expanded(matrix_config_file):
    """~ in matrix.store_path is expanded to home directory."""
    config = load_config(matrix_config_file)
    assert "~" not in config["matrix"]["store_path"]
    assert config["matrix"]["store_path"].startswith(os.path.expanduser("~"))


def test_config_without_matrix_loads_fine(config_file):
    """Config without matrix section loads without error."""
    config = load_config(config_file)
    assert "matrix" not in config


def test_matrix_missing_homeserver_raises(tmp_path):
    """Missing homeserver in matrix section raises ConfigError."""
    config = _base_config(
        matrix={
            "user_id": "@bot:matrix.org",
            "access_token": "token",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ConfigError, match="homeserver"):
        load_config(path)


def test_matrix_missing_user_id_raises(tmp_path):
    """Missing user_id in matrix section raises ConfigError."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "access_token": "token",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ConfigError, match="user_id"):
        load_config(path)


def test_matrix_missing_room_id_raises(tmp_path):
    """Missing room_id in matrix section raises ConfigError."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "access_token": "token",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ConfigError, match="room_id"):
        load_config(path)


def test_matrix_missing_allowed_users_raises(tmp_path):
    """Missing allowed_users in matrix section raises ConfigError."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "access_token": "token",
            "room_id": "!room:matrix.org",
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ConfigError, match="allowed_users"):
        load_config(path)


def test_matrix_access_token_from_env(tmp_path):
    """access_token from MATRIX_ACCESS_TOKEN env var is accepted."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with patch.dict("os.environ", {"MATRIX_ACCESS_TOKEN": "env_token"}):
        result = load_config(path)

    assert "matrix" in result


def test_matrix_password_only_accepted(tmp_path):
    """Config with password but no access_token is valid."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "password": "secret",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with patch.dict("os.environ", {}, clear=False):
        os.environ.pop("MATRIX_ACCESS_TOKEN", None)
        result = load_config(path)

    assert "matrix" in result


def test_matrix_password_from_env(tmp_path):
    """MATRIX_PASSWORD env var is accepted as credential."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with patch.dict("os.environ", {"MATRIX_PASSWORD": "env_pass"}):
        os.environ.pop("MATRIX_ACCESS_TOKEN", None)
        result = load_config(path)

    assert "matrix" in result


def test_matrix_no_credentials_raises(tmp_path):
    """Missing both token and password raises ConfigError."""
    config = _base_config(
        matrix={
            "homeserver": "https://matrix.org",
            "user_id": "@bot:matrix.org",
            "room_id": "!room:matrix.org",
            "allowed_users": [],
        }
    )
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)

    with patch.dict("os.environ", {}, clear=False):
        os.environ.pop("MATRIX_ACCESS_TOKEN", None)
        os.environ.pop("MATRIX_PASSWORD", None)
        with pytest.raises(ConfigError, match="access_token.*password|password.*access_token"):
            load_config(path)
