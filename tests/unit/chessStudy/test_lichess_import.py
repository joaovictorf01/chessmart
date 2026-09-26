# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Importing a game from Lichess (README, "Import a Lichess game").

What the user may type, the address asked for (clocks yes, Lichess's own
evaluations no), and what happens when Lichess answers or does not. The
server here is local; nothing reaches lichess.org.
"""

import http.server
import io
import threading
import unittest

from chessStudy.lichess_import import GameRef, export_url, fetch_game, imported_filename, parse_reference
from chessStudy.paths import import_bundled
from chessStudy.tactic.download import DownloadError

with import_bundled():
	import chess.pgn

PGN = """[Event "rated rapid game"]
[Site "https://lichess.org/o9PtYEji"]
[White "Someone"]
[Black "victorf01"]
[Result "0-1"]
[TimeControl "900+10"]

1. e4 { [%clk 0:15:00] } 1... c5 { [%clk 0:15:00] } 0-1
"""


class ReferenceTest(unittest.TestCase):
	def test_links_ids_and_usernames(self):
		self.assertEqual(parse_reference("https://lichess.org/o9PtYEji"), GameRef("game", "o9PtYEji"))
		self.assertEqual(parse_reference("lichess.org/o9PtYEjiXyZw/black"), GameRef("game", "o9PtYEji"))
		self.assertEqual(parse_reference("https://lichess.org/o9PtYEji#34"), GameRef("game", "o9PtYEji"))
		self.assertEqual(parse_reference("o9PtYEji"), GameRef("game", "o9PtYEji"))
		self.assertEqual(parse_reference("victorf01"), GameRef("user", "victorf01"))
		self.assertEqual(parse_reference("  @victorf1 "), GameRef("user", "victorf1"))
		self.assertEqual(parse_reference("https://lichess.org/@/victorf01"), GameRef("user", "victorf01"))

	def test_nonsense_is_refused(self):
		self.assertIsNone(parse_reference(""))
		self.assertIsNone(parse_reference("https://lichess.org/training"))
		self.assertIsNone(parse_reference("not a name!"))

	def test_the_export_asks_for_clocks_and_no_lichess_evaluations(self):
		url = export_url(GameRef("game", "o9PtYEji"))
		self.assertTrue(url.startswith("https://lichess.org/game/export/o9PtYEji?"))
		self.assertIn("clocks=true", url)
		self.assertIn("evals=false", url)
		self.assertIn("/api/games/user/victorf01?max=1&", export_url(GameRef("user", "victorf01")))


class FilenameTest(unittest.TestCase):
	def test_date_players_and_game_id(self):
		headers = '[UTCDate "2026.09.22"]\n[GameId "o9PtYEji"]\n'
		game = chess.pgn.read_game(io.StringIO(headers + PGN))
		assert game is not None
		self.assertEqual(imported_filename(game), "2026-09-22_Someone-vs-victorf01_lichess-o9PtYEji.pgn")


class Handler(http.server.BaseHTTPRequestHandler):
	def do_GET(self):  # noqa: N802 - http.server's name
		if "/game/export/o9PtYEji" in self.path:
			body = PGN.encode("utf-8")
			self.send_response(200)
			self.send_header("Content-Type", "application/x-chess-pgn")
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)
			return
		self.send_response(404)
		self.send_header("Content-Length", "0")
		self.end_headers()

	def log_message(self, format, *args):  # noqa: A002 - http.server's signature
		pass


class FetchTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
		cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
		cls.thread.start()

	@classmethod
	def tearDownClass(cls):
		cls.server.shutdown()
		cls.server.server_close()

	def test_a_game_arrives_with_its_clock(self):
		game = fetch_game(GameRef("game", "o9PtYEji"), base=self.base)
		self.assertEqual(game.headers["Black"], "victorf01")
		self.assertEqual(game.next().clock(), 900.0)  # type: ignore[union-attr]

	def test_a_missing_game_says_not_found(self):
		with self.assertRaises(DownloadError) as caught:
			fetch_game(GameRef("game", "zzzzzzzz"), base=self.base)
		self.assertIn("not found", str(caught.exception))


if __name__ == "__main__":
	unittest.main()
