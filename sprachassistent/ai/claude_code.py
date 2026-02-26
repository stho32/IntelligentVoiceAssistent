"""Claude Code subprocess wrapper.

Sends transcribed user commands to Claude Code via the --print flag.
Maintains a persistent conversation using --continue for follow-up turns.
Supports resuming a previous session with --resume.
"""

import os
import subprocess
from pathlib import Path

from sprachassistent.exceptions import AIBackendError
from sprachassistent.utils.logging import get_logger

log = get_logger("ai.claude_code")


class ClaudeCodeBackend:
    """AI backend using Claude Code as a subprocess.

    Maintains a persistent conversation across multiple ask() calls.
    By default, the first call resumes the most recent session (--resume).
    If no previous session exists, it falls back to starting fresh
    with the system prompt. Subsequent calls use --continue.

    Args:
        working_directory: Directory where Claude Code operates (notes folder).
        system_prompt: System prompt text for Claude Code.
        timeout: Maximum seconds to wait for a response.
        resume_session: If True (default), first call uses --resume to
            continue the most recent Claude Code session.
    """

    def __init__(
        self,
        working_directory: str | Path,
        system_prompt: str = "",
        timeout: int = 120,
        resume_session: bool = True,
    ):
        self.working_directory = str(working_directory)
        self.system_prompt = system_prompt
        self.timeout = timeout
        self._session_started = False
        self._resume_on_next = resume_session
        self._current_process: subprocess.Popen | None = None

    def _build_cmd(self, user_message: str) -> list[str]:
        """Build the Claude Code command list.

        Args:
            user_message: The transcribed user command.

        Returns:
            Command list for subprocess.Popen.
        """
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]

        if self._session_started:
            cmd.append("--continue")
        elif self._resume_on_next:
            cmd.append("--resume")
        elif self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])

        cmd.append(user_message)
        return cmd

    def _run_command(self, cmd: list[str]) -> str:
        """Execute a Claude Code command and return the response.

        Args:
            cmd: Command list for subprocess.Popen.

        Returns:
            Claude Code's text response.

        Raises:
            AIBackendError: If Claude Code returns a non-zero exit code,
                times out, or returns an empty response.
        """
        # Remove CLAUDECODE env var to allow running inside a Claude Code session
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=self.working_directory,
                env=env,
            )
            stdout, stderr = self._current_process.communicate(timeout=self.timeout)
            returncode = self._current_process.returncode
        except subprocess.TimeoutExpired:
            if self._current_process:
                self._current_process.kill()
                self._current_process.wait()
            raise AIBackendError(
                f"Claude Code did not respond within {self.timeout}s"
            ) from subprocess.TimeoutExpired(cmd=cmd, timeout=self.timeout)
        finally:
            self._current_process = None

        if returncode != 0:
            raise AIBackendError(f"Claude Code exited with code {returncode}: {stderr.strip()}")

        response = stdout.strip()
        if not response:
            raise AIBackendError("Claude Code returned an empty response.")

        return response

    def ask(self, user_message: str) -> str:
        """Send a message to Claude Code and get a response.

        The first call either resumes the most recent session (default)
        or starts fresh with the system prompt. Subsequent calls continue
        the same conversation, preserving context.

        If --resume fails (e.g. no previous session), automatically falls
        back to starting a fresh session with --system-prompt.

        Args:
            user_message: The transcribed user command.

        Returns:
            Claude Code's text response.

        Raises:
            AIBackendError: If Claude Code returns a non-zero exit code,
                times out, or is cancelled.
        """
        cmd = self._build_cmd(user_message)
        log.info("Asking Claude Code: %s", user_message[:80])

        try:
            response = self._run_command(cmd)
        except AIBackendError:
            if self._resume_on_next:
                log.warning("--resume failed, starting fresh session")
                self._resume_on_next = False
                cmd = self._build_cmd(user_message)
                response = self._run_command(cmd)
            else:
                raise

        self._session_started = True
        self._resume_on_next = False
        log.info("Claude Code response: %s", response[:80])
        return response

    def reset_session(self) -> None:
        """Reset the conversation session.

        The next ask() call will start a fresh session with the system
        prompt instead of using --continue or --resume.
        """
        self._session_started = False
        self._resume_on_next = False
        log.info("Conversation session reset")

    def cancel(self) -> None:
        """Cancel the currently running AI request.

        Terminates the subprocess if one is running. Safe to call
        even if no process is active (no-op).
        """
        proc = self._current_process
        if proc is not None:
            log.info("Cancelling Claude Code subprocess")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
