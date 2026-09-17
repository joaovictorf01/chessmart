# coding: utf-8

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PLUGIN_DIRECTORY = Path(__file__).resolve().parents[1]
ADDON_DATA_DIRECTORY = PLUGIN_DIRECTORY / "data"
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
        from logHandler import log
    except ImportError:
        print(message, file=sys.stderr)
    else:
        log.info(message)


def _split_legacy_if_needed() -> None:
    """Divide o `tactic.db` antigo (puzzles + histórico num arquivo só), uma vez.

    Acontece na primeira abertura depois da atualização, e só quando ainda não
    existe `puzzles.db`. O histórico ganha um backup datado ao lado.
    """
    puzzles_path = ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME
    if puzzles_path.exists() or not HISTORY_DB_PATH.is_file():
        return
    _ensure_sqlite3_importable()
    from . import sqlite_bridge

    if not sqlite_bridge.has_puzzles_table(HISTORY_DB_PATH):
        return
    backup = sqlite_bridge.split_legacy_database(HISTORY_DB_PATH, puzzles_path, HISTORY_DB_PATH)
    _repoint_theme_catalog_cache(HISTORY_DB_PATH, puzzles_path)
    _log(
        f"chessmart: tactic.db dividido em {puzzles_path.name} e {HISTORY_DB_PATH.name}; "
        f"backup do histórico em {backup.name}"
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
        payload.update(
            dbPath=str(new_path.resolve()), dbSize=stat.st_size, dbModifiedNs=stat.st_mtime_ns
        )
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        # Cache é conveniência; se não der para ajustar, ele se refaz sozinho.
        return


def is_puzzles_database(db_path: Path) -> bool:
    """Diz se o arquivo é um banco de puzzles (tem a tabela `puzzles`)."""
    _ensure_sqlite3_importable()
    from . import sqlite_bridge

    return sqlite_bridge.has_puzzles_table(db_path)


def resolve_default_db_path() -> Path | None:
    """O banco de puzzles em uso, ou None se ainda não houver nenhum."""
    _split_legacy_if_needed()
    for candidate in DEFAULT_DB_CANDIDATES:
        db_path = Path(candidate)
        if db_path.is_file():
            return db_path
    return None


def run_bridge(db_path: Path, command: str, *args: object, history_path: Path | None = None):
    """Executa um comando do `sqlite_bridge` no próprio processo.

    `db_path` é o banco de puzzles; o histórico vai sempre em `tactic.db` na
    pasta de dados, salvo quando um teste passa outro em `history_path`.

    O nome ficou da época em que isto abria um `py -3` por chamada, o que exigia
    Python instalado na máquina de quem usa o add-on. O contrato é o mesmo de
    então: os argumentos chegam como texto (como chegavam pelo `argv`) e o
    resultado passa por JSON, para que a forma seja idêntica à que a camada de
    cima sempre recebeu (tuplas viram listas, chaves viram texto).
    """
    _ensure_sqlite3_importable()
    from . import sqlite_bridge

    handler = sqlite_bridge.COMMANDS.get(command)
    if handler is None:
        raise RuntimeError(f"SQLite bridge failed for {command}: unknown command")
    try:
        connection = sqlite_bridge.connect(Path(db_path), history_path or HISTORY_DB_PATH)
        try:
            # O `with` só cuida do commit/rollback; fechar é por nossa conta --
            # antes o processo filho morria e levava a conexão junto.
            with connection:
                result = handler(connection, *(str(arg) for arg in args))
        finally:
            connection.close()
    except Exception as error:
        raise RuntimeError(f"SQLite bridge failed for {command}: {error}") from error
    if result is None:
        return None
    return json.loads(json.dumps(result, ensure_ascii=False))
