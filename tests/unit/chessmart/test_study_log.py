# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Meu estudo: o resumo por dia e o mapa das lições, lidos do histórico."""

import datetime
import tempfile
import unittest
from pathlib import Path

from chessmart import study_log
from chessmart.endgame import log
from chessmart.tactic.db import load_store


class TestStudyLog(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		path = Path(self.directory.name) / "tactic.db"
		self.connection = log.open_log(path)
		# A tabela de táticas, como o histórico de verdade a cria.
		self.connection.executescript(load_store().SCHEMA)

	def tearDown(self):
		self.connection.close()
		self.directory.cleanup()

	def _tactic(self, when: str, solved: bool, ms: int):
		self.connection.execute(
			"INSERT INTO attempts (puzzle_id, solved, mistakes, hints_used, elapsed_ms, created_at)"
			" VALUES ('x', ?, 0, 0, ?, ?)",
			(int(solved), ms, when),
		)
		self.connection.commit()

	def _endgame(self, when: str, position_id: str, held: bool, ms: int = 60000, correct=True):
		self.connection.execute(
			"INSERT INTO endgame_attempts (lesson_id, position_id, answer_correct, kept_result, moves, elapsed_ms,"
			" outcome, created_at) VALUES ('kingAndOpposition', ?, ?, ?, 8, ?, 'checkmate', ?)",
			(position_id, int(correct), int(held), ms, when),
		)
		self.connection.commit()

	def test_days_group_local_dates_and_sum_minutes(self):
		today = datetime.date(2026, 9, 19)
		self._tactic("2026-09-19 11:13:00", True, 480000)
		self._tactic("2026-09-19 11:20:00", False, 420000)
		self._endgame("2026-09-19 14:00:00", "kingFirst", True, 300000)
		self._tactic("2026-09-10 05:00:00", True, 60000)  # fora dos 7 dias
		summaries = study_log.daily_summaries(self.connection, 7, today=today)
		self.assertEqual(len(summaries), 1)
		day = summaries[0]
		self.assertEqual(
			(day.tactics_attempts, day.tactics_solved, day.endgame_attempts, day.endgame_held), (2, 1, 1, 1)
		)
		self.assertEqual(day.total_minutes, 20)
		lines = study_log.render_days(summaries, 7)
		self.assertIn(
			"2026-09-19: tactics: 2 puzzles, 1 solved, 15 min; endgames: 1 positions, 1 held, 5 min. Total 20 min.",
			lines,
		)
		self.assertEqual(lines[-1], "1 days with study in the last 7, 20 min in all.")
		self.assertEqual(len(study_log.daily_summaries(self.connection, 30, today=today)), 2)

	def test_empty_period(self):
		self.assertEqual(study_log.render_days([], 1), ["Nothing recorded in the last 1 days."])

	def test_lesson_progress_and_current_lesson(self):
		for _ in range(3):
			self._endgame("2026-09-19 10:00:00", "kingFirst", True)
		self._endgame("2026-09-19 10:30:00", "oppositionWhiteToMove", False)
		progress = study_log.lesson_progress(self.connection)
		by_id = {item.lesson.lesson_id: item for item in progress}
		opposition = by_id["kingAndOpposition"]
		self.assertEqual(opposition.firm, ("kingFirst",))
		self.assertEqual(len(opposition.pending), 5)
		self.assertEqual(opposition.attempted, 2)
		self.assertFalse(by_id["mateQueen"].complete)
		self.assertEqual(study_log.current_lesson(progress).lesson.lesson_id, "mateQueen")
		lines = study_log.render_progress(progress)
		self.assertIn("1a. Mate with queen and king: not started.", lines)
		self.assertTrue(
			any(line.startswith("2. The king and the opposition: 1 of 6 firm. Pending: ") for line in lines)
		)
		self.assertIn("You are at: 1a. Mate with queen and king.", lines)
