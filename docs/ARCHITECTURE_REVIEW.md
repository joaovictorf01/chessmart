# Architecture review

Reviewed at commit `1e7aa7f` (2026-09-21, "Remove unfinished online play"). Scope: `addon/globalPlugins/chessmart/` except `lib/`, plus `tests/unit`. All line numbers refer to that commit. Tests, `ruff check`, `ruff format --check` and `tools/i18n.py check` were run and are green (96 tests, 1 expected failure from the template sanity test).

## (a) Verdict

This is a healthy add-on with a clear split between what can run outside NVDA and what cannot: `tactic/`, `endgame/`, `trainer.py`, `theme_*.py`, `notation.py`, `study_log.py` and `training_session.py` import no NVDA module, are covered by 96 real tests (SQLite fixtures, a local HTTP server for downloads, 3-piece Syzygy tables), and the modules that do touch NVDA (`virtual_chessboard/`, `graphical_interface/`, `chessboard.py`, `__init__.py`) mostly follow NVDA's rules: `script_*`/`event_*` naming, `@script` gestures, secure-mode guards, `wx.CallAfter` from worker threads, `if not self` after deferred calls, `_()` through one `i18n.py`. The problems are concentrated and fixable in days, not weeks: a handful of real bugs inherited from the upstream fork (two wx dialogs opened from a worker thread, an engine resignation that raises `TypeError`, PGN headers read from the wrong tag, an untranslated German colour name that says "black" for white, a `None` passed to the board factory), a process-wide replacement of NVDA's `http`/`xml` packages with Python 3.7 copies, leaked boards through the home-made signal system, and about 3,300 lines of board logic with no tests because pure decisions (attempt state, hint order, board geometry, PGN parsing) live inside NVDA-importing modules. Layering is right for the size: the menu class in `__init__.py` is the application layer and knows how to build every board, which is fine for four modes but is the one place that grows with each feature. Nothing here calls for ports-and-adapters, dependency-injection frameworks or an event bus; the right moves are extracting pure functions, disconnecting signals, and deleting what the online-play removal left behind.

## (b) Findings, ranked

Legend: size S = under an hour, M = half a day, L = days. "NVDA test" says whether the change can only be verified by running NVDA.

### 1. wx dialogs are created and shown from a worker thread

- Evidence: `virtual_chessboard/base.py:872-919` — `save_game` and `save_board_image` are decorated with `@call_threaded` (line 872, 896) and build `wx.FileDialog` and call `ShowModal()` inside (lines 874-888, 898-912); `save_board_image` also calls `self.dialog.bitmap_buffer.SaveFile` off-thread (line 915).
- Why it matters: the NVDA developer guide is explicit that dialogs "cannot be created, initialised, or shown (modally or non-modally) from any thread other than the GUI thread"; this can crash NVDA or leave a hung modal. Control+S / Control+Shift+S on any board hit this path.
- Change: drop `@call_threaded`; run the dialog on the main thread and, if the PGN write is considered slow (it is not), thread only the file write after the path is known.
- Size S. Risk low. NVDA test: yes (press Control+S on a board).

### 2. `http` and `xml` from a Python 3.7 install replace NVDA's own packages process-wide

- Evidence: `__init__.py:19-29` pops `http` and `xml` from `sys.modules` and re-imports them from `lib/` ("obtained from a Python 3.7 installation"); `lib/http/`, `lib/xml/`, `lib/concurrent/` exist. `tactic/download.py` and `endgame/tablebase.py` use `urllib.request`, which uses `http.client`.
- Why it matters: NVDA 2026.1 runs Python 3.13 with a full standard library (only `sqlite3` is missing, which the add-on already handles correctly in `tactic/db.py:234-252`). Replacing `http` and `xml` affects every other add-on and NVDA core code that imports them after Chessmart loads, and runs the downloads on a 3.7-era `http.client`. The comment dates from the 2021 upstream; the reason (aiohttp needs) left with the online play.
- Change: delete the block at `__init__.py:19-29` and `lib/http`, `lib/xml`, `lib/concurrent`, `lib/asyncio_disabled`; keep `import chess` inside `import_bundled()`. Verify in NVDA: puzzle download, tablebase download, PGN replay, engine game.
- Size S (code) / M (verification). Risk medium (only because it cannot be verified outside NVDA). NVDA test: yes.

### 3. Engine resignation raises `TypeError`; engine callbacks are deferred twice

