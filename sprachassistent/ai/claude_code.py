"""Claude Code subprocess wrapper.

Sends transcribed user commands to Claude Code via the --print flag.
Maintains a persistent conversation using --continue for follow-up turns.
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
    The first call starts a new session with the system prompt,
    subsequent calls use --continue to stay in the same conversation.

    Args:
        working_directory: Directory where Claude Code operates (notes folder).
        system_prompt: System prompt text for Claude Code.
        timeout: Maximum seconds to wait for a response.
    """

    def __init__(
        self,
        working_directory: str | Path,
        system_prompt: str = "",
        timeout: int = 120,
    ):
        self.working_directory = str(working_directory)
        self.system_prompt = system_prompt
        self.timeout = timeout
        self._session_started = False

    def ask(self, user_message: str) -> str:
        """Send a message to Claude Code and get a response.

        The first call starts a new session. Subsequent calls continue
        the same conversation, preserving context.

        Args:
            user_message: The transcribed user command.

        Returns:
            Claude Code's text response.

        Raises:
            AIBackendError: If Claude Code returns a non-zero exit code or times out.
        """
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]

        if self._session_started:
            cmd.append("--continue")
        elif self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])

        cmd.append(user_message)

        log.info("Asking Claude Code: %s", user_message[:80])

        # Remove CLAUDECODE env var to allow running inside a Claude Code session
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_directory,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            raise AIBackendError(f"Claude Code did not respond within {self.timeout}s") from e

        if result.returncode != 0:
            raise AIBackendError(
                f"Claude Code exited with code {result.returncode}: {result.stderr.strip()}"
            )

        response = result.stdout.strip()
        if not response:
            raise AIBackendError("Claude Code returned an empty response.")

        self._session_started = True
        log.info("Claude Code response: %s", response[:80])
        return response
