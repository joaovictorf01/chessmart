# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""My Games: the folder's games, newest file first, with the player's notes counted."""

import os
import tempfile
import time
import unittest
from pathlib import Path

from chessmart.my_games import list_saved_games

ANNOTATED = """[Event "rated rapid game"]
[Date "2026.09.23"]
[White "victorf01"]
[Black "dheekshan2020"]
[Result "0-1"]

1. c4 { [%clk 0:15:00] } 1... c6 { [%clk 0:15:00] } 2. g3 $6 { achei estranho [%clk 0:15:04] }
( 2. e4 { outra ideia } ) 2... b6 $4 0-1
"""

PLAIN = """[Event "Casual"]
[Date "????.??.??"]
[White "A"]
[Black "B"]
[Result "1/2-1/2"]

1. e4 e5 1/2-1/2
"""


class TestMyGames(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		self.folder = Path(self.directory.name)

	def tearDown(self):
		self.directory.cleanup()

	def write(self, name, text, age_seconds=0):
		path = self.folder / name
		path.write_text(text, encoding="utf-8")
		stamp = time.time() - age_seconds
		os.utime(path, (stamp, stamp))
		return path

	def test_notes_count_the_players_own_work_not_the_clock(self):
		self.write("a.pgn", ANNOTATED)
		(game,), unreadable = list_saved_games(str(self.folder))
		self.assertEqual(unreadable, [])
		self.assertEqual((game.notes.comments, game.notes.marks, game.notes.variations), (2, 2, 1))
		self.assertEqual(
			game.description(),
			"2026-09-23, victorf01 versus dheekshan2020, Black won. Comments: 2, marks: 2, variations: 1.",
		)
		self.assertTrue(game.single_game_file)

	def test_newest_file_first_and_every_game_of_a_collection(self):
		self.write("old.pgn", ANNOTATED, age_seconds=3600)
		self.write("collection.pgn", PLAIN + "\n" + PLAIN)
		games, _ = list_saved_games(str(self.folder))
		self.assertEqual(
			[Path(g.info.filename).name for g in games],
			["collection.pgn", "collection.pgn", "old.pgn"],
		)
		self.assertFalse(games[0].single_game_file)
		self.assertEqual(games[0].description(), "no date, A versus B, Game ended in a draw. No notes.")
		self.assertNotEqual(games[0].info.offset, games[1].info.offset)

	def test_other_files_and_a_missing_folder_are_ignored(self):
		self.write("notes.txt", "not a game")
		self.assertEqual(list_saved_games(str(self.folder)), ([], []))
		self.assertEqual(list_saved_games(str(self.folder / "missing")), ([], []))
