# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Finais contra a engine: posições, sorteio e o anúncio do resultado."""

import random
import sys
import unittest

from chessmart.endgame import drills as endgame_drill
from chessmart.paths import LIB_DIRECTORY

if LIB_DIRECTORY not in sys.path:
	sys.path.append(LIB_DIRECTORY)
import chess  # noqa: E402


class TestDrillCatalog(unittest.TestCase):
	def test_examples_are_legal_and_won_for_white_to_move(self):
		for drill in endgame_drill.ENDGAME_DRILLS:
			for fen in drill.example_fens:
				board = chess.Board(fen)
				self.assertTrue(endgame_drill.is_playable_drill_position(board), fen)

	def test_capablanca_examples_open_each_drill(self):
		queen = endgame_drill.get_endgame_drill("queenVsKing")
		self.assertEqual(endgame_drill.opening_fen(queen), "8/8/8/4k3/8/8/8/4K2Q w - - 0 1")
		rook = endgame_drill.get_endgame_drill("rookVsKing")
		self.assertEqual(endgame_drill.opening_fen(rook), "7k/8/8/8/8/8/8/R6K w - - 0 1")

	def test_unknown_id_falls_back_to_the_first_drill(self):
		self.assertEqual(
			endgame_drill.get_endgame_drill("nope").drill_id,
			endgame_drill.DEFAULT_ENDGAME_DRILL_ID,
		)
		self.assertEqual(
			endgame_drill.get_endgame_drill(None).drill_id,
			endgame_drill.DEFAULT_ENDGAME_DRILL_ID,
		)


class TestRandomPositions(unittest.TestCase):
	def test_random_queen_positions_are_playable_and_have_the_right_pieces(self):
		drill = endgame_drill.get_endgame_drill("queenVsKing")
		rng = random.Random(7)
		for _ in range(200):
			board = chess.Board(endgame_drill.random_fen(drill, rng))
			self.assertTrue(endgame_drill.is_playable_drill_position(board), board.fen())
			self.assertEqual(sorted(str(p) for p in board.piece_map().values()), ["K", "Q", "k"])

	def test_random_rook_positions_vary(self):
		drill = endgame_drill.get_endgame_drill("rookVsKing")
		rng = random.Random(3)
		fens = {endgame_drill.random_fen(drill, rng) for _ in range(20)}
		self.assertGreater(len(fens), 1)

	def test_pawn_drill_draws_from_the_checked_examples(self):
		drill = endgame_drill.get_endgame_drill("pawnVsKing")
		rng = random.Random(1)
		for _ in range(20):
			self.assertIn(endgame_drill.random_fen(drill, rng), drill.example_fens)

	def test_hanging_piece_is_rejected(self):
		# Rei preto em e5 ataca a torre de d4 pela diagonal, e o rei branco em h1 não a defende.
		# (Com a dama isso não acontece: rei ao lado da dama está em xeque, e a posição é ilegal.)
		board = chess.Board("8/8/8/4k3/3R4/8/8/7K w - - 0 1")
		self.assertFalse(endgame_drill.is_playable_drill_position(board))
		# Com o rei branco em c3 a torre está defendida: o rei preto não pode tomar.
		board = chess.Board("8/8/8/4k3/3R4/2K5/8/8 w - - 0 1")
		self.assertTrue(endgame_drill.is_playable_drill_position(board))

	def test_positions_already_over_are_rejected(self):
		# Afogado antes de começar: rei preto em a8, dama em b6, rei branco em c7 -- e Pretas a jogar.
		board = chess.Board("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")
		self.assertFalse(endgame_drill.is_playable_drill_position(board))


