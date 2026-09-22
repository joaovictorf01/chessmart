# coding: utf-8
# pyright: basic


import abc
from .paths import import_bundled
from .i18n import _
from .ibca_notation import (
	IBCA_COLOR_NAMES,
	IBCA_FILE_MAP,
	IBCA_RANK_MAP,
	IBCA_PIECE_NAMES,
	IBCA_KING_SIDE_CASTLING,
	IBCA_QUEEN_SIDE_CASTLING,
)


with import_bundled():
	import chess


class GameAnnouncer(abc.ABC):
	@abc.abstractmethod
	def piece_name(self, piece_type: chess.PieceType) -> str:
		"""Return piece name given piece type."""

	@abc.abstractmethod
	def color_name(self, color: chess.Color) -> str:
		"""Return the name of the given color."""

	@abc.abstractmethod
	def square_name(self, square: chess.Square) -> str:
		"""Return the name of the given square index."""

	@abc.abstractmethod
	def square_file(self, square: chess.Square) -> str:
		"""Return the name of the file of the given square."""

	@abc.abstractmethod
	def square_rank(self, square: chess.Square) -> str:
		"""Return the rank of the file of the given square."""

	def describe_piece(self, piece: chess.Piece):
		"""Return the color and the name of the piece in a single string."""
		return f"{self.color_name(piece.color)} {self.piece_name(piece.piece_type)}"

	@abc.abstractmethod
	def normal_move(self, move: chess.Move, moved_piece: chess.Piece, move_maker: chess.Color) -> list:
		"""Return a list of strings to describe the given move."""

	@abc.abstractmethod
	def capture_move(self, move: chess.Move, moved_piece: chess.Piece, captured: chess.Piece) -> list:
		"""Return a list of strings to describe a capture move."""

	@abc.abstractmethod
	def castling_move(self, move_maker: chess.Color, is_king_side: bool) -> list:
		"""Return a list of strings to describe description a castling move."""

	@abc.abstractmethod
	def drop_move(self, move_maker: chess.Color, move: chess.Move):
		"""A drop move."""

	@abc.abstractmethod
	def promotion_move(self, move: chess.Move, move_maker: chess.Color) -> list:
		"""Return a list of string describing a promotion move."""


def spoken_piece_name(piece_type: chess.PieceType) -> str:
	"""The piece name in NVDA's language. Resolved on every call, like the rest."""
	return {
		# Translators: Name of the chess piece.
		chess.PAWN: _("pawn"),
		# Translators: Name of the chess piece.
		chess.KNIGHT: _("knight"),
		# Translators: Name of the chess piece.
		chess.BISHOP: _("bishop"),
		# Translators: Name of the chess piece.
		chess.ROOK: _("rook"),
		# Translators: Name of the chess piece.
		chess.QUEEN: _("queen"),
		# Translators: Name of the chess piece.
		chess.KING: _("king"),
	}[piece_type]


def spoken_color_name(color: chess.Color) -> str:
	# Translators: The side that plays the white pieces.
	# Translators: The side that plays the black pieces.
	return _("white") if color == chess.WHITE else _("black")


def spoken_termination_name(termination: chess.Termination) -> str:
	"""How the game ended, in NVDA's language; one entry per `chess.Termination` value."""
	return {
		# Translators: How a game ended, spoken at game over.
		chess.Termination.CHECKMATE: _("checkmate"),
		# Translators: How a game ended, spoken at game over.
		chess.Termination.STALEMATE: _("stalemate"),
		# Translators: How a game ended, spoken at game over.
		chess.Termination.INSUFFICIENT_MATERIAL: _("insufficient material"),
		# Translators: How a game ended, spoken at game over (the automatic 75-move rule).
		chess.Termination.SEVENTYFIVE_MOVES: _("seventy-five move rule"),
		# Translators: How a game ended, spoken at game over (the automatic fivefold repetition rule).
		chess.Termination.FIVEFOLD_REPETITION: _("fivefold repetition"),
		# Translators: How a game ended, spoken at game over.
		chess.Termination.FIFTY_MOVES: _("fifty-move rule"),
		# Translators: How a game ended, spoken at game over.
		chess.Termination.THREEFOLD_REPETITION: _("threefold repetition"),
		# Translators: How a game ended, spoken at game over (a win by the rules of a chess variant).
		chess.Termination.VARIANT_WIN: _("win by the rules of the variant"),
		# Translators: How a game ended, spoken at game over (a loss by the rules of a chess variant).
		chess.Termination.VARIANT_LOSS: _("loss by the rules of the variant"),
		# Translators: How a game ended, spoken at game over (a draw by the rules of a chess variant).
		chess.Termination.VARIANT_DRAW: _("draw by the rules of the variant"),
	}[termination]


