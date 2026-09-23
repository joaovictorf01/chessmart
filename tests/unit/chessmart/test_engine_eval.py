# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the engine's numbers become (README, "Engine analysis").

The bands and the winning-chance curve decide what the user hears and which
mark is suggested, so their edges are pinned here.
"""

import unittest

from chessmart.engine_eval import (
	Advantage,
	Assessment,
	MoveReview,
	MoveVerdict,
)
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.engine
	import chess.pgn


def cp(value: int) -> Assessment:
	return Assessment(centipawns=value, mate=None)


class AssessmentTest(unittest.TestCase):
	def test_bands_and_symbols(self):
		self.assertEqual((cp(0).advantage, cp(0).symbol), (Advantage.EQUAL, "="))
		self.assertEqual(cp(25).symbol, "=")
		self.assertEqual(cp(40).symbol, "+=")
		self.assertEqual(cp(-40).symbol, "=+")
		self.assertEqual(cp(150).symbol, "±")
		self.assertEqual(cp(-150).symbol, "∓")
		self.assertEqual(cp(350).symbol, "+-")
		self.assertEqual(cp(-350).symbol, "-+")

	def test_mate_is_winning_for_the_side_that_mates(self):
		self.assertEqual(Assessment(centipawns=None, mate=3).symbol, "+-")
		self.assertEqual(Assessment(centipawns=None, mate=-2).side_ahead, chess.BLACK)

	def test_from_engine_score_is_from_whites_point_of_view(self):
		score = chess.engine.PovScore(chess.engine.Cp(120), chess.BLACK)
		self.assertEqual(Assessment.from_score(score).centipawns, -120)

	def test_written_to_pgn_as_lichess_reads_it(self):
		node = chess.pgn.Game().add_variation(chess.Move.from_uci("e2e4"))
		node.set_eval(cp(-42).to_pov_score(), 20)
		self.assertIn("[%eval -0.42,20]", node.comment)
		self.assertEqual(node.eval().white().score(), -42)
		node.set_eval(Assessment(None, 3).to_pov_score(), 25)
		self.assertIn("[%eval #3,25]", node.comment)

	def test_pawns_are_rounded_to_one_decimal(self):
		self.assertEqual(cp(37).pawns, 0.4)
		self.assertEqual(cp(-130).pawns, -1.3)

	def test_band_edges(self):
		# The upper bound of each band belongs to it; one centipawn more is the next band.
		self.assertEqual(cp(75).symbol, "+=")
		self.assertEqual(cp(76).symbol, "±")
		self.assertEqual(cp(200).symbol, "±")
		self.assertEqual(cp(201).symbol, "+-")
		self.assertEqual(cp(-201).symbol, "-+")

	def test_win_chance_matches_lichess(self):
		# Lichess (ui/ceval winningChances): 2 / (1 + exp(-0.00368208 * cp)) - 1, from -1 to 1.
		# At +100 that is 0.18203, which is 59.10 on the 0 to 100 scale used here.
		self.assertAlmostEqual(cp(100).win_chance(chess.WHITE), 59.10, places=2)
		self.assertAlmostEqual(cp(-300).win_chance(chess.WHITE), 24.89, places=2)

	def test_win_chance_is_fifty_at_zero_and_symmetric(self):
		self.assertAlmostEqual(cp(0).win_chance(chess.WHITE), 50.0)
		self.assertAlmostEqual(cp(300).win_chance(chess.WHITE) + cp(300).win_chance(chess.BLACK), 100.0)
		self.assertGreater(cp(300).win_chance(chess.WHITE), 75)


class MoveReviewTest(unittest.TestCase):
	def review(self, best_cp, played_cp, mover=chess.WHITE, same_move=False):
		best_move = chess.Move.from_uci("e2e4")
		played_move = best_move if same_move else chess.Move.from_uci("a2a3")
		return MoveReview(
			mover=mover,
			played=cp(played_cp),
			best=cp(best_cp),
			best_move=best_move,
			played_move=played_move,
		)

	def test_the_engine_move_is_best(self):
		self.assertEqual(self.review(30, 30, same_move=True).verdict, MoveVerdict.BEST)

	def test_losing_a_pawn_in_a_level_position_is_an_inaccuracy(self):
		# 50 -> 41 points of winning chance, as Lichess counts it.
		review = self.review(0, -100)
		self.assertEqual(review.verdict, MoveVerdict.INACCURACY)
		self.assertEqual(review.suggested_mark, chess.pgn.NAG_DUBIOUS_MOVE)

	def test_losing_a_pawn_and_a_half_in_a_level_position_is_a_mistake(self):
		review = self.review(0, -150)
		self.assertEqual(review.verdict, MoveVerdict.MISTAKE)
		self.assertEqual(review.suggested_mark, chess.pgn.NAG_MISTAKE)

	def test_verdict_edges_follow_lichess(self):
		# From a level position, how many centipawns lose 5, 10 and 15 points of winning chance.
		self.assertEqual(self.review(0, -54).verdict, MoveVerdict.GOOD)  # 4.95 points lost
		self.assertEqual(self.review(0, -56).verdict, MoveVerdict.INACCURACY)  # 5.14
		self.assertEqual(self.review(0, -110).verdict, MoveVerdict.INACCURACY)  # 9.99
		self.assertEqual(self.review(0, -120).verdict, MoveVerdict.MISTAKE)  # 10.87
		self.assertEqual(self.review(0, -166).verdict, MoveVerdict.MISTAKE)  # 14.82
		self.assertEqual(self.review(0, -170).verdict, MoveVerdict.BLUNDER)  # 15.16

	def mate_review(self, best, played, mover=chess.WHITE):
		return MoveReview(
			mover=mover,
			played=played,
			best=best,
			best_move=chess.Move.from_uci("e2e4"),
			played_move=chess.Move.from_uci("a2a3"),
		)

	def test_walking_into_mate_from_a_level_position_is_a_blunder(self):
		self.assertEqual(self.mate_review(cp(0), Assessment(None, -3)).verdict, MoveVerdict.BLUNDER)

	def test_walking_into_mate_when_already_lost_counts_less(self):
		# Lichess: already 7 pawns down, a mistake; more than 10 down, an inaccuracy.
		self.assertEqual(self.mate_review(cp(-800), Assessment(None, -3)).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(cp(-1200), Assessment(None, -3)).verdict, MoveVerdict.INACCURACY)

	def test_letting_a_forced_mate_go(self):
		self.assertEqual(self.mate_review(Assessment(None, 2), cp(300)).verdict, MoveVerdict.BLUNDER)
		self.assertEqual(self.mate_review(Assessment(None, 2), cp(800)).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(Assessment(None, 2), cp(1500)).verdict, MoveVerdict.INACCURACY)

	def test_mate_rule_edges_follow_lichess(self):
		# Advice.scala: "< -700" and "< -999" before the move, "> 700" and "> 999" after it.
		mated = Assessment(None, -3)
		self.assertEqual(self.mate_review(cp(-700), mated).verdict, MoveVerdict.BLUNDER)
		self.assertEqual(self.mate_review(cp(-701), mated).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(cp(-999), mated).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(cp(-1000), mated).verdict, MoveVerdict.INACCURACY)
		mating = Assessment(None, 2)
		self.assertEqual(self.mate_review(mating, cp(700)).verdict, MoveVerdict.BLUNDER)
		self.assertEqual(self.mate_review(mating, cp(701)).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(mating, cp(999)).verdict, MoveVerdict.MISTAKE)
		self.assertEqual(self.mate_review(mating, cp(1000)).verdict, MoveVerdict.INACCURACY)

	def test_a_slower_mate_is_not_marked(self):
		self.assertEqual(self.mate_review(Assessment(None, 2), Assessment(None, 5)).verdict, MoveVerdict.GOOD)

	def test_mate_rules_are_from_the_movers_side(self):
		# Black walks into mate: White mates, which is a positive mate from White's side.
		self.assertEqual(
			self.mate_review(cp(0), Assessment(None, 4), mover=chess.BLACK).verdict,
			MoveVerdict.BLUNDER,
		)

	def test_losing_a_pawn_a_rook_up_hardly_matters(self):
		self.assertEqual(self.review(600, 500).verdict, MoveVerdict.GOOD)

	def test_throwing_away_a_won_position_is_a_blunder(self):
		review = self.review(400, -100)
		self.assertEqual(review.verdict, MoveVerdict.BLUNDER)
		self.assertEqual(review.suggested_mark, chess.pgn.NAG_BLUNDER)

	def test_half_a_pawn_in_a_level_position_is_still_good(self):
		self.assertEqual(self.review(0, -50).verdict, MoveVerdict.GOOD)

	def test_verdict_is_from_the_movers_side(self):
		# Black to move: going from -100 (Black better) to +50 gave away chances.
		self.assertEqual(self.review(-100, 50, mover=chess.BLACK).verdict, MoveVerdict.MISTAKE)

	def test_a_better_than_expected_move_loses_nothing(self):
		self.assertEqual(self.review(0, 40).lost_chance, 0.0)


if __name__ == "__main__":
	unittest.main()
