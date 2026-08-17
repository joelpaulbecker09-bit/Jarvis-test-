# JARVIS – Bestandsaufnahme, Zielarchitektur und Prioritäten

## 1. Bestandsaufnahme (Stand vor diesem Umbau)

| Bereich | Datei | Zustand |
| --- | --- | --- |
| Einstiegspunkt | `src/main.py` | Einfache CLI-Schleife, funktioniert |
| Denklogik | `src/core/brain.py` (608 Zeilen) | Analyzer + Memory-Aktionen + Antwort in einer Klasse |
| Kurzzeitgedächtnis | `src/core/context.py` | Sauber, funktioniert |
| Systemstatus | `src/core/state.py` | Nur Metadaten, kein Laufzeit-State (IDLE/LISTENING/…) |
| LLM | `src/llm/ollama_provider.py`, `model_manager.py` | Bereits entkoppelt, Fallback vorhanden |
| Prompts | `src/llm/prompts.py` | Umfangreicher Analyzer-Prompt, funktioniert |
| Langzeitgedächtnis | `src/memory/memory.py` (990 Zeilen) | SQLite, Validierung, Duplikatschutz, Migration – solide |
| Konfiguration | `config/config.py`, `config/settings.json` | Vorhanden, aber nur LLM-/Memory-Einstellungen |
| Tests | `tests/` | 3 Unittest-Dateien, laufen |

### Was bereits gut ist und erhalten bleibt

* Das SQLite-Memory mit `category | memory_type | entity_type | information | time_context`.
* Der Analyzer-Prompt und das `NEU / AENDERN / LOESCHEN / KEINE`-Schema.
* Die Trennung `ModelManager` ↔ `OllamaProvider`.
* Die vorhandene öffentliche Brain-API (`respond`, `analyze_message`, `process_memory`, …).

### Identifizierte Schwachstellen

1. **Kein Tool-System** – JARVIS konnte ausschließlich reden, nichts tun.
2. **`print()` statt Logging** – keine `[CORE]`/`[MEMORY]`/`[TOOL]`-Kanäle.
3. **Memory-Suche nur `LIKE %x%`** – Tippfehler, Teilbegriffe und Mehrdeutigkeit brechen Löschen/Ändern.
4. **`brain.py` macht zu viel** – Analyse, Memory-Verwaltung und Antwort in einer Datei.
5. **Kein Laufzeit-State** – `IDLE/LISTENING/THINKING/SPEAKING/ERROR` fehlte komplett.
6. **Keine Stimme, keine UI**.
7. **Keine `requirements.txt`, `.venv` und `data/*.db` waren nicht ignoriert.**
8. `generate_response()` nahm `message` entgegen, benutzte es aber nicht (die Nachricht kam nur über die Historie herein) – harmlos, aber irreführend.

## 2. Zielarchitektur

```text
                       UI (PySide6, schwarz, Partikel-Orb)
                                    │
                     JarvisState: IDLE/LISTENING/THINKING/SPEAKING/ERROR
                                    │
          ┌───────────── Orchestrator (src/core/orchestrator.py) ─────────────┐
          │                          │                          │             │
     IntentAnalyzer            MemoryManager               ToolManager     Persona/LLM
   (src/core/intent.py)   (src/core/memory_manager.py)  (src/core/tool_manager.py)
          │                          │                          │
      ModelManager               Memory + MemorySearch      ToolRegistry
          │                          │                     ┌────┴─────────────┐
    OllamaProvider              SQLite (data/memory.db)   Zeit  Rechner  Web
                                                          Dateien  Apps  System
                                                          Terminal  Erinnerungen
                                                                    │
                                                            PermissionPolicy
```

Voice liegt daneben und ist austauschbar:

```text
src/voice/stt.py   – Whisper (faster-whisper) oder Vosk, lokal
src/voice/tts.py   – Piper (lokal, deutsch, männlich) → pyttsx3 → stumm
src/voice/audio.py – Mikrofonaufnahme + Pegel für den Orb
```

Regeln der Architektur:

* Der Orchestrator kennt **Schnittstellen**, keine konkreten Engines.
* Jedes Tool ist eine eigenständige Klasse mit Beschreibung, Parametern und Risikostufe.
* Gefährliche Tools laufen nur nach Freigabe durch die `PermissionPolicy`.
* Ein Fehler in einem Tool beendet JARVIS niemals – er wird zu einem `ToolResult(ok=False)`.

## 3. Prioritäten (umgesetzte Reihenfolge)

1. Logging + Konfiguration (Fundament)
2. Memory-Suche robuster machen (Scoring statt `LIKE`)
3. LLM-Schicht: Provider-Protokoll, Verfügbarkeitsprüfung
4. Tool-System + Registry + Sicherheitsschicht
5. Web-Suche (DuckDuckGo, ohne API-Key)
6. Erinnerungen/Timer
7. `brain.py` aufteilen (Fassade bleibt abwärtskompatibel)
8. Voice (TTS/STT als austauschbare Engines)
9. State-System + Push-to-Talk
10. UI mit Partikel-Orb

## 4. Bewusst noch offen

* **Wake Word** – Schnittstelle (`src/voice/wake_word.py`) existiert, Erkennung folgt, sobald Push-to-Talk im Alltag stabil ist.
* **Semantische Memory-Suche** – erst sinnvoll bei deutlich mehr Einträgen; die Suchschicht ist dafür vorbereitet.
* **Smart Home / Hardware** – über das Tool-Interface später ohne Kernänderung ergänzbar.
