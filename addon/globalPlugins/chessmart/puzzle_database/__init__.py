# coding: utf-8

from __future__ import annotations

import dataclasses
import typing as t
from concurrent.futures import Future
from pathlib import Path

from ..helpers import import_bundled
from ..i18n import _
from ..theme_catalog import (
	describe_theme_filter,
	get_theme_entry,
	humanize_theme_slug,
	load_theme_catalog,
	parse_theme_filter,
)
from ..tactic.db import resolve_default_db_path
from ..tactic.repository import PuzzleRepository
from ..trainer import challenge_label, get_challenge_level, get_trainer_preset, preset_label


with import_bundled():
	import chess


@dataclasses.dataclass(frozen=True)
class ThemeInfo:
	slug: str
	label: str
	description: str


@dataclasses.dataclass(frozen=True)
class PuzzleInfo:
	puzzle_id: str
	rating: int | None
	popularity: int | None
	nb_plays: int | None
	fen: str
	game_url: str
	opening_tags: str
	auto_performed_move: chess.Move
	solution_moves: t.Tuple[chess.Move, ...]
	themes: t.Tuple[ThemeInfo, ...]

	def get_theme_info(self):
		for theme in self.themes:
			yield theme.label, theme.description


@dataclasses.dataclass(frozen=True)
class TacticSessionOptions:
	db_path: str | None = None
	puzzle_id: str = ""
	theme: str = ""
	trainer_preset: str = ""
	challenge_level: str = ""
	min_rating: int | None = 800
	max_rating: int | None = 1600
	min_popularity: int | None = 50
	# Quando verdadeiro, min_rating e max_rating são ignorados: a faixa passa a
	# ser derivada do rating do jogador a cada sorteio.
	adaptive: bool = False


def get_default_tactic_db_path() -> str | None:
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
	from ..tactic.db import is_puzzles_database

	return candidate if is_puzzles_database(Path(candidate)) else None


def _load_tactic_defaults():
	try:
		from ..addon_config import get_tactics_defaults
	except ImportError:
		return None
	return get_tactics_defaults()


def get_default_tactic_session_options() -> TacticSessionOptions:
	defaults = _load_tactic_defaults()
	if defaults is None:
		return TacticSessionOptions(db_path=get_default_tactic_db_path())
	return TacticSessionOptions(
		db_path=usable_db_path(defaults.db_path) or get_default_tactic_db_path(),
		theme=defaults.theme,
		trainer_preset=defaults.trainer_preset,
		challenge_level=defaults.challenge_level,
		min_rating=defaults.min_rating,
		max_rating=defaults.max_rating,
		min_popularity=defaults.min_popularity,
		# O nível escolhido é que decide se o sorteio é calibrado; a
		# configuração guarda o identificador dele, não o comportamento.
		adaptive=get_challenge_level(defaults.challenge_level).adaptive,
	)


def _theme_info_from_slug(theme_slug: str, db_path: Path | None = None) -> ThemeInfo:
	catalog_entry = get_theme_entry(theme_slug, db_path=db_path)
	if catalog_entry is not None:
		return ThemeInfo(
			slug=catalog_entry.slug,
			label=catalog_entry.label,
			description=catalog_entry.description,
		)
	label = humanize_theme_slug(theme_slug)
	return ThemeInfo(
		slug=theme_slug,
		label=label,
		# Translators: Description of a puzzle theme that is not in the catalog yet.
		description=_("Lichess theme: {label}.").format(label=label),
	)


def _puzzle_info_from_record(record, db_path: Path | None = None) -> PuzzleInfo:
	auto_performed_move, *solution_moves = (chess.Move.from_uci(move) for move in record.moves)
	return PuzzleInfo(
		puzzle_id=record.id,
		rating=record.rating,
		popularity=record.popularity,
		nb_plays=record.nb_plays,
		fen=record.fen,
		game_url=record.game_url,
		opening_tags=record.opening_tags,
		auto_performed_move=auto_performed_move,
		solution_moves=tuple(solution_moves),
		themes=tuple(_theme_info_from_slug(theme, db_path=db_path) for theme in record.themes),
	)


