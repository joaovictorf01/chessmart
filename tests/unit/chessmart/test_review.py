# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The review queue: a missed puzzle comes back, two clean reviews make it firm, and none of it is rated."""

import datetime
import sqlite3
import tempfile
import unittest
from pathlib import Path

from chessmart import study_log
from chessmart.puzzle_attempt import AttemptState, SessionStats
from chessmart.tactic.db import load_store
from chessmart.tactic.repository import PuzzleRepository
from chessmart.tactic.review import (
	FIRM_AFTER,
	REVIEWS_PER_SESSION,
	ReviewEvent,
	build_queue,
	outcome_for,
)
from chessmart.training_session import TrainingOptions, TrainingSession

from .test_store import PUZZLES, PUZZLES_SCHEMA

DAY = datetime.date(2026, 9, 20)


def event(puzzle_id, days, clean, is_review=False):
	return ReviewEvent(puzzle_id, DAY + datetime.timedelta(days=days), clean, is_review)


class TestBuildQueue(unittest.TestCase):
	def test_a_miss_comes_back_the_next_day(self):
		queue = build_queue([event("a", 0, clean=False)])
		self.assertEqual([item.puzzle_id for item in queue.due(DAY + datetime.timedelta(days=1))], ["a"])
		self.assertEqual(queue.due(DAY), [])
		self.assertEqual(queue.waiting(DAY), 1)

	def test_a_clean_attempt_never_missed_is_not_queued(self):
		queue = build_queue([event("a", 0, clean=True)])
		self.assertEqual(queue.items, ())
		self.assertEqual(queue.firm, 0)

	def test_two_clean_reviews_days_apart_make_it_firm(self):
		events = [event("a", 0, clean=False), event("a", 1, clean=True, is_review=True)]
		queue = build_queue(events)
		(item,) = queue.items
		self.assertEqual(item.clean_streak, 1)
		self.assertEqual(item.due, DAY + datetime.timedelta(days=4))
		queue = build_queue([*events, event("a", 4, clean=True, is_review=True)])
		self.assertEqual(queue.items, ())
		self.assertEqual(queue.firm, 1)
		self.assertEqual(FIRM_AFTER, 2)

	def test_a_slip_in_a_review_starts_over(self):
		queue = build_queue(
			[
				event("a", 0, clean=False),
				event("a", 1, clean=True, is_review=True),
				event("a", 4, clean=False, is_review=True),
			],
		)
		(item,) = queue.items
		self.assertEqual(item.clean_streak, 0)
		self.assertEqual(item.due, DAY + datetime.timedelta(days=5))
		# The day it was first missed is kept: it orders the queue, oldest first.
		self.assertEqual(item.missed_on, DAY)

	def test_a_firm_puzzle_missed_again_comes_back(self):
		queue = build_queue(
			[
				event("a", 0, clean=False),
				event("a", 1, clean=True, is_review=True),
				event("a", 4, clean=True, is_review=True),
				event("a", 10, clean=False),
			],
		)
		self.assertEqual([item.puzzle_id for item in queue.items], ["a"])
		self.assertEqual(queue.firm, 0)

	def test_due_puzzles_come_oldest_first(self):
		queue = build_queue(
			[event("b", 2, clean=False), event("a", 0, clean=False), event("c", 1, clean=False)]
		)
		due = queue.due(DAY + datetime.timedelta(days=10))
		self.assertEqual([item.puzzle_id for item in due], ["a", "c", "b"])

	def test_outcome_after_a_review(self):
		queue = build_queue([event("a", 0, clean=False), event("a", 1, clean=True, is_review=True)])
		outcome = outcome_for(queue, "a", clean=True)
		self.assertFalse(outcome.firm)
		self.assertEqual(outcome.clean_streak, 1)
		self.assertTrue(outcome_for(build_queue([]), "a", clean=True).firm)


