# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Opening names, as Lichess gives them: ECO code and name, looked up by position.

The table is lichess-org/chess-openings (CC0; see COPYING.txt here), rebuilt by
`tools/build_openings.py`. Lookup is by position, not by move order, so a
transposition finds its name too. The file is read once, on first use.
"""

import dataclasses
import functools
import typing as t
from pathlib import Path

from ..paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


TABLE_PATH = Path(__file__).resolve().parent / "openings.tsv"


@dataclasses.dataclass(frozen=True)
class Opening:
	eco: str
	name: str


@functools.lru_cache(maxsize=1)
def _table(path: Path = TABLE_PATH) -> dict[str, Opening]:
	table = {}
	for line in path.read_text(encoding="utf-8").splitlines():
		if not line or line.startswith("#") or line.startswith("eco\t"):
			continue
		eco, name, epd = line.split("\t")
		table[epd] = Opening(eco=eco, name=name)
	return table


def lookup(board: "chess.Board") -> t.Optional[Opening]:
	"""The opening this exact position has a name for, or None."""
	return _table().get(board.epd())


def opening_of_line(node: "chess.pgn.GameNode") -> t.Optional[Opening]:
	"""The last named position on the way to `node`: the name the game is in, even after it leaves theory."""
	current: t.Optional["chess.pgn.GameNode"] = node
	while current is not None:
		opening = lookup(current.board())
		if opening is not None:
			return opening
		current = current.parent
	return None


def last_book_node(game: "chess.pgn.Game") -> t.Optional["chess.pgn.GameNode"]:
	"""The last node of the main line whose position is in the table: where the game left theory."""
	last = None
	for node in game.mainline():
		if lookup(node.board()) is not None:
			last = node
	return last
