---
id: R00003
title: "Tempo-Waehler und neue Stimmen"
type: Feature
status: Erledigt
created: 2026-08-15
---

# R00003: Tempo-Waehler und neue Stimmen

## Zweck

Das Sprechtempo soll in der Oberflaeche einstellbar sein, und die seit dem letzten
Stand hinzugekommenen OpenAI-Stimmen sollen zur Auswahl stehen.

Betrifft beide Apps — [R00001](R00001-tts-player.md) und [R00002](R00002-tts-player-linux.md).
Umgesetzt zuerst in der Linux-Variante, anschliessend unveraendert nachgezogen.

## Recherche-Ergebnis (Stand August 2026)

Untersucht wurde, ob neuere TTS-Modelle verfuegbar sind und wie sich das Tempo steuern laesst:

| Befund | Ergebnis |
|---|---|
| Verfuegbare TTS-Modelle | unveraendert `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd` — kein neueres Modell |
| Snapshot von `gpt-4o-mini-tts` | neuer Default `gpt-4o-mini-tts-2025-12-15`; der Alias zieht automatisch nach |
| Neue Stimmen | `marin` und `cedar` — nur bei `gpt-4o-mini-tts`, nicht bei `tts-1`/`tts-1-hd` |
| `speed`-Parameter | 0.25–4.0, Default 1.0; wirkt messbar, auch bei `gpt-4o-mini-tts` |
| `instructions` zur Temposteuerung | praktisch wirkungslos, daher nicht verwendet |

Messung ueber die Worker-Methode `_synthesize_chunk_to_wav` (Streaming-Pfad), gleicher Testsatz:

| `speed` | Audio-Dauer |
|---|---|
| 1.0 | 5,20 s |
| 2.0 | 2,69 s |
| 0.5 | 12,13 s |

Damit ist der API-Parameter der Weg der Wahl — clientseitiges Resampling waere unnoetig gewesen.

## Funktionale Anforderungen

- [x] Tempo-Auswahl in der Steuerleiste (Spinbox, 0.25x–4.00x, Schrittweite 0.05, Vorgabe 1.00x)
- [x] Schaltflaeche "1x" setzt das Tempo auf den Standardwert zurueck
- [x] Das Tempo wird als `speed` an beide API-Pfade uebergeben (Streaming und Fallback)
- [x] Werte ausserhalb von 0.25–4.0 werden begrenzt, ungueltige Eingaben fallen auf 1.0 zurueck;
      die Begrenzung wird im Log gemeldet
- [x] Stimmenliste um `marin` und `cedar` erweitert (13 statt 11)
- [x] Bei `tts-1`/`tts-1-hd` zeigt die Auswahl nur die 6 unterstuetzten Stimmen; eine nicht
      unterstuetzte Stimme wird mit Log-Hinweis auf die erste gueltige umgestellt
- [x] Das Log nennt je Abschnitt Stimme und Tempo
- [x] "Vorlesen" uebernimmt die Einstellungen selbsttaetig — der Klick auf
      "Einstellungen übernehmen" ist nicht mehr noetig
- [x] Tempo-Bedienelemente sind waehrend der Wiedergabe gesperrt wie die uebrigen Einstellungen

## Technische Anforderungen

- Keine neuen Abhaengigkeiten — der Effekt entsteht serverseitig ueber den API-Parameter
- Bereichsgrenzen als Konstanten `SPEED_MIN`, `SPEED_MAX`, `DEFAULT_SPEED`
- Hilfsfunktionen `clamp_speed()` und `voices_for_model()` sind GUI-frei und dadurch pruefbar

## Verwendung

```bash
export OPENAI_API_KEY="sk-..."
uv run Apps/tts-player-linux.py
uv run Apps/tts-player.py
```

Tempo in der oberen Leiste einstellen, Text eingeben, "Vorlesen".

## Verifikation

- Logik-Pruefungen ohne GUI (Begrenzung, ungueltige Eingaben, Stimmenmenge je Modell):
  14 von 14 bestanden, je Datei einzeln ausgefuehrt
- E2E gegen die echte API ueber `_synthesize_chunk_to_wav` (Linux-Variante, Streaming-Pfad):
  Dauer skaliert wie oben gemessen
- Kein Rueckfall auf den Nicht-Streaming-Pfad — `speed` wird auch beim Streaming akzeptiert
- Der Synthese-Pfad beider Dateien ist nach dem Nachziehen zeichengleich, daher wurde der
  kostenpflichtige E2E-Lauf nicht fuer beide Dateien wiederholt

## Offener Punkt

Das Tempo wirkt erst ab dem naechsten synthetisierten Abschnitt; bereits erzeugte
Audiodateien behalten ihr Tempo. Eine Neusynthese laufender Abschnitte ist nicht vorgesehen.
