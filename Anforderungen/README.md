# Anforderungen

Anforderungsdokumente dieses Repositories — ein Dokument je App bzw. Feature.

## Nummerierung

- **Format**: `R` + 5 Ziffern mit fuehrenden Nullen — z.B. `R00042`
- **Dateiname**: `RXXXXX-kebab-case-zusammenfassung.md`
- Nummern werden fortlaufend um 1 erhoeht, Luecken werden nicht wiederverwendet

## Status-Werte

| Status | Bedeutung |
|---|---|
| `Neu` | Erfasst, noch nicht in Umsetzung |
| `In Arbeit` | Umsetzung laeuft |
| `Erledigt` | Umgesetzt und verifiziert |

## Konvention

Anforderungsdateien sind feste Vorgaben und werden nach Erstellung nicht mehr veraendert.

## Bestand

| ID | Titel | Status | App |
|---|---|---|---|
| [R00001](R00001-tts-player.md) | TTS-Player (plattformuebergreifend) | Erledigt | `Apps/tts-player.py` |
| [R00002](R00002-tts-player-linux.md) | TTS-Player Linux-Variante | Erledigt | `Apps/tts-player-linux.py` |
