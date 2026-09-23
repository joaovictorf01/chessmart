# Architecture

Everything lives under `addon/globalPlugins/chessmart/`.

## Two layers

```
NVDA-bound (runs only inside NVDA)          pure (runs anywhere, tested)
-----------------------------------         ------------------------------------------
__init__.py      plugin, menu, shortcuts     tactic/          puzzle database, history, rating
chessboard.py    the wx window of a board    endgame/         drills, lessons, tablebase judge
virtual_chessboard/  the boards the          training_session.py, trainer.py, theme_*.py
                 screen reader navigates     game_tree.py     analysis tree (variations, comments, marks)
graphical_interface/  wx dialogs             engine_eval.py   what engine numbers mean
                                             openings/        opening names by position
                                             analysis_words.py what the analysis board says
                                             puzzle_attempt.py, board_geometry.py, pgn.py, played_move.py,
                                             notation.py, study_log.py, concurrency.py
```

The left side imports the right side, never the reverse (`test_boundaries.py`). A rule that matters to the user belongs on the right, with a test named after it.

## Opening a board

Menu item (`__init__.py`, `ChessboardMenu`) → dialog when there are options (`graphical_interface/`) → `GameInfo` (`game_elements.py`) → `ChessboardDialog.from_game_info(board class, game info)` → the window takes focus → `set_focus_to_board` builds the board (`virtual_chessboard/*`) with the keyword arguments of `GameInfo.vboard_kwargs`.

Boards: `base.py` (squares, navigation, speech of moves, the game's end; what A, M and F1 say is in `announcements.py`, Control+S in `board_files.py`) → `user_driven.py` (picking up and dropping pieces) → `user_user.py` (two people), `user_engine.py` (against Stockfish), `puzzle_board.py`, `endgame_board.py`, `analysis_board.py` (the engine keys in `engine_actions.py`, the engine process in `analysis_engine.py`); `pgn_player.py` replays. The Tab bar of the trainers and the analysis board is `actions_bar.py`.

## A move

Enter on a square (`UserDrivenCell` → `activate_cell`) → `user_play` → `move_piece_and_check_game_status`: `PlayedMove.capture` records what is needed to say the move before it is pushed → the move is spoken → `move_completed_signal` → the engine, if any, answers on a worker thread (`concurrency.call_threaded`) and comes back with `wx.CallAfter`. The analysis board overrides the move: it goes into its `GameTree` and nothing ends the session.

## Closing

Escape → `leave_prompt` (asks only when something would be lost) → `hide_board_gui` → `ChessboardDialog.onClose` → `chessboard_closed_signal` → `game_over`, the engine quits, the tablebase closes → the board's signal receivers are disconnected.

## Threads

The pool in `concurrency.py` runs the engine, downloads and the board picture. `LatestWins` keeps one picture conversion at a time. Anything that touches wx or speech goes back through `wx.CallAfter` or `queueHandler`.

## Data

In NVDA's configuration folder, `chessmart/` (outside the add-on, so updates never touch it): `puzzles.db` (the Lichess puzzles, replaced on update), `tactic.db` (the player's history: attempts, rating, endgame attempts; never replaced), `theme_catalog_cache.json`, `syzygy/` (tablebases). Settings are in NVDA's configuration, section `chessmart` (`addon_config.py`). Analysed games go to the games folder the user chooses.

Shipped with the add-on: `bin/` (Stockfish 16, Fairy-Stockfish, rsvg-convert for the board picture), `lib/` (see `lib/README.md`), `openings/openings.tsv`, `endgame/syzygy_manifest.json`, `sounds/`, `locale/`.
