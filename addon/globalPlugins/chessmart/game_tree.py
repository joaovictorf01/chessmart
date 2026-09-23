# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""A game being recorded or analysed: the main line, its variations and comments.

The analysis board (virtual_chessboard/analysis_board.py) keeps one of these and
a pointer into it; every key the user presses becomes one call here. It is free
of NVDA imports so the tree rules can be tested outside the screen reader.

The model is PGN's own: a move played where the line already continues with a
different move becomes a variation of that move, a comment belongs to the move
it follows, and the whole tree is written back as one PGN game.
"""

import dataclasses
import datetime
import enum
import os
import re
import typing as t

from .game_clock import annotations, plain_comment
from .paths import import_bundled


with import_bundled():
	import chess
	import chess.engine
	import chess.pgn


# The six move assessments of PGN, in the order they are offered: NAGs 1 to 6.
MOVE_MARK_SYMBOLS = {
	chess.pgn.NAG_GOOD_MOVE: "!",
	chess.pgn.NAG_MISTAKE: "?",
	chess.pgn.NAG_BRILLIANT_MOVE: "!!",
	chess.pgn.NAG_BLUNDER: "??",
	chess.pgn.NAG_SPECULATIVE_MOVE: "!?",
	chess.pgn.NAG_DUBIOUS_MOVE: "?!",
}
MOVE_MARKS = frozenset(MOVE_MARK_SYMBOLS)


class PlayResult(enum.Enum):
	# The line had no continuation: the move extends it.
	EXTENDED = "extended"
	# The move was already there (main line or a variation): the pointer follows it.
	FOLLOWED = "followed"
	# The line continued with another move: this one becomes a new variation.
	NEW_VARIATION = "new_variation"


class GameTree:
	def __init__(self, game: t.Optional["chess.pgn.Game"] = None):
		self.game = game if game is not None else chess.pgn.Game()
		self.node: "chess.pgn.GameNode" = self.game

	# -- where we are ---------------------------------------------------------

	def board(self) -> "chess.Board":
		"""The position at the pointer, with the move stack of the line that leads to it."""
		return self.node.board()

	@property
	def at_start(self) -> bool:
		return self.node.parent is None

	@property
	def at_end_of_line(self) -> bool:
		return not self.node.variations

	@property
	def in_variation(self) -> bool:
		return not self.node.is_mainline()

	@property
	def depth(self) -> int:
		"""How many variations deep the pointer is: 0 on the main line."""
		depth = 0
		node = self.node
		while node.parent is not None:
			if not node.is_main_variation():
				depth += 1
			node = node.parent
		return depth

	def starts_variation(self, node: t.Optional["chess.pgn.GameNode"] = None) -> bool:
		"""True if the node is the first move of a variation (not its parent's main continuation)."""
		node = self.node if node is None else node
		return node.parent is not None and not node.is_main_variation()

	def line_san(self) -> list[str]:
		"""The moves from the start to the pointer, in SAN, as the score sheet reads them."""
		nodes = []
		node = self.node
		while node.parent is not None:
			nodes.append(node)
			node = node.parent
		nodes.reverse()
		return [n.san() for n in nodes]

	def alternatives(self) -> list["chess.pgn.ChildNode"]:
		"""The moves recorded from this position: the continuation first, then its variations."""
		return list(self.node.variations)

	# -- moving the pointer ----------------------------------------------------

	def play(self, move: "chess.Move") -> PlayResult:
		existing = self.node.variation(move) if self.node.has_variation(move) else None
		if existing is not None:
			self.node = existing
			return PlayResult.FOLLOWED
		had_continuation = bool(self.node.variations)
		self.node = self.node.add_variation(move)
		return PlayResult.NEW_VARIATION if had_continuation else PlayResult.EXTENDED

	def add_line(
		self,
		moves: t.Sequence["chess.Move"],
		comment: str = "",
		score: t.Optional["chess.engine.PovScore"] = None,
		depth: t.Optional[int] = None,
	) -> t.Optional["chess.pgn.ChildNode"]:
		"""Records a line of moves from the pointer without moving it; the engine's line, typically.

		Moves already recorded are followed, and left as they are: their
		comments, clocks and marks are the player's. Returns the first move the
		line adds, or None when the whole line was already there. The comment
		and evaluation describe the position at the pointer, so they go on that
		first move only when the line branches right at the pointer; further
		down they would describe another position.
		"""
		node = self.node
		first_new = None
		for move in moves:
			if node.has_variation(move):
				node = node.variation(move)
				continue
			node = node.add_variation(move)
			if first_new is None:
				first_new = node
		if first_new is not None and first_new.parent is self.node:
			if comment:
				first_new.comment = comment
			if score is not None:
				first_new.set_eval(score, depth)
		return first_new

	def back(self) -> bool:
		if self.node.parent is None:
			return False
		self.node = self.node.parent
		return True

	def forward(self) -> bool:
		"""One move along the current line (the first continuation)."""
		if not self.node.variations:
			return False
		self.node = self.node.variations[0]
		return True

	def to_start(self) -> None:
		self.node = self.game

	def to_end_of_line(self) -> None:
		while self.node.variations:
			self.node = self.node.variations[0]

	def leave_variation(self) -> bool:
		"""Back to the position where the current variation branched off.

		From there, forward goes along the line the variation was an alternative to.
		Returns False on the main line, where there is nothing to leave.
		"""
		node = self.node
		while node.parent is not None and node.is_main_variation():
			node = node.parent
		if node.parent is None:
			return False
		self.node = node.parent
		return True

	# -- editing ---------------------------------------------------------------

	def delete_last_move(self) -> bool:
		"""Takes back the move at the pointer, if nothing was recorded after it.

		For fixing a move entered by mistake: only the end of a line can go, so a
		slip of the key never erases a variation or the rest of the game.
		"""
		if self.node.parent is None or self.node.variations:
			return False
		parent = self.node.parent
		parent.remove_variation(self.node)
		self.node = parent
		return True

	def promote_variation(self) -> bool:
		"""Makes the variation at the pointer the main continuation of its branch point."""
		node = self.node
		while node.parent is not None and node.is_main_variation():
			node = node.parent
		if node.parent is None:
			return False
		node.parent.promote_to_main(node)
		return True

	@property
	def comment(self) -> str:
		"""What the person wrote; `[%clk ...]` and other annotations are not part of it."""
		return plain_comment(self.node.comment)

	def set_comment(self, text: str) -> None:
		"""Replaces the written comment, keeping the annotations (clock, evaluation) that were there."""
		kept = annotations(self.node.comment)
		self.node.comment = " ".join(part for part in (text.strip(), kept) if part)

	@property
	def move_mark(self) -> t.Optional[int]:
		"""The move's assessment (!, ?, !!, ??, !?, ?!) as a PGN NAG, or None."""
		marks = self.node.nags & MOVE_MARKS
		return min(marks) if marks else None

	def set_move_mark(self, nag: t.Optional[int]) -> bool:
		"""A move carries at most one assessment: setting one replaces the other.

		`None` clears it. The start of the game has no move to mark.
		"""
		if self.node.parent is None:
			return False
		self.node.nags -= MOVE_MARKS
		if nag is not None:
			self.node.nags.add(nag)
		return True

	# -- headers and file ------------------------------------------------------

	def set_headers(self, **headers: str) -> None:
		for key, value in headers.items():
			value = value.strip()
			self.game.headers[key] = value or "?"

	def pgn_text(self) -> str:
		exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
		return self.game.accept(exporter) + "\n"


# -- the folder of recorded games -------------------------------------------------

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _name_part(text: str) -> str:
	text = _UNSAFE.sub(" ", text).strip().strip(".")
	return re.sub(r"\s+", "-", text)[:40]


def record_filename(date: datetime.date, white: str, black: str) -> str:
	"""`2026-09-23_White-vs-Black.pgn`: sorted by date in any file list, names readable.

	A name left blank is left out rather than written as `?`, which Windows refuses in a filename.
	"""
	names = [part for part in (_name_part(white), _name_part(black)) if part]
	if not names:
		return f"{date.isoformat()}.pgn"
	return "{date}_{names}.pgn".format(date=date.isoformat(), names="-vs-".join(names))


def unique_path(folder: str, filename: str) -> str:
	"""The path in the folder, with ` (2)`, ` (3)`... when the name is taken: two games a day happen."""
	base, extension = os.path.splitext(filename)
	candidate = os.path.join(folder, filename)
	number = 2
	while os.path.exists(candidate):
		candidate = os.path.join(folder, f"{base} ({number}){extension}")
		number += 1
	return candidate


def write_pgn(tree: GameTree, path: str) -> None:
	"""Writes to a temporary file first, so an interrupted save never leaves half a game."""
	temporary = path + ".tmp"
	with open(temporary, "w", encoding="utf-8", newline="\n") as file:
		file.write(tree.pgn_text())
	os.replace(temporary, path)


def pgn_date(date: datetime.date) -> str:
	return date.strftime("%Y.%m.%d")


@dataclasses.dataclass
class RecordHeaders:
	"""What the save dialog asks: who played, where, and the result."""

	white: str = ""
	black: str = ""
	event: str = ""
	date: datetime.date = dataclasses.field(default_factory=datetime.date.today)
	result: str = "*"

	def apply(self, tree: GameTree) -> None:
		tree.set_headers(
			Event=self.event,
			Date=pgn_date(self.date),
			White=self.white,
			Black=self.black,
		)
		tree.game.headers["Result"] = self.result or "*"
