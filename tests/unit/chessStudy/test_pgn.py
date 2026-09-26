# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Reading games out of a PGN file (README, "Replay PGN File...").

PGN files are untrusted input: a game without headers, a result the file
does not know yet, or a Latin-1 file must still list and load.
"""

import tempfile
import unittest
from pathlib import Path

from chessStudy.pgn import PGNGame, PGNGameInfo

TWO_GAMES = """[Event "Club championship"]
[Site "Salvador BRA"]
[Date "2026.09.21"]
[Round "1"]
[White "Teles, Jeferson"]
[Black "Ferreira, Joao"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0

[Event "Casual game"]
[Site "?"]
[Date "2026.09.22"]
[White "Ferreira, Joao"]
[Black "Teles, Jeferson"]
[Result "*"]

1. d4 d5 *
"""

HEADERLESS = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6\n"


class PGNFileTest(unittest.TestCase):
	def setUp(self):
		self._dir = tempfile.TemporaryDirectory()
		self.addCleanup(self._dir.cleanup)
		self.dir = Path(self._dir.name)

	def write(self, name, text, encoding="utf-8"):
		path = self.dir / name
		path.write_bytes(text.encode(encoding))
		return str(path)

	def test_event_and_site_come_from_their_own_tags(self):
		path = self.write("games.pgn", TWO_GAMES)
		first, second = PGNGameInfo.game_info_from_pgn_filename(path)
		self.assertEqual(first.event, "Club championship")
		self.assertEqual(first.site, "Salvador BRA")
		self.assertEqual(first.date, "2026.09.21")
		self.assertEqual(first.white, "Teles, Jeferson")
		self.assertEqual(first.black, "Ferreira, Joao")
		self.assertEqual(first.result, "White won")
		self.assertEqual(second.event, "Casual game")
		self.assertEqual(second.site, "?")
		self.assertIn("Club championship", first.description)
		self.assertNotIn("2026.09.21, 2026.09.21", first.description)

	def test_a_star_result_is_an_unfinished_game(self):
		path = self.write("games.pgn", TWO_GAMES)
		_first, second = PGNGameInfo.game_info_from_pgn_filename(path)
		self.assertEqual(second.result, "Game not finished")
		game = PGNGame.from_game_info(second)
		self.assertEqual(len(game.moves), 2)

	def test_a_headerless_game_lists_and_loads(self):
		path = self.write("bare.pgn", HEADERLESS)
		games = list(PGNGameInfo.game_info_from_pgn_filename(path))
		self.assertEqual(len(games), 1)
		info = games[0]
		self.assertEqual(info.result, "Unknown result")
		self.assertEqual(info.white, "?")
		self.assertEqual(info.event, "?")
		game = PGNGame.from_game_info(info)
		self.assertEqual(len(game.moves), 8)
		self.assertEqual(game.get_board().fen().split()[0], "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR")

	def test_a_latin_1_file_still_loads(self):
		text = TWO_GAMES.replace("Ferreira, Joao", "Ferreira, João")
		path = self.write("latin1.pgn", text, encoding="latin-1")
		first, second = PGNGameInfo.game_info_from_pgn_filename(path)
		# The accented byte is replaced, not fatal; the rest of the name survives.
		self.assertTrue(first.black.startswith("Ferreira, Jo"))
		self.assertEqual(first.result, "White won")
		game = PGNGame.from_game_info(second)
		self.assertEqual(len(game.moves), 2)

	def test_result_parser_never_raises(self):
		parse = PGNGameInfo.parse_pgn_result_string
		self.assertEqual(parse(""), "Unknown result")
		self.assertEqual(parse("garbage"), "Unknown result")
		self.assertEqual(parse("1-0-0"), "Unknown result")
		self.assertEqual(parse(" 0-1 "), "Black won")
		self.assertEqual(parse("1/2-1/2"), "Game ended in a draw")
		self.assertEqual(parse("*"), "Game not finished")

	def test_loading_a_missing_file_raises_oserror(self):
		with self.assertRaises(OSError):
			list(PGNGameInfo.game_info_from_pgn_filename(str(self.dir / "missing.pgn")))
