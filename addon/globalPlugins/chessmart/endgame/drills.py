# coding: utf-8
# pyright: basic

"""Finais elementares contra a engine: dama, torre, dois bispos, bispo e cavalo, e peão contra rei nu.

O que se treina aqui não é ver, é técnica: levar o rei adversário à borda,
subir o próprio rei e dar o mate sem afogar, num relógio curto. Cada final
tem as posições do Capablanca (*Chess Fundamentals*, capítulo 1) como
exemplo e, para dama e torre, posições sorteadas -- três peças no tabuleiro,
qualquer uma é ganha, e sortear evita decorar uma só. Rei e peão contra rei
usa posições fixas, conferidas como ganhas com as Brancas a jogar: aí nem
toda posição é ganha, e o treino é justamente saber por quê.

Sem NVDA neste módulo, de propósito: é o que os testes importam.
"""

from __future__ import annotations

import dataclasses
import random
import typing

from ..i18n import N_, _
from ..paths import import_bundled


with import_bundled():
	import chess


@dataclasses.dataclass(frozen=True)
class EndgameDrill:
	drill_id: str
	label: str
	description: str
	# Lances das Brancas em que o mate "deve" sair, segundo o Capablanca.
	# None quando a meta é só ganhar (rei e peão: primeiro coroar, depois o mate).
	target_moves: int | None
	# Posições de exemplo, com as Brancas a jogar. A primeira é a que abre.
	example_fens: tuple[str, ...]
	# Peças brancas além do rei, para sortear posições; vazio = só os exemplos.
	random_pieces: tuple[chess.PieceType, ...] = ()
	# Sorteio só com juiz: nem toda posição deste final é ganha (rei e peão),
	# então a sorteada precisa ser confirmada por quem chama (`accept`), e sem
	# juiz o treino fica nos exemplos.
	needs_judge: bool = False


# Os FENs dos exemplos batem com `livros/capablanca/capitulo-01-secao-1.md`.
ENDGAME_DRILLS = (
	EndgameDrill(
		drill_id="queenVsKing",
		# Translators: Name of the endgame drill with queen and king against king.
		label=N_("Queen and king against king"),
		# Translators: What to do in the queen against king drill.
		description=N_(
			"Checkmate in under 10 moves. The queen alone cannot mate: drive the king to the edge, bring your own king up, and mind the stalemate.",
		),
		target_moves=10,
		example_fens=("8/8/8/4k3/8/8/8/4K2Q w - - 0 1",),
		random_pieces=(chess.QUEEN,),
	),
	EndgameDrill(
		drill_id="rookVsKing",
		# Translators: Name of the endgame drill with rook and king against king.
		label=N_("Rook and king against king"),
		# Translators: What to do in the rook against king drill.
		description=N_(
			"Checkmate in under 20 moves. Keep your king on the same rank or file as the other king, next to the rook, and push the king to the edge.",
		),
		target_moves=20,
		example_fens=(
			"7k/8/8/8/8/8/8/R6K w - - 0 1",
			"8/8/8/4k3/8/8/8/4K2R w - - 0 1",
		),
		random_pieces=(chess.ROOK,),
	),
	EndgameDrill(
		drill_id="twoRooksVsKing",
		# Translators: Name of the endgame drill with two rooks and king against king.
		label=N_("Two rooks and king against king"),
		# Translators: What to do in the two rooks against king drill.
		description=N_(
			"Checkmate in under 10 moves. The ladder: one rook cuts the king off along a rank, the other checks on the next rank, and they take turns. When the king comes close to a rook, move that rook far away along its rank. Your king stays out of it.",
		),
		target_moves=10,
		example_fens=("8/8/8/4k3/8/8/8/R3K2R w - - 0 1",),
		random_pieces=(chess.ROOK, chess.ROOK),
	),
	EndgameDrill(
		drill_id="twoBishopsVsKing",
		# Translators: Name of the endgame drill with two bishops and king against king.
		label=N_("Two bishops and king against king"),
		# Translators: What to do in the two bishops against king drill.
		description=N_(
			"Checkmate in under 20 moves. The two bishops side by side make a wall: push the king to the edge, then into a corner, with your own king close behind. Mind the stalemate.",
		),
		target_moves=20,
		example_fens=("8/8/8/4k3/8/8/8/2B1KB2 w - - 0 1",),
		random_pieces=(chess.BISHOP, chess.BISHOP),
	),
	EndgameDrill(
		drill_id="bishopKnightVsKing",
		# Translators: Name of the endgame drill with bishop, knight and king against king.
		label=N_("Bishop, knight and king against king"),
		# Translators: What to do in the bishop and knight against king drill.
		description=N_(
			"Checkmate in under 35 moves. The mate only exists in a corner of the bishop's colour: drive the king to the edge, then along it to the right corner. Give yourself a longer clock.",
		),
		target_moves=35,
		example_fens=("8/8/8/4k3/8/8/8/2B1K1N1 w - - 0 1",),
		random_pieces=(chess.BISHOP, chess.KNIGHT),
	),
	EndgameDrill(
		drill_id="pawnVsKing",
		# Translators: Name of the endgame drill with king and pawn against king.
		label=N_("King and pawn against king"),
		# Translators: What to do in the king and pawn drill.
		description=N_(
			"Promote the pawn and checkmate. The king goes in front of the pawn and takes the opposition; the pawn moves last.",
		),
		target_moves=None,
		# Conferidas com o Stockfish 14 do add-on: todas com mate forçado
		# para as Brancas a jogar (11, 21, 34 e 63 lances, nesta ordem).
		example_fens=(
			"4k3/8/4K3/4P3/8/8/8/8 w - - 0 1",
			"8/8/8/2k5/8/3KP3/8/8 w - - 0 1",
			"8/4k3/8/8/8/8/4PK2/8 w - - 0 1",
			"8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
		),
		# Com a tablebase instalada, sorteia peão de qualquer coluna, inclusive
		# de torre, e só aceita posição ganha: o treino é reconhecer e converter.
		random_pieces=(chess.PAWN,),
		needs_judge=True,
	),
)

