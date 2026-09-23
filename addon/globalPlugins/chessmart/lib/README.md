# Bundled libraries

Loaded through `paths.import_bundled`. Never edited here; replaced whole when updated.

| Folder | What | Version and source | Why it is bundled |
|---|---|---|---|
| `chess/` | python-chess: boards, moves, PGN, UCI engines, Syzygy | 1.7.0, pypi.org/project/chess (GPL v3) | NVDA ships no chess library |
| `chess_clock/` | The game clock | 0.1.0, by Musharraf Omer, written for this add-on | Small, not on PyPI |
| `sqlite3_runtime/` | `sqlite3` for NVDA's Python | CPython 3.13.13, Windows x64; see its README | NVDA's Python does not include `sqlite3`; must match NVDA's Python series |
