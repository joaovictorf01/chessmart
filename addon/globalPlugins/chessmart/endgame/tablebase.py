# coding: utf-8
# pyright: basic

"""Tabelas Syzygy de 3 a 5 peças: o que baixar, de onde, e como abrir.

O manifesto (`syzygy_manifest.json`, gerado por `tools/build_syzygy_manifest.py`)
lista os 290 arquivos do espelho do Lichess com tamanho e SHA-256. O download
é arquivo por arquivo: um que já está no disco com o tamanho certo é pulado,
então cancelar e voltar continua de onde parou; cada arquivo é conferido pelo
hash antes de tomar o nome definitivo. As tabelas ficam na pasta de dados do
usuário (`syzygy/`), fora da pasta do add-on, que é apagada a cada atualização.

Sem NVDA aqui: os testes baixam nada e abrem tabelas de 3 peças que estão
no repositório.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from ..paths import import_bundled
from ..tactic.db import ADDON_DATA_DIRECTORY
from ..tactic.download import CHUNK, USER_AGENT, DownloadCancelled, DownloadError, ProgressCallback

with import_bundled():
	import chess
	import chess.syzygy


MANIFEST_PATH = Path(__file__).resolve().parent / "syzygy_manifest.json"
SYZYGY_DIRECTORY = ADDON_DATA_DIRECTORY / "syzygy"
# Até quantas peças as tabelas cobrem. Acima disto o juiz fica calado.
MAX_PIECES = 5


@dataclasses.dataclass(frozen=True)
class TableFile:
	file: str
	kind: str  # "wdl" ou "dtz"
	pieces: int
	bytes: int
	sha256: str
	url: str


@dataclasses.dataclass(frozen=True)
class TableSet:
	"""Um conjunto que o usuário pode escolher baixar: até N peças."""

	set_id: str
	max_pieces: int
	files: tuple[TableFile, ...]

	@property
	def total_bytes(self) -> int:
		return sum(f.bytes for f in self.files)


def load_manifest(path: Path = MANIFEST_PATH) -> tuple[TableFile, ...]:
	payload = json.loads(Path(path).read_text(encoding="utf-8"))
	return tuple(
		TableFile(
			file=str(entry["file"]),
			kind=str(entry["kind"]),
			pieces=int(entry["pieces"]),
			bytes=int(entry["bytes"]),
			sha256=str(entry["sha256"]),
			url=str(entry["url"]),
		)
		for entry in payload.get("files", [])
	)


def table_sets(files: Iterable[TableFile] | None = None) -> tuple[TableSet, ...]:
	"""Os dois conjuntos oferecidos: até 4 peças (poucos MB) e até 5 (quase 1 GB)."""
	files = tuple(files if files is not None else load_manifest())
	return tuple(
		TableSet(
			set_id=f"upTo{limit}",
			max_pieces=limit,
			files=tuple(f for f in files if f.pieces <= limit),
		)
		for limit in (4, 5)
	)


# ---------------------------------------------------------------- instalado


def is_installed(table: TableFile, directory: Path = SYZYGY_DIRECTORY) -> bool:
	"""Presente com o tamanho do manifesto. O hash foi conferido ao baixar."""
	path = Path(directory) / table.file
	try:
		return path.stat().st_size == table.bytes
	except OSError:
		return False


def missing_files(files: Iterable[TableFile], directory: Path = SYZYGY_DIRECTORY) -> tuple[TableFile, ...]:
	return tuple(f for f in files if not is_installed(f, directory))


def installed_piece_limit(
	files: Iterable[TableFile] | None = None,
	directory: Path = SYZYGY_DIRECTORY,
) -> int:
	"""Até quantas peças as tabelas instaladas cobrem por inteiro: 0, 3, 4 ou 5."""
	files = tuple(files if files is not None else load_manifest())
	limit = 0
	for pieces in (3, 4, 5):
		group = [f for f in files if f.pieces == pieces]
		if group and all(is_installed(f, directory) for f in group):
			limit = pieces
		else:
			break
	return limit


# ---------------------------------------------------------------- download


def download_tables(
	files: Iterable[TableFile],
	directory: Path = SYZYGY_DIRECTORY,
	progress: ProgressCallback | None = None,
	cancel: threading.Event | None = None,
	timeout: float = 60.0,
	attempts_per_file: int = 3,
	retry_delay: float = 5.0,
) -> int:
	"""Baixa o que falta de `files` para `directory`; devolve quantos arquivos baixou.

	O progresso conta os bytes do conjunto inteiro, com os já instalados
	somados de saída, para a barra continuar de onde parou. Um arquivo que
	falha (rede, tamanho ou hash) é tentado de novo sozinho; depois de
	`attempts_per_file` vezes o download inteiro para com `DownloadError`.
	"""
	files = tuple(files)
	directory = Path(directory)
	directory.mkdir(parents=True, exist_ok=True)
	total = sum(f.bytes for f in files)
	done = sum(f.bytes for f in files if is_installed(f, directory))
	if progress:
		progress(done, total)
	downloaded = 0
	for table in files:
		if is_installed(table, directory):
			continue
		for attempt in range(1, attempts_per_file + 1):
			try:
				_download_file(table, directory, done, total, progress, cancel, timeout)
				break
			except (_FileFailed, urllib.error.URLError, OSError) as error:
				if attempt == attempts_per_file:
					raise DownloadError(f"download: {table.file}: {error}") from error
				if cancel is not None and cancel.wait(retry_delay):
					raise DownloadCancelled()
				elif cancel is None:
					time.sleep(retry_delay)
		done += table.bytes
		downloaded += 1
		if progress:
			progress(done, total)
	return downloaded


class _FileFailed(Exception):
	"""Chegou com tamanho ou hash diferentes do manifesto; vale tentar de novo."""


def _download_file(
	table: TableFile,
	directory: Path,
	done_before: int,
	total: int,
	progress: ProgressCallback | None,
	cancel: threading.Event | None,
	timeout: float,
) -> None:
	partial = directory / (table.file + ".part")
	request = urllib.request.Request(table.url, headers={"User-Agent": USER_AGENT})
	digest = hashlib.sha256()
	received = 0
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response, partial.open("wb") as out:
			while True:
				if cancel is not None and cancel.is_set():
					raise DownloadCancelled()
				chunk = response.read(CHUNK)
				if not chunk:
					break
				digest.update(chunk)
				out.write(chunk)
				received += len(chunk)
				if progress:
					progress(done_before + received, total)
		if received != table.bytes:
			raise _FileFailed(f"expected {table.bytes} bytes, received {received}")
		if digest.hexdigest() != table.sha256:
			raise _FileFailed("checksum mismatch")
		partial.replace(directory / table.file)
	except BaseException:
		partial.unlink(missing_ok=True)
		raise


# ---------------------------------------------------------------- abrir


def open_tablebase(directory: Path = SYZYGY_DIRECTORY) -> "chess.syzygy.Tablebase | None":
	"""Abre o que houver na pasta; None se não há tabela nenhuma.

	Abrir só registra os arquivos; nada é lido até a primeira consulta, e uma
	posição cujo material não tem tabela levanta `MissingTableError` na hora.
	"""
	directory = Path(directory)
	if not directory.is_dir() or not any(directory.glob("*.rtb[wz]")):
		return None
	return chess.syzygy.open_tablebase(str(directory))
