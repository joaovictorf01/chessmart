# coding: utf-8
# pyright: basic

"""Theme filter and puzzle-database theme count catalog.

What a theme is (name, description) lives in `theme_names`. Two things live
here: the filter text ("fork, pin") and the catalog, i.e. the list of themes
the installed database actually has, with how many puzzles each one -- that
requires scanning the whole database, so it's done once and cached.
"""

from __future__ import annotations

import dataclasses
import json
import re
import threading
from pathlib import Path

from .tactic.db import ADDON_DATA_DIRECTORY, resolve_default_db_path
from .tactic.repository import PuzzleRepository
from .theme_names import theme_description, theme_label


THEME_FILTER_SPLIT_PATTERN = re.compile(r"[\s,;]+")
THEME_CATALOG_CACHE_PATH = ADDON_DATA_DIRECTORY / "theme_catalog_cache.json"


@dataclasses.dataclass(frozen=True)
class ThemeCatalogEntry:
	slug: str
	label: str
	description: str
	count: int


def parse_theme_filter(value: str) -> tuple[str, ...]:
	tokens = [
		token.strip() for token in THEME_FILTER_SPLIT_PATTERN.split((value or "").strip()) if token.strip()
	]
	seen: list[str] = []
	for token in tokens:
		if token not in seen:
			seen.append(token)
	return tuple(seen)


def format_theme_filter(theme_slugs) -> str:
	return ", ".join(parse_theme_filter(" ".join(theme_slugs)))


def describe_theme_filter(theme_text: str) -> str:
	"""The filter's themes by name, on one line: "Fork, Pin, Back rank mate"."""
	return ", ".join(theme_label(slug) for slug in parse_theme_filter(theme_text))


def resolve_theme_db_path(db_path: str | Path | None = None) -> Path | None:
	if db_path is None:
		return resolve_default_db_path()
	resolved = Path(db_path)
	return resolved if resolved.is_file() else None


def _build_signature(db_path: Path) -> dict[str, object]:
	stat = db_path.stat()
	return {
		"dbPath": str(db_path.resolve()),
		"dbSize": stat.st_size,
		"dbModifiedNs": stat.st_mtime_ns,
	}


def _cache_matches(payload: dict[str, object], db_path: Path) -> bool:
	signature = _build_signature(db_path)
	for key, value in signature.items():
		if payload.get(key) != value:
			return False
	return True


def _load_cache_payload(db_path: Path) -> dict[str, object] | None:
	if not THEME_CATALOG_CACHE_PATH.is_file():
		return None
	try:
		payload = json.loads(THEME_CATALOG_CACHE_PATH.read_text(encoding="utf-8"))
	except Exception:
		return None
	if not isinstance(payload, dict):
		return None
	if not _cache_matches(payload, db_path):
		return None
	return payload


def rebuild_theme_catalog(db_path: str | Path | None = None) -> tuple[ThemeCatalogEntry, ...]:
	resolved_db_path = resolve_theme_db_path(db_path)
	if resolved_db_path is None:
		return ()
	ADDON_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
	counts = PuzzleRepository(resolved_db_path).theme_counts()
	payload = {
		**_build_signature(resolved_db_path),
		"themes": [{"slug": slug, "count": count} for slug, count in counts],
	}
	THEME_CATALOG_CACHE_PATH.write_text(
		json.dumps(payload, ensure_ascii=False, indent=2),
		encoding="utf-8",
	)
	return _payload_to_entries(payload)


def _payload_to_entries(payload: dict[str, object]) -> tuple[ThemeCatalogEntry, ...]:
	raw_items = payload.get("themes") or []
	if not isinstance(raw_items, list):
		return ()
	entries = []
	for item in raw_items:
		if not isinstance(item, dict):
			continue
		slug = str(item.get("slug", "")).strip()
		if not slug:
			continue
		entries.append(
			ThemeCatalogEntry(
				slug=slug,
				label=theme_label(slug),
				description=theme_description(slug),
				count=int(item.get("count", 0) or 0),
			),
		)
	return tuple(sorted(entries, key=lambda entry: entry.label.casefold()))


def load_theme_catalog(
	db_path: str | Path | None = None,
	allow_rebuild: bool = True,
) -> tuple[ThemeCatalogEntry, ...]:
	"""The database's theme catalog, from cache.

	Without a cache, `allow_rebuild=True` scans the database right here -- and
	that takes tens of seconds on the full database, blocking the caller. Only
	the download does this on purpose, on its own thread. Everything else
	passes `allow_rebuild=False` and, if there is no cache, triggers the scan
	in the background with `ensure_theme_catalog_async` and proceeds without
	the catalog.
	"""
	resolved_db_path = resolve_theme_db_path(db_path)
	if resolved_db_path is None:
		return ()
	payload = _load_cache_payload(resolved_db_path)
	if payload is None:
		if not allow_rebuild:
			ensure_theme_catalog_async(resolved_db_path)
			return ()
		return rebuild_theme_catalog(resolved_db_path)
	return _payload_to_entries(payload)


_REBUILD_LOCK = threading.Lock()
_REBUILD_IN_PROGRESS: set[str] = set()


def ensure_theme_catalog_async(db_path: str | Path | None = None, on_done=None) -> bool:
	"""Ensures the catalog exists, without blocking the caller.

	Returns True if the cache is already ready. If not, starts ONE scan in a
	thread (repeated calls while it's running don't start another) and returns
	False; `on_done(entries)` is called on that thread when it finishes.
	"""
	resolved_db_path = resolve_theme_db_path(db_path)
	if resolved_db_path is None:
		return False
	if _load_cache_payload(resolved_db_path) is not None:
		return True
	key = str(resolved_db_path.resolve())
	with _REBUILD_LOCK:
		if key in _REBUILD_IN_PROGRESS:
			return False
		_REBUILD_IN_PROGRESS.add(key)

	def work():
		try:
			entries = rebuild_theme_catalog(resolved_db_path)
		except Exception:
			entries = ()
		finally:
			with _REBUILD_LOCK:
				_REBUILD_IN_PROGRESS.discard(key)
		if on_done is not None:
			on_done(entries)

	threading.Thread(target=work, name="chessStudy.theme-catalog", daemon=True).start()
	return False


__all__ = [
	"ThemeCatalogEntry",
	"describe_theme_filter",
	"ensure_theme_catalog_async",
	"format_theme_filter",
	"load_theme_catalog",
	"parse_theme_filter",
	"rebuild_theme_catalog",
	"resolve_theme_db_path",
]
