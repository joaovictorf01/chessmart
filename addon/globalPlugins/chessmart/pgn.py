# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Reading games out of a PGN file: the list of games, and one game's moves.

Free of NVDA imports so the parsing can be tested outside the screen reader.
PGN files come from anywhere (a download, an e-mail attachment), so nothing
here assumes a well-formed file: missing headers, odd results and non-UTF-8
bytes all produce a readable description rather than an exception.
"""

import dataclasses
import typing as t

from .i18n import _
from .paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


# Latin-1 is still common in PGN files from older tools and Windows programs;
# `errors="replace"` keeps the game readable (the moves are ASCII) at the
# cost of a replacement character in a name.
PGN_ENCODING = "utf-8"
PGN_ERRORS = "replace"


@dataclasses.dataclass
class PGNGameInfo:
	result: str
	white: str
	black: str
	date: str
	event: str
	site: str
	termination: t.Optional[str]
	filename: str
	offset: t.Optional[int] = 0

	@classmethod
	def args_from_headers(cls, headers):
		return dict(
			result=cls.parse_pgn_result_string(headers.get("Result", "")),
			white=headers.get("White", "?"),
			black=headers.get("Black", "?"),
			date=headers.get("Date", "????.??.??"),
			event=headers.get("Event", "?"),
			site=headers.get("Site", "?"),
			termination=headers.get("Termination"),
		)

	@classmethod
	def game_info_from_pgn_filename(cls, filename):
		with open(filename, "r", encoding=PGN_ENCODING, errors=PGN_ERRORS) as file:
			while True:
				offset = file.tell()
				headers = chess.pgn.read_headers(file)
				if headers is None:
					break
				yield cls(filename=filename, offset=offset, **cls.args_from_headers(headers))

	@property
	def players(self):
		"""Both players, e.g. "Kasparov versus Karpov"."""
		# Translators: The two players of a PGN game, white first.
		return _("{white} versus {black}").format(white=self.white, black=self.black)

	@property
	def description(self):
		return " ".join(
			[
				f"{self.players},",
				f"{self.event},",
				f" - {self.date}",
			],
		)

	@staticmethod
	def parse_pgn_result_string(result_string):
		"""The spoken result for a PGN `Result` tag; never raises, whatever the tag holds."""
		result_string = result_string.strip()
		if result_string == "*":
			# Translators: Result of a PGN game that has no result yet.
			return _("Game not finished")
		scores = [s.strip() for s in result_string.split("-")]
		if len(scores) == 2:
			w_score, b_score = scores
			if w_score == "1" and b_score == "0":
				# Translators: Result of a PGN game.
				return _("White won")
			elif w_score == "0" and b_score == "1":
				# Translators: Result of a PGN game.
				return _("Black won")
			elif w_score == b_score and w_score in ("1/2", "½"):
				# Translators: Result of a PGN game.
				return _("Game ended in a draw")
		# Translators: Result of a PGN game whose Result tag is missing or not understood.
		return _("Unknown result")


@dataclasses.dataclass
class PGNGame:
	game_obj: chess.pgn.Game
	moves: t.Tuple[chess.Move, ...]
	info: PGNGameInfo

	@classmethod
	def from_game_info(cls, info):
		with open(info.filename, "r", encoding=PGN_ENCODING, errors=PGN_ERRORS) as file:
			file.seek(info.offset)
			game = chess.pgn.read_game(file)
			if game is None:
				raise ValueError(f"no game at offset {info.offset} of {info.filename}")
			return cls(game_obj=game, moves=tuple(g.move for g in game.mainline()), info=info)

	def get_board(self):
		return self.game_obj.board()
