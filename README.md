# Sprachassistent "Jarvis"

Ein lokaler Sprachassistent, der per Wake-Word **"Hey Jarvis"** aktiviert wird, natuerliche Sprache versteht und Aufgaben ueber Claude Code im Terminal ausfuehrt -- mit Lese-/Schreibzugriff auf einen konfigurierbaren Notizen-Ordner. Optional auch per **Matrix-Chat** (z.B. Element-App auf dem Smartphone) erreichbar.

## Funktionsweise

```
"Hey Jarvis" → *ding* → Spracheingabe → Stille erkannt → Whisper STT → Claude Code → OpenAI TTS → *ready*
```

1. **Wake-Word-Erkennung** -- OpenWakeWord erkennt "Hey Jarvis" lokal (ONNX-Inference, kein Cloud-Zugriff)
2. **Sprachaufnahme** -- Silero-VAD erkennt Sprechpausen und beendet die Aufnahme automatisch
3. **Sprache-zu-Text** -- OpenAI Whisper API transkribiert die Aufnahme (primaer Deutsch)
4. **KI-Verarbeitung** -- Claude Code wird als Subprocess aufgerufen und fuehrt Dateioperationen im Notizen-Ordner aus
5. **Text-zu-Sprache** -- OpenAI TTS streamt die Antwort als PCM-Audio fuer niedrige Latenz
6. **Durchgehende Konversation** -- Folgebefehle nutzen `--continue`, sodass Rueckbezuege moeglich sind

## Voraussetzungen

