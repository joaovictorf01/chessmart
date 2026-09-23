# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Squares, neighbours and material: what the arrow keys and M rely on.

Moved out of the board (architecture review, finding 15) so they can be tested
without NVDA. Squares are python-chess indexes: a1 is 0, h1 is 7, a8 is 56.
"""

import dataclasses
import typing as t

from .paths import import_bundled


with import_bundled():
	import chess


# Pawn units, the usual count. Bishop and knight are worth the same on purpose:
# counting them together avoids getting lost when one was traded for the other.
MATERIAL_VALUES = {
	chess.QUEEN: 9,
	chess.ROOK: 5,
	chess.BISHOP: 3,
	chess.KNIGHT: 3,
	chess.PAWN: 1,
}

LEFT, RIGHT, UP, DOWN = "left", "right", "up", "down"


def square_color(square: int) -> bool:
	"""chess.WHITE for a light square, chess.BLACK for a dark one (a1 is dark)."""
	return chess.WHITE if (chess.square_file(square) % 2) != (chess.square_rank(square) % 2) else chess.BLACK


def neighbour(square: int, direction: str) -> t.Optional[int]:
	"""The square next to `square`, from White's side of the board; None at the edge.

	Left and right stay on the rank; up is towards the eighth rank.
	"""
	file, rank = chess.square_file(square), chess.square_rank(square)
	if direction == LEFT:
		return square - 1 if file > 0 else None
	if direction == RIGHT:
		return square + 1 if file < 7 else None
	if direction == UP:
		return square + 8 if rank < 7 else None
	if direction == DOWN:
		return square - 8 if rank > 0 else None
	raise ValueError(f"unknown direction: {direction}")


@dataclasses.dataclass(frozen=True)
class MaterialCount:
	"""What M says, from `me`'s side: the pieces of each kind, the balance and the bishop pair."""

	queens: tuple[int, int]
	rooks: tuple[int, int]
	minor_pieces: tuple[int, int]
	pawns: tuple[int, int]
	# In pawn units; positive when `me` is up.
	balance: int
	# Who alone has both bishops: True for `me`, False for the opponent, None for neither or both.
	bishop_pair: t.Optional[bool]


def count_material(board: "chess.Board", me: bool) -> MaterialCount:
	them = not me

	def count(piece_type, color):
		return len(board.pieces(piece_type, color))

	balance = sum(
		value * (count(piece_type, me) - count(piece_type, them))
		for piece_type, value in MATERIAL_VALUES.items()
	)
	my_bishops, their_bishops = count(chess.BISHOP, me), count(chess.BISHOP, them)
	bishop_pair = None
	if my_bishops == 2 and their_bishops < 2:
		bishop_pair = True
	elif their_bishops == 2 and my_bishops < 2:
		bishop_pair = False
	return MaterialCount(
		queens=(count(chess.QUEEN, me), count(chess.QUEEN, them)),
		rooks=(count(chess.ROOK, me), count(chess.ROOK, them)),
		minor_pieces=(
			count(chess.BISHOP, me) + count(chess.KNIGHT, me),
			count(chess.BISHOP, them) + count(chess.KNIGHT, them),
		),
		pawns=(count(chess.PAWN, me), count(chess.PAWN, them)),
		balance=balance,
		bishop_pair=bishop_pair,
	)
