"""Tests for ClaudeCodeBackend (subprocess mocked)."""

import subprocess
from unittest.mock import patch

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


def _make_result(stdout="Response text", stderr="", returncode=0):
    """Create a mock subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["claude", "--print", "test"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_returns_response(mock_run, backend):
    """ask() returns Claude Code's stdout."""
    mock_run.return_value = _make_result(stdout="Hello from Claude")
    result = backend.ask("Say hello")
    assert result == "Hello from Claude"


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_passes_correct_command(mock_run, backend):
    """ask() calls claude --print with system prompt and user message."""
    mock_run.return_value = _make_result()
    backend.ask("Test message")

    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--system-prompt" in cmd
    assert "Test prompt" in cmd
    assert "Test message" in cmd
    assert call_args.kwargs["cwd"] == backend.working_directory


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_nonzero_exit_raises(mock_run, backend):
    """Non-zero exit code raises RuntimeError."""
    mock_run.return_value = _make_result(returncode=1, stderr="Error occurred")
    with pytest.raises(AIBackendError, match="exited with code 1"):
        backend.ask("Bad command")


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_empty_response_raises(mock_run, backend):
    """Empty stdout raises RuntimeError."""
    mock_run.return_value = _make_result(stdout="")
    with pytest.raises(AIBackendError, match="empty response"):
        backend.ask("Silent command")


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_timeout_raises(mock_run, backend):
    """subprocess.TimeoutExpired is converted to TimeoutError."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
    with pytest.raises(AIBackendError, match="did not respond"):
        backend.ask("Slow command")


@patch("sprachassistent.ai.claude_code.subprocess.run")
def test_ask_without_system_prompt(mock_run, tmp_path):
    """Works without a system prompt."""
    backend = ClaudeCodeBackend(working_directory=str(tmp_path))
    mock_run.return_value = _make_result(stdout="OK")
    result = backend.ask("Hello")
    assert result == "OK"

    cmd = mock_run.call_args[0][0]
    assert "--system-prompt" not in cmd
