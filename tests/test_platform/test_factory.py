"""Tests for platform detection and factory functions."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.platform.factory import (
    create_audio_input,
    create_audio_output,
    create_restart_strategy,
    detect_platform,
)


class TestDetectPlatform:
    def test_linux(self):
        with patch("sprachassistent.platform.factory.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert detect_platform() == "linux"

    def test_windows(self):
        with patch("sprachassistent.platform.factory.sys") as mock_sys:
            mock_sys.platform = "win32"
            assert detect_platform() == "windows"

    def test_unsupported_raises(self):
        with patch("sprachassistent.platform.factory.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                detect_platform()


class TestCreateAudioInput:
    def test_linux_creates_microphone_stream(self):
        """Linux factory creates MicrophoneStream from audio.microphone."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.MicrophoneStream = mock_cls

        with patch.dict(sys.modules, {"sprachassistent.audio.microphone": mock_module}):
            result = create_audio_input(rate=16000, channels=1, chunk_size=1280, platform="linux")

        mock_cls.assert_called_once_with(rate=16000, channels=1, chunk_size=1280)
        assert result is mock_cls.return_value

    def test_windows_creates_windows_microphone_stream(self):
        """Windows factory creates WindowsMicrophoneStream."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.WindowsMicrophoneStream = mock_cls

        with patch.dict(
            sys.modules, {"sprachassistent.platform.windows.microphone": mock_module}
        ):
            result = create_audio_input(
                rate=16000, channels=1, chunk_size=1280, platform="windows"
            )

        mock_cls.assert_called_once_with(rate=16000, channels=1, chunk_size=1280)
        assert result is mock_cls.return_value

    def test_unsupported_platform_raises(self):
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            create_audio_input(platform="darwin")


class TestCreateAudioOutput:
    def test_linux_creates_audio_player(self):
        """Linux factory creates AudioPlayer."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.AudioPlayer = mock_cls

        with patch.dict(sys.modules, {"sprachassistent.audio.player": mock_module}):
            result = create_audio_output(platform="linux")

        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_windows_creates_windows_audio_player(self):
        """Windows factory creates WindowsAudioPlayer."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.WindowsAudioPlayer = mock_cls

        with patch.dict(sys.modules, {"sprachassistent.platform.windows.player": mock_module}):
            result = create_audio_output(platform="windows")

        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_unsupported_platform_raises(self):
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            create_audio_output(platform="darwin")


class TestCreateRestartStrategy:
    def test_linux_returns_linux_restart(self):
        """Linux factory returns linux_restart callable."""
        mock_fn = MagicMock()
        mock_module = MagicMock()
        mock_module.linux_restart = mock_fn

        with patch.dict(sys.modules, {"sprachassistent.platform._linux_restart": mock_module}):
            result = create_restart_strategy(platform="linux")

        assert result is mock_fn

    def test_windows_returns_windows_restart(self):
        """Windows factory returns windows_restart callable."""
        mock_fn = MagicMock()
        mock_module = MagicMock()
        mock_module.windows_restart = mock_fn

        with patch.dict(sys.modules, {"sprachassistent.platform.windows.restart": mock_module}):
            result = create_restart_strategy(platform="windows")

        assert result is mock_fn

    def test_unsupported_platform_raises(self):
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            create_restart_strategy(platform="darwin")
