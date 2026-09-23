# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The modules that must work without NVDA do (AGENTS.md, "The boundary").

Each is imported in a fresh interpreter with only the two stand-ins the tests
use (logHandler, addonHandler); afterwards none of NVDA's own modules may be
loaded. Adding `import ui` to one of them fails here, not in a user's NVDA.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

PURE_MODULES = (
	"board_geometry",
	"concurrency",
	"endgame.drills",
	"endgame.judge",
	"endgame.lessons",
	"endgame.tablebase",
	"engine_eval",
	"game_tree",
	"i18n",
	"notation",
	"openings",
	"paths",
	"pgn",
	"puzzle_attempt",
	"study_log",
	"tactic.download",
	"tactic.repository",
	"tactic.store",
	"theme_catalog",
	"theme_names",
	"trainer",
	"training_session",
)

NVDA_MODULES = (
	"api",
	"controlTypes",
	"eventHandler",
	"globalVars",
	"gui",
	"NVDAObjects",
	"queueHandler",
	"scriptHandler",
	"speech",
	"ui",
	"wx",
)

PROBE = """
import importlib, sys
import tests.unit.chessmart  # installs the two stand-ins and the `chessmart` package
for name in {modules!r}:
	importlib.import_module("chessmart." + name)
loaded = sorted(name for name in {forbidden!r} if name in sys.modules)
print(",".join(loaded))
"""


class BoundaryTest(unittest.TestCase):
	def test_pure_modules_import_nothing_from_nvda(self):
		result = subprocess.run(
			[sys.executable, "-c", PROBE.format(modules=PURE_MODULES, forbidden=NVDA_MODULES)],
			cwd=REPO,
			capture_output=True,
			text=True,
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertEqual(result.stdout.strip(), "", "NVDA modules loaded by a pure module")


if __name__ == "__main__":
	unittest.main()
