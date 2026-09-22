# Contributing to Chessmart

Chessmart is an NVDA add-on. The user-facing side is Python 3.13 (NVDA's runtime), the chess logic is [python-chess](https://python-chess.readthedocs.io/), bundled under `addon/globalPlugins/chessmart/lib/`.

## Layout

- `addon/globalPlugins/chessmart/` — the add-on.
  - `__init__.py` — the NVDA global plugin: the Tools menu, the shortcuts, and the code that opens a board.
  - `virtual_chessboard/` — the boards: human vs engine, human vs human, PGN replay, tactics (`puzzle_board.py`), endgames (`endgame_board.py`).
  - `tactic/` — the puzzle database (SQLite, downloaded), the player's history and Glicko-2 rating, the download code. No NVDA imports here.
  - `endgame/` — mate drills, endgame lessons, the Syzygy tablebase judge. No NVDA imports here.
  - `graphical_interface/` — wx dialogs.
  - `locale/<lang>/LC_MESSAGES/nvda.po` — translations (English is the source language).
- `tests/unit/` — unit tests. They run outside NVDA; `tests/unit/chessmart/__init__.py` stubs the two NVDA modules the code imports.
- `tools/` — `i18n.py` (extract/update/compile translations), `build_puzzles.py` (monthly puzzle database), `build_syzygy_manifest.py`.
- `readme.md`, `changelog.md` (English) and `changelog.pt_BR.md` (Portuguese).

## Running the tests

```
py -3 -m unittest discover -s tests -t . -q
```

Any Python 3.12+ works; the tests do not need NVDA.

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
