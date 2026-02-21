# Sprachassistent "Jarvis" -- Basisanforderungen

## 1. Vision

Ein lokaler Sprachassistent, der per Schluesselwort **"Hey Jarvis"** aktiviert wird, natuerliche Sprache versteht und Aufgaben ueber eine KI im Terminal ausfuehrt -- mit direktem Lese-/Schreibzugriff auf den Notizen-Ordner.

---

## 2. Architekturuebersicht

```
+-----------------------------------------------------------+
|                    Hauptprozess (Python)                   |
|                                                           |
|  +-----------+    +-----------+    +-------------------+  |
|  |  Wake-Word |-->|  STT      |-->|  KI-Backend       |  |
|  |  (lokal)   |   |  (Cloud)  |   |  (Claude Code     |  |
|  |  OpenWake  |   |  Whisper  |   |   Subprocess)     |  |
|  |  Word ONNX |   |  API      |   |                   |  |
|  +-----------+    +-----------+    +---------+---------+  |
|       ^                                      |            |
|       | Mikrofon                             v            |
|  +----+------+                      +---------------+     |
|  |  Audio-   |                      |  TTS          |     |
|  |  Stream   |<---------------------+  (Cloud)      |     |
|  |  (PyAudio)|     Lautsprecher     |  OpenAI TTS   |     |
|  +-----------+                      +---------------+     |
|                                                           |
|  +-------------------------------------------------+      |
|  |  Dateisystem-Zugriff                            |      |
|  |  ~/Projekte/Training2/**                        |      |
|  |  - Notizen lesen/schreiben/suchen               |      |
|  |  - Checklisten verwalten                        |      |
|  |  - Aufgaben & Termine                           |      |
|  +-------------------------------------------------+      |
+-----------------------------------------------------------+
```

---

## 3. Komponenten im Detail

### 3.1 Wake-Word-Erkennung

| Aspekt | Entscheidung |
|--------|-------------|
| **Methode** | Lokal, offline |
| **Schluesselwort** | "Hey Jarvis" (konfigurierbar) |
| **Engine** | **OpenWakeWord** mit ONNX-Inference |
| **Modell** | Built-in `hey_jarvis` Modell (kein Download noetig) |
| **Schwellwert** | Konfigurierbar (Standard: 0.3) |
| **Frame-Groesse** | 80ms (1280 Samples bei 16kHz) |
| **Anforderung** | Niedriger CPU-Verbrauch im Dauerbetrieb, wenige False Positives |

**Hinweis:** OpenWakeWord wurde gewaehlt, da es komplett Open Source ist und "Hey Jarvis" als vorgefertigtes Modell bietet. ONNX-Inference wird genutzt, da `tflite-runtime` fuer Python 3.13 nicht verfuegbar ist.

### 3.2 Sprache-zu-Text (STT)

| Aspekt | Entscheidung |
|--------|-------------|
| **Methode** | Cloud-API |
| **Dienst** | **OpenAI Whisper API** (`whisper-1`) |
| **Sprachen** | Deutsch (primaer), Englisch |
| **Kosten** | ~$0.006 / Minute |
| **Endpunkt-Erkennung** | Lokale VAD (Voice Activity Detection) via **Silero-VAD** (PyTorch) -- erkennt Sprechpause, sendet Audiochunk an API |
| **PCM-zu-WAV** | In-Memory-Konvertierung vor API-Uebertragung |

**Ablauf:**
1. Wake-Word erkannt -> Bestaetigungston abspielen
2. Aufnahme startet
3. VAD erkennt Stille (konfigurierbar, Standard: 1,5 Sekunden Pause) -> Aufnahme endet
4. Audio wird an Whisper API gesendet
5. Transkription kommt zurueck als Text

### 3.3 KI-Backend (Claude Code Subprocess)

```
Transkription -> claude --print "Befehl" (mit Arbeitsverzeichnis = Notizen-Ordner)
```

| Aspekt | Entscheidung |
|--------|-------------|
| **Aufrufmethode** | `claude --print` als Subprocess |
| **Konversation** | Erster Aufruf mit `--system-prompt`, Folgeaufrufe mit `--continue` |
| **Permissions** | `--dangerously-skip-permissions` fuer unbeaufsichtigten Betrieb |
| **Timeout** | Konfigurierbar (Standard: 300 Sekunden) |
| **Nesting-Schutz** | `CLAUDECODE` Umgebungsvariable wird entfernt |
| **Arbeitsverzeichnis** | `~/Projekte/Training2` (konfigurierbar) |

Siehe auch: `002-Durchgehende-Konversation.md` fuer Details zur Session-Verwaltung.

### 3.4 Text-zu-Sprache (TTS)

