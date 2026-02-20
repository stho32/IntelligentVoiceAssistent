# Sprachassistent "Computer" -- Basisanforderungen

## 1. Vision

Ein lokaler Sprachassistent, der per Schluesselwort **"Computer"** aktiviert wird, natuerliche Sprache versteht und Aufgaben ueber eine KI im Terminal ausfuehrt -- mit direktem Lese-/Schreibzugriff auf den Notizen-Ordner.

---

## 2. Architekturuebersicht

```
+-----------------------------------------------------------+
|                    Hauptprozess (Python)                   |
|                                                           |
|  +-----------+    +-----------+    +-------------------+  |
|  |  Wake-Word |-->|  STT      |-->|  KI-Backend       |  |
|  |  (lokal)   |   |  (Cloud)  |   |  (Claude Code     |  |
|  |  Porcupine |   |  Whisper  |   |   oder API)       |  |
|  |  / Vosk    |   |  API      |   |                   |  |
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
|  |  C:\Projekte\Training2\**                       |      |
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
| **Schluesselwort** | "Computer" (konfigurierbar) |
| **Optionen** | **Picovoice Porcupine** (bevorzugt, genau, custom wake words moeglich, kostenloser Tier) oder **OpenWakeWord** (komplett Open Source) |
| **Anforderung** | Niedriger CPU-Verbrauch im Dauerbetrieb, wenige False Positives |

**Empfehlung:** Porcupine -- hat "Computer" als vorgefertigtes Wake-Word, sehr zuverlaessig, laeuft auf Windows.

### 3.2 Sprache-zu-Text (STT)

| Aspekt | Entscheidung |
|--------|-------------|
| **Methode** | Cloud-API |
| **Dienst** | **OpenAI Whisper API** (`whisper-1`) |
| **Sprachen** | Deutsch (primaer), Englisch |
| **Kosten** | ~$0.006 / Minute |
| **Endpunkt-Erkennung** | Lokale VAD (Voice Activity Detection) via `webrtcvad` oder `silero-vad` -- erkennt Sprechpause, sendet Audiochunk an API |

**Ablauf:**
1. Wake-Word erkannt -> Bestaetigungston abspielen
2. Aufnahme startet
3. VAD erkennt Stille (z.B. 1,5 Sekunden Pause) -> Aufnahme endet
4. Audio wird an Whisper API gesendet
5. Transkription kommt zurueck als Text

### 3.3 KI-Backend

#### Variante A: Claude Code als Subprocess (empfohlen)

```
Transkription -> claude-code --print "Befehl" (mit Arbeitsverzeichnis = Notizen-Ordner)
```

| Vorteil | Nachteil |
|---------|----------|
| Claude Code hat bereits Dateizugriff, Shell-Zugriff, Tool-Use | Braucht Node.js + Claude Code Installation |
| Versteht Kontext, kann eigenstaendig suchen & bearbeiten | Etwas langsamere Startzeit pro Aufruf |
| Kann komplexe Aufgaben (z.B. "fasse alle Notizen von letzter Woche zusammen") | Kosten via Anthropic API |
| Nutzt `--print` Flag fuer non-interaktive Aufrufe | |

#### Variante B: Claude API + eigenes Tool-System

```
Transkription -> Python-Script -> Claude API mit Function Calling -> lokale Tool-Funktionen
```

| Vorteil | Nachteil |
|---------|----------|
| Volle Kontrolle ueber Tools & Verhalten | Muss selbst Tools fuer Dateizugriff implementieren |
| Schnellerer Roundtrip (kein Subprocess) | Weniger flexibel als Claude Code |
| Guenstiger (nur API-Kosten, kein Claude Code Overhead) | Komplexere Aufgaben brauchen mehr Eigenentwicklung |

**Empfehlung:** Starte mit **Variante A (Claude Code)** -- weniger Eigenentwicklung, maechtigere Faehigkeiten.

### 3.4 Text-zu-Sprache (TTS)

| Aspekt | Entscheidung |
|--------|-------------|
| **Methode** | Cloud-API |
| **Dienst** | **OpenAI TTS** (`tts-1` oder `tts-1-hd`) |
| **Stimme** | `onyx` oder `nova` (deutsch klingt bei beiden gut) |
| **Kosten** | ~$0.015 / 1.000 Zeichen |
| **Alternative** | **Edge-TTS** (kostenlos, Microsoft, gute deutsche Stimmen, etwas weniger natuerlich) |

### 3.5 Dateisystem-Zugriff

| Aspekt | Detail |
|--------|--------|
| **Basisverzeichnis** | `C:\Projekte\Training2` |
| **Operationen** | Lesen, Erstellen, Bearbeiten, Suchen, Auflisten |
| **Dateitypen** | Markdown (.md), Text (.txt), ggf. JSON/YAML |
| **Suchtiefe** | Rekursiv ueber alle Unterordner |

---

## 4. Ablauf eines typischen Befehls

```
Nutzer: "Computer"
  -> [Bestaetigungston: *ding*]

