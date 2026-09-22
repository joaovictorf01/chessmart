# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The training session: draw without repeats, puzzle by id, prefetch and description.

Uses the same small database from `test_store` and a history in a temporary
directory. `chess` comes from `lib/` via `import_bundled`, as in the add-on.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from chessmart.tactic.models import AttemptStats
from chessmart.training_session import PuzzleInfo, TrainingOptions, TrainingSession

from .test_store import PUZZLES, PUZZLES_SCHEMA


class TrainingSessionTestCase(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		cls.puzzles_path = Path(cls.tmp.name) / "puzzles.db"
		connection = sqlite3.connect(cls.puzzles_path)
		connection.executescript(PUZZLES_SCHEMA)
		connection.executemany(
			"INSERT INTO puzzles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
			[
				# A real position, so the moves become chess.Move without error:
				# 1.e4 e5 2.Nf3 is the auto-performed move plus two of the solution.
				(
					puzzle_id,
					"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
					"e2e4 e7e5 g1f3",
					rating,
					75,
					popularity,
					1000,
					themes,
					"",
					"",
				)
				for puzzle_id, rating, popularity, themes in PUZZLES
			],
		)
		connection.commit()
		connection.close()

	@classmethod
	def tearDownClass(cls):
		cls.tmp.cleanup()

	def setUp(self):
		self.history_dir = tempfile.TemporaryDirectory(dir=self.tmp.name)
		self.history_path = Path(self.history_dir.name) / "tactic.db"

	def tearDown(self):
		self.history_dir.cleanup()

	def session(self, **options) -> TrainingSession:
		options.setdefault("db_path", str(self.puzzles_path))
		return TrainingSession(TrainingOptions(**options), history_path=self.history_path)


class TestDrawing(TrainingSessionTestCase):
	def test_all_themes_serves_every_puzzle_once_then_ends(self):
		session = self.session(trainer_preset="allThemes", challenge_level="hard")
		session.ensure_ready()
		served = []
		while (puzzle := session.next_puzzle()) is not None:
			served.append(puzzle.puzzle_id)
		# The "hard" level is rating 1600 or above, with no popularity filter.
		self.assertEqual(sorted(served), ["hard1", "hard2"])

	def test_puzzle_info_has_the_moves_split(self):
		session = self.session(trainer_preset="allThemes", challenge_level="beginner")
		puzzle = session.next_puzzle()
		self.assertIsInstance(puzzle, PuzzleInfo)
		self.assertEqual(puzzle.auto_performed_move.uci(), "e2e4")
		self.assertEqual([move.uci() for move in puzzle.solution_moves], ["e7e5", "g1f3"])
		self.assertTrue(all(theme.label for theme in puzzle.themes))

	def test_single_puzzle_session_serves_it_once(self):
		session = self.session(puzzle_id=" mid2 ")
		session.ensure_ready()
		self.assertEqual(session.next_puzzle().puzzle_id, "mid2")
		self.assertIsNone(session.next_puzzle())
		self.assertEqual(session.describe_filters(), "Puzzle ID mid2")

	def test_unknown_puzzle_id_is_a_lookup_error(self):
		with self.assertRaises(LookupError):
			self.session(puzzle_id="ghost").ensure_ready()

	def test_filters_with_nothing_behind_them_fail_early(self):
		with self.assertRaises(LookupError):
			self.session(
				trainer_preset="customThemes",
				custom_theme_text="zugzwang",
				challenge_level="beginner",
			).ensure_ready()

	def test_missing_database_is_file_not_found(self):
		os.environ.pop("CHESSMART_PUZZLES_DB_PATH", None)
		session = self.session(db_path=str(Path(self.tmp.name) / "nope.db"))
		if session.repository is not None:
			self.skipTest("a default database is installed on this machine")
		with self.assertRaises(FileNotFoundError):
			session.ensure_ready()

	def test_prefetch_gives_the_same_result_as_drawing_now(self):
		session = self.session(
			trainer_preset="customThemes",
			custom_theme_text="fork",
			challenge_level="intermediate",
		)
		first = session.next_puzzle()
		session.prefetch_next()
		second = session.next_puzzle()
		# Only one "fork" between 900 and 1500 with popularity 50: easy2 (1000, 80).
		self.assertEqual(first.puzzle_id, "easy2")
		self.assertIsNone(second)


class TestDescriptionAndHistory(TrainingSessionTestCase):
	def test_describe_filters_reads_plan_level_and_themes(self):
		session = self.session(trainer_preset="kingAttack", challenge_level="advanced")
		text = session.describe_filters()
		self.assertIn("Training plan: Attack the king", text)
		self.assertIn("Challenge: Advanced: puzzles rated 1200 to 1900", text)
		self.assertIn("Themes: Mate in one", text)
		self.assertIn("Minimum popularity: 25", text)

	def test_recording_goes_to_the_private_history(self):
		session = self.session(trainer_preset="allThemes", challenge_level="hard")
		result = session.record_attempt("hard1", solved=True, mistakes=0, hints_used=0, elapsed_ms=500)
		self.assertGreater(result.rating_delta, 0)
		self.assertEqual(session.attempt_stats(), AttemptStats(total=1, solved=1))
		self.assertEqual(session.rating().rated_attempts, 1)
		self.assertTrue(self.history_path.is_file())
