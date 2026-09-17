# coding: utf-8
# pyright: basic

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PLUGIN_DIRECTORY = Path(__file__).resolve().parents[1]


def _user_data_directory() -> Path:
	"""Onde ficam os dados do usuário: o banco de puzzles, o histórico e o cache.

	Dentro do NVDA é `<pasta de configuração do NVDA>/chessmart`, como os
	outros add-ons fazem: a pasta do add-on é apagada e recriada a cada
	atualização, e o histórico do jogador não pode ir junto. Fora do NVDA
	(testes, ferramentas) é `data/` ao lado do código, como sempre foi.
	"""
	try:
		import globalVars  # pyright: ignore[reportMissingImports] - módulo do NVDA

		config_path = globalVars.appArgs.configPath
	except (ImportError, AttributeError):
		config_path = None
	if config_path:
		return Path(config_path) / "chessmart"
	return PLUGIN_DIRECTORY / "data"


ADDON_DATA_DIRECTORY = _user_data_directory()
LEGACY_DATA_DIRECTORY = PLUGIN_DIRECTORY / "data"
# O Python do NVDA não traz `sqlite3`; a pasta abaixo carrega a extensão e o
# pacote da biblioteca padrão do CPython 3.13 x64 (ver o README que está lá).
SQLITE_RUNTIME_DIRECTORY = PLUGIN_DIRECTORY / "lib" / "sqlite3_runtime"

# Dois arquivos, de propósito. `puzzles.db` é a base do Lichess: grande,
# substituída inteira a cada atualização, e é ela que o usuário pode apontar
# para outro lugar. `tactic.db` é o histórico do jogador -- tentativas, rating,
# evolução -- e mora sempre na pasta de dados do add-on, intocado por
# atualização nenhuma.
PUZZLES_DB_NAME = "puzzles.db"
HISTORY_DB_NAME = "tactic.db"
HISTORY_DB_PATH = ADDON_DATA_DIRECTORY / HISTORY_DB_NAME
DEFAULT_DB_CANDIDATES = tuple(
	candidate
	for candidate in (
		os.environ.get("CHESSMART_PUZZLES_DB_PATH"),
		str(ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME),
	)
	if candidate
)


def _ensure_sqlite3_importable() -> None:
	"""Deixa `import sqlite3` funcionar dentro do NVDA.

	Fora do NVDA (Python de sistema, testes) o módulo já existe e nada é feito.
	Dentro, a pasta do runtime entra no `sys.path` e no caminho de DLLs, para
	que `_sqlite3.pyd` encontre o `sqlite3.dll` que está ao lado dele.
	"""
	try:
		import sqlite3  # noqa: F401

		return
	except ImportError:
		pass
	runtime = str(SQLITE_RUNTIME_DIRECTORY)
	if runtime not in sys.path:
		sys.path.insert(0, runtime)
	if hasattr(os, "add_dll_directory"):
		os.add_dll_directory(runtime)
	import sqlite3  # noqa: F401


def _log(message: str) -> None:
	try:
		from logHandler import log  # pyright: ignore[reportMissingImports] - módulo do NVDA
	except ImportError:
		print(message, file=sys.stderr)
	else:
		log.info(message)


def _move_legacy_data_if_needed() -> None:
	"""Leva os dados da pasta antiga (dentro do add-on) para a pasta do usuário, uma vez.

	Só move o que ainda não existe no destino; é rename, não cópia, então
	o banco de 1,4 GB não custa nada.
	"""
	if LEGACY_DATA_DIRECTORY == ADDON_DATA_DIRECTORY or not LEGACY_DATA_DIRECTORY.is_dir():
		return
	moved = []
	for name in ("puzzles.db", "tactic.db", "theme_catalog_cache.json", "manifest_url.txt"):
		source = LEGACY_DATA_DIRECTORY / name
		target = ADDON_DATA_DIRECTORY / name
		if source.is_file() and not target.exists():
			ADDON_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
			try:
				source.replace(target)
				moved.append(name)
			except OSError:
				continue
	for backup in LEGACY_DATA_DIRECTORY.glob("tactic.backup-*.db"):
		target = ADDON_DATA_DIRECTORY / backup.name
		if not target.exists():
			try:
				backup.replace(target)
			except OSError:
				continue
	if moved:
		_log(
			f"chessmart: dados movidos de {LEGACY_DATA_DIRECTORY} para {ADDON_DATA_DIRECTORY}: {', '.join(moved)}",
		)


