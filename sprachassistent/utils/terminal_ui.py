"""Terminal UI using Rich.

Displays the voice assistant's current state, transcription,
and response in a dynamic terminal panel.
"""

from enum import Enum

from rich.console import Console
from rich.live import Live
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
    AssistantState.LISTENING: ("green", "Listening for 'Computer'..."),
    AssistantState.RECORDING: ("bright_green", "Recording speech..."),
    AssistantState.PROCESSING: ("blue", "Processing..."),
    AssistantState.SPEAKING: ("cyan", "Speaking..."),
    AssistantState.ERROR: ("red", "Error"),
}


class TerminalUI:
    """Rich-based terminal status display for the voice assistant.

    Usage::

        ui = TerminalUI()
        with ui:
            ui.set_state(AssistantState.LISTENING)
            ui.set_transcription("Hallo Computer")
            ui.set_response("Hallo! Wie kann ich helfen?")
    """

    def __init__(self):
        self.console = Console()
        self._state = AssistantState.IDLE
        self._transcription = ""
        self._response = ""
        self._live: Live | None = None

    def __enter__(self) -> "TerminalUI":
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
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
        """Update the displayed transcription."""
        self._transcription = text
        self._refresh()

    def set_response(self, text: str) -> None:
        """Update the displayed AI response."""
        self._response = text
        self._refresh()

    def log(self, message: str) -> None:
        """Print a log message above the status display."""
        if self._live is not None:
            self._live.console.log(message)

    def _refresh(self) -> None:
        """Re-render the display."""
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Panel:
        """Build the status panel."""
        color, label = _STATE_CONFIG[self._state]

        content = Text()
        content.append("Status: ", style="bold")
        content.append(label, style=f"bold {color}")

        if self._transcription:
            content.append("\n\nYou: ", style="bold")
            content.append(self._transcription)

        if self._response:
            content.append("\n\nAssistant: ", style="bold")
            content.append(self._response, style="dim")

        return Panel(
            content,
            title="[bold]Sprachassistent[/bold]",
            border_style=color,
        )
