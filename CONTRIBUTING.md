# Contributing to Chessmart

Chessmart is an NVDA add-on. The user-facing side is Python 3.13 (NVDA's runtime), the chess logic is [python-chess](https://python-chess.readthedocs.io/), bundled under `addon/globalPlugins/chessmart/lib/`.

## Building

The repository follows the [NVDA add-on template](https://github.com/nvaccess/addonTemplate): `uv sync` then `uv run scons` builds `chessmart-<version>.nvda-addon`; pushing a `v*` tag builds and publishes a GitHub release. `tools/build_puzzles.py` regenerates the puzzle databases from the Lichess CSV, and `.github/workflows/puzzles.yml` does it monthly.

## Layout

Everything the add-on runs is under `addon/globalPlugins/chessmart/`. Read it in this order:

- `tactic/` — the data layer, pure Python with no NVDA imports. `store.py` talks to the two SQLite files (`puzzles.db`, the Lichess base; `tactic.db`, the player's history) and returns the dataclasses in `models.py`; `glicko2.py` is the rating maths; `review.py` the queue of missed puzzles; `repository.py` is the facade the rest of the add-on calls; `download.py` fetches the database.
- `endgame/` — mate drills (`drills.py`), endgame lessons (`lessons.py`), the Syzygy tablebase and its judge (`tablebase.py`, `judge.py`), the record of attempts (`log.py`). No NVDA imports here.
- `trainer.py`, `theme_names.py`, `theme_catalog.py` — the rules: training plans, challenge levels, the name and description of every Lichess theme. Also pure Python.
- `puzzle_attempt.py`, `board_geometry.py`, `game_tree.py`, `engine_eval.py`, `game_review.py`, `accuracy.py`, `openings/`, `position_editor.py`, `lichess_import.py`, `my_games.py`, `study_log.py` — more rules free of NVDA, each with its test file: what counts in a puzzle attempt and in the session; square colours, arrow-key neighbours and the material count; the analysis tree (variations, comments, marks, the PGN written); what the engine's numbers mean (Lichess's winning-chance thresholds); the critical moments of a game review; Lichess's accuracy formula; opening names by position; a position set up by hand and what is wrong with it; games from lichess.org; the games folder listed; the study log.
- `training_session.py` — one training session: the options the user chose (`TrainingOptions`) and the puzzle sequence (`TrainingSession`), with prefetch of the next puzzle.
- `virtual_chessboard/` — the boards the screen reader user navigates: `base.py` (squares, moves, speech; what A, M and F1 say is in `announcements.py`, Control+S and Control+Shift+S in `board_files.py`), `user_driven.py` (picking up and dropping pieces), `user_engine.py` (against Stockfish), `user_user.py` (two people), `pgn_player.py`, `puzzle_board.py` (the trainer), `endgame_board.py` (drills and lessons), `analysis_board.py` (recording and analysis, over the tree in `game_tree.py`; the engine keys E, Shift+E, Control+E and X in `engine_actions.py`, the game review F7 in `review_actions.py`, the engine process in `analysis_engine.py`), `editor_board.py` (the Board Editor).
- `virtual_chessboard/actions_bar.py` is the Tab bar shared by the puzzle, endgame, analysis and editor boards.
- `graphical_interface/` — the wx dialogs: new game, tactics session (with `tactics_setup.py`, shared with the settings), settings, endgames (`endgame_dialog.py`), My Study (`study_dialog.py`), the game details Control+S asks for (`record_dialog.py`), the game review options (`review_dialog.py`, shared by the settings and the analysis board), the two downloads (`download_dialog.py` for the puzzles, `tablebase_dialog.py` for the tablebases, sharing `download_base.py`), and the message boxes (`messages.py`).
- `chessboard.py` is the wx window that hosts a board; `__init__.py` is the NVDA global plugin: the Tools menu, the shortcuts, and the code that opens a board. `addon_config.py`, `notation.py`, `spoken_messages.py`, `signals.py`, `concurrency.py`, `paths.py`, `sounds.py` and `speaking.py` are the small shared pieces their names say.
- `lib/` — the bundled libraries (python-chess and the rest; see `lib/README.md`); `bin/` — Stockfish 16, Fairy-Stockfish and the board-picture converter.

Outside the add-on:

- `addon/locale/<lang>/LC_MESSAGES/nvda.po` — translations (English is the source language).
- `tests/unit/` — unit tests. They run outside NVDA and never touch the user's history; `tests/unit/chessmart/__init__.py` stubs the NVDA modules the code imports.
- `tools/` — `check.py` (the one verification command), `i18n.py` (extract/update/compile translations), `build_puzzles.py` and `verify_puzzles.py` (the monthly puzzle database), `build_openings.py` (the opening table), `build_syzygy_manifest.py`.
- `readme.md` — the user manual, in English; the build copies it to `addon/doc/en/` and NVDA's Help button opens it. `addon/doc/pt_BR/readme.md` is the Brazilian Portuguese manual: it must follow `readme.md`, the same sections in the same order, so a change to the manual is made in both.
- `changelog.md` (English) and `changelog.pt_BR.md` (Portuguese).
- `docs/ARCHITECTURE.md` (the map), `docs/MANUAL_CHECKS.md` (what only NVDA can show).

## Checking a change

```
uv run python tools/check.py
```

One command, the same CI runs: unit tests, ruff lint and format check, the translation catalog check, and pyright when NVDA's sources are cloned at `../nvda`. Pyright type-checks the add-on in basic mode; it resolves NVDA's own modules from that checkout of [nvaccess/nvda](https://github.com/nvaccess/nvda) and the bundled libraries from `lib/`. The tests do not need NVDA; `docs/MANUAL_CHECKS.md` lists what only NVDA can show. `AGENTS.md` has the rules for coding agents, `docs/ARCHITECTURE.md` the map.

## Code checks

CI runs the hooks in `prek.toml` (trailing commas, ruff lint and format, pyright) and refuses a release tag that fails them. Run them before pushing:

```
uvx --from add-trailing-comma==3.2.0 add-trailing-comma $(git ls-files '*.py' | grep -v chessmart/lib/)
py -3 -m ruff check --fix --exclude addon/globalPlugins/chessmart/lib .
py -3 -m ruff format --exclude addon/globalPlugins/chessmart/lib .
```

Tabs for indentation, as in NVDA itself.

## Translations

Every string spoken or shown to the user goes through `_()` (or `N_()` for constants translated later), with a `# Translators:` comment above it. After changing strings:

```
py -3 tools/i18n.py extract
py -3 tools/i18n.py update pt_BR
py -3 tools/i18n.py update es
py -3 tools/i18n.py compile
```

Then fill the new `msgstr` entries in the `.po` files. `tools/i18n.py check` reports untranslated strings and placeholder mismatches.

## Trying your change in NVDA

Replace `%APPDATA%\nvda\addons\chessmart` with a directory junction to this repository's `addon/` folder (`mklink /J`), restart NVDA once, and from then on NVDA+Control+F3 reloads the plugin after edits. Keep no other copy of the add-on inside `addons/`: two add-ons with the same manifest name make NVDA load the wrong one.

## Comments, commits, pull requests

- Comments and docstrings in English, and only where the code does not already say it: the *why*, a source, a non-obvious constraint.
- Commit messages in English, one change per commit.
- Endgame positions cite their source (Silman, De la Villa, Capablanca) and must match the Syzygy tablebase; `tests/unit/chessmart/test_endgame_lessons.py` checks every position that has a table in `tests/fixtures/syzygy`.
- Open a pull request against `main`. CI runs the tests and the code checks.

## Releases

Semantic Versioning: a patch release (1.1.x) only fixes, a minor release (1.x.0) adds features. Changes accumulate under `# Unreleased` in both changelogs; the version in `buildVars.py` changes only when a release is cut. Pushing a `v*` tag builds the package and publishes the GitHub release.
