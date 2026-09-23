# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the analysis board says about the engine's numbers (README, "Engine analysis")."""

import unittest

from chessmart.analysis_words import MARK_KEYS, spoken_assessment, spoken_mark, spoken_pawns, spoken_verdict
from chessmart.engine_eval import Assessment, MoveVerdict
from chessmart.paths import import_bundled

with import_bundled():
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


if __name__ == "__main__":
	unittest.main()
