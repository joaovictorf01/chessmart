# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Testes unitários do chessmart que rodam fora do NVDA.

Os módulos do add-on importam `logHandler` e `addonHandler` (do NVDA); aqui
eles ganham substitutos mínimos, e o pacote é importado como `chessmart` a
partir de `addon/globalPlugins`, sem passar pelo `__init__` do plugin (que
puxa wx e o resto do NVDA).
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
_stub("addonHandler")  # sem initTranslation: i18n cai na identidade

if "chessmart" not in sys.modules:
	package = types.ModuleType("chessmart")
	package.__path__ = [str(ADDON_PLUGINS / "chessmart")]
	sys.modules["chessmart"] = package
