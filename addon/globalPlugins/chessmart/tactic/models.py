# coding: utf-8

"""Os valores que circulam entre o banco de puzzles e o resto do add-on.

Tudo aqui é dado puro: nada de NVDA, nada de sqlite. É o contrato que
`store.py` cumpre e que a camada de cima consome pelo nome do campo, em vez de
por chave de dicionário.
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
	"""O que restringe um sorteio. Campo em None (ou vazio) não entra na consulta."""

	min_rating: int | None = None
	max_rating: int | None = None
	theme_slugs: tuple[str, ...] = ()
	min_popularity: int | None = None
	excluded_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttemptResult:
	"""O que uma tentativa gravada mudou no rating do jogador."""

	attempt_id: int
	rating_before: int
	rating: int
	deviation: float

	@property
	def rating_delta(self) -> int:
		return self.rating - self.rating_before

	@property
	def provisional(self) -> bool:
		"""Enquanto o desvio é grande o número ainda é chute, e vale dizer isso a quem ouve."""
		return self.deviation > PROVISIONAL_DEVIATION


@dataclass(frozen=True)
class RatingSummary:
	"""O rating atual, com a faixa de confiança e quantas tentativas o formaram."""

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
	"""Totais do histórico inteiro do jogador."""

	total: int = 0
	solved: int = 0
	mistakes: int = 0
	hints_used: int = 0
