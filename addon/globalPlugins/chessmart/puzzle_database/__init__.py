# coding: utf-8

from __future__ import annotations

import dataclasses
import typing as t
from pathlib import Path

from ..helpers import import_bundled
from ..theme_catalog import (
    describe_theme_filter,
    get_theme_entry,
    humanize_theme_slug,
    load_theme_catalog,
    parse_theme_filter,
)
from ..tactic.db import resolve_default_db_path
from ..tactic.repository import PuzzleRepository
from ..trainer import get_challenge_level, get_trainer_preset


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


def get_default_tactic_db_path() -> str | None:
    db_path = resolve_default_db_path()
    return None if db_path is None else str(db_path)


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
        db_path=defaults.db_path or get_default_tactic_db_path(),
        theme=defaults.theme,
        trainer_preset=defaults.trainer_preset,
        challenge_level=defaults.challenge_level,
        min_rating=defaults.min_rating,
        max_rating=defaults.max_rating,
        min_popularity=defaults.min_popularity,
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
        description=f"Tema do Lichess: {label}.",
    )


def _puzzle_info_from_record(record, db_path: Path | None = None) -> PuzzleInfo:
    auto_performed_move, *solution_moves = (
        chess.Move.from_uci(move) for move in record.moves
    )
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

    def __post_init__(self):
        default_options = get_default_tactic_session_options()
        resolved_db_path = self.options.db_path or default_options.db_path
        self.db_path = None if not resolved_db_path else Path(resolved_db_path)
        self.repository = None if self.db_path is None else PuzzleRepository(self.db_path)

    def __getitem__(self, index):
        raise TypeError("Puzzle sets backed by the tactics database are not indexable.")

    def __iter__(self):
        return self

    def __next__(self):
        record = self._get_next_record()
        if record is None:
            raise StopIteration
        self.current_item_index += 1
        if record.id not in self._seen_puzzle_ids:
            self._seen_puzzle_ids.append(record.id)
        return _puzzle_info_from_record(record, db_path=self.db_path)

    def _get_next_record(self):
        if self.repository is None:
            raise FileNotFoundError("Tactics database not found.")

        puzzle_id = self.options.puzzle_id.strip()
        if puzzle_id:
            if self.current_item_index > 0:
                return None
            return self.repository.get(puzzle_id)

        theme_slugs = parse_theme_filter(self.options.theme)
        return self.repository.random_puzzle(
            min_rating=self.options.min_rating,
            max_rating=self.options.max_rating,
            theme=theme_slugs or None,
            min_popularity=self.options.min_popularity,
            excluded_ids=self._seen_puzzle_ids,
        )

    def ensure_ready(self):
        if self.repository is None or self.db_path is None:
            raise FileNotFoundError("Tactics database not found.")

        if self.options.puzzle_id.strip():
            if self.repository.get(self.options.puzzle_id.strip()) is None:
                raise LookupError(
                    f"Puzzle not found: {self.options.puzzle_id.strip()}"
                )
            return

        preview = self.repository.random_puzzle(
            min_rating=self.options.min_rating,
            max_rating=self.options.max_rating,
            theme=parse_theme_filter(self.options.theme) or None,
            min_popularity=self.options.min_popularity,
        )
        if preview is None:
            raise LookupError("No puzzles found for the selected filters.")

    def describe_filters(self) -> str:
        if self.options.puzzle_id.strip():
            return f"Puzzle ID {self.options.puzzle_id.strip()}"

        parts = []
        if self.options.trainer_preset:
            preset = get_trainer_preset(self.options.trainer_preset)
            parts.append(f"Training plan: {preset.label}")
        if self.options.challenge_level:
            challenge = get_challenge_level(self.options.challenge_level)
            parts.append(f"Challenge: {challenge.label}")
        if self.options.theme.strip():
            parts.append(
                "Themes: "
                + (
                    describe_theme_filter(self.options.theme, db_path=self.db_path)
                    or self.options.theme.strip()
                )
            )
        if self.options.min_rating is not None or self.options.max_rating is not None:
            min_rating = "any" if self.options.min_rating is None else str(self.options.min_rating)
            max_rating = "any" if self.options.max_rating is None else str(self.options.max_rating)
            parts.append(f"Rating: {min_rating} to {max_rating}")
        if self.options.min_popularity:
            parts.append(f"Minimum popularity: {self.options.min_popularity}")
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
    ) -> None:
        if self.repository is None:
            return
        self.repository.record_attempt(
            puzzle_id=puzzle_id,
            solved=solved,
            mistakes=mistakes,
            hints_used=hints_used,
            elapsed_ms=elapsed_ms,
        )

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
                db_path=db_path or default_options.db_path,
                puzzle_id="",
                theme=default_options.theme,
                trainer_preset=default_options.trainer_preset,
                challenge_level=default_options.challenge_level,
                min_rating=default_options.min_rating,
                max_rating=default_options.max_rating,
                min_popularity=default_options.min_popularity,
            )
        )
