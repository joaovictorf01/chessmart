# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What is needed to say a move out loud, taken from the board before the move is played.

Free of NVDA imports (architecture: responsibilities of base.py); the board
turns `sound_name` into the sound it plays.
"""

import dataclasses

from .paths import import_bundled


with import_bundled():
	import chess


@dataclasses.dataclass(frozen=True)
class PlayedMove:
	"""Everything needed to describe a move out loud.

	Captured BEFORE the move is applied to the board, because afterwards the
	position has changed: the captured piece is gone, SAN can no longer be
	computed (disambiguating "Ngf3" depends on which pieces could reach the
	same square), and castling has already moved the rook.
	"""

	move: chess.Move
	mover: chess.Color
	moved_piece: chess.Piece | None
	captured_piece: chess.Piece | None
	is_castling: bool
	is_kingside_castling: bool
	is_en_passant: bool
	san: str

	@classmethod
	def capture(cls, board: chess.Board, move: chess.Move) -> "PlayedMove":
		is_castling = board.is_castling(move)
		is_en_passant = board.is_en_passant(move)
		if is_en_passant:
			# The captured pawn is not on the destination square: it stands beside
			# the capturing pawn, on the file it moves to and the rank it leaves.
			# (Always "one rank below" was right for White only.)
			captured = board.piece_at(
				chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
			)
		else:
			captured = board.piece_at(move.to_square)
		return cls(
			move=move,
			mover=board.turn,
			moved_piece=board.piece_at(move.from_square),
			captured_piece=captured,
			is_castling=is_castling,
			is_kingside_castling=is_castling and board.is_kingside_castling(move),
			is_en_passant=is_en_passant,
			san=board.san(move),
		)

	@property
	def is_capture(self) -> bool:
		return self.captured_piece is not None

	@property
	def sound_name(self) -> str:
		"""The name of the sound that announces the type of move (a `GameSound` value)."""
		if self.move.promotion is not None:
			return "promotion"
		if self.is_castling:
			return "castling"
		if self.move.drop:
			return "drop_move"
		if self.is_capture:
			return "en_passant" if self.is_en_passant else "capture"
		return "drop_piece"
