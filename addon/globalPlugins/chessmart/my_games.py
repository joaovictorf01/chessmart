# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""My Games: the games in the games folder, the most recently changed first.

The folder is already the player's archive: games saved from the analysis
board and games imported from Lichess all land there. This lists them with
what matters when choosing one to open -- date, players, result, and how much
of it the player has already annotated. No NVDA here; the dialog only shows
the lines and opens the chosen game.
"""

from __future__ import annotations

import dataclasses
import os
import typing as t

from .game_clock import plain_comment
from .i18n import _
from .paths import import_bundled
from .pgn import PGN_ENCODING, PGN_ERRORS, PGNGameInfo

with import_bundled():
	import chess.pgn


@dataclasses.dataclass(frozen=True)
class Notes:
	"""What the player added to a game: comments they wrote, marks, and variations."""

	comments: int = 0
	marks: int = 0
	variations: int = 0

	@property
	def empty(self) -> bool:
		return not (self.comments or self.marks or self.variations)


@dataclasses.dataclass(frozen=True)
class SavedGame:
	info: PGNGameInfo
	notes: Notes
	# Games in the same file: a file with one game is saved back in place,
	# a game out of a collection is saved as a new file.
	games_in_file: int
	modified: float

	@property
	def single_game_file(self) -> bool:
		return self.games_in_file == 1

	def description(self) -> str:
		date = self.info.date.replace(".", "-")
		if "?" in date:
			# Translators: In My Games, for a game whose date is unknown.
			date = _("no date")
		# Translators: A game in My Games, e.g. "2026-09-23, victorf01 versus dheekshan2020, Black won.".
		line = _("{date}, {players}, {result}.").format(
			date=date,
			players=self.info.players,
			result=self.info.result,
		)
		if self.notes.empty:
			# Translators: In My Games, after a game the player has not annotated.
			notes = _("No notes.")
		else:
			# Translators: In My Games, what the player added to a game, e.g. "Comments: 12, marks: 4, variations: 2.".
			notes = _("Comments: {comments}, marks: {marks}, variations: {variations}.").format(
				comments=self.notes.comments,
				marks=self.notes.marks,
				variations=self.notes.variations,
			)
		return f"{line} {notes}"


def count_notes(game: chess.pgn.Game) -> Notes:
	"""Count across the whole tree, variations included. Clock and engine annotations are not the player's notes."""
	comments = marks = variations = 0
	stack: list[chess.pgn.GameNode] = [game]
	while stack:
		node = stack.pop()
		if node is not game:
			if plain_comment(node.comment):
				comments += 1
			if node.nags:
				marks += 1
		variations += max(0, len(node.variations) - 1)
		stack.extend(node.variations)
	return Notes(comments=comments, marks=marks, variations=variations)


def _games_in(path: str) -> list[tuple[PGNGameInfo, Notes]]:
	games = []
	with open(path, "r", encoding=PGN_ENCODING, errors=PGN_ERRORS) as file:
		while True:
			offset = file.tell()
			game = chess.pgn.read_game(file)
			if game is None:
				break
			info = PGNGameInfo(filename=path, offset=offset, **PGNGameInfo.args_from_headers(game.headers))
			games.append((info, count_notes(game)))
	return games


def list_saved_games(folder: str) -> tuple[list[SavedGame], list[str]]:
	"""Every game in the folder's PGN files, newest file first, and the files that could not be read.

	Only the folder itself, not its subfolders: that is where the add-on saves.
	"""
	saved: list[SavedGame] = []
	unreadable: list[str] = []
	try:
		names = os.listdir(folder)
	except OSError:
		return saved, unreadable
	for name in names:
		path = os.path.join(folder, name)
		if not name.lower().endswith(".pgn") or not os.path.isfile(path):
			continue
		try:
			modified = os.path.getmtime(path)
			games = _games_in(path)
		except (OSError, UnicodeDecodeError, ValueError):
			unreadable.append(name)
			continue
		saved.extend(SavedGame(info, notes, len(games), modified) for info, notes in games)
	saved.sort(key=lambda game: (-game.modified, game.info.filename, game.info.offset or 0))
	return saved, sorted(unreadable)


def choices(games: t.Sequence[SavedGame]) -> list[str]:
	return [game.description() for game in games]