- Evidence: `virtual_chessboard/user_engine.py:89` — `wx.CallAfter(self.game_resigned)` but `base.py:463` declares `def game_resigned(self, resigning_color)`. Also `user_engine.py:79` and `:124` already wrap `engine_play` in `wx.CallAfter`, and `engine_play` wraps its own calls again at lines 86, 89, 91.
- Why it matters: a resignation from the engine (`PlayResult.resigned`) ends in an unhandled exception inside a `CallAfter`; the game silently never ends. The double deferral is harmless but hides which thread the code believes it is on.
- Change: `wx.CallAfter(self.game_resigned, not self.prospective)`; remove the inner `CallAfter`s since `engine_play` is already on the main thread.
- Size S. Risk low. NVDA test: partly (the argument fix is obvious; the deferral cleanup deserves one game).

### 4. Boards never disconnect from the module-level signals

- Evidence: `signals.py:8-10` says receivers are strong references and only `disconnect` releases them; `disconnect` is never called anywhere (grep). Every board connects in `base.py:427-428`; engine boards add three more at `user_engine.py:38-40`; endgame boards add one at `endgame_board.py:123`. `chessboard.py:117-123` (`onClose`) destroys the window but nothing removes the receivers.
- Why it matters: every game, puzzle session and endgame position played since NVDA started stays alive: the board, its 64 cell objects, the score sheet, the closed `SimpleEngine` wrapper. `chessboard_opened_signal` (`chessboard.py:94`) has no receivers at all.
- Change: in `ChessboardDialog.onClose`, after sending `chessboard_closed_signal`, call a `board.disconnect_signals()` that removes the board's receivers (sender-filtered). Or make `Signal` hold `weakref.WeakMethod` for bound methods; the lambdas in `base.py:427-428` would then need to become methods. Remove `chessboard_opened_signal`.
- Size S. Risk low. NVDA test: yes (open and close a few boards; check nothing breaks on the second game).

### 5. PGN replay: wrong header tags, strict decoding, uncaught parse errors, and a documented key that does nothing

- Evidence: `virtual_chessboard/pgn_player.py:40-41` read `event` and `site` from `headers.get("Date")` (copy-paste); `:47` and `:91` open the file with `encoding="utf-8"` (strict); `:66-80` `parse_pgn_result_string` raises `ValueError` for any file without a `Result` tag (`"".split("-")` cannot unpack at line 70) or with an unusual one; `__init__.py:311-337` (`list_games_in_pgn`) has no `try`. `:156` `rewind` is a no-op while `readme.md:97` says "Backspace takes it back".
- Why it matters: a Latin-1 PGN, a game without `Result`, or a truncated file produces an NVDA error tone and a traceback in the log instead of a spoken message; the game list shows the date three times. Untrusted files are the normal input of this feature.
- Change: fix the two tags; open with `errors="replace"`; make the result parser return `_("Unknown result")` instead of raising; wrap the load in `except (OSError, UnicodeDecodeError, ValueError)` with `ui.message`; implement `rewind` as `board.pop()` plus focus, or remove the readme line. Move `PGNGameInfo`/`PGNGame` (pure) into a module without `ui`/`queueHandler` imports so a test can cover a headerless file, a `*` result and a Latin-1 file.
- Size S (fixes) + S (test). Risk low. NVDA test: only for `rewind`.

### 6. `NewGameOptionsDialog.onOk` passes `None` to the board factory

- Evidence: `graphical_interface/new_game_dialog.py:151-155` — `game_info = self.get_game_info()` may return `None` (lines 122, 133, after the message box for an invalid time control or FEN), and `self.callback(vboard_cls, game_info)` runs anyway; `chessboard.py:80-88` then dereferences `game_info.pychess_board`.
- Why it matters: typing an invalid FEN shows the error, then the dialog closes and NVDA logs an `AttributeError`; the user gets no game and no explanation.
- Change: `if game_info is None: return` before the callback.
- Size S. Risk low. NVDA test: yes, trivial.

### 7. IBCA notation says "black" for white; other spoken strings bypass translation

