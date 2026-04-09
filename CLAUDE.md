# CLAUDE.md

## Projektbeschreibung

Text-to-Speech (TTS) Desktop-Anwendung mit OpenAI API. Konvertiert Text in Sprache ueber
die OpenAI TTS-API mit einer Tkinter-GUI. Unterstuetzt mehrere Stimmen, Batch-Verarbeitung
von Textabschnitten und Audio-Wiedergabe mit Pause/Skip/Zurueck-Steuerung.

## TechStack

- **Sprache**: Python 3.11+
- **GUI**: Tkinter
- **Audio**: pygame (bevorzugt), winsound (Fallback auf Windows)
- **API**: OpenAI TTS API (gpt-4o-mini-tts)
- **Paketmanager**: uv (PEP 723 inline script dependencies)

## Architektur-Vorlage

python-uv-app

## Run

```bash
# Windows
./start_tts.bat

# Direkt mit uv
uv run tts_app.py

# Linux-Variante
uv run tts_app_linux.py
```

Voraussetzung: Environment-Variable `OPENAI_API_KEY` muss gesetzt sein.

## Konventionen

- Keine UTF-8-Icons im Code
- Commit-Messages auf Deutsch
- Inline script dependencies (PEP 723) statt requirements.txt/pyproject.toml
- Zwei Varianten: `tts_app.py` (Windows, mit winsound-Fallback) und `tts_app_linux.py` (Linux, nur pygame)
