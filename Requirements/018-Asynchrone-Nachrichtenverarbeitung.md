# Asynchrone Nachrichtenverarbeitung mit einheitlicher Queue

## 1. Ziel

Alle Nachrichtenquellen (Spracheingabe, Texteingabe, Matrix-Chat) sollen in eine gemeinsame Queue schreiben. Ein Worker-Thread verarbeitet die Nachrichten der Reihe nach. Der Benutzer kann weitere Eingaben machen, ohne auf den Abschluss der aktuellen Verarbeitung warten zu muessen.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Die Hauptschleife in `main.py` ist **synchron und blockierend**: Waehrend die KI antwortet oder TTS abspielt, werden keine neuen Eingaben angenommen
- Voice-Eingaben blockieren den gesamten Ablauf (Aufnahme → STT → KI → TTS)
- Matrix-Nachrichten werden nur waehrend der Idle-Phase gepollt (Wake-Word-Erkennung)
- `_process_chat_message()` wird synchron im Hauptthread ausgefuehrt
- Texteingabe blockiert ebenfalls bis zur vollstaendigen Verarbeitung
- Es gibt keinen einheitlichen Nachrichtentyp -- Voice liefert `str`, Chat liefert `ChatMessage`
- Ergebnis-Routing ist hart kodiert: Voice → TTS, Chat → Matrix-Queue

---

## 3. Soll-Zustand

### 3.1 Ueberblick

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Mikrofon     │    │  Tastatur     │    │  Matrix-Chat  │
│  (Wake Word)  │    │  (Text)       │    │  (Text/Audio) │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼
  ┌─────────────────────────────────────────────────┐
  │          Gemeinsame Eingangs-Queue               │
  │  AssistantMessage(source, input_type, content)   │
  └──────────────────────┬──────────────────────────┘
                         │
                    Worker-Thread
                         │
               ┌─────────┴─────────┐
               │  Verarbeitung:     │
               │  1. STT (falls Audio)│
               │  2. Filterung       │
               │  3. KI-Anfrage      │
               └─────────┬─────────┘
                         │
              ┌──────────┴──────────┐
              │  Antwort-Routing     │
              │  (basierend auf      │
              │   source)            │
              └──────────┬──────────┘
                    ┌────┴────┐
                    ▼         ▼
              ┌─────────┐ ┌──────────┐
              │  TTS +   │ │  Matrix   │
              │  Speaker │ │  Antwort  │
              └─────────┘ └──────────┘
```

### 3.2 Einheitlicher Nachrichtentyp

Neuer Datentyp `AssistantMessage`:

```python
@dataclass(frozen=True)
class AssistantMessage:
    source: MessageSource         # VOICE, KEYBOARD, MATRIX
    input_type: InputType         # TEXT, AUDIO
    content: str | bytes          # Text oder rohe Audio-Daten
    room_id: str | None = None    # Fuer Matrix-Antwort-Routing
    sender: str | None = None     # Absender (Matrix)
    event_id: str | None = None   # Matrix Event-ID