| Aspekt | Entscheidung |
|--------|-------------|
| **Methode** | Cloud-API |
| **Dienst** | **OpenAI TTS** (`tts-1`) |
| **Stimme** | `onyx` (konfigurierbar) |
| **Geschwindigkeit** | Konfigurierbar (Standard: 1.0) |
| **Ausgabeformat** | PCM (24kHz, 16-bit, mono) |
| **Latenz** | Streaming-Wiedergabe direkt ueber PyAudio |
| **Kosten** | ~$0.015 / 1.000 Zeichen |

### 3.5 Dateisystem-Zugriff

| Aspekt | Detail |
|--------|--------|
| **Basisverzeichnis** | `~/Projekte/Training2` |
| **Operationen** | Lesen, Erstellen, Bearbeiten, Suchen, Auflisten |
| **Dateitypen** | Markdown (.md), Text (.txt), ggf. JSON/YAML |
| **Suchtiefe** | Rekursiv ueber alle Unterordner |
| **Zugriff** | Ueber Claude Code (hat Shell- und Dateizugriff) |

---

## 4. Ablauf eines typischen Befehls

```
Nutzer: "Hey Jarvis"
  -> [Bestaetigungston: *ding*]

Nutzer: "Vermerke in meinen Notizen, dass ich am Montag einen Arzttermin um 14 Uhr habe"
  -> [Aufnahme... Stille erkannt... Senden an Whisper API]
  -> [Thinking-Beep alle 3 Sekunden waehrend KI arbeitet]
  -> Transkription: "Vermerke in meinen Notizen, dass ich am Montag einen Arzttermin um 14 Uhr habe"
  -> [Claude Code wird aufgerufen mit diesem Befehl]
  -> Claude Code: oeffnet/erstellt passende Notiz-Datei, fuegt Eintrag hinzu
  -> Antwort: "Ich habe den Arzttermin am Montag um 14 Uhr in deinen Notizen vermerkt."
  -> [TTS spricht Antwort vor]
  -> [Ready-Sound: bereit fuer naechsten Befehl]
```

---

## 5. Technologie-Stack

| Komponente | Technologie | Lizenz / Kosten |
|-----------|-------------|-----------------|
| Sprache (Haupt) | Python 3.12+ (via uv) | Frei |
| Paketmanager | uv | Frei |
| Wake-Word | OpenWakeWord (ONNX) | Frei / Open Source |
| Audio I/O | PyAudio | Frei |
| VAD | Silero-VAD (PyTorch) | Frei |
| STT | OpenAI Whisper API | ~$0.006/min |
| KI | Claude Code (Anthropic) | API-Kosten |
| TTS | OpenAI TTS | $0.015/1k Zeichen |
| Terminal UI | Rich (Python) | Frei |
| Inference | ONNX Runtime | Frei |

---

## 6. Konfiguration

```yaml
wake_word:
  engine: openwakeword
  model_name: "hey_jarvis"
  threshold: 0.3
  inference_framework: onnx

stt:
  provider: openai
  model: whisper-1
  language: de

ai:
  backend: claude-code
  working_directory: "~/Projekte/Training2"
  system_prompt_path: "ai/prompts/system.md"
  timeout: 300
  thinking_beep_interval: 3

tts:
  provider: openai
  model: tts-1
  voice: onyx
  speed: 1.0

audio:
  sample_rate: 16000
  channels: 1
  chunk_size: 1280
  vad_chunk_size: 512
  silence_threshold_sec: 1.5
  max_recording_sec: 30
  vad_threshold: 0.5
```

---

## 7. Systemvoraussetzungen

- Ubuntu 25.04 (oder kompatibel)
- uv (Python-Paketmanager & Runtime)
- Python 3.12+ (via `uv python install`)
- Node.js 18+ (fuer Claude Code)
- Claude Code global installiert (`npm install -g @anthropic/claude-code`)
- Mikrofon (z.B. Poly BT700 Headset)
- Lautsprecher/Kopfhoerer
- PipeWire Audio
- Internetverbindung (fuer APIs)
- API-Keys: OpenAI (`OPENAI_API_KEY`), Anthropic (ueber Claude Code)

---

## 8. Umsetzungsreihenfolge

1. **Phase 1:** Wake-Word + Audio-Aufnahme + STT (Whisper) -- "spricht man, kommt Text raus" ✅
2. **Phase 2:** Claude Code Integration -- "Text wird intelligent verarbeitet" ✅
3. **Phase 3:** TTS -- "Antwort wird vorgelesen" ✅
4. **Phase 4:** Polish -- Fehlerbehandlung, UI, Konfigurierbarkeit ✅

---

## 9. Verwandte Anforderungen

| Dokument | Thema |
|----------|-------|
| `002-Durchgehende-Konversation.md` | Persistente Konversation mit `--continue` |
| `003-Audio-Signale.md` | Akustische Rueckmeldungen und Thinking-Beep |
| `004-Terminal-UI.md` | Rich-basierte Terminal-Oberflaeche |
| `005-Fehlerbehandlung-und-Logging.md` | Exception-Hierarchie und strukturiertes Logging |
