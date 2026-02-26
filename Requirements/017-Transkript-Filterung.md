# Transkript-Filterung und Leertext-Behandlung

## 1. Ziel

Transkripte der Whisper-API enthalten gelegentlich Artefakte -- wiederkehrende Phantomsequenzen, die nichts mit dem gesprochenen Text zu tun haben (z.B. "Untertitel der Amara.org-Community"). Solche Sequenzen sollen automatisch entfernt werden. Zusaetzlich sollen leere Transkripte einheitlich ignoriert und zu kurze Aufnahmen (unter 2 Sekunden) gar nicht erst transkribiert werden.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Whisper liefert gelegentlich Phantomtexte bei kurzen oder stillen Aufnahmen (bekanntes Whisper-Halluzinationsproblem)
- Der Voice-Pfad prueft `text.strip()` auf leer und springt zurueck zum Lauschen
- Der Matrix-Audio-Pfad prueft `text.strip()` und sendet eine Fehlermeldung bei leerem Transkript
- Es gibt keine Filterung bekannter Artefakt-Phrasen
- Es gibt keine Mindestdauer-Pruefung fuer Aufnahmen -- auch Sekundenbruchteile werden an Whisper gesendet
- Sehr kurze Aufnahmen (z.B. versehentliches Ausloesen) verbrauchen unnoetig API-Aufrufe

---

## 3. Soll-Zustand

### 3.1 Ueberblick

```
Aufnahme beendet
      |
Dauer < min_duration_sec? --ja--> ignorieren (zurueck zum Lauschen)
      |nein
Whisper-Transkription
      |
Artefakt-Phrasen entfernen
      |
Text leer nach Filterung? --ja--> ignorieren
      |nein
Weiterverarbeitung (AI, Chat-Antwort usw.)
```

### 3.2 Artefakt-Filterung (Phantom-Phrasen)

- Eine konfigurierbare Liste von Textsequenzen, die aus Transkripten entfernt werden
- Filterung erfolgt case-insensitiv
- Nach Entfernung wird der Text erneut auf leer geprueft
- Die Filterung findet zentral statt (eine Funktion, von allen Pfaden genutzt)

### 3.3 Mindestdauer fuer Aufnahmen

- Voice-Aufnahmen unter einer konfigurierbaren Mindestdauer (Standard: 2 Sekunden) werden nicht transkribiert
- Die Dauer wird anhand der Byte-Laenge und der Sample-Rate berechnet: `len(audio_data) / (sample_rate * 2)` (16-bit = 2 Bytes pro Sample)
- Gilt fuer den Voice-Pfad in `main.py`; Matrix-Audio hat bereits eigene Laengenvalidierung

### 3.4 Einheitliche Leertext-Behandlung

- Alle Pfade (Voice, Matrix-Audio, Texteingabe) pruefen nach der Filterung auf leeren Text
- Leere Transkripte werden still ignoriert (Voice-Pfad) bzw. mit Hinweis quittiert (Matrix-Pfad)

---

## 4. Akzeptanzkriterien

### Artefakt-Filterung

- [ ] Konfigurierbare Liste `stt.filter_phrases` in `config.yaml`
- [ ] Bekannte Phrase "Untertitel der Amara.org-Community" ist als Standard enthalten
- [ ] Phrasen werden case-insensitiv aus Transkripten entfernt
- [ ] Filterfunktion in `stt/whisper_api.py` als Methode des Transcribers
- [ ] Voice-Pfad nutzt die Filterung nach `transcribe()`
- [ ] Matrix-Audio-Pfad nutzt die Filterung nach `transcribe_file()`

### Mindestdauer

- [ ] Konfigurierbarer Wert `audio.min_recording_sec` in `config.yaml` (Standard: 2.0)
- [ ] Voice-Aufnahmen unter der Mindestdauer werden nicht transkribiert
- [ ] Stattdessen wird leise zurueck zum Lauschen gewechselt (kein Fehler)

### Leertext-Behandlung

- [ ] Nach Filterung leere Transkripte werden in allen Pfaden korrekt ignoriert
- [ ] Bestehendes Verhalten fuer bereits leere Transkripte bleibt erhalten

### Tests

- [ ] Unit-Tests fuer die Filterfunktion (Phrase entfernt, case-insensitiv, mehrere Phrasen)
- [ ] Unit-Tests fuer die Mindestdauer-Pruefung
- [ ] Unit-Tests fuer Leertext nach Filterung
- [ ] Bestehende Tests laufen unveraendert durch

---

## 5. Konfiguration

Neue Felder in `config.yaml`:

```yaml
stt:
  provider: openai
  model: whisper-1
  language: de
  filter_phrases:
    - "Untertitel der Amara.org-Community"

audio:
  # ... bestehende Felder ...
  min_recording_sec: 2.0
```

---

## 6. Neue/Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/config.yaml` | Neue Felder `stt.filter_phrases`, `audio.min_recording_sec` |
| `sprachassistent/stt/whisper_api.py` | Neue Methode `filter_transcript()` im `WhisperTranscriber` |
| `sprachassistent/main.py` | Mindestdauer-Pruefung vor Transkription, Filterung nach Transkription |
| `sprachassistent/chat/matrix_client.py` | Filterung nach Audio-Transkription |
| `tests/test_stt/test_whisper_api.py` | Tests fuer `filter_transcript()` |
| `tests/test_main.py` | Tests fuer Mindestdauer-Pruefung |
| `tests/test_chat/test_matrix_client.py` | Tests fuer Filterung im Chat-Pfad |

---

## 7. Abhaengigkeiten

### Zu anderen Anforderungen

- Abhaengig von: `001-Basisanforderungen.md` (STT/Whisper-Anbindung)
- Abhaengig von: `016-Matrix-Audio-Transkription.md` (Audio-Transkription im Chat)

### Externe Abhaengigkeiten

Keine neuen.

---

## 8. Offene Fragen

Keine.

---

## 9. Status

- [ ] Offen
