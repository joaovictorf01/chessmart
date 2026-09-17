# Chessmart 1.0.0

First public release of the tactics trainer built on Musharraf Omer's Chessmart.

- Lichess puzzle database downloaded on demand from the add-on (light, 76 MB, or complete, 591 MB), regenerated every month from the Lichess open database and offered as an update, never installed automatically.
- Player history (attempts, Glicko-2 rating, evolution) kept in its own file, untouched by database updates.
- Adaptive challenge level that follows your tactics rating; training plans by theme; puzzle by id.
- Next puzzle drawn in the background and theme catalog built in the background: the screen reader never waits.
- Move notation configurable in the settings: descriptive, SAN, UCI, literate, NATO and anna (the names blind players use at the board).
- Runs on NVDA 2026.1 and later (64-bit Python 3.13) without any Python installed on the machine.
- Brazilian Portuguese translation.
