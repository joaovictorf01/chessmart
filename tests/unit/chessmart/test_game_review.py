# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Reviewing a whole game (README, "Game review").

The engine is not run here: each position gets a made-up evaluation, and the
tests check what the review keeps from it: whose moves, from which verdict up,
how many, in which order, and that opening theory is left alone.
"""

import io
import unittest

from chessmart.engine_eval import Assessment, MoveVerdict
from chessmart.game_review import (
	PositionEval,
	ReviewOptions,
	ReviewProgress,
	Side,
	accuracy_by_color,
	critical_moments,
	mainline_nodes,
	review_moves,
	same_line,
	still_in_game,
)
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.pgn

# Off the book from the first move, so theory does not interfere unless asked.
MOVES = "1. a3 h6 2. b3 g6 3. c3 f6 4. d3 e6 *"


def game(text: str = MOVES) -> "chess.pgn.Game":
	parsed = chess.pgn.read_game(io.StringIO(text))
	assert parsed is not None
	return parsed


def evals_for(g: "chess.pgn.Game", scores: list[int]) -> list[PositionEval]:
	"""One evaluation per position; the best move is always a quiet one that was not played."""
	evaluations = []
	for node, score in zip(mainline_nodes(g), scores):
		board = node.board()
		following = node.next()
		best = next((move for move in board.legal_moves if following is None or move != following.move), None)
		evaluations.append(PositionEval(Assessment(centipawns=score, mate=None), best))
	return evaluations


# Positions: start, after a3, h6, b3, g6, c3, f6, d3, e6.
# White loses 150 with 2. b3 (0 -> -150) and 60 with 4. d3; Black loses 300 with 2... g6.
SCORES = [0, 0, 0, -150, 150, 150, 150, 90, 90]


class ReviewTest(unittest.TestCase):
	def test_one_evaluation_per_position_is_required(self):
		with self.assertRaises(ValueError):
			review_moves(game(), [], ReviewOptions(), chess.WHITE)

	def test_only_my_moves_by_default(self):
		g = game()
		moments = review_moves(g, evals_for(g, SCORES), ReviewOptions(skip_theory=False), chess.WHITE)
		self.assertEqual({moment.mover for moment in moments}, {chess.WHITE})
		self.assertEqual(len(moments), 4)

	def test_both_sides(self):
		g = game()
		options = ReviewOptions(side=Side.BOTH, skip_theory=False)
		self.assertEqual(len(review_moves(g, evals_for(g, SCORES), options, chess.WHITE)), 8)

	def test_verdicts_come_from_the_evaluations(self):
		g = game()
		options = ReviewOptions(side=Side.BOTH, skip_theory=False)
		moments = review_moves(g, evals_for(g, SCORES), options, chess.WHITE)
		verdicts = {moment.node.san(): moment.review.verdict for moment in moments}
		self.assertEqual(verdicts["b3"], MoveVerdict.MISTAKE)
		self.assertEqual(verdicts["g6"], MoveVerdict.BLUNDER)
		self.assertEqual(verdicts["d3"], MoveVerdict.INACCURACY)
		self.assertEqual(verdicts["a3"], MoveVerdict.GOOD)

	def test_theory_is_skipped(self):
		g = game("1. e4 e5 2. Nf3 Nc6 *")
		moments = review_moves(g, evals_for(g, [0, 0, 0, 0, 0]), ReviewOptions(side=Side.BOTH), chess.WHITE)
		self.assertEqual(moments, [])

	def test_a_mating_move_is_judged_on_the_final_position(self):
		g = game("1. f3 e5 2. g4 Qh4# 0-1")
		evaluations: list = evals_for(g, [0, 0, 0, 0, 0])
		evaluations[-1] = None  # the game is over after Qh4#
		evaluations[3] = PositionEval(Assessment(centipawns=None, mate=-1), chess.Move.from_uci("d8h4"))
		moments = review_moves(g, evaluations, ReviewOptions(side=Side.BOTH, skip_theory=False), chess.WHITE)
		qh4 = next(moment for moment in moments if moment.node.san() == "Qh4#")
		self.assertEqual(qh4.review.verdict, MoveVerdict.BEST)


class ChangedGameTest(unittest.TestCase):
	def test_a_move_played_after_the_review_started_is_noticed(self):
		g = game()
		nodes = mainline_nodes(g)
		self.assertTrue(same_line(g, nodes))
		g.end().add_main_variation(chess.Move.from_uci("h2h3"))
		self.assertFalse(same_line(g, nodes))

	def test_a_promoted_variation_of_the_same_length_is_noticed(self):
		g = game()
		nodes = mainline_nodes(g)
		last = g.end()
		sibling = last.parent.add_variation(chess.Move.from_uci("e7e5"))  # type: ignore[union-attr]
		last.parent.promote_to_main(sibling)  # type: ignore[union-attr]
		self.assertFalse(same_line(g, nodes))

	def test_a_moment_taken_back_is_no_longer_in_the_game(self):
		g = game()
		options = ReviewOptions(side=Side.BOTH, skip_theory=False)
		moments = critical_moments(review_moves(g, evals_for(g, SCORES), options, chess.WHITE), options)
		g6 = next(moment for moment in moments if moment.node.san() == "g6")
		self.assertTrue(still_in_game(g6))
		g6.node.parent.remove_variation(g6.node)  # type: ignore[union-attr]
		self.assertFalse(still_in_game(g6))


class AccuracyTest(unittest.TestCase):
	def test_a_blunder_costs_its_side_accuracy(self):
		g = game()
		accuracy = accuracy_by_color(g, evals_for(g, SCORES))
		assert accuracy[chess.WHITE] is not None and accuracy[chess.BLACK] is not None
		# Black gave away 300 centipawns with 2... g6; White 150 and 60.
		self.assertLess(accuracy[chess.BLACK], 100)
		self.assertLess(accuracy[chess.WHITE], 100)

	def test_a_finished_game_counts_its_result(self):
		g = game("1. f3 e5 2. g4 Qh4# 0-1")
		evaluations: list = evals_for(g, [0, 0, 0, -1000, 0])
		evaluations[-1] = None
		accuracy = accuracy_by_color(g, evaluations)
		self.assertIsNotNone(accuracy[chess.WHITE])


class CriticalMomentsTest(unittest.TestCase):
	def moments(self, **options):
		g = game()
		review = ReviewOptions(side=Side.BOTH, skip_theory=False, **options)
		return critical_moments(review_moves(g, evals_for(g, SCORES), review, chess.WHITE), review)

	def test_mistakes_and_blunders_by_default(self):
		self.assertEqual([moment.node.san() for moment in self.moments()], ["b3", "g6"])

	def test_everything_from_inaccuracies(self):
		sans = [moment.node.san() for moment in self.moments(threshold=MoveVerdict.INACCURACY)]
		self.assertEqual(sans, ["b3", "g6", "d3"])

	def test_only_blunders(self):
		self.assertEqual(
			[moment.node.san() for moment in self.moments(threshold=MoveVerdict.BLUNDER)], ["g6"]
		)

	def test_the_cap_keeps_the_worst_then_orders_by_move(self):
		sans = [moment.node.san() for moment in self.moments(threshold=MoveVerdict.INACCURACY, max_moments=2)]
		self.assertEqual(sans, ["b3", "g6"])
		self.assertEqual([moment.move_number for moment in self.moments(max_moments=1)], [2])


if __name__ == "__main__":
	unittest.main()


class TestReviewProgress(unittest.TestCase):
	def run_through(self, mode, total=84, **kwargs):
		progress = ReviewProgress(mode=mode, **kwargs)
		beeps, spoken = [], []
		for done in range(1, total + 1):
			beep, percent = progress.update(done, total)
			if beep is not None:
				beeps.append(beep)
			if percent is not None:
				spoken.append(percent)
		return beeps, spoken

	def test_beep_mode_beeps_every_position_and_rises(self):
		beeps, spoken = self.run_through("beep")
		self.assertEqual(len(beeps), 84)
		self.assertEqual(beeps, sorted(beeps))
		self.assertEqual(spoken, [])

	def test_speak_mode_says_each_quarter_but_not_the_end(self):
		beeps, spoken = self.run_through("speak")
		self.assertEqual((beeps, spoken), ([], [25, 50, 75]))

	def test_both_and_off(self):
		beeps, spoken = self.run_through("both")
		self.assertEqual((len(beeps), spoken), (84, [25, 50, 75]))
		self.assertEqual(self.run_through("off"), ([], []))

	def test_beep_interval_is_respected(self):
		beeps, _ = self.run_through("beep", total=200, beep_interval=10)
		self.assertEqual(len(beeps), 10)

	def test_an_unknown_mode_speaks(self):
		self.assertEqual(self.run_through("future-mode")[1], [25, 50, 75])
