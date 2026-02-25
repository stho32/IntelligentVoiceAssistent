# 015: Texteingabe-Modus

## 1. Ziel

Der Nutzer soll waehrend der Wartezeit auf ein neues Wake-Word (LISTENING-Phase) alternativ eine Texteingabe starten koennen. So koennen Informationen uebermittelt werden, die per Sprache unpraktisch sind -- z.B. Dateipfade, URLs, Code-Schnipsel oder technische Bezeichnungen.

---

## 2. Ist-Zustand

- Eingabe ausschliesslich per Audio (Wake-Word -> Aufnahme -> STT)
- Kein Mechanismus fuer Tastatureingabe
- Die LISTENING-Phase blockiert in `mic.read_chunk()` und wartet auf Audio-Chunks
- Terminal-UI zeigt nur Status-Panel, keine Eingabeaufforderung

---

## 3. Soll-Zustand

### 3.1 Aktivierung

| Aspekt | Entscheidung |
|--------|-------------|
| **Ausloeser** | Beliebige Taste waehrend LISTENING-Phase |
| **Erkennung** | Hintergrund-Thread ueberwacht stdin auf Tastendruecke |
| **Verhalten** | Erster Tastendruck wird als erstes Zeichen der Eingabe uebernommen |
| **Zustandswechsel** | LISTENING -> TYPING (neuer Zustand) |

### 3.2 Texteingabe

| Aspekt | Entscheidung |
|--------|-------------|
| **Eingabe** | Einzeiliges Textfeld im Terminal (unterhalb des Status-Panels) |
| **Senden** | Enter-Taste sendet die Nachricht |
| **Abbrechen** | Escape-Taste bricht ab und kehrt zu LISTENING zurueck |
| **Anzeige** | Status-Panel wechselt zu "Texteingabe... (Enter = senden, Esc = abbrechen)" |

### 3.3 Verarbeitung

| Aspekt | Entscheidung |
|--------|-------------|
| **Nach Enter** | Text wird direkt als Nutzer-Nachricht an den KI-Backend weitergegeben |
| **Bypass** | Wake-Word-Erkennung, Aufnahme und STT werden uebersprungen |
| **Gespraechsverlauf** | Text erscheint im Verlauf wie eine Spracheingabe (mit "[Tastatur]"-Kennzeichnung) |
| **Antwort** | KI-Antwort wird ganz normal per TTS gesprochen |

### 3.4 Phasen-Uebersicht

```
Phase LISTENING:
  Mikrofon hoert auf Wake-Word...
  Gleichzeitig: Tastendruck erkannt?
    JA  -> TYPING-Modus
      Nutzer tippt... Enter?
        JA  -> Text als Eingabe -> PROCESSING -> SPEAKING -> LISTENING
        NEIN (Esc) -> Zurueck zu LISTENING
    NEIN -> Weiter Wake-Word-Erkennung
```

---

## 4. Akzeptanzkriterien

### 4.1 Aktivierung

- [ ] Waehrend der LISTENING-Phase kann durch einen Tastendruck der Texteingabe-Modus aktiviert werden
- [ ] Der erste Tastendruck wird als erstes Zeichen der Eingabe uebernommen (kein verlorenes Zeichen)
- [ ] Die Wake-Word-Erkennung pausiert waehrend der Texteingabe

### 4.2 Texteingabe

- [ ] Der Nutzer kann eine Textnachricht eintippen
- [ ] Enter sendet die Nachricht
- [ ] Escape bricht die Eingabe ab und kehrt zu LISTENING zurueck
- [ ] Leere Eingabe (nur Enter) wird ignoriert und kehrt zu LISTENING zurueck
- [ ] Das Status-Panel zeigt den TYPING-Zustand an

### 4.3 Verarbeitung

- [ ] Der eingegebene Text wird direkt an das KI-Backend weitergegeben (kein STT)
- [ ] Die KI-Antwort wird per TTS gesprochen (wie bei Spracheingabe)
- [ ] Der Gespraechsverlauf zeigt den Text mit "[Tastatur]"-Kennzeichnung
- [ ] Kommandos (Abbruch, Reset, Neustart) werden auch bei Texteingabe erkannt

### 4.4 Terminal-Kompatibilitaet

- [ ] Rich Live Display und Texteingabe kollidieren nicht
- [ ] Die Eingabezeile ist sichtbar und editierbar (Backspace funktioniert)
- [ ] Nach Ende der Texteingabe kehrt das Status-Panel korrekt zurueck

### 4.5 Abwaertskompatibilitaet

- [ ] Reine Sprachsteuerung funktioniert weiterhin unveraendert
- [ ] Bestehende Tests bestehen weiterhin

---

## 5. Technische Umsetzung

### 5.1 Neuer Zustand in TerminalUI

```python
class AssistantState(Enum):
    # ... bestehende Zustaende ...
    TYPING = "typing"  # Neu
```

Status-Panel-Konfiguration:
```python
AssistantState.TYPING: ("magenta", "Texteingabe... (Enter = senden, Esc = abbrechen)")
```

### 5.2 Neues Modul: Keyboard-Monitor

