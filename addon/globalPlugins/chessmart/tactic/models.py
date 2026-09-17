# coding: utf-8

from __future__ import annotations

from dataclasses import dataclass


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

	@property
	def themes_text(self) -> str:
		return " ".join(self.themes)
