# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Spoken move notation, in the styles used by Lichess's blind mode."""

import unittest

from chessStudy.notation import ANNA, LITERATE, NATO, SAN, UCI, render_san, render_square


class TestRenderSan(unittest.TestCase):
	def test_plain_knight_move_in_every_style(self):
		self.assertEqual(render_san("Nf3", "g1f3", SAN), "Nf3")
		self.assertEqual(render_san("Nf3", "g1f3", UCI), "g1f3")
		self.assertEqual(render_san("Nf3", "g1f3", LITERATE), "knight f 3")
		self.assertEqual(render_san("Nf3", "g1f3", NATO), "knight foxtrot 3")
		self.assertEqual(render_san("Nf3", "g1f3", ANNA), "knight felix 3")

	def test_capture_promotion_check_and_mate_are_spelled_out(self):
		self.assertEqual(render_san("exd5", "e4d5", ANNA), "eva takes david 5")
		self.assertEqual(render_san("b8=Q+", "b7b8q", LITERATE), "b 8 promotion queen check")
		self.assertEqual(render_san("b8=Q+", "b7b8q", SAN), "b8=Q check")
		self.assertEqual(render_san("Ra8#", "a1a8", ANNA), "rook anna 8 checkmate")

	def test_disambiguation_keeps_both_files(self):
		self.assertEqual(render_san("Ngf3", "g1f3", ANNA), "knight gustav felix 3")

	def test_castling_is_named_not_spelled(self):
		self.assertEqual(render_san("O-O", "e1g1", SAN), "short castling")
		self.assertEqual(render_san("O-O-O+", "e1c1", ANNA), "long castling check")

	def test_empty_san_gives_empty_speech(self):
		self.assertEqual(render_san("", "", ANNA), "")


class TestRenderSquare(unittest.TestCase):
	def test_only_nato_and_anna_change_squares(self):
		self.assertEqual(render_square("f3", ANNA), "felix 3")
		self.assertEqual(render_square("f3", NATO), "foxtrot 3")
		self.assertEqual(render_square("f3", SAN), "f3")
		self.assertEqual(render_square("f3", LITERATE), "f3")