Nutzer: "Vermerke in meinen Notizen, dass ich am Montag einen Arzttermin um 14 Uhr habe"
  -> [Aufnahme... Stille erkannt... Senden an Whisper API]
  -> Transkription: "Vermerke in meinen Notizen, dass ich am Montag einen Arzttermin um 14 Uhr habe"
  -> [Claude Code wird aufgerufen mit diesem Befehl]
  -> Claude Code: oeffnet/erstellt passende Notiz-Datei, fuegt Eintrag hinzu
  -> Antwort: "Ich habe den Arzttermin am Montag um 14 Uhr in deinen Notizen vermerkt."
  -> [TTS spricht Antwort vor]
```

---

## 5. Technologie-Stack

| Komponente | Technologie | Lizenz / Kosten |
|-----------|-------------|-----------------|
| Sprache (Haupt) | Python 3.11+ (via uv) | Frei |
| Paketmanager | uv / uvx | Frei |
| Wake-Word | Picovoice Porcupine | Kostenlos (Free Tier) |
| Audio I/O | PyAudio / sounddevice | Frei |
| VAD | silero-vad oder webrtcvad | Frei |
| STT | OpenAI Whisper API | ~$0.006/min |
| KI | Claude Code (Anthropic) | API-Kosten |
| TTS | OpenAI TTS oder Edge-TTS | $0.015/1k Zeichen bzw. kostenlos |
| Terminal UI | Rich (Python) | Frei |

---

## 6. Konfiguration

```yaml
wake_word:
  engine: porcupine
  keyword: computer
  sensitivity: 0.6

stt:
  provider: openai
  model: whisper-1
  language: de

ai:
  backend: claude-code
  working_directory: "C:\\Projekte\\Training2"
  system_prompt_path: "ai/prompts/system.md"

tts:
  provider: openai
  model: tts-1
  voice: onyx
  speed: 1.0

audio:
  sample_rate: 16000
  silence_threshold_sec: 1.5
  max_recording_sec: 30
```

---

## 7. Offene Entscheidungen

- [ ] Picovoice API-Key besorgen (kostenlos registrieren)
- [ ] OpenAI API-Key vorhanden? (fuer Whisper + ggf. TTS)
- [ ] Anthropic API-Key vorhanden? (fuer Claude Code)
- [ ] Mikrofon: welches wird verwendet?
- [ ] Edge-TTS als kostenlosen TTS-Fallback testen?

---

## 8. Umsetzungsreihenfolge

1. **Phase 1:** Wake-Word + Audio-Aufnahme + STT (Whisper) -- "spricht man, kommt Text raus"
2. **Phase 2:** Claude Code Integration -- "Text wird intelligent verarbeitet"
3. **Phase 3:** TTS -- "Antwort wird vorgelesen"
4. **Phase 4:** Polish -- Fehlerbehandlung, UI, Konfigurierbarkeit

---

## 9. Systemvoraussetzungen

- Windows 10/11
- uv (Python-Paketmanager & Runtime)
- Python 3.11+ (via `uv python install`)
- Node.js 18+ (fuer Claude Code)
- Mikrofon
- Lautsprecher/Kopfhoerer
- Internetverbindung (fuer APIs)
- API-Keys: Picovoice, OpenAI, Anthropic
