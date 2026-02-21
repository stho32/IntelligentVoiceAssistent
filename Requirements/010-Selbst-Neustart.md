# Selbst-Neustart per Sprachbefehl

## 1. Ziel

Der Nutzer soll den Sprachassistenten per Sprachbefehl komplett neu starten koennen -- der laufende Prozess wird beendet und automatisch wieder gestartet. Das ist hilfreich bei technischen Problemen, nach Updates oder wenn der Assistent sich in einem unerwuenschten Zustand befindet.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Ein Neustart ist nur manuell moeglich: `Ctrl+C` im Terminal und erneuter Start
- Der Nutzer muss physisch am Rechner sein, um den Assistenten neu zu starten
- Bei technischen Problemen (z.B. Mikrofon-Haenger, Speicherlecks) gibt es keine Selbstheilung
- Ein Konversations-Reset (`008`) setzt nur den KI-Kontext zurueck, nicht den gesamten Prozess

---

## 3. Soll-Zustand

### 3.1 Neustart-Befehl

| Aspekt | Entscheidung |
|--------|-------------|
| **Schluesselwoerter** | "Neustart", "Starte neu", "Jarvis Neustart" (konfigurierbar) |
| **Erkennung** | Nach Transkription: Pruefen ob der Text ein Neustart-Befehl ist |
| **Wirkung** | Gesprochene Bestaetigung, dann Prozess-Neustart ueber `os.execv` |
| **Rueckmeldung** | "Alles klar, ich starte jetzt neu." per TTS vor dem Neustart |

### 3.2 Ablauf

```
Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Starte neu"
  -> Transkription: "Starte neu"
  -> Neustart-Befehl erkannt
  -> TTS: "Alles klar, ich starte jetzt neu."
  -> Ressourcen aufraeumen (Mikrofon, Player, UI)
  -> Prozess ersetzt sich selbst via os.execv
  -> Assistent startet frisch
  -> "Assistant ready. Say 'Hey Jarvis' to activate."
```

---

## 4. Akzeptanzkriterien

### Erkennung
- [ ] Neustart-Schluesselwoerter sind konfigurierbar in `config.yaml`
- [ ] Erkennung ist case-insensitive
- [ ] Neustart-Check wird nach Abbruch- und Reset-Check geprueft (niedrigste Prioritaet)

### Neustart-Verhalten
- [ ] Assistent spricht Bestaetigung vor dem Neustart
- [ ] Mikrofon-Stream wird sauber geschlossen
- [ ] Audio-Player wird sauber geschlossen
- [ ] Terminal-UI wird sauber geschlossen
- [ ] Prozess startet mit identischen Argumenten neu
- [ ] Nach Neustart ist der Assistent wieder voll funktionsfaehig

### Robustheit
- [ ] Fehlgeschlagener TTS vor Neustart verhindert den Neustart nicht
- [ ] `os.execv`-Fehler wird geloggt und fuehrt zu sauberem Shutdown statt Absturz

---

## 5. Konfiguration

```yaml
commands:
  cancel_keywords:
    - "abbrechen"
    - "stopp"
    - "vergiss es"
    - "jarvis stopp"
  reset_keywords:
    - "neue konversation"
    - "reset"
    - "vergiss alles"
    - "von vorne"
  restart_keywords:
    - "neustart"
    - "starte neu"
    - "jarvis neustart"
```

---

## 6. Technische Umsetzung

### 6.1 Neustart-Mechanismus

```python
import os
import sys

def _restart_assistant() -> None:
    """Restart the assistant process by replacing it with a fresh instance."""
    log.info("Restarting assistant process...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
```

`os.execv` ersetzt den laufenden Prozess durch eine neue Instanz mit denselben Argumenten. Kein neuer Prozess wird erzeugt -- der bestehende wird direkt ersetzt. Context-Manager (`with`-Bloecke) werden dabei nicht ausgefuehrt, daher muessen Ressourcen vorher explizit freigegeben werden.

### 6.2 Integration im Hauptloop

```python
# Reihenfolge der Befehlserkennung nach Transkription:
# 1. Abbruch? -> verwerfen
# 2. Reset? -> Session zuruecksetzen
# 3. Neustart? -> Prozess neu starten
# 4. Normaler Befehl -> an KI weiterleiten

if restart_keywords and _is_cancel_command(text, restart_keywords):
    ui.log("Restart requested by user.")
    try:
        tts.speak("Alles klar, ich starte jetzt neu.", pa=player._pa)
    except Exception:
        pass
    raise SystemExit(42)  # Special exit code for restart
```

### 6.3 Neustart im Hauptprogramm

```python
def main() -> None:
    # ... bestehender Code ...
    try:
        run_loop(...)
    except KeyboardInterrupt:
        ui.log("Shutting down...")
    except SystemExit as e:
        if e.code == 42:
            ui.log("Restarting...")
            # Ressourcen werden durch with-Block freigegeben
            _restart_assistant()
        raise
```

Alternativ: `run_loop` gibt einen Rueckgabewert zurueck (`"restart"` oder `None`), und `main()` entscheidet basierend darauf.

### 6.4 Reihenfolge der Befehlserkennung

```
Transkription
  -> 1. Abbruch-Befehl? (007) -> verwerfen
  -> 2. Reset-Befehl? (008) -> Session zuruecksetzen
  -> 3. Neustart-Befehl? (010) -> Prozess neu starten
  -> 4. Normaler Befehl -> an KI weiterleiten
```

---

## 7. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | Neustart-Check nach Transkription, `_restart_assistant()`, Anpassung `main()` |
| `sprachassistent/config.yaml` | `commands.restart_keywords` Konfiguration |
| `sprachassistent/ai/prompts/system.md` | Neustart-Befehle in Hilfedokumentation |

### Tests

| Testdatei | Prueft |
|-----------|-------|
| `tests/test_main.py` | Neustart-Erkennung, TTS-Bestaetigung, SystemExit(42) wird ausgeloest |

---

## 8. Abhaengigkeiten

- Abhaengig von: `007-Kommando-Abbruch.md` (gleiche Erkennungslogik)
- Abhaengig von: `008-Konversations-Reset.md` (gleiche Erkennungslogik)
- Ergaenzt: `009-Hilfe-und-Befehlsdokumentation.md` (Neustart in Hilfedoku erwaehnt)

---

## 9. Status

- [ ] Offen
