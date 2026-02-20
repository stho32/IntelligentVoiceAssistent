# Rich Terminal Library API Reference

> Rich v14.1.0 -- Python library for rich text and beautiful formatting in the terminal.
> Install: `pip install rich`

## Quick Start

```python
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
console.print("[bold green]Hello[/bold green] World!")
console.print(Panel("Bordered content", title="My Panel"))
```

## Console Class

### Constructor

```python
from rich.console import Console

console = Console(
    stderr=False,              # True to write to sys.stderr
    style=None,                # Default style for all output (e.g., "bold")
    width=None,                # Override terminal width (None = auto-detect)
    file=None,                 # File-like object (None = sys.stdout)
    record=False,              # Enable output recording for export
    force_terminal=False,      # Force terminal control codes
    force_interactive=None,    # Override animation behavior (True/False/None)
    color_system="auto",       # "auto", "standard" (16), "256", "truecolor", "windows", or None
    markup=True,               # Enable console markup parsing
    highlight=True,            # Enable syntax highlighting
)
```

### print()

```python
console.print(
    *objects,                  # Objects to print (strings, renderables, etc.)
    sep=" ",                   # Separator between objects
    end="\n",                  # String appended after last object
    style=None,                # Style to apply (e.g., "bold red")
    justify=None,              # "default", "left", "right", "center", "full"
    overflow=None,             # "fold" (default), "crop", "ellipsis", "ignore"
    highlight=None,            # Enable/disable highlighting (None = use console default)
    markup=None,               # Enable/disable markup (None = use console default)
    soft_wrap=False,           # True to disable word wrapping
)
```

### Other Key Methods

```python
console.log(*objects, log_locals=False)    # Print with timestamp + source location
console.rule(title="Section", style="rule.line", align="center")  # Horizontal divider
console.clear()                            # Clear the terminal
console.input(prompt="Enter: ")            # Rich-aware input()
console.bell()                             # Terminal bell
```

### Auto-Detected Properties

```python
console.size          # Terminal dimensions (width, height)
console.encoding      # Text encoding (typically "utf-8")
console.is_terminal   # True if output is a real terminal
console.color_system  # Detected color system
```

### Export (requires `record=True`)

```python
console = Console(record=True)
console.print("Hello!")
text = console.export_text()       # Plain text
html = console.export_html()       # HTML
svg = console.export_svg()         # SVG
console.save_text("out.txt")       # Save to file
console.save_html("out.html")
console.save_svg("out.svg")
```

### Capture Output

```python
with console.capture() as capture:
    console.print("Hello")
output = capture.get()  # "Hello\n"
```

## Console Markup (BBCode-style)

Rich uses square-bracket tags inspired by BBCode for inline styling.

### Syntax

```python
console.print("[bold]Bold text[/bold]")
console.print("[bold red]Bold and red[/bold red]")
console.print("[bold red]Bold red[/] back to normal")     # [/] closes last tag
console.print("[bold]Bold [italic]bold+italic[/bold] italic only[/italic]")  # Overlapping OK
console.print("[link=https://example.com]Click here[/link]")   # Hyperlinks
console.print(":warning: Emoji codes")                         # Emoji with :name:
```

### Common Style Names

- Colors: `red`, `green`, `blue`, `yellow`, `cyan`, `magenta`, `white`, `black`
- Bright colors: `bright_red`, `bright_green`, etc.
- Modifiers: `bold`, `dim`, `italic`, `underline`, `strike`, `reverse`, `blink`
- Background: `on red`, `on blue`, `on bright_green`, etc.
- Combined: `"bold white on blue"`, `"italic bright_red"`
- Hex colors: `"#ff8800"`, `"on #004400"`
- RGB: `"rgb(255,128,0)"`

### Escaping Markup