```

### 3.3 Eingabe-Threads (Produzenten)

Jede Nachrichtenquelle laeuft unabhaengig und schreibt in die gemeinsame Queue:

- **Voice-Listener**: Wake-Word → Aufnahme → `AssistantMessage(VOICE, AUDIO, pcm_bytes)` in Queue
- **Keyboard-Listener**: Tastendruck → Texteingabe → `AssistantMessage(KEYBOARD, TEXT, text)` in Queue
- **Matrix-Bridge**: Bestehender Mechanismus, schreibt statt `ChatMessage` nun `AssistantMessage` in die gemeinsame Queue

### 3.4 Worker-Thread (Konsument)

Ein einzelner Worker-Thread verarbeitet die Queue sequentiell:

1. Nachricht aus Queue nehmen (blockierend)
2. Falls `AUDIO`: STT-Transkription durchfuehren
3. Transkript-Filterung (Req 017)
4. Leertext-Pruefung
5. Kommando-Pruefung (Cancel, Reset, Restart)
6. KI-Anfrage
7. Antwort an die richtige Ausgabe routen (basierend auf `source`)

### 3.5 Antwort-Routing

Jede Antwort wird **immer** im Terminal angezeigt (Konsolenausgabe). Zusaetzlich erfolgt eine quellspezifische Ausgabe:

| Source | Konsolenausgabe | Zusaetzliche Ausgabe |
|--------|-----------------|----------------------|
| `VOICE` | Ja | TTS-Sprachausgabe + Ready-Sound |
| `KEYBOARD` | Ja | Keine (nur Terminal) |
| `MATRIX` | Ja | Text-Antwort in den Matrix-Raum |

### 3.6 Warteschlangen-Verhalten

- Neue Nachrichten warten in der Queue, bis die aktuelle Verarbeitung abgeschlossen ist
- Keine Unterbrechung der laufenden KI-Verarbeitung durch neue Nachrichten
- Kein Queue-Limit (unbegrenzte Warteschlange)

### 3.7 Matrix: Nur neue Nachrichten

- Beim Start des Assistenten sollen nur **neue** Nachrichten verarbeitet werden
- Historische Nachrichten, die vor dem Start eingegangen sind, werden ignoriert
- Der Zeitstempel des Startzeitpunkts dient als Grenze: Nur Events mit Server-Timestamp nach dem Start werden verarbeitet

### 3.8 Nebenlaeufikgeit

- Waehrend der Worker eine Nachricht verarbeitet, koennen neue Eingaben in die Queue geschrieben werden
- Der Hauptthread bleibt frei fuer Wake-Word-Erkennung und Tastatur-Polling
- Matrix-Nachrichten werden sofort empfangen (bestehender Async-Thread)
- Die Queue fungiert als Puffer: Mehrere Nachrichten koennen anstehen

---

## 4. Akzeptanzkriterien

### Einheitliche Queue

- [x] Neuer Datentyp `AssistantMessage` mit Feldern: `source`, `input_type`, `content`, `room_id`, `sender`, `event_id`
- [x] Enum `MessageSource` mit Werten `VOICE`, `KEYBOARD`, `MATRIX`
- [x] Enum `InputType` mit Werten `TEXT`, `AUDIO`
- [x] Gemeinsame `queue.Queue` fuer alle Eingabequellen

### Produzenten

- [x] Voice-Pfad schreibt `AssistantMessage(VOICE, AUDIO, pcm_bytes)` in die Queue
- [x] Tastatur-Pfad schreibt `AssistantMessage(KEYBOARD, TEXT, text)` in die Queue
- [x] Matrix-Bridge schreibt `AssistantMessage(MATRIX, TEXT|AUDIO, content)` in die Queue
- [x] Alle Produzenten arbeiten unabhaengig voneinander

### Worker

- [x] Einzelner Worker-Thread verarbeitet Nachrichten sequentiell aus der Queue
- [x] Audio-Nachrichten werden transkribiert (STT)
- [x] Transkript-Filterung wird angewendet (Req 017)
- [x] Kommandos (Cancel, Reset, Restart) werden erkannt und ausgefuehrt
- [x] KI-Anfrage wird gestellt
- [x] Antwort wird basierend auf `source` geroutet

### Antwort-Routing

- [x] Alle Antworten werden im Terminal angezeigt (Konsolenausgabe)
- [x] Voice-Antworten werden zusaetzlich per TTS gesprochen + Ready-Sound
- [x] Keyboard-Antworten nur im Terminal (keine zusaetzliche Ausgabe)
- [x] Matrix-Antworten werden zusaetzlich in den richtigen Raum gesendet

### Matrix: Nur neue Nachrichten

- [x] Beim Start werden nur Nachrichten verarbeitet, die nach dem Startzeitpunkt eingehen
- [x] Historische Nachrichten (vor dem Start) werden ignoriert
- [x] Server-Timestamp des Events wird mit dem Startzeitpunkt verglichen

### Nebenlaeufikgeit

- [x] Neue Eingaben koennen waehrend laufender Verarbeitung gemacht werden
- [x] Wake-Word-Erkennung laeuft unterbrechungsfrei
- [x] Matrix-Nachrichten werden sofort empfangen und eingereiht
- [ ] UI zeigt an, wie viele Nachrichten in der Queue warten (optional)

### Tests

- [x] Unit-Tests fuer `AssistantMessage` und Enums
- [x] Unit-Tests fuer Worker-Thread (Verarbeitung, Routing)
- [x] Unit-Tests fuer Queue-Integration der Produzenten
- [x] Integrations-Test: Voice → Queue → Worker → TTS
- [x] Integrations-Test: Matrix → Queue → Worker → Matrix-Antwort
- [x] Bestehende Tests laufen unveraendert durch

---

## 5. Konfiguration

Keine neuen Konfigurationsfelder erforderlich. Die bestehende Konfiguration wird weiterverwendet.

---

## 6. Neue/Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/chat/message.py` | `AssistantMessage`, `MessageSource`, `InputType` hinzufuegen |
| `sprachassistent/main.py` | Hauptschleife umbauen: Produzenten + Worker-Thread statt synchroner Ablauf |
| `sprachassistent/chat/matrix_client.py` | Statt eigener `incoming_queue` in die gemeinsame Queue schreiben |
| `tests/test_chat/test_message.py` | Tests fuer neue Datentypen |
| `tests/test_main.py` | Tests fuer Worker-Thread und Queue-Integration |
| `tests/test_chat/test_matrix_client.py` | Anpassung an neue Queue-Struktur, Tests fuer Startzeitpunkt-Filter |

---

## 7. Abhaengigkeiten

### Zu anderen Anforderungen

- Abhaengig von: `015-Matrix-Chat-Integration.md` (Matrix-Bridge-Architektur)
- Abhaengig von: `016-Matrix-Audio-Transkription.md` (Audio-Input-Typ)
- Abhaengig von: `017-Transkript-Filterung.md` (Filterung im Worker)

### Externe Abhaengigkeiten

Keine neuen.

---

## 8. Entschiedene Fragen

- [x] **KI-Abbruch:** Neue Nachrichten warten in der Queue. Keine Unterbrechung der laufenden Verarbeitung.
- [x] **TTS-Unterbrechung:** Nicht implementieren. Solide Basisfunktionalitaet hat Vorrang vor Komplexitaet.
- [x] **Queue-Limit:** Kein Limit. Die Queue ist unbegrenzt.
- [x] **Ausgabe-Routing:** Jede Antwort wird immer im Terminal angezeigt. Zusaetzlich: Voice → TTS, Matrix → Chat-Antwort, Keyboard → nur Terminal.
- [x] **Historische Matrix-Nachrichten:** Nur neue Nachrichten nach dem Startzeitpunkt verarbeiten. Keine historischen Nachrichten beim Start.

---

## 9. Status

- [x] Umgesetzt
