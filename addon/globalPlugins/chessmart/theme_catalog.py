# coding: utf-8

from __future__ import annotations

import dataclasses
import json
import re
import threading
from pathlib import Path

from .tactic.db import ADDON_DATA_DIRECTORY, resolve_default_db_path, run_bridge


THEME_FILTER_SPLIT_PATTERN = re.compile(r"[\s,;]+")
CAMEL_CASE_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")
THEME_CATALOG_CACHE_PATH = ADDON_DATA_DIRECTORY / "theme_catalog_cache.json"


@dataclasses.dataclass(frozen=True)
class ThemeCatalogEntry:
    slug: str
    label: str
    description: str
    count: int


def parse_theme_filter(value: str) -> tuple[str, ...]:
    tokens = [
        token.strip()
        for token in THEME_FILTER_SPLIT_PATTERN.split((value or "").strip())
        if token.strip()
    ]
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return tuple(seen)


def format_theme_filter(theme_slugs) -> str:
    return ", ".join(parse_theme_filter(" ".join(theme_slugs)))


def humanize_theme_slug(slug: str) -> str:
    humanized = CAMEL_CASE_PATTERN.sub(" ", slug).replace("_", " ").strip()
    return humanized[:1].upper() + humanized[1:] if humanized else slug


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
    items = run_bridge(resolved_db_path, "themeCatalog") or []
    payload = {
        **_build_signature(resolved_db_path),
        "themes": items,
    }
    THEME_CATALOG_CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _payload_to_entries(payload)


def _payload_to_entries(payload: dict[str, object]) -> tuple[ThemeCatalogEntry, ...]:
    raw_items = payload.get("themes") or []
    entries = []
    for item in raw_items:
        slug = str(item.get("slug", "")).strip()
        if not slug:
            continue
        count = int(item.get("count", 0) or 0)
        label = humanize_theme_slug(slug)
        entries.append(
            ThemeCatalogEntry(
                slug=slug,
                label=label,
                description=f"Lichess theme: {label}. {count} puzzles in this database.",
                count=count,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.label.casefold()))


def load_theme_catalog(
    db_path: str | Path | None = None, allow_rebuild: bool = True
) -> tuple[ThemeCatalogEntry, ...]:
    """O catálogo de temas do banco, do cache.

    Sem cache, `allow_rebuild=True` varre o banco aqui mesmo -- e isso leva
    dezenas de segundos na base completa, com quem chamou parado. Só o
    download faz isso de propósito, na própria thread. Todo o resto passa
    `allow_rebuild=False` e, se não houver cache, dispara a varredura em
    segundo plano com `ensure_theme_catalog_async` e segue sem o catálogo.
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
    """Garante que o catálogo existe, sem parar quem chamou.

    Devolve True se o cache já está pronto. Se não está, começa UMA varredura
    em thread (chamadas repetidas enquanto ela corre não começam outra) e
    devolve False; `on_done(entries)` é chamado na thread quando terminar.
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

    threading.Thread(target=work, name="chessmart.theme-catalog", daemon=True).start()
    return False


def get_theme_entry(
    slug: str,
    db_path: str | Path | None = None,
) -> ThemeCatalogEntry | None:
    if not slug:
        return None
    # Chamado ao carregar cada puzzle: nunca pode varrer o banco aqui. Sem
    # cache, o tema sai do slug (`humanize_theme_slug`) e o catálogo se
    # constrói em segundo plano para as próximas vezes.
    for entry in load_theme_catalog(db_path, allow_rebuild=False):
        if entry.slug == slug:
            return entry
    return None


def describe_theme_filter(
    theme_text: str,
    db_path: str | Path | None = None,
) -> str:
    slugs = parse_theme_filter(theme_text)
    if not slugs:
        return ""
    labels = []
    for slug in slugs:
        entry = get_theme_entry(slug, db_path=db_path)
        labels.append(entry.label if entry else humanize_theme_slug(slug))
    return ", ".join(labels)
