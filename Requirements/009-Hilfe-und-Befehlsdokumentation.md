# Hilfe und Befehlsdokumentation im System-Prompt

## 1. Ziel

Der Sprachassistent soll dem Nutzer auf Nachfrage erklaeren koennen, welche Sprachbefehle verfuegbar sind und wie er bedient wird -- direkt per Sprachausgabe.

---

## 2. Ist-Zustand (vor dieser Aenderung)

- Der System-Prompt (`system.md`) beschreibt nur das allgemeine Verhalten des Assistenten
- Der Assistent weiss nichts ueber seine eigenen Sonderbefehle (Abbruch, Reset)
- Fragt der Nutzer "Was kannst du?", kann der Assistent nur allgemein antworten
- Die verfuegbaren Befehle sind nur in der `config.yaml` und im Code dokumentiert

---

## 3. Soll-Zustand

### 3.1 Erweiterter System-Prompt

Der System-Prompt wird um eine Beschreibung der verfuegbaren Funktionen erweitert:

| Funktion | Beschreibung im Prompt |
|----------|----------------------|
| **Sprachbefehle** | Aktivierung per Wake-Word, dann Befehl sprechen |
| **Abbruch** | Schluesselwoerter zum Abbrechen eines laufenden Befehls |
| **Reset** | Schluesselwoerter zum Zuruecksetzen der Konversation |
| **Neustart** | Schluesselwoerter zum Neustarten des Assistenten |

### 3.2 Erwartetes Verhalten

```
Nutzer: "Hey Jarvis"
  -> *ding*
Nutzer: "Was kannst du?" / "Hilfe" / "Welche Befehle gibt es?"
  -> KI antwortet mit Uebersicht der verfuegbaren Funktionen
  -> Antwort ist kurz, natuerlich und vorlesbar (keine Listen, kein Markdown)
```

---

## 4. Akzeptanzkriterien

### System-Prompt
- [ ] System-Prompt enthaelt Beschreibung aller Sonderbefehle
- [ ] Abbruch-Schluesselwoerter sind aufgefuehrt
- [ ] Reset-Schluesselwoerter sind aufgefuehrt
- [ ] Neustart-Schluesselwoerter sind aufgefuehrt (sofern implementiert)
- [ ] Allgemeine Bedienung (Wake-Word-Aktivierung) ist beschrieben

### Verhalten
- [ ] Bei Fragen wie "Was kannst du?" liefert der Assistent eine hilfreiche Antwort
- [ ] Die Antwort ist vorlesbar (kurz, keine Sonderzeichen, keine Listen)
- [ ] Die Antwort umfasst die wichtigsten Befehle

---

## 5. Technische Umsetzung

### 5.1 Geaenderte Datei

| Datei | Aenderung |
|-------|-----------|
| `sprachassistent/ai/prompts/system.md` | Erweiterung um Befehlsdokumentation |

### 5.2 Prompt-Erweiterung

Der bestehende System-Prompt wird um einen Abschnitt ergaenzt, der die verfuegbaren Funktionen beschreibt:

- Grundlegende Bedienung (Wake-Word, Befehl, Antwort)
- Abbruch-Befehle mit Schluesselwoertern
- Konversations-Reset mit Schluesselwoertern
- Neustart-Befehl mit Schluesselwoertern

Die Formulierung ist natuerlich und instruktiv, damit der Assistent die Information in eigenen Worten wiedergeben kann.

---

## 6. Abhaengigkeiten

- Abhaengig von: `007-Kommando-Abbruch.md` (Abbruch-Schluesselwoerter)
- Abhaengig von: `008-Konversations-Reset.md` (Reset-Schluesselwoerter)
- Optional: `010-Selbst-Neustart.md` (Neustart-Schluesselwoerter, sobald implementiert)

---

## 7. Status

- [ ] Offen
