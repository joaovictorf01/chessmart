# coding: utf-8

"""Acesso ao banco de puzzles e ao histórico do jogador, em SQLite.

Uma conexão, dois arquivos: o histórico (`tactic.db`) é o banco principal e o
de puzzles (`puzzles.db`) vai anexado só para leitura como `lichess`. Todas as
funções recebem a conexão aberta por `connect` e devolvem os dataclasses de
`models.py`; nenhuma fala em texto ou dicionário.

Este módulo já foi um processo à parte, chamado por linha de comando, e por
isso recebia tudo como string e devolvia JSON. O processo acabou; a interface
em texto acabou junto.
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

HISTORY_TABLES = ("attempts", "player_rating", "rating_history")


# ---------------------------------------------------------------- conexão


def file_uri(db_path: Path, mode: str) -> str:
	"""URI de arquivo para o SQLite, com o modo de abertura.

	Caminho absoluto com barras normais e prefixo `file:///`, que é a forma
	que o SQLite documenta para Windows. `?` e `#` têm significado numa URI;
	num caminho são raros, mas não impossíveis.
	"""
	escaped = Path(db_path).resolve().as_posix().replace("%", "%25").replace("?", "%3F").replace("#", "%23")
	return f"file:///{escaped.lstrip('/')}?mode={mode}"


def read_only_uri(db_path: Path) -> str:
	return file_uri(db_path, "ro")


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


def has_puzzles_table(db_path: Path) -> bool:
	"""Diz se o arquivo tem a tabela `puzzles` do Lichess, isto é, se é um banco de puzzles."""
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
	"""Abre o histórico do jogador e anexa o banco de puzzles como `lichess`.

	São dois arquivos de propósito: o de puzzles vem do Lichess e é trocado
	inteiro a cada atualização; o histórico é do jogador e não pode ser tocado
	por atualização nenhuma. O de puzzles é anexado só para leitura -- nada
	aqui escreve nele, e assim fica garantido pelo SQLite, não por disciplina.
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


# ---------------------------------------------------------------- migração de formato


def split_legacy_database(legacy_path: Path, puzzles_path: Path, history_path: Path) -> Path:
	"""Divide um `tactic.db` antigo, que juntava puzzles e histórico num arquivo só.

	Na ordem que deixa o pior caso recuperável:
	1. o histórico é copiado para um arquivo novo e para um backup datado;
	2. as tabelas de histórico são apagadas do arquivo antigo;
	3. o antigo é renomeado para `puzzles.db` e o novo para `tactic.db`.
	Se o passo 3 falhar no meio, o antigo (só puzzles) e o novo (só histórico)
	ficam lado a lado com nomes provisórios, e nada se perdeu.
	Devolve o caminho do backup.
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
	"""Tira a tabela `puzzles` de um histórico que ainda a carrega.

	Caso de quem baixou um banco de puzzles antes de a divisão rodar: o
	`tactic.db` antigo ficou como histórico, com os milhões de puzzles
	dentro. O histórico é copiado para um arquivo novo (e um backup datado),
	e o novo toma o lugar do antigo -- mais rápido e mais seguro do que
	apagar a tabela e compactar 1,4 GB no lugar.
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
			# Só as colunas que os dois lados conhecem: o antigo pode ter nascido
			# antes de uma coluna existir, e o novo já nasce com todas.
			old_columns = [row[1] for row in connection.execute(f"PRAGMA old.table_info({table})")]
			new_columns = [row[1] for row in connection.execute(f"PRAGMA main.table_info({table})")]
			columns = ", ".join(column for column in old_columns if column in new_columns)
			connection.execute(f"INSERT INTO main.{table} ({columns}) SELECT {columns} FROM old.{table}")
		connection.commit()
		connection.execute("DETACH DATABASE old")
	finally:
		connection.close()


# ---------------------------------------------------------------- rating do jogador


