#!/usr/bin/env python3
"""Gera o `puzzles.db` do chessmart a partir da base aberta de puzzles do Lichess.

Uso típico (quem roda é o mantenedor ou a Action mensal, nunca o usuário):

    py -3 tools/build_puzzles.py --download --out dist/puzzles
    py -3 tools/build_puzzles.py --csv lichess_db_puzzle.csv.zst --tier light --out dist/puzzles

Saída em `--out`:

    puzzles-light.db, puzzles-full.db   bancos prontos para o add-on
    puzzles-light.db.gz, ...            os mesmos, comprimidos para transporte
    manifest.json                       o que o add-on lê para saber se há base nova

A base do Lichess (https://database.lichess.org/#puzzles) é CC0 e é atualizada
mensalmente. O download guarda o ETag ao lado do arquivo e, se o servidor disser
que nada mudou, não baixa de novo -- é o que permite rodar isto todo mês sem
custo quando não há nada novo.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

LICHESS_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
USER_AGENT = "chessmart-build-puzzles/1.0 (+https://github.com/joaovictorf01/chessmart)"
SCHEMA_VERSION = 1

# Cada nível é um filtro sobre a base inteira. O leve fica com o que muita
# gente jogou e aprovou: é o que faz sentido baixar na primeira vez.
TIERS = {
	"light": {
		"description": "Puzzles com popularidade >= 95 e pelo menos 500 jogadas",
		"keep": lambda row: row["popularity"] >= 95 and row["nb_plays"] >= 500,
	},
	"full": {
		"description": "A base inteira do Lichess",
		"keep": lambda row: True,
	},
}

# O mesmo schema que o add-on sempre usou (tactic/sqlite_bridge.py consulta
# `lichess.puzzles` com estas colunas e estes índices).
PUZZLES_SCHEMA = """
CREATE TABLE puzzles (
  id TEXT PRIMARY KEY,
  fen TEXT NOT NULL,
  moves TEXT NOT NULL,
  rating INTEGER,
  rating_deviation INTEGER,
  popularity INTEGER,
  nb_plays INTEGER,
  themes TEXT NOT NULL DEFAULT '',
  game_url TEXT NOT NULL DEFAULT '',
  opening_tags TEXT NOT NULL DEFAULT ''
);
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""
PUZZLES_INDEXES = """
CREATE INDEX idx_puzzles_rating ON puzzles(rating);
CREATE INDEX idx_puzzles_popularity ON puzzles(popularity);
CREATE INDEX idx_puzzles_rating_popularity ON puzzles(rating, popularity);
"""
COLUMNS = (
	"id",
	"fen",
	"moves",
	"rating",
	"rating_deviation",
	"popularity",
	"nb_plays",
	"themes",
	"game_url",
	"opening_tags",
)
BATCH = 20_000


def log(message: str) -> None:
	print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------- download


def download(target: Path) -> tuple[Path, str | None]:
	"""Baixa o CSV do Lichess se ele mudou. Devolve (caminho, Last-Modified)."""
	etag_path = target.with_suffix(target.suffix + ".etag")
	headers = {"User-Agent": USER_AGENT}
	if target.is_file() and etag_path.is_file():
		headers["If-None-Match"] = etag_path.read_text(encoding="utf-8").strip()
	request = urllib.request.Request(LICHESS_URL, headers=headers)
	try:
		response = urllib.request.urlopen(request, timeout=60)
	except urllib.error.HTTPError as error:
		if error.code == 304:
			log(f"Lichess: sem mudança desde o último download ({target.name})")
			return target, _read_sidecar(target, "last-modified")
		raise
	with response:
		total = int(response.headers.get("Content-Length") or 0)
		last_modified = response.headers.get("Last-Modified")
		etag = response.headers.get("ETag")
		log(f"Lichess: baixando {total / 1e6:.0f} MB (Last-Modified: {last_modified})")
		target.parent.mkdir(parents=True, exist_ok=True)
		partial = target.with_suffix(target.suffix + ".part")
		done = 0
		with partial.open("wb") as handle:
			while chunk := response.read(1 << 20):
				handle.write(chunk)
				done += len(chunk)
				if total and done % (50 << 20) < (1 << 20):
					log(f"  {done / 1e6:.0f} / {total / 1e6:.0f} MB")
		partial.replace(target)
	if etag:
		etag_path.write_text(etag, encoding="utf-8")
	if last_modified:
		_write_sidecar(target, "last-modified", last_modified)
	return target, last_modified


def _write_sidecar(target: Path, name: str, value: str) -> None:
	target.with_suffix(target.suffix + f".{name}").write_text(value, encoding="utf-8")


def _read_sidecar(target: Path, name: str) -> str | None:
	path = target.with_suffix(target.suffix + f".{name}")
	return path.read_text(encoding="utf-8").strip() if path.is_file() else None


# ---------------------------------------------------------------- leitura


def open_zst_text(path: Path):
	"""Abre o `.csv.zst` como texto, com o zstd da stdlib (3.14+) ou o pacote `zstandard`."""
	raw = path.open("rb")
	try:
		from compression import zstd  # Python 3.14+
	except ImportError:
		try:
			import zstandard
		except ImportError as error:
			raise SystemExit(
				"Precisa do Python 3.14+ (compression.zstd) ou do pacote `zstandard` (pip install zstandard).",
			) from error
		stream = zstandard.ZstdDecompressor().stream_reader(raw)
	else:
		stream = zstd.ZstdFile(raw, "rb")
	return io.TextIOWrapper(io.BufferedReader(stream, 1 << 20), encoding="utf-8", newline="")


