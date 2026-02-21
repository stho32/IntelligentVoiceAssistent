# Audio-Signale und Thinking-Beep

## 1. Ziel

Der Sprachassistent gibt akustische Rueckmeldungen in jeder Phase der Verarbeitung, damit der Nutzer den aktuellen Zustand erkennt, ohne auf das Terminal schauen zu muessen.

---

## 2. Signaltoene

### 2.1 Uebersicht

| Signal | Datei | Zeitpunkt | Zweck |
|--------|-------|-----------|-------|
| **Ding** | `sounds/ding.wav` | Wake-Word erkannt | Bestaetigung: "Ich hoere zu" |
| **Processing** | `sounds/processing.wav` | Aufnahme beendet, Verarbeitung startet | Rueckmeldung: "Ich verarbeite deine Anfrage" |
| **Thinking Beep** | `sounds/thinking.wav` | Periodisch waehrend KI-Verarbeitung | Lebenssignal: "Ich arbeite noch" |
| **Ready** | `sounds/ready.wav` | Antwort gesprochen, bereit fuer naechsten Befehl | Rueckmeldung: "Ich bin wieder bereit" |

### 2.2 Ablauf im Hauptloop

```
Wake-Word erkannt
  -> *ding*
  -> Aufnahme laeuft...
  -> Stille erkannt
  -> *processing*
  -> STT (Whisper)
  -> KI-Verarbeitung startet
     -> *thinking beep* (alle N Sekunden)
     -> *thinking beep*
     -> ...
  -> KI-Antwort erhalten
  -> Thinking-Beep stoppt
  -> TTS spricht Antwort
  -> *ready*
  -> Zurueck zu "Listening"
```

---

## 3. Thinking-Beep im Detail

### 3.1 Problem

Die KI-Verarbeitung ueber Claude Code kann mehrere Sekunden bis Minuten dauern. Ohne akustische Rueckmeldung weiss der Nutzer nicht, ob der Assistent noch arbeitet oder haengt.

### 3.2 Loesung

Ein periodischer, dezenter Beep-Ton signalisiert, dass die Verarbeitung noch laeuft.

| Aspekt | Entscheidung |
|--------|-------------|
| **Intervall** | Konfigurierbar (Standard: 3 Sekunden) |
| **Konfig-Key** | `ai.thinking_beep_interval` |
| **Threading** | Separater Daemon-Thread |
| **Stop-Mechanismus** | `threading.Event` -- wird gesetzt sobald Antwort vorliegt |
| **Cleanup** | Thread wird per `join(timeout=1)` nach Stop aufgeraeumt |

### 3.3 Technische Umsetzung

```python
def _thinking_beep_loop(player, stop_event, interval):
    """Play a periodic beep while the AI is thinking."""
    while not stop_event.wait(timeout=interval):
        if _THINKING_PATH.exists():
            player.play_wav(_THINKING_PATH)

# Im Hauptloop:
stop_beep = threading.Event()
beep_thread = threading.Thread(
    target=_thinking_beep_loop,
    args=(player, stop_beep, thinking_beep_interval),
    daemon=True,
)
beep_thread.start()
try:
    response = ai_backend.ask(text)
finally:
    stop_beep.set()
    beep_thread.join(timeout=1)
```

---

## 4. Signalton-Erzeugung

Die Signaltoene werden per Python-Skripte generiert (keine externen Audiodateien noetig):

| Skript | Erzeugt | Beschreibung |
|--------|---------|------------|
| `scripts/generate_ding.py` | `ding.wav` | Kurzer, klarer Bestaetigungston |
| `scripts/generate_thinking_beep.py` | `thinking.wav` | Dezenter, leiser Beep-Ton |

Die Skripte erzeugen WAV-Dateien im Verzeichnis `sprachassistent/audio/sounds/`.

---

## 5. Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | Abspielen aller Signaltoene, Thinking-Beep-Thread |
| `sprachassistent/config.yaml` | `ai.thinking_beep_interval` Parameter |
| `sprachassistent/audio/player.py` | `play_wav()` Methode fuer WAV-Wiedergabe |
| `sprachassistent/audio/sounds/` | Signaltondateien (ding, processing, ready, thinking) |
| `scripts/generate_ding.py` | Generator fuer Ding-Sound |
| `scripts/generate_thinking_beep.py` | Generator fuer Thinking-Beep |