@dataclasses.dataclass
class PuzzleSet:
	options: TacticSessionOptions
	current_item_index: int = 0
	_seen_puzzle_ids: list[str] = dataclasses.field(default_factory=list)
	# O próximo puzzle, já sorteado e convertido numa thread enquanto o
	# jogador ainda resolve o atual. Ver prefetch_next.
	_prefetched: "Future | None" = dataclasses.field(default=None, repr=False)

	def __post_init__(self):
		default_options = get_default_tactic_session_options()
		resolved_db_path = usable_db_path(self.options.db_path) or default_options.db_path
		self.db_path = None if not resolved_db_path else Path(resolved_db_path)
		self.repository = None if self.db_path is None else PuzzleRepository(self.db_path)

	def __getitem__(self, index):
		raise TypeError("Puzzle sets backed by the tactics database are not indexable.")

	def __iter__(self):
		return self

	def __next__(self):
		future, self._prefetched = self._prefetched, None
		if future is not None:
			# Se a thread já terminou, isto volta na hora; se não, espera só
			# o que falta -- nunca mais do que o sorteio inteiro custaria aqui.
			record, info = future.result()
		else:
			record = self._get_next_record()
			info = None if record is None else _puzzle_info_from_record(record, db_path=self.db_path)
		if record is None:
			raise StopIteration
		self.current_item_index += 1
		if record.id not in self._seen_puzzle_ids:
			self._seen_puzzle_ids.append(record.id)
		return info

	def prefetch_next(self) -> None:
		"""Sorteia o próximo puzzle numa thread, para o Control+N não esperar.

		Chamado logo depois de um puzzle ser carregado. O sorteio usa os ids já
		vistos até aqui (o atual incluído) e, no modo adaptativo, o rating de
		agora -- a tentativa em andamento vai mexer nele um pouco, e o puzzle
		pré-sorteado fica calibrado pelo rating de um puzzle atrás. É uma
		diferença de poucos pontos dentro de uma janela de centenas, e o
		preço de esperar o banco a cada Control+N era maior.
		"""
		if self._prefetched is not None or self.repository is None:
			return
		if self.options.puzzle_id.strip():
			return
		seen_snapshot = list(self._seen_puzzle_ids)
		try:
			from ..concurrency import THREADED_EXECUTOR
		except ImportError:
			return

		def work():
			record = self._get_next_record(seen_ids=seen_snapshot)
			info = None if record is None else _puzzle_info_from_record(record, db_path=self.db_path)
			return record, info

		try:
			self._prefetched = THREADED_EXECUTOR.submit(work)
		except RuntimeError:
			self._prefetched = None

	def discard_prefetch(self) -> None:
		"""Esquece o pré-sorteio (por exemplo quando a sessão termina)."""
		self._prefetched = None

	def _get_next_record(self, seen_ids: list[str] | None = None):
		if self.repository is None:
			raise FileNotFoundError("Tactics database not found.")
		if seen_ids is None:
			seen_ids = self._seen_puzzle_ids

		puzzle_id = self.options.puzzle_id.strip()
		if puzzle_id:
			if self.current_item_index > 0:
				return None
			return self.repository.get(puzzle_id)

		theme_slugs = parse_theme_filter(self.options.theme)
		if self.options.adaptive:
			# No modo adaptativo a faixa de rating não vem da escolha do
			# usuário: ela é derivada do rating dele a cada sorteio, do lado do
			# banco, onde o rating vive.
			return self.repository.adaptive_random_puzzle(
				theme=theme_slugs or None,
				min_popularity=self.options.min_popularity,
				excluded_ids=seen_ids,
			)
		return self.repository.random_puzzle(
			min_rating=self.options.min_rating,
			max_rating=self.options.max_rating,
			theme=theme_slugs or None,
			min_popularity=self.options.min_popularity,
			excluded_ids=seen_ids,
		)

	def ensure_ready(self):
		if self.repository is None or self.db_path is None:
			raise FileNotFoundError("Tactics database not found.")

		if self.options.puzzle_id.strip():
			if self.repository.get(self.options.puzzle_id.strip()) is None:
				raise LookupError(
					# Translators: Error shown when the typed puzzle id does not exist in the database.
					_("Puzzle not found: {puzzle_id}").format(puzzle_id=self.options.puzzle_id.strip()),
				)
			return

		preview = self.repository.random_puzzle(
			min_rating=self.options.min_rating,
			max_rating=self.options.max_rating,
			theme=parse_theme_filter(self.options.theme) or None,
			min_popularity=self.options.min_popularity,
		)
		if preview is None:
			# Translators: Error shown when no puzzle matches the chosen plan, level and themes.
			raise LookupError(_("No puzzles found for the selected filters."))

	def describe_filters(self) -> str:
		if self.options.puzzle_id.strip():
			# Translators: Session description when one puzzle was opened by id.
			return _("Puzzle ID {puzzle_id}").format(puzzle_id=self.options.puzzle_id.strip())

		parts = []
		if self.options.trainer_preset:
			preset = get_trainer_preset(self.options.trainer_preset)
			# Translators: Part of the session description, e.g. "Training plan: Guided basics".
			parts.append(_("Training plan: {plan}").format(plan=preset_label(preset)))
		if self.options.challenge_level:
			challenge = get_challenge_level(self.options.challenge_level)
			# Translators: Part of the session description, e.g. "Challenge: Balanced".
			parts.append(_("Challenge: {level}").format(level=challenge_label(challenge)))
		if self.options.theme.strip():
			parts.append(
				# Translators: Part of the session description, e.g. "Themes: Fork, Pin".
				_("Themes: {themes}").format(
					themes=describe_theme_filter(self.options.theme, db_path=self.db_path)
					or self.options.theme.strip(),
				),
			)
		if self.options.min_rating is not None or self.options.max_rating is not None:
			# Translators: Used for an open end of the rating range, e.g. "Rating: any to 1600".
			min_rating = _("any") if self.options.min_rating is None else str(self.options.min_rating)
			max_rating = _("any") if self.options.max_rating is None else str(self.options.max_rating)
			# Translators: Part of the session description, e.g. "Rating: 800 to 1600".
			parts.append(_("Rating: {low} to {high}").format(low=min_rating, high=max_rating))
		if self.options.min_popularity:
			# Translators: Part of the session description.
			parts.append(_("Minimum popularity: {popularity}").format(popularity=self.options.min_popularity))
		return "; ".join(parts)

	def available_themes(self):
		return load_theme_catalog(self.db_path)

	def record_attempt(
		self,
		puzzle_id: str,
		solved: bool,
		mistakes: int,
		hints_used: int,
		elapsed_ms: int,
	):
		"""Grava a tentativa e devolve o rating resultante, ou None sem banco."""
		if self.repository is None:
			return None
		return self.repository.record_attempt(
			puzzle_id=puzzle_id,
			solved=solved,
			mistakes=mistakes,
			hints_used=hints_used,
			elapsed_ms=elapsed_ms,
		)

	def rating(self):
		"""O rating atual do jogador, ou None quando não há banco."""
		if self.repository is None:
			return None
		return self.repository.rating()

	def attempt_stats(self):
		if self.repository is None:
			return {"total": 0, "solved": 0, "mistakes": 0, "hints_used": 0}
		return self.repository.attempt_stats()

	def save_history(self):
		return None

	def load_history(self):
		raise FileNotFoundError("Tactic sessions do not persist history.")


class RandomPuzzleSet(PuzzleSet):
	def __init__(self, db_path: str | None = None):
		default_options = get_default_tactic_session_options()
		super().__init__(
			options=TacticSessionOptions(
				db_path=usable_db_path(db_path) or default_options.db_path,
				puzzle_id="",
				theme=default_options.theme,
				trainer_preset=default_options.trainer_preset,
				challenge_level=default_options.challenge_level,
				min_rating=default_options.min_rating,
				max_rating=default_options.max_rating,
				min_popularity=default_options.min_popularity,
			),
		)
