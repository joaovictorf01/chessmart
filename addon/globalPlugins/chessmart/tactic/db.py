# coding: utf-8

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PLUGIN_DIRECTORY = Path(__file__).resolve().parents[1]
ADDON_DATA_DIRECTORY = PLUGIN_DIRECTORY / "data"
BRIDGE_SCRIPT = Path(__file__).with_name("sqlite_bridge.py")
DEFAULT_DB_CANDIDATES = tuple(
    candidate
    for candidate in (
        os.environ.get("CHESSMART_TACTIC_DB_PATH"),
        str(ADDON_DATA_DIRECTORY / "tactic.db"),
        r"C:\projetos\tactic\data\tactic.db",
    )
    if candidate
)


def resolve_default_db_path() -> Path | None:
    for candidate in DEFAULT_DB_CANDIDATES:
        db_path = Path(candidate)
        if db_path.is_file():
            return db_path
    return None


def run_bridge(db_path: Path, command: str, *args: object):
    completed = subprocess.run(
        [
            "py",
            "-3",
            str(BRIDGE_SCRIPT),
            str(db_path),
            command,
            *(str(arg) for arg in args),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"SQLite bridge failed for {command}: {stderr or 'unknown error'}"
        )
    payload = completed.stdout.strip()
    if not payload:
        return None
    return json.loads(payload)
