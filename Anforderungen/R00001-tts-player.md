---
id: R00001
title: "TTS-Player (plattformuebergreifend)"
type: Feature
status: Erledigt
created: 2026-08-15
---

# R00001: TTS-Player (plattformuebergreifend)

> Retrospektiv erfasst — die App existierte vor Einfuehrung des Anforderungs-Workflows.

## Zweck

Laengere Texte ueber die OpenAI-TTS-API in Sprache umwandeln und direkt abspielen,
mit Steuerung auf Abschnittsebene und optionalem Export als WAV-Datei.

## Funktionale Anforderungen

- [x] Texteingabe ueber eine Tkinter-GUI mit Log-Fenster und Statuszeile
- [x] Automatische Zerlegung des Textes in Abschnitte an Absatz- und Markdown-Ueberschriften-Grenzen
- [x] Abschnittsgroesse in der UI einstellbar (200–4000 Zeichen, Standard 800)
- [x] Synthese je Abschnitt ueber die OpenAI-TTS-API, Antwortformat WAV
- [x] Streaming-Antwort mit Fallback auf nicht-streamende Anfrage
- [x] Auswahl aus 11 Stimmen (alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage)
- [x] Optionale zufaellige Stimmenwahl je Abschnitt
- [x] Wiedergabesteuerung: Start, Pause, Stopp, naechster Abschnitt, vorheriger Abschnitt
- [x] Fortschrittsanzeige und Hervorhebung des aktuell gesprochenen Abschnitts im Eingabefeld
- [x] Export aller erzeugten Abschnitte als einzelne WAV-Datei
- [x] Synthese und Wiedergabe laufen in einem Hintergrund-Thread, die GUI bleibt bedienbar
- [x] Temporaeres Arbeitsverzeichnis (`tts_openai_*`) wird beim Beenden aufgeraeumt
- [x] Logging nach STDOUT mit Zeitstempel; `--verbose` schaltet auf DEBUG

## Technische Anforderungen

- Python >= 3.11
- Abhaengigkeiten: `openai>=1.40.0`, `pygame>=2.6.0`
- GUI: Tkinter (Standardbibliothek)
- Audio-Backend: pygame bevorzugt, `winsound` als Fallback unter Windows
- API-Schluessel ueber Umgebungsvariable `OPENAI_API_KEY`
- Standardmodell: `gpt-4o-mini-tts`

## Verwendung

```bash
export OPENAI_API_KEY="sk-..."
uv run Apps/tts-player.py
uv run Apps/tts-player.py --verbose
```

## Fehlerverhalten

| Situation | Verhalten |
|---|---|
| `OPENAI_API_KEY` nicht gesetzt | Warnung im Log beim Start, Synthese schlaegt spaeter mit Fehlermeldung fehl |
| Kein Audio-Backend verfuegbar | Fehlermeldung, Wiedergabe nicht moeglich |
| API-Fehler bei einem Abschnitt | Fehlermeldung im Log, Verarbeitung wird abgebrochen |
| Inkonsistente WAV-Parameter beim Export | Fehlermeldung, kein Export |

## Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | Normales Beenden |
| `1` | Unerwarteter Fehler |
| `2` | Ungueltige Argumente |