- Evidence: `ibca_notation.py:11` maps `chess.WHITE` to `"schwarts"` and `chess.BLACK` to `"Schwarze Farbe"` (both are "black"; white is "weiss"). `base.py:670` speaks `outcome.termination.name` (an enum name such as "FIVEFOLD REPETITION") untranslated at game over; `user_driven.py:290-294` forms plurals with `_("{count} {piece}s")` instead of `ngettext`; `pgn_player.py:59` builds "X versus Y" with an f-string.
- Why it matters: F3 gives blind players the wrong colour in the notation used at tournaments; game-over reasons are English enum names in every language; Portuguese and Spanish plurals cannot be right.
- Change: `chess.WHITE: "weiss"`; a small `termination_name()` mapping with `_()` and `# Translators:` (seven values); `ngettext` for the pocket; `_("{white} versus {black}")`.
- Size S. Risk low. NVDA test: no (pure strings; a test can assert the mapping).

### 8. Translator comments are missing in exactly the files a translator needs them most

- Evidence: ratio of `# Translators:` comments to `_()`/`N_()` calls per file: `puzzle_board.py` 3/97, `game_elements.py` 0/24, `new_game_dialog.py` 2/36, `__init__.py` 13/34. The rest of the tree is at or near 1.0 (`lessons.py` 109/113, `tactics_setup.py` 25/25, `notation.py` 19/19). `CONTRIBUTING.md` requires the comment on every string.
- Why it matters: the puzzle board carries the strings a translator is most likely to get wrong (short spoken fragments with placeholders: "Rating {rating}, up {delta}.", "your move {current} of {total}"); Crowdin shows nothing but the msgid.
- Change: add the comments; nothing else changes. `tools/i18n.py extract` will pick them up.
- Size M (about 160 comments). Risk none. NVDA test: no.

### 9. Trainer boards render a PNG through a subprocess on every arrow key

- Evidence: `base.py:401` defaults `use_visuals=True`; `__init__.py:286-297`, `:217-251` and `:253-273` open the puzzle and endgame boards without overriding it; `base.py:206-221` (`update_visual_highlight`) runs from the cell's `event_gainFocus` (`:223-228`) and calls `chessboard.py:150-153`, which spawns `rsvg_convert.exe` (`:155-171`) in the thread pool for every focus change. `new_game_dialog.py:141` lets a game turn it off; the trainer never does. Results are applied in completion order (`chessboard.py:173-180`) with no sequence check.
- Why it matters: the tactics trainer is used with rapid arrow navigation; each key press costs a process spawn and a 900x900 raster, with up to 8 in flight (`concurrency.py:10`), and a fast sequence can leave a stale highlight on screen. The per-move render at `base.py:583` is defensible (a sighted helper sees the position); the per-focus one is not.
- Change: pass `use_visuals=False` from the three trainer launchers, or render the highlight only when a sighted-view toggle is on; add a generation counter so a late result does not overwrite a newer one.
- Size S. Risk low. NVDA test: yes (the image window must still update after moves).

### 10. The tablebase is reopened for every candidate position when drawing a random drill

- Evidence: `__init__.py:206-215` (`_drill_position_is_won`) calls `tablebase.open_tablebase()` on every call; `endgame/drills.py:165-186` (`random_fen`) calls `accept(board)` up to 2000 times; `endgame/tablebase.py:219-228` globs the directory and constructs a `chess.syzygy.Tablebase` each time.
- Why it matters: Control+N on the king-and-pawn drill can scan a 290-file directory hundreds of times on the main thread before a position is accepted; with the 5-piece set installed this is a visible pause.
- Change: open once in `open_endgame`/`open_endgame_drill`, pass a closure that reuses it, close it after the draw (or hand it to the board, which already owns one in `endgame_board.py:113-131`).
- Size S. Risk low. NVDA test: yes, but only for the pause.

### 11. Duplicated code between the two trainer boards and the two download dialogs

- Evidence: `focus_action_bar`/`focus_board_from_actions` in `puzzle_board.py:298-308` and `endgame_board.py:92-102`; the "With {hints} hints from the tablebase" sentence at `endgame_board.py:319` and `:612`; `_record_attempt` in `endgame_board.py:345-362` and `:640-657` (same ten fields); `_megabytes` in `download_dialog.py:40` and `tablebase_dialog.py:29`; `_progress`/`_finished_*` in `download_dialog.py:283-359` and `tablebase_dialog.py:167-222`; the invalid-time-control message in `new_game_dialog.py:117` and `endgame_dialog.py:152`; the "database not found" handling in `__init__.py:124-144` and `:167-186`.
- Why it matters: the puzzle and endgame boards drift (the endgame one already ignores `reverse` order differences); the two download dialogs are 60% the same and any fix (the "Try again" button just added to one) has to be done twice.
- Change: move the actions-bar focus code into `TrainingActionsBar` itself (it knows its parent), a single `record_endgame_attempt(board, *, outcome, kept, answer_correct)` helper, a `DownloadDialogBase` with `_progress`/`_finished_*`/`onCancel`, one `format_megabytes` in a shared module, one `_open_session(options)` in the menu.
- Size M. Risk low-medium (the two dialogs are NVDA-only). NVDA test: yes for the dialogs.

