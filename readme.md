# Chessmart

**Chessmart** is an NVDA add-on that turns the screen reader into an accessible chess environment: a virtual board you play on with the keyboard, an engine to play against, PGN replay, and a tactics trainer built on the [Lichess puzzle database](https://database.lichess.org/#puzzles) with a rating that follows you.

It is a fork of [Chessmart by Musharraf Omer](https://github.com/blindpandas/chessmart), which provides the board, the engines and the variants. This fork adds the tactics trainer, the puzzle database download, the configurable move notation and the translations. Both are released under the GNU GPL v2.

Requires NVDA 2026.1 or later (64-bit Python 3.13). Nothing else needs to be installed: the SQLite runtime the trainer needs ships inside the add-on.

## Getting started

1. Install the add-on and restart NVDA.
2. Open the NVDA menu and find the **Chessmart** submenu.
3. Choose **Tactics...** to train, **Endgames...** for the endgame lessons, **My Study...** to see how far you have come, or **New Game...** to play.

The first time you open Tactics, the add-on offers to download the puzzle database. Pick **Light** (about 76 MB, 745,000 puzzles that many players have solved and approved) or **Complete** (about 591 MB, the whole Lichess base of 5.8 million puzzles). The download runs in the background with spoken progress; you can cancel with Escape. The database is stored in your NVDA configuration folder, under `chessmart`, together with your training history.

## Tactics training

The **Tactics** dialog sets up a session:

* **Training plan** — which themes are in play: fundamentals (mate, fork, pin and skewer), win material, attack the king, mixed motifs, all themes, or your own selection of Lichess themes.
* **Challenge level** — how hard the puzzles are, with the rating range spoken in the list: beginner (up to 1100), intermediate (900 to 1500), advanced (1200 to 1900), hard (1600 and above), or **adaptive**, which follows your own tactics rating.
* **Puzzle ID** — type the id of one Lichess puzzle to open exactly that one.
* **Save training setup as default** — keeps this setup for next time.

Each puzzle is presented on the board with the opponent's last move already played. Find the move, navigate to the piece, press Enter, navigate to the destination square and press Enter again. Multi-move puzzles continue until the end of the solution; the opponent's replies are announced.

### Rating

Every puzzle you attempt counts as a rated game against that puzzle, using the Glicko-2 system (the same family Lichess uses). Your rating starts at 1500 with a large uncertainty and settles as you play. As on Lichess, the first wrong move already counts as a failure: solving the puzzle afterwards teaches you the solution but does not change the rating, and retrying a puzzle is never rated.

The rating, the attempts and their history live in `tactic.db` in your NVDA configuration folder. Database updates never touch that file.

### Keyboard commands on the puzzle board

| Key | Action |
|---|---|
| Control+N | Next puzzle (drawn in the background while you solve the current one) |
| Control+R | Retry the current puzzle (not rated) |
| Control+H | Hint: first the themes, then the origin square, then the destination |
| Control+Enter (twice) | Play the expected move |
| Control+F1 | Puzzle details: rating, popularity, themes, source game |
| Control+F2 | Session status: solved, mistakes, hints |
| Control+Shift+R | Your current tactics rating |
| Tab / Shift+Tab | Training actions (next, retry, back to board) |
| Escape | Leave training. It asks first; a puzzle you have not touched is not counted |

All the board commands below work on the puzzle board too.

### Keeping the database up to date

Lichess publishes a new puzzle base every month. This project regenerates the databases from it and publishes them on the [`puzzles-latest` release](https://github.com/joaovictorf01/chessmart/releases/tag/puzzles-latest). In the Tactics dialog or in the settings, **Download or update...** shows what you have installed against what is published and lets you update. Updates are never installed automatically.

## Endgames

**Endgames...** is the endgame trainer. It follows the order of the endgame courses (Silman's *Complete Endgame Course*, Parts 1 to 4, and De la Villa's *100 Endgames You Must Know*), and every position is a theoretical one: known result, known method, checked against the Syzygy tablebases.

* **Lessons 1a and 1b** are the mate drills: queen and king, then rook and king, against a bare king, played against the engine at full strength. The first position is Capablanca's example; **Control+N** opens a random one. An optional clock can be set for records; by default there is none. At the end the board says how many moves the mate took and whether it fit the target (under 10 with the queen, under 20 with the rook), and names a stalemate for what it is.
* **Lessons 2 to 8** are the ideas: the king and the opposition; king and pawn against king (rule of the square, king in front, pawn on the sixth); a piece against a pawn; pawns on both sides; rook and pawn against rook (Philidor, the passive rook, Lucena); queen against a pawn on the seventh; bishop and rook pawn. Each position is set up on the board and asks **win, draw or loss** for your side. Answer, and the board says whether you were right and speaks the rule. Then you play the position out against the engine: win it, or hold the draw. Lost positions are only the question and the rule.

### The tablebase judge

**Download tablebases...** in the Endgames dialog fetches the Syzygy tables (3 to 5 pieces, WDL and DTZ, 984 MB; or up to 4 pieces, 4 MB) file by file from the Lichess mirror, checking each one by SHA-256; a cancelled download resumes where it stopped. With the tables installed, in any drill or lesson the board judges every move you make: a move that turns a win into a draw, or a draw into a loss, is announced at once, and **Backspace** takes it back in a lesson. **Control+T** says the theoretical result of the position and how many moves to the next irreversible move (pawn move, capture or mate); **Control+Shift+T** names the moves that keep the result.

Every attempt is recorded in your history (`tactic.db`): the answer, whether the result was held without a slip, moves and time. The dialog shows how many times in a row each position was held.

### My study

**My Study...** reads the same history and tells you how much and how you studied: by day, the tactics (puzzles, solved, minutes) and the endgames (positions, held, minutes) with the day's total, for today, the last 7 or the last 30 days; and how far the endgame lessons go, lesson by lesson: which positions are firm (held three times in a row, question right and result kept without a slip), which are pending, and where you are. **Copy to clipboard** puts the whole text in the clipboard. Games are not counted here on purpose: real games are played elsewhere.

### Keyboard commands on the endgame board

| Key | Action |
|---|---|
| Tab / Shift+Tab | The actions bar: goal or rule, verdict, best moves, take back, next position |
| Control+F1 | Repeat the goal (drill) or the rule (lesson) |
| Control+N | Another position of the drill, or the next position of the lesson |
| Control+R | The same lesson position again |
| Backspace | Take back your last move (lessons) |
| Control+T | The tablebase verdict for the position |
| Control+Shift+T | The moves that keep the result |
| Escape | Leave. During a game it asks first |

All the board commands below work here too.

## Playing a game

**New Game...** opens the game setup:

* **Play mode**: human versus computer, or human versus human on the same keyboard.
* **Variant**: standard chess, Chess 960, Antichess, Atomic, King of the hill, Racing kings, Horde, Three check and Crazyhouse.
* **Time control**: classical, rapid, blitz, bullet or custom (for example `10+5`).
* **Starting FEN**: any position.
* **Engine options**: strength (Elo) and thinking time, when playing the computer. Standard chess uses Stockfish 14; variants use Fairy-Stockfish.

**Replay PGN File...** opens a PGN file: Enter plays the next move of the game and Backspace takes it back, while the arrow keys let you inspect the board at any point.

### Keyboard commands on the board

| Key | Action |
|---|---|
| Arrow keys | Move between squares; each square announces its piece and name |
| Enter or Space | Select the piece to move, then the destination square |
| R, N, B, Q, K, P | Jump to your next rook, knight, bishop, queen, king or pawn |
| Shift + letter | Jump to the opponent's next piece of that type |
| A | Which pieces attack the focused square |
| M | Material count for both sides |
| F1 / Shift+F1 | Overview of your pieces / of the opponent's pieces |
| F2 / Shift+F2 | Remaining time on your clock / on the opponent's clock |
| F3 | The focused square and piece in IBCA notation |
| F4 | Score sheet: the moves played so far |
| F6 / Shift+F6 | Your pocket / the opponent's pocket (Crazyhouse) |
| Control+D | Offer a draw, or withdraw the offer |
| Control+Shift+R | Resign (online games) |
| Control+S | Save the game as a PGN file |
| Control+Shift+S | Save the board as a PNG image |
| Escape | Close the board. During a game it asks first: leaving abandons the game against the engine and resigns (or aborts, in the first moves) an online game |

## Settings

**Settings...** in the Chessmart menu:

* Default training plan, challenge level and themes for new tactics sessions.
* The puzzle database in use, with **Browse...** to point at a database elsewhere and **Download or update...**.
* **Move notation**: how moves and squares are spoken.

### Move notation

The same styles as the blind mode of Lichess, plus the descriptive style Chessmart always had:

| Style | Example |
|---|---|
| Descriptive | white knight from g1 to f3 |
| SAN | Nf3 |
| UCI | g1f3 |
| Literate | knight f 3 |
| NATO | knight foxtrot 3 |
| Anna | knight felix 3 |

Anna is the notation blind players use at the board (anna, bella, cesar, david, eva, felix, gustav, hector). In the NATO and Anna styles the squares are spoken the same way when you move around the board. Only the speech changes: moves are always entered on the board, never typed.

## Translations

The interface is in English and Brazilian Portuguese. Translations live in `addon/locale/<language>/LC_MESSAGES/nvda.po`, in the standard NVDA add-on layout, and are welcome: to start a new one, run `py -3 tools/i18n.py update <language>` and fill in the `msgstr` lines, or ask for the add-on to be added to the NVDA add-ons project on Crowdin. The NATO and Anna square names and the IBCA notation are international and are not translated.

## For developers

The repository follows the [NVDA add-on template](https://github.com/nvaccess/addonTemplate): `uv sync` then `uv run scons` builds `chessmart-<version>.nvda-addon`; pushing a `v*` tag builds and publishes a GitHub release. `tools/build_puzzles.py` regenerates the puzzle databases from the Lichess CSV, and `.github/workflows/puzzles.yml` does it monthly.

### Where things live

Everything is under `addon/globalPlugins/chessmart/`. Read it in this order:

* `tactic/` — the data layer, pure Python with no NVDA imports. `store.py` talks to the two SQLite files (`puzzles.db`, the Lichess base; `tactic.db`, the player's history) and returns the dataclasses in `models.py`; `glicko2.py` is the rating maths; `repository.py` is the facade the rest of the add-on calls; `download.py` fetches the database. This package is type-checked with pyright and covered by unit tests.
* `trainer.py`, `theme_names.py`, `theme_catalog.py` — the rules: training plans, challenge levels, the name and description of every Lichess theme. Also pure Python.
* `training_session.py` — one training session: the options the user chose (`TrainingOptions`) and the puzzle sequence (`TrainingSession`), with prefetch of the next puzzle.
* `virtual_chessboard/` — the boards the screen reader user navigates: `base.py` (squares, moves, speech), `user_driven.py` (drag and drop of pieces), `user_engine.py` (against Stockfish), `user_user.py`, `internet_chessboard.py` (Lichess), `pgn_player.py`, `puzzle_board.py` (the trainer).
* `graphical_interface/` — the wx dialogs: new game, tactics session, settings, download.
* `chessboard.py` is the wx window that hosts a board; `__init__.py` is the NVDA plugin and menu; `addon_config.py`, `notation.py`, `spoken_messages.py`, `signals.py`, `concurrency.py`, `paths.py`, `sounds.py` and `speaking.py` are the small shared pieces their names say.

Tests run with `uv run python -m unittest discover -s tests`; they stub the NVDA modules they need and never touch the user's history. `uv run pyright` type-checks the add-on (basic mode); it resolves NVDA's own modules from a checkout of [nvaccess/nvda](https://github.com/nvaccess/nvda) cloned next to this repository (`../nvda`), and the bundled libraries from `lib/`. User-visible text goes through `_()` (or `N_()` for constants translated later) with a `# Translators:` comment, and `py -3 tools/i18n.py update pt_BR` refreshes the catalog.

## Credits

* [Musharraf Omer](https://github.com/mush42) — the original Chessmart: board, engines, variants, PGN replay.
* [Lichess](https://lichess.org) — the puzzle database (CC0) and the notation styles of its blind mode.
* [Stockfish](https://stockfishchess.org) and [Fairy-Stockfish](https://fairy-stockfish.github.io) — the engines.
* [python-chess](https://python-chess.readthedocs.io) — the chess library.
* Tactics trainer, database tooling, move notation and Portuguese translation by João Victor.
