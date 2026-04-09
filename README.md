# TTS - Text-to-Speech mit OpenAI

Desktop-Anwendung zur Text-zu-Sprache-Konvertierung ueber die OpenAI TTS-API.

## Features

- Mehrere Stimmen (alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage)
- Zufaellige Stimmenwahl pro Textabschnitt
- Intelligente Textaufteilung an Absaetzen und Markdown-Ueberschriften
- Wiedergabesteuerung: Play, Pause, Stopp, Vor, Zurueck
- Hervorhebung des aktuell vorgelesenen Abschnitts
- Export als WAV-Datei
- Konfigurierbarer Chunk-Groesse (200-4000 Zeichen)

## Voraussetzungen

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (empfohlen)
- OpenAI API-Schluessel

## Nutzung

1. Environment-Variable setzen:
   ```bash
   # Windows (PowerShell)
   $env:OPENAI_API_KEY = "sk-..."

   # Linux/macOS
   export OPENAI_API_KEY="sk-..."
   ```

2. Anwendung starten:
   ```bash
   # Windows (Batch-Script)
   start_tts.bat

   # Direkt mit uv
   uv run tts_app.py

   # Linux-Variante
   uv run tts_app_linux.py
   ```

3. Text eingeben oder einfuegen, Stimme und Modell waehlen, "Vorlesen" klicken.

## Abhaengigkeiten

Die Abhaengigkeiten werden ueber PEP 723 inline script metadata verwaltet und von `uv` automatisch installiert:

- `openai>=1.40.0`
- `pygame>=2.6.0`