def _load_rating(connection: sqlite3.Connection) -> glicko2.Rating:
	"""O rating atual, ou o inicial se ainda não houver nenhum registrado."""
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
	"""Sorteia uma linha sem contar o conjunto inteiro.

	O padrão COUNT(*) seguido de LIMIT 1 OFFSET n custa caro em tabela grande:
	o COUNT percorre tudo e o OFFSET percorre de novo até a enésima linha. Com
	filtro de tema é pior ainda, porque o LIKE não usa índice -- medido neste
	banco, dava mais de 10 segundos por sorteio, com o NVDA mudo enquanto isso.

	Aqui a ideia é outra: escolher um `rowid` ao acaso e pegar a PRIMEIRA linha
	que casa dali para frente; se não houver nenhuma até o fim, procurar antes
	do ponto escolhido. As duas consultas juntas cobrem a tabela exatamente uma
	vez, então o pior caso (filtro que não casa com nada) é uma varredura, não
	duas -- e o caso comum termina em algumas dezenas de linhas.

	Ressalva honesta: isto não é uniforme. Uma linha que vem logo depois de uma
	sequência longa de linhas que não casam tem chance maior de ser escolhida.
	O viés é pequeno e o preço da uniformidade eram dez segundos de espera.
	"""
	bounds = connection.execute("SELECT MIN(rowid), MAX(rowid) FROM lichess.puzzles").fetchone()
	if bounds is None or bounds[0] is None:
		return None
	anchor = random.randint(bounds[0], bounds[1])
	where, params = _where_clause(filters)
	# NOT INDEXED é obrigatório aqui, e não é micro-otimização. Sem ele o
	# SQLite prefere o índice de rating e percorre em ordem de rating, então
	# "a primeira que casa" passa a ser sempre a de menor rating da faixa --
	# medido: 20 sorteios seguidos devolveram exatamente o piso da janela.
	# NOT INDEXED força a varredura pela ordem física da tabela, que é o que
	# dá sentido à âncora sorteada. O rowid continua utilizável, porque é a
	# chave da própria tabela e não um índice secundário.
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
	"""Sorteia um puzzle calibrado pelo rating atual do jogador.

	A faixa de rating de `filters` é ignorada: a janela é centrada um pouco
	ACIMA do rating -- um puzzle levemente além do teu nível ensina mais do que
	um que você resolve no automático -- e a largura dela acompanha o DESVIO:
	enquanto o sistema não te conhece, sorteia largo (o que também é o jeito
	mais rápido de te conhecer); conforme a confiança aumenta, a janela fecha
	em volta de você.

	Se a janela vier vazia -- possível quando há filtro de tema estreito --,
	ela é alargada em etapas, e no limite o rating é ignorado: é melhor um
	puzzle fora da faixa ideal do que nenhum puzzle.
	"""
	player = _load_rating(connection)
	# 2,5 desvios cobrem a faixa em que o jogador plausivelmente está. Os
	# limites impedem os dois extremos ruins: janela estreita demais para achar
	# puzzle, e larga a ponto de deixar de ser calibrada.
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
	# Nada na vizinhança: cai para o sorteio sem restrição de rating.
	return random_puzzle(
		connection,
		PuzzleFilters(
			theme_slugs=filters.theme_slugs,
			min_popularity=filters.min_popularity,
			excluded_ids=filters.excluded_ids,
		),
	)


# ---------------------------------------------------------------- histórico


def record_attempt(
	connection: sqlite3.Connection,
	puzzle_id: str,
	solved: bool,
	mistakes: int,
	hints_used: int,
	elapsed_ms: int,
) -> AttemptResult:
	"""Grava a tentativa, atualiza o rating do jogador e devolve o que mudou."""
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
		# A tentativa vira uma partida contra este puzzle. Só o jogador muda:
		# o rating do puzzle vem do Lichess, calculado sobre milhões de
		# tentativas, e não é nosso para mexer.
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
	"""Cada tema do banco com quantos puzzles o têm. Varre a tabela inteira."""
	counts: Counter[str] = Counter()
	for (themes,) in connection.execute("SELECT themes FROM lichess.puzzles"):
		for slug in (themes or "").split():
			counts[slug] += 1
	return sorted(counts.items(), key=lambda item: item[0].casefold())
