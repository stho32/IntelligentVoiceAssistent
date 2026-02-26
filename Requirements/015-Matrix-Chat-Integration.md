# Matrix-Chat-Integration -- Zusaetzlicher Eingabekanal

## 1. Ziel

Der Sprachassistent soll neben der Spracheingabe auch Textnachrichten ueber das Matrix-Protokoll empfangen und beantworten koennen. Dadurch laesst sich Jarvis von einem Smartphone (z.B. via Element-App auf Android) per Chat ansprechen -- auch aus dem lokalen Netz heraus, ohne Ports nach aussen zu oeffnen. Die Matrix-Integration ist **optional**: Wenn keine Matrix-Konfiguration vorhanden ist, laeuft der Assistent wie bisher nur mit Spracheingabe.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Der Assistent empfaengt Eingaben ausschliesslich per **Sprache** (Wake-Word → Aufnahme → STT)
- Der Hauptloop in `main.py` pollt in 80ms-Zyklen auf Audio-Chunks und prueft das Wake-Word
- Antworten werden ausschliesslich per **TTS** gesprochen
- Es gibt keine Moeglichkeit, den Assistenten per Text zu erreichen
- Auf Rechnern ohne Audio-Hardware (kein Mikrofon/Lautsprecher) ist der Assistent nicht nutzbar

---

## 3. Soll-Zustand

### 3.1 Ueberblick

Ein Matrix-Client laeuft in einem **Hintergrund-Thread** und verbindet sich ausgehend (HTTPS) zu einem Matrix-Homeserver (z.B. `matrix.org`). Eingehende Nachrichten werden ueber eine thread-sichere `queue.Queue` an den Hauptloop weitergegeben. Der Hauptloop prueft die Queue nach jedem Wake-Word-Check und verarbeitet Chat-Nachrichten ueber dasselbe AI-Backend.

```
Smartphone (Element App)
        | HTTPS (ausgehend vom Handy)
        v
Matrix Homeserver (z.B. matrix.org, oeffentlich)
        ^ HTTPS (ausgehend vom Rechner, kein offener Port)
        |
Lokaler Bot (Python, hinter NAT/Firewall)
```

### 3.2 Integration in den Hauptloop

Der bestehende Wake-Word-Loop wird erweitert:

```python
while True:
    audio_chunk = mic.read_chunk()              # ~80ms, blockierend

    if wake_word.process(audio_chunk):
        # ... bestehender Sprach-Pipeline-Ablauf ...

    # Nicht-blockierender Check auf Chat-Nachrichten
    try:
        chat_msg = matrix_queue.get_nowait()
    except queue.Empty:
        continue

    # Chat-Nachricht verarbeiten
    response = ai_backend.ask(chat_msg.text)
    matrix_client.send_response(response)
```

Da der Loop sequentiell ist, gibt es kein Concurrency-Problem mit dem AI-Backend. Wenn eine Sprachanfrage laeuft, warten Matrix-Nachrichten in der Queue.

### 3.3 Matrix-Client-Thread

- Nutzt `matrix-nio[e2e]` (async Python-Library mit E2E-Unterstuetzung) in einem eigenen Thread mit eigenem `asyncio`-Event-Loop
- Verbindet sich per **Long-Polling/Sync** zum Homeserver (nur ausgehende HTTPS-Verbindungen)
- Reagiert nur auf Nachrichten von **erlaubten Absendern** (Whitelist, siehe 3.4) im **konfigurierten Raum** (eine einzelne `room_id`)
- Tritt dem konfigurierten Raum beim Start automatisch bei (falls noch nicht Mitglied)
- Verarbeitet beim Start **ungelesene Nachrichten** (Backlog), die waehrend der Offline-Zeit eingingen
- Legt eingehende Nachrichten als Objekte in eine `queue.Queue`
- Sendet Antworten zurueck in den Matrix-Raum
- Unterstuetzt **E2E-Verschluesselung** (Pflicht, siehe 3.5)

### 3.4 Absender-Whitelist

Der Bot reagiert ausschliesslich auf Nachrichten von explizit erlaubten Matrix-Benutzern. Nachrichten von anderen Absendern werden ignoriert (kein Fehler, kein Log-Spam -- nur Debug-Level).

Die Identifikation erfolgt ueber die **Matrix User ID** (`@benutzername:homeserver.org`). Diese ist an die Authentifizierung des Homeservers gebunden und kann nicht von anderen Nutzern gefaelscht werden (im Gegensatz zu Display-Namen).

```yaml
matrix:
  allowed_users:
    - "@mein-account:matrix.org"
```

Verhalten:
- Nachricht von erlaubtem Absender → normal verarbeiten
- Nachricht von unbekanntem Absender → ignorieren (Debug-Log)
- Nachricht vom Bot selbst → immer ignorieren (keine Endlosschleife)
- Leere `allowed_users`-Liste → Bot reagiert auf niemanden (Sicherheitsdefault)

