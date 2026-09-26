# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""A position being set up by hand: pieces placed one by one, then checked and used.

Free of NVDA imports (the editor board speaks what this decides). Castling
rights follow the pieces: a right exists while its king and rook stand on
their starting squares, unless the user switched it off. The checks are
python-chess's own `Board.status()`, said in words.
"""

import typing as t

from .i18n import _
from .paths import import_bundled


with import_bundled():
	import chess


# The four castling rights: the rook's starting square names each one.
CASTLING_ROOKS = (chess.H1, chess.A1, chess.H8, chess.A8)


class PositionDraft:
	def __init__(self, fen: t.Optional[str] = None):
		self.board = chess.Board(None)
		# Rights the user switched off; the rest follow the pieces.
		self.castling_off: set[int] = set()
		if fen is not None:
			self.set_fen(fen)

	# -- editing -------------------------------------------------------------------

	def place(self, square: int, piece: "chess.Piece") -> None:
		self.board.set_piece_at(square, piece)
		self._refresh()

	def clear(self, square: int) -> t.Optional["chess.Piece"]:
		removed = self.board.remove_piece_at(square)
		self._refresh()
		return removed

	def clear_all(self) -> None:
		self.board.clear()
		self.castling_off.clear()

	def standard(self) -> None:
		self.board.reset()
		self.castling_off.clear()

	def set_turn(self, color: bool) -> None:
		self.board.turn = color
		self._refresh()

	def castling_available(self, rook_square: int) -> bool:
		"""Whether the pieces allow this right: king and rook on their starting squares."""
		return bool(self._possible_castling() & chess.BB_SQUARES[rook_square])

	def castling_on(self, rook_square: int) -> bool:
		return bool(self.board.castling_rights & chess.BB_SQUARES[rook_square])

	def toggle_castling(self, rook_square: int) -> bool:
		"""Switches a right off or back on; returns the new state (always False when the pieces forbid it)."""
		if rook_square in self.castling_off:
			self.castling_off.discard(rook_square)
		else:
			self.castling_off.add(rook_square)
		self._refresh()
		return self.castling_on(rook_square)

	def _possible_castling(self) -> int:
		probe = self.board.copy(stack=False)
		probe.castling_rights = chess.BB_A1 | chess.BB_H1 | chess.BB_A8 | chess.BB_H8
		return probe.clean_castling_rights()

	def _refresh(self) -> None:
		rights = self._possible_castling()
		for square in self.castling_off:
			rights &= ~chess.BB_SQUARES[square]
		self.board.castling_rights = rights
		# An en passant square from a pasted FEN stays only while it is still legal.
		if self.board.ep_square is not None and not self.board.has_legal_en_passant():
			self.board.ep_square = None

	# -- FEN -------------------------------------------------------------------------

	def fen(self) -> str:
		return self.board.fen()

	def set_fen(self, fen: str) -> None:
		"""Loads a FEN; ValueError when it is not one. Castling rights come from the FEN."""
		board = chess.Board(fen.strip())
		self.board = board
		self.castling_off = {
			square for square in CASTLING_ROOKS if not board.castling_rights & chess.BB_SQUARES[square]
		}
		self._refresh()

	# -- checking --------------------------------------------------------------------

	def is_valid(self) -> bool:
		return self.board.is_valid()

	def problems(self) -> list[str]:
		"""What is wrong with the position, one sentence each; empty when it can be played."""
		status = self.board.status()
		return [text for flag, text in _status_sentences() if status & flag]


def _status_sentences() -> list[tuple["chess.Status", str]]:
	return [
		# Translators: Position editor check: no white king on the board.
		(chess.STATUS_NO_WHITE_KING, _("There is no white king.")),
		# Translators: Position editor check: no black king on the board.
		(chess.STATUS_NO_BLACK_KING, _("There is no black king.")),
		# Translators: Position editor check: more than one king of a colour.
		(chess.STATUS_TOO_MANY_KINGS, _("There is more than one king of the same colour.")),
		# Translators: Position editor check.
		(chess.STATUS_TOO_MANY_WHITE_PAWNS, _("White has more than eight pawns.")),
		# Translators: Position editor check.
		(chess.STATUS_TOO_MANY_BLACK_PAWNS, _("Black has more than eight pawns.")),
		# Translators: Position editor check: a pawn on the first or eighth rank.
		(chess.STATUS_PAWNS_ON_BACKRANK, _("A pawn stands on the first or the eighth rank.")),
		# Translators: Position editor check.
		(chess.STATUS_TOO_MANY_WHITE_PIECES, _("White has more than sixteen pieces.")),
		# Translators: Position editor check.
		(chess.STATUS_TOO_MANY_BLACK_PIECES, _("Black has more than sixteen pieces.")),
		# Translators: Position editor check: castling rights that the pieces do not allow.
		(chess.STATUS_BAD_CASTLING_RIGHTS, _("A castling right does not match the kings and rooks.")),
		# Translators: Position editor check: the en passant square is not possible.
		(chess.STATUS_INVALID_EP_SQUARE, _("The en passant square is not possible.")),
		# Translators: Position editor check: the side not to move is in check.
		(chess.STATUS_OPPOSITE_CHECK, _("The side that is not to move is in check.")),
		# Translators: Position editor check: the board has no pieces.
		(chess.STATUS_EMPTY, _("The board is empty.")),
		# Translators: Position editor check: a check no legal move could have given.
		(chess.STATUS_TOO_MANY_CHECKERS, _("The king is in check from more pieces than a move can give.")),
		# Translators: Position editor check: a check that no legal move could have given.
		(chess.STATUS_IMPOSSIBLE_CHECK, _("The check on the king could not have come from a legal move.")),
	]


def spoken_piece(piece: "chess.Piece") -> str:
	"""`white king`, `black knight`: how a placed piece is announced.

	Twelve whole names, not a colour glued to a piece: in Portuguese the
	colour agrees with the piece (rei branco, dama branca).
	"""
	return {
		# Translators: Piece name in the position editor.
		(chess.KING, chess.WHITE): _("white king"),
		# Translators: Piece name in the position editor.
		(chess.QUEEN, chess.WHITE): _("white queen"),
		# Translators: Piece name in the position editor.
		(chess.ROOK, chess.WHITE): _("white rook"),
		# Translators: Piece name in the position editor.
		(chess.BISHOP, chess.WHITE): _("white bishop"),
		# Translators: Piece name in the position editor.
		(chess.KNIGHT, chess.WHITE): _("white knight"),
		# Translators: Piece name in the position editor.
		(chess.PAWN, chess.WHITE): _("white pawn"),
		# Translators: Piece name in the position editor.
		(chess.KING, chess.BLACK): _("black king"),
		# Translators: Piece name in the position editor.
		(chess.QUEEN, chess.BLACK): _("black queen"),
		# Translators: Piece name in the position editor.
		(chess.ROOK, chess.BLACK): _("black rook"),
		# Translators: Piece name in the position editor.
		(chess.BISHOP, chess.BLACK): _("black bishop"),
		# Translators: Piece name in the position editor.
		(chess.KNIGHT, chess.BLACK): _("black knight"),
		# Translators: Piece name in the position editor.
		(chess.PAWN, chess.BLACK): _("black pawn"),
	}[(piece.piece_type, piece.color)]
