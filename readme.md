# Chessmart

**Chessmart** is an NVDA add-on that turns the screen reader into an accessible chess environment: a virtual board you play on with the keyboard, an engine to play against, PGN replay, and a tactics trainer built on the [Lichess puzzle database](https://database.lichess.org/#puzzles) with a rating that follows you.

It is a fork of [Chessmart by Musharraf Omer](https://github.com/blindpandas/chessmart), which provides the board, the engines and the variants. This fork adds the tactics trainer, the puzzle database download, the configurable move notation and the translations. Both are released under the GNU GPL v2.

Requires NVDA 2026.1 or later (64-bit Python 3.13). Nothing else needs to be installed: the SQLite runtime the trainer needs ships inside the add-on.

## Getting started

1. Install the add-on and restart NVDA.
2. Open the NVDA menu (NVDA+N), go to **Tools** and find the **Chessmart** submenu.
3. Choose **Tactics...** to train, **Endgames...** for the endgame lessons, **My Study...** to see how far you have come, or **New Game...** to play.
4. **NVDA+Alt+X** opens Tactics from anywhere. Shortcuts for a random puzzle, Endgames, My Study, My Games and New Game have no key by default: assign them in NVDA's Input Gestures dialog, under the Chessmart category.

The first time you open Tactics, the add-on offers to download the puzzle database. Pick **Light** (about 90 MB, the puzzles many players have solved and approved -- around 880,000 of them) or **Complete** (about 600 MB, the whole Lichess base, over 6 million). The download dialog gives the exact size and puzzle count of each, which grow a little every month as Lichess publishes a new base. The download runs in the background with spoken progress; you can cancel with Escape. The database is stored in your NVDA configuration folder, under `chessmart`, together with your training history.

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

### Reviewing the puzzles you missed

A puzzle you missed -- a wrong move, a hint, or the solution played with Control+Enter -- comes back the next day. When a tactics session opens and reviews are due, they come first: up to 3, the oldest first, whatever the training plan and level. Each is announced as a review and is never rated: you have seen the solution once, so a rating for it would measure memory, not tactics.

A clean review (every move found, no hint) brings the puzzle back once more, three days later. The second clean review in a row makes it firm and it leaves the queue. A review with a slip starts over: back the next day.

Control+N or Next puzzle during a review asks whether to skip the reviews, with No as the default; Yes goes straight to new puzzles, and the skipped ones stay due. Control+F2 counts the session's clean reviews apart from the new puzzles, and My Study shows the queue.

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

* **Lessons 1a to 1e** are the mate drills: queen and king, rook and king, two rooks (the ladder), two bishops, and bishop and knight, against a bare king, played against the engine at full strength. The first position is the book example; **Control+N** opens a random one (two bishops always land on opposite colours; with the tablebases installed, king and pawn draws a pawn of any file, rook pawns included, and only positions the tablebase calls won). An optional clock can be set for records; by default there is none. At the end the board says how many moves the mate took and whether it fit the target (under 10 with the queen or two rooks, under 20 with the rook or two bishops, under 35 with bishop and knight), and names a stalemate for what it is.
* **Lessons 2 to 9** are the ideas: the king and the opposition; king and pawn against king (rule of the square, king in front, pawn on the sixth); a piece against a pawn; pawns on both sides; rook and pawn against rook (Philidor, the passive rook, Lucena); queen against a pawn on the seventh; bishop and rook pawn; and the rook endings that decide games (the short side, Vancura, the back-rank defence, the rule of five, the rook behind the passed pawn), each with its right and wrong version. Every position is checked against the Syzygy tablebase before it goes in. Each position is set up on the board and asks **win, draw or loss** for your side. Answer, and the board says whether you were right and speaks the rule. Then you play the position out against the engine: win it, or hold the draw. Lost positions are only the question and the rule.

### The tablebase judge

**Download tablebases...** in the Endgames dialog fetches the Syzygy tables (3 to 5 pieces, WDL and DTZ, 984 MB; or up to 4 pieces, 4 MB) file by file from the Lichess mirror, checking each one by SHA-256; a cancelled download resumes where it stopped. With the tables installed, in any drill or lesson the board judges every move you make: a move that turns a win into a draw, or a draw into a loss, is announced at once, and **Backspace** takes it back in a lesson. **Control+T** says the theoretical result of the position and how many moves to the next irreversible move (pawn move, capture or mate); **Control+Shift+T** names the moves that keep the result.

Every attempt is recorded in your history (`tactic.db`): the starting position and the moves, the answer, whether the result was held without a slip, how many hints were asked, moves and time. The dialog shows how many times in a row each position was held; an attempt with hints counts as practice, not as held.

### My study

**My Study...** reads the same history and tells you how much and how you studied: by day, the tactics (puzzles, solved, minutes) and the endgames (positions, held, minutes) and the reviews of missed puzzles (how many, how many clean) with the day's total, for today, the last 7 or the last 30 days; and how far the endgame lessons go, lesson by lesson: which positions are firm (held three times in a row, question right and result kept without a slip), which are pending, and where you are; and the review queue: how many missed puzzles are due today, how many wait for their day, and how many are firm. **Copy to clipboard** puts the whole text in the clipboard. Games are not counted here on purpose: real games are played elsewhere.

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
* **Engine options**: strength (Elo) and thinking time, when playing the computer. Standard chess uses Stockfish 16 (the official 64-bit build); variants use Fairy-Stockfish.

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
| Control+S | Save the game as a PGN file |
| Control+Shift+S | Save the board as a PNG image |
| Escape | Close the board. During a game it asks first: leaving abandons the game against the engine |

## Record and Analyse a Game

**Record and Analyse Game** opens an empty board where you enter a game move by move, both sides from the keyboard — a game you played over the board, following it on your tactile set, or any game you want to study. **Analyse PGN File...** opens a saved game on the same board, variations and comments included.

Nothing ends the session: a checkmate inside a variation is only a position. Wherever the line already continues, a different move starts a **variation**; you can come back to the main line at any time. Each move can carry a **comment** (what you were thinking, what you missed) and a **mark**: ! good move, ? mistake, !! brilliant, ?? blunder, !? interesting, ?! dubious. The marks are spoken in words.

**Control+S** saves. The first time, a new game asks for the players, the event, the date and the result, and goes to your **games folder** (Settings; by default `Documents\Chessmart`) as `year-month-day_White-vs-Black.pgn`. After that, and for a game opened from a file with a single game or imported from Lichess, Control+S saves to that file without asking. **Control+Alt+S** opens the details (players, event, date, result) at any time, and saves.

Once the game has a file, every change -- a move, a comment, a mark, a line added by the engine -- is saved by itself, so nothing is lost if you close the board or NVDA. Settings, "Save analysed games automatically", turns this off; then Control+S saves and Escape asks before leaving unsaved changes.

### My games

**My Games...** lists every game in your games folder, the most recently changed first: the date, the players, the result, and how much you have annotated it ("Comments: 12, marks: 4, variations: 2", or "No notes"). Enter opens the game on the analysis board, where it keeps saving to its own file. A file with several games shows each of them; a game opened out of such a file is saved as a new file. The shortcut has no key by default: assign one in Input Gestures, under Chessmart.

### Game review

**F7** on the analysis board (or Tab, "Review the game") reviews the whole game: the engine evaluates every position of the main line (about a second each; F7 again stops; progress follows NVDA's "Progress bar output" setting, beeps by default), judges each move with Lichess's rules, and says each player's accuracy, computed as Lichess does ("Your accuracy 96 percent, opponent 87."), then the critical moments: "3 critical moments: move 14, mistake; move 22, inaccuracy; move 31, blunder." **Alt+Page Down** and **Alt+Page Up** go from one to the next. Each opens on the position before the move, so the better move is looked for there: play a candidate and Shift+E judges it.

Settings, "Game review", or "Review options..." in the analysis board's Tab bar, decide how much the engine says: whose moves (only yours, the side at the bottom of the board, or both); what counts (blunders only; mistakes and blunders; everything); how many moments at most (3, 5, 10 or all, keeping the worst); what the engine reveals (by default only where the move went wrong; or also its move; or its move and its line as a variation); the time per position; and whether opening theory is skipped. The review marks a critical move with its verdict only when you left the move unmarked: your own marks are never changed.

### Import a Lichess game

**Import Lichess Game...** offers the Lichess link on the clipboard, if there is one (in the browser, Control+L then Control+C copies it), and otherwise asks for a game link, a game code, or a Lichess username (that player's last game; the name is remembered for next time). The game is saved in the games folder as `year-month-day_White-vs-Black_lichess-code.pgn` and opens on the analysis board, from Black's side when the remembered user played Black. Importing the same game again opens your saved copy, with your notes, instead of downloading over it. Lichess's own evaluations are left out: the engine answers you, it does not speak first.

Every move carries its clock: moving through the game says the time left and the time the move took ("clock 0:48, took 0:12, under a minute"). **T** sums up the clock for both sides: from which move a player was under a minute, the lowest clock, the longest think.

### Import a Lichess game

**Import Lichess Game...** asks for a game link, a game code, or a Lichess username (that player's last game; the name is remembered for next time). The game is saved in the games folder as `year-month-day_White-vs-Black_lichess-code.pgn` and opens on the analysis board, from Black's side when the remembered user played Black. Importing the same game again opens your saved copy, with your notes, instead of downloading over it. Lichess's own evaluations are left out: the engine answers you, it does not speak first.

Every move carries its clock: moving through the game says the time left and the time the move took ("clock 0:48, took 0:12, under a minute"). **T** sums up the clock for both sides: from which move a player was under a minute, the lowest clock, the longest think.

### Engine analysis

The engine is Stockfish 16. An evaluation is said the way players say it: "white slightly better, plus 0.4" (a pawn is 1.0). Shift+E judges a move the way Lichess does: the evaluation becomes a winning chance from 0 to 100, and the move is an inaccuracy when it gives away 5 points of it, a mistake at 10, a blunder at 15. That is why losing a pawn in a level position is an inaccuracy, while losing one with a rook up is nothing. The suggested mark is only a suggestion: the mark stays yours.

Opening names come from Lichess ([lichess-org/chess-openings](https://github.com/lichess-org/chess-openings), public domain), looked up by position, so a transposition is recognised too. A move that reaches a new named opening says its name, the first move out of the table says "out of theory", Shift+E on a theory move says so instead of asking the engine, and saving writes the ECO and Opening tags.

Your own variations have no limit: calculate until you can say how the position stands, and stop there. The engine's line added with Control+E stops at 8 half-moves, enough to see the idea.

### Keyboard commands on the analysis board

The commands of the game board work here too (arrows, Enter, A, M, F1, F4...). On top of them:

| Key | Action |
|---|---|
| Alt+Left / Alt+Right | Back / forward one move along the current line |
| Alt+Home / Alt+End | Start of the game / end of the current line |
| Alt+Up | Leave the variation: back to the position where it branched off |
| Alt+Down | The moves recorded from this position: the continuation and its variations |
| Backspace | Take back the last move of a line, to fix a move entered by mistake |
| C / Shift+C | Write / read the comment of the current move |
| Control+1 to Control+6 | Mark the move: ! ? !! ?? !? ?! |
| Control+0 | Remove the mark |
| Control+P | Make the current variation the main line |
| Control+S | Save (a new game asks for its details the first time) |
| Control+Alt+S | Edit the players, event, date and result, and save |
| E | With five pieces or fewer and the tablebases installed (Endgames, Download tablebases): the exact result and the moves that keep it, instead of the engine. Otherwise the engine evaluation: who is better and by how much, the best move with its line, and two other candidates. Press twice to let the engine think 8 seconds instead of 2 |
| X | The threat, as on Lichess: what the other side would play if it were its move, with the evaluation and the line. Not in check (the threat is already there) |
| Shift+E | Review the move that led here against the engine's best: the engine's move, good, inaccuracy, mistake or blunder, and the mark that suggests |
| Control+E | After E, add the engine's line (up to 8 half-moves) as a variation, with the evaluation as its comment |
| F7 | Review the whole game; F7 again stops |
| Alt+Page Down / Alt+Page Up | Next / previous critical moment of the review |
| T | The clock of the game, for both sides (imported games) |
| T | The clock of the game, for both sides (imported games) |
| O | The opening the line is in, with its ECO code, and whether the position is still theory |
| Tab, "Play from here against the computer..." | The New Game dialog with this position as the start and its side to move as yours: choose the engine strength and the clock |
| Tab / Shift+Tab | All these actions as a bar, each with its key: for when a key is forgotten. Also flips the board |
| Control+S | Save the game in the games folder |
| Escape | Close the board; if something changed since the last save, it asks first |

## Board Editor

**Board Editor** opens an empty board to set up any position square by square. The piece letters place pieces, as in FEN: **Shift+K, Q, R, B, N, P** for a white king, queen, rook, bishop, knight or pawn, the letter alone for a black one. **Delete** or **Backspace** empties the square; **Enter** says what is on it. **Control+C** copies the position as FEN, **Control+V** takes one from the clipboard.

**Tab** opens the editor's actions: switch whose move it is; switch each castling right (a right exists only while its king and rook stand on their starting squares); check the position, which says in words what is wrong ("There is no black king.", "A pawn stands on the first or the eighth rank.", "The side that is not to move is in check.") or that it is valid; analyse the position on the analysis board; the starting position; clear the board; flip it. "Analyse this position" opens it on the analysis board, where "Play from here against the computer..." in the Tab bar starts a game from it.

## Settings

**Settings...** in the Chessmart menu:

* Default training plan, challenge level and themes for new tactics sessions.
* The puzzle database in use, with **Browse...** to point at a database elsewhere and **Download or update...**.
* **Move notation**: how moves and squares are spoken.
* **Games folder**: where the analysis board saves games.

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
* `puzzle_attempt.py`, `board_geometry.py`, `game_tree.py`, `engine_eval.py`, `openings/` — more rules free of NVDA, each with its test file: what counts in a puzzle attempt and in the session; square colours, arrow-key neighbours and the material count; the analysis tree (variations, comments, marks, the PGN written); what the engine's numbers mean (Lichess's winning-chance thresholds); opening names by position.
* `training_session.py` — one training session: the options the user chose (`TrainingOptions`) and the puzzle sequence (`TrainingSession`), with prefetch of the next puzzle.
* `virtual_chessboard/` — the boards the screen reader user navigates: `base.py` (squares, moves, speech), `user_driven.py` (drag and drop of pieces), `user_engine.py` (against Stockfish), `user_user.py`, `internet_chessboard.py` (Lichess), `pgn_player.py`, `puzzle_board.py` (the trainer), `analysis_board.py` (recording and analysis, over the tree in `game_tree.py`).
* `virtual_chessboard/actions_bar.py` is the Tab bar shared by the puzzle, endgame and analysis boards; `virtual_chessboard/analysis_engine.py` runs Stockfish for the analysis board.
* `graphical_interface/` — the wx dialogs: new game, tactics session, settings, the two downloads (sharing `download_base.py`), saving an analysed game.
* `chessboard.py` is the wx window that hosts a board; `__init__.py` is the NVDA plugin and menu; `addon_config.py`, `notation.py`, `spoken_messages.py`, `signals.py`, `concurrency.py`, `paths.py`, `sounds.py` and `speaking.py` are the small shared pieces their names say.

Tests run with `uv run python -m unittest discover -s tests`; they stub the NVDA modules they need and never touch the user's history. `uv run pyright` type-checks the add-on (basic mode); it resolves NVDA's own modules from a checkout of [nvaccess/nvda](https://github.com/nvaccess/nvda) cloned next to this repository (`../nvda`), and the bundled libraries from `lib/`. User-visible text goes through `_()` (or `N_()` for constants translated later) with a `# Translators:` comment, and `py -3 tools/i18n.py update pt_BR` refreshes the catalog.

## Credits

* [Musharraf Omer](https://github.com/mush42) — the original Chessmart: board, engines, variants, PGN replay.
* [Lichess](https://lichess.org) — the puzzle database (CC0) and the notation styles of its blind mode.
* [Stockfish](https://stockfishchess.org) and [Fairy-Stockfish](https://fairy-stockfish.github.io) — the engines.
* [python-chess](https://python-chess.readthedocs.io) — the chess library.
* Tactics trainer, database tooling, move notation and Portuguese translation by João Victor.
