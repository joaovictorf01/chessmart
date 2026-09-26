# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The clock of a game, read from the PGN: what was left after each move, and what each move took.

Lichess writes `[%clk 0:14:52]` after every move: the time left once the move
was made, increment already added. With the `TimeControl` tag ("900+10") the
time a move took is the clock before it, plus the increment, minus the clock
after it. Free of NVDA imports; the analysis board speaks what this computes.
"""

import dataclasses
import re
import typing as t

from .paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


# The time trouble line of the player's own routine: under a minute on the clock.
TIME_TROUBLE_SECONDS = 60

_ANNOTATION = re.compile(r"\[%[^\]]*\]")


@dataclasses.dataclass(frozen=True)
class TimeControl:
	initial: int
	increment: int


@dataclasses.dataclass(frozen=True)
class MoveClock:
	ply: int
	color: bool
	san: str
	# Seconds left after the move.
	left: float
	# Seconds the move took; None when it cannot be known (no time control).
	spent: t.Optional[float]

	@property
	def move_number(self) -> int:
		return (self.ply + 1) // 2


@dataclasses.dataclass(frozen=True)
class ClockSummary:
	"""One side's clock over the game."""

	color: bool
	lowest: t.Optional[MoveClock]
	# The first move made with less than a minute left; None if it never happened.
	first_in_time_trouble: t.Optional[MoveClock]
	longest_think: t.Optional[MoveClock]


def parse_time_control(value: t.Optional[str]) -> t.Optional[TimeControl]:
	"""`900+10` -> 900 s and 10 s; anything else (`-`, `?`, correspondence `1/86400`) -> None."""
	match = re.fullmatch(r"\s*(\d+)\+(\d+)\s*", value or "")
	if match is None:
		return None
	return TimeControl(initial=int(match.group(1)), increment=int(match.group(2)))


def annotations(comment: str) -> str:
	"""Only the `[%...]` annotations of a comment, in their order."""
	return " ".join(_ANNOTATION.findall(comment))


def plain_comment(comment: str) -> str:
	"""The comment as a person wrote it, without `[%clk ...]`, `[%eval ...]` and other annotations."""
	return re.sub(r"\s+", " ", _ANNOTATION.sub("", comment)).strip()


def move_clocks(game: "chess.pgn.Game") -> list[MoveClock]:
	"""Every main-line move that carries a clock, with the time it took when that can be known."""
	control = parse_time_control(game.headers.get("TimeControl"))
	previous: dict[bool, t.Optional[float]] = {chess.WHITE: None, chess.BLACK: None}
	if control is not None:
		previous = {chess.WHITE: float(control.initial), chess.BLACK: float(control.initial)}
	clocks = []
	board = game.board()
	for ply, node in enumerate(game.mainline(), start=1):
		color = board.turn
		san = board.san(node.move)
		board.push(node.move)
		left = node.clock()
		if left is None:
			continue
		before = previous[color]
		spent = None
		if control is not None and before is not None:
			spent = max(0.0, before + control.increment - left)
		previous[color] = left
		clocks.append(MoveClock(ply=ply, color=color, san=san, left=left, spent=spent))
	return clocks


def node_clock(node: "chess.pgn.GameNode") -> t.Optional[tuple[float, t.Optional[float]]]:
	"""(left, spent) for one move of the tree, or None when it carries no clock.

	`spent` needs the same side's previous clock (two plies up) or, for its
	first move, the initial time; None when that is not known.
	"""
	left = node.clock()
	if left is None or node.parent is None:
		return None
	game = node.game()
	control = parse_time_control(game.headers.get("TimeControl"))
	if control is None:
		return left, None
	before_node = node.parent.parent
	if before_node is None or before_node.parent is None:
		before = float(control.initial)
	else:
		before = before_node.clock()
		if before is None:
			return left, None
	return left, max(0.0, before + control.increment - left)


def summarize(clocks: t.Sequence[MoveClock], color: bool) -> ClockSummary:
	own = [clock for clock in clocks if clock.color == color]
	timed = [clock for clock in own if clock.spent is not None]
	return ClockSummary(
		color=color,
		lowest=min(own, key=lambda clock: clock.left) if own else None,
		first_in_time_trouble=next((clock for clock in own if clock.left < TIME_TROUBLE_SECONDS), None),
		longest_think=max(timed, key=lambda clock: clock.spent or 0.0) if timed else None,
	)


def format_clock(seconds: float) -> str:
	"""`14:52`, `0:48`, `1:02:05`: how a chess clock shows it, whole seconds."""
	total = int(seconds)
	hours, rest = divmod(total, 3600)
	minutes, secs = divmod(rest, 60)
	if hours:
		return f"{hours}:{minutes:02d}:{secs:02d}"
	return f"{minutes}:{secs:02d}"
