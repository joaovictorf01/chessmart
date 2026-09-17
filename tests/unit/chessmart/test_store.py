# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""O acesso ao banco: sorteio com filtros, gravação de tentativa e rating.

Um banco de puzzles pequeno é criado num diretório temporário com o mesmo
schema que `tools/build_puzzles.py` gera; o histórico vai para outro arquivo
no mesmo lugar, para nunca tocar o do usuário.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from chessmart.tactic import glicko2
from chessmart.tactic.models import AttemptResult, AttemptStats, PuzzleFilters, RatingSummary
from chessmart.tactic.repository import PuzzleRepository

PUZZLES_SCHEMA = """
CREATE TABLE puzzles (
  id TEXT PRIMARY KEY,
  fen TEXT NOT NULL,
  moves TEXT NOT NULL,
  rating INTEGER,
  rating_deviation INTEGER,
  popularity INTEGER,
  nb_plays INTEGER,
  themes TEXT NOT NULL DEFAULT '',
  game_url TEXT NOT NULL DEFAULT '',
  opening_tags TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_puzzles_rating ON puzzles(rating);
"""

# (id, rating, popularity, temas). O FEN e os lances são os mesmos em todos:
# o que está em teste é o filtro, não o xadrez.
PUZZLES = [
	("easy1", 800, 90, "mateIn1 short"),
	("easy2", 1000, 80, "fork short hangingPiece"),
	("mid1", 1300, 60, "pin middlegame short"),
	("mid2", 1500, 40, "fork long"),
	("hard1", 1900, 20, "sacrifice veryLong"),
	("hard2", 2300, 5, "zugzwang endgame"),
]


