# Cross-Platform-Abstraktion -- Linux und Windows

## 1. Ziel

Der Sprachassistent soll sowohl unter Linux als auch unter Windows lauffaehig sein. Dazu wird eine Plattform-Abstraktionsschicht eingefuehrt, die betriebssystemspezifische Funktionalitaet hinter einheitlichen Interfaces kapselt. Die bestehenden Linux-Implementierungen bleiben vollstaendig erhalten und werden unveraendert weiterverwendet. Fuer Windows kommen neue Implementierungen derselben Interfaces hinzu.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Der Assistent laeuft ausschliesslich unter **Ubuntu 25.04**
- **Audio I/O** (Mikrofon, Wiedergabe) nutzt PyAudio direkt, kompiliert gegen PipeWire/ALSA (Linux-spezifisches Binary `.so`)
- **TTS-Wiedergabe** (`OpenAITextToSpeech.speak()`) erhaelt eine `pyaudio.PyAudio`-Instanz als Parameter und oeffnet PyAudio-Streams direkt
- **Prozess-Neustart** (`_restart_assistant()` in `main.py`) nutzt `os.execv()`, einen POSIX-only Systemaufruf
- Keine Plattform-Erkennung oder -Abstraktion vorhanden
- Die Audio-Klassen `MicrophoneStream` und `AudioPlayer` sind direkt an PyAudio gebunden

### Betroffene Stellen im Code

| Datei | OS-spezifischer Code | Problem auf Windows |
|-------|---------------------|---------------------|
| `audio/microphone.py` | `pyaudio.PyAudio()`, `pa.open(input=True)` | Linux-Binary, PipeWire-Backend |
| `audio/player.py` | `pyaudio.PyAudio()`, `pa.open(output=True)`, `open_pcm_stream()` | Linux-Binary, PipeWire-Backend |
| `tts/openai_tts.py` | `pyaudio.PyAudio()`, `pa.open(output=True)` in `speak()` | Linux-Binary, PipeWire-Backend |
| `main.py:116` | `os.execv(sys.executable, ...)` | Existiert unter Windows nicht |

---

## 3. Soll-Zustand

### 3.1 Plattform-Abstraktionsschicht

| Aspekt | Entscheidung |
|--------|-------------|
| **Abstraktionsmechanismus** | Python Protocols oder ABCs (Abstract Base Classes) |
| **Linux-Implementierungen** | Bestehender Code, unveraendert, hinter dem Interface |
| **Windows-Implementierungen** | Neue Klassen, selbes Interface |
| **Plattform-Erkennung** | `sys.platform` zur Laufzeit |
| **Factory** | Zentrale Factory-Funktion(en), die anhand der Plattform die richtige Implementierung instanziiert |
| **Konfiguration** | Optional: explizite Plattform-Angabe in `config.yaml` (Override) |

### 3.2 Zu abstrahierende Bereiche

#### 3.2.1 Audio-Eingabe (Mikrofon)

Abstraktes Interface fuer `MicrophoneStream` mit folgender Schnittstelle:

- Context Manager (`__enter__`, `__exit__`)
- `read_chunk() -> bytes` -- liefert PCM-Daten (int16, mono)
- `close()` -- Ressourcen freigeben
- Properties: `rate`, `channels`, `chunk_size`

**Linux-Implementierung:** Bestehende `MicrophoneStream`-Klasse (PyAudio/PipeWire), unveraendert.

**Windows-Implementierung:** Neue Klasse, z.B. basierend auf `sounddevice` oder PyAudio mit WASAPI-Backend. Muss dasselbe Interface erfuellen.

#### 3.2.2 Audio-Ausgabe (Player)

Abstraktes Interface fuer `AudioPlayer` mit folgender Schnittstelle:

- Context Manager (`__enter__`, `__exit__`)
- `play_wav(path: str | Path) -> None`
- `play_pcm(data: bytes, rate: int, channels: int) -> None`
- `open_pcm_stream(rate: int, channels: int) -> StreamHandle` -- Gibt ein abstraktes Stream-Handle zurueck (statt `pyaudio.Stream`)
- `close()` -- Ressourcen freigeben

