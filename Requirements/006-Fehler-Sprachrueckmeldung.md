# Fehler-Sprachrueckmeldung

## 1. Ziel

Bei Fehlern waehrend der Verarbeitung (STT, KI, TTS) soll der Assistent den Nutzer per Sprachausgabe informieren, anstatt nur im Terminal zu loggen. Damit bleibt der Assistent auch ohne Sichtkontakt zum Bildschirm nutzbar.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Fehler werden nur per `ui.log()` im Terminal angezeigt
- Der Nutzer hoert nach einem Fehler nur Stille
- Ohne Blick auf den Bildschirm ist unklar, ob der Assistent noch arbeitet oder ein Problem aufgetreten ist
- Der Assistent springt stumm zurueck zum LISTENING-Zustand

---

## 3. Soll-Zustand

### 3.1 Fehlermeldungen per TTS

| Fehlertyp | Sprachrueckmeldung |
|-----------|-------------------|
| **STT-Fehler** (Whisper API) | "Entschuldigung, ich konnte dich nicht verstehen. Bitte versuche es nochmal." |
| **KI-Timeout** | "Die Verarbeitung hat zu lange gedauert. Bitte versuche es nochmal." |
| **KI-Fehler** (sonstige) | "Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten." |
| **TTS-Fehler** | Kann nicht gesprochen werden (TTS selbst ist ausgefallen) -- nur Terminal-Log + Error-Sound |

### 3.2 Verhalten

| Aspekt | Entscheidung |
|--------|-------------|
| **Sprache** | Deutsch (passend zur Standardkonfiguration `language: de`) |
| **TTS-Ausfall** | Wenn TTS selbst fehlschlaegt, wird ein Error-Sound abgespielt statt Sprache |
| **Konfigurierbar** | Fehlermeldungen als Dictionary in `config.yaml` oder als Konstanten im Code |
| **Ablauf nach Fehler** | Fehlermeldung sprechen -> Ready-Sound -> zurueck zu LISTENING |

### 3.3 Error-Sound als Fallback

Ein kurzer, eindeutiger Error-Sound (`sounds/error.wav`) wird abgespielt, wenn:
- TTS selbst fehlschlaegt (Sprachausgabe unmoeglich)
- Als zusaetzliches Signal vor der gesprochenen Fehlermeldung (optional)

---

## 4. Akzeptanzkriterien

### Sprachrueckmeldung
- [ ] Bei STT-Fehler wird eine gesprochene Fehlermeldung ausgegeben
- [ ] Bei KI-Timeout wird eine spezifische Timeout-Meldung gesprochen
- [ ] Bei sonstigen KI-Fehlern wird eine allgemeine Fehlermeldung gesprochen
- [ ] Wenn TTS selbst ausfaellt, wird ein Error-Sound abgespielt

### Ablauf
- [ ] Nach der Fehlermeldung kehrt der Assistent zum LISTENING-Zustand zurueck
- [ ] Der Ready-Sound wird nach der Fehlermeldung abgespielt
- [ ] Fehler werden weiterhin im Terminal geloggt (zusaetzlich zur Sprache)

### Robustheit
- [ ] Ein Fehler in der Fehler-TTS fuehrt nicht zu einem Absturz
- [ ] Doppelte Try/Except-Absicherung: Fehler beim Sprechen der Fehlermeldung wird abgefangen

---

## 5. Technische Umsetzung

### 5.1 Fehlermeldungen als Konstanten

```python
_ERROR_MESSAGES = {
    "stt": "Entschuldigung, ich konnte dich nicht verstehen. Bitte versuche es nochmal.",
    "ai_timeout": "Die Verarbeitung hat zu lange gedauert. Bitte versuche es nochmal.",
    "ai_general": "Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten.",
}
```

### 5.2 Hilfsfunktion

```python
def _speak_error(tts, player, error_key: str, ui) -> None:
    """Speak an error message to the user, with sound fallback."""
    message = _ERROR_MESSAGES.get(error_key, _ERROR_MESSAGES["ai_general"])
    try:
        tts.speak(message, pa=player._pa)
    except Exception:
        # TTS itself failed -- play error sound as fallback
        if _ERROR_SOUND_PATH.exists():
            try:
                player.play_wav(_ERROR_SOUND_PATH)
            except Exception:
                pass
```

### 5.3 Anpassung im Hauptloop

```python
# Phase 3: Transcribe
try:
    text = transcriber.transcribe(recorded_audio)
except Exception as e:
    ui.set_state(AssistantState.ERROR)
    ui.log(f"STT error: {e}")
    _speak_error(tts, player, "stt", ui)
    ui.set_state(AssistantState.LISTENING)
    continue

# Phase 4: AI
try:
    response = ai_backend.ask(text)
except subprocess.TimeoutExpired:
    _speak_error(tts, player, "ai_timeout", ui)
    ...
except Exception as e:
    _speak_error(tts, player, "ai_general", ui)
    ...
```

---

## 6. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/main.py` | `_speak_error()` Hilfsfunktion, Fehler-Konstanten, Anpassung der Except-Bloecke |

### Neue Dateien

| Datei | Beschreibung |
|-------|------------|
| `sprachassistent/audio/sounds/error.wav` | Error-Sound als TTS-Fallback |
| `scripts/generate_error_sound.py` | Generator fuer den Error-Sound |

### Tests

| Testdatei | Prueft |
|-----------|-------|
| `tests/test_main.py` | Fehlermeldung wird bei STT-/KI-Fehler gesprochen; Fallback auf Error-Sound bei TTS-Ausfall |

---

## 7. Abhaengigkeiten

- Abhaengig von: `005-Fehlerbehandlung-und-Logging.md` (Exception-Hierarchie)
- Abhaengig von: `003-Audio-Signale.md` (Sound-Infrastruktur)

---

## 8. Status

- [x] Implementiert (2026-02-21)
