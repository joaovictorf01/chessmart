# Unreleased

Versioning follows [Semantic Versioning](https://semver.org/): a patch release (1.1.x) only fixes; a minor release (1.x.0) adds features; a major release changes what existing users rely on. The version is decided when the release is cut, from what this section holds.

## Added

- **NVDA+Alt+X** opens Tactics from anywhere. Scripts for a random puzzle, Endgames, My Study and New Game are in the Input Gestures dialog, under Chessmart, with no default key.

## To do

- Puzzle download: accept a `.db.gz` downloaded by hand in the browser (for machines that cannot reach GitHub from the add-on); log the exact error when the manifest cannot be fetched. First report: 21-09-2026, "could not reach the download server".

## Fixed

- Puzzle download dialog: the first status says to wait for the list; if the list cannot be fetched, the button becomes **Try again** instead of leaving everything disabled.
- README: the submenu is under NVDA menu > Tools.

# Chessmart 1.1.0

- **Endgames...** in the menu. Five mate drills against the engine at full strength: queen, rook, two rooks (the ladder), two bishops, and bishop and knight against a bare king. The book position opens each drill; Control+N draws a random one (two bishops always on opposite colours). Optional clock; at the end the board counts the moves against the target (under 10, 20 or 35) and names a stalemate for what it is.
- King and pawn against king as a drill too: with the tablebases installed, Control+N draws a pawn of any file, rook pawns included, and only positions the tablebase calls won. Without them, the four checked examples.
- Nine endgame lessons that follow the order of the endgame courses (Silman's *Complete Endgame Course*; De la Villa's *100 Endgames You Must Know*): the king and the opposition; king and pawn against king (rule of the square, king in front, pawn on the sixth); a piece against a pawn; pawns on both sides; rook and pawn against rook (Philidor, the passive rook, Lucena); queen against a pawn on the seventh; bishop and rook pawn; and the rook endings that decide games (the short side, Vancura, the back-rank defence, the rule of five, the rook behind the passed pawn), each with its right and wrong version. Forty positions, every one checked against the Syzygy tablebase before it went in. Each position asks win, draw or loss for your side, tells the rule, and is then played out against the engine; Backspace takes a move back, Control+N goes to the next position.
- Syzygy tablebases (3 to 5 pieces, WDL and DTZ) downloaded file by file from the Lichess mirror, checked by SHA-256, resumable. With them installed the board judges every move of the player in a drill or lesson ("that move let the win slip"), Control+T says the theoretical result and how many moves to the next irreversible move, Control+Shift+T the moves that keep the result. Help from the tablebase counts as practice, not as a held result.
- Every drill and lesson attempt is recorded in the player's history (`tactic.db`): answer, whether the result was held, moves, time, and the starting position. The Endgames dialog shows how many times in a row each position was held; three in a row without help makes it firm.
- **My Study...** in the menu: how much and how you studied, by day (tactics: puzzles, solved, minutes; endgames: positions, held, minutes; totals for today, 7 or 30 days), and how far the endgame lessons go: which positions are firm, which are pending, and where you are. One text, copyable to the clipboard.
- Tactics: Control+N in the middle of a puzzle now asks for a second press and names the puzzle ("Press Control+N twice to skip tactic X"); the skipped id is also written to the NVDA log. A finished puzzle still moves on with one press.
- Spanish translation (first pass, theme names from the official Lichess translation; native review welcome). The changelog in the add-on store is now translated too.

# Chessmart 1.0.2

- Escape asks before leaving a game in progress: "No, keep playing" or "Yes, leave". It used to close the board at once, and the closed board kept the engine running, the clock ticking and an online game open on Lichess. Leaving now shuts the engine down, resigns (or aborts, in the first two moves) the online game and frees the window.
- A puzzle you have not touched (no move, no mistake, no hint) is no longer counted as a failure when you move on or leave.
- Online games: the board no longer raises an error when the game starts (it called a method the window never had); the clock shown is the server's. A draw offer from the opponent now opens the accept/decline menu and the answer reaches the server; a resignation names the right side; a move the server refuses is announced instead of crashing; the game stream reconnects after an error, as it was meant to.
- Challenge levels renamed so the list says what they are: beginner, intermediate, advanced, hard and adaptive, each spoken with its rating range. Saved settings with the old names keep working.
- Puzzle themes have real names and descriptions ("Mate in one", "Attack on f2 or f7", "Smothered mate") instead of the raw Lichess tags split on capitals ("Mate In1", "Attacking F2 F7", "Super G M"); the theme picker reads the description with each theme.
- Training plans name the motifs they cover.
- Internal: typed database layer, single source of truth for the training setup, unit tests for the database access, the rating and the trainer rules.

# Chessmart 1.0.1

- The complete puzzle database (about 620 MB) is now published and downloaded in parts of 300 MB: GitHub refuses to store a single asset that large. Each part is verified as it arrives, a part that fails is retried on its own, and the whole file is verified at the end. Older manifests without parts keep working.
- Unit tests for the download and the move notation now run in CI.

# Chessmart 1.0.0

First public release of the tactics trainer built on Musharraf Omer's Chessmart.

- Lichess puzzle database downloaded on demand from the add-on (light, 76 MB, or complete, 591 MB), regenerated every month from the Lichess open database and offered as an update, never installed automatically.
- Player history (attempts, Glicko-2 rating, evolution) kept in its own file, untouched by database updates.
- Adaptive challenge level that follows your tactics rating; training plans by theme; puzzle by id.
- Next puzzle drawn in the background and theme catalog built in the background: the screen reader never waits.
- Move notation configurable in the settings: descriptive, SAN, UCI, literate, NATO and anna (the names blind players use at the board).
- Runs on NVDA 2026.1 and later (64-bit Python 3.13) without any Python installed on the machine.
- Brazilian Portuguese translation.
