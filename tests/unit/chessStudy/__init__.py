# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Unit tests for chessStudy that run outside of NVDA.

The add-on modules import `logHandler` and `addonHandler` (from NVDA); here
they get minimal stand-ins, and the package is imported as `chessStudy` from
`addon/globalPlugins`, bypassing the plugin's `__init__` (which pulls in wx
and the rest of NVDA).
"""

import sys
import types
from pathlib import Path

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

if "chessStudy" not in sys.modules:
	package = types.ModuleType("chessStudy")
	package.__path__ = [str(ADDON_PLUGINS / "chessStudy")]
	sys.modules["chessStudy"] = package
