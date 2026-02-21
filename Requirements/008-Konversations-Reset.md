# Konversations-Reset per Sprachbefehl

## 1. Ziel

Der Nutzer soll per Sprachbefehl die Claude-Code-Konversation zuruecksetzen koennen, um mit einem frischen Kontext zu beginnen -- ohne den Assistenten neu starten zu muessen.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Die Claude-Code-Session laeuft durchgehend ueber `--continue` (siehe `002-Durchgehende-Konversation.md`)
- Ein Reset ist nur durch Neustart des Assistenten moeglich (`Ctrl+C` + erneut starten)
- Bei langen Sessions kann der Kontext verrauscht oder irrelevant werden
- Missverstaendnisse der KI koennen sich durch den persistenten Kontext ueber mehrere Befehle fortsetzen

---

## 3. Soll-Zustand

### 3.1 Reset-Befehl

| Aspekt | Entscheidung |
|--------|-------------|
| **Schluesselwoerter** | "Neue Konversation", "Reset", "Vergiss alles", "Jarvis, von vorne" (konfigurierbar) |
| **Erkennung** | Nach Transkription: Pruefen ob der Text ein Reset-Befehl ist |
| **Wirkung** | `_session_started` wird auf `False` zurueckgesetzt |
| **Naechster Aufruf** | Wird wieder mit `--system-prompt` statt `--continue` ausgefuehrt |
| **Rueckmeldung** | "Alles klar, ich starte eine neue Konversation." per TTS |

### 3.2 Ablauf

```
Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Neue Konversation"
  -> Transkription: "Neue Konversation"
  -> Reset-Befehl erkannt
  -> _session_started = False
  -> TTS: "Alles klar, ich starte eine neue Konversation."
  -> *ready*
  -> LISTENING

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Was steht in meinen Notizen fuer morgen?"
  -> Claude Code wird mit --system-prompt aufgerufen (frischer Kontext)
```

---

## 4. Akzeptanzkriterien

### Erkennung
- [ ] Reset-Schluesselwoerter sind konfigurierbar in `config.yaml`
- [ ] Erkennung ist case-insensitive
- [ ] Erkennung funktioniert auch mit kleinen Variationen (z.B. "neue konversation" vs "Neue Konversation")

### Reset-Verhalten
- [ ] `_session_started` wird auf `False` zurueckgesetzt
- [ ] Der naechste KI-Aufruf verwendet `--system-prompt` statt `--continue`
- [ ] Kein KI-Aufruf wird fuer den Reset-Befehl selbst gestartet

### Rueckmeldung
- [ ] Nutzer erhaelt eine gesprochene Bestaetigung per TTS
- [ ] Ready-Sound wird nach der Bestaetigung abgespielt

### Robustheit
- [ ] Mehrfacher Reset hintereinander fuehrt nicht zu Fehlern
- [ ] Reset funktioniert auch wenn noch keine Session gestartet wurde

---

## 5. Konfiguration

```yaml
commands:
  reset_keywords:
    - "neue konversation"
    - "reset"
    - "vergiss alles"
    - "von vorne"
```

---

## 6. Technische Umsetzung

### 6.1 Reset-Erkennung

```python
def _is_reset_command(text: str, reset_keywords: list[str]) -> bool:
    """Check if transcribed text is a conversation reset command."""
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in reset_keywords)
```

### 6.2 Reset-Methode im Backend

```python
class ClaudeCodeBackend:
    def reset_session(self) -> None:
        """Reset the conversation session.

        The next ask() call will start a fresh session
        with the system prompt instead of using --continue.
        """
        self._session_started = False
```

### 6.3 Integration im Hauptloop

```python
# Nach Transkription, vor KI-Aufruf:
if _is_reset_command(text, reset_keywords):
    ai_backend.reset_session()
    ui.log("Conversation reset by user.")
    _speak_short(tts, player, "Alles klar, ich starte eine neue Konversation.")
    if _READY_PATH.exists():
        player.play_wav(_READY_PATH)
    ui.set_state(AssistantState.LISTENING)
    continue
```

### 6.4 Reihenfolge der Befehlserkennung

Im Hauptloop nach der Transkription werden Sonderbefehle in dieser Reihenfolge geprueft:

```
Transkription
  -> 1. Abbruch-Befehl? (007) -> verwerfen
  -> 2. Reset-Befehl? (008) -> Session zuruecksetzen
  -> 3. Normaler Befehl -> an KI weiterleiten
```

---

## 7. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | `_is_reset_command()`, Reset-Check nach Transkription |
| `sprachassistent/ai/claude_code.py` | `reset_session()` Methode |
| `sprachassistent/config.yaml` | `commands.reset_keywords` Konfiguration |

### Tests

| Testdatei | Prueft |
|-----------|-------|
| `tests/test_main.py` | Reset-Erkennung, kein KI-Aufruf bei Reset, Bestaetigung wird gesprochen |
| `tests/test_ai/test_claude_code.py` | `reset_session()` setzt `_session_started` zurueck, naechster Aufruf nutzt `--system-prompt` |

---

## 8. Abhaengigkeiten

- Abhaengig von: `002-Durchgehende-Konversation.md` (Session-Management)
- Synergie mit: `007-Kommando-Abbruch.md` (gleiche Erkennungslogik fuer Sonderbefehle)

---

## 9. Status

- [ ] Offen
