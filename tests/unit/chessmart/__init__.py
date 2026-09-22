# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Unit tests for chessmart that run outside of NVDA.

The add-on modules import `logHandler` and `addonHandler` (from NVDA); here
they get minimal stand-ins, and the package is imported as `chessmart` from
`addon/globalPlugins`, bypassing the plugin's `__init__` (which pulls in wx
and the rest of NVDA).
"""

import asyncio  # noqa: F401  (see below)
import sys
import types
from pathlib import Path

# `chess.pgn` imports `chess.engine`, which imports asyncio. While lib/ is on
# sys.path (`import_bundled`), the Python 3.7 `_overlapped.pyd` bundled there
# would shadow the interpreter's own and fail to load; importing asyncio here
# first caches the real one in `sys.modules`.

ADDON_PLUGINS = Path(__file__).resolve().parents[3] / "addon" / "globalPlugins"


def _stub(name: str, **attrs: object) -> None:
	if name in sys.modules:
		return
	module = types.ModuleType(name)
	for key, value in attrs.items():
		setattr(module, key, value)
	sys.modules[name] = module


_stub(
	"logHandler",
	log=types.SimpleNamespace(
		debug=lambda *a, **k: None,
		info=lambda *a, **k: None,
		warning=lambda *a, **k: None,
		error=lambda *a, **k: None,
		exception=lambda *a, **k: None,
	),
)
_stub("addonHandler")  # no initTranslation: i18n falls back to identity

if "chessmart" not in sys.modules:
	package = types.ModuleType("chessmart")
	package.__path__ = [str(ADDON_PLUGINS / "chessmart")]
	sys.modules["chessmart"] = package
