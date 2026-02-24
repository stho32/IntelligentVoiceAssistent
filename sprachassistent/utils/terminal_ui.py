"""Terminal UI using Rich.

Displays the voice assistant's current state as a dynamic status panel
at the bottom of the terminal, with conversation history printed above.
"""

from datetime import datetime
from enum import Enum

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


class AssistantState(Enum):
    """Voice assistant states."""

    IDLE = "idle"
    LISTENING = "listening"
    RECORDING = "recording"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


_STATE_CONFIG = {
    AssistantState.IDLE: ("yellow", "Waiting for wake word..."),
    AssistantState.LISTENING: ("green", "Listening for 'Hey Jarvis'..."),
    AssistantState.RECORDING: ("bright_green", "Recording speech..."),
    AssistantState.PROCESSING: ("blue", "Processing..."),
    AssistantState.SPEAKING: ("cyan", "Speaking..."),
    AssistantState.ERROR: ("red", "Error"),
}


class TerminalUI:
    """Rich-based terminal status display for the voice assistant.

    The status panel stays at the bottom (transient Live display).
    Conversation turns and system messages are printed above it.

    Usage::

        ui = TerminalUI()
        with ui:
            ui.set_state(AssistantState.LISTENING)
            ui.set_transcription("Hey Jarvis, wie wird das Wetter?")
            ui.set_response("Hallo! Wie kann ich helfen?")
            ui.print_conversation_turn()
    """

    def __init__(self):
        self.console = Console()
        self._state = AssistantState.IDLE
        self._transcription = ""
        self._response = ""
        self._transcription_time: str = ""
        self._response_time: str = ""
        self._live: Live | None = None

    def __enter__(self) -> "TerminalUI":
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        )
        self._live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        return None

    def set_state(self, state: AssistantState) -> None:
        """Update the displayed state."""
        self._state = state
        self._refresh()

    def set_transcription(self, text: str) -> None:
        """Store user transcription with timestamp."""
        self._transcription = text
        self._transcription_time = datetime.now().strftime("%H:%M:%S")

    def set_response(self, text: str) -> None:
        """Store AI response with timestamp."""
        self._response = text
        self._response_time = datetime.now().strftime("%H:%M:%S")

    def print_conversation_turn(self) -> None:
        """Print a completed conversation turn above the status panel.

        Formats the user's transcription and the AI response as a
        readable conversation block with timestamps.
        """
        if not self._transcription and not self._response:
            return

        console = self._live.console if self._live else self.console

        if self._transcription:
            user_line = Text()
            user_line.append(f"[{self._transcription_time}] ", style="dim")
            user_line.append("Du: ", style="bold green")
            user_line.append(self._transcription)
            console.print(user_line)
            console.print()

        if self._response:
            header = Text()
            header.append(f"[{self._response_time}] ", style="dim")
            header.append("Jarvis:", style="bold cyan")
            console.print(header)
            console.print(Markdown(self._response))
            console.print()

    def log(self, message: str) -> None:
        """Print a system message above the status display."""
        if self._live is not None:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            text = Text()
            text.append(f"{timestamp} ", style="dim")
            text.append(message, style="dim")
            self._live.console.print(text)

    def _refresh(self) -> None:
        """Re-render the display."""
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Panel:
        """Build the status panel (status only, no transcription/response)."""
        color, label = _STATE_CONFIG[self._state]

        content = Text()
        content.append("Status: ", style="bold")
        content.append(label, style=f"bold {color}")

        return Panel(
            content,
            title="[bold]Sprachassistent[/bold]",
            border_style=color,
        )