**Wichtig:** `open_pcm_stream()` gibt aktuell ein `pyaudio.Stream`-Objekt zurueck, das in `tts/openai_tts.py` direkt verwendet wird. Das Stream-Handle muss ebenfalls abstrahiert werden (mindestens `write(data)`, `stop_stream()`, `close()`).

**Linux-Implementierung:** Bestehende `AudioPlayer`-Klasse, unveraendert.

**Windows-Implementierung:** Neue Klasse mit WASAPI-kompatiblem Backend.

#### 3.2.3 TTS-Audio-Ausgabe

Die `OpenAITextToSpeech.speak()`-Methode nutzt aktuell `pyaudio.PyAudio` direkt als Parameter. Dies muss entkoppelt werden:

- `speak()` soll statt `pa: pyaudio.PyAudio` ein abstraktes Audio-Ausgabe-Objekt oder den `AudioPlayer` selbst erhalten
- Alternativ: `speak()` nutzt intern `synthesize()` + uebergibt PCM-Daten an den abstrakten Player

**Ziel:** Die TTS-Klasse soll keine direkte PyAudio-Abhaengigkeit mehr haben.

#### 3.2.4 Prozess-Neustart

Abstraktes Interface oder plattformspezifische Funktion fuer `_restart_assistant()`:

**Linux-Implementierung:** `os.execv(sys.executable, [sys.executable] + sys.argv)` -- bestehender Code, unveraendert.

**Windows-Implementierung:** `subprocess.Popen([sys.executable] + sys.argv)` gefolgt von `sys.exit(0)`, oder aequivalente Windows-kompatible Restart-Strategie.

### 3.3 Plattform-Factory

Eine zentrale Stelle (z.B. `sprachassistent/platform/factory.py` oder aehnlich), die:

1. Die aktuelle Plattform erkennt (`sys.platform`)
2. Die passenden Implementierungen instanziiert
3. In `main.py` anstelle der direkten Klassen-Importe verwendet wird

Beispielhafte Struktur:

```
sprachassistent/
  platform/
    __init__.py          # Plattform-Erkennung, Factory-Funktionen
    audio_base.py        # Abstrakte Interfaces (Protocol/ABC)
    linux/
      __init__.py
      microphone.py      # Bestehende MicrophoneStream (verschoben oder importiert)
      player.py          # Bestehende AudioPlayer (verschoben oder importiert)
      process.py         # os.execv-basierter Restart
    windows/
      __init__.py
      microphone.py      # Neue Windows-MicrophoneStream
      player.py          # Neue Windows-AudioPlayer
      process.py         # subprocess-basierter Restart
```

**Alternative:** Die bestehenden Dateien (`audio/microphone.py`, `audio/player.py`) koennen auch an Ort und Stelle bleiben und als Linux-Implementierung dienen. Die Abstraktion wird dann als zusaetzliche Schicht darueber gelegt, und die Windows-Implementierungen kommen in ein separates Verzeichnis. Die konkrete Dateistruktur wird bei der Implementierung entschieden.

### 3.4 Abhaengigkeiten je Plattform

| Abhaengigkeit | Linux | Windows | Anmerkung |
|---------------|-------|---------|-----------|
| `pyaudio` | Ja (bestehend) | Optional | Kann auf Windows mit WASAPI-Backend funktionieren, oder durch `sounddevice` ersetzt werden |
| `sounddevice` | Nein (nicht noetig) | Moeglich | Cross-platform Alternative zu PyAudio |
| `openai` | Ja | Ja | Plattformunabhaengig |
| `torch`, `silero-vad` | Ja | Ja | Haben Windows-Wheels |
| `openwakeword`, `onnxruntime` | Ja | Ja | Haben Windows-Wheels |

Die konkreten Windows-Audio-Abhaengigkeiten werden bei der Implementierung evaluiert. `sounddevice` waere die einfachste Option, da es auf beiden Plattformen funktioniert und PortAudio intern kapselt.

---

## 4. Akzeptanzkriterien

### Abstraktion
- [ ] Es existieren abstrakte Interfaces (Protocol oder ABC) fuer Audio-Eingabe, Audio-Ausgabe und Prozess-Neustart
- [ ] Die bestehenden Linux-Implementierungen sind **unveraendert funktionsfaehig** und erfuellen die Interfaces
- [ ] Die Interfaces sind vollstaendig dokumentiert (Docstrings mit Parametern und Rueckgabetypen)

