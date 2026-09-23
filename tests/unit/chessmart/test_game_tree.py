# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The game tree behind the analysis board (README, "Record and Analyse a Game").

What a key does to the tree: a move where the line already goes elsewhere is a
variation, Backspace only takes back the end of a line, a comment and a mark
stay on their move, and the file written is the PGN a reader expects.
"""

import datetime
import io
import tempfile
import unittest
from pathlib import Path

from chessmart.game_tree import (
	GameTree,
	PlayResult,
	RecordHeaders,
	record_filename,
	unique_path,
	write_pgn,
)
from chessmart.paths import import_bundled

with import_bundled():
	import chess
	import chess.pgn


def play(tree: GameTree, *sans: str) -> list[PlayResult]:
	results = []
	for san in sans:
		results.append(tree.play(tree.board().parse_san(san)))
	return results


class PlayTest(unittest.TestCase):
	def test_moves_on_an_empty_line_extend_it(self):
		tree = GameTree()
		self.assertEqual(play(tree, "e4", "e5", "Nf3"), [PlayResult.EXTENDED] * 3)
		self.assertEqual(tree.line_san(), ["e4", "e5", "Nf3"])
		self.assertFalse(tree.in_variation)

	def test_another_move_where_the_line_continues_is_a_variation(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3")
		tree.back()
		self.assertEqual(play(tree, "Bc4"), [PlayResult.NEW_VARIATION])
		self.assertTrue(tree.in_variation)
		self.assertTrue(tree.starts_variation())
		self.assertEqual(tree.depth, 1)
		# The main line is untouched.
		self.assertEqual([n.san() for n in tree.game.mainline()], ["e4", "e5", "Nf3"])

	def test_replaying_a_recorded_move_follows_it(self):
		tree = GameTree()
		play(tree, "e4", "e5")
		tree.to_start()
		self.assertEqual(play(tree, "e4"), [PlayResult.FOLLOWED])
		self.assertEqual(len(tree.game.variations), 1)

	def test_moves_inside_a_variation_extend_the_variation(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3")
		tree.back()
		self.assertEqual(play(tree, "Bc4", "Nf6"), [PlayResult.NEW_VARIATION, PlayResult.EXTENDED])
		self.assertEqual(tree.line_san(), ["e4", "e5", "Bc4", "Nf6"])
		self.assertEqual(tree.depth, 1)


class NavigationTest(unittest.TestCase):
	def test_back_and_forward_walk_the_current_line(self):
		tree = GameTree()
		play(tree, "d4", "d5", "c4")
		self.assertTrue(tree.back())
		self.assertTrue(tree.back())
		self.assertEqual(tree.line_san(), ["d4"])
		self.assertTrue(tree.forward())
		self.assertEqual(tree.line_san(), ["d4", "d5"])

	def test_back_at_the_start_and_forward_at_the_end_do_nothing(self):
		tree = GameTree()
		self.assertFalse(tree.back())
		play(tree, "d4")
		self.assertFalse(tree.forward())

	def test_leaving_a_variation_returns_to_its_branch_point(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3", "Nc6")
		tree.back()
		tree.back()
		play(tree, "Bc4", "Nf6", "d3")
		self.assertTrue(tree.leave_variation())
		self.assertEqual(tree.line_san(), ["e4", "e5"])
		self.assertFalse(tree.in_variation)
		# Forward goes along the main line, the one the variation was an alternative to.
		tree.forward()
		self.assertEqual(tree.line_san(), ["e4", "e5", "Nf3"])

	def test_leaving_a_nested_variation_goes_one_level_up(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3")
		tree.back()
		play(tree, "Bc4", "Nf6")
		tree.back()
		play(tree, "Bc5")
		self.assertEqual(tree.depth, 2)
		tree.leave_variation()
		self.assertEqual(tree.line_san(), ["e4", "e5", "Bc4"])
		self.assertEqual(tree.depth, 1)

	def test_on_the_main_line_there_is_no_variation_to_leave(self):
		tree = GameTree()
		play(tree, "e4", "e5")
		self.assertFalse(tree.leave_variation())
		self.assertEqual(tree.line_san(), ["e4", "e5"])

	def test_board_is_the_position_at_the_pointer(self):
		tree = GameTree()
		play(tree, "e4", "c5", "Nf3")
		tree.back()
		board = tree.board()
		self.assertEqual(
			board.fen(), chess.Board("rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2").fen()
		)
		self.assertEqual(len(board.move_stack), 2)


class EditTest(unittest.TestCase):
	def test_backspace_takes_back_the_end_of_a_line(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Qh5")
		self.assertTrue(tree.delete_last_move())
		self.assertEqual(tree.line_san(), ["e4", "e5"])
		self.assertEqual([n.san() for n in tree.game.mainline()], ["e4", "e5"])

	def test_backspace_never_erases_moves_recorded_after_the_pointer(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3")
		tree.back()
		self.assertFalse(tree.delete_last_move())
		self.assertEqual([n.san() for n in tree.game.mainline()], ["e4", "e5", "Nf3"])

	def test_backspace_on_the_first_move_of_a_variation_removes_the_variation(self):
		tree = GameTree()
		play(tree, "e4", "e5")
		tree.back()
		play(tree, "c5")
		self.assertTrue(tree.delete_last_move())
		self.assertEqual(len(tree.node.variations), 1)
		self.assertFalse(tree.in_variation)

	def test_promoting_a_variation_makes_it_the_main_line(self):
		tree = GameTree()
		play(tree, "e4", "e5")
		tree.back()
		play(tree, "c5", "Nf3")
		self.assertTrue(tree.promote_variation())
		self.assertEqual([n.san() for n in tree.game.mainline()], ["e4", "c5", "Nf3"])
		self.assertFalse(tree.in_variation)

	def test_comment_stays_on_its_move(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3")
		tree.back()
		tree.set_comment("  I thought the queen could come out.  ")
		tree.forward()
		self.assertEqual(tree.comment, "")
		tree.back()
		self.assertEqual(tree.comment, "I thought the queen could come out.")

	def test_editing_a_comment_keeps_the_clock(self):
		tree = GameTree()
		play(tree, "e4")
		tree.node.comment = "[%clk 0:14:52]"
		self.assertEqual(tree.comment, "")
		tree.set_comment("Played fast")
		self.assertEqual(tree.comment, "Played fast")
		self.assertEqual(tree.node.clock(), 892.0)
		tree.set_comment("")
		self.assertEqual(tree.node.comment, "[%clk 0:14:52]")

	def test_a_move_has_one_mark_and_a_new_one_replaces_it(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Qh5")
		self.assertIsNone(tree.move_mark)
		tree.set_move_mark(chess.pgn.NAG_DUBIOUS_MOVE)
		tree.set_move_mark(chess.pgn.NAG_MISTAKE)
		self.assertEqual(tree.move_mark, chess.pgn.NAG_MISTAKE)
		self.assertEqual(tree.node.nags, {chess.pgn.NAG_MISTAKE})
		tree.set_move_mark(None)
		self.assertIsNone(tree.move_mark)

	def test_an_engine_line_becomes_a_variation_and_the_pointer_stays(self):
		tree = GameTree()
		play(tree, "e4", "e5", "Qh5")
		tree.back()
		board = tree.board()
		line = [board.parse_san("Nf3")]
		board.push(line[0])
		line.append(board.parse_san("Nc6"))
		first = tree.add_line(line, comment="Stockfish 16: +0.4")
		self.assertEqual(tree.line_san(), ["e4", "e5"])
		self.assertIsNotNone(first)
		self.assertEqual([child.san() for child in tree.alternatives()], ["Qh5", "Nf3"])
		self.assertEqual(tree.alternatives()[1].comment, "Stockfish 16: +0.4")
		# Asking again follows the recorded moves instead of duplicating them.
		tree.add_line(line)
		self.assertEqual(len(tree.alternatives()), 2)

	def test_the_start_of_the_game_has_no_move_to_mark(self):
		self.assertFalse(GameTree().set_move_mark(chess.pgn.NAG_GOOD_MOVE))


class FileTest(unittest.TestCase):
	def _analysed_game(self) -> GameTree:
		tree = GameTree()
		play(tree, "e4", "e5", "Nf3", "Nc6")
		tree.back()
		tree.back()
		play(tree, "Qh5")
		tree.set_move_mark(chess.pgn.NAG_DUBIOUS_MOVE)
		tree.set_comment("Too early.")
		RecordHeaders(
			white="João Victor",
			black="Jeferson",
			event="Treino",
			date=datetime.date(2026, 9, 23),
			result="1-0",
		).apply(tree)
		return tree

	def test_the_written_pgn_reads_back_with_variation_comment_and_mark(self):
		tree = self._analysed_game()
		with tempfile.TemporaryDirectory() as folder:
			path = str(Path(folder) / "game.pgn")
			write_pgn(tree, path)
			text = Path(path).read_text(encoding="utf-8")
			self.assertFalse(Path(path + ".tmp").exists())
		# PGN export format writes marks as NAGs: $6 is ?!.
		self.assertIn("( 2. Qh5 $6 { Too early. } )", text)
		game = chess.pgn.read_game(io.StringIO(text))
		assert game is not None
		self.assertEqual(game.headers["White"], "João Victor")
		self.assertEqual(game.headers["Date"], "2026.09.23")
		self.assertEqual(game.headers["Result"], "1-0")
		self.assertEqual([n.san() for n in game.mainline()], ["e4", "e5", "Nf3", "Nc6"])
		variation = game.next().next().variations[1]  # type: ignore[union-attr]
		self.assertEqual(variation.san(), "Qh5")
		self.assertEqual(variation.comment, "Too early.")

	def test_blank_headers_are_written_as_unknown(self):
		tree = GameTree()
		RecordHeaders().apply(tree)
		self.assertEqual(tree.game.headers["White"], "?")
		self.assertEqual(tree.game.headers["Result"], "*")

	def test_filename_has_the_date_first_and_safe_names(self):
		date = datetime.date(2026, 9, 23)
		self.assertEqual(
			record_filename(date, "João Victor", "Jeferson"), "2026-09-23_João-Victor-vs-Jeferson.pgn"
		)
		self.assertEqual(record_filename(date, "a/b:c?", "d"), "2026-09-23_a-b-c-vs-d.pgn")
		self.assertEqual(record_filename(date, "", "  "), "2026-09-23.pgn")

	def test_a_taken_name_gets_a_number(self):
		with tempfile.TemporaryDirectory() as folder:
			first = unique_path(folder, "2026-09-23.pgn")
			Path(first).write_text("x", encoding="utf-8")
			second = unique_path(folder, "2026-09-23.pgn")
			self.assertEqual(Path(second).name, "2026-09-23 (2).pgn")


if __name__ == "__main__":
	unittest.main()
