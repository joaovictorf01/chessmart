# coding: utf-8
# pyright: basic

"""O registro dos treinos de final, no mesmo `tactic.db` do histórico de táticas.

Uma linha por tentativa: qual posição, se a pergunta foi acertada, se o
resultado teórico foi mantido até o fim, em quantos lances, em quanto tempo,
e como terminou. É o que responde "quantas vezes seguidas" por posição e o
que a revisão da semana lê. Nada aqui toca o banco de puzzles.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from ..tactic.db import HISTORY_DB_PATH, load_store

SCHEMA = """
CREATE TABLE IF NOT EXISTS endgame_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lesson_id TEXT NOT NULL,
  position_id TEXT NOT NULL,
  answer_correct INTEGER,
  kept_result INTEGER NOT NULL,
  moves INTEGER NOT NULL,
  elapsed_ms INTEGER NOT NULL,
  outcome TEXT NOT NULL,
  line TEXT NOT NULL DEFAULT '',
  fen TEXT NOT NULL DEFAULT '',
  hints INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_endgame_attempts_position ON endgame_attempts(position_id, id);
"""


@dataclasses.dataclass(frozen=True)
class PositionStats:
	attempts: int
	streak: int  # tentativas seguidas, da mais recente para trás, com pergunta certa e resultado mantido
	best_moves: int | None  # menor número de lances numa tentativa que manteve o resultado


def open_log(history_path: Path = HISTORY_DB_PATH):
	"""Abre (e cria, se preciso) a tabela no histórico do jogador."""
	store = load_store()
	import sqlite3

	Path(history_path).parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(store.file_uri(Path(history_path), "rwc"), uri=True)
	connection.row_factory = sqlite3.Row
	connection.executescript(SCHEMA)
	_migrate(connection)
	return connection


def _migrate(connection) -> None:
	"""A coluna `line` (os lances, em UCI) veio depois da tabela; bancos antigos ganham ela aqui."""
	existing = {row[1] for row in connection.execute("PRAGMA table_info(endgame_attempts)")}
	if "line" not in existing:
		connection.execute("ALTER TABLE endgame_attempts ADD COLUMN line TEXT NOT NULL DEFAULT ''")
	if "fen" not in existing:
		connection.execute("ALTER TABLE endgame_attempts ADD COLUMN fen TEXT NOT NULL DEFAULT ''")
	if "hints" not in existing:
		connection.execute("ALTER TABLE endgame_attempts ADD COLUMN hints INTEGER NOT NULL DEFAULT 0")


def record(
	connection,
	lesson_id: str,
	position_id: str,
	*,
	answer_correct: bool | None,
	kept_result: bool,
	moves: int,
	elapsed_ms: int,
	outcome: str,
	line: str = "",
	fen: str = "",
	hints: int = 0,
) -> int:
	"""`fen` é a posição de partida e `line` os lances em UCI: juntos permitem rever a tentativa.

	`hints` conta as vezes que a tablebase foi consultada pelo melhor lance:
	a tentativa vale como treino, mas com ajuda não entra na sequência.
	"""
	cursor = connection.execute(
		"INSERT INTO endgame_attempts (lesson_id, position_id, answer_correct, kept_result, moves, elapsed_ms,"
		" outcome, line, fen, hints) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		(
			lesson_id,
			position_id,
			None if answer_correct is None else int(answer_correct),
			int(kept_result),
			int(moves),
			int(elapsed_ms),
			outcome,
			line,
			fen,
			int(hints),
		),
	)
	connection.commit()
	return int(cursor.lastrowid or 0)


def position_stats(connection, position_id: str) -> PositionStats:
	rows = connection.execute(
		"SELECT answer_correct, kept_result, moves, hints FROM endgame_attempts WHERE position_id = ?"
		" ORDER BY id DESC",
		(position_id,),
	).fetchall()
	streak = 0
	for row in rows:
		success = bool(row["kept_result"]) and row["answer_correct"] != 0 and int(row["hints"]) == 0
		if not success:
			break
		streak += 1
	kept = [int(row["moves"]) for row in rows if row["kept_result"]]
	return PositionStats(attempts=len(rows), streak=streak, best_moves=min(kept) if kept else None)


def lesson_stats(connection, lesson_id: str) -> dict[str, PositionStats]:
	position_ids = [
		row["position_id"]
		for row in connection.execute(
			"SELECT DISTINCT position_id FROM endgame_attempts WHERE lesson_id = ?",
			(lesson_id,),
		)
	]
	return {position_id: position_stats(connection, position_id) for position_id in position_ids}
