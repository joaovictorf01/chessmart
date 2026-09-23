# Working on Chessmart

Chessmart is an NVDA add-on: an accessible chessboard, a Lichess tactics trainer, endgame drills and lessons, and an analysis board. Its users are blind; everything is spoken, and nothing may depend on seeing the screen. `docs/ARCHITECTURE.md` is the map; read it before a change that crosses modules.

## The one command

```
uv run python tools/check.py
```

Unit tests, ruff lint, ruff format check, translation catalog check, and pyright when `../nvda` (a clone of nvaccess/nvda) exists. It must pass before any commit. CI runs the same script.

## The boundary

These modules import nothing from NVDA and must stay that way (`tests/unit/chessmart/test_boundaries.py` fails otherwise): `tactic/`, `endgame/`, `trainer.py`, `theme_catalog.py`, `theme_names.py`, `notation.py`, `study_log.py`, `training_session.py`, `paths.py`, `pgn.py`, `game_tree.py`, `engine_eval.py`, `openings/`, `puzzle_attempt.py`, `board_geometry.py`, `played_move.py`, `analysis_words.py`, `concurrency.py`, `i18n.py`.

The rest (`virtual_chessboard/`, `graphical_interface/`, `chessboard.py`, `__init__.py`) cannot be imported outside NVDA. Do not write tests that import them: move the rule into a pure module and test it there.

## NVDA rules nothing will tell you

- wx and speech only on the main thread. From a worker, `wx.CallAfter`; in a callback that may arrive after the window closed, `if not self: return`.
- A script cannot block on `ShowModal`: use `graphical_interface.messages.run_modal`.
- NVDA binds only the `script_*` methods a class defines itself. Keys cannot come from a mixin; declare them in each cell class (see `actions_bar.py`).
- A board connects to module-level signals; `ChessboardDialog.onClose` disconnects them. Anything a board starts (an engine, a tablebase) must stop on `chessboard_closed_signal`.
- Log with the `chessmart:` prefix and lazy formatting (`log.info("chessmart: %s", value)`), so the NVDA log a user pastes can be searched.

## Text the user hears

- Every string goes through `_()`, `N_()` or `ngettext()` with a `# Translators:` comment on the line above: where it is heard and what each placeholder holds.
- Whole sentences, never pieces glued together: word order changes with the language.
- After adding strings: `py -3 tools/i18n.py update pt_BR`, translate, `py -3 tools/i18n.py compile`.
- `theme_names.py` has its own wording on purpose (licence): do not replace it with Lichess's text.

## Changes and releases

- Every user-visible change goes in `changelog.md` under "Unreleased"; the README says how to use it.
- Semantic versioning: a patch only fixes, a minor adds features. The version is decided at release time.
- NVDA-only behaviour cannot be verified here. Say which parts of `docs/MANUAL_CHECKS.md` need a human after the change.
