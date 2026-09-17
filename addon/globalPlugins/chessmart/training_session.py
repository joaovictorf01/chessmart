# coding: utf-8

"""Uma sessão de treino de táticas: as opções escolhidas e a sequência de puzzles.

`TrainingOptions` é o que o usuário decidiu (banco, plano, nível, temas, ou um
id de puzzle). `TrainingSession` sorteia os puzzles a partir disso, um por vez,
sem repetir, e faz de passagem o que a tela precisa do banco: gravar tentativa,
ler rating e estatísticas.
"""

from __future__ import annotations

import dataclasses
from concurrent.futures import Future
from pathlib import Path

from .helpers import import_bundled
from .i18n import _
from .tactic.db import is_puzzles_database, resolve_default_db_path
from .tactic.models import AttemptResult, AttemptStats, Puzzle, PuzzleFilters, RatingSummary
from .tactic.repository import PuzzleRepository
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
	"""Um puzzle pronto para o tabuleiro: lances já convertidos, temas já nomeados."""

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

	@classmethod
	def from_puzzle(cls, puzzle: Puzzle) -> PuzzleInfo:
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
		)


@dataclasses.dataclass(frozen=True)
class TrainingOptions:
	"""O que o usuário escolheu para a sessão.

	Só a escolha, não o que se deriva dela: a faixa de rating e a popularidade
	vêm do nível, e os temas do plano (ou de `custom_theme_text`, quando o
	plano é o personalizado). `selection` faz essa conta.
	"""

	db_path: str | None = None
	puzzle_id: str = ""
	trainer_preset: str = DEFAULT_TRAINER_PRESET_ID
	challenge_level: str = DEFAULT_CHALLENGE_ID
	custom_theme_text: str = ""

	@property
	def single_puzzle_id(self) -> str:
		"""O id digitado, limpo; vazio quando a sessão é de sorteio."""
		return self.puzzle_id.strip()

	@property
	def selection(self) -> ResolvedTrainingSelection:
		return resolve_training_selection(self.trainer_preset, self.challenge_level, self.custom_theme_text)


def default_db_path() -> str | None:
	db_path = resolve_default_db_path()
	return None if db_path is None else str(db_path)


def usable_db_path(candidate: str | None) -> str | None:
	"""Devolve `candidate` só se ele apontar para um banco de puzzles que existe.

	Um caminho guardado na configuração envelhece: o banco muda de pasta, o
	disco sai da máquina, o usuário reinstala. Preencher não é o mesmo que
	existir, e entregar um caminho morto ao SQLite estoura três camadas
	abaixo com "unable to open database file", que não diz nada a quem lê.
	Preferimos cair no caminho padrão, que é o que o usuário esperaria.

	Existir também não basta: desde a divisão em dois arquivos, `tactic.db` é
	o histórico, e uma configuração antiga ainda aponta para ele. Só vale o
	arquivo que tem a tabela de puzzles.
	"""
	if not candidate or not Path(candidate).is_file():
		return None
	return candidate if is_puzzles_database(Path(candidate)) else None


def default_training_options() -> TrainingOptions:
	"""As opções guardadas na configuração do NVDA, com o banco já validado."""
	from .addon_config import get_tactics_defaults

	defaults = get_tactics_defaults()
	return TrainingOptions(
		db_path=usable_db_path(defaults.db_path) or default_db_path(),
		trainer_preset=defaults.trainer_preset,
		challenge_level=defaults.challenge_level,
		custom_theme_text=defaults.theme,
	)


