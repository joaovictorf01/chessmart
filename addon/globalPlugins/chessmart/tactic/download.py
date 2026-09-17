# coding: utf-8
"""Download e atualização do banco de puzzles.

O banco é publicado como asset da release fixa `puzzles-latest` do repositório,
regenerado todo mês pelo workflow a partir da base do Lichess. Aqui não há
nada de interface: quem chama passa uma função de progresso e um `Event` de
cancelamento, e cuida de mostrar isso do jeito que quiser.
"""

from __future__ import annotations

import dataclasses
import email.utils
import hashlib
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Callable

DEFAULT_MANIFEST_URL = (
	"https://github.com/joaovictorf01/chessmart/releases/download/puzzles-latest/manifest.json"
)


def manifest_url() -> str:
	"""De onde vem o manifesto: variável de ambiente, arquivo de override na
	pasta de dados (para testar contra um servidor local), ou a release."""
	from .db import ADDON_DATA_DIRECTORY

	override = os.environ.get("CHESSMART_PUZZLES_MANIFEST_URL")
	if override:
		return override
	override_file = ADDON_DATA_DIRECTORY / "manifest_url.txt"
	if override_file.is_file():
		value = override_file.read_text(encoding="utf-8").strip()
		if value:
			return value
	return DEFAULT_MANIFEST_URL


USER_AGENT = "chessmart-nvda-addon/1.0"
CHUNK = 256 * 1024

ProgressCallback = Callable[[int, int], None]


class DownloadCancelled(Exception):
	pass


class DownloadError(Exception):
	pass


@dataclasses.dataclass(frozen=True)
class TierInfo:
	tier: str
	description: str
	puzzle_count: int
	disk_bytes: int
	download_bytes: int
	download_file: str
	download_sha256: str
	download_url: str


@dataclasses.dataclass(frozen=True)
class Manifest:
	generated_at: str
	source_last_modified: str
	tiers: dict[str, TierInfo]

	@property
	def source_date(self):
		return _parse_http_date(self.source_last_modified)


@dataclasses.dataclass(frozen=True)
class InstalledInfo:
	tier: str
	puzzle_count: int
	source_last_modified: str
	generated_at: str

	@property
	def source_date(self):
		return _parse_http_date(self.source_last_modified)


def _parse_http_date(value: str):
	try:
		return email.utils.parsedate_to_datetime(value)
	except (TypeError, ValueError, IndexError):
		return None


# ---------------------------------------------------------------- manifesto


def fetch_manifest(url: str | None = None, timeout: float = 30.0) -> Manifest:
	url = url or manifest_url()
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			payload = json.loads(response.read().decode("utf-8"))
	except (urllib.error.URLError, OSError, ValueError) as error:
		raise DownloadError(f"manifest: {error}") from error
	return parse_manifest(payload, base_url=url)


def parse_manifest(payload: dict, base_url: str) -> Manifest:
	tiers = {}
	for name, entry in (payload.get("tiers") or {}).items():
		download = entry.get("download") or {}
		tiers[name] = TierInfo(
			tier=name,
			description=str(entry.get("description", "")),
			puzzle_count=int(entry.get("puzzleCount", 0)),
			disk_bytes=int(entry.get("bytes", 0)),
			download_bytes=int(download.get("bytes", 0)),
			download_file=str(download.get("file", "")),
			download_sha256=str(download.get("sha256", "")),
			download_url=urllib.parse.urljoin(base_url, str(download.get("file", ""))),
		)
	source = payload.get("source") or {}
	return Manifest(
		generated_at=str(payload.get("generatedAt", "")),
		source_last_modified=str(source.get("lastModified", "")),
		tiers=tiers,
	)


# ---------------------------------------------------------------- instalado


def installed_info(db_path: Path | None) -> InstalledInfo | None:
	"""Lê a tabela `meta` do banco instalado; None se não houver banco ou meta."""
	if db_path is None or not Path(db_path).is_file():
		return None
	from .db import _ensure_sqlite3_importable

	_ensure_sqlite3_importable()
	import sqlite3

	try:
		connection = sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True)
	except sqlite3.Error:
		return None
	try:
		rows = dict(connection.execute("SELECT key, value FROM meta"))
	except sqlite3.Error:
		return None
	finally:
		connection.close()
	return InstalledInfo(
		tier=rows.get("tier", ""),
		puzzle_count=int(rows.get("puzzleCount", 0) or 0),
		source_last_modified=rows.get("sourceLastModified", ""),
		generated_at=rows.get("generatedAt", ""),
	)


def update_available(manifest: Manifest, installed: InstalledInfo | None) -> bool:
	"""Há base mais nova do que a instalada? Sem `meta` no instalado, sim."""
	if installed is None:
		return True
	new, old = manifest.source_date, installed.source_date
	if new is None or old is None:
		return manifest.generated_at > installed.generated_at
	return new > old


# ---------------------------------------------------------------- download


def download_tier(
	tier: TierInfo,
	target_path: Path,
	progress: ProgressCallback | None = None,
	cancel: threading.Event | None = None,
	timeout: float = 60.0,
) -> Path:
	"""Baixa o `.db.gz` do nível, descomprime em fluxo e instala em `target_path`.

	O arquivo comprimido nunca toca o disco: cada pedaço passa pelo zlib e o
	resultado vai para `target.part`. O SHA-256 é conferido sobre os bytes
	comprimidos, que é o que o manifesto assina. Só depois de tudo conferido o
	`.part` toma o lugar do banco atual -- quem estiver no meio de uma sessão
	continua com o antigo até a próxima abertura.
	"""
	target_path = Path(target_path)
	target_path.parent.mkdir(parents=True, exist_ok=True)
	partial = target_path.with_name(target_path.name + ".part")
	request = urllib.request.Request(tier.download_url, headers={"User-Agent": USER_AGENT})
	digest = hashlib.sha256()
	inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
	done = 0
	total = tier.download_bytes
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response, partial.open("wb") as out:
			total = int(response.headers.get("Content-Length") or total or 0)
			if progress:
				progress(0, total)
			while True:
				if cancel is not None and cancel.is_set():
					raise DownloadCancelled()
				chunk = response.read(CHUNK)
				if not chunk:
					break
				digest.update(chunk)
				out.write(inflater.decompress(chunk))
				done += len(chunk)
				if progress:
					progress(done, total)
			out.write(inflater.flush())
	except DownloadCancelled:
		partial.unlink(missing_ok=True)
		raise
	except (urllib.error.URLError, OSError, zlib.error) as error:
		partial.unlink(missing_ok=True)
		raise DownloadError(f"download: {error}") from error

	if tier.download_sha256 and digest.hexdigest() != tier.download_sha256:
		partial.unlink(missing_ok=True)
		raise DownloadError("download: checksum mismatch, the file is corrupt or was changed in transit")

	from .db import is_puzzles_database

	if not is_puzzles_database(partial):
		partial.unlink(missing_ok=True)
		raise DownloadError("download: the file is not a puzzle database")

	try:
		partial.replace(target_path)
	except OSError as error:
		partial.unlink(missing_ok=True)
		raise DownloadError(f"install: {error}") from error
	return target_path
