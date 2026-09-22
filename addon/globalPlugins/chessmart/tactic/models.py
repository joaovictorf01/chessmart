# coding: utf-8
# pyright: basic

"""The values that flow between the puzzle database and the rest of the add-on.

Everything here is plain data: no NVDA, no sqlite. It is the contract that
`store.py` fulfills and that the layer above consumes by field name, instead
of by dictionary key.
"""

from __future__ import annotations

from dataclasses import dataclass

from .glicko2 import PROVISIONAL_DEVIATION


@dataclass(frozen=True)
class Puzzle:
	id: str
	fen: str
	moves: list[str]
	rating: int | None
	rating_deviation: int | None
	popularity: int | None
	nb_plays: int | None
	themes: list[str]
	game_url: str
	opening_tags: str


@dataclass(frozen=True)
class PuzzleFilters:
	"""What constrains a random draw. A field left as None (or empty) is left out of the query."""

	min_rating: int | None = None
	max_rating: int | None = None
	theme_slugs: tuple[str, ...] = ()
	min_popularity: int | None = None
	excluded_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttemptResult:
	"""What a recorded attempt changed in the player's rating."""

	attempt_id: int
	rating_before: int
	rating: int
	deviation: float

	@property
	def rating_delta(self) -> int:
		return self.rating - self.rating_before

	@property
	def provisional(self) -> bool:
		"""While the deviation is large the number is still a guess, and that's worth telling the listener."""
		return self.deviation > PROVISIONAL_DEVIATION


@dataclass(frozen=True)
class RatingSummary:
	"""The current rating, with its confidence interval and how many attempts shaped it."""

	rating: int
	deviation: float
	volatility: float
	interval_low: int
	interval_high: int
	rated_attempts: int

	@property
	def provisional(self) -> bool:
		return self.deviation > PROVISIONAL_DEVIATION


@dataclass(frozen=True)
class AttemptStats:
	"""Totals across the player's whole history."""

	total: int = 0
	solved: int = 0
	mistakes: int = 0
	hints_used: int = 0
