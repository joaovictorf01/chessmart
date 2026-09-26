# coding: utf-8
# pyright: basic

"""A tactics training session: the chosen options and the sequence of puzzles.

`TrainingOptions` is what the user decided (database, plan, level, themes, or
a puzzle id). `TrainingSession` draws puzzles from that, one at a time,
without repeating, and along the way does what the screen needs from the
database: recording attempts, reading rating and statistics.
"""

from __future__ import annotations

import dataclasses
import datetime
from concurrent.futures import Future
from pathlib import Path

from .paths import import_bundled
from .i18n import _
from .tactic.db import is_puzzles_database, resolve_default_db_path
from .tactic.models import AttemptResult, AttemptStats, Puzzle, PuzzleFilters, RatingSummary
from .tactic.repository import PuzzleRepository
from .tactic.review import REVIEWS_PER_SESSION, ReviewOutcome
from .theme_catalog import describe_theme_filter, parse_theme_filter
from .theme_names import theme_description, theme_label
from .trainer import (
	DEFAULT_CHALLENGE_ID,
	DEFAULT_TRAINER_PRESET_ID,
	ResolvedTrainingSelection,
	challenge_label,
	preset_label,
	resolve_training_selection,
)


with import_bundled():
	import chess


@dataclasses.dataclass(frozen=True)
class ThemeInfo:
	slug: str
	label: str
	description: str


@dataclasses.dataclass(frozen=True)
class PuzzleInfo:
	"""A puzzle ready for the board: moves already converted, themes already named."""

	puzzle_id: str
	rating: int | None
	popularity: int | None
	nb_plays: int | None
	fen: str
	game_url: str
	opening_tags: str
	auto_performed_move: chess.Move
	solution_moves: tuple[chess.Move, ...]
	themes: tuple[ThemeInfo, ...]
	# A puzzle the player missed before, served again from the review queue: never rated.
	review: bool = False

	@classmethod
	def from_puzzle(cls, puzzle: Puzzle, review: bool = False) -> PuzzleInfo:
		auto_performed_move, *solution_moves = (chess.Move.from_uci(move) for move in puzzle.moves)
		return cls(
			puzzle_id=puzzle.id,
			rating=puzzle.rating,
			popularity=puzzle.popularity,
			nb_plays=puzzle.nb_plays,
			fen=puzzle.fen,
			game_url=puzzle.game_url,
			opening_tags=puzzle.opening_tags,
			auto_performed_move=auto_performed_move,
			solution_moves=tuple(solution_moves),
			themes=tuple(
				ThemeInfo(slug=slug, label=theme_label(slug), description=theme_description(slug))
				for slug in puzzle.themes
			),
			review=review,
		)


@dataclasses.dataclass(frozen=True)
class TrainingOptions:
	"""What the user chose for the session.

	Only the choice, not what's derived from it: the rating range and
	popularity come from the level, and the themes from the plan (or from
	`custom_theme_text`, when the plan is the custom one). `selection` does
	that math.
	"""

	db_path: str | None = None
	puzzle_id: str = ""
	trainer_preset: str = DEFAULT_TRAINER_PRESET_ID
	challenge_level: str = DEFAULT_CHALLENGE_ID
	custom_theme_text: str = ""

	@property
	def single_puzzle_id(self) -> str:
		"""The typed id, stripped; empty when the session draws at random."""
		return self.puzzle_id.strip()

	@property
	def selection(self) -> ResolvedTrainingSelection:
		return resolve_training_selection(self.trainer_preset, self.challenge_level, self.custom_theme_text)


def default_db_path() -> str | None:
	db_path = resolve_default_db_path()
	return None if db_path is None else str(db_path)


def usable_db_path(candidate: str | None) -> str | None:
	"""Returns `candidate` only if it points to a puzzle database that exists.

	A path saved in the configuration goes stale: the database moves to
	another folder, the drive is removed, the user reinstalls. Being set is
	not the same as existing, and handing a dead path to SQLite blows up
	three layers down with "unable to open database file", which tells the
	reader nothing. We'd rather fall back to the default path, which is what
	the user would expect.

	Existing isn't enough either: since the split into two files, `tactic.db`
	is the history file, and an old configuration may still point to it. Only
	a file that has the puzzles table counts.
	"""
	if not candidate or not Path(candidate).is_file():
		return None
	return candidate if is_puzzles_database(Path(candidate)) else None


