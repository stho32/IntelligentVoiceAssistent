# 014: Verbesserte Terminal-Darstellung

## 1. Ziel

Die Terminal-Ausgabe des Sprachassistenten soll visuell klar und uebersichtlich sein, sodass der Nutzer dem Gespraech leicht folgen kann. Aktuell ist die Darstellung "zersetzt": Status-Panels werden dupliziert, Informationen erscheinen doppelt, und lange KI-Antworten werden als unformatierte Log-Zeilen ausgegeben.

---

## 2. Problembeschreibung

### 2.1 Ist-Zustand

| Problem | Ursache | Auswirkung |
|---------|---------|------------|
| **Panel-Duplizierung** | `transient=False` in Rich Live: jedes `console.log()` "druckt" das aktuelle Panel in den Scroll-Verlauf | Mehrere identische Status-Panels untereinander |
| **Doppelte Informationen** | `ui.log(f"Transcription: {text}")` UND `ui.set_transcription(text)` zeigen denselben Text | Transkription und Antwort erscheinen zweimal |
| **Unformatierte Antworten** | `ui.log(f"Response: {response}")` gibt die gesamte KI-Antwort als einzelne Log-Zeile aus | Lange Markdown-Antworten sind im Log unleserlich |
| **Quellverweise im Log** | `console.log()` fuegt automatisch `terminal_ui.py:89` hinzu | Stoerende technische Details in der Nutzeransicht |
| **Getrennte Konsolen** | Logging nutzt `Console(stderr=True)`, TerminalUI nutzt `Console()` (stdout) | Ausgaben werden nicht koordiniert, Interleaving-Artefakte |

### 2.2 Soll-Zustand

Der Nutzer sieht:
1. **Ein einziges, aktuelles Status-Panel** das sich in-place aktualisiert (kein Duplizieren)
2. **Einen sauberen Gespraechsverlauf** oberhalb des Panels mit klar getrennten Nutzer- und Assistenten-Beitraegen
3. **Keine doppelten Informationen** - jede Information erscheint genau einmal
4. **Keine technischen Artefakte** wie Dateipfade oder Logger-Metadaten

---

## 3. Akzeptanzkriterien

### 3.1 Panel-Darstellung
- [ ] Das Status-Panel erscheint genau einmal am unteren Rand des Terminals
- [ ] Zustandswechsel aktualisieren das Panel in-place (kein neues Panel im Scroll-Verlauf)
- [ ] Das Panel zeigt nur den aktuellen Status mit Farbcodierung (keine Transkription/Antwort im Panel)

### 3.2 Gespraechsverlauf
- [ ] Abgeschlossene Gespraechsrunden werden als formatierter Block oberhalb des Panels angezeigt
- [ ] Jeder Block enthaelt: Nutzer-Aussage und Assistenten-Antwort, visuell getrennt
- [ ] Lange Antworten werden mit Zeilenumbruechen sauber formatiert (kein Abschneiden, aber Markdown-gerecht)
- [ ] Zeitstempel sind dezent und einheitlich
- [ ] Der Verlauf scrollt unbegrenzt (alle Runden bleiben sichtbar)

### 3.3 Keine Duplizierung
- [ ] Transkription erscheint nicht mehr als separate Log-Zeile UND im Panel
- [ ] KI-Antwort erscheint nicht mehr als separate Log-Zeile UND im Panel
- [ ] Systemmeldungen (Wake Word, Fehler, Cancel) erscheinen genau einmal

### 3.4 Logging-Trennung
- [ ] Nutzer-sichtbare Ausgabe und technisches Logging sind sauber getrennt
- [ ] Technische Debug-Logs werden in eine Log-Datei geschrieben (nicht ins Terminal)
- [ ] Die nutzersichtbare Ausgabe enthaelt keine Quellverweise (`terminal_ui.py:89` etc.)
- [ ] Der Log-Dateipfad ist konfigurierbar

### 3.5 Abwaertskompatibilitaet
- [ ] Alle bestehenden UI-Methoden (`set_state`, `set_transcription`, `set_response`, `log`) bleiben funktional
- [ ] Bestehende Tests fuer TerminalUI bestehen weiterhin (ggf. angepasst)

---

## 4. Loesungsansatz

### 4.1 Panel mit `transient=True`

Das Rich Live Display auf `transient=True` umstellen. Damit verschwindet das Panel beim naechsten Update aus dem Scroll-Verlauf und erscheint nur einmal am unteren Rand.

### 4.2 Gespraechsverlauf als formatierte Bloecke

Statt `ui.log(f"Response: {response}")` einen dedizierten Mechanismus einfuehren, der abgeschlossene Gespraechsrunden als formatierte Rich-Panels oder -Texte oberhalb des Status-Panels ausgibt:

```
[13:42:30] Du: Ich denke, ich wuerde es am Kontext erkennen...

[13:43:21] Jarvis: Guter Ansatz! Der Kontext ist genau der richtige Hebel...
```

### 4.3 Doppelte Log-Aufrufe entfernen

In `main.py` die redundanten `ui.log()` Aufrufe fuer Transkription und Antwort entfernen. Diese Informationen werden stattdessen ueber den Gespraechsverlauf (4.2) dargestellt.

### 4.4 Logging in Datei umleiten

Debug-Logs werden in eine Log-Datei geschrieben (z.B. `jarvis.log`). Der `RichHandler` fuer stderr wird durch einen `FileHandler` ersetzt (oder ergaenzt). Das Terminal bleibt frei von technischen Details. Der Log-Dateipfad wird ueber `config.yaml` konfigurierbar.

---

## 5. Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/utils/terminal_ui.py` | Panel-Modus aendern, Gespraechsverlauf-Darstellung einbauen, `log()` ueberarbeiten |
| `sprachassistent/main.py` | Redundante `ui.log()` Aufrufe entfernen/ersetzen, ggf. neue UI-Methoden nutzen |
| `sprachassistent/utils/logging.py` | Konsolen-Koordination mit TerminalUI |
| `tests/test_utils/test_terminal_ui.py` | Tests fuer neue Darstellungslogik, bestehende Tests anpassen |

---

## 6. Abhaengigkeiten

- Baut auf: 004-Terminal-UI, 005-Fehlerbehandlung-und-Logging

## 7. Status

- [x] Umgesetzt

## 8. Entschiedene Fragen

| Frage | Entscheidung | Begruendung |
|-------|-------------|-------------|
| Gespraechsverlauf begrenzen? | **Unbegrenzt scrollen** | Alle Runden bleiben sichtbar, Nutzer kann im Terminal zurueckscrollen |
| Laufende Daten im Panel? | **Nur Status im Panel** | Panel zeigt nur den aktuellen Zustand (Recording, Processing...). Transkription und Antwort erscheinen erst als fertige Bloecke im Verlauf |
| Debug-Ausgabe? | **In Log-Datei schreiben** | Debug-Logs werden in eine Datei geschrieben (z.B. `jarvis.log`), nicht ins Terminal. Das Terminal bleibt frei von technischen Details |
