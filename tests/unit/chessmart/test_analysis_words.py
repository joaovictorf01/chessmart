# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the analysis board says about the engine's numbers (README, "Engine analysis")."""

import unittest

from chessmart.analysis_words import (
	MARK_KEYS,
	spoken_accuracy,
	spoken_assessment,
	spoken_clock_summary,
	spoken_mark,
	spoken_move_clock,
	spoken_pawns,
	spoken_verdict,
)
from chessmart.game_clock import ClockSummary, MoveClock
from chessmart.engine_eval import Assessment, MoveVerdict
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.pgn


class PawnsTest(unittest.TestCase):
	def test_sign_and_one_decimal(self):
		self.assertEqual(spoken_pawns(37), "plus 0.4")
		self.assertEqual(spoken_pawns(-130), "minus 1.3")

	def test_zero_has_no_sign(self):
		self.assertEqual(spoken_pawns(3), "0.0")


class AssessmentTest(unittest.TestCase):
	def test_equal(self):
		self.assertEqual(spoken_assessment(Assessment(centipawns=10, mate=None)), "equal, plus 0.1")

	def test_bands_name_the_side(self):
		self.assertEqual(spoken_assessment(Assessment(50, None)), "white slightly better, plus 0.5")
		self.assertEqual(spoken_assessment(Assessment(-140, None)), "black clearly better, minus 1.4")
		self.assertEqual(spoken_assessment(Assessment(420, None)), "white winning, plus 4.2")

	def test_mate(self):
		self.assertEqual(spoken_assessment(Assessment(None, -3)), "black mates in 3")


class MarksTest(unittest.TestCase):
	def test_control_keys_follow_the_pgn_order(self):
		self.assertEqual(MARK_KEYS[0], chess.pgn.NAG_GOOD_MOVE)
		self.assertEqual(MARK_KEYS[5], chess.pgn.NAG_DUBIOUS_MOVE)

	def test_marks_and_verdicts_are_words(self):
		self.assertEqual(spoken_mark(chess.pgn.NAG_SPECULATIVE_MOVE), "interesting move")
		self.assertEqual(spoken_verdict(MoveVerdict.BLUNDER), "blunder")


class AccuracyWordsTest(unittest.TestCase):
	def test_mine_first(self):
		accuracy = {chess.WHITE: 86.6, chess.BLACK: 95.7}
		self.assertEqual(spoken_accuracy(accuracy, chess.BLACK), "Your accuracy 96 percent, opponent 87.")

	def test_unknown_says_nothing(self):
		self.assertEqual(spoken_accuracy({chess.WHITE: None, chess.BLACK: 90.0}, chess.BLACK), "")


class ClockTest(unittest.TestCase):
	def test_move_clock(self):
		self.assertEqual(spoken_move_clock(892, 25), "clock 14:52, took 0:25")
		self.assertEqual(spoken_move_clock(48, 12), "clock 0:48, took 0:12, under a minute")
		self.assertEqual(spoken_move_clock(892, None), "clock 14:52")

	def test_summary(self):
		qxg5 = MoveClock(ply=10, color=chess.BLACK, san="Qxg5", left=50, spent=866)
		qd8 = MoveClock(ply=12, color=chess.BLACK, san="Qd8", left=41, spent=19)
		summary = ClockSummary(color=chess.BLACK, lowest=qd8, first_in_time_trouble=qxg5, longest_think=qxg5)
		self.assertEqual(
			spoken_clock_summary(summary),
			"black: under a minute from move 5; lowest clock 0:41 at move 6; longest think 5... Qxg5, 14:26.",
		)

	def test_summary_without_clock(self):
		empty = ClockSummary(color=chess.WHITE, lowest=None, first_in_time_trouble=None, longest_think=None)
		self.assertEqual(spoken_clock_summary(empty), "white: no clock")


if __name__ == "__main__":
	unittest.main()
