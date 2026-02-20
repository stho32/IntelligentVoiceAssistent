# CLAUDE.md - Projektrichtlinien fuer Claude Code

## Projekt

Lokaler Sprachassistent "Computer" - aktiviert per Wake-Word, versteht natuerliche Sprache
und fuehrt Aufgaben ueber Claude Code im Terminal aus.

## Umgebung

- Ubuntu 25.04, Python 3.13, Intel NUC, Poly BT700 Headset, PipeWire Audio

## Verzeichnisstruktur

- `sprachassistent/` - Hauptpaket (Python)
- `ai-docs/` - API-Referenzdokumentation fuer alle Bibliotheken
- `models/` - ONNX-Modelle (nicht im Git)
- `scripts/` - Hilfsskripte (Download, Generierung)
- `tests/` - Unit- und Integrationstests
- `Requirements/` - Anforderungsdokumente

## Technologie-Stack

- Python 3.12+ mit uv als Paketmanager
- OpenWakeWord mit ONNX-Inference (Wake-Word "Computer")
- silero-vad-lite (Voice Activity Detection, kein PyTorch)
- OpenAI Whisper API (STT)
- Claude Code Subprocess `--print` (KI-Backend)
- OpenAI TTS tts-1 mit PCM-Streaming (Text-zu-Sprache)
- PyAudio (Audio I/O)
- Rich (Terminal-UI)

## Kommandos

- `uv run pytest` - Tests ausfuehren
- `uv run ruff check .` - Linting
- `uv run ruff format --check .` - Formatierung pruefen
- `uv run sprachassistent` - Assistent starten

## Tests

**Wichtig:** Bei jedem Entwicklungsschritt muessen Tests erstellt und ausgefuehrt werden.

- Fuer jede neue Funktion oder Aenderung muessen passende Unit-Tests geschrieben werden.
- Tests befinden sich im Verzeichnis `tests/` und spiegeln die Struktur von `sprachassistent/` wider.
- Vor jedem Commit muessen alle Tests erfolgreich durchlaufen.
- Testframework: `pytest`
- Externe APIs und Hardware (PyAudio, OpenAI, etc.) werden in Tests gemockt.

## Sprache

- Code und Kommentare: Englisch
- Anforderungen und Dokumentation: Deutsch
- Keine Umlaute in Dateinamen oder Code-Bezeichnern
