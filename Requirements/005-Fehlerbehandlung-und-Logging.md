# Fehlerbehandlung und Logging

## 1. Ziel

Der Sprachassistent soll robust auf Fehler reagieren, ohne abzustuerzen. Jede Fehlerart wird durch eine spezifische Exception abgebildet. Strukturiertes Logging unterstuetzt Diagnose und Debugging.

---

## 2. Exception-Hierarchie

### 2.1 Klassenbaum

```
AssistantError (Basis)
├── AudioError
│   ├── WakeWordError
│   └── RecordingError
├── TranscriptionError
├── AIBackendError
├── TTSError
└── ConfigError
```

### 2.2 Exception-Beschreibungen

| Exception | Ausgeloest bei | Beispiel |
|-----------|----------------|----------|
| **AssistantError** | Basis fuer alle Fehler | -- |
| **AudioError** | Allgemeine Audio-Probleme | Mikrofon kann nicht geoeffnet werden |
| **WakeWordError** | Wake-Word-Erkennung schlaegt fehl | Modell kann nicht geladen werden |
| **RecordingError** | Aufnahme-Probleme | VAD-Initialisierung fehlgeschlagen |
| **TranscriptionError** | STT-Fehler | Whisper API nicht erreichbar |
| **AIBackendError** | KI-Backend-Fehler | Claude Code Subprocess Timeout, leere Antwort, Exit-Code != 0 |
| **TTSError** | Text-zu-Sprache-Fehler | OpenAI TTS API nicht erreichbar |
| **ConfigError** | Konfigurationsfehler | YAML-Datei nicht lesbar, fehlende Pflichtfelder |

---

## 3. Fehlerbehandlung im Hauptloop

### 3.1 Strategie

Fehler in einzelnen Phasen (STT, KI, TTS) fuehren **nicht** zum Absturz des Assistenten. Stattdessen:

1. Fehler wird geloggt
2. Terminal-UI zeigt ERROR-Zustand
3. Assistent kehrt zum LISTENING-Zustand zurueck
4. Naechster Sprachbefehl wird normal verarbeitet

### 3.2 Fehlerbehandlung pro Phase

| Phase | Fehlertyp | Verhalten |
|-------|-----------|-----------|
| **Wake-Word** | WakeWordError | Log + weiter hoeren |
| **Aufnahme** | RecordingError | Log + zurueck zu LISTENING |
| **STT** | TranscriptionError | Log + zurueck zu LISTENING |
| **KI** | AIBackendError | Log + zurueck zu LISTENING |
| **TTS** | TTSError | Log + zurueck zu LISTENING (Antwort geht verloren) |

### 3.3 Beispiel

```python
try:
    response = ai_backend.ask(text)
except Exception as e:
    logger.error("AI backend failed: %s", e)
    ui.log(f"AI error: {e}")
    ui.set_state(AssistantState.LISTENING)
    continue
```

---

## 4. Logging

### 4.1 Bibliothek

**Rich** (Python) -- farbige Konsolenausgabe mit strukturierter Formatierung.

### 4.2 API

| Funktion | Zweck |
|----------|-------|
| `setup_logging()` | Logging initialisieren (Rich-Console, Format) |
| `get_logger(name)` | Modul-spezifischen Logger erzeugen |

### 4.3 Konventionen

- Jedes Modul nutzt seinen eigenen Logger: `logger = get_logger(__name__)`
- Fehler werden mit `logger.error()` geloggt
- Statusaenderungen mit `logger.info()` oder `logger.debug()`
- Rich-Konsole sorgt fuer farbige, lesbare Ausgabe

---

## 5. Betroffene Dateien

| Datei | Inhalt |
|-------|--------|
| `sprachassistent/exceptions.py` | Exception-Hierarchie (`AssistantError` und Unterklassen) |
| `sprachassistent/utils/logging.py` | `setup_logging()`, `get_logger()` |
| `sprachassistent/main.py` | Try/Except-Bloecke im Hauptloop |
| `tests/test_exceptions.py` | Tests fuer Exception-Hierarchie |
| `tests/test_utils/test_logging.py` | Tests fuer Logging-Setup |
