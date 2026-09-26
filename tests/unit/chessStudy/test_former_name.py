# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Taking the user's data and settings over from the former name, Chessmart."""

import os
import tempfile
import unittest
from pathlib import Path

from chessStudy import former_name


class TestAdoptRenamedFolder(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		self.root = Path(self.directory.name)
		self.former = self.root / "chessmart"
		self.current = self.root / "chessStudy"

	def tearDown(self):
		self.directory.cleanup()

	def test_former_folder_is_renamed_with_everything_in_it(self):
		(self.former / "syzygy").mkdir(parents=True)
		(self.former / "tactic.db").write_bytes(b"history")
		self.assertEqual(former_name.adopt_renamed_folder(self.former, self.current), self.current)
		self.assertFalse(self.former.exists())
		self.assertEqual((self.current / "tactic.db").read_bytes(), b"history")
		self.assertTrue((self.current / "syzygy").is_dir())

	def test_existing_new_folder_is_never_overwritten(self):
		self.former.mkdir()
		(self.former / "tactic.db").write_bytes(b"old")
		self.current.mkdir()
		self.assertEqual(former_name.adopt_renamed_folder(self.former, self.current), self.current)
		self.assertEqual((self.former / "tactic.db").read_bytes(), b"old")

	def test_new_user_gets_the_new_folder(self):
		self.assertEqual(former_name.adopt_renamed_folder(self.former, self.current), self.current)
		self.assertFalse(self.current.exists())

	def test_refused_rename_keeps_using_the_former_folder(self):
		self.former.mkdir()
		original = Path.rename

		def refuse(path, target):
			raise PermissionError("in use")

		Path.rename = refuse
		try:
			result = former_name.adopt_renamed_folder(self.former, self.current)
		finally:
			Path.rename = original
		self.assertEqual(result, self.former)


class TestCarriedOverSettings(unittest.TestCase):
	KEYS = ("tacticsDbPath", "moveNotation", "reviewSeconds")
	FORMER_DATA = Path("C:/Users/x/AppData/Roaming/nvda/chessmart")
	DATA = Path("C:/Users/x/AppData/Roaming/nvda/chessStudy")

	def test_known_keys_come_as_text_and_unknown_ones_stay_behind(self):
		settings = former_name.carried_over_settings(
			{"moveNotation": "san", "reviewSeconds": 2.5, "onlineToken": "x"},
			self.KEYS,
			self.FORMER_DATA,
			self.DATA,
		)
		self.assertEqual(settings, {"moveNotation": "san", "reviewSeconds": "2.5"})

	def test_database_inside_the_former_folder_moves_along(self):
		inside = os.path.join(str(self.FORMER_DATA), "puzzles.db")
		settings = former_name.carried_over_settings(
			{"tacticsDbPath": inside},
			self.KEYS,
			self.FORMER_DATA,
			self.DATA,
		)
		self.assertEqual(Path(settings["tacticsDbPath"]), self.DATA / "puzzles.db")

	def test_database_elsewhere_is_left_alone(self):
		elsewhere = r"D:\xadrez\puzzles.db"
		settings = former_name.carried_over_settings(
			{"tacticsDbPath": elsewhere},
			self.KEYS,
			self.FORMER_DATA,
			self.DATA,
		)
		self.assertEqual(settings["tacticsDbPath"], elsewhere)


class TestGamesFolder(unittest.TestCase):
	def setUp(self):
		self.directory = tempfile.TemporaryDirectory()
		self.documents = Path(self.directory.name)

	def tearDown(self):
		self.directory.cleanup()

	def test_new_user_gets_chess_study(self):
		self.assertEqual(former_name.games_folder(self.documents), self.documents / "Chess Study")

	def test_former_games_stay_where_they_are(self):
		(self.documents / "Chessmart").mkdir()
		self.assertEqual(former_name.games_folder(self.documents), self.documents / "Chessmart")

	def test_new_folder_wins_once_it_exists(self):
		(self.documents / "Chessmart").mkdir()
		(self.documents / "Chess Study").mkdir()
		self.assertEqual(former_name.games_folder(self.documents), self.documents / "Chess Study")


if __name__ == "__main__":
	unittest.main()
