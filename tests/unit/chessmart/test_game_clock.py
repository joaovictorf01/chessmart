# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The clock of a game on the analysis board (README, "Import a Lichess game").

The numbers here are a real Lichess 15+10 game's first moves, and a short
invented ending to reach time trouble.
"""

import io
import unittest

from chessmart.game_clock import (
	format_clock,
	move_clocks,
	node_clock,
	parse_time_control,
	plain_comment,
	summarize,
)
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.pgn

GAME = """[TimeControl "900+10"]
[White "A"]
[Black "B"]

1. e4 { [%clk 0:15:00] } 1... c5 { [%clk 0:15:00] } 2. Nf3 { [%clk 0:15:03] } 2... g6 { [%clk 0:15:05] }
3. Bc4 { [%clk 0:15:07] } 3... Bg7 { [%clk 0:15:08] } 4. Ng5 { [%clk 0:15:08] } 4... e6 { [%clk 0:15:06] }
5. Qf3 { [%clk 0:14:53] } 5... Qxg5 { [%clk 0:00:50] } 6. h4 { [%clk 0:13:29] } 6... Qd8 { [%clk 0:00:41] } *
"""


def game(text: str = GAME) -> "chess.pgn.Game":
	parsed = chess.pgn.read_game(io.StringIO(text))
	assert parsed is not None
	return parsed


class TimeControlTest(unittest.TestCase):
	def test_base_and_increment(self):
		control = parse_time_control("900+10")
		assert control is not None
		self.assertEqual((control.initial, control.increment), (900, 10))

	def test_unknown_controls(self):
		self.assertIsNone(parse_time_control("-"))
		self.assertIsNone(parse_time_control("1/86400"))
		self.assertIsNone(parse_time_control(None))


class MoveClockTest(unittest.TestCase):
	def test_time_spent_is_clock_before_plus_increment_minus_clock_after(self):
		clocks = move_clocks(game())
		# 2. Nf3: 15:00 before, +10, 15:03 after -> 7 seconds.
		nf3 = clocks[2]
		self.assertEqual((nf3.san, nf3.left, nf3.spent), ("Nf3", 903.0, 7.0))
		# 5. Qf3: 15:08 before, +10, 14:53 after -> 25 seconds.
		self.assertEqual(clocks[8].spent, 25.0)
		# The first move of each side counts from the initial time.
		self.assertEqual(clocks[0].spent, 10.0)
		self.assertEqual(clocks[1].move_number, 1)

	def test_without_a_time_control_the_time_spent_is_unknown(self):
		clocks = move_clocks(game(GAME.replace('[TimeControl "900+10"]', "")))
		self.assertEqual(clocks[0].left, 900.0)
		self.assertIsNone(clocks[0].spent)

	def test_moves_without_a_clock_are_left_out(self):
		self.assertEqual(move_clocks(game("1. e4 e5 *")), [])


class NodeClockTest(unittest.TestCase):
	def test_a_node_in_the_tree(self):
		first = game().next()
		assert first is not None
		self.assertEqual(node_clock(first), (900.0, 10.0))
		qf3 = list(game().mainline())[8]
		self.assertEqual(node_clock(qf3), (893.0, 25.0))

	def test_the_start_and_a_move_without_clock(self):
		self.assertIsNone(node_clock(game()))
		self.assertIsNone(node_clock(game("1. e4 e5 *").next()))  # type: ignore[arg-type]


class SummaryTest(unittest.TestCase):
	def test_time_trouble_and_the_longest_think(self):
		black = summarize(move_clocks(game()), chess.BLACK)
		assert black.first_in_time_trouble is not None and black.longest_think is not None
		self.assertEqual(black.first_in_time_trouble.san, "Qxg5")
		self.assertEqual(black.first_in_time_trouble.move_number, 5)
		self.assertEqual(black.lowest and black.lowest.left, 41.0)
		# 5... Qxg5: 15:06 before, +10, 0:50 after -> 14 minutes 26 seconds.
		self.assertEqual((black.longest_think.san, black.longest_think.spent), ("Qxg5", 866.0))

	def test_a_side_that_never_reached_time_trouble(self):
		self.assertIsNone(summarize(move_clocks(game()), chess.WHITE).first_in_time_trouble)


class TextTest(unittest.TestCase):
	def test_clock_format(self):
		self.assertEqual(format_clock(892.0), "14:52")
		self.assertEqual(format_clock(48.7), "0:48")
		self.assertEqual(format_clock(3725), "1:02:05")

	def test_annotations_are_not_read_aloud(self):
		self.assertEqual(plain_comment("[%eval 0.18] [%clk 0:15:00]"), "")
		self.assertEqual(plain_comment("I saw the fork [%clk 0:01:02] too late"), "I saw the fork too late")


if __name__ == "__main__":
	unittest.main()
