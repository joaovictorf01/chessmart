# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Opening names on the analysis board (README, "Record and Analyse a Game")."""

import io
import unittest

from chessStudy.openings import last_book_node, lookup, opening_of_line
from chessStudy.paths import import_bundled

with import_bundled():
	import chess
	import chess.pgn


def board_after(*sans: str) -> "chess.Board":
	board = chess.Board()
	for san in sans:
		board.push_san(san)
	return board


class LookupTest(unittest.TestCase):
	def test_a_known_position_has_its_name(self):
		opening = lookup(board_after("e4", "c5"))
		assert opening is not None
		self.assertEqual(opening.eco, "B20")
		self.assertEqual(opening.name, "Sicilian Defense")

	def test_transposition_finds_the_same_name(self):
		direct = lookup(board_after("d4", "Nf6", "c4", "e6", "g3"))
		transposed = lookup(board_after("c4", "e6", "g3", "Nf6", "d4"))
		assert direct is not None
		self.assertEqual(direct.name, "Catalan Opening")
		self.assertEqual(direct, transposed)

	def test_the_starting_position_and_a_random_one_have_no_name(self):
		self.assertIsNone(lookup(chess.Board()))
		self.assertIsNone(lookup(board_after("a4", "h5", "Ra3", "Rh6")))


class LineTest(unittest.TestCase):
	def test_the_name_stays_after_the_game_leaves_theory(self):
		game = chess.pgn.read_game(io.StringIO("1. e4 c5 2. a4 h5 3. Ra3 *"))
		assert game is not None
		end = game.end()
		opening = opening_of_line(end)
		assert opening is not None
		self.assertTrue(opening.name.startswith("Sicilian Defense"))

	def test_last_book_node_is_where_theory_ends(self):
		game = chess.pgn.read_game(io.StringIO("1. e4 c5 2. Nf3 d6 3. a4 h5 *"))
		assert game is not None
		node = last_book_node(game)
		assert node is not None
		self.assertEqual(node.board().fullmove_number, 3)
		self.assertEqual(node.san(), "d6")


if __name__ == "__main__":
	unittest.main()
