# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Setting up a position by hand (README, "Board Editor").

Pieces go on and off, castling follows the kings and rooks unless switched
off, a FEN goes in and out, and what is wrong is said in words.
"""

import unittest

from chessStudy.paths import import_bundled
from chessStudy.position_editor import PositionDraft, spoken_piece

with import_bundled():
	import chess


def king_and_queen_mate_drill() -> PositionDraft:
	draft = PositionDraft()
	draft.place(chess.E1, chess.Piece(chess.KING, chess.WHITE))
	draft.place(chess.D1, chess.Piece(chess.QUEEN, chess.WHITE))
	draft.place(chess.E8, chess.Piece(chess.KING, chess.BLACK))
	return draft


class EditingTest(unittest.TestCase):
	def test_an_editor_starts_empty_and_says_so(self):
		draft = PositionDraft()
		self.assertFalse(draft.is_valid())
		self.assertIn("The board is empty.", draft.problems())

	def test_placing_and_clearing(self):
		draft = king_and_queen_mate_drill()
		self.assertTrue(draft.is_valid())
		self.assertEqual(draft.problems(), [])
		self.assertEqual(draft.clear(chess.D1), chess.Piece(chess.QUEEN, chess.WHITE))
		self.assertIsNone(draft.board.piece_at(chess.D1))
		self.assertIsNone(draft.clear(chess.D1))

	def test_a_piece_placed_on_an_occupied_square_replaces_it(self):
		draft = king_and_queen_mate_drill()
		draft.place(chess.D1, chess.Piece(chess.ROOK, chess.WHITE))
		self.assertEqual(draft.board.piece_at(chess.D1), chess.Piece(chess.ROOK, chess.WHITE))

	def test_the_standard_position(self):
		draft = PositionDraft()
		draft.standard()
		self.assertEqual(draft.fen(), chess.STARTING_FEN)


class ProblemsTest(unittest.TestCase):
	def test_missing_king_and_pawn_on_the_back_rank(self):
		draft = PositionDraft()
		draft.place(chess.E1, chess.Piece(chess.KING, chess.WHITE))
		draft.place(chess.A8, chess.Piece(chess.PAWN, chess.WHITE))
		problems = draft.problems()
		self.assertIn("There is no black king.", problems)
		self.assertIn("A pawn stands on the first or the eighth rank.", problems)

	def test_the_side_not_to_move_in_check(self):
		draft = king_and_queen_mate_drill()
		draft.place(chess.E2, chess.Piece(chess.ROOK, chess.WHITE))
		# White to move while the black king on e8 stands in check from e2.
		self.assertIn("The side that is not to move is in check.", draft.problems())
		draft.set_turn(chess.BLACK)
		self.assertEqual(draft.problems(), [])


class CastlingTest(unittest.TestCase):
	def test_rights_follow_the_kings_and_rooks(self):
		draft = PositionDraft()
		draft.place(chess.E1, chess.Piece(chess.KING, chess.WHITE))
		draft.place(chess.H1, chess.Piece(chess.ROOK, chess.WHITE))
		draft.place(chess.E8, chess.Piece(chess.KING, chess.BLACK))
		self.assertTrue(draft.castling_on(chess.H1))
		self.assertFalse(draft.castling_on(chess.A1))
		draft.clear(chess.H1)
		self.assertFalse(draft.castling_on(chess.H1))

	def test_a_right_switched_off_stays_off(self):
		draft = PositionDraft()
		draft.standard()
		self.assertFalse(draft.toggle_castling(chess.A8))
		draft.place(chess.B1, chess.Piece(chess.KNIGHT, chess.WHITE))
		self.assertFalse(draft.castling_on(chess.A8))
		self.assertTrue(draft.toggle_castling(chess.A8))
		self.assertEqual(draft.fen(), chess.STARTING_FEN)

	def test_a_right_the_pieces_forbid_cannot_be_switched_on(self):
		draft = king_and_queen_mate_drill()
		self.assertFalse(draft.castling_available(chess.H1))
		self.assertFalse(draft.toggle_castling(chess.H1))
		self.assertFalse(draft.toggle_castling(chess.H1))


class FenTest(unittest.TestCase):
	def test_fen_in_and_out(self):
		fen = "8/8/8/4k3/8/8/8/4K2Q w - - 0 1"
		draft = PositionDraft(fen)
		self.assertEqual(draft.fen(), fen)
		self.assertTrue(draft.is_valid())

	def test_castling_from_a_pasted_fen_is_kept(self):
		draft = PositionDraft("r3k2r/8/8/8/8/8/8/R3K2R w Kq - 0 1")
		self.assertTrue(draft.castling_on(chess.H1))
		self.assertFalse(draft.castling_on(chess.A1))
		self.assertTrue(draft.castling_on(chess.A8))

	def test_not_a_fen(self):
		with self.assertRaises(ValueError):
			PositionDraft().set_fen("not a position")


class WordsTest(unittest.TestCase):
	def test_piece_names(self):
		self.assertEqual(spoken_piece(chess.Piece(chess.KING, chess.WHITE)), "white king")
		self.assertEqual(spoken_piece(chess.Piece(chess.KNIGHT, chess.BLACK)), "black knight")


if __name__ == "__main__":
	unittest.main()
