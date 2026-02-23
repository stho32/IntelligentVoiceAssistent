# Konversations-Persistenz ueber Neustart

## 1. Ziel

Die Claude-Code-Konversation soll bei einem Start des Sprachassistenten standardmaessig fortgesetzt werden (`--resume`), damit der KI-Kontext nicht verloren geht. Ueber ein Command-Line-Argument (`--new-session`) kann der Nutzer explizit eine frische Konversation erzwingen.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Bei einem Neustart (010) wird `os.execv` aufgerufen -- der Prozess startet komplett neu
- `ClaudeCodeBackend.__init__` setzt `_session_started = False`
- Dadurch wird der naechste Aufruf mit `--system-prompt` statt `--continue` ausgefuehrt
- Die vorherige Claude-Code-Konversation ist verloren, obwohl Claude Code sie lokal gespeichert hat
- Der Reset-Befehl (008) und der Neustart-Befehl (010) fuehren beide zum Kontextverlust
- Es gibt keine Moeglichkeit, nach einem Neustart an die vorherige Konversation anzuknuepfen

---

## 3. Soll-Zustand

### 3.1 Command-Line-Argumente

| Argument | Verhalten |
|----------|-----------|
| `uv run sprachassistent` | **Default:** Konversation fortsetzen (`--resume`) |
| `uv run sprachassistent --new-session` | Frische Konversation starten (`--system-prompt`) |

### 3.2 Konversations-Uebernahme (Default)

| Aspekt | Entscheidung |
|--------|-------------|
| **Default-Verhalten** | Konversation wird fortgesetzt (`--resume`) |
| **Mechanismus** | Claude Code `--resume` Flag knuepft an die letzte Konversation an |
| **Erster Aufruf** | `claude --print --dangerously-skip-permissions --resume "<nachricht>"` |
| **Folgeaufrufe** | Wie bisher: `claude --print --dangerously-skip-permissions --continue "<nachricht>"` |
| **Fallback** | Wenn keine vorherige Session existiert, automatisch `--system-prompt` |

### 3.3 Neue Konversation (--new-session)

| Aspekt | Entscheidung |
|--------|-------------|
| **Ausloeser** | CLI-Argument `--new-session` oder Sprach-Reset-Befehl (008) |
| **Verhalten** | Erster Aufruf mit `--system-prompt`, Folgeaufrufe mit `--continue` |

### 3.4 Neustart-Befehl (010)

| Aspekt | Entscheidung |
|--------|-------------|
| **Verhalten** | `os.execv` startet ohne `--new-session` -> Konversation wird fortgesetzt |
| **Sprach-Reset nach Neustart** | "Neue Konversation" setzt weiterhin auf frischen Kontext |

### 3.5 Ablauf: Normaler Start (Default, mit Resume)

```
$ uv run sprachassistent
  -> "Assistant ready. Say 'Hey Jarvis' to activate."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Was hatten wir gestern besprochen?"
  -> Claude Code wird mit --resume aufgerufen
  -> Claude Code kennt den vorherigen Kontext
  -> Antwort mit Bezug auf die vorherige Konversation
```

### 3.6 Ablauf: Start mit frischer Konversation

```
$ uv run sprachassistent --new-session
  -> "Assistant ready. Say 'Hey Jarvis' to activate."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Erstelle eine neue Notiz..."
  -> Claude Code mit --system-prompt (frischer Kontext)
```

---

## 4. Akzeptanzkriterien

### Command-Line-Interface

- [x] `--new-session` Argument wird ueber `argparse` bereitgestellt
- [x] Ohne `--new-session`: erster KI-Aufruf verwendet `--resume`
- [x] Mit `--new-session`: erster KI-Aufruf verwendet `--system-prompt`

### Konversations-Uebernahme (Default)

- [x] `--resume` wird nur fuer den ersten Aufruf verwendet
- [x] Folgeaufrufe verwenden wie bisher `--continue`
- [x] Wenn `--resume` fehlschlaegt (z.B. keine vorherige Konversation), wird automatisch auf `--system-prompt` zurueckgefallen

### Neue Konversation

- [x] Der Sprach-Reset-Befehl (008) startet weiterhin eine frische Konversation mit `--system-prompt`
- [x] Reset setzt auch den Resume-Zustand zurueck

