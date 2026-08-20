# JARVIS

Lokaler, sprachfähiger KI-Assistent mit Langzeitgedächtnis, echtem
Werkzeugsystem und minimalistischer Partikel-Oberfläche.

Alles läuft auf dem eigenen Rechner: die Modelle über Ollama, das
Gedächtnis in SQLite, Sprache und Suche über freie, lokale Komponenten.

## Start

```bash
pip install -r requirements.txt
python -m src.main          # Oberfläche mit Partikel-Orb
python -m src.main --cli    # nur Text im Terminal
```

Voraussetzung ist ein laufendes [Ollama](https://ollama.com) mit dem in
`config/settings.json` eingestellten Modell (Standard: `qwen3:8b`).
Unter Linux wird für die Oberfläche zusätzlich `sudo apt install python3-tk`
benötigt.

## Aufbau

```
src/
├── core/      Brain (Fassade), Intent, Memory-Manager, Tool-Manager, Orchestrator, Zustand
├── memory/    SQLite-Gedächtnis, Datenmodell, robuste Suche
├── llm/       Provider-Schnittstelle, Ollama, Modellauswahl, Prompts
├── tools/     Registry, Rechte, Zeit, Rechner, Dateien, Programme, Terminal, Web, Erinnerungen
├── voice/     Sprachausgabe, Spracherkennung, Mikrofon, Wake Word
├── ui/        Fenster, Partikel-Orb, Zustände
└── utils/     Logging
```

Der Ablauf einer Anfrage:

```
Eingabe → Intent-Analyse → Gedächtnis → Werkzeug → Rechteprüfung → Antwort → Stimme
```

Details und Begründungen stehen in [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md).

## Werkzeuge

Uhrzeit, Rechner, Dateien (lesen, schreiben, suchen, kopieren,
verschieben, löschen), Programme starten und beenden, laufende Programme,
Systeminfo, Speicherplatz, Lautstärke, Terminal, Websuche (DuckDuckGo mit
Wikipedia als Rückfall), Webseite abrufen, Erinnerungen und Aufgaben.

JARVIS fragt das Modell nicht nach Uhrzeit oder Rechenergebnissen – dafür
laufen echte Werkzeuge.

## Sicherheit

Vor jeder Ausführung entscheidet die `PermissionPolicy`:

| Einstellung (`config/settings.json` → `tools`) | Standard | Wirkung |
|---|---|---|
| `allow_terminal` | `false` | Terminalbefehle gesperrt |
| `allow_file_write` | `true` | Dateien schreiben erlaubt |
| `allow_file_delete` | `false` | Löschen gesperrt |
| `confirm_dangerous` | `true` | Rückfrage bei heiklen Aktionen |
| `file_roots` | `[]` | leer = nur das Benutzerverzeichnis |

Zusätzlich: keine Shell, keine Pipes und keine Befehlsverkettung im
Terminal-Werkzeug, gesperrte Systembefehle, Bestätigung vor dem
Überschreiben, und ein Fehler in einem Werkzeug beendet JARVIS nie.

## Sprache

Sprachausgabe und Spracherkennung sind austauschbar und optional:

- Ausgabe: Piper → pyttsx3 → espeak-ng (erste verfügbare gewinnt)
- Erkennung: faster-whisper → whisper → vosk
- Mikrofon: sounddevice oder PyAudio, Push-to-Talk über die Leertaste

Fehlt eine Komponente, sagt JARVIS das und bleibt per Tastatur bedienbar.

## Oberfläche

Dunkles Fenster, rotierender Partikel-Orb, große Uhr mit Datum. Die Farbe
und der Puls des Orbs zeigen den Zustand: bereit, zuhören, denken,
sprechen, Störung. Beim Zuhören reagieren die Partikel auf den
Mikrofonpegel.

`F11` Vollbild · `Esc` schließen · `Leertaste` Mikrofon

## Konfiguration

`config/settings.json` überschreibt die Standardwerte aus
`config/config.py`; Umgebungsvariablen und `.env` gehen nochmals vor.
Sektionen: `logging`, `voice`, `ui`, `tools`, `web`.

## Tests

```bash
python -m unittest discover -s tests
```
