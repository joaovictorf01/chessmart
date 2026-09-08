from __future__ import annotations

from collections import Counter
import json
import random
import re
import sqlite3
import sys
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  puzzle_id TEXT NOT NULL,
  solved INTEGER NOT NULL,
  mistakes INTEGER NOT NULL,
  hints_used INTEGER NOT NULL,
  elapsed_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (puzzle_id) REFERENCES puzzles(id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_puzzle_id ON attempts(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON attempts(created_at);
"""

THEME_SPLIT_PATTERN = re.compile(r"[\s,;]+")


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def _build_puzzle_filters(
    min_rating: int | None,
    max_rating: int | None,
    theme_filter: str | None,
    min_popularity: int | None,
    excluded_ids: list[str] | tuple[str, ...] | None = None,
) -> tuple[str, list[object]]:
    clauses = ["1 = 1"]
    params: list[object] = []
    if min_rating is not None:
        clauses.append("rating >= ?")
        params.append(min_rating)
    if max_rating is not None:
        clauses.append("rating <= ?")
        params.append(max_rating)
    if min_popularity is not None:
        clauses.append("popularity >= ?")
        params.append(min_popularity)
    theme_slugs = [
        token.strip()
        for token in THEME_SPLIT_PATTERN.split((theme_filter or "").strip())
        if token.strip()
    ]
    if theme_slugs:
        clauses.append(
            "("
            + " OR ".join("(' ' || themes || ' ') LIKE ?" for _ in theme_slugs)
            + ")"
        )
        params.extend(f"% {theme_slug} %" for theme_slug in theme_slugs)
    if excluded_ids:
        placeholders = ", ".join("?" for _ in excluded_ids)
        clauses.append(f"id NOT IN ({placeholders})")
        params.extend(excluded_ids)
    return " AND ".join(clauses), params


def _row_to_dict(row: sqlite3.Row | None):
    if row is None:
        return None
    return {
        "id": row["id"],
        "fen": row["fen"],
        "moves": row["moves"].split(),
        "rating": row["rating"],
        "rating_deviation": row["rating_deviation"],
        "popularity": row["popularity"],
        "nb_plays": row["nb_plays"],
        "themes": row["themes"].split(),
        "game_url": row["game_url"],
        "opening_tags": row["opening_tags"],
    }


def cmd_count(connection: sqlite3.Connection):
    return connection.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]


def cmd_get(connection: sqlite3.Connection, puzzle_id: str):
    row = connection.execute(
        "SELECT * FROM puzzles WHERE id = ?",
        (puzzle_id,),
    ).fetchone()
    return _row_to_dict(row)


def cmd_random(
    connection: sqlite3.Connection,
    min_rating: str,
    max_rating: str,
    theme_filter: str,
    min_popularity: str,
    excluded_ids_json: str = "[]",
):
    excluded_ids = json.loads(excluded_ids_json) if excluded_ids_json else []
    where, params = _build_puzzle_filters(
        int(min_rating) if min_rating else None,
        int(max_rating) if max_rating else None,
        theme_filter or None,
        int(min_popularity) if min_popularity else None,
        excluded_ids,
    )
    total = connection.execute(
        f"SELECT COUNT(*) FROM puzzles WHERE {where}",
        params,
    ).fetchone()[0]
    if total == 0:
        return None
    offset = random.randrange(total)
    row = connection.execute(
        f"SELECT * FROM puzzles WHERE {where} LIMIT 1 OFFSET ?",
        [*params, offset],
    ).fetchone()
    return _row_to_dict(row)


def cmd_record_attempt(
    connection: sqlite3.Connection,
    puzzle_id: str,
    solved: str,
    mistakes: str,
    hints_used: str,
    elapsed_ms: str,
):
    connection.execute(
        """
        INSERT INTO attempts (puzzle_id, solved, mistakes, hints_used, elapsed_ms)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            puzzle_id,
            int(solved),
            int(mistakes),
            int(hints_used),
            int(elapsed_ms),
        ),
    )
    connection.commit()
    return {"ok": True}


def cmd_attempt_stats(connection: sqlite3.Connection):
    row = connection.execute(
        """
        SELECT
          COUNT(*) AS total,
          COALESCE(SUM(solved), 0) AS solved,
          COALESCE(SUM(mistakes), 0) AS mistakes,
          COALESCE(SUM(hints_used), 0) AS hints_used
        FROM attempts
        """
    ).fetchone()
    return {
        "total": row["total"],
        "solved": row["solved"],
        "mistakes": row["mistakes"],
        "hints_used": row["hints_used"],
    }


def cmd_theme_catalog(connection: sqlite3.Connection):
    counts: Counter[str] = Counter()
    cursor = connection.execute("SELECT themes FROM puzzles")
    for (themes,) in cursor:
        for slug in (themes or "").split():
            counts[slug] += 1
    return [
        {"slug": slug, "count": count}
        for slug, count in sorted(counts.items(), key=lambda item: item[0].casefold())
    ]


COMMANDS = {
    "count": cmd_count,
    "get": cmd_get,
    "random": cmd_random,
    "recordAttempt": cmd_record_attempt,
    "attemptStats": cmd_attempt_stats,
    "themeCatalog": cmd_theme_catalog,
}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        raise SystemExit("usage: sqlite_bridge.py <db_path> <command> [args...]")
    db_path = Path(argv[1])
    command = argv[2]
    args = argv[3:]
    handler = COMMANDS.get(command)
    if handler is None:
        raise SystemExit(f"unknown command: {command}")
    with connect(db_path) as connection:
        result = handler(connection, *args)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
