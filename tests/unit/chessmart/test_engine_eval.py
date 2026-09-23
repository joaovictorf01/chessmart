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
	numbered_line,
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

	def test_pawns_are_rounded_to_one_decimal(self):
		self.assertEqual(cp(37).pawns, 0.4)
		self.assertEqual(cp(-130).pawns, -1.3)

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


class NumberedLineTest(unittest.TestCase):
	def test_line_from_white(self):
		board = chess.Board()
		moves = [chess.Move.from_uci(u) for u in ("e2e4", "e7e5", "g1f3")]
		self.assertEqual(numbered_line(board, moves), ["1.", "e4", "e5", "2.", "Nf3"])

	def test_line_from_black_starts_with_ellipsis(self):
		board = chess.Board()
		board.push_san("e4")
		moves = [chess.Move.from_uci(u) for u in ("c7c5", "g1f3")]
		self.assertEqual(numbered_line(board, moves), ["1...", "c5", "2.", "Nf3"])

	def test_line_is_cut_at_the_limit(self):
		board = chess.Board()
		moves = [chess.Move.from_uci(u) for u in ("e2e4", "e7e5", "g1f3", "b8c6")]
		self.assertEqual(len([w for w in numbered_line(board, moves, limit=2) if not w.endswith(".")]), 2)


if __name__ == "__main__":
	unittest.main()
