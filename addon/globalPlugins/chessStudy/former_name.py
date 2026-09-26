# coding: utf-8
# pyright: basic

"""Carrying the user's things over from the add-on's former name, Chessmart.

Until 2.0.0 the add-on was `chessmart`: its data folder, its section in NVDA's
configuration and its games folder in Documents were all named after it. NVDA
sees Chess Study as a different add-on, so none of that follows by itself.
Everything here is taken over once, and only when the new place is still empty.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path


FORMER_NAME = "chessmart"
FORMER_GAMES_FOLDER_NAME = "Chessmart"
GAMES_FOLDER_NAME = "Chess Study"


def adopt_renamed_folder(former: Path, current: Path) -> Path:
	"""The data folder to use: `current`, after taking over `former` once.

	The whole folder is renamed, so the 1.4 GB database and the tablebases cost
	nothing. If Windows refuses (the old add-on still installed and holding a
	file open), the old folder keeps being used as it is, and the rename is
	tried again on the next start.
	"""
	if current.exists() or not former.is_dir():
		return current
	try:
		former.rename(current)
	except OSError:
		return former
	return current


def carried_over_settings(
	former: Mapping[str, object],
	keys: Iterable[str],
	former_data_folder: Path,
	data_folder: Path,
) -> dict[str, str]:
	"""The former settings that still mean something, as NVDA stored them (text).

	A database chosen inside the former data folder now lives in the new one,
	so its path is moved along.
	"""
	settings = {key: str(former[key]) for key in keys if key in former}
	db_path = settings.get("tacticsDbPath", "").strip()
	if db_path:
		former_prefix = os.path.normcase(str(former_data_folder)) + os.sep
		if os.path.normcase(db_path).startswith(former_prefix):
			settings["tacticsDbPath"] = str(data_folder / db_path[len(former_prefix) :])
	return settings


def games_folder(documents: Path) -> Path:
	"""The default games folder: the former one while it holds the user's games and the new one doesn't exist."""
	current = documents / GAMES_FOLDER_NAME
	former = documents / FORMER_GAMES_FOLDER_NAME
	if former.is_dir() and not current.exists():
		return former
	return current
