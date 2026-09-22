# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Spoken names that do not depend on the board: colours in IBCA notation, game-over reasons."""

import re
import unittest
from pathlib import Path

from chessmart.ibca_notation import IBCA_COLOR_NAMES
from chessmart.paths import import_bundled
from chessmart.spoken_messages import ibca_game_announcer, spoken_termination_name

with import_bundled():
	import chess

LOCALE = Path(__file__).resolve().parents[3] / "addon" / "locale"


def translation_of(language: str, msgid: str) -> str:
	"""The msgstr for a single-line `msgid` in that language's catalog, "" if absent or untranslated."""
	catalog = (LOCALE / language / "LC_MESSAGES" / "nvda.po").read_text(encoding="utf-8")
	pattern = '^msgid "%s"\nmsgstr "(.*)"$' % re.escape(msgid)
	match = re.search(pattern, catalog, re.MULTILINE)
	return match.group(1) if match else ""


class TestIBCAColours(unittest.TestCase):
	def test_white_is_weiss_and_black_is_schwarz(self):
		self.assertEqual(IBCA_COLOR_NAMES[chess.WHITE], "weiss")
		self.assertEqual(IBCA_COLOR_NAMES[chess.BLACK], "schwarz")
		self.assertEqual(ibca_game_announcer.color_name(chess.WHITE), "weiss")
		self.assertNotEqual(IBCA_COLOR_NAMES[chess.WHITE], IBCA_COLOR_NAMES[chess.BLACK])


class TestTerminationNames(unittest.TestCase):
	def test_every_termination_has_a_translated_name(self):
		# Outside NVDA `_` is the identity, so the name is the msgid; the
		# catalogs must carry a translation for it in every language shipped.
		for termination in chess.Termination:
			with self.subTest(termination=termination.name):
				name = spoken_termination_name(termination)
				self.assertTrue(name)
				self.assertNotIn("_", name, "an enum name leaked into speech")
				for language in ("pt_BR", "es"):
					self.assertTrue(translation_of(language, name), f"{name!r} not translated in {language}")

	def test_checkmate_and_stalemate_are_named(self):
		self.assertEqual(spoken_termination_name(chess.Termination.CHECKMATE), "checkmate")
		self.assertEqual(spoken_termination_name(chess.Termination.STALEMATE), "stalemate")