class StoreTestCase(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		cls.puzzles_path = Path(cls.tmp.name) / "puzzles.db"
		connection = sqlite3.connect(cls.puzzles_path)
		connection.executescript(PUZZLES_SCHEMA)
		connection.executemany(
			"INSERT INTO puzzles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
			[
				(
					puzzle_id,
					"8/8/8/8/8/8/8/8 w - - 0 1",
					"e2e4 e7e5 g1f3",
					rating,
					75,
					popularity,
					1000,
					themes,
					"",
					"",
				)
				for puzzle_id, rating, popularity, themes in PUZZLES
			],
		)
		connection.commit()
		connection.close()

	@classmethod
	def tearDownClass(cls):
		cls.tmp.cleanup()

	def setUp(self):
		# Histórico novo a cada teste: o rating começa do zero.
		self.history_dir = tempfile.TemporaryDirectory(dir=self.tmp.name)
		self.repository = PuzzleRepository(self.puzzles_path, Path(self.history_dir.name) / "tactic.db")

	def tearDown(self):
		self.history_dir.cleanup()


class TestPuzzles(StoreTestCase):
	def test_count_and_get(self):
		self.assertEqual(self.repository.count(), len(PUZZLES))
		puzzle = self.repository.get("mid1")
		self.assertEqual(puzzle.id, "mid1")
		self.assertEqual(puzzle.moves, ["e2e4", "e7e5", "g1f3"])
		self.assertEqual(puzzle.themes, ["pin", "middlegame", "short"])
		self.assertIsNone(self.repository.get("nope"))

	def test_random_respects_rating_and_popularity(self):
		filters = PuzzleFilters(min_rating=1200, max_rating=1600, min_popularity=50)
		for _ in range(20):
			puzzle = self.repository.random_puzzle(filters)
			self.assertEqual(puzzle.id, "mid1")

	def test_theme_filter_is_an_or_and_matches_whole_words(self):
		ids = {self.repository.random_puzzle(PuzzleFilters(theme_slugs=("fork",))).id for _ in range(40)}
		self.assertEqual(ids, {"easy2", "mid2"})
		# "long" não pode casar com "veryLong": o LIKE é por palavra inteira.
		ids = {self.repository.random_puzzle(PuzzleFilters(theme_slugs=("long",))).id for _ in range(20)}
		self.assertEqual(ids, {"mid2"})
		ids = {
			self.repository.random_puzzle(PuzzleFilters(theme_slugs=("zugzwang", "mateIn1"))).id
			for _ in range(40)
		}
		self.assertEqual(ids, {"easy1", "hard2"})

	def test_excluded_ids_and_empty_result(self):
		filters = PuzzleFilters(theme_slugs=("fork",), excluded_ids=("easy2",))
		for _ in range(10):
			self.assertEqual(self.repository.random_puzzle(filters).id, "mid2")
		self.assertIsNone(self.repository.random_puzzle(PuzzleFilters(min_rating=5000)))

	def test_adaptive_uses_the_player_rating_window(self):
		# Rating inicial 1500, desvio 350: janela de 1550 +- 700 alcança tudo
		# menos o extremo... aqui só o hard2 (2300) fica de fora da primeira
		# janela, mas a exclusão de ids força o alargamento até chegar nele.
		excluded = tuple(puzzle_id for puzzle_id, *_ in PUZZLES if puzzle_id != "hard2")
		puzzle = self.repository.adaptive_random_puzzle(PuzzleFilters(excluded_ids=excluded))
		self.assertEqual(puzzle.id, "hard2")

	def test_theme_counts(self):
		counts = dict(self.repository.theme_counts())
		self.assertEqual(counts["short"], 3)
		self.assertEqual(counts["fork"], 2)
		self.assertEqual(counts["zugzwang"], 1)


class TestHistory(StoreTestCase):
	def test_fresh_history_has_default_rating(self):
		summary = self.repository.rating()
		self.assertIsInstance(summary, RatingSummary)
		self.assertEqual(summary.rating, 1500)
		self.assertEqual(summary.rated_attempts, 0)
		self.assertTrue(summary.provisional)
		self.assertEqual(self.repository.attempt_stats(), AttemptStats())

	def test_solving_raises_and_failing_lowers_the_rating(self):
		win = self.repository.record_attempt("hard1", solved=True, mistakes=0, hints_used=0, elapsed_ms=1200)
		self.assertIsInstance(win, AttemptResult)
		self.assertEqual(win.rating_before, 1500)
		self.assertGreater(win.rating_delta, 0)
		loss = self.repository.record_attempt("easy1", solved=False, mistakes=1, hints_used=2, elapsed_ms=800)
		self.assertEqual(loss.rating_before, win.rating)
		self.assertLess(loss.rating_delta, 0)
		summary = self.repository.rating()
		self.assertEqual(summary.rating, loss.rating)
		self.assertEqual(summary.rated_attempts, 2)
		self.assertEqual(
			self.repository.attempt_stats(), AttemptStats(total=2, solved=1, mistakes=1, hints_used=2)
		)

	def test_unknown_puzzle_is_logged_but_not_rated(self):
		result = self.repository.record_attempt("ghost", solved=True, mistakes=0, hints_used=0, elapsed_ms=10)
		self.assertEqual(result.rating_delta, 0)
		self.assertEqual(self.repository.rating().rated_attempts, 0)
		self.assertEqual(self.repository.attempt_stats().total, 1)


class TestGlicko2(unittest.TestCase):
	def test_expected_score_is_half_against_an_equal_puzzle(self):
		player = glicko2.Rating(rating=1500, deviation=50)
		self.assertAlmostEqual(glicko2.expected_score(player, 1500, 50), 0.5, places=6)
		self.assertGreater(glicko2.expected_score(player, 1200, 50), 0.8)
		self.assertLess(glicko2.expected_score(player, 1800, 50), 0.2)

	def test_update_moves_toward_the_result_and_shrinks_deviation(self):
		player = glicko2.Rating()
		after = glicko2.update(player, 1500, 75, solved=True)
		self.assertGreater(after.rating, player.rating)
		self.assertLess(after.deviation, player.deviation)
		after_loss = glicko2.update(player, 1500, 75, solved=False)
		self.assertLess(after_loss.rating, player.rating)

	def test_upset_moves_more_than_expected_result(self):
		player = glicko2.Rating(rating=1500, deviation=60)
		expected_win = glicko2.update(player, 1200, 75, solved=True).rating - 1500
		upset_win = glicko2.update(player, 1900, 75, solved=True).rating - 1500
		self.assertGreater(upset_win, expected_win)

	def test_decay_only_widens_the_deviation_up_to_the_default(self):
		player = glicko2.Rating(rating=1700, deviation=60)
		decayed = glicko2.decay(player, periods=5)
		self.assertEqual(decayed.rating, 1700)
		self.assertGreater(decayed.deviation, 60)
		self.assertLessEqual(glicko2.decay(player, periods=10_000).deviation, glicko2.DEFAULT_DEVIATION)
		self.assertEqual(glicko2.decay(player, periods=0), player)

	def test_confidence_interval_and_rounding(self):
		player = glicko2.Rating(rating=1499.6, deviation=100)
		self.assertEqual(player.rounded(), 1500)
		self.assertEqual(player.confidence_interval(), (1300, 1700))