### 12. Leftovers of the online-play removal and other dead code

- Evidence (each verified by grep for references outside its own definition): `graphical_interface/components.py:21-110` `SimpleDialog`/`SnakDialog` and the vendored `lib/wx_lib_sized_controls.py` (only used there); `user_engine.py:110-116` `on_user_response_to_engine_draw_offer`; `base.py:391` `can_resign` (set in three classes, read nowhere); `base.py:441`/`user_driven.py:132` `get_highlighted_squares`; `game_elements.py:32` `custom_starting_fen` (written at `new_game_dialog.py:139`, never read); `ui_components.py:82` `remove_item`; `ui_components.py:34-36` the "should be set to Tru in the final release" flag from 2021; `signals.py:55` `chessboard_opened_signal`; `time_control.py:17-19,47-59` `from_string`/`TIME_CONTROL_REGEX` (only the removed Lichess client used the `;` format); `sounds.py:43` `you_won` is never played; `glicko2.decay` (`tactic/glicko2.py:177`) is used only by tests.
- Why it matters: each one is a question a contributor or an agent has to answer before touching the file; `SimpleDialog` also carries a third-party module in `lib/`.
- Change: delete; keep `glicko2.decay` only if rating decay is planned (then say so in a comment).
- Size S. Risk low. NVDA test: no.

### 13. Manifest hashes are optional in the puzzle download

