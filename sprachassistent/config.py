"""Configuration loader for the voice assistant.

Loads settings from config.yaml and provides typed access.
"""

import os
from pathlib import Path

import yaml

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
    }
    for section_key, value_key in path_keys:
        section = config.get(section_key, {})
        if value_key in section and isinstance(section[value_key], str):
            section[value_key] = os.path.expanduser(section[value_key])
