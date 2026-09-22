#!/usr/bin/env python3
"""Generates chessmart's `puzzles.db` from Lichess's open puzzle database.

Typical usage (run by the maintainer or the monthly Action, never the user):

    py -3 tools/build_puzzles.py --download --out dist/puzzles
    py -3 tools/build_puzzles.py --csv lichess_db_puzzle.csv.zst --tier light --out dist/puzzles

Output in `--out`:

    puzzles-light.db, puzzles-full.db   databases ready for the add-on
    puzzles-light.db.gz, ...            the same, compressed for transport
    manifest.json                       what the add-on reads to know if there's a new database

The Lichess database (https://database.lichess.org/#puzzles) is CC0 and is
updated monthly. The download keeps the ETag alongside the file and, if the
server says nothing changed, doesn't download again -- which lets this run
every month at no cost when there's nothing new.
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
SCHEMA_VERSION = 2
# Release assets above ~500 MB fail on GitHub ("Error saving asset");
# the .gz is split into parts of this size and the add-on downloads them in sequence.
DEFAULT_PART_SIZE = 300 * 1024 * 1024

# Each tier is a filter over the whole database. The light one keeps what
# a lot of people have played and approved of: the sensible first download.
TIERS = {
	"light": {
		"description": "Puzzles with popularity >= 95 and at least 500 plays",
		"keep": lambda row: row["popularity"] >= 95 and row["nb_plays"] >= 500,
	},
	"full": {
		"description": "The entire Lichess database",
		"keep": lambda row: True,
	},
}

# The same schema the add-on has always used (tactic/store.py queries
# `lichess.puzzles` with these columns and these indexes).
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
	"""Download the Lichess CSV if it changed. Returns (path, Last-Modified)."""
	etag_path = target.with_suffix(target.suffix + ".etag")
	headers = {"User-Agent": USER_AGENT}
	if target.is_file() and etag_path.is_file():
		headers["If-None-Match"] = etag_path.read_text(encoding="utf-8").strip()
	request = urllib.request.Request(LICHESS_URL, headers=headers)
	try:
		response = urllib.request.urlopen(request, timeout=60)
	except urllib.error.HTTPError as error:
		if error.code == 304:
			log(f"Lichess: no change since the last download ({target.name})")
			return target, _read_sidecar(target, "last-modified")
		raise
	with response:
		total = int(response.headers.get("Content-Length") or 0)
		last_modified = response.headers.get("Last-Modified")
		etag = response.headers.get("ETag")
		log(f"Lichess: downloading {total / 1e6:.0f} MB (Last-Modified: {last_modified})")
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


# ---------------------------------------------------------------- reading


def open_zst_text(path: Path):
	"""Opens the `.csv.zst` as text, using stdlib zstd (3.14+) or the `zstandard` package."""
	raw = path.open("rb")
	try:
		from compression import zstd  # Python 3.14+
	except ImportError:
		try:
			import zstandard
		except ImportError as error:
			raise SystemExit(
				"Requires Python 3.14+ (compression.zstd) or the `zstandard` package (pip install zstandard).",
			) from error
		stream = zstandard.ZstdDecompressor().stream_reader(raw)
	else:
		stream = zstd.ZstdFile(raw, "rb")
	return io.TextIOWrapper(io.BufferedReader(stream, 1 << 20), encoding="utf-8", newline="")


def iter_rows(csv_path: Path):
	"""CSV rows already converted: numbers as int, text as-is."""
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


# ---------------------------------------------------------------- writing


def build_tier(
	csv_path: Path,
	tier: str,
	out_dir: Path,
	source_info: dict,
	part_size: int = DEFAULT_PART_SIZE,
) -> dict:
	keep = TIERS[tier]["keep"]
	db_path = out_dir / f"puzzles-{tier}.db"
	if db_path.exists():
		db_path.unlink()
	log(f"{tier}: generating {db_path.name}")
	connection = sqlite3.connect(db_path)
	# A fresh database, disposable if it fails partway through: no journal or
	# fsync, which would only cost time here.
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
				log(f"  {kept:,} puzzles written ({seen:,} read)")
	if batch:
		connection.executemany(insert, batch)
	log(f"  indexes ({kept:,} puzzles)")
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
	log(f"  compressing {gz_path.name}")
	with db_path.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
		shutil.copyfileobj(src, dst, 1 << 20)
	parts = split_into_parts(gz_path, part_size)
	entry = {
		"tier": tier,
		"description": TIERS[tier]["description"],
		"puzzleCount": kept,
		"file": db_path.name,
		"bytes": db_path.stat().st_size,
		"sha256": sha256(db_path),
		"download": {
			# The whole: logical name, size and SHA-256 of the entire .gz, which the
			# add-on checks after joining the parts.
			"file": gz_path.name,
			"bytes": gz_path.stat().st_size,
			"sha256": sha256(gz_path),
			# The parts, in order: each with its own SHA-256, checked as soon as it
			# finishes arriving.
			"parts": parts,
		},
	}
	log(
		f"  done: {entry['bytes'] / 1e6:.0f} MB on disk, "
		f"{entry['download']['bytes'] / 1e6:.0f} MB to download in {len(parts)} part(s)",
	)
	return entry


def split_into_parts(gz_path: Path, part_size: int) -> list[dict]:
	"""Splits the .gz into `name.partN` files of up to `part_size` bytes; a small file becomes a single part.

	Concatenating the parts reproduces the original .gz byte for byte: the
	add-on doesn't need to know where one ends and the next begins, just feed
	the same decompressor all of them, in order.
	"""
	for stale in gz_path.parent.glob(gz_path.name + ".part*"):
		stale.unlink()
	total = gz_path.stat().st_size
	if total <= part_size:
		return [{"file": gz_path.name, "bytes": total, "sha256": sha256(gz_path)}]
	parts = []
	with gz_path.open("rb") as src:
		index = 1
		while True:
			chunk_path = gz_path.with_name(f"{gz_path.name}.part{index}")
			written = 0
			digest = hashlib.sha256()
			with chunk_path.open("wb") as dst:
				while written < part_size:
					piece = src.read(min(1 << 20, part_size - written))
					if not piece:
						break
					dst.write(piece)
					digest.update(piece)
					written += len(piece)
			if written == 0:
				chunk_path.unlink()
				break
			parts.append({"file": chunk_path.name, "bytes": written, "sha256": digest.hexdigest()})
			index += 1
	return parts


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
	source.add_argument(
		"--download",
		action="store_true",
		help="download the CSV from Lichess (cached by ETag)",
	)
	source.add_argument("--csv", type=Path, help="use an already downloaded lichess_db_puzzle.csv.zst")
	parser.add_argument(
		"--cache-dir",
		type=Path,
		default=Path("build/lichess"),
		help="where the download is kept",
	)
	parser.add_argument("--tier", choices=[*TIERS, "all"], default="all")
	parser.add_argument("--out", type=Path, default=Path("dist/puzzles"))
	parser.add_argument("--limit", type=int, default=0, help="read only the first N lines (for testing)")
	parser.add_argument(
		"--part-size",
		type=int,
		default=DEFAULT_PART_SIZE,
		help="maximum size of each .gz part, in bytes (default: 300 MiB)",
	)
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
	entries = [build_tier(csv_path, tier, args.out, source_info, args.part_size) for tier in tiers]
	manifest = {
		"schemaVersion": SCHEMA_VERSION,
		"generatedAt": source_info["generatedAt"],
		"source": {"url": LICHESS_URL, "lastModified": last_modified},
		"tiers": {entry["tier"]: entry for entry in entries},
	}
	manifest_path = args.out / "manifest.json"
	manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
	log(f"manifest: {manifest_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