- **Betriebssystem:** Ubuntu 25.04, Windows 11 (oder kompatibel)
- **Python:** 3.12+
- **Node.js:** 18+ (fuer Claude Code)
- **Paketmanager:** [uv](https://docs.astral.sh/uv/)
- **Claude Code:** Muss global installiert sein (`npm install -g @anthropic/claude-code`)
- **Hardware:** Mikrofon und Lautsprecher/Kopfhoerer (optional im Chat-Only-Modus)
- **Internetverbindung:** Fuer OpenAI- und Anthropic-APIs

### API-Keys

| Dienst | Umgebungsvariable | Verwendung |
|--------|-------------------|------------|
| OpenAI | `OPENAI_API_KEY` | Whisper STT + TTS |
| Anthropic | ueber Claude Code konfiguriert | KI-Backend |
| Matrix (optional) | `MATRIX_ACCESS_TOKEN` | Matrix-Chat-Integration |

## Installation

```bash
# Repository klonen
git clone <repo-url>
cd IntelligentVoiceAssistent

# Abhaengigkeiten installieren
uv sync

# openwakeword separat installieren (--no-deps wegen tflite auf Python 3.13)
uv pip install openwakeword --no-deps

# Optional: Matrix-Chat-Integration installieren
uv sync --extra matrix

# API-Keys setzen
export OPENAI_API_KEY="sk-..."
```

## Verwendung

```bash
# Assistent starten (Sprache + optionaler Matrix-Chat)
uv run sprachassistent

# Nur Matrix-Chat (ohne Audio-Hardware, z.B. auf einem Server)
uv run sprachassistent --chat-only

# Neue Konversation starten (ohne vorherige Session fortzusetzen)
uv run sprachassistent --new-session
```

Der Assistent zeigt ein Rich-Terminal-UI mit dem aktuellen Status an:
- **Listening** -- Wartet auf "Hey Jarvis" (und prueft Matrix-Chat-Queue)
- **Recording** -- Nimmt Sprache auf
- **Processing** -- Transkription und KI-Verarbeitung
- **Speaking** -- Spricht die Antwort vor

Beenden mit `Ctrl+C`.

### Beispiel-Interaktion

```
Nutzer: "Hey Jarvis"
  → *ding*
Nutzer: "Erstelle eine Notiz fuer morgen: Meeting um 10 Uhr mit Team Alpha"
  → Claude Code erstellt die Notiz
  → "Ich habe die Notiz fuer morgen erstellt."

Nutzer: "Hey Jarvis"
  → *ding*
Nutzer: "Aendere die Uhrzeit auf 11 Uhr"
  → Claude Code weiss durch die durchgehende Konversation, welche Notiz gemeint ist
  → "Ich habe die Uhrzeit auf 11 Uhr geaendert."
```

## Konfiguration

Alle Einstellungen befinden sich in `sprachassistent/config.yaml`:

```yaml
wake_word:
  engine: openwakeword
  model_name: "hey_jarvis"
  threshold: 0.5

stt:
  provider: openai
  model: whisper-1
  language: de

ai:
  backend: claude-code
  working_directory: "~/Projekte/Training2"
  system_prompt_path: "ai/prompts/system.md"

tts:
  provider: openai
  model: tts-1
  voice: onyx
  speed: 1.0

audio:
  sample_rate: 16000
  channels: 1
  chunk_size: 1280
  silence_threshold_sec: 1.5
  max_recording_sec: 30
  vad_threshold: 0.5
```

Die KI-Persona wird ueber `sprachassistent/ai/prompts/system.md` gesteuert.

### Matrix-Chat-Integration (optional)

Jarvis kann zusaetzlich per Matrix-Chat (z.B. Element-App) angesprochen werden. Dazu muss ein Matrix-Bot-Account erstellt und in `config.yaml` konfiguriert werden.

#### Einrichtung

1. **Matrix-Bot-Account erstellen:**
   - Einen neuen Account auf einem Matrix-Homeserver registrieren (z.B. `matrix.org`)
   - Empfehlung: Eigener Homeserver oder separater Bot-Account

2. **Access-Token beschaffen:**
   - In Element einloggen mit dem Bot-Account
   - Unter Einstellungen → Hilfe & Info → "Access Token" kopieren
   - Oder per API: `curl -XPOST -d '{"type":"m.login.password","user":"@bot:matrix.org","password":"..."}' https://matrix.org/_matrix/client/r0/login`

3. **Raum erstellen:**
   - Einen privaten Raum in Element erstellen
   - Den Bot-Account einladen (oder den Raum mit dem Bot-Account erstellen)
   - Die Raum-ID kopieren (in Element: Raumeinstellungen → Erweitert → "Interne Raum-ID")

4. **Konfiguration in `config.yaml` hinzufuegen:**

```yaml
matrix:
  homeserver: "https://matrix.org"
  user_id: "@jarvis-bot:matrix.org"
  access_token: "syt_..."          # oder via MATRIX_ACCESS_TOKEN Umgebungsvariable
  room_id: "!abc123:matrix.org"
  allowed_users:
    - "@dein-account:matrix.org"   # nur diese User duerfen den Bot ansprechen
  store_path: "~/.config/jarvis/matrix_store"
```

Alternativ kann das Access-Token ueber die Umgebungsvariable `MATRIX_ACCESS_TOKEN` gesetzt werden (empfohlen, damit es nicht in der Config-Datei steht).

5. **Matrix-Abhaengigkeiten installieren:**

```bash
uv sync --extra matrix
```

6. **Starten:**

```bash
# Mit Sprache + Chat
uv run sprachassistent

# Nur Chat (ohne Mikrofon/Lautsprecher)
uv run sprachassistent --chat-only
```

#### Sicherheitshinweise

- Das **Access-Token** ist ein Geheimnis -- nicht ins Repository einchecken (`config.yaml` ist in `.gitignore`)
- Nur explizit in `allowed_users` gelistete Matrix-User-IDs koennen den Bot ansprechen
- Nachrichten von unbekannten Absendern werden still ignoriert
- E2E-Verschluesselung wird unterstuetzt (Schluessel werden unter `store_path` gespeichert)

## Architektur

```
sprachassistent/
├── main.py              # Hauptloop: Wake-Word → Record → STT → AI → TTS + Chat
├── config.py            # YAML-Konfiguration laden
├── config.yaml          # Zentrale Einstellungen
├── exceptions.py        # Exception-Hierarchie (AssistantError)
├── audio/
│   ├── wake_word.py     # OpenWakeWord ONNX-Erkennung
│   ├── recorder.py      # VAD-basierte Sprachaufnahme (Silero)
│   ├── microphone.py    # PyAudio Mikrofon-Eingabe
│   ├── player.py        # WAV- und PCM-Wiedergabe
│   └── sounds/          # Signaltoene (ding, processing, ready)
├── chat/
│   ├── message.py       # ChatMessage Datenklasse
│   └── matrix_client.py # Matrix-Bridge (async nio, Hintergrund-Thread)
├── stt/
│   └── whisper_api.py   # OpenAI Whisper Transkription
├── ai/
│   ├── claude_code.py   # Claude Code Subprocess (--print, --continue)
│   └── prompts/
│       └── system.md    # System-Prompt fuer die KI-Persona
├── tts/
│   └── openai_tts.py    # OpenAI TTS mit PCM-Streaming
└── utils/
    ├── terminal_ui.py   # Rich Live-Display mit Zustandsanzeige
    └── logging.py       # Rich-basiertes Logging
```

### Technologie-Stack

| Komponente | Technologie |
|-----------|-------------|
| Sprache | Python 3.12+ (uv) |
| Wake-Word | OpenWakeWord (ONNX) |
| VAD | Silero-VAD (PyTorch) |
| STT | OpenAI Whisper API |
| KI-Backend | Claude Code Subprocess |
| TTS | OpenAI TTS (PCM-Streaming) |
| Audio I/O | PyAudio |
| Chat (optional) | matrix-nio (E2E) |
| Terminal-UI | Rich |

## Entwicklung

```bash
# Tests ausfuehren
uv run pytest

# Einzelnen Test ausfuehren
uv run pytest tests/test_audio/test_recorder.py
uv run pytest -k test_ask_first_call

# Linting
uv run ruff check .

# Formatierung pruefen / anwenden
uv run ruff format --check .
uv run ruff format .
```

### Testrichtlinien

- Tests befinden sich in `tests/` und spiegeln die Struktur von `sprachassistent/` wider
- Externe APIs und Hardware (PyAudio, OpenAI, Claude Code) werden gemockt
- Jede neue Funktion oder Aenderung erfordert passende Tests

## Anforderungsdokumente

Detaillierte Anforderungen befinden sich im `Requirements/`-Verzeichnis:
- `001-Basisanforderungen.md` -- Grundarchitektur, Komponentenbeschreibungen, Umsetzungsplan
- `002-Durchgehende-Konversation.md` -- Persistente Konversation mit `--continue`
- `015-Matrix-Chat-Integration.md` -- Optionaler Textkanal ueber Matrix-Protokoll

## API-Dokumentation

Referenzdokumentation fuer alle verwendeten Bibliotheken liegt im `ai-docs/`-Verzeichnis.

## Lizenz

Privates Projekt.
