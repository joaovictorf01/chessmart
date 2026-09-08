from __future__ import annotations

from collections import Counter
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

# Este arquivo é executado como script solto pelo run_bridge, e nesse caso o
# import relativo não existe. Importado como parte do pacote, o absoluto é que
# não vale. As duas formas cobrem os dois modos de uso.
try:
    from . import glicko2
except ImportError:
    import glicko2


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

-- Uma linha só: o rating atual do jogador. O CHECK garante isso.
CREATE TABLE IF NOT EXISTS player_rating (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  rating REAL NOT NULL,
  deviation REAL NOT NULL,
  volatility REAL NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Uma linha por atualização, para desenhar a evolução ao longo do tempo.
CREATE TABLE IF NOT EXISTS rating_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id INTEGER,
  rating REAL NOT NULL,
  deviation REAL NOT NULL,
  volatility REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (attempt_id) REFERENCES attempts(id)
);

CREATE INDEX IF NOT EXISTS idx_rating_history_created_at ON rating_history(created_at);
"""

# Colunas acrescentadas a `attempts` depois que ela já existia em bancos reais.
# O SQLite não tem "ADD COLUMN IF NOT EXISTS", então a migração é feita à mão.
# Guardar o rating do puzzle no momento da tentativa é o que torna o histórico
# reproduzível: se o banco do Lichess for atualizado, aquele puzzle pode valer
# outra coisa, e sem isto o passado mudaria junto.
ATTEMPT_COLUMNS = (
    ("puzzle_rating", "REAL"),
    ("puzzle_deviation", "REAL"),
    ("rating_before", "REAL"),
    ("rating_after", "REAL"),
)

THEME_SPLIT_PATTERN = re.compile(r"[\s,;]+")


def _migrate_attempts(connection: sqlite3.Connection) -> None:
    """Acrescenta a `attempts` as colunas de rating que faltarem.

    Roda a cada conexão e é barata: uma consulta ao catálogo do SQLite e, na
    imensa maioria das vezes, nenhum ALTER. Bancos criados antes do rating
    existir continuam funcionando, ganhando as colunas na primeira abertura.
    """
    existing = {row[1] for row in connection.execute("PRAGMA table_info(attempts)")}
    for column, column_type in ATTEMPT_COLUMNS:
        if column not in existing:
            connection.execute(f"ALTER TABLE attempts ADD COLUMN {column} {column_type}")


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    _migrate_attempts(connection)
    return connection


def _load_rating(connection: sqlite3.Connection) -> glicko2.Rating:
    """O rating atual, ou o inicial se ainda não houver nenhum registrado."""
    row = connection.execute(
        "SELECT rating, deviation, volatility FROM player_rating WHERE id = 1"
    ).fetchone()
    if row is None:
        return glicko2.Rating()
    return glicko2.Rating(row["rating"], row["deviation"], row["volatility"])


def _store_rating(
    connection: sqlite3.Connection,
    rating: glicko2.Rating,
    attempt_id: int | None = None,
) -> None:
    """Grava o rating atual e acrescenta uma linha ao histórico."""
    connection.execute(
        """
        INSERT INTO player_rating (id, rating, deviation, volatility, updated_at)
        VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          rating = excluded.rating,
          deviation = excluded.deviation,
          volatility = excluded.volatility,
          updated_at = excluded.updated_at
        """,
        (rating.rating, rating.deviation, rating.volatility),
    )
    connection.execute(
        """
        INSERT INTO rating_history (attempt_id, rating, deviation, volatility)
        VALUES (?, ?, ?, ?)
        """,
        (attempt_id, rating.rating, rating.deviation, rating.volatility),
    )


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
    solved_flag = int(solved)
    cursor = connection.execute(
        """
        INSERT INTO attempts (puzzle_id, solved, mistakes, hints_used, elapsed_ms)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            puzzle_id,
            solved_flag,
            int(mistakes),
            int(hints_used),
            int(elapsed_ms),
        ),
    )
    attempt_id = cursor.lastrowid

    puzzle = connection.execute(
        "SELECT rating, rating_deviation FROM puzzles WHERE id = ?", (puzzle_id,)
    ).fetchone()

    before = _load_rating(connection)
    after = before
    if puzzle is not None:
        # A tentativa vira uma partida contra este puzzle. Só o jogador muda:
        # o rating do puzzle vem do Lichess, calculado sobre milhões de
        # tentativas, e não é nosso para mexer.
        after = glicko2.update(
            before,
            float(puzzle["rating"]),
            float(puzzle["rating_deviation"]),
            bool(solved_flag),
        )
        connection.execute(
            """
            UPDATE attempts
               SET puzzle_rating = ?, puzzle_deviation = ?,
                   rating_before = ?, rating_after = ?
             WHERE id = ?
            """,
            (
                float(puzzle["rating"]),
                float(puzzle["rating_deviation"]),
                before.rating,
                after.rating,
                attempt_id,
            ),
        )
        _store_rating(connection, after, attempt_id)

    connection.commit()
    return {
        "ok": True,
        "attemptId": attempt_id,
        "ratingBefore": before.rounded(),
        "rating": after.rounded(),
        "ratingDelta": after.rounded() - before.rounded(),
        "deviation": round(after.deviation, 1),
    }


def cmd_rating(connection: sqlite3.Connection):
    """O rating atual, com a faixa de confiança e quantas tentativas o formaram."""
    rating = _load_rating(connection)
    low, high = rating.confidence_interval()
    attempts = connection.execute(
        "SELECT COUNT(*) FROM attempts WHERE rating_after IS NOT NULL"
    ).fetchone()[0]
    return {
        "rating": rating.rounded(),
        "deviation": round(rating.deviation, 1),
        "volatility": round(rating.volatility, 5),
        "intervalLow": low,
        "intervalHigh": high,
        "ratedAttempts": attempts,
        # Enquanto o desvio é grande o número ainda é chute: vale dizer isso a
        # quem lê, em vez de apresentar 1500 como se fosse medida.
        "provisional": rating.deviation > 110.0,
    }


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
    "rating": cmd_rating,
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
