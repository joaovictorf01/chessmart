# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Accuracy of each player over a game, computed the way Lichess does.

Transcribed from lila, modules/analyse/src/main/AccuracyPercent.scala, and the
helpers in lichess-org/scalalib Maths.scala. A move's accuracy comes from the
winning chance it gave away; a game's is the mean of two means of the
player's moves: one weighted by how volatile the position was around the
move, one harmonic (which punishes a single disaster). Free of NVDA imports;
checked against the accuracy Lichess published for a real game.
"""

import math
import statistics
import typing as t

from .engine_eval import Assessment
from .paths import import_bundled


with import_bundled():
	import chess


# The evaluation Lichess assumes for the starting position, in centipawns.
INITIAL_CENTIPAWNS = 15
# Winning chances are computed with evaluations clamped to 10 pawns; a mate counts as that ceiling.
CEILING = 1000


def win_percent(centipawns: float) -> float:
	"""0 to 100 for White, with the evaluation clamped to the ceiling (WinPercent.fromCentiPawns)."""
	clamped = max(-CEILING, min(CEILING, centipawns))
	return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * clamped)) - 1)


def as_centipawns(assessment: Assessment) -> float:
	"""A mate as the ceiling, for its side; centipawns as they are."""
	if assessment.mate is not None:
		return CEILING if assessment.mate > 0 else -CEILING
	assert assessment.centipawns is not None
	return assessment.centipawns


def move_accuracy(before: float, after: float) -> float:
	"""0 to 100 for one move, from the mover's winning chance before and after it."""
	if after >= before:
		return 100.0
	raw = 103.1668100711649 * math.exp(-0.04354415386753951 * (before - after)) - 3.166924740191411
	# Lichess adds one point for the imperfection of the analysis itself.
	return max(0.0, min(100.0, raw + 1))


def _windows(values: list[t.Optional[float]], size: int) -> list[list[t.Optional[float]]]:
	"""Scala's `sliding`: one window of the whole list when it is shorter than the size."""
	if len(values) <= size:
		return [values]
	return [values[start : start + size] for start in range(len(values) - size + 1)]


def game_accuracy(
	centipawns: t.Sequence[t.Optional[float]],
	start_color: bool = chess.WHITE,
	initial: float = INITIAL_CENTIPAWNS,
) -> dict[bool, t.Optional[float]]:
	"""Accuracy per colour; `centipawns` is White's evaluation after each move, None when unknown."""
	win_percents = [win_percent(initial)] + [None if cp is None else win_percent(cp) for cp in centipawns]
	size = max(2, min(8, len(centipawns) // 10))
	padding = max(0, min(size, len(win_percents)) - 2)
	windows = [win_percents[:size]] * padding + _windows(win_percents, size)
	weights = [
		None if any(value is None for value in window) else max(0.5, min(12.0, statistics.pstdev(window)))  # type: ignore[arg-type]
		for window in windows
	]
	per_color: dict[bool, list[tuple[float, float]]] = {chess.WHITE: [], chess.BLACK: []}
	for index, weight in enumerate(weights):
		if index + 1 >= len(win_percents):
			break
		previous, following = win_percents[index], win_percents[index + 1]
		color = chess.WHITE if (index % 2 == 0) == (start_color == chess.WHITE) else chess.BLACK
		if previous is None or following is None or weight is None:
			continue
		if color == chess.WHITE:
			accuracy = move_accuracy(previous, following)
		else:
			accuracy = move_accuracy(following, previous)
		per_color[color].append((accuracy, weight))
	return {color: _combine(moves) for color, moves in per_color.items()}


def _combine(moves: list[tuple[float, float]]) -> t.Optional[float]:
	if not moves:
		return None
	total_weight = sum(weight for _accuracy, weight in moves)
	if total_weight == 0:
		return None
	weighted = sum(accuracy * weight for accuracy, weight in moves) / total_weight
	harmonic = len(moves) / sum(1 / max(1.0, accuracy) for accuracy, _weight in moves)
	return (weighted + harmonic) / 2
