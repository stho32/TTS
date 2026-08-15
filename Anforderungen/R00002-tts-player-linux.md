---
id: R00002
title: "TTS-Player Linux-Variante"
type: Feature
status: Erledigt
created: 2026-08-15
---

# R00002: TTS-Player Linux-Variante

> Retrospektiv erfasst — die App existierte vor Einfuehrung des Anforderungs-Workflows.

## Zweck

Linux-Variante von [R00001](R00001-tts-player.md) ohne Windows-spezifische Codepfade:
pygame ist das einzige Audio-Backend, fehlt es, bricht die App mit klarer Meldung ab
statt auf ein nicht vorhandenes `winsound` auszuweichen.

## Funktionale Anforderungen

Identisch zu [R00001](R00001-tts-player.md), mit folgenden Abweichungen:

- [x] Fenstertitel lautet "TTS Player (OpenAI) - Linux"
- [x] Kein `winsound`-Import und kein Windows-Fallback
- [x] Fehlt pygame, wird die App mit Exit-Code 1 und Installationshinweis beendet
- [x] Pause/Fortsetzen ist immer verfuegbar, da pygame das einzige Backend ist

## Technische Anforderungen

- Python >= 3.11
- Abhaengigkeiten: `openai>=1.40.0`, `pygame>=2.6.0`
- GUI: Tkinter (Standardbibliothek, unter Debian/Ubuntu ggf. `python3-tk` erforderlich)
- Audio-Backend: ausschliesslich pygame
- API-Schluessel ueber Umgebungsvariable `OPENAI_API_KEY`

## Verwendung

```bash
export OPENAI_API_KEY="sk-..."
uv run Apps/tts-player-linux.py
uv run Apps/tts-player-linux.py --verbose
```

## Exit-Codes

| Code | Bedeutung |
|---|---|
| `0` | Normales Beenden |
| `1` | pygame nicht verfuegbar oder unerwarteter Fehler |
| `2` | Ungueltige Argumente |

## Offener Punkt

`Apps/tts-player.py` laeuft technisch ebenfalls unter Linux (der `winsound`-Import ist
abgesichert). Die beiden Skripte teilen dadurch ~90 % identischen Code. Eine
Zusammenfuehrung waere moeglich, wurde aber bewusst zurueckgestellt.
