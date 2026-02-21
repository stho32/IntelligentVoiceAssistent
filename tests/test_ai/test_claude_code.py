"""Tests for ClaudeCodeBackend (subprocess mocked)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from sprachassistent.ai.claude_code import ClaudeCodeBackend
from sprachassistent.exceptions import AIBackendError


@pytest.fixture()
def backend(tmp_path):
    """Create a backend with a temp working directory."""
    return ClaudeCodeBackend(
        working_directory=str(tmp_path),
        system_prompt="Test prompt",
        timeout=30,
    )


def _make_mock_process(stdout="Response text", stderr="", returncode=0):
    """Create a mock Popen process."""
    proc = MagicMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    return proc


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_returns_response(mock_popen, backend):
    """ask() returns Claude Code's stdout."""
    mock_popen.return_value = _make_mock_process(stdout="Hello from Claude")
    result = backend.ask("Say hello")
    assert result == "Hello from Claude"


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_first_call_uses_system_prompt(mock_popen, backend):
    """First ask() uses --system-prompt, not --continue."""
    mock_popen.return_value = _make_mock_process()
    backend.ask("Test message")

    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--system-prompt" in cmd
    assert "Test prompt" in cmd
    assert "--continue" not in cmd
    assert "Test message" in cmd
    assert mock_popen.call_args.kwargs["cwd"] == backend.working_directory


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_second_call_uses_continue(mock_popen, backend):
    """Subsequent ask() calls use --continue instead of --system-prompt."""
    mock_popen.return_value = _make_mock_process()

    backend.ask("First message")
    backend.ask("Second message")

    cmd = mock_popen.call_args[0][0]
    assert "--continue" in cmd
    assert "--system-prompt" not in cmd
    assert "Second message" in cmd


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_nonzero_exit_raises(mock_popen, backend):
    """Non-zero exit code raises AIBackendError."""
    mock_popen.return_value = _make_mock_process(returncode=1, stderr="Error occurred")
    with pytest.raises(AIBackendError, match="exited with code 1"):
        backend.ask("Bad command")


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_empty_response_raises(mock_popen, backend):
    """Empty stdout raises AIBackendError."""
    mock_popen.return_value = _make_mock_process(stdout="")
    with pytest.raises(AIBackendError, match="empty response"):
        backend.ask("Silent command")


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_timeout_raises(mock_popen, backend):
    """subprocess.TimeoutExpired is converted to AIBackendError."""
    proc = _make_mock_process()
    proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
    mock_popen.return_value = proc
    with pytest.raises(AIBackendError, match="did not respond"):
        backend.ask("Slow command")


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_ask_without_system_prompt(mock_popen, tmp_path):
    """First call without system prompt omits --system-prompt flag."""
    backend = ClaudeCodeBackend(working_directory=str(tmp_path))
    mock_popen.return_value = _make_mock_process(stdout="OK")
    result = backend.ask("Hello")
    assert result == "OK"

    cmd = mock_popen.call_args[0][0]
    assert "--system-prompt" not in cmd
    assert "--dangerously-skip-permissions" in cmd


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_session_not_started_on_error(mock_popen, backend):
    """Failed first call does not mark session as started."""
    mock_popen.return_value = _make_mock_process(returncode=1, stderr="fail")

    with pytest.raises(AIBackendError):
        backend.ask("Bad command")

    # Next call should still use --system-prompt, not --continue
    mock_popen.return_value = _make_mock_process(stdout="OK")
    backend.ask("Retry")

    cmd = mock_popen.call_args[0][0]
    assert "--system-prompt" in cmd
    assert "--continue" not in cmd


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_cancel_terminates_process(mock_popen, backend):
    """cancel() terminates the running subprocess."""
    proc = _make_mock_process()
    mock_popen.return_value = proc

    # Simulate a long-running process by setting _current_process directly
    backend._current_process = proc
    backend.cancel()

    proc.terminate.assert_called_once()


def test_cancel_without_process_is_noop(backend):
    """cancel() without a running process does nothing."""
    backend.cancel()  # Should not raise


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_session_state_after_cancel(mock_popen, backend):
    """Cancelled first call does not mark session as started."""
    proc = _make_mock_process()
    # Simulate cancel: communicate raises after terminate
    proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
    mock_popen.return_value = proc

    with pytest.raises(AIBackendError):
        backend.ask("Will be cancelled")

    assert backend._session_started is False


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_reset_session_clears_flag(mock_popen, backend):
    """reset_session() sets _session_started back to False."""
    mock_popen.return_value = _make_mock_process()

    backend.ask("First message")
    assert backend._session_started is True

    backend.reset_session()
    assert backend._session_started is False


@patch("sprachassistent.ai.claude_code.subprocess.Popen")
def test_reset_session_next_call_uses_system_prompt(mock_popen, backend):
    """After reset, next ask() uses --system-prompt again."""
    mock_popen.return_value = _make_mock_process()

    backend.ask("First message")
    backend.reset_session()
    backend.ask("After reset")

    cmd = mock_popen.call_args[0][0]
    assert "--system-prompt" in cmd
    assert "--continue" not in cmd


def test_reset_session_without_session_is_safe(backend):
    """reset_session() before any ask() does not raise."""
    backend.reset_session()  # Should not raise
    assert backend._session_started is False