### 3.5 Ende-zu-Ende-Verschluesselung (E2E)

E2E-Verschluesselung ist **Pflicht**. Der Bot muss verschluesselte Nachrichten empfangen und senden koennen.

- Verwendung von `matrix-nio[e2e]` (bringt `python-olm` bzw. `vodozemac` mit)
- Lokale Speicherung der Verschluesselungs-Keys in einer Datei (z.B. `~/.config/jarvis/matrix_store/`)
- Beim ersten Start: Device-Verifikation durchfuehren (Trust-on-first-use oder manuell in Element)
- Der Key-Store-Pfad ist konfigurierbar

### 3.6 Antwortformat pro Kanal

Der System-Prompt ist fuer Sprachausgabe optimiert (kurz, kein Markdown). Fuer Chat-Antworten soll Markdown erlaubt sein. Loesung: Die Nachrichtenquelle wird dem AI-Backend mitgeteilt:

- **Spracheingabe:** `ai_backend.ask(text)` -- wie bisher, Antwort fuer TTS optimiert
- **Chat-Eingabe:** `ai_backend.ask(f"[Chat-Nachricht, Markdown-Antwort erlaubt]: {text}")` -- AI darf laengere, formatierte Antworten geben

### 3.7 Betrieb ohne Audio-Hardware

Wenn keine Audio-Konfiguration vorhanden ist oder die Audio-Initialisierung fehlschlaegt:

- Audio-Komponenten (Wake-Word, Recorder, STT, TTS, Mikrofon, Player) werden uebersprungen
- Der Loop wechselt in einen reinen **Matrix-Polling-Modus** (blockierendes `queue.get()` statt Audio-Polling)
- Alle anderen Komponenten (AI-Backend, Config, Logging) funktionieren wie gewohnt

### 3.8 Kommandos ueber Chat

Die bestehenden Kommandos (Reset, Abbruch) sollen auch per Chat funktionieren:

- Reset-Keywords (z.B. "reset", "neue konversation") → `ai_backend.reset_session()`
- Abbruch waehrend laufender AI-Verarbeitung → `ai_backend.cancel()`

Restart-Kommandos werden im Chat ignoriert (kein Sinn, den lokalen Prozess vom Handy aus neu zu starten).

---

## 4. Akzeptanzkriterien

### Matrix-Client

- [ ] Ein Matrix-Client verbindet sich zu einem konfigurierten Homeserver
- [ ] Der Bot tritt dem konfigurierten Raum (`room_id`) beim Start automatisch bei
- [ ] Eingehende Nachrichten werden empfangen und entschluesselt (E2E)
- [ ] Beim Start werden ungelesene Nachrichten (Backlog) verarbeitet
- [ ] Antworten werden verschluesselt als Text in den Matrix-Raum gesendet
- [ ] Nur Nachrichten von erlaubten Absendern (`allowed_users`) werden verarbeitet
- [ ] Nachrichten in anderen Raeumen werden ignoriert
- [ ] Nachrichten von unbekannten Absendern werden still ignoriert (Debug-Log)
- [ ] Nachrichten vom Bot selbst werden ignoriert (keine Endlosschleife)
- [ ] Nur ausgehende HTTPS-Verbindungen, kein offener Port noetig
- [ ] Der Client laeuft in einem Hintergrund-Thread und blockiert den Hauptloop nicht
- [ ] E2E-Verschluesselungs-Keys werden lokal gespeichert (konfigurierbarer Pfad)

### Integration in den Hauptloop

- [ ] Chat-Nachrichten werden im Idle-Zustand (Wake-Word-Loop) verarbeitet
- [ ] Spracheingabe und Chat-Eingabe teilen dasselbe AI-Backend (gleicher Konversationskontext)
- [ ] Chat-Nachrichten warten in der Queue, wenn eine Sprachanfrage laeuft
- [ ] Antworten auf Chat-Nachrichten werden per Text gesendet (kein TTS)

### Optionalitaet

- [ ] Ohne `matrix`-Sektion in der Config startet der Assistent wie bisher (nur Sprache)
- [ ] Ohne Audio-Hardware (kein Mikrofon) laeuft der Assistent im reinen Chat-Modus
- [ ] Keine Aenderung am bestehenden Verhalten, wenn Matrix nicht konfiguriert ist

### Kommandos

- [ ] Reset-Keywords funktionieren auch ueber Chat
- [ ] Abbruch einer laufenden AI-Anfrage ist ueber Chat moeglich
- [ ] Restart-Keywords werden im Chat ignoriert

### Tests

