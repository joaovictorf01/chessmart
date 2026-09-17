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
import time
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
class DownloadPart:
	"""Um arquivo a baixar: uma fatia do .gz, ou ele inteiro quando é pequeno."""

	file: str
	bytes: int
	sha256: str
	url: str


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
	# As partes, na ordem; concatenadas são o .gz inteiro. Um manifesto antigo,
	# sem `parts`, vira uma parte só: o próprio arquivo.
	parts: tuple[DownloadPart, ...] = ()


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
		raw_parts = download.get("parts") or [download]
		parts = tuple(
			DownloadPart(
				file=str(part.get("file", "")),
				bytes=int(part.get("bytes", 0)),
				sha256=str(part.get("sha256", "")),
				url=urllib.parse.urljoin(base_url, str(part.get("file", ""))),
			)
			for part in raw_parts
			if part.get("file")
		)
		tiers[name] = TierInfo(
			tier=name,
			description=str(entry.get("description", "")),
			puzzle_count=int(entry.get("puzzleCount", 0)),
			disk_bytes=int(entry.get("bytes", 0)),
			download_bytes=int(download.get("bytes", 0)),
			download_file=str(download.get("file", "")),
			download_sha256=str(download.get("sha256", "")),
			download_url=urllib.parse.urljoin(base_url, str(download.get("file", ""))),
			parts=parts,
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


class _PartFailed(Exception):
	"""Uma parte não chegou inteira ou não conferiu; vale tentar essa parte de novo."""


def download_tier(
	tier: TierInfo,
	target_path: Path,
	progress: ProgressCallback | None = None,
	cancel: threading.Event | None = None,
	timeout: float = 60.0,
	attempts_per_part: int = 3,
	retry_delay: float = 5.0,
) -> Path:
	"""Baixa o `.db.gz` do nível, descomprime em fluxo e instala em `target_path`.

	O .gz pode vir em partes (assets grandes falham no GitHub); elas passam, em
	ordem, pelo mesmo descompressor, como se fossem um arquivo só. O arquivo
	comprimido nunca toca o disco: cada pedaço vai para o zlib e o resultado
	para `target.part`.

	Conferência em dois níveis: o SHA-256 de cada parte assim que ela termina
	(um erro aparece cedo, não depois de 600 MB) e o do .gz inteiro no fim, que
	é o que o manifesto assina. Uma parte que falha é tentada de novo sozinha:
	antes de cada parte guardam-se cópias do descompressor e do hash do todo, e
	a saída volta ao ponto em que a parte começou. Só com tudo conferido o
	`.part` toma o lugar do banco atual -- quem estiver no meio de uma sessão
	continua com o antigo até a próxima abertura.
	"""
	target_path = Path(target_path)
	target_path.parent.mkdir(parents=True, exist_ok=True)
	partial = target_path.with_name(target_path.name + ".part")
	parts = tier.parts or (
		DownloadPart(tier.download_file, tier.download_bytes, tier.download_sha256, tier.download_url),
	)
	total = tier.download_bytes or sum(part.bytes for part in parts)
	whole_digest = hashlib.sha256()
	inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
	done = 0
	try:
		with partial.open("wb") as out:
			if progress:
				progress(0, total)
			for part in parts:
				out_offset = out.tell()
				done_before = done
				digest_before = whole_digest.copy()
				inflater_before = inflater.copy()
				for attempt in range(1, attempts_per_part + 1):
					try:
						done = _download_part(
							part,
							out,
							inflater,
							whole_digest,
							done,
							total,
							progress,
							cancel,
							timeout,
						)
						break
					except (_PartFailed, urllib.error.URLError, OSError, zlib.error) as error:
						if attempt == attempts_per_part:
							raise DownloadError(f"download: {part.file}: {error}") from error
						# Volta ao estado de antes desta parte e tenta só ela de novo.
						out.seek(out_offset)
						out.truncate()
						done = done_before
						whole_digest = digest_before.copy()
						inflater = inflater_before.copy()
						if cancel is not None and cancel.wait(retry_delay):
							raise DownloadCancelled()
						elif cancel is None:
							time.sleep(retry_delay)
			out.write(inflater.flush())
	except DownloadCancelled:
		partial.unlink(missing_ok=True)
		raise
	except DownloadError:
		partial.unlink(missing_ok=True)
		raise
	except (OSError, zlib.error) as error:
		partial.unlink(missing_ok=True)
		raise DownloadError(f"download: {error}") from error

	if tier.download_sha256 and whole_digest.hexdigest() != tier.download_sha256:
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


def _download_part(
	part: DownloadPart,
	out,
	inflater,
	whole_digest,
	done: int,
	total: int,
	progress: ProgressCallback | None,
	cancel: threading.Event | None,
	timeout: float,
) -> int:
	"""Baixa uma parte para dentro do fluxo em andamento; devolve o total de bytes recebidos.

	Levanta `_PartFailed` se a parte veio com tamanho ou SHA-256 diferentes do
	manifesto, `DownloadCancelled` se o usuário desistiu, e deixa passar os
	erros de rede e de zlib para quem chamou decidir a repetição.
	"""
	request = urllib.request.Request(part.url, headers={"User-Agent": USER_AGENT})
	part_digest = hashlib.sha256()
	received = 0
	with urllib.request.urlopen(request, timeout=timeout) as response:
		while True:
			if cancel is not None and cancel.is_set():
				raise DownloadCancelled()
			chunk = response.read(CHUNK)
			if not chunk:
				break
			part_digest.update(chunk)
			whole_digest.update(chunk)
			out.write(inflater.decompress(chunk))
			received += len(chunk)
			done += len(chunk)
			if progress:
				progress(done, total)
	if part.bytes and received != part.bytes:
		raise _PartFailed(f"expected {part.bytes} bytes, received {received}")
	if part.sha256 and part_digest.hexdigest() != part.sha256:
		raise _PartFailed("checksum mismatch")
	return done
