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
DEFAULT_DB_CANDIDATES = tuple(
    candidate
    for candidate in (
        os.environ.get("CHESSMART_TACTIC_DB_PATH"),
        str(ADDON_DATA_DIRECTORY / "tactic.db"),
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


def resolve_default_db_path() -> Path | None:
    for candidate in DEFAULT_DB_CANDIDATES:
        db_path = Path(candidate)
        if db_path.is_file():
            return db_path
    return None


def run_bridge(db_path: Path, command: str, *args: object):
    """Executa um comando do `sqlite_bridge` no próprio processo.

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
        connection = sqlite_bridge.connect(Path(db_path))
        try:
            # O `with` só cuida do commit/rollback; fechar é por nossa conta —
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
