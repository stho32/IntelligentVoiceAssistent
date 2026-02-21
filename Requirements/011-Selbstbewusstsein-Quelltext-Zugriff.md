# Selbstbewusstsein -- Zugriff auf eigenen Quelltext

## 1. Ziel

Der Sprachassistent soll wissen, wo sein eigener Quelltext liegt, und auf Anweisung des Nutzers sich selbst aendern koennen -- neue Features hinzufuegen, Bugs fixen, Konfiguration anpassen oder Tests ausfuehren. Analog zum Notizen-Ordner (`~/Projekte/Training2`), auf den Jarvis bereits Lese-/Schreibzugriff hat, soll auch der eigene Quelltext-Ordner (`~/Projekte/IntelligentVoiceAssistent`) als bekannter Arbeitsbereich konfiguriert sein.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Jarvis arbeitet ausschliesslich im Notizen-Ordner (`~/Projekte/Training2`)
- Der Quelltext-Ordner ist dem Assistenten nicht bekannt
- Aenderungen am Assistenten selbst erfordern manuelles Arbeiten mit Claude Code im Terminal
- Der System-Prompt erwaehnt nur den Notizen-Ordner
- Die CLAUDE.md beschreibt das Projekt, aber nicht die Selbstbezueglichkeit

---

## 3. Soll-Zustand

### 3.1 Selbstbewusstsein

| Aspekt | Entscheidung |
|--------|-------------|
| **Quelltext-Pfad** | `~/Projekte/IntelligentVoiceAssistent` (konfigurierbar) |
| **Bekanntmachung** | Ueber System-Prompt und CLAUDE.md |
| **Zugriff** | Lesen, Erstellen, Bearbeiten, Tests ausfuehren |
| **Kontextwechsel** | Automatisch bei Selbstbezug erkannt |

### 3.2 Erkennbare Selbstbezugs-Befehle

Der Assistent soll erkennen, wenn sich ein Befehl auf ihn selbst bezieht. Beispiele:

- "Aendere dein Wake-Word zu Computer"
- "Fuege ein neues Feature hinzu: ..."
- "Zeig mir deinen Quelltext fuer die Wake-Word-Erkennung"
- "Fuehre deine Tests aus"
- "Was steht in deiner Konfiguration?"
- "Fix den Bug in deiner Audio-Aufnahme"
- "Erstelle eine neue Anforderung fuer ..."

### 3.3 Architektur-Integration

Der System-Prompt (`sprachassistent/ai/prompts/system.md`) wird um folgende Informationen erweitert:

1. **Quelltext-Pfad**: Wo der eigene Quelltext liegt
2. **Projektstruktur**: Ueberblick ueber die wichtigsten Module
3. **Entwicklungs-Commands**: Wie Tests ausgefuehrt werden, Linting, Formatierung
4. **Anforderungen**: Wo die Anforderungsdokumente liegen
5. **Konvention**: Code und Kommentare auf Englisch, Dokumentation auf Deutsch

### 3.4 CLAUDE.md Selbstbewusstsein

Die `CLAUDE.md` im Projektverzeichnis wird um einen Abschnitt ergaenzt, der explizit festhalt:

- Dieses Repository IST der Quelltext des Sprachassistenten Jarvis
- Claude Code arbeitet hier an seinem eigenen Code
- Aenderungsauftraege beziehen sich auf den Assistenten selbst
- Qualitaetsansprueche: Tests, Linting, bestehende Architektur respektieren

---

## 4. Akzeptanzkriterien

### Konfiguration
- [ ] Quelltext-Pfad ist in `config.yaml` konfigurierbar
- [ ] CLAUDE.md enthaelt Selbstbewusstseins-Abschnitt

### System-Prompt
- [ ] System-Prompt enthaelt Quelltext-Pfad
- [ ] System-Prompt enthaelt Projektstruktur-Ueberblick
- [ ] System-Prompt enthaelt Entwicklungs-Commands

### Funktionalitaet
- [ ] Nutzer kann per Sprache Aenderungen am Quelltext beauftragen
- [ ] Nutzer kann per Sprache Tests ausfuehren lassen
- [ ] Nutzer kann per Sprache die Konfiguration einsehen/aendern
- [ ] Nutzer kann per Sprache neue Anforderungen erstellen lassen

