# coding: utf-8
# pyright: basic

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ..former_name import FORMER_NAME, adopt_renamed_folder


PLUGIN_DIRECTORY = Path(__file__).resolve().parents[1]


def _user_data_directory() -> Path:
	"""Where the user's data lives: the puzzle database, the history and the cache.

	Inside NVDA it's `<NVDA config folder>/chessStudy`, like other add-ons do:
	the add-on folder is wiped and recreated on every update, and the player's
	history can't go along with it. Outside NVDA (tests, tools) it's `data/`
	next to the code, as it always was.
	"""
	try:
		import globalVars  # pyright: ignore[reportMissingImports] - NVDA module

		config_path = globalVars.appArgs.configPath
	except (ImportError, AttributeError):
		config_path = None
	if config_path:
		return adopt_renamed_folder(Path(config_path) / FORMER_NAME, Path(config_path) / "chessStudy")
	return PLUGIN_DIRECTORY / "data"


ADDON_DATA_DIRECTORY = _user_data_directory()
LEGACY_DATA_DIRECTORY = PLUGIN_DIRECTORY / "data"
# NVDA's Python does not ship `sqlite3`; the folder below carries the
# extension and the standard library package from CPython 3.13 x64 (see the README there).
SQLITE_RUNTIME_DIRECTORY = PLUGIN_DIRECTORY / "lib" / "sqlite3_runtime"

# Two files, on purpose. `puzzles.db` is the Lichess database: large,
# replaced wholesale on every update, and the one the user can point
# elsewhere. `tactic.db` is the player's history -- attempts, rating,
# progress -- and always lives in the add-on's data folder, untouched by any update.
PUZZLES_DB_NAME = "puzzles.db"
HISTORY_DB_NAME = "tactic.db"
HISTORY_DB_PATH = ADDON_DATA_DIRECTORY / HISTORY_DB_NAME
DEFAULT_DB_CANDIDATES = tuple(
	candidate
	for candidate in (
		os.environ.get("CHESS_STUDY_PUZZLES_DB_PATH"),
		str(ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME),
	)
	if candidate
)


def _ensure_sqlite3_importable() -> None:
	"""Make `import sqlite3` work inside NVDA.

	Outside NVDA (system Python, tests) the module already exists and nothing
	is done. Inside, the runtime folder is added to `sys.path` and to the DLL
	search path, so that `_sqlite3.pyd` finds the `sqlite3.dll` next to it.
	"""
	try:
		import sqlite3  # noqa: F401

		return
	except ImportError:
		pass
	runtime = str(SQLITE_RUNTIME_DIRECTORY)
	if runtime not in sys.path:
		sys.path.insert(0, runtime)
	if hasattr(os, "add_dll_directory"):
		os.add_dll_directory(runtime)
	import sqlite3  # noqa: F401


def _log(message: str) -> None:
	try:
		from logHandler import log  # pyright: ignore[reportMissingImports] - NVDA module
	except ImportError:
		print(message, file=sys.stderr)
	else:
		log.info(message)


def _move_legacy_data_if_needed() -> None:
	"""Move data from the old folder (inside the add-on) to the user's folder, once.

	Only moves what does not already exist at the destination; it's a rename,
	not a copy, so the 1.4 GB database costs nothing.
	"""
	if LEGACY_DATA_DIRECTORY == ADDON_DATA_DIRECTORY or not LEGACY_DATA_DIRECTORY.is_dir():
		return
	moved = []
	for name in ("puzzles.db", "tactic.db", "theme_catalog_cache.json", "manifest_url.txt"):
		source = LEGACY_DATA_DIRECTORY / name
		target = ADDON_DATA_DIRECTORY / name
		if source.is_file() and not target.exists():
			ADDON_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
			try:
				source.replace(target)
				moved.append(name)
			except OSError:
				continue
	for backup in LEGACY_DATA_DIRECTORY.glob("tactic.backup-*.db"):
		target = ADDON_DATA_DIRECTORY / backup.name
		if not target.exists():
			try:
				backup.replace(target)
			except OSError:
				continue
	if moved:
		_log(
			f"chessStudy: data moved from {LEGACY_DATA_DIRECTORY} to {ADDON_DATA_DIRECTORY}: {', '.join(moved)}",
		)


def _split_legacy_if_needed() -> None:
	"""Split the old `tactic.db` (puzzles + history in a single file), once.

	Happens on the first open after an update, and only when `puzzles.db`
	does not exist yet. The history gets a dated backup alongside it.
	"""
	puzzles_path = ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME
	if not HISTORY_DB_PATH.is_file():
		return
	store = load_store()
	if not store.has_puzzles_table(HISTORY_DB_PATH):
		return
	if puzzles_path.exists():
		# A puzzle database already exists (downloaded before the split ran):
		# the history just needs to drop the puzzles table it's carrying.
		backup = store.slim_legacy_history(HISTORY_DB_PATH)
		_log(
			f"chessStudy: puzzles table removed from {HISTORY_DB_PATH.name}; history backup at {backup.name}",
		)
		return
	backup = store.split_legacy_database(HISTORY_DB_PATH, puzzles_path, HISTORY_DB_PATH)
	_repoint_theme_catalog_cache(HISTORY_DB_PATH, puzzles_path)
	_log(
		f"chessStudy: tactic.db split into {puzzles_path.name} and {HISTORY_DB_PATH.name}; "
		f"history backup at {backup.name}",
	)


def _repoint_theme_catalog_cache(old_path: Path, new_path: Path) -> None:
	"""Make the theme cache follow the renamed file.

	The cache signature stores the database's path, size and date. After the
	split the path changes, and without this the first open would redo the
	scan of millions of puzzles with NVDA frozen. The themes are the same;
	only the envelope needs to follow along.
	"""
	cache_path = ADDON_DATA_DIRECTORY / "theme_catalog_cache.json"
	if not cache_path.is_file():
		return
	try:
		payload = json.loads(cache_path.read_text(encoding="utf-8"))
		if payload.get("dbPath") != str(old_path.resolve()):
			return
		stat = new_path.stat()
		payload.update(dbPath=str(new_path.resolve()), dbSize=stat.st_size, dbModifiedNs=stat.st_mtime_ns)
		cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
	except (OSError, ValueError):
		# The cache is a convenience; if it can't be adjusted, it rebuilds itself.
		return


def load_store():
	"""The `store` module, with `sqlite3` guaranteed to be importable first.

	`store.py` imports `sqlite3` at the top, and inside NVDA that only works
	once the runtime folder is on the path. That's why nothing imports it
	directly: it always goes through here, at the point of use, so the rest
	of the add-on still loads on a machine where SQLite is missing.
	"""
	_ensure_sqlite3_importable()
	from . import store

	return store


def is_puzzles_database(db_path: Path) -> bool:
	"""Say whether the file is a puzzle database (has the `puzzles` table)."""
	return load_store().has_puzzles_table(db_path)


def resolve_default_db_path() -> Path | None:
	"""The puzzle database in use, or None if there isn't one yet."""
	_move_legacy_data_if_needed()
	_split_legacy_if_needed()
	for candidate in DEFAULT_DB_CANDIDATES:
		db_path = Path(candidate)
		if db_path.is_file():
			return db_path
	return None
