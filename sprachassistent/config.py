"""Configuration loader for the voice assistant.

Loads settings from config.yaml and provides typed access.
"""

import os
from pathlib import Path

import yaml

from sprachassistent.exceptions import ConfigError

_CONFIG_DIR = Path(__file__).parent
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "config.yaml"
_EXAMPLE_CONFIG_PATH = _CONFIG_DIR / "config.example.yaml"

_config: dict | None = None


def load_config(path: Path | None = None) -> dict:
    """Load configuration from a YAML file.

    Args:
        path: Path to the config file. Defaults to sprachassistent/config.yaml.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    if path is not None:
        config_path = path
    elif _DEFAULT_CONFIG_PATH.exists():
        config_path = _DEFAULT_CONFIG_PATH
    elif _EXAMPLE_CONFIG_PATH.exists():
        config_path = _EXAMPLE_CONFIG_PATH
    else:
        raise FileNotFoundError(f"Config file not found: {_DEFAULT_CONFIG_PATH}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    _expand_paths(config)
    _validate_matrix_config(config)
    return config


def get_config() -> dict:
    """Get the cached configuration, loading it if necessary."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _expand_paths(config: dict) -> None:
    """Expand ~ and environment variables in path-like config values."""
    path_keys = {
        ("ai", "working_directory"),
        ("ai", "source_directory"),
        ("wake_word", "model_path"),
        ("ai", "system_prompt_path"),
        ("logging", "file"),
        ("matrix", "store_path"),
    }
    for section_key, value_key in path_keys:
        section = config.get(section_key, {})
        if value_key in section and isinstance(section[value_key], str):
            section[value_key] = os.path.expanduser(section[value_key])


def _validate_matrix_config(config: dict) -> None:
    """Validate the optional matrix configuration section.

    If the 'matrix' section is absent, nothing happens (Matrix is optional).
    If present, required fields are checked and access_token must be in
    config or the MATRIX_ACCESS_TOKEN environment variable.

    Raises:
        ConfigError: If the matrix section is present but incomplete.
    """
    matrix = config.get("matrix")
    if matrix is None:
        return

    required = ("homeserver", "user_id", "room_id")
    for field in required:
        if not matrix.get(field):
            raise ConfigError(f"matrix.{field} is required when matrix section is present")

    has_token = bool(matrix.get("access_token") or os.environ.get("MATRIX_ACCESS_TOKEN"))
    has_password = bool(matrix.get("password") or os.environ.get("MATRIX_PASSWORD"))
    if not has_token and not has_password:
        raise ConfigError(
            "matrix: either access_token/MATRIX_ACCESS_TOKEN or "
            "password/MATRIX_PASSWORD must be provided"
        )

    if "allowed_users" not in matrix:
        raise ConfigError("matrix.allowed_users must be present (may be an empty list)")

    if not isinstance(matrix["allowed_users"], list):
        raise ConfigError("matrix.allowed_users must be a list")
