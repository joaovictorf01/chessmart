# coding: utf-8
# pyright: basic

"""Access to the puzzle database and the player's history, in SQLite.

One connection, two files: the history (`tactic.db`) is the main database
and the puzzles one (`puzzles.db`) is attached read-only as `lichess`. Every
function takes the connection opened by `connect` and returns the
dataclasses from `models.py`; none of them speak in plain text or dictionaries.

This module used to be a separate process, invoked from the command line,
and so it took everything as strings and returned JSON. The process is gone; so is the text interface.
"""

from __future__ import annotations

import datetime
import random
import sqlite3
from collections import Counter
from pathlib import Path

from . import glicko2
from .models import AttemptResult, AttemptStats, Puzzle, PuzzleFilters, RatingSummary


SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  puzzle_id TEXT NOT NULL,
  solved INTEGER NOT NULL,
  mistakes INTEGER NOT NULL,
  hints_used INTEGER NOT NULL,
  elapsed_ms INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attempts_puzzle_id ON attempts(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON attempts(created_at);

-- A single row: the player's current rating. The CHECK guarantees this.
CREATE TABLE IF NOT EXISTS player_rating (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  rating REAL NOT NULL,
  deviation REAL NOT NULL,
  volatility REAL NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row per update, to draw the evolution over time.
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

# Columns added to `attempts` after it already existed in real databases.
# SQLite has no "ADD COLUMN IF NOT EXISTS", so the migration is done by hand.
# Storing the puzzle's rating at the time of the attempt is what makes the
# history reproducible: if the Lichess database is updated, that puzzle may
# be worth something else, and without this the past would change along with it.
ATTEMPT_COLUMNS = (
	("puzzle_rating", "REAL"),
	("puzzle_deviation", "REAL"),
	("rating_before", "REAL"),
	("rating_after", "REAL"),
)

HISTORY_TABLES = ("attempts", "player_rating", "rating_history")


# ---------------------------------------------------------------- connection


def file_uri(db_path: Path, mode: str) -> str:
	"""File URI for SQLite, with the open mode.

	Absolute path with forward slashes and the `file:///` prefix, which is
	the form SQLite documents for Windows. `?` and `#` are meaningful in a
	URI; rare in a path, but not impossible.
	"""
	escaped = Path(db_path).resolve().as_posix().replace("%", "%25").replace("?", "%3F").replace("#", "%23")
	return f"file:///{escaped.lstrip('/')}?mode={mode}"


def read_only_uri(db_path: Path) -> str:
	return file_uri(db_path, "ro")


def _migrate_attempts(connection: sqlite3.Connection) -> None:
	"""Add to `attempts` whichever rating columns are missing.

	Runs on every connection and is cheap: one query to SQLite's catalog and,
	the vast majority of the time, no ALTER at all. Databases created before
	rating existed keep working, gaining the columns on first open.
	"""
	existing = {row[1] for row in connection.execute("PRAGMA table_info(attempts)")}
	for column, column_type in ATTEMPT_COLUMNS:
		if column not in existing:
			connection.execute(f"ALTER TABLE attempts ADD COLUMN {column} {column_type}")


def has_puzzles_table(db_path: Path) -> bool:
	"""Say whether the file has the Lichess `puzzles` table, i.e. whether it is a puzzle database."""
	try:
		connection = sqlite3.connect(read_only_uri(db_path), uri=True)
	except sqlite3.Error:
		return False
	try:
		row = connection.execute(
			"SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'puzzles'",
		).fetchone()
		return row is not None
	except sqlite3.Error:
		return False
	finally:
		connection.close()


def connect(puzzles_path: Path, history_path: Path) -> sqlite3.Connection:
	"""Open the player's history and attach the puzzle database as `lichess`.

	Two files on purpose: the puzzles one comes from Lichess and is replaced
	wholesale on every update; the history belongs to the player and must
	never be touched by an update. The puzzles one is attached read-only --
	nothing here writes to it, and that is guaranteed by SQLite, not by discipline.
	"""
	history_path.parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(file_uri(history_path, "rwc"), uri=True)
	connection.row_factory = sqlite3.Row
	connection.executescript(SCHEMA)
	_migrate_attempts(connection)
	try:
		connection.execute("ATTACH DATABASE ? AS lichess", (read_only_uri(puzzles_path),))
		connection.execute("SELECT 1 FROM lichess.puzzles LIMIT 1")
	except sqlite3.Error as error:
		connection.close()
		raise RuntimeError(f"not a puzzle database: {puzzles_path} ({error})") from error
	return connection


# ---------------------------------------------------------------- format migration


def split_legacy_database(legacy_path: Path, puzzles_path: Path, history_path: Path) -> Path:
	"""Split an old `tactic.db` that combined puzzles and history in a single file.

	In the order that leaves the worst case recoverable:
	1. the history is copied to a new file and to a dated backup;
	2. the history tables are dropped from the old file;
	3. the old file is renamed to `puzzles.db` and the new one to `tactic.db`.
	If step 3 fails partway through, the old file (puzzles only) and the new
	one (history only) sit side by side with provisional names, and nothing is lost.
	Returns the backup path.
	"""
	if puzzles_path.exists():
		raise FileExistsError(f"refusing to overwrite {puzzles_path}")
	fresh_path = history_path.with_name(history_path.name + ".new")
	backup_path = _backup_path(history_path)
	for target in (fresh_path, backup_path):
		if target.exists():
			target.unlink()
		_copy_history_tables(legacy_path, target)
	legacy = sqlite3.connect(legacy_path)
	try:
		with legacy:
			for table in HISTORY_TABLES:
				legacy.execute(f"DROP TABLE IF EXISTS {table}")
			placeholders = ", ".join("?" for _ in HISTORY_TABLES)
			legacy.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", HISTORY_TABLES)
	finally:
		legacy.close()
	legacy_path.rename(puzzles_path)
	fresh_path.rename(history_path)
	return backup_path


def slim_legacy_history(history_path: Path) -> Path:
	"""Strip the `puzzles` table from a history that still carries it.

	The case of someone who downloaded a puzzle database before the split
	ran: the old `tactic.db` was left as the history, with the millions of
	puzzles inside it. The history is copied to a new file (and a dated
	backup), and the new one replaces the old -- faster and safer than
	dropping the table and vacuuming 1.4 GB in place.
	"""
	fresh_path = history_path.with_name(history_path.name + ".new")
	backup_path = _backup_path(history_path)
	for target in (fresh_path, backup_path):
		if target.exists():
			target.unlink()
		_copy_history_tables(history_path, target)
	old_path = history_path.with_name(history_path.name + ".old")
	if old_path.exists():
		old_path.unlink()
	history_path.replace(old_path)
	fresh_path.replace(history_path)
	old_path.unlink()
	return backup_path


def _backup_path(history_path: Path) -> Path:
	stamp = datetime.date.today().strftime("%Y%m%d")
	return history_path.with_name(f"{history_path.stem}.backup-{stamp}{history_path.suffix}")


def _copy_history_tables(legacy_path: Path, target_path: Path) -> None:
	connection = sqlite3.connect(file_uri(target_path, "rwc"), uri=True)
	try:
		connection.executescript(SCHEMA)
		_migrate_attempts(connection)
		connection.execute("ATTACH DATABASE ? AS old", (read_only_uri(legacy_path),))
		for table in HISTORY_TABLES:
			exists = connection.execute(
				"SELECT 1 FROM old.sqlite_master WHERE type = 'table' AND name = ?",
				(table,),
			).fetchone()
			if exists is None:
				continue
			# Only the columns both sides know about: the old database may predate
			# a column's existence, while the new one is born with all of them.
			old_columns = [row[1] for row in connection.execute(f"PRAGMA old.table_info({table})")]
			new_columns = [row[1] for row in connection.execute(f"PRAGMA main.table_info({table})")]
			columns = ", ".join(column for column in old_columns if column in new_columns)
			connection.execute(f"INSERT INTO main.{table} ({columns}) SELECT {columns} FROM old.{table}")
		connection.commit()
		connection.execute("DETACH DATABASE old")
	finally:
		connection.close()


# ---------------------------------------------------------------- player rating


def _load_rating(connection: sqlite3.Connection) -> glicko2.Rating:
	"""The current rating, or the initial one if none has been recorded yet."""
	row = connection.execute(
		"SELECT rating, deviation, volatility FROM player_rating WHERE id = 1",
	).fetchone()
	if row is None:
		return glicko2.Rating()
	return glicko2.Rating(row["rating"], row["deviation"], row["volatility"])


def _store_rating(
	connection: sqlite3.Connection,
	rating: glicko2.Rating,
	attempt_id: int | None = None,
) -> None:
	"""Store the current rating and append a row to the history."""
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


# ---------------------------------------------------------------- puzzles


def _puzzle_from_row(row: sqlite3.Row | None) -> Puzzle | None:
	if row is None:
		return None
	return Puzzle(
		id=row["id"],
		fen=row["fen"],
		moves=row["moves"].split(),
		rating=row["rating"],
		rating_deviation=row["rating_deviation"],
		popularity=row["popularity"],
		nb_plays=row["nb_plays"],
		themes=row["themes"].split(),
		game_url=row["game_url"],
		opening_tags=row["opening_tags"],
	)


def _where_clause(filters: PuzzleFilters) -> tuple[str, list[object]]:
	clauses = ["1 = 1"]
	params: list[object] = []
	if filters.min_rating is not None:
		clauses.append("rating >= ?")
		params.append(filters.min_rating)
	if filters.max_rating is not None:
		clauses.append("rating <= ?")
		params.append(filters.max_rating)
	if filters.min_popularity is not None:
		clauses.append("popularity >= ?")
		params.append(filters.min_popularity)
	if filters.theme_slugs:
		clauses.append("(" + " OR ".join("(' ' || themes || ' ') LIKE ?" for _ in filters.theme_slugs) + ")")
		params.extend(f"% {slug} %" for slug in filters.theme_slugs)
	if filters.excluded_ids:
		placeholders = ", ".join("?" for _ in filters.excluded_ids)
		clauses.append(f"id NOT IN ({placeholders})")
		params.extend(filters.excluded_ids)
	return " AND ".join(clauses), params


def count(connection: sqlite3.Connection) -> int:
	return int(connection.execute("SELECT COUNT(*) FROM lichess.puzzles").fetchone()[0])


def get(connection: sqlite3.Connection, puzzle_id: str) -> Puzzle | None:
	row = connection.execute("SELECT * FROM lichess.puzzles WHERE id = ?", (puzzle_id,)).fetchone()
	return _puzzle_from_row(row)


def _random_row(connection: sqlite3.Connection, filters: PuzzleFilters) -> sqlite3.Row | None:
	"""Pick a random row without counting the whole set.

	The usual COUNT(*) followed by LIMIT 1 OFFSET n pattern is expensive on a
	large table: COUNT scans everything and OFFSET scans again up to the nth
	row. With a theme filter it's worse still, because LIKE cannot use an
	index -- measured on this database, it took over 10 seconds per draw, with NVDA silent the whole time.

	The idea here is different: pick a random `rowid` and take the FIRST row
	that matches from there onward; if none matches to the end, look before
	the chosen point. The two queries together cover the table exactly once,
	so the worst case (a filter matching nothing) is one scan, not two -- and
	the common case finishes within a few dozen rows.

	Honest caveat: this is not uniform. A row right after a long run of
	non-matching rows has a higher chance of being picked. The bias is small,
	and the price of uniformity was a ten-second wait.
	"""
	bounds = connection.execute("SELECT MIN(rowid), MAX(rowid) FROM lichess.puzzles").fetchone()
	if bounds is None or bounds[0] is None:
		return None
	anchor = random.randint(bounds[0], bounds[1])
	where, params = _where_clause(filters)
	# NOT INDEXED is required here, and it is not a micro-optimization.
	# Without it SQLite prefers the rating index and scans in rating order, so
	# "the first one that matches" always becomes the lowest rating in the
	# range -- measured: 20 draws in a row returned exactly the floor of the
	# window. NOT INDEXED forces a scan in the table's physical order, which
	# is what makes the random anchor meaningful. rowid remains usable,
	# because it is the table's own key, not a secondary index.
	row = connection.execute(
		f"SELECT * FROM lichess.puzzles NOT INDEXED WHERE rowid >= ? AND {where} LIMIT 1",
		[anchor, *params],
	).fetchone()
	if row is not None:
		return row
	return connection.execute(
		f"SELECT * FROM lichess.puzzles NOT INDEXED WHERE rowid < ? AND {where} LIMIT 1",
		[anchor, *params],
	).fetchone()


def random_puzzle(connection: sqlite3.Connection, filters: PuzzleFilters) -> Puzzle | None:
	return _puzzle_from_row(_random_row(connection, filters))


def adaptive_random_puzzle(connection: sqlite3.Connection, filters: PuzzleFilters) -> Puzzle | None:
	"""Draw a puzzle calibrated to the player's current rating.

	The rating range in `filters` is ignored: the window is centered a bit
	ABOVE the rating -- a puzzle slightly beyond the player's level teaches
	more than one solved on autopilot -- and its width tracks the DEVIATION:
	while the system doesn't know the player yet, it draws wide (which is
	also the fastest way to learn); as confidence grows, the window closes in.

	If the window comes back empty -- possible with a narrow theme filter --
	it is widened in steps, and as a last resort the rating is ignored
	altogether: a puzzle outside the ideal range beats no puzzle at all.
	"""
	player = _load_rating(connection)
	# 2.5 deviations cover the range where the player plausibly stands. The
	# bounds prevent both bad extremes: a window too narrow to find a puzzle,
	# and one so wide it stops being calibrated.
	spread = max(120.0, min(2.5 * player.deviation, 700.0))
	center = player.rating + 50.0
	for multiplier in (1.0, 2.0, 4.0):
		window = PuzzleFilters(
			min_rating=int(center - spread * multiplier),
			max_rating=int(center + spread * multiplier),
			theme_slugs=filters.theme_slugs,
			min_popularity=filters.min_popularity,
			excluded_ids=filters.excluded_ids,
		)
		puzzle = random_puzzle(connection, window)
		if puzzle is not None:
			return puzzle
	# Nothing nearby: fall back to drawing with no rating restriction.
	return random_puzzle(
		connection,
		PuzzleFilters(
			theme_slugs=filters.theme_slugs,
			min_popularity=filters.min_popularity,
			excluded_ids=filters.excluded_ids,
		),
	)


# ---------------------------------------------------------------- history


def record_attempt(
	connection: sqlite3.Connection,
	puzzle_id: str,
	solved: bool,
	mistakes: int,
	hints_used: int,
	elapsed_ms: int,
) -> AttemptResult:
	"""Record the attempt, update the player's rating, and return what changed."""
	cursor = connection.execute(
		"""
        INSERT INTO attempts (puzzle_id, solved, mistakes, hints_used, elapsed_ms)
        VALUES (?, ?, ?, ?, ?)
        """,
		(puzzle_id, int(solved), int(mistakes), int(hints_used), int(elapsed_ms)),
	)
	attempt_id = int(cursor.lastrowid or 0)

	puzzle = connection.execute(
		"SELECT rating, rating_deviation FROM lichess.puzzles WHERE id = ?",
		(puzzle_id,),
	).fetchone()

	before = _load_rating(connection)
	after = before
	if puzzle is not None:
		# The attempt becomes a game against this puzzle. Only the player
		# changes: the puzzle's rating comes from Lichess, computed over
		# millions of attempts, and is not ours to touch.
		after = glicko2.update(before, float(puzzle["rating"]), float(puzzle["rating_deviation"]), solved)
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
	return AttemptResult(
		attempt_id=attempt_id,
		rating_before=before.rounded(),
		rating=after.rounded(),
		deviation=round(after.deviation, 1),
	)


def rating(connection: sqlite3.Connection) -> RatingSummary:
	player = _load_rating(connection)
	low, high = player.confidence_interval()
	rated = connection.execute("SELECT COUNT(*) FROM attempts WHERE rating_after IS NOT NULL").fetchone()[0]
	return RatingSummary(
		rating=player.rounded(),
		deviation=round(player.deviation, 1),
		volatility=round(player.volatility, 5),
		interval_low=low,
		interval_high=high,
		rated_attempts=int(rated),
	)


def attempt_stats(connection: sqlite3.Connection) -> AttemptStats:
	row = connection.execute(
		"""
        SELECT
          COUNT(*) AS total,
          COALESCE(SUM(solved), 0) AS solved,
          COALESCE(SUM(mistakes), 0) AS mistakes,
          COALESCE(SUM(hints_used), 0) AS hints_used
        FROM attempts
        """,
	).fetchone()
	return AttemptStats(
		total=int(row["total"]),
		solved=int(row["solved"]),
		mistakes=int(row["mistakes"]),
		hints_used=int(row["hints_used"]),
	)


def theme_counts(connection: sqlite3.Connection) -> list[tuple[str, int]]:
	"""Each theme in the database with how many puzzles have it. Scans the whole table."""
	counts: Counter[str] = Counter()
	for (themes,) in connection.execute("SELECT themes FROM lichess.puzzles"):
		for slug in (themes or "").split():
			counts[slug] += 1
	return sorted(counts.items(), key=lambda item: item[0].casefold())