def default_training_options() -> TrainingOptions:
	"""The options saved in NVDA's configuration, with the database already validated."""
	from .addon_config import get_tactics_defaults

	defaults = get_tactics_defaults()
	return TrainingOptions(
		db_path=usable_db_path(defaults.db_path) or default_db_path(),
		trainer_preset=defaults.trainer_preset,
		challenge_level=defaults.challenge_level,
		custom_theme_text=defaults.theme,
	)


class TrainingSession:
	def __init__(self, options: TrainingOptions, history_path: Path | None = None):
		"""`history_path` exists only so tests don't touch the user's real history."""
		self.options = options
		self.selection = options.selection
		resolved_db_path = usable_db_path(options.db_path) or default_db_path()
		self.db_path = None if not resolved_db_path else Path(resolved_db_path)
		self.repository = None if self.db_path is None else PuzzleRepository(self.db_path, history_path)
		self._served = 0
		self._seen_ids: list[str] = []
		# The next puzzle, already drawn and converted on a thread while the
		# player is still solving the current one. See prefetch_next.
		self._prefetched: Future | None = None
		# Puzzles the player missed, due today, served before any new one. Filled
		# by ensure_ready; emptied as they are served or when the player skips them.
		self._reviews: list[Puzzle] = []
		self.reviews_total = 0
		self.reviews_served = 0

	# -- preparation ------------------------------------------------------------

	def ensure_ready(self) -> None:
		"""Raises FileNotFoundError with no database, and LookupError when no puzzle matches the options."""
		if self.repository is None:
			raise FileNotFoundError("Tactics database not found.")
		puzzle_id = self.options.single_puzzle_id
		if puzzle_id:
			if self.repository.get(puzzle_id) is None:
				# Translators: Error shown when the typed puzzle id does not exist in the database.
				raise LookupError(_("Puzzle not found: {puzzle_id}").format(puzzle_id=puzzle_id))
			return
		if self.repository.random_puzzle(self._filters()) is None:
			# Translators: Error shown when no puzzle matches the chosen plan, level and themes.
			raise LookupError(_("No puzzles found for the selected filters."))
		self._load_reviews()

	def _load_reviews(self) -> None:
		"""The misses due today open the session, whatever its plan: a missed pattern is worth it at any level."""
		assert self.repository is not None
		self._reviews = self.repository.due_review_puzzles(datetime.date.today(), REVIEWS_PER_SESSION)
		self.reviews_total = len(self._reviews)
		self.reviews_served = 0
		# Kept out of the random draws, so a new puzzle is never one waiting its review turn.
		self._seen_ids.extend(puzzle.id for puzzle in self._reviews if puzzle.id not in self._seen_ids)

	@property
	def reviews_left(self) -> int:
		"""Reviews not served yet in this session."""
		return len(self._reviews)

	def skip_reviews(self) -> None:
		"""The player chose to go straight to new puzzles. The skipped ones stay due for the next session."""
		self._reviews = []

	def _filters(self, excluded_ids: tuple[str, ...] = ()) -> PuzzleFilters:
		return PuzzleFilters(
			min_rating=self.selection.min_rating,
			max_rating=self.selection.max_rating,
			theme_slugs=parse_theme_filter(self.selection.theme_text),
			min_popularity=self.selection.min_popularity,
			excluded_ids=excluded_ids,
		)

	# -- puzzle sequence --------------------------------------------------------

	def next_puzzle(self) -> PuzzleInfo | None:
		"""The next puzzle, or None when the session has ended. Due reviews come first."""
		if self._reviews:
			puzzle = self._reviews.pop(0)
			self.reviews_served += 1
			return PuzzleInfo.from_puzzle(puzzle, review=True)
		future, self._prefetched = self._prefetched, None
		if future is not None:
			# If the thread has already finished, this returns right away; if
			# not, it waits only for what's left -- never more than the full
			# draw would cost here.
			puzzle = future.result()
		else:
			puzzle = self._draw(tuple(self._seen_ids))
		if puzzle is None:
			return None
		self._served += 1
		if puzzle.id not in self._seen_ids:
			self._seen_ids.append(puzzle.id)
		return PuzzleInfo.from_puzzle(puzzle)

	def prefetch_next(self) -> None:
		"""Draws the next puzzle on a thread, so Control+N doesn't have to wait.

		Called right after a puzzle is loaded. The draw uses the ids already
		seen so far (including the current one) and, in adaptive mode, the
		rating as of now -- the attempt in progress will nudge it a little, so
		the prefetched puzzle ends up calibrated on the rating from one puzzle
		back. That's a difference of a few points within a window of hundreds,
		and the cost of waiting on the database on every Control+N was bigger.
		"""
		if self._prefetched is not None or self.repository is None or self.options.single_puzzle_id:
			return
		from .concurrency import THREADED_EXECUTOR

		seen_snapshot = tuple(self._seen_ids)
		try:
			self._prefetched = THREADED_EXECUTOR.submit(self._draw, seen_snapshot)
		except RuntimeError:
			# Executor already shut down (NVDA closing): the next draw will be synchronous.
			self._prefetched = None

	def _draw(self, excluded_ids: tuple[str, ...]) -> Puzzle | None:
		if self.repository is None:
			raise FileNotFoundError("Tactics database not found.")
		puzzle_id = self.options.single_puzzle_id
		if puzzle_id:
			# Single-puzzle session: it comes out once, then the session ends.
			return None if self._served else self.repository.get(puzzle_id)
		filters = self._filters(excluded_ids)
		if self.selection.adaptive:
			# In adaptive mode the rating range doesn't come from the user's
			# choice: it's derived from their rating on every draw, on the
			# database side, where the rating lives.
			return self.repository.adaptive_random_puzzle(filters)
		return self.repository.random_puzzle(filters)

	# -- description ------------------------------------------------------------

	def describe_filters(self) -> str:
		puzzle_id = self.options.single_puzzle_id
		if puzzle_id:
			# Translators: Session description when one puzzle was opened by id.
			return _("Puzzle ID {puzzle_id}").format(puzzle_id=puzzle_id)
		parts = [
			# Translators: Part of the session description, e.g. "Training plan: Fundamentals".
			_("Training plan: {plan}").format(plan=preset_label(self.selection.preset)),
			# Translators: Part of the session description, e.g. "Challenge: Intermediate".
			_("Challenge: {level}").format(level=challenge_label(self.selection.challenge)),
		]
		if self.selection.theme_text:
			# Translators: Part of the session description, e.g. "Themes: Fork, Pin".
			parts.append(
				_("Themes: {themes}").format(themes=describe_theme_filter(self.selection.theme_text)),
			)
		if self.selection.min_popularity:
			# Translators: Part of the session description.
			parts.append(
				_("Minimum popularity: {popularity}").format(popularity=self.selection.min_popularity),
			)
		# The rating range is already inside challenge_label; repeating it here would say it twice.
		return "; ".join(parts)

	# -- player history ---------------------------------------------------------

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
		revealed: bool = False,
	) -> AttemptResult | None:
		"""Records the attempt and returns how the rating changed, or None with no database."""
		if self.repository is None:
			return None
		return self.repository.record_attempt(puzzle_id, solved, mistakes, hints_used, elapsed_ms, revealed)

	def record_review(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		revealed: bool,
		elapsed_ms: int,
	) -> ReviewOutcome | None:
		"""Records a review (never rated) and says where the puzzle stands, or None with no database."""
		if self.repository is None:
			return None
		return self.repository.record_review(puzzle_id, solved, mistakes, hints_used, revealed, elapsed_ms)

	def rating(self) -> RatingSummary | None:
		"""The player's current rating, or None when there's no database."""
		if self.repository is None:
			return None
		return self.repository.rating()

	def attempt_stats(self) -> AttemptStats:
		if self.repository is None:
			return AttemptStats()
		return self.repository.attempt_stats()
