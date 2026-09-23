# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The one verification command: must pass before any commit.

Usage: uv run python tools/check.py

Runs, in order and without fixing anything: the unit tests, ruff lint, ruff
format check, the translation catalog check, and pyright. Pyright needs NVDA's
sources cloned next to this repository (../nvda); without them it is skipped
and says so. Stops at the first step that fails and exits with its code. CI runs
the same script.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = "addon/globalPlugins/chessmart/lib"

STEPS = [
	("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"]),
	("ruff check", [sys.executable, "-m", "ruff", "check", "--exclude", LIB, "."]),
	# Line endings are git's business (.gitattributes, text=auto): a Windows
	# checkout has CRLF on disk and LF in the repository, so they are not checked here.
	(
		"ruff format",
		[
			sys.executable,
			"-m",
			"ruff",
			"format",
			"--check",
			"--config",
			"format.line-ending = 'auto'",
			"--exclude",
			LIB,
			".",
		],
	),
	("translations", [sys.executable, "tools/i18n.py", "check"]),
]


def main() -> int:
	steps = list(STEPS)
	if (ROOT.parent / "nvda" / "source").is_dir():
		steps.append(("pyright", [sys.executable, "-m", "pyright"]))
	else:
		print("pyright: skipped, no NVDA checkout at ../nvda", flush=True)
	for name, command in steps:
		print(f"== {name}", flush=True)
		result = subprocess.run(command, cwd=ROOT)
		if result.returncode != 0:
			print(f"FAILED: {name}", flush=True)
			return result.returncode
	print("all checks passed", flush=True)
	return 0


if __name__ == "__main__":
	sys.exit(main())