- Evidence: `tactic/download.py:293` (`if tier.download_sha256 and ...`) and `:347` (`if part.sha256 and ...`) skip the check when the manifest has an empty hash; `endgame/tablebase.py:206-209` checks unconditionally. `urllib.parse.urljoin` at `download.py:141,154` accepts an absolute URL in `file`, so a manifest can point anywhere.
- Why it matters: the manifest is the trust root (fetched over TLS from the project's GitHub release, `download.py:27-29`), so this is not exploitable today; but a mis-generated manifest without hashes installs an unverified 600 MB file silently, and the tests cannot tell (they always supply hashes).
- Change: raise `DownloadError("manifest has no checksum for ...")` when a hash is empty; optionally reject part URLs whose host differs from the manifest's. Everything else in the download path is right: per-part and whole-file SHA-256, size check, `.part` staging, structural check via `is_puzzles_database`, 30 s/60 s timeouts, three retries, cancellation without leftovers.
- Size S. Risk low. NVDA test: no (add a test with an empty hash).

### 14. `log.exception` outside an `except` and a stale mixed-language remainder

- Evidence: `chessboard.py:176` calls `log.exception` in normal flow (it logs "NoneType: None" as the traceback); three `# noqa` explanations are still in Portuguese (`__init__.py:25,29`, `i18n.py:39`); nine log calls use f-strings while `pyproject.toml` declares `logger-objects = ["logHandler.log"]` for ruff's lazy-formatting rules; `GlobalPlugin.terminate` (`__init__.py:421-430`) does not call `super().terminate()`.
- Why it matters: small, but every one of them is the kind of thing a reviewer or an agent flags again on the next pull request.
- Change: `log.error(...)` at `chessboard.py:176`; translate the three comments; `%s` in log calls; `super().terminate()` first.
- Size S. Risk none. NVDA test: no.

### 15. Board logic that could be tested is trapped in NVDA-importing modules

- Evidence: `puzzle_board.py:34-131` (`AttemptState`, `SessionStats`) and `:764-775` (`_player_move_progress`), `:732-762` (hint order), `base.py:64-117` (`PlayedMove`), `:721-783` (material count), `:386-388,801-825` (row ranges and navigation), `:175-183` (square colour), `pgn_player.py:22-99`, `endgame_board.py:619-627` (`_kept_result`). The modules import `api`, `speech`, `ui`, `eventHandler`, `wx`, so `tests/unit/chessmart/__init__.py` cannot import them; no test names the product rules "first wrong move settles the rating", "retry is never rated", "an untouched puzzle is not counted", "hints go themes, origin, destination".
- Why it matters: these rules are in the README and in `changelog.md` and are the part of the product a contributor is most likely to break; today only NVDA can check them.
- Change: a `virtual_chessboard/attempt.py` (attempt state machine and session stats), a `board_geometry.py` (row ranges, neighbours, square colour, material), a `pgn_games.py` (`PGNGameInfo`, `PGNGame`), each free of NVDA imports and each with a test file that names the rule. The boards keep calling them. See finding 3 in section (e) and the "explicit state machine" note in (c).
- Size M. Risk low (moves, not rewrites). NVDA test: one pass to confirm nothing changed.

### Noted and considered fine

- `except Exception` appears 20 times, nearly all at boundaries where the alternative is an NVDA error tone: dialog refresh (`study_dialog.py:79`, `endgame_dialog.py:132`), worker threads (`download_dialog.py:319`, `theme_catalog.py:184`), recording an attempt (`puzzle_board.py:850`, `endgame_board.py:187`). Two could be narrower: `theme_catalog.py:86` (`OSError, ValueError`) and `__init__.py:212` (should at least `log.warning`).
- `Any` is used 12 times, each with a reason in a comment (`addon_config.py:48-49`, `endgame_board.py:75-81` for mixin attributes). Acceptable.
- Only five functions exceed 60 lines (`download_tier` 97, `NewGameOptionsDialog.makeSettings` 89, `TablebaseDownloadDialog._build` 77, `onSelectThemes` 64, puzzle `move_piece_and_check_game_status` 61) and each is linear wx layout or a single download loop. Not worth splitting.
- Module sizes are reasonable: the largest, `base.py` (915) and `puzzle_board.py` (855), read top to bottom; `lessons.py` (751) is data.
- Naming: camelCase is required by NVDA/wx for `script_*`, `event_*`, `makeSettings`, `postInit`, `onOk`, `roleText`, `positionInfo`, `windowHandle`, `processID`, `_gestureMap`, `bindGesture`, `getScript`, `scriptCategory`, and by NVDA's config convention for `tacticsDbPath`. The `onNewGame`/`onPaint`/`onBrowseDatabase` handler names and the `databasePathTextCtrl`-style widget attributes are habit (NVDA core's own style), not a requirement. Do not mass-rename: the churn would touch every dialog, break nothing and fix nothing.
- Magic numbers: `speech.commands.BreakCommand` appears 86 times with nine distinct values (50 to 500 ms). `PUZZLE_*_DELAY_MS` (`puzzle_board.py:28-30`) and `TIME_NOTIFICATION_MINUTES` are named already. A four-constant `pauses.py` would document intent; low priority. `threading.Timer(interval=2)` at `user_engine.py:127` and the Elo range at `new_game_dialog.py:212` (Stockfish's `UCI_Elo` bounds) deserve one comment each.
- Global state: `concurrency.THREADED_EXECUTOR`, `theme_catalog._REBUILD_IN_PROGRESS` (lock-guarded), the two stateless announcer singletons, and `signals.chessboard_signals`. Only the last one is a problem (finding 4).
- SQLite: every query is parameterised; f-strings interpolate only constant table/column names (`store.py:107,175,177,229-232,361,367`); the puzzle file is attached with `mode=ro` (`store.py:141`) so an update can never corrupt the history; connections are per call and closed in `finally`; `file_uri` escapes `%?#`. Migrations run on every open and are cheap. Good.
- Secure mode: menu not created (`__init__.py:368`), shortcuts refuse (`:377-383`), saving refuses (`base.py:303-312`). Correct.
- i18n bootstrap: one `addonHandler.initTranslation()` in `i18n.py` with an explicit `from .i18n import _` everywhere deviates from the guide's "call it in every module" but is more robust (the docstring explains the 1.0 bug it fixed). Keep.

## (c) What NOT to change

- Ports/adapters for speech and wx. The boards call `ui.message`, `speech.commands.*`, `eventHandler.queueEvent` in roughly 150 places; an abstraction would be a large mechanical rewrite that still cannot be exercised outside NVDA, because the behaviour under test is NVDA focus and speech-queue semantics. Extract what to say (lists of strings) into pure functions instead; leave how to say it where it is.
- Dependency injection of the engine and tablebase. `vboard_kwargs` is already an injection channel (`chessboard.py:80-88`); the boards open the engine in `__init__` and close it on `game_over`, and open/close the tablebase with the window. Adding `engine_factory=` would be a one-line optional kwarg if a fake engine is ever needed for an NVDA-stubbed test; until such a test exists it buys nothing. Keep.
- An explicit state machine for `is_game_over` on the base board. One boolean, set in one place, guarded against re-entry (`base.py:449-461`). Keep. The puzzle attempt is different: `AttemptState` (`puzzle_board.py:34-79`) already is the state machine, expressed as seven booleans whose invariants live in comments ("never twice", "once at the end"). Turning it into `phase: NOT_STARTED | IN_PROGRESS | SETTLED_FAILED | FINISHED` plus `is_retry`/`auto_solved` is worth doing only as part of finding 15, where it becomes testable; not as a standalone refactor.
- Splitting "a move happened" from "what to say". `PlayedMove.capture` (facts) and `_describe_move` (speech) are already separate (`base.py:64-117`, `:586-637`), and `move_completed_signal` carries the event. Keep.
- An application-service layer replacing the menu handlers. `ChessboardMenu` (`__init__.py:53-357`) is the service layer; it is 300 lines because it builds four kinds of `GameInfo`. The proportionate change is a `launchers.py` with four pure functions (`puzzle_game_info(session)`, `drill_game_info(...)`, `lesson_game_info(...)`, `pgn_game_info(...)`) that the menu calls, so a new mode adds one function and one menu line. A class hierarchy of services would be more than the four modes justify.
- Replacing the home-made `Signal` with a library. Blinker was just removed from `lib/`; the class is 40 lines. Fix the leak (finding 4), keep the class.
- Moving settings into NVDA's Settings dialog (`SettingsPanel` + `NVDASettingsDialog.categoryClasses`). Allowed and common, but the current standalone `gui.SettingsDialog` reached from the Chessmart submenu is what a blind user opens next to Tactics and Endgames; nothing is gained by moving it.
- Renaming camelCase handlers and widget attributes to snake_case. See "Noted and considered fine".
- Splitting `base.py` into cells/board/menus. Cosmetic; do it only if someone is already rewriting the file.

## (d) Suggested order of work

Batch 1, bugs and deletions (one afternoon, then one NVDA session to check): findings 1, 3, 5 (the four fixes), 6, 7, 10, 12, 13, 14. All are S; together they remove every known crash path and the leftovers of the online-play removal. Commit them separately so each can be reverted alone.

Batch 2, lifecycle and hygiene (two or three sessions; each needs an NVDA pass): findings 2, 4, 9, 8, 11. Finding 2 first, alone, because it is the one whose effect can only be seen inside NVDA; then 4 and 9 (both touch board open/close), then the translator comments (8), then the dedupe (11).

Batch 3, testability and seams (a week, spread out): finding 15 and the `launchers.py` from section (c), plus the AI-readiness items ranked 1-4 in section (e). Each extraction lands with its test file; the board files shrink, the pure files grow, and the count of product rules with a named test goes up. Do not start batch 3 before batch 1 is in, or the moved code will carry the bugs with it.

## (e) AI readiness

How well an AI coding agent (Claude Code, Codex, Cursor) can maintain this repository today, and what would make it better. The base is good: the pure/NVDA split is real, tests run in under two seconds with no NVDA, `uv.lock` and `.python-version` pin the toolchain, `ruff` and `prek` are configured, comments say why, and `CONTRIBUTING.md` and the README's "Where things live" already read like an agent brief. What is missing is mostly that the knowledge is spread across three files and a few conventions are only in people's heads.

### 1. `AGENTS.md` at the repository root

- Today: `CONTRIBUTING.md` (layout, commands, i18n rules, junction trick) and `readme.md` "For developers" overlap and neither is where agents look first. There is no `CLAUDE.md`/`AGENTS.md`.
- Content, specifically for this repo: (1) the one verification command (item 2) and the statement that it must pass before any commit; (2) the boundary rule "these modules import no NVDA module and must stay that way: `tactic/`, `endgame/`, `trainer.py`, `theme_catalog.py`, `theme_names.py`, `notation.py`, `study_log.py`, `training_session.py`, `paths.py`" and its inverse "`virtual_chessboard/`, `graphical_interface/`, `chessboard.py`, `__init__.py` cannot be imported outside NVDA; do not add tests that import them, extract the logic instead"; (3) the NVDA rules the agent cannot discover by running anything: wx and speech only on the main thread (`wx.CallAfter` from workers, `if not self` after it), `script_*` methods must live on the class that receives focus (not in a mixin, see `endgame_board.py:197-198`), `__gestures`/`@script` for keys, secure mode means no menu, no file dialogs; (4) the i18n contract: every user-visible string through `_()`/`N_()` with a `# Translators:` comment on the line above, `tools/i18n.py extract` + `update pt_BR` + `update es` after changing strings, NATO/Anna/IBCA never translated; (5) tabs for indentation, `ruff` line length 110, English comments and commit messages, one change per commit, changelog under `# Unreleased` in both languages; (6) what the agent must not do: touch `lib/`, touch `addon/locale/*.po` msgstr by hand except when asked, write to the user's `%APPDATA%\nvda\chessmart`, download anything in tests; (7) how to verify NVDA-bound changes: the junction from `CONTRIBUTING.md`, NVDA+Control+F3 to reload, and a short manual checklist per area (open a board, play a move, Escape, Control+S); (8) domain vocabulary the code assumes: prospective, drill vs lesson, held vs firm, tier, WDL/DTZ, "touched" attempt.
- Size S (the content exists; it needs one file). Risk none.

### 2. One verification command

- Today: four commands in two places (`CONTRIBUTING.md` lists tests, `add-trailing-comma`, `ruff check --fix`, `ruff format`; CI additionally runs `prek run --all-files` and `scons pot`; `tools/i18n.py check` is documented only in the README). `pyright` needs `../nvda` cloned, which an agent's sandbox will not have, and `pyproject.toml` says `typeCheckingMode = "strict"` while every file opts down to `# pyright: basic`.
- Change: a `tools/check.py` (or a `check` script in `pyproject.toml` run through `uv run`) that runs, in order and without `--fix`: `python -m unittest discover -s tests -t . -q`, `ruff check --exclude addon/globalPlugins/chessmart/lib .`, `ruff format --check --exclude ...`, `python tools/i18n.py check`, and `pyright` only if `../nvda` exists (print "skipped: no NVDA checkout" otherwise). CI calls the same script. `AGENTS.md` names only this command. All four steps pass today, so this is wiring, not fixing.
- Size S. Risk none.

### 3. Tests as executable specification of the product rules

- Today: the rules that are tested are named well (`test_hinted_attempts_count_as_practice_but_break_the_streak`, `test_wrong_whole_checksum_is_rejected`, `test_lost_positions_are_not_played_out`). The rules that are not tested are the ones in NVDA-bound code, and they are exactly the ones an agent will change by accident: first mistake settles the rating (`puzzle_board.py:476-478`), retry never rated (`:363-370`), untouched puzzle not counted (`:829-830`), Control+N needs two presses mid-puzzle (`:197-210`), hint order themes/origin/destination (`:740-756`), take-back undoes a pair and counts (`endgame_board.py:569-590`), leaving a lesson counts as not held (`:543-547`), lessons record `answer_correct` and drills record `None` (`:354`, `:649`). Also untested: `endgame/tablebase.py:131-173` `download_tables` (the puzzle download has a flaky-server test; the tablebase one has none) and `addon_config.py` validation of unknown notation values.
- Change: after the extraction in finding 15, one test per rule, named after the README sentence; a `tests/unit/chessmart/test_tablebase_download.py` reusing `FlakyHandler` from `test_download.py`. Add a docstring line to each existing test module saying which README section it specifies. An agent then has a place to add "the rule I was told" before touching code.
- Size M. Risk low.

### 4. A one-page `docs/ARCHITECTURE.md`

- Today: the README's "Where things live" is the closest thing; it is inside a user document and lists files, not flows.
- Content: the two-layer diagram (pure vs NVDA-bound) with the import rule; the three flows an agent needs to trace: menu → dialog → `GameInfo` → `ChessboardDialog.from_game_info` → board `__init__` → `set_focus_to_board`; a move: cell `activate` → `user_play` → `move_piece_and_check_game_status` → `PlayedMove` → speech → `move_completed_signal` → engine reply on a thread → `wx.CallAfter`; closing: Escape → `leave_prompt` → `hide_board_gui` → `onClose` → `chessboard_closed_signal` → `game_over` → engine quit / tablebase close. The data files (`puzzles.db` read-only attached, `tactic.db` history, `theme_catalog_cache.json`, `syzygy/`), where they live in NVDA and outside, and which are safe to delete. The seams for the four common additions with the files to touch: a lesson position (`endgame/lessons.py` only; the tablebase test checks it), a drill (`endgame/drills.py` + `lessons.py`), a notation style (`notation.py` only; `addon_config.py` validates against `STYLE_IDS` automatically), a board mode (`virtual_chessboard/<mode>.py`, `virtual_chessboard/__init__.py`, a launcher, a menu line, a dialog if it needs options, README).
- Size S. Risk none.

### 5. Purity and size: keep the runnable surface large

- Today: about 6,800 of 11,400 lines are importable without NVDA. The NVDA-bound remainder is where the bugs in section (b) are, which is not a coincidence: an agent can run and verify the pure half and can only read the other half. Two modules sit on the wrong side for no reason: `pgn_player.py` (data classes plus 40 lines of board) and `puzzle_board.py` (state and stats plus the board).
- Change: finding 15; then a lint rule an agent can run. The cheapest is a test, `tests/unit/chessmart/test_boundaries.py`, that imports each pure module with `sys.modules` guards asserting none of `wx`, `ui`, `speech`, `api`, `gui`, `eventHandler`, `queueHandler`, `NVDAObjects`, `controlTypes`, `scriptHandler`, `globalVars` appears in `sys.modules` afterwards (`logHandler` and `addonHandler` are stubbed and allowed). It fails the moment someone adds `import ui` to `trainer.py`.
- Size S (test) + M (extraction). Risk low.

### 6. Deterministic tooling and environment

- Today, good: `uv.lock`, `.python-version` (3.13), exact `ruff==0.14.5` and `pyright==1.1.407`, tests use `tempfile`, a local HTTP server on port 0 and fixture tables; nothing downloads. Less good: `test_missing_database_is_file_not_found` skips itself when a database exists on the machine (`test_training_session.py:105-109`); `test_endgame_lessons.py:48` silently checks fewer positions when 4- and 5-piece tables are absent (it is honest about it, but an agent reads "OK" and assumes all 40 were checked); `tactic/db.py:224-231` reads `CHESSMART_PUZZLES_DB_PATH` from the environment at import time, so an agent's shell can change what the tests see; the `ResourceWarning` from an unclosed `HTTPError` in `test_download.py` (the 404 case) prints on every run and will be mistaken for a failure.
- Change: make the skip an assertion by pointing `CHESSMART_PUZZLES_DB_PATH` at a temp directory in `setUp`; print the count of positions the tablebase test actually verified; close the `HTTPError` in `endgame/tablebase.py:162` / `tactic/download.py:269` (`error.close()` when it is an `HTTPError`); build the CI job's `unitTests.yml` on the same `tools/check.py`.
- Size S. Risk none.

### 7. Make the NVDA-only verification legible

- Today: an agent cannot run NVDA. The junction trick and NVDA+Control+F3 are documented, but there is no list of what to press after a change, and NVDA's log is the only output.
- Change: a `docs/MANUAL_CHECKS.md` with a ten-line checklist per area (board: arrows, Enter twice, Control+S, Escape twice; tactics: first move spoken, wrong move counted, Control+N twice, Control+R; endgames: question, judge speaks on a spoiled move, Backspace, Control+N; download: cancel mid-way, resume). The agent writes "manual checks needed: tactics, board" in the pull request and the human runs the list. Also: a `log.info("chessmart: ...")` prefix is already used consistently; say so in `AGENTS.md` so an agent can grep the NVDA log the human pastes.
- Size S. Risk none.

### 8. Reduce ambiguity an agent will trip on

- Today: `readme.md:97` promises a Backspace that does nothing (finding 5); `changelog.md` "To do" holds work items an agent might pick up without being asked; `pyproject.toml` says pyright strict while files say basic; three `# noqa` comments in Portuguese; `lib/` contains `old_time_control.py` and `asyncio_disabled/` whose purpose is not written anywhere; `theme_names.py` says the text is original for licence reasons, which an agent must not "improve" by copying Lichess.
- Change: fix or remove the README line; move "To do" out of the changelog into issues; align the pyright statement with reality (`typeCheckingMode = "basic"` and drop the per-file comments, or the reverse); a `lib/README.md` with one line per vendored package (source, version, why); a sentence in `AGENTS.md` about the theme-text licence rule.
- Size S. Risk none.
