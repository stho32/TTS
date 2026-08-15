# TTS

Text-to-Speech-Anwendungen auf Basis der OpenAI-TTS-API mit Tkinter-GUI.

Dieses Repository enthaelt UV-basierte Python-Anwendungen als Single-File-Scripts.

## Struktur

- **Anforderungen/** — Anforderungsdokumente fuer die Apps (Markdown-Dateien)
- **Apps/** — Fertige UV-Single-File-Scripts

## Voraussetzungen

- Python >= 3.11
- [UV](https://docs.astral.sh/uv/) als Script-Runner
- Umgebungsvariable `OPENAI_API_KEY`
- Linux: ggf. `python3-tk` fuer Tkinter

```bash
# UV installieren
curl -LsSf https://astral.sh/uv/install.sh | sh                                    # Linux/macOS
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```

## Verwendung

### App ausfuehren

```bash
export OPENAI_API_KEY="sk-..."       # Linux/macOS
uv run Apps/tts-player.py
```

```powershell
$env:OPENAI_API_KEY = "sk-..."       # Windows (PowerShell)
uv run Apps\tts-player.py
```

Debug-Logging:

```bash
uv run Apps/tts-player.py --verbose
```

### Windows-Starter

| Datei | Zweck |
|---|---|
| `start_tts.bat` | Startet `Apps\tts-player.py` im Repo-Verzeichnis |
| `start_tts_hidden.vbs` | Ruft `start_tts.bat` ohne sichtbares Konsolenfenster auf |

`start_tts_hidden.vbs` enthaelt den absoluten Pfad `C:\Projekte\TTS` — bei abweichendem
Ablageort dort anpassen.

### Neue App erstellen

1. Anforderungsdokument in `Anforderungen/` anlegen (`/erstelle-anforderung`)
2. App in `Apps/` implementieren (`/implementiere RXXXXX`)
3. Tabelle unten ergaenzen

## Apps

| App | Beschreibung | Anforderung |
|-----|--------------|-------------|
| `Apps/tts-player.py` | TTS-Player mit pygame und winsound-Fallback (Windows) | [R00001](Anforderungen/R00001-tts-player.md) |
| `Apps/tts-player-linux.py` | TTS-Player, ausschliesslich pygame als Backend | [R00002](Anforderungen/R00002-tts-player-linux.md) |

## Funktionsumfang

- Zerlegung laengerer Texte in Abschnitte an Absatz- und Ueberschriften-Grenzen
- Synthese je Abschnitt ueber `gpt-4o-mini-tts`, Antwortformat WAV
- 11 Stimmen, optional zufaellig je Abschnitt
- Wiedergabesteuerung: Start, Pause, Stopp, vor, zurueck
- Export aller Abschnitte als einzelne WAV-Datei

## UV Single-File Script Format

Jede App ist ein einzelnes Python-Script mit eingebetteten Abhaengigkeiten (PEP 723):

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai>=1.40.0",
#     "pygame>=2.6.0",
# ]
# ///
```

UV loest die Abhaengigkeiten beim ersten Start selbst auf — kein `requirements.txt`,
keine manuelle Virtualenv-Verwaltung.
