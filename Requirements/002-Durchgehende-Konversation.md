# Durchgehende Konversation mit Claude Code

## 1. Ziel

Der Sprachassistent soll eine durchgehende Konversation mit Claude Code fuehren koennen. Aufeinanderfolgende Sprachbefehle sollen im selben Kontext verarbeitet werden, sodass Rueckbezuege auf vorherige Aussagen moeglich sind.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Jeder Sprachbefehl startete einen neuen `claude --print` Subprocess
- Kein Konversationsgedaechtnis zwischen Befehlen
- System-Prompt wurde bei jedem Aufruf erneut uebergeben
- Rueckfragen wie "Was habe ich gerade gesagt?" waren nicht moeglich

---

## 3. Soll-Zustand

### 3.1 Konversations-Kontinuitaet

| Aspekt | Verhalten |
|--------|-----------|
| **Erster Aufruf** | `claude --print --dangerously-skip-permissions --system-prompt "..." "<nachricht>"` |
| **Folgeaufrufe** | `claude --print --dangerously-skip-permissions --continue "<nachricht>"` |
| **Kontext** | Claude Code erinnert sich an alle vorherigen Nachrichten der Session |
| **System-Prompt** | Wird nur beim ersten Aufruf uebergeben, bleibt fuer die Session aktiv |

### 3.2 Permissions

| Aspekt | Entscheidung |
|--------|-------------|
| **Flag** | `--dangerously-skip-permissions` |
| **Begruendung** | Sprachassistent laeuft unbeaufsichtigt; Permissions-Dialoge koennen nicht per Sprache bestaetigt werden |
| **Risiko** | Claude Code kann Dateien lesen, schreiben, loeschen und Shell-Befehle ausfuehren ohne Nachfrage |
| **Mitigierung** | Arbeitsverzeichnis ist auf den Notizen-Ordner (`~/Projekte/Training2`) beschraenkt |

### 3.3 Session-Lebenszyklus

- Eine Session lebt solange der Sprachassistent-Prozess laeuft
- Bei Neustart des Assistenten beginnt eine neue Session
- `--continue` setzt automatisch die letzte Claude-Code-Konversation fort
- Bei Fehler im ersten Aufruf wird die Session nicht als gestartet markiert (Retry moeglich)

---

## 4. Beispiel-Interaktion

```
Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Erstelle eine Notiz fuer morgen: Meeting um 10 Uhr mit Team Alpha"
  -> Claude Code erstellt Notiz, antwortet: "Ich habe die Notiz fuer morgen erstellt."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Aendere die Uhrzeit auf 11 Uhr"
  -> Claude Code weiss durch --continue, welche Notiz gemeint ist
  -> Antwort: "Ich habe die Uhrzeit auf 11 Uhr geaendert."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Lies mir die Notiz nochmal vor"
  -> Claude Code liest die Notiz aus dem Dateisystem
  -> Antwort: "Die Notiz fuer morgen lautet: Meeting um 11 Uhr mit Team Alpha."
```

---

## 5. Technische Umsetzung

### 5.1 ClaudeCodeBackend

```python
class ClaudeCodeBackend:
    _session_started: bool = False

    def ask(self, user_message: str) -> str:
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]

        if self._session_started:
            cmd.append("--continue")
        elif self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])

        cmd.append(user_message)
        # ... subprocess.run ...
        self._session_started = True
        return response
```

### 5.2 Umgebungsvariable

Die Umgebungsvariable `CLAUDECODE` wird aus dem Subprocess entfernt, damit der Assistent auch innerhalb einer laufenden Claude-Code-Session gestartet werden kann (Nesting-Schutz umgehen).

---

## 6. Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/ai/claude_code.py` | `--continue` fuer Folgeaufrufe, `--dangerously-skip-permissions`, Session-Tracking |
| `tests/test_ai/test_claude_code.py` | Tests fuer Erst-/Folgeaufruf, Session-Verhalten bei Fehler |
