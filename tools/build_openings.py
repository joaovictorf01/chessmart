# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Builds the add-on's table of opening names from lichess-org/chess-openings.

Usage: py -3 tools/build_openings.py <folder with a.tsv ... e.tsv> [commit]

The source (CC0) lists each opening as ECO code, name and moves. The add-on
looks openings up by position, so this replays every line once, here, and
writes `openings/openings.tsv` with ECO, name and the EPD of the final
position; the add-on then needs no move parsing at load time. A position
reached by several move orders keeps the first name the source gives it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon" / "globalPlugins" / "chessmart" / "lib"))

import chess  # noqa: E402

OUTPUT = ROOT / "addon" / "globalPlugins" / "chessmart" / "openings" / "openings.tsv"


def build(source: Path, commit: str) -> int:
	seen: dict[str, tuple[str, str]] = {}
	for part in "abcde":
		lines = (source / f"{part}.tsv").read_text(encoding="utf-8").splitlines()
		for line in lines[1:]:
			if not line.strip():
				continue
			eco, name, pgn = line.split("\t")
			board = chess.Board()
			for token in pgn.split():
				if token.endswith("."):
					continue
				board.push_san(token)
			seen.setdefault(board.epd(), (eco, name))
	OUTPUT.parent.mkdir(parents=True, exist_ok=True)
	with OUTPUT.open("w", encoding="utf-8", newline="\n") as out:
		out.write(f"# lichess-org/chess-openings {commit} (CC0). Built by tools/build_openings.py.\n")
		out.write("eco\tname\tepd\n")
		for epd, (eco, name) in sorted(seen.items(), key=lambda item: (item[1][0], item[1][1])):
			out.write(f"{eco}\t{name}\t{epd}\n")
	return len(seen)


if __name__ == "__main__":
	count = build(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "unknown")
	print(f"{OUTPUT}: {count} positions")