class TestResultMessages(unittest.TestCase):
	def _mate_board(self):
		# Mate do exemplo 4 do Capablanca, 8 lances das Brancas.
		board = chess.Board("8/8/8/4k3/8/8/8/4K2Q w - - 0 1")
		for san in "Qc6 Kd4 Kd2 Ke5 Ke3 Kf5 Qd6 Kg4 Qe6+ Kh4 Qg6 Kh3 Kf3 Kh2 Qg2#".split():
			board.push_san(san)
		return board

	def test_checkmate_within_target(self):
		drill = endgame_drill.get_endgame_drill("queenVsKing")
		board = self._mate_board()
		self.assertTrue(board.is_checkmate())
		messages = endgame_drill.drill_result_messages(drill, board, seconds_left=41.7)
		self.assertEqual(
			messages,
			[
				"Checkmate in 8 moves.",
				"Within the target of under 10 moves.",
				"41 seconds left on the clock.",
			],
		)

	def test_checkmate_over_target_names_the_target(self):
		drill = endgame_drill.get_endgame_drill("queenVsKing")
		board = self._mate_board()
		# O mesmo mate, mas com 13 lances na pilha.
		messages = endgame_drill.drill_result_messages(drill, _LongerBoard(board, 13), None)
		self.assertEqual(messages, ["Checkmate in 13 moves.", "The target was under 10 moves."])

	def test_stalemate_is_named(self):
		drill = endgame_drill.get_endgame_drill("queenVsKing")
		board = chess.Board("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")
		self.assertTrue(board.is_stalemate())
		messages = endgame_drill.drill_result_messages(drill, board, None)
		self.assertEqual(
			messages,
			["Stalemate: the black king had no legal move and was not in check. Draw."],
		)

	def test_pawn_drill_has_no_target(self):
		drill = endgame_drill.get_endgame_drill("pawnVsKing")
		board = self._mate_board()
		self.assertEqual(endgame_drill.drill_result_messages(drill, board, None), ["Checkmate in 8 moves."])

	def test_game_not_over_says_nothing(self):
		drill = endgame_drill.get_endgame_drill("queenVsKing")
		self.assertEqual(endgame_drill.drill_result_messages(drill, chess.Board(), 10), [])


class _LongerBoard:
	"""Um tabuleiro terminado com mais lances na pilha do que o de verdade."""

	def __init__(self, board, white_moves):
		self._board = board
		self.move_stack = [None] * (2 * white_moves - 1)

	def outcome(self):
		return self._board.outcome()


class TestMinorPieceDrills(unittest.TestCase):
	def test_random_two_bishop_positions_have_bishops_on_both_colours(self):
		drill = endgame_drill.get_endgame_drill("twoBishopsVsKing")
		rng = random.Random(7)
		for _ in range(30):
			board = chess.Board(endgame_drill.random_fen(drill, rng))
			self.assertTrue(endgame_drill.is_playable_drill_position(board), board.fen())
			bishops = board.pieces(chess.BISHOP, chess.WHITE)
			self.assertEqual(len(bishops), 2)
			self.assertEqual(
				len({(chess.square_file(s) + chess.square_rank(s)) % 2 for s in bishops}),
				2,
				board.fen(),
			)

	def test_same_colour_bishops_are_rejected(self):
		board = chess.Board("8/8/8/4k3/8/8/8/B1B1K3 w - - 0 1")
		self.assertFalse(endgame_drill.is_playable_drill_position(board))

	def test_random_bishop_knight_positions_are_playable(self):
		drill = endgame_drill.get_endgame_drill("bishopKnightVsKing")
		rng = random.Random(11)
		for _ in range(30):
			board = chess.Board(endgame_drill.random_fen(drill, rng))
			self.assertTrue(endgame_drill.is_playable_drill_position(board), board.fen())
			self.assertEqual(len(board.pieces(chess.BISHOP, chess.WHITE)), 1)
			self.assertEqual(len(board.pieces(chess.KNIGHT, chess.WHITE)), 1)

	def test_random_two_rook_positions_are_playable(self):
		drill = endgame_drill.get_endgame_drill("twoRooksVsKing")
		rng = random.Random(3)
		for _ in range(30):
			board = chess.Board(endgame_drill.random_fen(drill, rng))
			self.assertTrue(endgame_drill.is_playable_drill_position(board), board.fen())
			self.assertEqual(len(board.pieces(chess.ROOK, chess.WHITE)), 2)

	def test_pawn_drill_without_judge_stays_on_the_examples(self):
		drill = endgame_drill.get_endgame_drill("pawnVsKing")
		rng = random.Random(1)
		for _ in range(10):
			self.assertIn(endgame_drill.random_fen(drill, rng), drill.example_fens)

	def test_pawn_drill_with_judge_draws_random_won_positions(self):
		drill = endgame_drill.get_endgame_drill("pawnVsKing")
		rng = random.Random(5)
		seen = set()
		for _ in range(20):
			fen = endgame_drill.random_fen(drill, rng, accept=lambda board: True)
			board = chess.Board(fen)
			self.assertTrue(endgame_drill.is_playable_drill_position(board), fen)
			self.assertEqual(len(board.pieces(chess.PAWN, chess.WHITE)), 1)
			seen.add(fen)
		self.assertGreater(len(seen), 5)
