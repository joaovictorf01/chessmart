# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What a move is, taken before it is played (README, "Keyboard commands on the board").

After the push the captured piece is gone and SAN can no longer be computed,
so everything the board says about a move comes from here.
"""

import unittest

from chessmart.paths import import_bundled
from chessmart.played_move import PlayedMove

with import_bundled():
	import chess


class PlayedMoveTest(unittest.TestCase):
	def test_a_quiet_move(self):
		board = chess.Board()
		played = PlayedMove.capture(board, chess.Move.from_uci("g1f3"))
		self.assertEqual(played.san, "Nf3")
		self.assertEqual(played.mover, chess.WHITE)
		self.assertFalse(played.is_capture)
		self.assertEqual(played.sound_name, "drop_piece")

	def test_en_passant_takes_the_pawn_behind_the_square(self):
		board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
		played = PlayedMove.capture(board, chess.Move.from_uci("e5d6"))
		self.assertTrue(played.is_en_passant)
		self.assertEqual(played.captured_piece, chess.Piece(chess.PAWN, chess.BLACK))
		self.assertEqual(played.sound_name, "en_passant")

	def test_black_en_passant_takes_the_white_pawn(self):
		board = chess.Board("4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1")
		board.push_san("e4")
		played = PlayedMove.capture(board, chess.Move.from_uci("d4e3"))
		self.assertTrue(played.is_en_passant)
		self.assertEqual(played.captured_piece, chess.Piece(chess.PAWN, chess.WHITE))
		self.assertEqual(played.sound_name, "en_passant")

	def test_castling_is_seen_before_the_rook_moves(self):
		board = chess.Board("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
		played = PlayedMove.capture(board, chess.Move.from_uci("e1g1"))
		self.assertTrue(played.is_castling)
		self.assertTrue(played.is_kingside_castling)
		self.assertEqual(played.san, "O-O")
		self.assertEqual(played.sound_name, "castling")

	def test_promotion_sound_wins_over_capture(self):
		board = chess.Board("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1")
		played = PlayedMove.capture(board, chess.Move.from_uci("a7b8q"))
		self.assertTrue(played.is_capture)
		self.assertEqual(played.sound_name, "promotion")

	def test_capture_sound(self):
		board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
		self.assertEqual(PlayedMove.capture(board, chess.Move.from_uci("e4d5")).sound_name, "capture")


if __name__ == "__main__":
	unittest.main()