### Windows-Implementierung
- [ ] Es existieren Windows-spezifische Implementierungen fuer Audio-Eingabe, Audio-Ausgabe und Prozess-Neustart
- [ ] Die Windows-Implementierungen erfuellen dieselben Interfaces wie die Linux-Varianten
- [ ] Audio-Aufnahme und -Wiedergabe funktionieren unter Windows mit dem Standard-Audiogeraet

### Plattform-Erkennung
- [ ] Die richtige Implementierung wird automatisch anhand der Plattform geladen
- [ ] Optional: Plattform kann in `config.yaml` explizit ueberschrieben werden

### TTS-Entkopplung
- [ ] `OpenAITextToSpeech` hat keine direkte `pyaudio`-Abhaengigkeit mehr
- [ ] TTS-Ausgabe laeuft ueber die abstrahierte Audio-Ausgabe

### Tests
- [ ] Bestehende Tests laufen weiterhin unveraendert durch
- [ ] Neue Tests fuer die Abstraktionsschicht und Factory-Logik
- [ ] Neue Tests fuer die Windows-Implementierungen (mockbar ohne Windows)

### Nicht-Ziele (explizit ausgeklammert)
- macOS-Unterstuetzung (kann spaeter ergaenzt werden)
- Aenderungen an der Geschaeftslogik (Wake-Word, VAD, STT, AI-Backend)
- Aenderungen an der Terminal-UI oder am Logging

---

## 5. Betroffene Dateien

### Bestehende Dateien (Anpassung noetig)

| Datei | Aenderung |
|-------|-----------|
| `main.py` | Factory statt direkter Klassen-Importe verwenden; `_restart_assistant()` durch plattformspezifische Variante ersetzen |
| `tts/openai_tts.py` | PyAudio-Abhaengigkeit durch abstraktes Audio-Interface ersetzen |
| `pyproject.toml` | Ggf. `sounddevice` als optionale/Windows-Abhaengigkeit ergaenzen |

### Bestehende Dateien (NICHT aendern)

| Datei | Grund |
|-------|-------|
| `audio/microphone.py` | Bleibt als Linux-Implementierung erhalten |
| `audio/player.py` | Bleibt als Linux-Implementierung erhalten |
| `audio/recorder.py` | Plattformunabhaengig (nutzt nur `bytes` und `torch`) |
| `audio/wake_word.py` | Plattformunabhaengig (nutzt nur ONNX) |
| `stt/whisper_api.py` | Plattformunabhaengig (Cloud-API) |
| `ai/claude_code.py` | Plattformunabhaengig (`subprocess.Popen`) |

### Neue Dateien

| Datei | Inhalt |
|-------|--------|
| Abstrakte Interfaces | Protocol/ABC fuer Audio-Eingabe, Audio-Ausgabe, Stream-Handle, Prozess-Neustart |
| Plattform-Factory | Erkennung + Instanziierung der richtigen Implementierung |
| Windows Audio-Eingabe | `MicrophoneStream`-Implementierung fuer Windows |
| Windows Audio-Ausgabe | `AudioPlayer`-Implementierung fuer Windows |
| Windows Prozess-Neustart | `subprocess`-basierter Restart fuer Windows |
| Tests | Tests fuer Factory, Interfaces und Windows-Implementierungen |

Die konkrete Dateistruktur (ob `platform/`-Verzeichnis oder andere Organisation) wird bei der Implementierung festgelegt.

---

## 6. Abhaengigkeiten zu anderen Anforderungen

- Abhaengig von: `001-Basisanforderungen.md` (Audio-Pipeline-Architektur)
- Abhaengig von: `003-Audio-Signale.md` (WAV-Wiedergabe ueber AudioPlayer)
- Abhaengig von: `010-Selbst-Neustart.md` (`_restart_assistant()` wird abstrahiert)
- Beeinflusst: `011-Selbstbewusstsein-Quelltext-Zugriff.md` (Quelltext-Struktur aendert sich durch neue Dateien)
- Beeinflusst: `012-Konversations-Persistenz-ueber-Neustart.md` (Neustart-Mechanismus wird abstrahiert)

---

## 7. Status

- [ ] Offen
