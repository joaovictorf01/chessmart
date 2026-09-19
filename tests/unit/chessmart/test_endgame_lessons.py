# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""A trilha de finais: catálogo consistente, resultados conferidos onde há tabela, e o registro."""

import sys
import tempfile
import unittest
from pathlib import Path

from chessmart.endgame import judge, lessons, log, tablebase
from chessmart.paths import LIB_DIRECTORY

if LIB_DIRECTORY not in sys.path:
	sys.path.append(LIB_DIRECTORY)
import chess  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "syzygy"


class TestCatalog(unittest.TestCase):
	def test_ids_are_unique_and_positions_are_legal_and_open(self):
		lesson_ids = [lesson.lesson_id for lesson in lessons.ENDGAME_LESSONS]
		self.assertEqual(len(lesson_ids), len(set(lesson_ids)))
		position_ids = [position.position_id for _, position in lessons.all_positions()]
		self.assertEqual(len(position_ids), len(set(position_ids)))
		self.assertGreaterEqual(len(position_ids), 30)
		for _, position in lessons.all_positions():
			board = chess.Board(position.fen)
			self.assertTrue(board.is_valid(), position.position_id)
			self.assertFalse(board.is_game_over(), position.position_id)
			self.assertLessEqual(chess.popcount(board.occupied), tablebase.MAX_PIECES, position.position_id)
			self.assertIn(position.expected, (judge.WIN, judge.DRAW, judge.LOSS))
			self.assertTrue(position.rule and position.title and position.source, position.position_id)

	def test_first_lessons_are_the_mate_drills(self):
		self.assertIsNotNone(lessons.ENDGAME_LESSONS[0].drill)
		self.assertIsNotNone(lessons.ENDGAME_LESSONS[1].drill)
		self.assertEqual(lessons.ENDGAME_LESSONS[0].positions, ())

	def test_lost_positions_are_not_played_out(self):
		lost = [p for _, p in lessons.all_positions() if p.expected == judge.LOSS]
		self.assertTrue(lost)
		for position in lost:
			self.assertFalse(position.playable)
			self.assertIn("lost", lessons.play_goal(position))

	def test_expected_results_match_the_tablebase_where_tables_exist(self):
		tb = tablebase.open_tablebase(FIXTURES)
		checked = 0
		try:
			for _, position in lessons.all_positions():
				board = chess.Board(position.fen)
				verdict = judge.probe(tb, board)
				if verdict is None:
					continue
				checked += 1
				self.assertEqual(
					verdict.for_color(position.player, board.turn).result,
					position.expected,
					position.position_id,
				)
		finally:
			tb.close()
		# As tabelas de 3 peças do repositório cobrem toda a lição 2 e a 3.
		self.assertGreaterEqual(checked, 12)

	def test_unknown_lesson_falls_back_to_the_first(self):
		self.assertIs(lessons.get_lesson("nope"), lessons.ENDGAME_LESSONS[0])


class TestLog(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		self.connection = log.open_log(Path(self.directory.name) / "tactic.db")

	def tearDown(self):
		self.connection.close()
		self.directory.cleanup()

	def test_streak_counts_recent_successes_only(self):
		kwargs = dict(answer_correct=True, kept_result=True, moves=9, elapsed_ms=1000, outcome="checkmate")
		log.record(self.connection, "kingAndPawn", "squareOutside", **kwargs)
		log.record(self.connection, "kingAndPawn", "squareOutside", **{**kwargs, "kept_result": False})
		log.record(self.connection, "kingAndPawn", "squareOutside", **{**kwargs, "moves": 7})
		log.record(self.connection, "kingAndPawn", "squareOutside", **kwargs)
		stats = log.position_stats(self.connection, "squareOutside")
		self.assertEqual((stats.attempts, stats.streak, stats.best_moves), (4, 2, 7))

	def test_wrong_answer_breaks_the_streak_but_a_drill_without_question_does_not(self):
		log.record(
			self.connection,
			"mateQueen",
			"queenVsKing",
			answer_correct=None,
			kept_result=True,
			moves=8,
			elapsed_ms=1,
			outcome="checkmate",
		)
		log.record(
			self.connection,
			"mateQueen",
			"queenVsKing",
			answer_correct=None,
			kept_result=True,
			moves=9,
			elapsed_ms=1,
			outcome="checkmate",
		)
		self.assertEqual(log.position_stats(self.connection, "queenVsKing").streak, 2)
		log.record(
			self.connection,
			"kingAndPawn",
			"squareInside",
			answer_correct=False,
			kept_result=True,
			moves=5,
			elapsed_ms=1,
			outcome="draw",
		)
		self.assertEqual(log.position_stats(self.connection, "squareInside").streak, 0)
		self.assertEqual(set(log.lesson_stats(self.connection, "kingAndPawn")), {"squareInside"})
		self.assertEqual(log.position_stats(self.connection, "never").attempts, 0)