Ein neues Modul `sprachassistent/input/keyboard.py` implementiert die nicht-blockierende Tastaturerkennung:

```python
class KeyboardMonitor:
    """Monitors stdin for keypresses in a background thread."""

    def start(self) -> None:
        """Start monitoring for keypresses."""

    def stop(self) -> None:
        """Stop monitoring."""

    def check(self) -> str | None:
        """Non-blocking check if a key was pressed.
        Returns the character or None."""
```

Implementierung ueber `select.select()` und `termios` fuer raw-mode stdin auf Linux.

### 5.3 Neues Modul: Texteingabe

Ein neues Modul `sprachassistent/input/text_input.py` verwaltet die Texteingabe-Interaktion:

```python
class TextInput:
    """Handles text input collection in the terminal."""

    def collect(self, initial_char: str, ui: TerminalUI) -> str | None:
        """Collect text from the user.

        Args:
            initial_char: First character already typed.
            ui: Terminal UI for display coordination.

        Returns:
            The entered text, or None if cancelled (Esc).
        """
```

Die Eingabe muss mit Rich Live koordiniert werden -- wahrscheinlich wird Live temporaer pausiert oder die Eingabe direkt in das Panel integriert.

### 5.4 Aenderungen im Hauptloop

In `run_loop()` wird der LISTENING-Loop erweitert:

```python
while True:
    # Check for keyboard input (non-blocking)
    key = keyboard_monitor.check()
    if key is not None:
        ui.set_state(AssistantState.TYPING)
        text = text_input.collect(initial_char=key, ui=ui)
        if text is None or not text.strip():
            ui.set_state(AssistantState.LISTENING)
            continue
        # Skip to command check / AI processing with text
        ...

    # Normal wake word detection
    audio_chunk = mic.read_chunk()
    if not wake_word.process(audio_chunk):
        continue
    # ... Rest wie bisher
```

### 5.5 Gespraechsverlauf-Kennzeichnung

In `TerminalUI.print_conversation_turn()` wird bei Texteingabe ein Hinweis ergaenzt:

```
[14:30:22] Du [Tastatur]: ~/Projekte/Training2/notes/wichtig.md

[14:30:45] Jarvis: Ich habe die Datei gelesen...
```

---

## 6. Betroffene Dateien

### Neue Dateien

| Datei | Beschreibung |
|-------|--------------|
| `sprachassistent/input/__init__.py` | Paket-Init |
| `sprachassistent/input/keyboard.py` | Hintergrund-Thread fuer Tastaturueberwachung |
| `sprachassistent/input/text_input.py` | Texteingabe-Sammlung und Terminal-Koordination |
| `tests/test_input/__init__.py` | Test-Paket-Init |
| `tests/test_input/test_keyboard.py` | Tests fuer KeyboardMonitor |
| `tests/test_input/test_text_input.py` | Tests fuer TextInput |

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | LISTENING-Loop um Tastatur-Check erweitern, Text-Bypass fuer Recording/STT |
| `sprachassistent/utils/terminal_ui.py` | Neuer TYPING-Zustand, Eingabe-Kennzeichnung im Verlauf |
| `tests/test_main.py` | Tests fuer Texteingabe-Pfad im Hauptloop |
| `tests/test_utils/test_terminal_ui.py` | Tests fuer TYPING-Zustand |

---

## 7. Abhaengigkeiten

- Baut auf: 004-Terminal-UI, 007-Kommando-Abbruch, 014-Verbesserte-Terminal-Darstellung
- Nutzt: Threading-Muster aus 007 (paralleles Monitoring im Hauptloop)

---

## 8. Komplexitaetshinweis

Die Hauptkomplexitaet liegt in der Koordination zwischen Rich Live Display und Terminal-Eingabe. Rich Live uebernimmt normalerweise die volle Kontrolle ueber das Terminal. Moegliche Ansaetze:

1. **Live temporaer stoppen**: Vor der Texteingabe `live.stop()`, danach `live.start()` -- einfach, aber kurzes Flackern
2. **Console.input() nutzen**: Rich's eigene `console.input()` Methode ist kompatibel mit Live
3. **Eigene Zeichensammlung**: Ueber `termios` raw-mode einzelne Zeichen lesen und im Panel darstellen -- flexibelster Ansatz, aber aufwaendiger

Empfehlung: Mit Ansatz 1 oder 2 starten und bei Bedarf auf Ansatz 3 wechseln.

---

## 9. Entschiedene Fragen

| Frage | Entscheidung | Begruendung |
|-------|-------------|-------------|
| Mehrzeilige Eingabe? | **Mehrzeilig wenn moeglich** | Nutzer wuenscht mehrzeilige Eingabe fuer komplexere Inhalte |
| Soll die KI-Antwort bei Texteingabe auch gesprochen werden? | **Immer sprechen** | Konsistentes Verhalten unabhaengig vom Eingabemodus |
| Soll ein Hinweis im Status-Panel auf die Tastatur-Option hinweisen? | **Ja** | Status-Panel zeigt: "Listening for 'Hey Jarvis'... (or press any key to type)" |

---

## 10. Status

- [ ] Offen