class TrainingSession:
	def __init__(self, options: TrainingOptions):
		self.options = options
		self.selection = options.selection
		resolved_db_path = usable_db_path(options.db_path) or default_db_path()
		self.db_path = None if not resolved_db_path else Path(resolved_db_path)
		self.repository = None if self.db_path is None else PuzzleRepository(self.db_path)
		self._served = 0
		self._seen_ids: list[str] = []
		# O próximo puzzle, já sorteado e convertido numa thread enquanto o
		# jogador ainda resolve o atual. Ver prefetch_next.
		self._prefetched: Future | None = None

	# -- preparação -----------------------------------------------------------

	def ensure_ready(self) -> None:
		"""Levanta FileNotFoundError sem banco e LookupError sem puzzle para as opções."""
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

	def _filters(self, excluded_ids: tuple[str, ...] = ()) -> PuzzleFilters:
		return PuzzleFilters(
			min_rating=self.selection.min_rating,
			max_rating=self.selection.max_rating,
			theme_slugs=parse_theme_filter(self.selection.theme_text),
			min_popularity=self.selection.min_popularity,
			excluded_ids=excluded_ids,
		)

	# -- sequência de puzzles ------------------------------------------------

	def next_puzzle(self) -> PuzzleInfo | None:
		"""O próximo puzzle, ou None quando a sessão acabou."""
		future, self._prefetched = self._prefetched, None
		if future is not None:
			# Se a thread já terminou, isto volta na hora; se não, espera só
			# o que falta -- nunca mais do que o sorteio inteiro custaria aqui.
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
		"""Sorteia o próximo puzzle numa thread, para o Control+N não esperar.

		Chamado logo depois de um puzzle ser carregado. O sorteio usa os ids já
		vistos até aqui (o atual incluído) e, no modo adaptativo, o rating de
		agora -- a tentativa em andamento vai mexer nele um pouco, e o puzzle
		pré-sorteado fica calibrado pelo rating de um puzzle atrás. É uma
		diferença de poucos pontos dentro de uma janela de centenas, e o
		preço de esperar o banco a cada Control+N era maior.
		"""
		if self._prefetched is not None or self.repository is None or self.options.single_puzzle_id:
			return
		from .concurrency import THREADED_EXECUTOR

		seen_snapshot = tuple(self._seen_ids)
		try:
			self._prefetched = THREADED_EXECUTOR.submit(self._draw, seen_snapshot)
		except RuntimeError:
			# Executor já encerrado (NVDA fechando): o próximo sorteio será síncrono.
			self._prefetched = None

	def _draw(self, excluded_ids: tuple[str, ...]) -> Puzzle | None:
		if self.repository is None:
			raise FileNotFoundError("Tactics database not found.")
		puzzle_id = self.options.single_puzzle_id
		if puzzle_id:
			# Sessão de um puzzle só: ele sai uma vez, e depois a sessão acaba.
			return None if self._served else self.repository.get(puzzle_id)
		filters = self._filters(excluded_ids)
		if self.selection.adaptive:
			# No modo adaptativo a faixa de rating não vem da escolha do
			# usuário: ela é derivada do rating dele a cada sorteio, do lado do
			# banco, onde o rating vive.
			return self.repository.adaptive_random_puzzle(filters)
		return self.repository.random_puzzle(filters)

	# -- descrição ------------------------------------------------------------

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
				_("Themes: {themes}").format(themes=describe_theme_filter(self.selection.theme_text))
			)
		if self.selection.min_popularity:
			# Translators: Part of the session description.
			parts.append(
				_("Minimum popularity: {popularity}").format(popularity=self.selection.min_popularity)
			)
		# A faixa de rating já vem dentro de challenge_label; repeti-la seria falar duas vezes.
		return "; ".join(parts)

	# -- histórico do jogador --------------------------------------------------

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
	) -> AttemptResult | None:
		"""Grava a tentativa e devolve o que mudou no rating, ou None sem banco."""
		if self.repository is None:
			return None
		return self.repository.record_attempt(puzzle_id, solved, mistakes, hints_used, elapsed_ms)

	def rating(self) -> RatingSummary | None:
		"""O rating atual do jogador, ou None quando não há banco."""
		if self.repository is None:
			return None
		return self.repository.rating()

	def attempt_stats(self) -> AttemptStats:
		if self.repository is None:
			return AttemptStats()
		return self.repository.attempt_stats()