### Neustart-Befehl (010)

- [x] `os.execv` startet ohne `--new-session` -> Konversation wird fortgesetzt
- [x] `sys.argv` wird unveraendert weitergegeben (kein `--new-session` eingefuegt)

### Robustheit

- [x] Fehlschlag von `--resume` fuehrt nicht zu einem Absturz
- [x] Fehlerfall wird geloggt und Fallback auf `--system-prompt` dokumentiert
- [x] Kein Fehler beim allerersten Start ohne vorherige Konversation

---

## 5. Technische Umsetzung

### 5.1 Argument-Parsing in main.py

```python
import argparse

def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Voice Assistant")
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Start with a fresh conversation instead of resuming the previous one",
    )
    args = parser.parse_args()

    resume_session = not args.new_session
    # ... ClaudeCodeBackend mit resume_session initialisieren ...
```

### 5.2 Zustandsverwaltung in ClaudeCodeBackend

```python
class ClaudeCodeBackend:
    def __init__(self, ..., resume_session: bool = True):
        self._session_started = False
        self._resume_on_next = resume_session

    def ask(self, user_message: str) -> str:
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]

        if self._session_started:
            cmd.append("--continue")
        elif self._resume_on_next:
            cmd.append("--resume")
        elif self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])

        cmd.append(user_message)
        # ... subprocess ...

        self._session_started = True
        self._resume_on_next = False
        return response
```

### 5.3 Fehlerbehandlung bei --resume

```python
    def ask(self, user_message: str) -> str:
        # ... Aufbau wie oben ...
        try:
            response = self._run_subprocess(cmd)
        except AIBackendError:
            if self._resume_on_next:
                # Fallback: frische Session starten
                log.warning("--resume failed, starting fresh session")
                self._resume_on_next = False
                self._session_started = False
                return self.ask(user_message)  # Retry mit --system-prompt
            raise

        self._session_started = True
        self._resume_on_next = False
        return response
```

### 5.4 Reset setzt auch Resume zurueck

```python
    def reset_session(self) -> None:
        self._session_started = False
        self._resume_on_next = False
        log.info("Conversation session reset")
```

### 5.5 Neustart-Befehl (010) gibt sys.argv weiter

`os.execv` verwendet `sys.argv` unveraendert. Da `--new-session` beim normalen Betrieb nicht in `sys.argv` steht, wird nach einem Sprachneustart automatisch resumed:

```python
def _restart_assistant() -> None:
    os.execv(sys.executable, [sys.executable] + sys.argv)
    # sys.argv enthaelt kein --new-session -> Default = resume
```

### 5.6 Reihenfolge der Befehlserkennung (unveraendert)

```
Transkription
  -> 1. Abbruch-Befehl? (007) -> verwerfen
  -> 2. Reset-Befehl? (008) -> Session zuruecksetzen (kein resume)
  -> 3. Neustart-Befehl? (010) -> Prozess neu starten (mit resume)
  -> 4. Normaler Befehl -> an KI weiterleiten
```

---

## 6. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/ai/claude_code.py` | `resume_session` Parameter, `_resume_on_next` Logik, Fallback bei Resume-Fehler |
| `sprachassistent/main.py` | `argparse` fuer `--new-session`, `ClaudeCodeBackend` mit `resume_session` initialisieren |

### Tests

| Testdatei | Prueft |
|-----------|-------|
| `tests/test_ai/test_claude_code.py` | `--resume` beim ersten Aufruf mit `resume_session=True`, `--system-prompt` bei `resume_session=False`, Fallback bei Resume-Fehler, Reset setzt Resume zurueck |
| `tests/test_main.py` | `--new-session` Argument wird korrekt geparst, `ClaudeCodeBackend` erhaelt korrektes Flag |

---

## 7. Abhaengigkeiten

- Abhaengig von: `002-Durchgehende-Konversation.md` (Session-Management, `--continue`)
- Abhaengig von: `008-Konversations-Reset.md` (Reset muss Resume ueberschreiben)
- Abhaengig von: `010-Selbst-Neustart.md` (Neustart-Mechanismus ueber `os.execv`)

---

## 8. Status

- [x] Implementiert
