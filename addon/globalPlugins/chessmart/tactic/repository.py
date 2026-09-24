# coding: utf-8
# pyright: basic

"""The facade the rest of the add-on uses to talk to the database.

Each call opens the connection, does one thing and closes it. It's simple
and it fits: calls are rare (a random draw, a recorded attempt) and never concurrent.
"""

from __future__ import annotations

import contextlib
import datetime
from pathlib import Path

from .db import HISTORY_DB_PATH, load_store
from .models import AttemptResult, AttemptStats, Puzzle, PuzzleFilters, RatingSummary
from .review import ReviewOutcome, ReviewQueue


class PuzzleRepository:
	def __init__(self, db_path: Path, history_path: Path | None = None):
		"""`db_path` is the puzzle database; the history is always the user's own, except in tests."""
		self.db_path = Path(db_path)
		self.history_path = Path(history_path) if history_path else HISTORY_DB_PATH

	@contextlib.contextmanager
	def _open(self):
		store = load_store()
		connection = store.connect(self.db_path, self.history_path)
		try:
			# The connection's `with` handles commit/rollback; closing is on us.
			with connection:
				yield store, connection
		finally:
			connection.close()

	def count(self) -> int:
		with self._open() as (store, connection):
			return store.count(connection)

	def get(self, puzzle_id: str) -> Puzzle | None:
		with self._open() as (store, connection):
			return store.get(connection, puzzle_id)

	def random_puzzle(self, filters: PuzzleFilters) -> Puzzle | None:
		with self._open() as (store, connection):
			return store.random_puzzle(connection, filters)

	def adaptive_random_puzzle(self, filters: PuzzleFilters) -> Puzzle | None:
		"""Draws a puzzle calibrated to the current rating; the rating range in `filters` is ignored."""
		with self._open() as (store, connection):
			return store.adaptive_random_puzzle(connection, filters)

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
		revealed: bool = False,
	) -> AttemptResult:
		with self._open() as (store, connection):
			return store.record_attempt(
				connection,
				puzzle_id,
				solved,
				mistakes,
				hints_used,
				elapsed_ms,
				revealed,
			)

	def due_review_puzzles(self, today: datetime.date, limit: int) -> list[Puzzle]:
		with self._open() as (store, connection):
			return store.due_review_puzzles(connection, today, limit)

	def review_queue(self) -> ReviewQueue:
		with self._open() as (store, connection):
			return store.review_queue(connection)

	def record_review(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		revealed: bool,
		elapsed_ms: int,
	) -> ReviewOutcome:
		with self._open() as (store, connection):
			return store.record_review(
				connection,
				puzzle_id,
				solved,
				mistakes,
				hints_used,
				revealed,
				elapsed_ms,
			)

	def rating(self) -> RatingSummary:
		with self._open() as (store, connection):
			return store.rating(connection)

	def attempt_stats(self) -> AttemptStats:
		with self._open() as (store, connection):
			return store.attempt_stats(connection)

	def theme_counts(self) -> list[tuple[str, int]]:
		"""Each theme in the database with how many puzzles have it. Scans the whole table."""
		with self._open() as (store, connection):
			return store.theme_counts(connection)
