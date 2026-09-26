# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The review of a whole game: which moves were the critical moments.

Every position of the main line is evaluated once; the evaluation of a
position is the "after" of the move that reached it and the "before" of the
next one. Each move is then judged by Lichess's rules (engine_eval.MoveReview)
and the options decide what is kept: whose moves, from which verdict up, how
many. Free of NVDA imports; the engine runs elsewhere and hands in
`PositionEval`s.
"""

import dataclasses
import enum
import typing as t

from .accuracy import as_centipawns, game_accuracy
from .engine_eval import Assessment, MoveReview, MoveVerdict
from .openings import lookup
from .paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


class Side(enum.Enum):
	MINE = "mine"
	BOTH = "both"


class Reveal(enum.Enum):
	# Only say where the move went wrong: finding the better one is the exercise.
	NOTHING = "nothing"
	# Also say the engine's move.
	MOVE = "move"
	# Also add the engine's line as a variation.
	LINE = "line"


# Verdicts in increasing order of seriousness; a threshold keeps it and everything above.
SEVERITY = (MoveVerdict.INACCURACY, MoveVerdict.MISTAKE, MoveVerdict.BLUNDER)


@dataclasses.dataclass(frozen=True)
class ReviewOptions:
	side: Side = Side.MINE
	threshold: MoveVerdict = MoveVerdict.MISTAKE
	# None keeps every critical moment.
	max_moments: t.Optional[int] = 5
	reveal: Reveal = Reveal.NOTHING
	seconds: float = 1.0
	skip_theory: bool = True


@dataclasses.dataclass(frozen=True)
class PositionEval:
	"""The engine's view of one position; None for a position where the game is over."""

	assessment: Assessment
	best_move: t.Optional["chess.Move"]
	line: tuple["chess.Move", ...] = ()
	depth: int = 0


@dataclasses.dataclass(frozen=True)
class Moment:
	"""A critical moment: the move, how it was judged, and the engine's view before it."""

	node: "chess.pgn.ChildNode"
	review: MoveReview
	before: PositionEval

	@property
	def ply(self) -> int:
		return self.node.ply()

	@property
	def move_number(self) -> int:
		return (self.ply + 1) // 2

	@property
	def mover(self) -> bool:
		return self.review.mover


def mainline_nodes(game: "chess.pgn.Game") -> list["chess.pgn.GameNode"]:
	"""The start and every main-line position: what the engine evaluates, in order."""
	return [game, *game.mainline()]


def same_line(game: "chess.pgn.Game", nodes: t.Sequence["chess.pgn.GameNode"]) -> bool:
	"""Whether the main line is still exactly `nodes`: nothing played, taken back or promoted since."""
	current = mainline_nodes(game)
	return len(current) == len(nodes) and all(a is b for a, b in zip(current, nodes))


def still_in_game(moment: "Moment") -> bool:
	"""Whether the moment's move is still on the main line (a take-back or a promotion may have removed it)."""
	node = moment.node
	parent = node.parent
	return parent is not None and any(child is node for child in parent.variations) and node.is_mainline()


def _final_assessment(board: "chess.Board") -> Assessment:
	"""A finished position: mate for the side that gave it, level for a draw."""
	outcome = board.outcome()
	assert outcome is not None
	if outcome.winner is None:
		return Assessment(centipawns=0, mate=None)
	return Assessment(centipawns=None, mate=1 if outcome.winner == chess.WHITE else -1)


def review_moves(
	game: "chess.pgn.Game",
	evaluations: t.Sequence[t.Optional[PositionEval]],
	options: ReviewOptions,
	my_color: bool,
) -> list[Moment]:
	"""Every move worth reviewing, judged; `evaluations` follows `mainline_nodes(game)`."""
	nodes = mainline_nodes(game)
	if len(evaluations) != len(nodes):
		raise ValueError("one evaluation per main-line position, the start included")
	moments = []
	for index in range(1, len(nodes)):
		node = nodes[index]
		assert node.move is not None, "every main-line node after the start carries its move"
		before = evaluations[index - 1]
		if before is None or before.best_move is None:
			continue
		board_before = nodes[index - 1].board()
		mover = board_before.turn
		if options.side is Side.MINE and mover != my_color:
			continue
		board_after = node.board()
		if options.skip_theory and lookup(board_after) is not None:
			continue
		after = evaluations[index]
		if node.move == before.best_move:
			played = before.assessment
		elif after is None:
			played = _final_assessment(board_after)
		else:
			played = after.assessment
		review = MoveReview(
			mover=mover,
			played=played,
			best=before.assessment,
			best_move=before.best_move,
			played_move=node.move,
		)
		moments.append(Moment(node=node, review=review, before=before))  # type: ignore[arg-type]
	return moments


def critical_moments(moments: t.Sequence[Moment], options: ReviewOptions) -> list[Moment]:
	"""The moves at or above the threshold, the worst first when capped, then in game order."""
	floor = SEVERITY.index(options.threshold)
	kept = [
		moment
		for moment in moments
		if moment.review.verdict in SEVERITY and SEVERITY.index(moment.review.verdict) >= floor
	]
	if options.max_moments is not None and len(kept) > options.max_moments:
		kept.sort(
			key=lambda moment: (SEVERITY.index(moment.review.verdict), moment.review.lost_chance),
			reverse=True,
		)
		kept = kept[: options.max_moments]
	return sorted(kept, key=lambda moment: moment.ply)


def accuracy_by_color(
	game: "chess.pgn.Game",
	evaluations: t.Sequence[t.Optional[PositionEval]],
) -> dict[bool, t.Optional[float]]:
	"""Each player's accuracy over the main line, from the review's evaluations (Lichess's formula).

	A finished position has no engine evaluation; it counts as its result
	(mate for the winner, level for a draw).
	"""
	nodes = mainline_nodes(game)
	centipawns: list[t.Optional[float]] = []
	for node, evaluation in zip(nodes[1:], evaluations[1:]):
		if evaluation is not None:
			centipawns.append(as_centipawns(evaluation.assessment))
		elif node.board().is_game_over():
			centipawns.append(as_centipawns(_final_assessment(node.board())))
		else:
			centipawns.append(None)
	start_color = nodes[0].board().turn
	return game_accuracy(centipawns, start_color=start_color)


@dataclasses.dataclass
class ReviewProgress:
	"""What to play and say while the review runs, following NVDA's own progress bar setting.

	`mode` is NVDA's "Progress bar output": beep, speak, both or off. The beep
	rises with the percentage the way NVDA's progress bars do; the speech says
	every quarter, as a sentence. Anything unknown speaks, as the review always did.
	"""

	mode: str = "speak"
	beep_interval: float = 1.0
	speech_step: int = 25
	_beeped: t.Optional[float] = None
	_spoken: int = 0

	def update(self, done: int, total: int) -> tuple[t.Optional[float], t.Optional[int]]:
		"""(percent to beep, or None; percent to say, or None) after `done` of `total` positions."""
		if total <= 0:
			return None, None
		percent = done * 100 / total
		mode = self.mode if self.mode in ("beep", "speak", "both", "off") else "speak"
		beep = None
		if mode in ("beep", "both") and (
			self._beeped is None or percent - self._beeped >= self.beep_interval
		):
			self._beeped = percent
			beep = percent
		speak = None
		step = int(percent) // self.speech_step * self.speech_step
		if mode in ("speak", "both") and step > self._spoken and percent < 100:
			self._spoken = step
			speak = step
		return beep, speak
