# Chessmart

* Authors: João Victor; original add-on by Musharraf Omer
* Compatibility: NVDA 2026.1 or later
* Download: [Chessmart releases on GitHub](https://github.com/joaovictorf01/chessmart/releases) (the NVDA Add-on Store once it is published there)
* Source code: [the Chessmart repository on GitHub](https://github.com/joaovictorf01/chessmart)
* License: GNU GPL v2

**Chessmart** is an NVDA add-on that turns the screen reader into an accessible chess environment, all from the keyboard and all spoken:

* a tactics trainer built on the [Lichess puzzle database](https://database.lichess.org/#puzzles), with a rating that follows you and the puzzles you missed coming back for review;
* endgame mate drills and lessons, judged move by move by the Syzygy tablebases;
* an analysis board to record, annotate and analyse your games with Stockfish 16: variations, comments, marks, opening names, a review of the whole game, and games imported from Lichess;
* a board editor to set up any position;
* games against the engine or a friend on the same keyboard, in standard chess and eight variants, and PGN replay;
* My Study, a record of how much and how you studied.

It is a fork of [Chessmart by Musharraf Omer](https://github.com/blindpandas/chessmart), which provides the board, the engines and the variants. Both are released under the GNU GPL v2.

Nothing else needs to be installed: the engines and the SQLite runtime the trainer needs ship inside the add-on (NVDA 2026.1 runs the 64-bit Python 3.13 they are built for).

What changed in each version: [the Chessmart changelog](https://github.com/joaovictorf01/chessmart/blob/main/changelog.md).

## Getting started

1. Install the add-on and restart NVDA.
2. Open the NVDA menu (NVDA+N), go to **Tools** and find the **Chessmart** submenu.
3. Choose what you want to do.

### The Chessmart menu

* **New Game...** — play against the computer or against a friend on the same keyboard (see "Playing a game").
* **Tactics...** — set up a tactics session and train (see "Tactics training").
* **Random Puzzle** — start a tactics session at once, with the training setup saved as default, without the dialog.
* **Endgames...** — the mate drills and the endgame lessons (see "Endgames").
* **My Study...** — how much and how you studied, and how far the lessons go (see "My Study").
* **Replay PGN File...** — replay a saved game move by move (see "Replaying a PGN file").
* **Record and Analyse Game** — enter a game move by move on the analysis board (see "Record and Analyse a Game").
* **Board Editor** — set up a position square by square (see "Board Editor").
* **Import Lichess Game...** — download a game from Lichess and open it on the analysis board (see "Import a Lichess game").
* **Analyse PGN File...** — open a saved game on the analysis board.
* **My Games...** — the games in your games folder (see "My games").
* **Settings...** — the Chessmart settings (see "Settings").

### Shortcuts

**NVDA+Alt+X** opens Tactics from anywhere. Random Puzzle, Endgames, My Study, My Games and New Game also have shortcuts, with no key by default: assign one in NVDA's Input Gestures dialog, Chessmart category.

### The puzzle database

The first time you open Tactics or Random Puzzle, the add-on offers to download the puzzle database. Pick **Light** (about 90 MB, the puzzles many players have solved and approved -- around 880,000 of them) or **Complete** (about 600 MB, the whole Lichess base, over 6 million). These figures are approximate: the download dialog gives the exact ones for each database, the puzzle count, the size to download and the size on disk, which grow a little every month as Lichess publishes a new base. The download runs in the background with spoken progress; you can cancel with Escape. The database is stored in your NVDA configuration folder, under `chessmart`, together with your training history.

### The Tab bar

The puzzle board, the endgame boards, the analysis board and the Board Editor each have a bar of actions, opened with **Tab** from the board. **Tab** lands on its first action and **Shift+Tab** on its last. Inside the bar, **Tab** and **Right arrow** go to the next action, **Shift+Tab** and **Left arrow** to the previous one, and **Enter** runs the focused action. **Escape**, the "Back to board" action, or going past either end of the bar returns to the board. The actions of each bar are listed with the commands of its board.

## Tactics training

The **Tactics** dialog sets up a session:

* **Tactics database** — the puzzle database in use, with **Browse...** to point at a database elsewhere and **Download or update...** (see "Keeping the database up to date").
* **Puzzle ID** — type the id of one Lichess puzzle to open exactly that one; the training plan and level are then ignored.
* **Training plan** — which themes are in play: fundamentals (mate, fork, pin and skewer), win material, attack the king, mixed motifs, all themes, or your own selection of Lichess themes.
* **Challenge level** — how hard the puzzles are, with the rating range spoken in the list: beginner (up to 1100), intermediate (900 to 1500), advanced (1200 to 1900), hard (1600 and above), or **adaptive**, which follows your own tactics rating.
* **Trainer summary** — a read-only text that sums up the chosen plan and level.
* **Themes** — the themes in play. With your own selection as the training plan, **Select themes...** opens the list of Lichess themes, each with its description and number of puzzles, and **Clear themes** empties the selection.
* **Save training setup as default** — keeps this setup for next time, and for Random Puzzle.

Each puzzle is presented on the board with the opponent's last move already played. Find the move, navigate to the piece, press Enter, navigate to the destination square and press Enter again. Multi-move puzzles continue until the end of the solution; the opponent's replies are announced.

**Random Puzzle** in the menu skips the dialog and opens a session with the setup saved as default.

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
| Control+N | Next puzzle (drawn in the background while you solve the current one). During a puzzle in progress, press it twice: the first press says "Press Control+N twice to skip". During a review it asks whether to skip the reviews |
| Control+R | Retry the current puzzle (not rated) |
| Control+H | Hint: first the themes, then the origin square, then the destination |
| Control+Enter (twice) | Play the expected move |
| Control+F1 | Puzzle details: the puzzle id, rating, popularity, number of plays, themes, opening tags, and whether the source game is available on Lichess |
| Control+F2 | Session status: solved, mistakes, hints |
| Control+Shift+R | Your current tactics rating |
| Tab / Shift+Tab | The training actions: Repeat instruction, Puzzle goal, Hint, Puzzle details, Session status, Restart puzzle, Next puzzle, Back to board |
| Escape | Leave training. It asks first; a puzzle you have not touched is not counted |

The commands of the game board (see "Keyboard commands on the board") work on the puzzle board too, except Control+D, which does nothing here, and F2 / Shift+F2, which say "No Time Control".

### Keeping the database up to date

Lichess publishes a new puzzle base every month. This project regenerates the databases from it and publishes them on the [`puzzles-latest` release](https://github.com/joaovictorf01/chessmart/releases/tag/puzzles-latest). In the Tactics dialog or in the settings, **Download or update...** shows what you have installed against what is published and lets you update. Updates are never installed automatically.

## Endgames

**Endgames...** is the endgame trainer. It follows the order of the endgame courses (Silman's *Complete Endgame Course*, Parts 1 to 4, and De la Villa's *100 Endgames You Must Know*), and every position is a theoretical one: known result, known method, checked against the Syzygy tablebases.

* **Lessons 1a to 1e** are the mate drills: queen and king, rook and king, two rooks (the ladder), two bishops, and bishop and knight, against a bare king, played against the engine at full strength. The first position is the book example; **Control+N** opens a random one (two bishops always land on opposite colours). An optional clock can be set for records; by default there is none. At the end the board says how many moves the mate took and whether it fit the target (under 10 with the queen or two rooks, under 20 with the rook or two bishops, under 35 with bishop and knight), and names a stalemate for what it is.
* **Lessons 2 to 9** are the ideas: the king and the opposition; king and pawn against king (rule of the square, king in front, pawn on the sixth); a piece against a pawn; pawns on both sides; rook and pawn against rook (Philidor, the passive rook, Lucena); queen against a pawn on the seventh; bishop and rook pawn; and the rook endings that decide games (the short side, Vancura, the back-rank defence, the rule of five, the rook behind the passed pawn), each with its right and wrong version. Every position is checked against the Syzygy tablebase before it goes in. Each position is set up on the board and asks **win, draw or loss** for your side. Answer, and the board says whether you were right and speaks the rule. Then you play the position out against the engine: win it, or hold the draw. Lost positions are only the question and the rule.

### The Endgames dialog

* **Lesson** — the lessons, in course order.
* **Position** — for a mate drill, "Capablanca's example" or "Random position"; for a lesson, its positions, each with how many times in a row you held it ("(3 in a row)") or "(not held yet)" once you have tried it.
* **About this lesson** — a read-only text: what the lesson teaches and its source.
* **Clock for the mate drills** — minutes+seconds (for example `5+0`), or empty for no clock. Only the mate drills use it.
* The tablebases installed, and **Download tablebases...** (see "The tablebase judge").

### The tablebase judge

**Download tablebases...** in the Endgames dialog fetches the Syzygy tables (3 to 5 pieces, WDL and DTZ, 984 MB; or up to 4 pieces, 4 MB) file by file from the Lichess mirror, checking each one by SHA-256; a cancelled download resumes where it stopped. With the tables installed, in any drill or lesson the board judges every move you make: a move that turns a win into a draw, or a draw into a loss, is announced at once, and **Backspace** takes it back in a lesson. **Control+T** says the theoretical result of the position and how many moves to the next irreversible move (pawn move, capture or mate); **Control+Shift+T** names the moves that keep the result.

Every attempt is recorded in your history (`tactic.db`): the starting position and the moves, the answer, whether the result was held without a slip, how many hints were asked, moves and time. The dialog shows how many times in a row each position was held; an attempt with hints counts as practice, not as held.

### Keyboard commands on the endgame board

| Key | Action |
|---|---|
| Tab / Shift+Tab | The actions bar. In a drill: Repeat goal, Tablebase verdict, Best moves, New position, Back to board. In a lesson: Repeat rule, Tablebase verdict, Best moves, Take back, Restart position, Next position, Back to board |
| Control+F1 | Repeat the goal (drill) or the rule (lesson) |
| Control+N | Another position of the drill, or the next position of the lesson |
| Control+R | The same lesson position again (lessons only) |
| Backspace | Take back your last move (lessons) |
| Control+T | The tablebase verdict for the position |
| Control+Shift+T | The moves that keep the result |
| Escape | Leave. During a game it asks first |

The commands of the game board (see "Keyboard commands on the board") work here too, except Control+D, which does nothing here, and F2 / Shift+F2, which say "No Time Control" unless a mate drill was given a clock.

## My Study

**My Study...** reads the same history and tells you how much and how you studied: by day, the tactics (puzzles, solved, minutes) and the endgames (positions, held, minutes) and the reviews of missed puzzles (how many, how many clean) with the day's total, for today, the last 7 or the last 30 days; and how far the endgame lessons go, lesson by lesson: which positions are firm (held three times in a row, question right and result kept without a slip), which are pending, and where you are; and the review queue: how many missed puzzles are due today, how many wait for their day, and how many are firm. **Copy to clipboard** puts the whole text in the clipboard. Games are not counted here on purpose: real games are played elsewhere.

## Playing a game

**New Game...** opens the game setup:

* **Play Mode**: human versus computer, or human versus human on the same keyboard.
* **Variant**: Standard, Chess 960, Anti chess, Atomic, King of the hill, Racing kings, Horde, Three check and Crazy house.
* **Time Control**: Classical (90+30), Rapid Play (15+10), Rapid Play (10+5), Blitz (5+5), Blitz (3+2), Bullet (2+2), Bullet (1+0), No Time Control, or Custom Time Control, typed in its own field (for example `10+5`).
* **Play As**: Random, White or Black, when playing the computer.
* **Starting FEN**: any position.
* **Engine Options...**: strength (Elo) and thinking time, when playing the computer. Standard chess uses Stockfish 16 (the official 64-bit build); variants use Fairy-Stockfish.
* **Visually highlight board interactions**: draws the focused square on the picture of the board, for whoever watches the screen.

### Replaying a PGN file

**Replay PGN File...** opens a PGN file; when the file holds several games, a list asks which one. Enter plays the next move of the game and Backspace takes it back, while the arrow keys let you inspect the board at any point. To add variations and comments, open the file with **Analyse PGN File...** instead.

### Keyboard commands on the board

| Key | Action |
|---|---|
| Arrow keys | Move between squares; each square announces its piece and name |
| Enter, Numpad Enter or Space | Select the piece to move, then the destination square |
| R, N, B, Q, K, P | Jump to your next rook, knight, bishop, queen, king or pawn. When you do not own a side (human versus human, the analysis board) they jump to the pieces of the side to move. In the Board Editor they place pieces instead |
| Shift + letter | Jump to the opponent's next piece of that type (or, when you do not own a side, the other side's) |
| A | Which pieces attack the focused square |
| M | Material count for both sides |
| F1 / Shift+F1 | Overview of your pieces / of the opponent's pieces |
| F2 / Shift+F2 | Remaining time on the clock of the side to move / of the other side |
| F3 | The focused square and piece in IBCA notation |
| F4 | Score sheet: the moves played so far, as a list. Up and Down arrows move through it; F4 or Escape closes it |
| F6 / Shift+F6 | Your pocket / the opponent's pocket (Crazyhouse) |
| Control+D | Human versus human only: offer a draw, or withdraw the offer; after the next move the other player accepts or declines. Against the computer it has no effect |
| Control+S | Save the game as a PGN file |
| Control+Shift+S | Save the board as a PNG image |
| Escape | Close the board. During a game it asks first: leaving abandons the game against the engine |

## Record and Analyse a Game

**Record and Analyse Game** opens the analysis board on the starting position, where you enter a game move by move, both sides from the keyboard — a game you played over the board, following it on your tactile set, or any game you want to study. (To start from an empty board and set up a position, use the "Board Editor".) **Analyse PGN File...** opens a saved game on the same board, variations and comments included.

Nothing ends the session: a checkmate inside a variation is only a position. Wherever the line already continues, a different move starts a **variation**; you can come back to the main line at any time. Each move can carry a **comment** (what you were thinking, what you missed) and a **mark**: ! good move, ? mistake, !! brilliant, ?? blunder, !? interesting, ?! dubious. The marks are spoken in words.

**Control+S** saves. The first time, a new game asks for the players, the event, the date and the result, and goes to your **games folder** (Settings; by default `Documents\Chessmart`) as `year-month-day_White-vs-Black.pgn`. After that, and for a game opened from a file with a single game or imported from Lichess, Control+S saves to that file without asking. **Control+Alt+S** opens the details (players, event, date, result) at any time, and saves.

Once the game has a file, every change -- a move, a comment, a mark, a line added by the engine -- is saved by itself, so nothing is lost if you close the board or NVDA. The setting "Save analysed games automatically, once they have a file" turns this off; then Control+S saves and Escape asks before leaving unsaved changes.

### My games

**My Games...** lists every game in your games folder, the most recently changed first: the date, the players, the result, and how much you have annotated it ("Comments: 12, marks: 4, variations: 2", or "No notes"). Enter opens the game on the analysis board, where it keeps saving to its own file. A file with several games shows each of them; a game opened out of such a file is saved as a new file. The shortcut has no key by default: assign one in NVDA's Input Gestures dialog, Chessmart category.

### Game review

**F7** on the analysis board (or Tab, "Review the game") reviews the whole game: the engine evaluates every position of the main line (about a second each; F7 again stops; progress follows NVDA's "Progress bar output" setting, beeps by default), judges each move with Lichess's rules, and says each player's accuracy, computed as Lichess does ("Your accuracy 96 percent, opponent 87."), then the critical moments: "3 critical moments: move 14, mistake; move 22, inaccuracy; move 31, blunder." **Alt+Page Down** and **Alt+Page Up** go from one to the next. Each opens on the position before the move, so the better move is looked for there: play a candidate and Shift+E judges it.

The "Game review (F7 on the analysis board)" group in Settings, or "Review options..." in the analysis board's Tab bar, decide how much the engine says: whose moves (only yours, the side at the bottom of the board, or both); what counts (blunders only; mistakes and blunders; everything); how many moments at most (3, 5, 10 or all, keeping the worst); what the engine reveals (by default only where the move went wrong; or also its move; or its move and its line as a variation); the time per position; and whether opening theory is skipped. The review marks a critical move with its verdict only when you left the move unmarked: your own marks are never changed.

### Import a Lichess game

**Import Lichess Game...** offers the Lichess link on the clipboard, if there is one (in the browser, Control+L then Control+C copies it), and otherwise asks for a game link, a game code, or a Lichess username (that player's last game; the name is remembered for next time). The game is saved in the games folder as `year-month-day_White-vs-Black_lichess-code.pgn` and opens on the analysis board, from Black's side when the remembered user played Black. Importing the same game again opens your saved copy, with your notes, instead of downloading over it. Lichess's own evaluations are left out: the engine answers you, it does not speak first.

Every move carries its clock: moving through the game says the time left and the time the move took ("clock 0:48, took 0:12, under a minute"). **T** sums up the clock for both sides: from which move a player was under a minute, the lowest clock, the longest think.

### Engine analysis

The engine is Stockfish 16. An evaluation is said the way players say it: "white slightly better, plus 0.4" (a pawn is 1.0). Shift+E judges a move the way Lichess does: the evaluation becomes a winning chance from 0 to 100, and the move is an inaccuracy when it gives away 5 points of it, a mistake at 10, a blunder at 15. That is why losing a pawn in a level position is an inaccuracy, while losing one with a rook up is nothing. The suggested mark is only a suggestion: the mark stays yours.

Opening names come from Lichess ([lichess-org/chess-openings](https://github.com/lichess-org/chess-openings), public domain), looked up by position, so a transposition is recognised too. A move that reaches a new named opening says its name, the first move out of the table says "out of theory", Shift+E on a theory move says so instead of asking the engine, and saving writes the ECO and Opening tags.

Your own variations have no limit: calculate until you can say how the position stands, and stop there. The engine's line added with Control+E stops at 8 half-moves, enough to see the idea.

### Keyboard commands on the analysis board

The commands of the game board work here too (arrows, Enter, A, M, F1, F4...), with three differences: the piece letters jump to the pieces of the side to move, Control+D does nothing, and F2 / Shift+F2 say "No Time Control". On top of them:

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
| Control+S | Save the game in the games folder (a new game asks for its details the first time) |
| Control+Alt+S | Edit the players, event, date and result, and save |
| E | With five pieces or fewer and the tablebases installed (Endgames, Download tablebases): the exact result and the moves that keep it, instead of the engine. Otherwise the engine evaluation, a sentence each: who is better and by how much, the best move, its line (three moves), and two other candidates. The engine's name and depth are left out of the speech; Control+E writes them in the game. Press twice to let the engine think 8 seconds instead of 2 |
| X | The threat, as on Lichess: what the other side would play if it were its move, with the evaluation and the line. Not in check (the threat is already there) |
| Shift+E | Review the move that led here against the engine's best: the engine's move, good, inaccuracy, mistake or blunder, and the mark that suggests |
| Control+E | After E, add the engine's line (up to 8 half-moves) as a variation, with the evaluation as its comment |
| F7 | Review the whole game; F7 again stops |
| Alt+Page Down / Alt+Page Up | Next / previous critical moment of the review |
| T | The clock of the game, for both sides (imported games) |
| O | The opening the line is in, with its ECO code, and whether the position is still theory |
| Tab / Shift+Tab | All these actions as a bar, each with its key: for when a key is forgotten. The bar also has Review options..., Mark the move, Play from here against the computer..., Flip the board and Back to board |
| Escape | Close the board; if something changed since the last save, it asks first |

"Play from here against the computer..." in the Tab bar opens the New Game dialog with this position as the start and its side to move as yours: choose the engine strength and the clock there.

## Board Editor

**Board Editor** opens an empty board to set up any position square by square. The piece letters place pieces, as in FEN: **Shift+K, Q, R, B, N, P** for a white king, queen, rook, bishop, knight or pawn, the letter alone for a black one. **Delete** or **Backspace** empties the square; **Enter** says what is on it. **Control+C** copies the position as FEN, **Control+V** takes one from the clipboard. The arrow keys, F1, F3, A, M and F4 work as on the game board.

**Tab** opens the editor's actions: switch whose move it is; switch each castling right (a right exists only while its king and rook stand on their starting squares); check the position, which says in words what is wrong ("There is no black king.", "A pawn stands on the first or the eighth rank.", "The side that is not to move is in check.") or that it is valid; analyse this position on the analysis board; copy as FEN (Control+C); paste a FEN (Control+V); the starting position; clear the board; flip it; back to board. "Analyse this position" opens it on the analysis board, where "Play from here against the computer..." in the Tab bar starts a game from it.

**Escape** closes the editor; when there are pieces on the board it asks first, since the position would be lost (Control+C copies it before you leave).

## Settings

**Settings...** in the Chessmart menu opens the Chessmart settings dialog:

* **Tactics database**, with **Browse...** to point at a database elsewhere and **Download or update...**.
* **Default training plan**, **Default challenge level**, the trainer summary and **Default themes** for new tactics sessions and Random Puzzle.
* **Move notation**: how moves and squares are spoken.
* **Games folder**: where the analysis board saves games, with **Browse folder...**.
* **Save analysed games automatically, once they have a file**: on by default (see "Record and Analyse a Game").
* **Game review (F7 on the analysis board)**: the review options (see "Game review").

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

The interface is in English, Brazilian Portuguese and Spanish (a first pass; native review welcome). This manual also has a Brazilian Portuguese version, which NVDA's Help button opens when NVDA is in Portuguese. Translations live in `addon/locale/<language>/LC_MESSAGES/nvda.po`, in the standard NVDA add-on layout, and are welcome: to start a new one, run `py -3 tools/i18n.py update <language>` and fill in the `msgstr` lines, or ask for the add-on to be added to the NVDA add-ons project on Crowdin. The NATO and Anna square names and the IBCA notation are international and are not translated.

To build the add-on or change its code, read [the Chessmart contributing guide](https://github.com/joaovictorf01/chessmart/blob/main/CONTRIBUTING.md).

## Credits

* [Musharraf Omer](https://github.com/mush42) — the original Chessmart: board, engines, variants, PGN replay.
* [Lichess](https://lichess.org) — the puzzle database (CC0), the opening names, the accuracy formula, the Syzygy tablebase mirror and the notation styles of its blind mode.
* [Stockfish](https://stockfishchess.org) and [Fairy-Stockfish](https://fairy-stockfish.github.io) — the engines.
* [python-chess](https://python-chess.readthedocs.io) — the chess library.
* João Victor — the tactics trainer and its database tooling, the review of missed puzzles, the endgame drills and lessons, the tablebase judge, My Study, the analysis board, engine analysis, opening names, game review, Lichess import, the Board Editor, My Games, the move notation, the update to Stockfish 16 and to the current python-chess, the cleanup of the old online-play code, and the Portuguese translation.
