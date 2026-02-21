# Kommando-Abbruch per Sprachwort

## 1. Ziel

Der Nutzer soll einen laufenden Vorgang (Aufnahme oder KI-Verarbeitung) per Sprachwort abbrechen koennen, ohne den Assistenten neu starten zu muessen. Nuetzlich bei versehentlicher Aktivierung oder wenn man sich verspricht.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Nach Wake-Word-Erkennung laeuft die Aufnahme zwingend bis zur Stille-Erkennung oder zum Max-Timeout
- Waehrend der KI-Verarbeitung gibt es keine Abbruchmoeglichkeit
- Einzige Option: Warten oder `Ctrl+C` (beendet den gesamten Assistenten)

---

## 3. Soll-Zustand

### 3.1 Abbruch waehrend Aufnahme

| Aspekt | Entscheidung |
|--------|-------------|
| **Abbruch-Erkennung** | Nach Ende der Aufnahme: Transkription pruefen, ob sie ein Abbruch-Schluesselwort enthaelt |
| **Schluesselwoerter** | "Abbrechen", "Stopp", "Vergiss es", "Jarvis stopp" (konfigurierbar) |
| **Verhalten** | Aufnahme wird verworfen, kein STT/KI-Aufruf, direkt zurueck zu LISTENING |
| **Rueckmeldung** | Kurzer Bestaetigungston oder kurzes "Alles klar" per TTS |

### 3.2 Abbruch waehrend KI-Verarbeitung

| Aspekt | Entscheidung |
|--------|-------------|
| **Erkennung** | Parallel zur KI-Verarbeitung: Wake-Word + Aufnahme + Abbruch-Check |
| **Mechanismus** | Claude-Code-Subprocess per `process.terminate()` / `process.kill()` abbrechen |
| **Verhalten** | KI-Antwort wird verworfen, zurueck zu LISTENING |
| **Rueckmeldung** | "Abgebrochen." per TTS |

### 3.3 Phasen-Uebersicht

```
Phase RECORDING:
  Aufnahme -> Transkription -> Ist es ein Abbruch-Befehl?
    JA  -> "Alles klar." -> LISTENING
    NEIN -> weiter mit KI-Verarbeitung

Phase PROCESSING:
  KI arbeitet... Nutzer sagt "Hey Jarvis" -> Aufnahme -> "Stopp"?
    JA  -> Subprocess abbrechen -> "Abgebrochen." -> LISTENING
    NEIN -> (zweiten Befehl nach KI-Antwort verarbeiten -- oder verwerfen)
```

---

## 4. Akzeptanzkriterien

### Abbruch waehrend Aufnahme
- [ ] Abbruch-Schluesselwoerter sind konfigurierbar in `config.yaml`
- [ ] Nach Transkription wird geprueft, ob der Text ein Abbruch-Befehl ist
- [ ] Bei Abbruch wird kein KI-Aufruf gestartet
- [ ] Nutzer erhaelt akustische Bestaetigung ("Alles klar" oder Bestaetigungston)
- [ ] Assistent kehrt sofort zu LISTENING zurueck

### Abbruch waehrend KI-Verarbeitung
- [ ] Waehrend die KI arbeitet, hoert der Assistent weiterhin auf das Wake-Word
- [ ] Nach Wake-Word + Abbruch-Schluesselwort wird der Claude-Code-Subprocess beendet
- [ ] Der Thinking-Beep stoppt sofort nach Abbruch
- [ ] Nutzer erhaelt akustische Bestaetigung ("Abgebrochen.")
- [ ] Assistent kehrt zu LISTENING zurueck

### Robustheit
- [ ] Subprocess-Abbruch fuehrt nicht zu einem fehlerhaften Session-Zustand
- [ ] `_session_started` wird nach Abbruch korrekt behandelt
- [ ] Abbruch-Erkennung ist case-insensitive

---

## 5. Konfiguration

```yaml
commands:
  cancel_keywords:
    - "abbrechen"
    - "stopp"
    - "vergiss es"
    - "jarvis stopp"
```

---

## 6. Technische Umsetzung

### 6.1 Abbruch-Erkennung

```python
def _is_cancel_command(text: str, cancel_keywords: list[str]) -> bool:
    """Check if transcribed text is a cancel command."""
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in cancel_keywords)
```

### 6.2 Abbruch im Hauptloop (nach Transkription)

```python
text = transcriber.transcribe(recorded_audio)

if _is_cancel_command(text, cancel_keywords):
    ui.log("Command cancelled by user.")
    _speak_short(tts, player, "Alles klar.")
    ui.set_state(AssistantState.LISTENING)
    continue
```

### 6.3 Abbruch waehrend KI-Verarbeitung

Fuer den Abbruch waehrend der KI-Verarbeitung muss die `ask()`-Methode in `ClaudeCodeBackend` so erweitert werden, dass der Subprocess abbrechbar ist:

```python
class ClaudeCodeBackend:
    _current_process: subprocess.Popen | None = None

    def ask(self, user_message: str) -> str:
        # ... start subprocess with Popen statt run ...
        self._current_process = subprocess.Popen(cmd, ...)
        # ... warten auf Ergebnis ...

    def cancel(self) -> None:
        """Cancel the currently running AI request."""
        if self._current_process:
            self._current_process.terminate()
            self._current_process = None
```

Der Hauptloop muss parallel zur KI-Verarbeitung auf Wake-Word + Abbruch hoeren. Dies erfordert Threading oder asyncio fuer die parallele Verarbeitung.

---

## 7. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | `_is_cancel_command()`, Abbruch-Check nach Transkription, paralleles Listening waehrend KI |
| `sprachassistent/ai/claude_code.py` | `Popen` statt `run`, `cancel()` Methode |
| `sprachassistent/config.yaml` | `commands.cancel_keywords` Konfiguration |

### Tests

| Testdatei | Prueft |
|-----------|-------|
| `tests/test_main.py` | Abbruch-Erkennung nach Transkription, kein KI-Aufruf bei Cancel |
| `tests/test_ai/test_claude_code.py` | `cancel()` beendet Subprocess korrekt, Session-State nach Abbruch |

---

## 8. Abhaengigkeiten

- Abhaengig von: `002-Durchgehende-Konversation.md` (Session-Management muss Abbruch verkraften)
- Abhaengig von: `006-Fehler-Sprachrueckmeldung.md` (TTS-Hilfsfunktion fuer kurze Rueckmeldungen)

---

## 9. Komplexitaetshinweis

Der Abbruch waehrend der KI-Verarbeitung (Phase PROCESSING) ist deutlich komplexer als der Abbruch nach der Aufnahme, da paralleles Listening und Subprocess-Management erforderlich sind. Eine stufenweise Umsetzung wird empfohlen:

1. **Stufe 1:** Abbruch nach Transkription (einfach, rein sequentiell)
2. **Stufe 2:** Abbruch waehrend KI-Verarbeitung (erfordert Threading/Popen-Umbau)

---

## 10. Status

- [ ] Offen
