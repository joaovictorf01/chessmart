# coding: utf-8
# pyright: basic

"""A fachada que o resto do add-on usa para falar com o banco.

Cada chamada abre a conexão, faz uma coisa e fecha. É simples e é o que cabe
aqui: as chamadas são raras (um sorteio, uma gravação) e nunca concorrem.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from .db import HISTORY_DB_PATH, load_store
from .models import AttemptResult, AttemptStats, Puzzle, PuzzleFilters, RatingSummary


class PuzzleRepository:
	def __init__(self, db_path: Path, history_path: Path | None = None):
		"""`db_path` é o banco de puzzles; o histórico é sempre o do usuário, salvo em teste."""
		self.db_path = Path(db_path)
		self.history_path = Path(history_path) if history_path else HISTORY_DB_PATH

	@contextlib.contextmanager
	def _open(self):
		store = load_store()
		connection = store.connect(self.db_path, self.history_path)
		try:
			# O `with` da conexão cuida do commit/rollback; fechar é por nossa conta.
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
		"""Sorteia calibrado pelo rating atual; a faixa de rating de `filters` é ignorada."""
		with self._open() as (store, connection):
			return store.adaptive_random_puzzle(connection, filters)

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
	) -> AttemptResult:
		with self._open() as (store, connection):
			return store.record_attempt(connection, puzzle_id, solved, mistakes, hints_used, elapsed_ms)

	def rating(self) -> RatingSummary:
		with self._open() as (store, connection):
			return store.rating(connection)

	def attempt_stats(self) -> AttemptStats:
		with self._open() as (store, connection):
			return store.attempt_stats(connection)

	def theme_counts(self) -> list[tuple[str, int]]:
		"""Cada tema do banco com quantos puzzles o têm. Varre a tabela inteira."""
		with self._open() as (store, connection):
			return store.theme_counts(connection)
