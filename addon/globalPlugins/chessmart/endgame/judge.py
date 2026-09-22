# coding: utf-8
# pyright: basic

"""The judge: the tablebase translated into a verdict.

WDL says whether the position is won, drawn or lost for the side to move;
DTZ, in how many moves (half-moves in the table) the next irreversible
move -- pawn move, capture or mate -- comes with perfect play. The judge
compares the verdict before and after a move and says when the result
changed hands: that's what teaches "what draws and what doesn't" on the
spot, not after the fact.

A "cursed" win (forced mate, but a draw under the fifty-move rule) counts
as a draw here: that's what holds at the board.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Iterable

from ..i18n import _
from ..paths import import_bundled
from .tablebase import MAX_PIECES

with import_bundled():
	import chess
	import chess.syzygy


WIN, DRAW, LOSS = "win", "draw", "loss"


@dataclasses.dataclass(frozen=True)
class Verdict:
	"""What the table says about a position, for the side to move."""

	wdl: int
	dtz: int

	@property
	def result(self) -> str:
		if self.wdl == 2:
			return WIN
		if self.wdl == -2:
			return LOSS
		return DRAW

	@property
	def moves(self) -> int:
		"""DTZ in whole moves, rounded up."""
		return math.ceil(abs(self.dtz) / 2)

	def for_color(self, color: chess.Color, turn: chess.Color) -> "Verdict":
		"""The same verdict as seen by `color`, given whose turn it is."""
		if color is turn:
			return self
		return Verdict(-self.wdl, -self.dtz)


def probe(tablebase: "chess.syzygy.Tablebase | None", board: chess.Board) -> Verdict | None:
	"""Verdict for the side to move; None with no table for this material, or with too many pieces."""
	if tablebase is None or board.uci_variant != "chess" or chess.popcount(board.occupied) > MAX_PIECES:
		return None
	try:
		wdl = tablebase.probe_wdl(board)
		dtz = tablebase.probe_dtz(board)
	except (chess.syzygy.MissingTableError, KeyError, OSError, IndexError):
		return None
	return Verdict(wdl, dtz)


@dataclasses.dataclass(frozen=True)
class MoveVerdict:
	move: chess.Move
	before: Verdict
	after: Verdict

	@property
	def spoiled(self) -> bool:
		"""The move made the result worse: a win that became a draw or loss, a draw that became a loss."""
		order = {WIN: 2, DRAW: 1, LOSS: 0}
		return order[self.after.result] < order[self.before.result]


def judge_move(
	tablebase: "chess.syzygy.Tablebase | None",
	board_before: chess.Board,
	move: chess.Move,
) -> MoveVerdict | None:
	"""Compare the verdict for the side to move before and after `move`."""
	before = probe(tablebase, board_before)
	if before is None:
		return None
	board_after = board_before.copy(stack=False)
	board_after.push(move)
	after_for_opponent = probe(tablebase, board_after)
	if after_for_opponent is None:
		return None
	after = after_for_opponent.for_color(board_before.turn, board_after.turn)
	return MoveVerdict(move=move, before=before, after=after)


@dataclasses.dataclass(frozen=True)
class RatedMove:
	move: chess.Move
	verdict: Verdict  # for the side to move, after the move


def rate_moves(tablebase: "chess.syzygy.Tablebase | None", board: chess.Board) -> tuple[RatedMove, ...]:
	"""All legal moves with the verdict for the side to move, best to worst.

	Best: highest WDL; among wins, lowest DTZ (the shortest path); among
	losses, highest DTZ (the longest resistance). Empty without a table.
	"""
	rated = []
	mover = board.turn
	for move in board.legal_moves:
		after = board.copy(stack=False)
		after.push(move)
		verdict = probe(tablebase, after)
		if verdict is None:
			return ()
		rated.append(RatedMove(move, verdict.for_color(mover, after.turn)))

	def key(item: RatedMove):
		wdl, dtz = item.verdict.wdl, item.verdict.dtz
		return (-wdl, dtz if wdl > 0 else -dtz)

	return tuple(sorted(rated, key=key))


def best_moves(tablebase: "chess.syzygy.Tablebase | None", board: chess.Board) -> tuple[chess.Move, ...]:
	"""The moves that hold the best result, the shortest ones first."""
	rated = rate_moves(tablebase, board)
	if not rated:
		return ()
	top = rated[0].verdict
	return tuple(item.move for item in rated if item.verdict.wdl == top.wdl and item.verdict.dtz == top.dtz)


# ---------------------------------------------------------------- speech


def describe_verdict(verdict: Verdict, color_name: str) -> str:
	"""'white wins in 7 moves', 'draw', 'white loses in 12 moves'."""
	if verdict.result == WIN:
		# Translators: Tablebase verdict, e.g. "white wins: 7 moves to the next capture, pawn move or mate".
		return _("{color} wins: {moves} moves to the next pawn move, capture or mate.").format(
			color=color_name,
			moves=verdict.moves,
		)
	if verdict.result == LOSS:
		# Translators: Tablebase verdict, e.g. "white loses: 12 moves ..." (moves the losing side can hold on).
		return _("{color} loses: {moves} moves of resistance at most.").format(
			color=color_name,
			moves=verdict.moves,
		)
	if verdict.wdl != 0:
		# Translators: Tablebase verdict for a cursed win or blessed loss.
		return _("Draw by the fifty-move rule: the mate exists, but it takes too long.")
	# Translators: Tablebase verdict.
	return _("Draw.")


def describe_spoiled(move_verdict: MoveVerdict) -> str | None:
	"""What to say when the move changed the result; None if it didn't."""
	if not move_verdict.spoiled:
		return None
	before, after = move_verdict.before.result, move_verdict.after.result
	if before == WIN and after == DRAW:
		# Translators: Spoken by the tablebase judge after a move that turned a win into a draw.
		return _("That move let the win slip: the position is now a draw.")
	if before == WIN and after == LOSS:
		# Translators: Spoken by the tablebase judge after a move that turned a win into a loss.
		return _("That move turned a won position into a lost one.")
	# Translators: Spoken by the tablebase judge after a move that turned a draw into a loss.
	return _("That move lost the draw: the position is now lost.")


def result_names() -> dict[str, str]:
	return {
		# Translators: One of the answers to "win or draw?".
		WIN: _("Win"),
		# Translators: One of the answers to "win or draw?".
		DRAW: _("Draw"),
		# Translators: One of the answers to "win or draw?".
		LOSS: _("Loss"),
	}


def sans(board: chess.Board, moves: Iterable[chess.Move]) -> list[str]:
	return [board.san(move) for move in moves]