class ReviewDatabaseTestCase(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		cls.puzzles_path = Path(cls.tmp.name) / "puzzles.db"
		connection = sqlite3.connect(cls.puzzles_path)
		connection.executescript(PUZZLES_SCHEMA)
		connection.executemany(
			"INSERT INTO puzzles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
			[
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
		self.repository = PuzzleRepository(self.puzzles_path, self.history_path)

	def tearDown(self):
		self.history_dir.cleanup()

	def backdate(self, days):
		"""Move every recorded attempt `days` into the past, as if played then."""
		connection = sqlite3.connect(self.history_path)
		for table in ("attempts", "review_attempts"):
			connection.execute(f"UPDATE {table} SET created_at = datetime(created_at, '-{days} days')")
		connection.commit()
		connection.close()

	def miss(self, puzzle_id, **kwargs):
		values = dict(solved=False, mistakes=1, hints_used=0, elapsed_ms=1000)
		values.update(kwargs)
		return self.repository.record_attempt(puzzle_id, **values)


class TestStoreQueue(ReviewDatabaseTestCase):
	def test_wrong_move_hint_and_reveal_all_enter_the_queue(self):
		self.miss("easy1")
		self.miss("easy2", solved=True, mistakes=0, hints_used=1)
		self.miss("mid1", solved=True, mistakes=0, revealed=True)
		self.repository.record_attempt("mid2", True, 0, 0, 1000)
		queue = self.repository.review_queue()
		self.assertEqual(sorted(item.puzzle_id for item in queue.items), ["easy1", "easy2", "mid1"])

	def test_due_only_from_the_next_day_and_at_most_the_limit(self):
		for puzzle_id in ("easy1", "easy2", "mid1", "mid2"):
			self.miss(puzzle_id)
		today = datetime.date.today()
		self.assertEqual(self.repository.due_review_puzzles(today, 3), [])
		due = self.repository.due_review_puzzles(today + datetime.timedelta(days=1), 3)
		self.assertEqual(len(due), 3)

	def test_a_puzzle_missing_from_the_installed_database_is_passed_over(self):
		self.miss("gone")
		self.miss("easy1")
		due = self.repository.due_review_puzzles(datetime.date.today() + datetime.timedelta(days=1), 3)
		self.assertEqual([puzzle.id for puzzle in due], ["easy1"])
		self.assertEqual(len(self.repository.review_queue().items), 2)

	def test_a_review_never_touches_the_rating(self):
		self.miss("easy1")
		before = self.repository.rating()
		self.backdate(1)
		outcome = self.repository.record_review("easy1", True, 0, 0, False, 1000)
		after = self.repository.rating()
		self.assertEqual((before.rating, before.rated_attempts), (after.rating, after.rated_attempts))
		self.assertTrue(outcome.clean)
		self.assertEqual(outcome.clean_streak, 1)
		self.assertFalse(outcome.firm)

	def test_second_clean_review_is_firm(self):
		self.miss("easy1")
		self.backdate(1)
		self.repository.record_review("easy1", True, 0, 0, False, 1000)
		self.backdate(3)
		outcome = self.repository.record_review("easy1", True, 0, 0, False, 1000)
		self.assertTrue(outcome.firm)
		self.assertEqual(self.repository.review_queue().firm, 1)

	def test_a_review_with_a_hint_is_not_clean(self):
		self.miss("easy1")
		self.backdate(1)
		outcome = self.repository.record_review("easy1", True, 0, 1, False, 1000)
		self.assertFalse(outcome.clean)
		self.assertEqual(outcome.clean_streak, 0)
		self.assertEqual(outcome.due, datetime.date.today() + datetime.timedelta(days=1))

	def test_an_old_history_gains_the_review_table_and_column(self):
		old = Path(self.history_dir.name) / "old.db"
		connection = sqlite3.connect(old)
		connection.executescript(
			"CREATE TABLE attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, puzzle_id TEXT NOT NULL,"
			" solved INTEGER NOT NULL, mistakes INTEGER NOT NULL, hints_used INTEGER NOT NULL,"
			" elapsed_ms INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);"
			"INSERT INTO attempts (puzzle_id, solved, mistakes, hints_used, elapsed_ms) VALUES ('easy1', 0, 1, 0, 5);",
		)
		connection.commit()
		connection.close()
		repository = PuzzleRepository(self.puzzles_path, old)
		self.assertEqual([item.puzzle_id for item in repository.review_queue().items], ["easy1"])


class TestSessionServesReviewsFirst(ReviewDatabaseTestCase):
	def session(self, **options):
		options.setdefault("db_path", str(self.puzzles_path))
		options.setdefault("trainer_preset", "allThemes")
		options.setdefault("challenge_level", "beginner")
		return TrainingSession(TrainingOptions(**options), history_path=self.history_path)

	def test_reviews_come_first_flagged_and_are_not_drawn_again(self):
		self.miss("hard1")
		self.miss("hard2")
		self.backdate(1)
		session = self.session()
		session.ensure_ready()
		self.assertEqual((session.reviews_total, session.reviews_left), (2, 2))
		first, second = session.next_puzzle(), session.next_puzzle()
		assert first is not None and second is not None
		self.assertTrue(first.review and second.review)
		self.assertEqual({first.puzzle_id, second.puzzle_id}, {"hard1", "hard2"})
		self.assertEqual(session.reviews_served, 2)
		new = session.next_puzzle()
		assert new is not None
		self.assertFalse(new.review)
		self.assertNotIn(new.puzzle_id, {"hard1", "hard2"})

	def test_at_most_the_session_limit(self):
		for puzzle_id in ("easy1", "easy2", "mid1", "mid2", "hard1"):
			self.miss(puzzle_id)
		self.backdate(1)
		session = self.session()
		session.ensure_ready()
		self.assertEqual(session.reviews_total, REVIEWS_PER_SESSION)

	def test_skipping_goes_to_new_puzzles_and_keeps_them_due(self):
		self.miss("hard1")
		self.backdate(1)
		session = self.session()
		session.ensure_ready()
		session.skip_reviews()
		puzzle = session.next_puzzle()
		assert puzzle is not None
		self.assertFalse(puzzle.review)
		self.assertEqual(len(self.repository.due_review_puzzles(datetime.date.today(), 3)), 1)

	def test_a_puzzle_opened_by_id_has_no_reviews(self):
		self.miss("hard1")
		self.backdate(1)
		session = self.session(puzzle_id="easy1")
		session.ensure_ready()
		self.assertEqual(session.reviews_total, 0)
		puzzle = session.next_puzzle()
		assert puzzle is not None
		self.assertEqual((puzzle.puzzle_id, puzzle.review), ("easy1", False))


class TestSessionStats(unittest.TestCase):
	def test_reviews_are_counted_apart_from_new_puzzles(self):
		stats = SessionStats()
		stats.count(AttemptState(is_review=True, solution_index=2), solved=True)
		stats.count(AttemptState(is_review=True, mistakes=1, solution_index=2), solved=True)
		self.assertEqual((stats.attempts, stats.reviews, stats.reviews_clean), (0, 2, 1))
		self.assertEqual(stats.summary(), "Reviews: 1 clean out of 2.")
		stats.count(AttemptState(solution_index=2), solved=True)
		self.assertEqual(stats.summary(), "Session: 1 solved out of 1. Reviews: 1 clean out of 2.")

	def test_clean_means_alone(self):
		self.assertTrue(AttemptState().clean(solved=True))
		self.assertFalse(AttemptState(hints_used=1).clean(solved=True))
		self.assertFalse(AttemptState(auto_solved=True).clean(solved=True))
		self.assertFalse(AttemptState().clean(solved=False))


class TestStudyLogReviews(ReviewDatabaseTestCase):
	def test_queue_and_days(self):
		self.miss("easy1")
		self.miss("easy2")
		self.backdate(1)
		self.repository.record_review("easy1", True, 0, 0, False, 120000)
		connection = sqlite3.connect(self.history_path)
		connection.row_factory = sqlite3.Row
		try:
			today = datetime.date.today()
			queue = study_log.review_queue(connection)
			lines = study_log.render_reviews(queue, today)
			self.assertEqual(lines[0], "In the queue: 1 due today, 1 waiting for their day. Firm: 0.")
			(summary,) = [s for s in study_log.daily_summaries(connection, 1, today)]
			self.assertEqual((summary.reviews, summary.reviews_clean, summary.reviews_ms), (1, 1, 120000))
			self.assertIn("reviews: 1, 1 clean, 2 min", study_log.render_days([summary], 1)[0])
		finally:
			connection.close()

	def test_nothing_missed(self):
		connection = sqlite3.connect(self.history_path)
		connection.row_factory = sqlite3.Row
		try:
			load_store().prepare_history(connection)
			queue = study_log.review_queue(connection)
			self.assertEqual(
				study_log.render_reviews(queue, datetime.date.today()), ["No missed puzzles to review."]
			)
		finally:
			connection.close()
