# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Local voice assistant "Jarvis" - activated by wake word "Hey Jarvis", understands natural language,
and executes tasks via Claude Code subprocess against a notes folder (`~/Projekte/Training2`).

## Environment

- Ubuntu 25.04, Python 3.13, Intel NUC, Poly BT700 Headset, PipeWire Audio
- API keys required: `OPENAI_API_KEY` (Whisper STT + TTS), Anthropic key (via Claude Code)
- Node.js required for Claude Code subprocess

## Commands

- `uv run sprachassistent` - Start the voice assistant
- `uv run pytest` - Run all tests
- `uv run pytest tests/test_audio/test_recorder.py` - Run a single test file
- `uv run pytest -k test_ask_first_call` - Run a single test by name
- `uv run ruff check .` - Linting
- `uv run ruff format --check .` - Check formatting
- `uv run ruff format .` - Auto-format

## Architecture

The assistant runs a synchronous main loop in `sprachassistent/main.py`:

```
Wake Word Detection -> Ding Sound -> Record Speech -> STT (Whisper API) -> AI (Claude Code) -> TTS (OpenAI) -> Ready Sound -> Repeat
```

### Key modules

- `audio/wake_word.py` - OpenWakeWord ONNX model, processes 80ms frames (1280 samples at 16kHz)
- `audio/recorder.py` - VAD-based recording using silero-vad (PyTorch), 512-sample frames, stops on silence
- `audio/microphone.py` - PyAudio input stream context manager
- `audio/player.py` - PyAudio output: WAV playback and PCM streaming
- `stt/whisper_api.py` - Converts raw PCM to WAV in-memory, sends to OpenAI Whisper API
- `ai/claude_code.py` - Subprocess wrapper: first call uses `--system-prompt`, subsequent calls use `--continue` for persistent conversation. Strips `CLAUDECODE` env var to allow nesting.
- `tts/openai_tts.py` - Streams PCM from OpenAI TTS at 24kHz for low-latency playback
- `utils/terminal_ui.py` - Rich Live display with state machine (IDLE/LISTENING/RECORDING/PROCESSING/SPEAKING/ERROR)
- `config.py` - Loads `sprachassistent/config.yaml`, expands `~` in path values
- `exceptions.py` - Exception hierarchy rooted at `AssistantError`

### Audio format conventions

- Microphone input: 16kHz, 16-bit int16, mono PCM
- TTS output: 24kHz, 16-bit int16, mono PCM
- Wake word expects 80ms chunks (1280 samples), VAD expects 32ms frames (512 samples)

### Configuration

All settings live in `sprachassistent/config.yaml`. The system prompt for the AI persona is in `sprachassistent/ai/prompts/system.md`.

### openwakeword installation note

openwakeword is installed with `--no-deps` because `tflite-runtime` is unavailable for Python 3.13. ONNX inference framework is used instead.

## Tests

- Tests mirror the source structure: `tests/test_audio/`, `tests/test_stt/`, `tests/test_ai/`, etc.
- All external APIs and hardware (PyAudio, OpenAI, Claude Code subprocess) must be mocked.
- Every new feature or change requires corresponding tests.

## Selbstbewusstsein

Dieses Repository IST der Quelltext des Sprachassistenten Jarvis. Wenn Claude Code in diesem Verzeichnis arbeitet, arbeitet es an seinem eigenen Code -- dem Code, der den Sprachassistenten ausmacht.

### Was das bedeutet

- **Aenderungsauftraege beziehen sich auf den Assistenten selbst.** Wenn der Nutzer sagt "fuege ein Feature hinzu", "fix den Bug", oder "aendere die Konfiguration", bezieht sich das auf diesen Sprachassistenten.
- **Du bist Entwickler und Produkt zugleich.** Du schreibst Code, der dein eigenes Verhalten bestimmt.
- **Der Quelltext-Pfad ist `~/Projekte/IntelligentVoiceAssistent`.**
- **Der Notizen-Ordner (`~/Projekte/Training2`) ist ein separates Projekt** -- der Arbeitsbereich, auf den Jarvis zur Laufzeit zugreift.

### Qualitaetsansprueche bei Selbstaenderung

- Tests nach Code-Aenderungen ausfuehren (`uv run pytest`)
- Linting und Formatierung einhalten (`uv run ruff check .`, `uv run ruff format .`)
- Bestehende Architektur und Muster respektieren
- Neue Features brauchen Tests
- Anforderungsdokumente in `Requirements/` pflegen

### Anforderungsdokumente

Alle Feature-Anforderungen liegen in `Requirements/` und folgen dem Schema `NNN-Titel.md`. Neue Anforderungen erhalten die naechste freie Nummer. Aktuelle Dokumente:

- `001` bis `010`: Basisarchitektur, Konversation, Audio, UI, Fehlerbehandlung, Abbruch, Reset, Hilfe, Neustart
- `011`: Selbstbewusstsein und Quelltext-Zugriff (dieses Feature)
- `012`: Konversations-Persistenz ueber Neustart

## Language

- Code and comments: English
- Requirements and documentation: German
- No umlauts in filenames or identifiers