```python
from rich.markup import escape

# Backslash escaping
console.print(r"Use \[bold] for bold")      # Prints: Use [bold] for bold

# Programmatic escaping
user_input = "some [dangerous] input"
console.print(f"User said: {escape(user_input)}")

# Disable markup entirely
console.print("[bold]Not bold[/bold]", markup=False)
```

## Text Class

Programmatic styled text construction -- use when markup strings are insufficient.

### Constructor and Factory Methods

```python
from rich.text import Text

# Basic construction
text = Text("Hello, World!")
text.stylize("bold magenta", 0, 6)  # Apply style to character range [start, end)

# From markup string
text = Text.from_markup("[bold]Hello[/bold] World")

# Assemble from parts
text = Text.assemble(
    ("Hello", "bold magenta"),    # (string, style) tuples
    ", ",                         # Plain strings
    ("World!", "italic green"),
)
```

### Key Methods

```python
text.stylize(style, start=0, end=None)         # Apply style to range
text.append(string, style=None)                 # Append styled text
text.highlight_words(words, style)              # Style specific words
text.highlight_regex(pattern, style)            # Style regex matches
text.plain                                      # Get/set plain text (no styles)
```

### Constructor Parameters

```python
Text(
    text="",
    style=None,            # Base style
    justify=None,          # "left", "center", "right", "full"
    overflow=None,         # "fold", "crop", "ellipsis"
    no_wrap=False,         # Prevent wrapping
    tab_size=8,            # Characters per tab
)
```

## Panel

Bordered box around content.

### Constructor

```python
from rich.panel import Panel

panel = Panel(
    renderable,            # Content to display (string, Text, Table, etc.)
    title=None,            # Optional title at top border
    subtitle=None,         # Optional subtitle at bottom border
    title_align="center",  # "left", "center", "right"
    subtitle_align="center",
    box=box.ROUNDED,       # Border style (see rich.box)
    border_style="",       # Style for the border (e.g., "bright_blue")
    expand=True,           # True to fill terminal width, False to fit content
    width=None,            # Explicit width
    height=None,           # Explicit height
    padding=(0, 1),        # (top/bottom, left/right) or (top, right, bottom, left)
    highlight=False,       # Enable syntax highlighting of content
)
```

### Panel.fit()

```python
# Panel sized to fit content (shorthand for expand=False)
panel = Panel.fit("Hello, World!", title="Greeting")
console.print(panel)
```

### Common Box Styles

```python
from rich import box
# box.ROUNDED (default), box.SQUARE, box.HEAVY, box.DOUBLE,
# box.MINIMAL, box.SIMPLE, box.ASCII, box.MARKDOWN
```

### Examples

```python
console.print(Panel("Simple panel"))
console.print(Panel("With title", title="Info", border_style="green"))
console.print(Panel.fit("[bold]Fitted[/bold] panel", title="Status", border_style="cyan"))
console.print(Panel(
    Panel("Inner", title="Nested"),
    title="Outer",
))
```

## Status Spinner

Displays an animated spinner with a status message. Other console output is not disrupted.

### Via Console (recommended)

```python
with console.status("Processing...") as status:
    # Do work...
    status.update("Almost done...")
    # Do more work...
# Spinner disappears when context exits
```

### Via Status Class Directly

```python
from rich.status import Status

status = Status(
    status="Working...",           # Status message (string or renderable)
    console=None,                  # Console instance (None = default)
    spinner="dots",                # Spinner animation name
    spinner_style="status.spinner", # Style for the spinner
    speed=1.0,                     # Animation speed multiplier
    refresh_per_second=12.5,       # Update frequency
)
```

### Methods

```python
status.start()                             # Start the spinner
status.stop()                              # Stop and remove the spinner
status.update(
    status=None,                           # New status message
    spinner=None,                          # New spinner name
    spinner_style=None,                    # New spinner style
    speed=None,                            # New speed
)
```

### As Context Manager

```python
with Status("Loading...", spinner="dots") as status:
    # Work happens here
    status.update("Phase 2...")
    # More work...
# Automatically stopped on exit
```

