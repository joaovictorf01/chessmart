# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Where the add-on's files live on disk, and how to load the bundled libraries.

Deliberately free of NVDA imports: this is the module any other module can import,
including tests running outside the screen reader.
"""

import contextlib
import os
import sys

PLUGIN_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
LIB_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "lib")
BIN_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "bin")
SOUNDS_DIRECTORY = os.path.join(PLUGIN_DIRECTORY, "sounds")


@contextlib.contextmanager
def import_bundled(packages_path=LIB_DIRECTORY):
	"""Lets `import chess` (and the other libraries under lib/) work inside the block.

	The folder is only added to `sys.path` for the duration of the `with`: the
	imported module stays in `sys.modules` and remains accessible afterward, but
	the path itself doesn't pollute the rest of NVDA.
	"""
	sys.path.insert(0, packages_path)
	try:
		yield
	finally:
		sys.path.remove(packages_path)
