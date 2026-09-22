# coding: utf-8
# pyright: basic
"""Single point of translation for the add-on: `from .i18n import _`.

`addonHandler.initTranslation()` finds the calling module via the stack frame
and writes the functions `_`, `ngettext`, `pgettext` and `npgettext` into THAT
module, pointing at the add-on's catalog (locale/<language>/LC_MESSAGES/nvda.mo).
That's why the call sits here at module level rather than inside a function:
called from within a function it would still write to the module, but the
function's return value -- `builtins`' `_`, which is NVDA's own translation --
would overwrite the correct one. That was exactly the bug until 1.0.

Outside an installed add-on (scratchpad, tests) the call fails, and `_` falls
back to whatever `_` already exists, or to the identity function.

`N_()` marks text that lives in a constant and will only be translated later,
with `_()`, at display time. It doesn't translate anything; it exists so the
extractor (`tools/i18n.py`) can find the literal and add it to the catalog.
"""

import builtins

from logHandler import log


def _identity(message):
	return message


def N_(message: str) -> str:
	"""Marks `message` for translation without translating it now. See the module docstring."""
	return message


try:
	import addonHandler

	addonHandler.initTranslation()
except Exception as error:  # noqa: BLE001 - outside NVDA, or outside an installed add-on
	log.debug("Chessmart translation is unavailable in this context: %s", error)
	_ = builtins.__dict__.get("_", _identity)
	ngettext = builtins.__dict__.get("ngettext", lambda singular, plural, n: singular if n == 1 else plural)
	pgettext = builtins.__dict__.get("pgettext", lambda context, message: message)
	npgettext = builtins.__dict__.get(
		"npgettext",
		lambda context, singular, plural, n: singular if n == 1 else plural,
	)

__all__ = ["_", "N_", "ngettext", "pgettext", "npgettext"]
