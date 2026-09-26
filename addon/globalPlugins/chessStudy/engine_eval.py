# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the engine's numbers mean, in the words and marks a player uses.

Free of NVDA imports so the thresholds can be tested. Two scales:

* The position: centipawns (hundredths of a pawn, White's point of view) turned
  into the usual assessment symbols: = equal, += / =+ slightly better,
  ± / ∓ clearly better, +- / -+ winning.
* A move: judged the way Lichess's computer analysis does (lila,
  modules/tree/src/main/Advice.scala; scalachess, eval.scala). Losing a pawn
  in a level position is serious; losing one when a rook up hardly matters.
  So centipawns become a winning chance and the drop of that chance decides
  the mark. Lichess measures the chance from -1 to 1 and calls a drop of 0.1
  an inaccuracy (?!), 0.2 a mistake (?), 0.3 a blunder (??); on the 0 to 100
  scale used here that is 5, 10 and 15 points. Mates have their own rule:
  walking into a forced mate, or letting one's own forced mate go, is a
  blunder, a mistake when the position was already lost (or still won) by
  more than 7 pawns, an inaccuracy past 10.
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


# Lichess's constant: a winning chance curve fitted to its own games (lila pull 11148).
_WIN_CURVE = 0.00368208
# Lichess's ceiling: a mate counts as 10 pawns when turned into a winning chance.
_MATE_AS_CP = 1000


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

	def to_pov_score(self) -> "chess.engine.PovScore":
		"""Back to python-chess's score, for `GameNode.set_eval` ([%eval ...] in the PGN)."""
		if self.mate is not None:
			return chess.engine.PovScore(chess.engine.Mate(self.mate), chess.WHITE)
		assert self.centipawns is not None
		return chess.engine.PovScore(chess.engine.Cp(self.centipawns), chess.WHITE)

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
			cp = self.centipawns
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

	def _pov(self, assessment: Assessment) -> tuple[t.Optional[int], t.Optional[int]]:
		"""(centipawns, mate) from the mover's side: positive is good for the mover."""
		sign = 1 if self.mover == chess.WHITE else -1
		cp = None if assessment.centipawns is None else sign * assessment.centipawns
		mate = None if assessment.mate is None else sign * assessment.mate
		return cp, mate

	def _mate_verdict(self) -> t.Optional[MoveVerdict]:
		"""Lichess's MateAdvice; None when no mate changed hands and centipawns decide."""
		best_cp, best_mate = self._pov(self.best)
		played_cp, played_mate = self._pov(self.played)
		if best_mate is None and played_mate is not None and played_mate < 0:
			# Walked into a forced mate.
			before = best_cp or 0
			if before < -999:
				return MoveVerdict.INACCURACY
			if before < -700:
				return MoveVerdict.MISTAKE
			return MoveVerdict.BLUNDER
		if best_mate is not None and best_mate > 0 and (played_mate is None or played_mate < 0):
			# Let a forced mate go.
			after = played_cp or 0
			if after > 999:
				return MoveVerdict.INACCURACY
			if after > 700:
				return MoveVerdict.MISTAKE
			return MoveVerdict.BLUNDER
		if best_mate is not None or played_mate is not None:
			# A slower mate, or still being mated: Lichess marks nothing.
			return MoveVerdict.GOOD
		return None

	@property
	def lost_chance(self) -> float:
		"""Points of winning chance the move gave away, never below zero."""
		return max(0.0, self.best.win_chance(self.mover) - self.played.win_chance(self.mover))

	@property
	def verdict(self) -> MoveVerdict:
		if self.is_best:
			return MoveVerdict.BEST
		mate_verdict = self._mate_verdict()
		if mate_verdict is not None:
			return mate_verdict
		lost = self.lost_chance
		for bound, verdict in VERDICT_BANDS:
			if lost < bound:
				return verdict
		return MoveVerdict.BLUNDER

	@property
	def suggested_mark(self) -> t.Optional[int]:
		return VERDICT_MARKS.get(self.verdict)


# No draw by agreement in the opening: before this move number (the board's
# fullmove counter, as a custom FEN sets it) the engine declines every offer.
ENGINE_DRAW_MIN_FULLMOVE = 20


def engine_accepts_draw(
	score: t.Optional["chess.engine.PovScore"],
	engine_color: bool,
	fullmove_number: int,
) -> bool:
	"""Whether the engine takes a draw offer, judged by its own score of the position.

	The way chess programs usually answer: yes when the position is level
	(Advantage.EQUAL, within a quarter of a pawn) or better for the other
	side, no when the engine is ahead. Never before move
	ENGINE_DRAW_MIN_FULLMOVE, and never with no score (the engine sent none):
	a draw is not given away on a guess.
	"""
	if fullmove_number < ENGINE_DRAW_MIN_FULLMOVE or score is None:
		return False
	return Assessment.from_score(score).side_ahead != engine_color


def threat_position(board: "chess.Board") -> t.Optional["chess.Board"]:
	"""The position with the move handed to the other side: its best move there is the threat.

	None when the game is over, or when the side to move is in check: passing
	would leave its king in check with the other side to move, which the
	validity check refuses. The en passant square goes, since passing gives no
	pawn the right to it.
	"""
	if board.is_game_over():
		return None
	passed = board.copy(stack=False)
	passed.turn = not passed.turn
	passed.ep_square = None
	if not passed.is_valid():
		return None
	return passed