### Sicherheit
- [ ] Quelltext-Aenderungen werden nicht automatisch deployed
- [ ] Destruktive Git-Operationen (force-push, reset --hard) werden nicht ausgefuehrt
- [ ] Der Assistent warnt bei potenziell riskanten Aenderungen

---

## 5. Konfiguration

```yaml
ai:
  backend: claude-code
  working_directory: "~/Projekte/Training2"
  source_directory: "~/Projekte/IntelligentVoiceAssistent"
  system_prompt_path: "ai/prompts/system.md"
```

---

## 6. Technische Umsetzung

### 6.1 System-Prompt Erweiterung

Der System-Prompt (`sprachassistent/ai/prompts/system.md`) wird um einen Abschnitt ergaenzt:

```markdown
Du hast ausserdem Zugriff auf deinen eigenen Quelltext unter ~/Projekte/IntelligentVoiceAssistent.
Dort befinden sich dein Python-Code, deine Tests, deine Konfiguration und deine Anforderungsdokumente.

Wenn der Nutzer dich bittet, etwas an dir selbst zu aendern (z.B. Features hinzufuegen, Bugs fixen,
Konfiguration anpassen), arbeite in diesem Verzeichnis. Beachte dabei:

- Fuehre nach Code-Aenderungen die Tests aus: uv run pytest
- Halte den bestehenden Code-Stil ein (ruff check, ruff format)
- Code und Kommentare auf Englisch, Dokumentation auf Deutsch
- Erstelle Tests fuer neue Features
```

### 6.2 CLAUDE.md Erweiterung

Die `CLAUDE.md` erhaelt einen neuen Abschnitt `## Selbstbewusstsein`, der fuer Claude Code im Terminal (nicht den Sprach-Subprocess) klarstellt, dass Aenderungsauftraege sich auf den Assistenten selbst beziehen.

### 6.3 Kontextwechsel

Der Claude-Code-Subprocess arbeitet mit `working_directory` als Basisverzeichnis. Da Claude Code Dateizugriff auf das gesamte Dateisystem hat (via `--dangerously-skip-permissions`), kann er auch auf den `source_directory`-Pfad zugreifen, ohne das Arbeitsverzeichnis zu wechseln. Der System-Prompt stellt sicher, dass der Assistent weiss, wo sein Quelltext liegt.

---

## 7. Beispiel-Interaktionen

```
Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Zeig mir deine aktuelle Konfiguration"
  -> Claude Code liest ~/Projekte/IntelligentVoiceAssistent/sprachassistent/config.yaml
  -> "Dein Wake-Word ist Hey Jarvis mit einem Schwellwert von 0.5.
      Die Sprache ist Deutsch, die TTS-Stimme ist Onyx."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Fuehre deine Tests aus"
  -> Claude Code fuehrt `uv run pytest` im Quelltext-Verzeichnis aus
  -> "Alle 42 Tests sind erfolgreich durchgelaufen."

Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Erstelle eine neue Anforderung fuer eine Lautstaerke-Regelung per Sprache"
  -> Claude Code erstellt ~/Projekte/IntelligentVoiceAssistent/Requirements/012-Lautstaerke-Regelung.md
  -> "Ich habe die Anforderung 012 Lautstaerke-Regelung erstellt."
```

---

## 8. Betroffene Dateien

### Zu aendernde Dateien

| Datei | Aenderung |
|-------|-----------|
| `CLAUDE.md` | Neuer Abschnitt "Selbstbewusstsein" |
| `sprachassistent/ai/prompts/system.md` | Quelltext-Pfad und Projektstruktur ergaenzen |
| `sprachassistent/config.yaml` | `ai.source_directory` hinzufuegen |

### Keine neuen Dateien noetig

Der Kontextwechsel erfordert keine Code-Aenderung, da Claude Code bereits Zugriff auf das gesamte Dateisystem hat. Die Steuerung erfolgt ausschliesslich ueber den System-Prompt.

---

## 9. Abhaengigkeiten

- Abhaengig von: `001-Basisanforderungen.md` (KI-Backend-Architektur)
- Abhaengig von: `002-Durchgehende-Konversation.md` (Session-Kontext)
- Ergaenzt: `009-Hilfe-und-Befehlsdokumentation.md` (Selbstbezugs-Befehle in Hilfedoku)

---

## 10. Status

- [ ] Offen