def iter_rows(csv_path: Path):
	"""Linhas do CSV já convertidas: números como int, texto como veio."""
	with open_zst_text(csv_path) as text:
		reader = csv.DictReader(text)
		for record in reader:
			yield {
				"id": record["PuzzleId"],
				"fen": record["FEN"],
				"moves": record["Moves"],
				"rating": int(record["Rating"]),
				"rating_deviation": int(record["RatingDeviation"]),
				"popularity": int(record["Popularity"]),
				"nb_plays": int(record["NbPlays"]),
				"themes": record.get("Themes") or "",
				"game_url": record.get("GameUrl") or "",
				"opening_tags": record.get("OpeningTags") or "",
			}


# ---------------------------------------------------------------- escrita


def build_tier(csv_path: Path, tier: str, out_dir: Path, source_info: dict) -> dict:
	keep = TIERS[tier]["keep"]
	db_path = out_dir / f"puzzles-{tier}.db"
	if db_path.exists():
		db_path.unlink()
	log(f"{tier}: gerando {db_path.name}")
	connection = sqlite3.connect(db_path)
	# Banco novo, descartável se falhar no meio: sem journal nem fsync, que
	# aqui só custariam tempo.
	connection.execute("PRAGMA journal_mode = OFF")
	connection.execute("PRAGMA synchronous = OFF")
	connection.execute("PRAGMA cache_size = -200000")
	connection.executescript(PUZZLES_SCHEMA)
	insert = f"INSERT INTO puzzles ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})"
	batch: list[tuple] = []
	seen = kept = 0
	for row in iter_rows(csv_path):
		seen += 1
		if not keep(row):
			continue
		kept += 1
		batch.append(tuple(row[column] for column in COLUMNS))
		if len(batch) >= BATCH:
			connection.executemany(insert, batch)
			batch.clear()
			if kept % 500_000 < BATCH:
				log(f"  {kept:,} puzzles gravados ({seen:,} lidos)")
	if batch:
		connection.executemany(insert, batch)
	log(f"  índices ({kept:,} puzzles)")
	connection.executescript(PUZZLES_INDEXES)
	meta = {
		"schemaVersion": str(SCHEMA_VERSION),
		"tier": tier,
		"tierDescription": TIERS[tier]["description"],
		"puzzleCount": str(kept),
		"generatedAt": source_info["generatedAt"],
		"sourceUrl": LICHESS_URL,
		"sourceLastModified": source_info.get("sourceLastModified") or "",
		"sourceRowCount": str(seen),
	}
	connection.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", list(meta.items()))
	connection.commit()
	connection.close()

	gz_path = db_path.with_suffix(db_path.suffix + ".gz")
	log(f"  comprimindo {gz_path.name}")
	with db_path.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
		shutil.copyfileobj(src, dst, 1 << 20)
	entry = {
		"tier": tier,
		"description": TIERS[tier]["description"],
		"puzzleCount": kept,
		"file": db_path.name,
		"bytes": db_path.stat().st_size,
		"sha256": sha256(db_path),
		"download": {
			"file": gz_path.name,
			"bytes": gz_path.stat().st_size,
			"sha256": sha256(gz_path),
		},
	}
	log(
		f"  pronto: {entry['bytes'] / 1e6:.0f} MB no disco, {entry['download']['bytes'] / 1e6:.0f} MB para baixar",
	)
	return entry


def sha256(path: Path) -> str:
	digest = hashlib.sha256()
	with path.open("rb") as handle:
		while chunk := handle.read(1 << 20):
			digest.update(chunk)
	return digest.hexdigest()


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	source = parser.add_mutually_exclusive_group(required=True)
	source.add_argument("--download", action="store_true", help="baixa o CSV do Lichess (com cache por ETag)")
	source.add_argument("--csv", type=Path, help="usa um lichess_db_puzzle.csv.zst já baixado")
	parser.add_argument(
		"--cache-dir",
		type=Path,
		default=Path("build/lichess"),
		help="onde o download fica guardado",
	)
	parser.add_argument("--tier", choices=[*TIERS, "all"], default="all")
	parser.add_argument("--out", type=Path, default=Path("dist/puzzles"))
	parser.add_argument("--limit", type=int, default=0, help="lê só as N primeiras linhas (para testar)")
	args = parser.parse_args(argv)

	if args.download:
		csv_path, last_modified = download(args.cache_dir / "lichess_db_puzzle.csv.zst")
	else:
		csv_path, last_modified = args.csv, _read_sidecar(args.csv, "last-modified")
		if last_modified is None:
			last_modified = dt.datetime.fromtimestamp(csv_path.stat().st_mtime, dt.timezone.utc).strftime(
				"%a, %d %b %Y %H:%M:%S GMT",
			)
	if args.limit:
		original = iter_rows

		def limited(path):
			for index, row in enumerate(original(path)):
				if index >= args.limit:
					break
				yield row

		globals()["iter_rows"] = limited

	args.out.mkdir(parents=True, exist_ok=True)
	source_info = {
		"generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
		"sourceLastModified": last_modified,
	}
	tiers = list(TIERS) if args.tier == "all" else [args.tier]
	entries = [build_tier(csv_path, tier, args.out, source_info) for tier in tiers]
	manifest = {
		"schemaVersion": SCHEMA_VERSION,
		"generatedAt": source_info["generatedAt"],
		"source": {"url": LICHESS_URL, "lastModified": last_modified},
		"tiers": {entry["tier"]: entry for entry in entries},
	}
	manifest_path = args.out / "manifest.json"
	manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
	log(f"manifesto: {manifest_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
