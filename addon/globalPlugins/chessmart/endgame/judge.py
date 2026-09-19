# coding: utf-8
# pyright: basic

"""O juiz: a tablebase traduzida em veredito.

WDL diz se a posição é ganha, empatada ou perdida para quem joga; DTZ, em
quantos lances (meios-lances na tabela) vem o próximo lance irreversível --
peão, captura ou mate -- com jogo perfeito. O juiz compara o veredito antes e
depois de um lance e diz quando o resultado mudou de mão: é isso que ensina
"o que empata e o que não empata" na hora, não depois.

Ganho "amaldiçoado" (mate forçado, mas empate pela regra dos 50 lances) conta
como empate aqui: é o que vale na mesa.
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
	"""O que a tabela diz de uma posição, para o lado que joga."""

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
		"""DTZ em lances inteiros, arredondado para cima."""
		return math.ceil(abs(self.dtz) / 2)

	def for_color(self, color: chess.Color, turn: chess.Color) -> "Verdict":
		"""O mesmo veredito visto por `color`, dado de quem é a vez."""
		if color is turn:
			return self
		return Verdict(-self.wdl, -self.dtz)


def probe(tablebase: "chess.syzygy.Tablebase | None", board: chess.Board) -> Verdict | None:
	"""Veredito para o lado que joga; None sem tabela para o material, ou com peças demais."""
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
		"""O lance piorou o resultado: ganho que virou empate ou perda, empate que virou perda."""
		order = {WIN: 2, DRAW: 1, LOSS: 0}
		return order[self.after.result] < order[self.before.result]


def judge_move(
	tablebase: "chess.syzygy.Tablebase | None",
	board_before: chess.Board,
	move: chess.Move,
) -> MoveVerdict | None:
	"""Compara o veredito do lado que jogou antes e depois de `move`."""
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
	verdict: Verdict  # para quem joga, depois do lance


def rate_moves(tablebase: "chess.syzygy.Tablebase | None", board: chess.Board) -> tuple[RatedMove, ...]:
	"""Todos os lances legais com o veredito para quem joga, do melhor ao pior.

	Melhor: maior WDL; entre ganhos, menor DTZ (o caminho mais curto); entre
	perdas, maior DTZ (a resistência mais longa). Vazio sem tabela.
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
	"""Os lances que mantêm o melhor resultado, os mais curtos primeiro."""
	rated = rate_moves(tablebase, board)
	if not rated:
		return ()
	top = rated[0].verdict
	return tuple(item.move for item in rated if item.verdict.wdl == top.wdl and item.verdict.dtz == top.dtz)


# ---------------------------------------------------------------- fala


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
	"""O que dizer quando o lance mudou o resultado; None se não mudou."""
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
