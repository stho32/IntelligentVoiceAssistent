# Matrix Audio-Transkription -- Sprachnachrichten per Chat

## 1. Ziel

Der Sprachassistent soll ueber Matrix empfangene Audio-Nachrichten (Sprachnachrichten) automatisch transkribieren und wie Textnachrichten verarbeiten. Dadurch kann der Benutzer Jarvis auch per Sprachnachricht ueber die Element-App ansprechen, ohne tippen zu muessen.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Der Matrix-Client reagiert ausschliesslich auf `RoomMessageText`-Events
- Audio-Nachrichten (`RoomMessageAudio`), Bilder (`RoomMessageImage`) und Dateien (`RoomMessageFile`) werden vollstaendig ignoriert -- kein Callback registriert
- Der Benutzer muss Textnachrichten tippen, um Jarvis per Chat zu erreichen
- Die Whisper-API-Anbindung existiert bereits in `stt/whisper_api.py`, wird aber nur fuer Mikrofon-Aufnahmen genutzt

---

## 3. Soll-Zustand

### 3.1 Ueberblick

Der Matrix-Client registriert einen zusaetzlichen Callback fuer `RoomMessageAudio`-Events. Empfangene Audio-Dateien werden heruntergeladen, an die bestehende Whisper-API weitergereicht und das Transkript wie eine normale Chat-Textnachricht verarbeitet.

```
Benutzer sendet Sprachnachricht (Element App)
        |
Matrix Homeserver
        |
Bot empfaengt RoomMessageAudio
        |
Audio-Datei herunterladen (mxc:// URL)
        |
Audio an Whisper API senden (STT)
        |
Transkript als Chat-Nachricht verarbeiten
        |
Antwort als Text in den Raum senden
```

### 3.2 Audio-Download

- Matrix speichert Medien unter `mxc://`-URLs
- `matrix-nio` bietet `AsyncClient.download()` zum Herunterladen
- Unterstuetzte Formate: OGG/Opus (Element-Standard fuer Sprachnachrichten), MP3, WAV, M4A
- Die heruntergeladene Datei wird als temporaere Datei gespeichert und nach der Transkription geloescht

### 3.3 Transkription

- Nutzung der bestehenden Whisper-API-Anbindung (`stt/whisper_api.py`)
- Die Whisper API akzeptiert diverse Formate (OGG, MP3, WAV, M4A etc.) direkt -- keine Konvertierung noetig
- Bei leerer Transkription (Stille, Rauschen): Hinweis an den Benutzer senden

### 3.4 Groessenbeschraenkung

- Maximale Dateigroesse: 25 MB (Whisper-API-Limit)
- Bei Ueberschreitung: Fehlermeldung an den Benutzer senden
- Maximale Dauer: konfigurierbar (Standard: 120 Sekunden)

### 3.5 Feedback an den Benutzer

- Nach Empfang einer Sprachnachricht: Transkript als Zitat in der Antwort mitsenden, damit der Benutzer sieht, was verstanden wurde

---

## 4. Akzeptanzkriterien

### Audio-Empfang

- [ ] Der Bot empfaengt `RoomMessageAudio`-Events im konfigurierten Raum
- [ ] Nur Nachrichten von erlaubten Absendern (`allowed_users`) werden verarbeitet
- [ ] Die Audio-Datei wird ueber die `mxc://`-URL heruntergeladen

### Transkription

- [ ] Die heruntergeladene Audio-Datei wird an die Whisper API gesendet
- [ ] Das Transkript wird wie eine normale Chat-Textnachricht verarbeitet
- [ ] Bei leerer Transkription wird eine Hinweisnachricht gesendet
- [ ] Temporaere Dateien werden nach der Verarbeitung geloescht

### Fehlerbehandlung

- [ ] Audio-Dateien ueber 25 MB werden abgelehnt (Fehlermeldung an Benutzer)
- [ ] Download-Fehler werden geloggt und dem Benutzer mitgeteilt
- [ ] Transkriptions-Fehler werden geloggt und dem Benutzer mitgeteilt

### Tests

- [ ] Unit-Tests fuer den Audio-Download (gemockter Matrix-Client)
- [ ] Unit-Tests fuer die Transkription von heruntergeladenen Dateien
- [ ] Unit-Tests fuer Fehlerszenarien (zu gross, Download-Fehler, leere Transkription)
- [ ] Bestehende Tests laufen weiterhin unveraendert durch

---

## 5. Konfiguration

Keine neuen Konfigurations-Felder erforderlich. Die bestehende STT-Konfiguration (`stt.provider`, `stt.model`, `stt.language`) wird mitgenutzt.

---

## 6. Neue/Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/chat/matrix_client.py` | Neuer Callback fuer `RoomMessageAudio`, Audio-Download-Logik |
| `sprachassistent/stt/whisper_api.py` | Ggf. neue Funktion `transcribe_file()` fuer Datei-basierte Transkription |
| `tests/test_chat/test_matrix_client.py` | Tests fuer Audio-Empfang und -Verarbeitung |

---

## 7. Abhaengigkeiten

### Zu anderen Anforderungen

- Abhaengig von: `015-Matrix-Chat-Integration.md` (Matrix-Client und Queue-Mechanismus)
- Abhaengig von: `001-Basisanforderungen.md` (STT/Whisper-Anbindung)

### Externe Abhaengigkeiten

Keine neuen -- `matrix-nio` und `openai` (Whisper API) sind bereits vorhanden.

---

## 8. Entschiedene Fragen

- [x] **Audio-Format:** Element sendet Sprachnachrichten als OGG/Opus. Die Whisper API akzeptiert dieses Format direkt.
- [x] **Bilder und andere Dateien:** Werden in dieser Anforderung nicht behandelt -- nur Audio.
- [x] **Konvertierung:** Nicht noetig, Whisper akzeptiert gaengige Formate.

---

## 9. Status

- [ ] Offen
