# Terminal-UI mit Rich

## 1. Ziel

Eine uebersichtliche Terminal-Oberflaeche zeigt den aktuellen Zustand des Assistenten, die letzte Transkription und die KI-Antwort in Echtzeit an. Der Nutzer sieht auf einen Blick, was passiert.

---

## 2. Zustandsmaschine

### 2.1 Zustaende

| Zustand | Anzeige | Farbe | Bedeutung |
|---------|---------|-------|-----------|
| **IDLE** | -- | -- | Initialer Zustand |
| **LISTENING** | "Listening for 'Hey Jarvis'..." | Gruen | Wartet auf Wake-Word |
| **RECORDING** | "Recording speech..." | Hellgruen | Nimmt Sprache auf |
| **PROCESSING** | "Processing..." | Blau | STT und KI-Verarbeitung |
| **SPEAKING** | "Speaking..." | Cyan | TTS gibt Antwort wieder |
| **ERROR** | "Error" | Rot | Fehler aufgetreten |

### 2.2 Zustandsuebergaenge

```
IDLE -> LISTENING -> RECORDING -> PROCESSING -> SPEAKING -> LISTENING
                                      |
                                      v
                                    ERROR -> LISTENING
```

---

## 3. Anzeige-Layout

### 3.1 Dargestellte Informationen

| Bereich | Inhalt |
|---------|--------|
| **Status** | Aktueller Zustand mit farbiger Markierung |
| **Transkription** | Zuletzt erkannter Sprachbefehl |
| **Antwort** | Letzte KI-Antwort |
| **Log** | Systemmeldungen und Ereignisse |

### 3.2 Aktualisierung

- **Rich Live Display** mit automatischer Aktualisierung
- Aenderungen werden sofort dargestellt (kein manuelles Refresh)

---

## 4. Technische Umsetzung

### 4.1 Bibliothek

**Rich** (Python) -- bietet Live-Display, farbige Ausgabe und strukturierte Layouts fuer das Terminal.

### 4.2 API

| Methode | Zweck |
|---------|-------|
| `set_state(state)` | Zustand aendern (LISTENING, RECORDING, etc.) |
| `set_transcription(text)` | Transkription anzeigen |
| `set_response(text)` | KI-Antwort anzeigen |
| `log(message)` | Systemmeldung hinzufuegen |

### 4.3 Context Manager

Die UI wird als Context Manager implementiert (`__enter__`/`__exit__`), um die Rich-Live-Session korrekt zu starten und zu beenden.

---

## 5. Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/utils/terminal_ui.py` | `TerminalUI` Klasse mit `AssistantState` Enum |
| `sprachassistent/main.py` | UI-Aufrufe im Hauptloop |
| `tests/test_utils/test_terminal_ui.py` | Tests fuer Zustandswechsel und Anzeige |