def _split_legacy_if_needed() -> None:
	"""Divide o `tactic.db` antigo (puzzles + histórico num arquivo só), uma vez.

	Acontece na primeira abertura depois da atualização, e só quando ainda não
	existe `puzzles.db`. O histórico ganha um backup datado ao lado.
	"""
	puzzles_path = ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME
	if not HISTORY_DB_PATH.is_file():
		return
	store = load_store()
	if not store.has_puzzles_table(HISTORY_DB_PATH):
		return
	if puzzles_path.exists():
		# Já existe um banco de puzzles (baixado antes de a divisão rodar):
		# o histórico só precisa largar a tabela de puzzles que carrega.
		backup = store.slim_legacy_history(HISTORY_DB_PATH)
		_log(
			f"chessmart: tabela de puzzles removida de {HISTORY_DB_PATH.name}; backup do histórico em {backup.name}",
		)
		return
	backup = store.split_legacy_database(HISTORY_DB_PATH, puzzles_path, HISTORY_DB_PATH)
	_repoint_theme_catalog_cache(HISTORY_DB_PATH, puzzles_path)
	_log(
		f"chessmart: tactic.db dividido em {puzzles_path.name} e {HISTORY_DB_PATH.name}; "
		f"backup do histórico em {backup.name}",
	)


def _repoint_theme_catalog_cache(old_path: Path, new_path: Path) -> None:
	"""Faz o cache de temas seguir o arquivo renomeado.

	A assinatura do cache guarda caminho, tamanho e data do banco. Depois da
	divisão o caminho muda, e sem isto a primeira abertura refaria a varredura
	dos milhões de puzzles com o NVDA parado. Os temas são os mesmos; só o
	envelope precisa acompanhar.
	"""
	cache_path = ADDON_DATA_DIRECTORY / "theme_catalog_cache.json"
	if not cache_path.is_file():
		return
	try:
		payload = json.loads(cache_path.read_text(encoding="utf-8"))
		if payload.get("dbPath") != str(old_path.resolve()):
			return
		stat = new_path.stat()
		payload.update(dbPath=str(new_path.resolve()), dbSize=stat.st_size, dbModifiedNs=stat.st_mtime_ns)
		cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
	except (OSError, ValueError):
		# Cache é conveniência; se não der para ajustar, ele se refaz sozinho.
		return


def load_store():
	"""O módulo `store`, com o `sqlite3` garantido antes.

	`store.py` importa `sqlite3` no topo, e dentro do NVDA isso só funciona
	depois que a pasta do runtime entrou no caminho. Por isso ele não é
	importado por ninguém diretamente: passa sempre por aqui, na hora de usar,
	e o resto do add-on carrega mesmo numa máquina onde o SQLite falte.
	"""
	_ensure_sqlite3_importable()
	from . import store

	return store


def is_puzzles_database(db_path: Path) -> bool:
	"""Diz se o arquivo é um banco de puzzles (tem a tabela `puzzles`)."""
	return load_store().has_puzzles_table(db_path)


def resolve_default_db_path() -> Path | None:
	"""O banco de puzzles em uso, ou None se ainda não houver nenhum."""
	_move_legacy_data_if_needed()
	_split_legacy_if_needed()
	for candidate in DEFAULT_DB_CANDIDATES:
		db_path = Path(candidate)
		if db_path.is_file():
			return db_path
	return None
