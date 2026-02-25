"""Text input collection for the voice assistant.

Temporarily takes over the terminal from Rich Live to let the user
type a message. Supports multi-line input (empty line sends, Esc cancels).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sprachassistent.utils.terminal_ui import TerminalUI


class TextInput:
    """Collects multi-line text input from the terminal.

    Usage::

        text_input = TextInput()
        text = text_input.collect(initial_char="h", ui=ui)
        if text:
            process(text)
    """

    def collect(self, initial_char: str, ui: TerminalUI) -> str | None:
        """Collect text from the user.

        Pauses the Rich Live display, shows a prompt with the initial
        character, and reads lines until an empty line (double Enter)
        is entered. Esc as the sole character on a line cancels.

        Args:
            initial_char: First character already typed by the user.
            ui: Terminal UI instance for Live display coordination.

        Returns:
            The entered text, or None if cancelled or empty.
        """
        ui.stop_live()
        try:
            return self._read_input(initial_char, ui)
        finally:
            ui.start_live()

    def _read_input(self, initial_char: str, ui: TerminalUI) -> str | None:
        """Read multi-line input from the user."""
        ui.console.print()
        ui.console.print(
            "[bold magenta]Texteingabe[/bold magenta] "
            "[dim](leere Zeile = senden, Esc = abbrechen)[/dim]"
        )

        lines: list[str] = []

        # First line: show the initial character as pre-filled text
        try:
            first_line = input(f"> {initial_char}")
            full_first = initial_char + first_line
        except (EOFError, KeyboardInterrupt):
            ui.console.print("[dim]Eingabe abgebrochen.[/dim]")
            return None

        # Check for Esc (character \x1b)
        if full_first == "\x1b":
            ui.console.print("[dim]Eingabe abgebrochen.[/dim]")
            return None

        lines.append(full_first)

        # Read subsequent lines until empty line
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                ui.console.print("[dim]Eingabe abgebrochen.[/dim]")
                return None

            # Esc as sole content cancels
            if line == "\x1b":
                ui.console.print("[dim]Eingabe abgebrochen.[/dim]")
                return None

            # Empty line sends
            if not line:
                break

            lines.append(line)

        text = "\n".join(lines).strip()
        if not text:
            return None

        return text
