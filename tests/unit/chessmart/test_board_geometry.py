# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Squares, arrow keys and the material count (README, "Keyboard commands on the board")."""

import unittest

from chessmart.board_geometry import (
	DOWN,
	LEFT,
	RIGHT,
	UP,
	count_material,
	neighbour,
	pocket_contents,
	square_color,
)
from chessmart.endgame import judge
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.variant


class SquareTest(unittest.TestCase):
	def test_a1_is_dark_and_h1_light(self):
		self.assertEqual(square_color(chess.A1), chess.BLACK)
		self.assertEqual(square_color(chess.H1), chess.WHITE)
		self.assertEqual(square_color(chess.E4), chess.WHITE)
		self.assertEqual(square_color(chess.D4), chess.BLACK)

	def test_arrows_stop_at_the_edges(self):
		self.assertIsNone(neighbour(chess.A1, LEFT))
		self.assertIsNone(neighbour(chess.H4, RIGHT))
		self.assertIsNone(neighbour(chess.E8, UP))
		self.assertIsNone(neighbour(chess.E1, DOWN))

	def test_left_and_right_never_wrap_to_the_next_rank(self):
		self.assertIsNone(neighbour(chess.H1, RIGHT))
		self.assertIsNone(neighbour(chess.A2, LEFT))

	def test_arrows_move_one_square(self):
		self.assertEqual(neighbour(chess.E4, UP), chess.E5)
		self.assertEqual(neighbour(chess.E4, DOWN), chess.E3)
		self.assertEqual(neighbour(chess.E4, LEFT), chess.D4)
		self.assertEqual(neighbour(chess.E4, RIGHT), chess.F4)


class MaterialTest(unittest.TestCase):
	def test_starting_position_is_even(self):
		material = count_material(chess.Board(), chess.WHITE)
		self.assertEqual(material.balance, 0)
		self.assertEqual(material.minor_pieces, (4, 4))
		self.assertIsNone(material.bishop_pair)

	def test_up_the_exchange_with_the_bishop_pair(self):
		# White: king, rook, two bishops. Black: king, knight, bishop.
		board = chess.Board("4k3/8/8/2nb4/8/8/8/R1B1KB2 w - - 0 1")
		material = count_material(board, chess.WHITE)
		self.assertEqual(material.balance, 5)
		self.assertIs(material.bishop_pair, True)
		self.assertEqual(count_material(board, chess.BLACK).balance, -5)
		self.assertIs(count_material(board, chess.BLACK).bishop_pair, False)


class PocketTest(unittest.TestCase):
	def test_captured_pieces_go_to_the_capturers_pocket(self):
		board = chess.variant.CrazyhouseBoard()
		for san in ("e4", "d5", "exd5", "Qxd5", "Nc3", "Qxg2"):
			board.push_san(san)
		self.assertEqual(pocket_contents(board, chess.WHITE), ((chess.PAWN, 1),))
		self.assertEqual(pocket_contents(board, chess.BLACK), ((chess.PAWN, 2),))

	def test_an_empty_pocket(self):
		self.assertEqual(pocket_contents(chess.variant.CrazyhouseBoard(), chess.WHITE), ())


class ResultTest(unittest.TestCase):
	def test_result_for_each_side(self):
		mate = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1").outcome()
		self.assertEqual(judge.result_for(mate, chess.WHITE), judge.WIN)
		self.assertEqual(judge.result_for(mate, chess.BLACK), judge.LOSS)
		stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1").outcome()
		self.assertEqual(judge.result_for(stalemate, chess.WHITE), judge.DRAW)
		self.assertIsNone(judge.result_for(None, chess.WHITE))


if __name__ == "__main__":
	unittest.main()
