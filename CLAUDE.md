# CLAUDE.md - Projektrichtlinien fuer Claude Code

## Projekt

Lokaler Sprachassistent "Computer" - aktiviert per Wake-Word, versteht natuerliche Sprache
und fuehrt Aufgaben ueber Claude Code im Terminal aus.

## Verzeichnisstruktur

- `sprachassistent/` - Hauptpaket (Python)
- `Requirements/` - Anforderungsdokumente (schrittweise verfeinert und erweitert)

## Technologie-Stack

- Python 3.11+ mit uv als Paketmanager
- Picovoice Porcupine (Wake-Word)
- OpenAI Whisper API (STT)
- Claude Code / Anthropic API (KI-Backend)
- OpenAI TTS / Edge-TTS (Text-zu-Sprache)

## Tests

**Wichtig:** Bei jedem Entwicklungsschritt muessen Tests erstellt und ausgefuehrt werden.

- Fuer jede neue Funktion oder Aenderung muessen passende Unit-Tests geschrieben werden.
- Tests befinden sich im Verzeichnis `tests/` und spiegeln die Struktur von `sprachassistent/` wider.
- Vor jedem Commit muessen alle Tests erfolgreich durchlaufen.
- Testframework: `pytest`
- Tests ausfuehren mit: `uv run pytest`

## Sprache

- Code und Kommentare: Englisch
- Anforderungen und Dokumentation: Deutsch
- Keine Umlaute in Dateinamen oder Code-Bezeichnern
