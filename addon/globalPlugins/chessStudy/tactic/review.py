# coding: utf-8
# pyright: basic

"""The review queue: puzzles the player missed come back until they are firm.

A puzzle enters the queue when a rated attempt went wrong: a wrong move, a
hint, or the solution revealed with Control+Enter. It comes back the next day.
A clean review (solved with no wrong move, no hint, nothing revealed) moves it
three days further; the second clean review in a row makes it firm and it
leaves the queue. A review with a slip starts the count over, back the next day.

Nothing here is stored as state: the queue is worked out from the history
every time, so it can never drift from what actually happened. Reviews never
touch the rating -- the solution was already seen once, and rating it would
be farming. They count in their own number: how many are firm.

No NVDA and no sqlite here: `store.py` reads the events, this decides.
"""

from __future__ import annotations

import dataclasses
import datetime
from typing import Iterable

# Days until the puzzle comes back, indexed by how many clean reviews in a row it has.
REVIEW_INTERVALS_DAYS = (1, 3)
# Clean reviews in a row that make a puzzle firm.
FIRM_AFTER = len(REVIEW_INTERVALS_DAYS)
# At most this many reviews open a session, oldest first; the rest wait for the next one.
REVIEWS_PER_SESSION = 3


@dataclasses.dataclass(frozen=True)
class ReviewEvent:
	"""One attempt at a puzzle, rated or review, reduced to what the queue needs."""

	puzzle_id: str
	day: datetime.date
	clean: bool
	is_review: bool


@dataclasses.dataclass(frozen=True)
class ReviewItem:
	"""A puzzle in the queue."""

	puzzle_id: str
	due: datetime.date
	clean_streak: int
	missed_on: datetime.date


@dataclasses.dataclass(frozen=True)
class ReviewQueue:
	items: tuple[ReviewItem, ...]
	firm: int

	def due(self, today: datetime.date) -> list[ReviewItem]:
		"""The puzzles whose day has come, the longest waiting first."""
		return sorted(
			(item for item in self.items if item.due <= today),
			key=lambda item: (item.due, item.missed_on, item.puzzle_id),
		)

	def waiting(self, today: datetime.date) -> int:
		return sum(1 for item in self.items if item.due > today)


def build_queue(events: Iterable[ReviewEvent]) -> ReviewQueue:
	"""Replay the history in order and say what is in the queue and how many became firm.

	`events` must come in the order they happened. A rated attempt that goes
	wrong puts a puzzle in (or back in); a clean rated attempt of a puzzle in
	the queue (opened by its id) counts like a clean review.
	"""
	pending: dict[str, ReviewItem] = {}
	firm: set[str] = set()
	for event in events:
		item = pending.get(event.puzzle_id)
		if not event.clean:
			pending[event.puzzle_id] = ReviewItem(
				puzzle_id=event.puzzle_id,
				due=event.day + datetime.timedelta(days=REVIEW_INTERVALS_DAYS[0]),
				clean_streak=0,
				missed_on=event.day if item is None else item.missed_on,
			)
			firm.discard(event.puzzle_id)
			continue
		if item is None:
			# A clean attempt at a puzzle that is not in the queue: nothing to review.
			continue
		streak = item.clean_streak + 1
		if streak >= FIRM_AFTER:
			del pending[event.puzzle_id]
			firm.add(event.puzzle_id)
			continue
		pending[event.puzzle_id] = dataclasses.replace(
			item,
			due=event.day + datetime.timedelta(days=REVIEW_INTERVALS_DAYS[streak]),
			clean_streak=streak,
		)
	return ReviewQueue(items=tuple(pending.values()), firm=len(firm))


@dataclasses.dataclass(frozen=True)
class ReviewOutcome:
	"""Where a puzzle stands right after a review, to say it to the player."""

	clean: bool
	clean_streak: int
	firm: bool
	due: datetime.date | None

	@property
	def clean_needed(self) -> int:
		return FIRM_AFTER


def outcome_for(queue: ReviewQueue, puzzle_id: str, clean: bool) -> ReviewOutcome:
	"""Read one puzzle's place in a queue already rebuilt with its latest review."""
	item = next((item for item in queue.items if item.puzzle_id == puzzle_id), None)
	if item is None:
		return ReviewOutcome(clean=clean, clean_streak=FIRM_AFTER, firm=True, due=None)
	return ReviewOutcome(clean=clean, clean_streak=item.clean_streak, firm=False, due=item.due)
