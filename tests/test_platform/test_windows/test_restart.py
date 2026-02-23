"""Tests for the Windows restart strategy."""

from unittest.mock import patch


def test_windows_restart_spawns_process_and_exits():
    """windows_restart() calls Popen with current args and then sys.exit(0)."""
    with (
        patch("sprachassistent.platform.windows.restart.subprocess") as mock_sub,
        patch("sprachassistent.platform.windows.restart.sys") as mock_sys,
    ):
        mock_sys.executable = "/usr/bin/python"
        mock_sys.argv = ["sprachassistent"]

        from sprachassistent.platform.windows.restart import windows_restart

        windows_restart()

        mock_sub.Popen.assert_called_once_with(["/usr/bin/python", "sprachassistent"])
        mock_sys.exit.assert_called_once_with(0)
