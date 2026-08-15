# CLAUDE.md

Konventionen fuer die Arbeit an diesem Repository.

## Architektur

Dieses Projekt folgt der Vorlage **`python-uv-app`** (`~/.claude/app-architectures/python-uv-app/`):
UV-basierte Python-Single-File-Scripts mit eingebetteten Abhaengigkeiten nach PEP 723.

```
TTS/
├── Anforderungen/       <- Anforderungsdokumente (hier anfangen zu lesen)
│   ├── README.md        <- Nummernsystem
│   └── RXXXXX-*.md      <- Eine Anforderung je App/Feature
├── Apps/                <- UV-Single-File-Scripts (der eigentliche Code)
│   └── *.py
├── start_tts.bat        <- Windows-Starter
├── start_tts_hidden.vbs <- Windows-Starter ohne Konsolenfenster
├── CLAUDE.md
└── README.md            <- Uebersicht mit Apps-Tabelle
```

## Sprache

Deutsch fuer Kommentare, Commit-Messages, Anforderungen und Dokumentation.
Code-Bezeichner und Bibliotheks-APIs bleiben englisch.

## Skript-Konventionen

Jede App in `Apps/` haelt dieses Muster ein:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "paket>=1.0",
# ]
# ///

"""
[App-Beschreibung]

Anforderungen: siehe ../Anforderungen/RXXXXX-app-name.md
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        logger.info("App gestartet")
        # Logik
        logger.info("App beendet")
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Regeln:

- Dateinamen in `Apps/` sind `kebab-case.py`
- Keine `requirements.txt`, kein `pyproject.toml` — Abhaengigkeiten stehen im Skript
- Logging immer nach STDOUT, mit Zeitstempel und Kontext (was, welcher Schritt, welcher Abschnitt)
- Jede App unterstuetzt `-v` / `--verbose` fuer DEBUG-Level
- Datei-I/O immer mit `encoding="utf-8"`
- Exit-Codes: `0` Erfolg, `1` allgemeiner Fehler, `2` ungueltige Argumente

## Anforderungs-Workflow

- IDs: `R` + 5 Ziffern (`R00042`), Dateiname `RXXXXX-kebab-case-titel.md`
- Nummernbereiche: `R00001-R00099` Apps/Features, `R00100-R00199` technisch/geteilt, `R00200+` Wartungsberichte
- Status: `Neu`, `In Arbeit`, `Erledigt`
- Anforderungsdateien werden nach Erstellung **nicht** mehr veraendert
- Neue App: Anforderung anlegen → `Apps/<name>.py` implementieren → Apps-Tabelle in `README.md` ergaenzen

Befehle: `/erstelle-anforderung`, `/implementiere RXXXXX`, `/review-anforderung RXXXXX`, `/abschluss-check`, `/wartung`

## Ausfuehren

```bash
export OPENAI_API_KEY="sk-..."
uv run Apps/tts-player.py
uv run Apps/tts-player.py --verbose
```

Unter Windows alternativ `start_tts.bat` (bzw. `start_tts_hidden.vbs` ohne Konsolenfenster).
Aenderungen an den App-Dateinamen muessen dort nachgezogen werden.

Kein Setup-Schritt noetig — UV loest die Abhaengigkeiten beim ersten Start auf.

## Projektspezifisches

- **API**: OpenAI TTS, Standardmodell `gpt-4o-mini-tts`, Antwortformat WAV, Streaming mit Fallback
- **API-Schluessel**: ausschliesslich ueber `OPENAI_API_KEY`, niemals im Code
- **GUI**: Tkinter; Synthese und Wiedergabe laufen im Hintergrund-Thread, die GUI bleibt bedienbar
- **Audio**: pygame; `Apps/tts-player.py` hat zusaetzlich `winsound` als Windows-Fallback
- **Temporaere Dateien**: Arbeitsverzeichnis `tts_openai_*`, wird beim Beenden aufgeraeumt
- **Bekannte Doppelung**: `tts-player.py` und `tts-player-linux.py` teilen ~90 % Code; bei Aenderungen an
  gemeinsamen Teilen beide Dateien anpassen (siehe offener Punkt in R00002)
- Keine UTF-8-Icons im Code

## Tests

Es gibt derzeit keine automatisierten Tests. Manuelle Pruefpunkte bei Aenderungen:

1. Synthese und Wiedergabe eines mehrteiligen Textes
2. Steuerung: Pause, Stopp, vor, zurueck
3. Stimmenauswahl und Zufallsmodus
4. WAV-Export
5. Fehlerfaelle: leerer Text, fehlender `OPENAI_API_KEY`, Netzwerkfehler

## Git

Trunk-Based: kleine, themenreine Commits direkt auf `main`.
Commit-Konvention: `[RXXXXX] <beschreibung>` (deutsch).