- [ ] Unit-Tests fuer den Matrix-Client (gemockter Homeserver)
- [ ] Unit-Tests fuer die Queue-Integration im Hauptloop
- [ ] Bestehende Tests laufen weiterhin unveraendert durch
- [ ] Integrationstests fuer den kombinierten Voice+Chat-Betrieb (gemockt)

---

## 5. Konfiguration

### Neue Sektion in `config.yaml` (optional)

```yaml
# Optional -- wenn nicht vorhanden, kein Matrix-Chat
matrix:
  homeserver: "https://matrix.org"
  user_id: "@jarvis-bot:matrix.org"
  access_token: "syt_..."
  room_id: "!abc123:matrix.org"
  allowed_users:
    - "@mein-account:matrix.org"
  store_path: "~/.config/jarvis/matrix_store"
```

| Feld | Beschreibung |
|------|-------------|
| `homeserver` | URL des Matrix-Homeservers |
| `user_id` | Matrix-User-ID des Bot-Accounts |
| `access_token` | Access-Token fuer die Authentifizierung (statt Passwort, sicherer) |
| `room_id` | Der eine Raum, in dem der Bot aktiv ist (tritt beim Start automatisch bei) |
| `allowed_users` | Whitelist: Nur diese Matrix User IDs duerfen den Bot ansprechen |
| `store_path` | Pfad fuer E2E-Verschluesselungs-Keys und Session-Daten |

### Sicherheit

- Das `access_token` ist ein Geheimnis und darf **nicht** ins Repository eingecheckt werden
- `config.yaml` ist bereits in `.gitignore` enthalten
- Alternative: Token ueber Umgebungsvariable (`MATRIX_ACCESS_TOKEN`) laden
- **Absender-Whitelist:** Nur explizit konfigurierte Matrix User IDs werden akzeptiert
- **E2E-Verschluesselung:** Pflicht -- alle Nachrichten sind Ende-zu-Ende verschluesselt
- **Key-Store:** Verschluesselungs-Keys liegen lokal unter `store_path`

---

## 6. Neue Dateien

| Datei | Inhalt |
|-------|--------|
| `sprachassistent/chat/__init__.py` | Package fuer Chat-Integration |
| `sprachassistent/chat/matrix_client.py` | Matrix-Client (async, `matrix-nio`), Verbindung und Nachrichten-Handling |
| `sprachassistent/chat/message.py` | Datenklasse fuer Chat-Nachrichten (room_id, sender, text, timestamp) |
| `tests/test_chat/test_matrix_client.py` | Tests fuer den Matrix-Client |
| `tests/test_chat/test_integration.py` | Tests fuer die Loop-Integration |

---

## 7. Betroffene bestehende Dateien

| Datei | Aenderung |
|-------|-----------|
| `main.py` | Queue-Check im Hauptloop; Matrix-Thread starten; Chat-only-Modus |
| `config.py` | Optionale `matrix`-Sektion laden und validieren |
| `config.yaml` | Neue `matrix`-Sektion (auskommentiert als Vorlage) |
| `pyproject.toml` | `matrix-nio` als optionale Abhaengigkeit |
| `ai/prompts/system.md` | Hinweis auf Chat-Kanal ergaenzen (Markdown erlaubt bei Chat) |

---

## 8. Abhaengigkeiten

### Zu anderen Anforderungen

- Abhaengig von: `001-Basisanforderungen.md` (AI-Backend, Hauptloop)
- Abhaengig von: `002-Durchgehende-Konversation.md` (geteilter Konversationskontext)
- Abhaengig von: `008-Konversations-Reset.md` (Reset auch per Chat)
- Abhaengig von: `013-Cross-Platform-Abstraktion.md` (Plattform-Factory fuer optionale Audio-Komponenten)

### Externe Abhaengigkeiten

| Abhaengigkeit | Version | Zweck |
|---------------|---------|-------|
| `matrix-nio[e2e]` | >=0.24 | Async Matrix-Client mit E2E-Verschluesselung |

---

## 9. Entschiedene Fragen

- [x] **Raum-Typ:** Ein einzelner konfigurierter Raum (`room_id`). Bot tritt beim Start automatisch bei.
- [x] **Absender-Kontrolle:** Nur explizit konfigurierte Matrix User IDs (`allowed_users`) duerfen den Bot ansprechen. Identifikation ueber die Matrix User ID (`@user:homeserver`), die an die Homeserver-Authentifizierung gebunden und faelschungssicher ist.
- [x] **E2E-Verschluesselung:** Pflicht. Verwendung von `matrix-nio[e2e]` mit lokaler Key-Speicherung.
- [x] **Auto-Join:** Bot tritt dem konfigurierten Raum beim Start bei, falls noch nicht Mitglied. Keine Einladungs-Logik.
- [x] **Backlog:** Ungelesene Nachrichten, die waehrend der Offline-Zeit eingingen, werden beim Start verarbeitet.

---

## 10. Status

- [ ] Offen
