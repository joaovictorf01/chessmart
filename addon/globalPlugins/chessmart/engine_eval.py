# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the engine's numbers mean, in the words and marks a player uses.

Free of NVDA imports so the thresholds can be tested. Two scales:

* The position: centipawns (hundredths of a pawn, White's point of view) turned
  into the usual assessment symbols: = equal, += / =+ slightly better,
  ± / ∓ clearly better, +- / -+ winning.
* A move: how much winning chance it gave away, as Lichess judges it. Losing a
  pawn in a level position is serious; losing one when a rook up hardly
  matters. So centipawns become a winning chance (Lichess's formula) and the
  drop of that chance decides the mark. Lichess measures the chance from -1 to
  1 and calls a drop of 0.1 an inaccuracy (?!), 0.2 a mistake (?), 0.3 a
  blunder (??); on the 0 to 100 scale used here that is 5, 10 and 15 points.
"""

import dataclasses
import enum
import math
import typing as t

from .paths import import_bundled


with import_bundled():
	import chess
	import chess.engine
	import chess.pgn


# Lichess's constant: a winning chance curve fitted to its own games.
_WIN_CURVE = 0.00368208
# A mate is worth this much when turned into centipawns (only for the curve).
_MATE_AS_CP = 10000


class Advantage(enum.IntEnum):
	EQUAL = 0
	SLIGHT = 1
	CLEAR = 2
	WINNING = 3


# Upper bounds, in centipawns, of each band; above the last one it is winning.
ADVANTAGE_BANDS = ((25, Advantage.EQUAL), (75, Advantage.SLIGHT), (200, Advantage.CLEAR))

# Symbols for (advantage, side ahead). Equal has no side.
ADVANTAGE_SYMBOLS = {
	(Advantage.SLIGHT, chess.WHITE): "+=",
	(Advantage.SLIGHT, chess.BLACK): "=+",
	(Advantage.CLEAR, chess.WHITE): "±",
	(Advantage.CLEAR, chess.BLACK): "∓",
	(Advantage.WINNING, chess.WHITE): "+-",
	(Advantage.WINNING, chess.BLACK): "-+",
}


@dataclasses.dataclass(frozen=True)
class Assessment:
	"""One evaluation of a position, from White's point of view."""

	centipawns: t.Optional[int]
	# Moves to mate: positive when White mates, negative when Black does.
	mate: t.Optional[int]

	@classmethod
	def from_score(cls, score: "chess.engine.PovScore") -> "Assessment":
		white = score.white()
		return cls(centipawns=white.score(), mate=white.mate())

	@property
	def side_ahead(self) -> t.Optional[bool]:
		if self.mate is not None:
			return chess.WHITE if self.mate > 0 else chess.BLACK
		assert self.centipawns is not None
		if self.advantage is Advantage.EQUAL:
			return None
		return chess.WHITE if self.centipawns > 0 else chess.BLACK

	@property
	def advantage(self) -> Advantage:
		if self.mate is not None:
			return Advantage.WINNING
		assert self.centipawns is not None
		size = abs(self.centipawns)
		for bound, advantage in ADVANTAGE_BANDS:
			if size <= bound:
				return advantage
		return Advantage.WINNING

	@property
	def symbol(self) -> str:
		side = self.side_ahead
		if side is None:
			return "="
		return ADVANTAGE_SYMBOLS[(self.advantage, side)]

	@property
	def pawns(self) -> t.Optional[float]:
		"""The evaluation in pawns, one decimal, as players say it: +0.4, -1.3."""
		return None if self.centipawns is None else round(self.centipawns / 100, 1)

	def win_chance(self, color: bool) -> float:
		"""0 to 100: how likely `color` is to win from here, by Lichess's curve."""
		if self.mate is not None:
			cp = _MATE_AS_CP if self.mate > 0 else -_MATE_AS_CP
		else:
			assert self.centipawns is not None
			cp = max(-_MATE_AS_CP, min(_MATE_AS_CP, self.centipawns))
		white = 50 + 50 * (2 / (1 + math.exp(-_WIN_CURVE * cp)) - 1)
		return white if color == chess.WHITE else 100 - white


class MoveVerdict(enum.Enum):
	BEST = "best"
	GOOD = "good"
	INACCURACY = "inaccuracy"
	MISTAKE = "mistake"
	BLUNDER = "blunder"


# Lichess's thresholds on the drop of winning chance, in points of 0 to 100.
VERDICT_BANDS = ((5, MoveVerdict.GOOD), (10, MoveVerdict.INACCURACY), (15, MoveVerdict.MISTAKE))

# The mark a verdict suggests; good and best moves carry none.
VERDICT_MARKS = {
	MoveVerdict.INACCURACY: chess.pgn.NAG_DUBIOUS_MOVE,
	MoveVerdict.MISTAKE: chess.pgn.NAG_MISTAKE,
	MoveVerdict.BLUNDER: chess.pgn.NAG_BLUNDER,
}


@dataclasses.dataclass(frozen=True)
class MoveReview:
	"""A played move against the engine's best from the same position."""

	mover: bool
	played: Assessment
	best: Assessment
	best_move: "chess.Move"
	played_move: "chess.Move"

	@property
	def is_best(self) -> bool:
		return self.played_move == self.best_move

	@property
	def lost_chance(self) -> float:
		"""Points of winning chance the move gave away, never below zero."""
		return max(0.0, self.best.win_chance(self.mover) - self.played.win_chance(self.mover))

	@property
	def verdict(self) -> MoveVerdict:
		if self.is_best:
			return MoveVerdict.BEST
		lost = self.lost_chance
		for bound, verdict in VERDICT_BANDS:
			if lost < bound:
				return verdict
		return MoveVerdict.BLUNDER

	@property
	def suggested_mark(self) -> t.Optional[int]:
		return VERDICT_MARKS.get(self.verdict)


def numbered_line(board: "chess.Board", moves: t.Sequence["chess.Move"], limit: int = 6) -> list[str]:
	"""The engine's line as a player reads it: `12. Nf3 Nc6 13. Bb5`, at most `limit` moves."""
	board = board.copy(stack=False)
	words = []
	for index, move in enumerate(moves[:limit]):
		if board.turn == chess.WHITE:
			words.append(f"{board.fullmove_number}.")
		elif index == 0:
			words.append(f"{board.fullmove_number}...")
		words.append(board.san(move))
		board.push(move)
	return words