### Available Spinners

Common spinner names: `"dots"`, `"line"`, `"dots2"`, `"dots3"`, `"arc"`, `"bouncingBar"`,
`"clock"`, `"earth"`, `"moon"`, `"runner"`, `"toggle"`, `"star"`, `"pong"`, `"hamburger"`.

Full list: `python -m rich.spinner`

## Live Display

For fully custom dynamic terminal displays that update in-place.

### Constructor

```python
from rich.live import Live

live = Live(
    renderable=None,           # Initial renderable to display
    console=None,              # Console instance
    refresh_per_second=4,      # Auto-refresh rate
    screen=False,              # True for alternate full-screen mode
    transient=False,           # True to remove display on exit
    auto_refresh=True,         # False for manual refresh only
    vertical_overflow="ellipsis",  # "crop", "ellipsis", "visible"
    redirect_stdout=True,      # Redirect stdout to prevent visual disruption
    redirect_stderr=True,      # Redirect stderr similarly
)
```

### Context Manager Usage

```python
from rich.live import Live
from rich.panel import Panel

# Method 1: Update the renderable in-place
with Live(panel, refresh_per_second=4):
    # Modify panel content; Live auto-refreshes
    pass

# Method 2: Replace the renderable via update()
with Live(refresh_per_second=4) as live:
    for state in ["Listening...", "Processing...", "Speaking..."]:
        live.update(Panel(f"[bold]{state}[/bold]", title="Assistant"))
        time.sleep(1)
```

### Key Methods

```python
live.update(renderable, refresh=False)    # Replace displayed content
live.refresh()                            # Force immediate refresh
live.console                              # Access internal Console for logging
```

### Logging While Live

```python
with Live(panel) as live:
    live.console.log("This appears above the live display")
    live.update(new_panel)
```

### Manual Refresh Mode

```python
with Live(auto_refresh=False) as live:
    live.update(panel, refresh=True)       # Update + immediate refresh
    # or
    live.update(panel)
    live.refresh()                         # Separate refresh call
```

## Practical Pattern: Voice Assistant Status Display

```python
import time
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()

def make_status_panel(state: str, detail: str = "") -> Panel:
    """Create a status panel for the voice assistant."""
    state_styles = {
        "idle": "dim white",
        "listening": "bold green",
        "processing": "bold yellow",
        "speaking": "bold cyan",
        "error": "bold red",
    }
    style = state_styles.get(state, "white")
    content = Text.assemble(
        ("State: ", "bold"),
        (state.upper(), style),
    )
    if detail:
        content.append(f"\n{detail}")
    return Panel(content, title="Voice Assistant", border_style=style)

# Usage with Live display
with Live(make_status_panel("idle"), refresh_per_second=4, transient=True) as live:
    live.update(make_status_panel("listening", "Waiting for speech..."))
    time.sleep(2)
    live.update(make_status_panel("processing", "Transcribing audio..."))
    time.sleep(1)
    live.update(make_status_panel("speaking", "Playing response..."))
    time.sleep(2)
    live.update(make_status_panel("idle"))
```

## Sources

- [Rich Console API Reference](https://rich.readthedocs.io/en/stable/reference/console.html)
- [Rich Console Guide](https://rich.readthedocs.io/en/latest/console.html)
- [Rich Live Display](https://rich.readthedocs.io/en/latest/live.html)
- [Rich Status Reference](https://rich.readthedocs.io/en/stable/reference/status.html)
- [Rich Panel Guide](https://rich.readthedocs.io/en/latest/panel.html)
- [Rich Text Guide](https://rich.readthedocs.io/en/latest/text.html)
- [Rich Markup Guide](https://rich.readthedocs.io/en/latest/markup.html)
- [Rich on GitHub](https://github.com/Textualize/rich)
- [Rich on PyPI](https://pypi.org/project/rich/)