class StandardGameAnnouncer(GameAnnouncer):
	def piece_name(self, piece_type: chess.PieceType) -> str:
		return spoken_piece_name(piece_type)

	def color_name(self, color: chess.Color) -> str:
		return spoken_color_name(color)

	def describe_piece(self, piece: chess.Piece):
		# Translators: A piece with its color, e.g. "white knight". Reorder the placeholders as your language needs.
		return _("{color} {piece}").format(
			color=self.color_name(piece.color),
			piece=self.piece_name(piece.piece_type),
		)

	def square_name(self, square: chess.Square) -> str:
		return chess.square_name(square)

	def square_file(self, square: chess.Square) -> str:
		return chess.FILE_NAMES[chess.square_file(square)]

	def square_rank(self, square: chess.Square) -> str:
		return chess.RANK_NAMES[chess.square_rank(square)]

	def normal_move(self, move: chess.Move, moved_piece: chess.Piece, move_maker: chess.Color) -> list:
		move_desc = [
			self.describe_piece(moved_piece),
			# Translators: Destination of a move, spoken after the piece, e.g. "to f3".
			_("to {square}").format(square=self.square_name(move.to_square)),
		]
		if (moved_piece.piece_type is not chess.PAWN) and (move.from_square != move.to_square):
			# Translators: Origin of a move, spoken after the piece, e.g. "from g1".
			move_desc.insert(1, _("from {square}").format(square=self.square_name(move.from_square)))
		return move_desc

	def capture_move(self, move: chess.Move, moved_piece: chess.Piece, captured: chess.Piece) -> list:
		return [
			self.describe_piece(moved_piece),
			# Translators: Origin of a capturing piece, e.g. "was at g1".
			_("was at {square}").format(square=self.square_name(move.from_square)),
			# Translators: Spoken between the capturing piece and the captured piece.
			_("captured"),
			self.describe_piece(captured),
			# Translators: Square where a capture happened, e.g. "at f3".
			_("at {square}").format(square=self.square_name(move.to_square)),
		]

	def castling_move(self, move_maker: chess.Color, is_king_side: bool) -> list:
		return [
			self.color_name(move_maker),
			# Translators: Spoken after the color that castled.
			_("castled"),
			# Translators: King-side castling.
			# Translators: Queen-side castling.
			_("king side") if is_king_side else _("queen side"),
		]

	def drop_move(self, move_maker, move):
		return (
			self.color_name(move_maker),
			# Translators: A piece dropped on the board (Crazyhouse), e.g. "dropped a knight".
			_("dropped a {piece}").format(piece=self.piece_name(move.drop or chess.PAWN)),
		)

	def promotion_move(self, move, move_maker):
		return [
			self.color_name(move_maker),
			# Translators: Pawn promotion, e.g. "promoted pawn at b7 to a queen at b8".
			_("promoted {pawn} at {origin} to a {piece} at {target}").format(
				pawn=self.piece_name(chess.PAWN),
				origin=self.square_name(move.from_square),
				piece=self.piece_name(move.promotion or chess.QUEEN),
				target=self.square_name(move.to_square),
			),
		]


class IBCAGameAnnouncer(GameAnnouncer):
	def piece_name(self, piece_type: chess.PieceType) -> str:
		return IBCA_PIECE_NAMES[piece_type]

	def color_name(self, color: chess.Color) -> str:
		return IBCA_COLOR_NAMES[color]

	def square_name(self, square: chess.Square) -> str:
		return "{file} {rank}".format(
			file=IBCA_FILE_MAP[chess.square_file(square)],
			rank=IBCA_RANK_MAP[chess.square_rank(square)],
		)

	def square_file(self, square: chess.Square) -> str:
		return IBCA_FILE_MAP[chess.square_file(square)]

	def square_rank(self, square: chess.Square) -> str:
		return IBCA_RANK_MAP[chess.square_rank(square)]

	def normal_move(self, move: chess.Move, moved_piece: chess.Piece, move_maker: chess.Color) -> list:
		return [self.describe_piece(moved_piece), self.square_name(move.to_square)]

	def capture_move(self, move: chess.Move, moved_piece: chess.Piece, captured: chess.Piece) -> list:
		return [
			self.describe_piece(moved_piece),
			_("captured"),
			self.describe_piece(captured),
			_("at {square}").format(square=self.square_name(move.to_square)),
		]

	def castling_move(self, move_maker: chess.Color, is_king_side: bool) -> list:
		return [
			self.color_name(move_maker),
			IBCA_KING_SIDE_CASTLING if is_king_side else IBCA_QUEEN_SIDE_CASTLING,
		]

	def drop_move(self, move_maker, move):
		return (
			self.color_name(move_maker),
			_("dropped a {piece}").format(piece=self.piece_name(move.drop or chess.PAWN)),
			_("at {square}").format(square=self.square_name(move.to_square)),
		)

	def promotion_move(self, move, move_maker):
		return [
			self.color_name(move_maker),
			_("promoted {pawn} at {origin} to a {piece} at {target}").format(
				pawn=self.piece_name(chess.PAWN),
				origin=self.square_name(move.from_square),
				piece=self.piece_name(move.promotion or chess.QUEEN),
				target=self.square_name(move.to_square),
			),
		]


standard_game_announcer = StandardGameAnnouncer()
ibca_game_announcer = IBCAGameAnnouncer()
