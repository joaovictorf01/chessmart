# coding: utf-8

from __future__ import annotations

import json
from pathlib import Path

from .db import run_bridge
from .models import Puzzle


def puzzle_from_row(row) -> Puzzle:
	return Puzzle(
		id=row["id"],
		fen=row["fen"],
		moves=row["moves"],
		rating=row["rating"],
		rating_deviation=row["rating_deviation"],
		popularity=row["popularity"],
		nb_plays=row["nb_plays"],
		themes=row["themes"],
		game_url=row["game_url"],
		opening_tags=row["opening_tags"],
	)


class PuzzleRepository:
	def __init__(self, db_path: Path):
		self.db_path = db_path

	def count(self) -> int:
		return int(run_bridge(self.db_path, "count"))

	def get(self, puzzle_id: str) -> Puzzle | None:
		row = run_bridge(self.db_path, "get", puzzle_id)
		return puzzle_from_row(row) if row else None

	def random_puzzle(
		self,
		min_rating: int | None = None,
		max_rating: int | None = None,
		theme: str | list[str] | tuple[str, ...] | None = None,
		min_popularity: int | None = 0,
		excluded_ids: list[str] | tuple[str, ...] | None = None,
	) -> Puzzle | None:
		if isinstance(theme, (list, tuple)):
			theme_filter = ",".join(theme)
		else:
			theme_filter = theme or ""
		row = run_bridge(
			self.db_path,
			"random",
			"" if min_rating is None else min_rating,
			"" if max_rating is None else max_rating,
			theme_filter,
			"" if min_popularity is None else min_popularity,
			json.dumps(list(excluded_ids or ()), ensure_ascii=False),
		)
		return puzzle_from_row(row) if row else None

	def adaptive_random_puzzle(
		self,
		theme: str | list[str] | tuple[str, ...] | None = None,
		min_popularity: int | None = 0,
		excluded_ids: list[str] | tuple[str, ...] | None = None,
	) -> Puzzle | None:
		"""Sorteia calibrado pelo rating atual, sem faixa vinda de fora."""
		if isinstance(theme, (list, tuple)):
			theme_filter = ",".join(theme)
		else:
			theme_filter = theme or ""
		row = run_bridge(
			self.db_path,
			"adaptiveRandom",
			theme_filter,
			"" if min_popularity is None else min_popularity,
			json.dumps(list(excluded_ids or ()), ensure_ascii=False),
		)
		return puzzle_from_row(row) if row else None

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
	):
		"""Grava a tentativa e devolve o rating resultante.

		A ponte já calcula o Glicko-2 e responde com rating, ratingDelta e
		deviation. Devolver isso aqui evita uma segunda ida ao banco só para
		descobrir o que a tentativa mudou.
		"""
		return run_bridge(
			self.db_path,
			"recordAttempt",
			puzzle_id,
			int(solved),
			mistakes,
			hints_used,
			elapsed_ms,
		)

	def rating(self):
		return run_bridge(self.db_path, "rating")

	def attempt_stats(self):
		return run_bridge(self.db_path, "attemptStats")

	def theme_catalog(self):
		return run_bridge(self.db_path, "themeCatalog")