DEFAULT_ENDGAME_DRILL_ID = ENDGAME_DRILLS[0].drill_id
# Um minuto: o final de hoje se perdeu com 19 segundos e a técnica na cabeça
# leva menos que isso. O usuário muda no diálogo.
DEFAULT_DRILL_TIME_CONTROL = "1+0"


def get_endgame_drill(drill_id: str | None) -> EndgameDrill:
	for drill in ENDGAME_DRILLS:
		if drill.drill_id == drill_id:
			return drill
	return ENDGAME_DRILLS[0]


def drill_label(drill: EndgameDrill) -> str:
	return _(drill.label)


def drill_description(drill: EndgameDrill) -> str:
	return _(drill.description)


def opening_fen(drill: EndgameDrill) -> str:
	"""A posição que abre o treino: o primeiro exemplo do Capablanca."""
	return drill.example_fens[0]


def random_fen(
	drill: EndgameDrill,
	rng: random.Random | None = None,
	accept: "typing.Callable[[chess.Board], bool] | None" = None,
) -> str:
	"""Uma posição nova do mesmo final.

	Com peças para sortear, monta rei branco, rei preto e a peça em casas
	distintas e aceita a posição quando é legal com as Brancas a jogar, a
	peça não está de graça e o jogo não acabou antes de começar. Um final
	que `needs_judge` só sorteia com `accept` (a tablebase dizendo que a
	posição é ganha); sem isso, e sem peças para sortear, escolhe um exemplo.
	"""
	rng = rng or random.Random()
	if not drill.random_pieces or (drill.needs_judge and accept is None):
		return rng.choice(drill.example_fens)
	for _ in range(2000):
		board = _random_board(drill.random_pieces, rng)
		if is_playable_drill_position(board) and (accept is None or accept(board)):
			return board.fen()
	return rng.choice(drill.example_fens)


def _random_board(pieces: tuple[chess.PieceType, ...], rng: random.Random) -> chess.Board:
	squares = rng.sample(chess.SQUARES, 2 + len(pieces))
	board = chess.Board(None)
	board.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
	board.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
	for square, piece_type in zip(squares[2:], pieces):
		board.set_piece_at(square, chess.Piece(piece_type, chess.WHITE))
	board.turn = chess.WHITE
	return board


def is_playable_drill_position(board: chess.Board) -> bool:
	"""Legal, Brancas a jogar, nenhuma peça branca de graça, jogo em aberto."""
	if board.turn is not chess.WHITE or not board.is_valid() or board.is_game_over():
		return False
	# Dois bispos da mesma cor não dão mate: a posição sorteada tem que ter
	# um em casa clara e outro em casa escura.
	bishops = board.pieces(chess.BISHOP, chess.WHITE)
	if len(bishops) >= 2 and len({(chess.square_file(square) + chess.square_rank(square)) % 2 for square in bishops}) < 2:
		return False
	for square, piece in board.piece_map().items():
		if piece.color is chess.WHITE and piece.piece_type is not chess.KING:
			hanging = board.is_attacked_by(chess.BLACK, square) and not board.is_attacked_by(
				chess.WHITE,
				square,
			)
			if hanging:
				return False
	return True


def white_moves_played(board: chess.Board) -> int:
	"""Quantos lances as Brancas fizeram desde a posição inicial do treino."""
	return (len(board.move_stack) + 1) // 2


def drill_result_messages(drill: EndgameDrill, board: chess.Board, seconds_left: float | None) -> list[str]:
	"""O que dizer quando o treino termina, além do anúncio normal de fim de jogo.

	Mate: quantos lances levou e se coube na meta. Afogamento: o que é, porque
	é o erro deste final. Empate por outro motivo (repetição, 50 lances, só
	os reis): a partida não foi ganha. Tempo: quem anuncia é o relógio.
	"""
	outcome = board.outcome()
	if outcome is None:
		return []
	messages: list[str] = []
	moves = white_moves_played(board)
	if outcome.termination is chess.Termination.CHECKMATE and outcome.winner is chess.WHITE:
		# Translators: Spoken when the drill ends in checkmate; {moves} is a number.
		messages.append(_("Checkmate in {moves} moves.").format(moves=moves))
		if drill.target_moves is not None:
			if moves < drill.target_moves:
				# Translators: Spoken when the mate came within the drill's target.
				messages.append(
					_("Within the target of under {target} moves.").format(target=drill.target_moves)
				)
			else:
				# Translators: Spoken when the mate took longer than the drill's target.
				messages.append(_("The target was under {target} moves.").format(target=drill.target_moves))
	elif outcome.termination is chess.Termination.STALEMATE:
		messages.append(
			# Translators: Spoken when the drill ends in stalemate.
			_("Stalemate: the black king had no legal move and was not in check. Draw."),
		)
	elif outcome.winner is None:
		# Translators: Spoken when the drill ends in a draw that is not stalemate.
		messages.append(_("Draw. The position was won."))
	if seconds_left is not None:
		# Translators: Spoken at the end of a drill; {seconds} is a number.
		messages.append(_("{seconds} seconds left on the clock.").format(seconds=int(seconds_left)))
	return messages
