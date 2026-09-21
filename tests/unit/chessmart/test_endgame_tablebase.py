# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Tabelas Syzygy: manifesto, o que está instalado, e o juiz sobre tabelas de 3 peças."""

import sys
import tempfile
import unittest
from pathlib import Path

from chessmart.endgame import judge, tablebase
from chessmart.paths import LIB_DIRECTORY

if LIB_DIRECTORY not in sys.path:
	sys.path.append(LIB_DIRECTORY)
import chess  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "syzygy"


class TestManifest(unittest.TestCase):
	def test_manifest_lists_the_whole_3_4_5_set(self):
		files = tablebase.load_manifest()
		self.assertEqual(len(files), 290)
		self.assertEqual({f.kind for f in files}, {"wdl", "dtz"})
		self.assertEqual({f.pieces for f in files}, {3, 4, 5})
		self.assertTrue(
			all(len(f.sha256) == 64 and f.bytes > 0 and f.url.startswith("https://") for f in files),
		)

	def test_table_sets_are_nested(self):
		small, full = tablebase.table_sets()
		self.assertEqual((small.max_pieces, full.max_pieces), (4, 5))
		self.assertLess(small.total_bytes, 10_000_000)
		self.assertGreater(full.total_bytes, 900_000_000)
		self.assertTrue(set(small.files) <= set(full.files))


class TestInstalled(unittest.TestCase):
	def test_fixture_tables_count_as_installed_by_size(self):
		files = [f for f in tablebase.load_manifest() if f.file.startswith(("KPvK.", "KQvK.", "KRvK."))]
		self.assertEqual(len(files), 6)
		self.assertEqual(tablebase.missing_files(files, FIXTURES), ())
		self.assertEqual(tablebase.installed_piece_limit(files, FIXTURES), 3)

	def test_missing_and_limit_with_an_empty_directory(self):
		files = tablebase.load_manifest()
		with tempfile.TemporaryDirectory() as directory:
			self.assertEqual(len(tablebase.missing_files(files, Path(directory))), 290)
			self.assertEqual(tablebase.installed_piece_limit(files, Path(directory)), 0)
			self.assertIsNone(tablebase.open_tablebase(Path(directory)))


class TestJudge(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tb = tablebase.open_tablebase(FIXTURES)

	@classmethod
	def tearDownClass(cls):
		cls.tb.close()

	def test_capablanca_queen_position_is_won_for_white(self):
		verdict = judge.probe(self.tb, chess.Board("8/8/8/4k3/8/8/8/4K2Q w - - 0 1"))
		self.assertEqual(verdict.result, judge.WIN)
		self.assertGreater(verdict.moves, 0)

	def test_pawn_positions_match_what_the_engine_said(self):
		won = ["4k3/8/4K3/4P3/8/8/8/8 w - - 0 1", "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1"]
		drawn = ["8/8/8/4k3/8/8/4P3/4K3 w - - 0 1", "8/8/8/8/8/3k4/3P4/3K4 w - - 0 1"]
		for fen in won:
			self.assertEqual(judge.probe(self.tb, chess.Board(fen)).result, judge.WIN, fen)
		for fen in drawn:
			self.assertEqual(judge.probe(self.tb, chess.Board(fen)).result, judge.DRAW, fen)

	def test_verdict_is_seen_from_the_other_side_when_black_moves(self):
		# Rei na sexta na frente do peão: ganho das Brancas mesmo com as Pretas a jogar.
		board = chess.Board("4k3/8/4K3/4P3/8/8/8/8 b - - 0 1")
		verdict = judge.probe(self.tb, board)
		self.assertEqual(verdict.result, judge.LOSS)
		self.assertEqual(verdict.for_color(chess.WHITE, board.turn).result, judge.WIN)

	def test_judge_flags_the_move_that_lets_the_win_slip(self):
		# Ke3, Pe2, ke6, Brancas jogam: ganho. 1.e4?? deixa escapar; 1.Kd4 mantém.
		board = chess.Board("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
		bad = judge.judge_move(self.tb, board, chess.Move.from_uci("e2e4"))
		good = judge.judge_move(self.tb, board, chess.Move.from_uci("e3d4"))
		self.assertEqual((bad.before.result, bad.after.result), (judge.WIN, judge.DRAW))
		self.assertTrue(bad.spoiled)
		self.assertIn("draw", judge.describe_spoiled(bad))
		self.assertFalse(good.spoiled)
		self.assertIsNone(judge.describe_spoiled(good))

	def test_best_moves_keep_the_win(self):
		board = chess.Board("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
		best = judge.best_moves(self.tb, board)
		self.assertTrue(best)
		for move in best:
			self.assertFalse(judge.judge_move(self.tb, board, move).spoiled, board.san(move))
		self.assertNotIn(chess.Move.from_uci("e2e4"), best)

	def test_no_table_means_no_verdict(self):
		# Dois cavalos contra rei: fora das tabelas de 3 peças do repositório.
		self.assertIsNone(judge.probe(self.tb, chess.Board("8/8/8/4k3/8/8/8/1NN1K3 w - - 0 1")))
		self.assertIsNone(judge.probe(self.tb, chess.Board()))
		self.assertEqual(judge.rate_moves(self.tb, chess.Board()), ())

	def test_stalemate_and_mate_are_probed_as_draw_and_loss(self):
		self.assertEqual(
			judge.probe(self.tb, chess.Board("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")).result,
			judge.DRAW,
		)
		self.assertEqual(
			judge.probe(self.tb, chess.Board("k7/1Q6/2K5/8/8/8/8/8 b - - 0 1")).result,
			judge.LOSS,
		)

	def test_describe_verdict_texts(self):
		self.assertEqual(
			judge.describe_verdict(judge.Verdict(2, 13), "white"),
			"white wins: 7 moves to the next pawn move, capture or mate.",
		)
		self.assertEqual(judge.describe_verdict(judge.Verdict(0, 0), "white"), "Draw.")
		self.assertEqual(
			judge.describe_verdict(judge.Verdict(-2, -4), "black"),
			"black loses: 2 moves of resistance at most.",
		)
