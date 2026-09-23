# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Accuracy per player, and the move judgments, against what Lichess published (README, "Game review").

The fixture is the analysis Lichess computed for a real 15+10 game (its 70
evaluations, the accuracy of each player, and the moves it called an
inaccuracy or a blunder). Our formulas, fed the same evaluations, must give
the same numbers.
"""

import json
import unittest
from pathlib import Path

from chessmart.accuracy import game_accuracy, move_accuracy, win_percent
from chessmart.engine_eval import Assessment, MoveReview, MoveVerdict
from chessmart.paths import import_bundled

with import_bundled():
	import chess

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "lichess" / "o9PtYEji_analysis.json"


def load():
	return json.loads(FIXTURE.read_text(encoding="utf-8"))


def centipawns(entry):
	if "mate" in entry:
		return 1000 if entry["mate"] > 0 else -1000
	return entry["eval"]


def assessment(entry):
	if "mate" in entry:
		return Assessment(centipawns=None, mate=entry["mate"])
	return Assessment(centipawns=entry["eval"], mate=None)


class FormulaTest(unittest.TestCase):
	def test_a_move_that_loses_nothing_is_100(self):
		self.assertEqual(move_accuracy(60, 60), 100.0)
		self.assertEqual(move_accuracy(60, 70), 100.0)

	def test_accuracy_falls_with_the_winning_chance_given_away(self):
		self.assertGreater(move_accuracy(60, 55), move_accuracy(60, 40))
		self.assertEqual(move_accuracy(100, 0), 0.0)

	def test_win_percent_is_clamped_at_ten_pawns(self):
		self.assertEqual(win_percent(1000), win_percent(5000))
		self.assertAlmostEqual(win_percent(0), 50.0)


class LichessGameTest(unittest.TestCase):
	def test_accuracy_matches_lichess(self):
		data = load()
		accuracy = game_accuracy([centipawns(entry) for entry in data["evals"]])
		# Lichess shows whole numbers: 87 for White, 96 for Black.
		self.assertEqual(round(accuracy[chess.WHITE]), data["accuracy"]["white"])
		self.assertEqual(round(accuracy[chess.BLACK]), data["accuracy"]["black"])

	def test_move_judgments_match_lichess(self):
		data = load()
		evals = [{"eval": 15}] + data["evals"]
		ours = []
		for ply in range(1, len(evals)):
			mover = chess.WHITE if ply % 2 == 1 else chess.BLACK
			review = MoveReview(
				mover=mover,
				played=assessment(evals[ply]),
				best=assessment(evals[ply - 1]),
				best_move=chess.Move.null(),
				played_move=chess.Move.from_uci("a1a2"),
			)
			verdict = review.verdict
			if verdict in (MoveVerdict.INACCURACY, MoveVerdict.MISTAKE, MoveVerdict.BLUNDER):
				ours.append((ply - 1, verdict.name.capitalize()))
		expected = [(index, name) for index, name in data["lichess_judgments"]]
		self.assertEqual(ours, expected)


if __name__ == "__main__":
	unittest.main()
