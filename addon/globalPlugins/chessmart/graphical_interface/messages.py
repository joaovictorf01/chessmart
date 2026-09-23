# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Message boxes and modal dialogs, on NVDA's `gui.message.MessageDialog`.

NVDA 2025.1 deprecated `gui.messageBox` and `gui.runScriptModalDialog`; these
are the add-on's replacements. Every function here must be called on the GUI
thread (menu handlers, scripts and `wx.CallAfter` callbacks all are).
"""

from typing import Callable

import wx
import gui
from gui.message import DefaultButtonSet, DialogType, MessageDialog, ReturnCode, displayDialogAsModal


def _parent(parent: wx.Window | None) -> wx.Window | None:
	return parent if parent is not None else gui.mainFrame


def show_message(message: str, caption: str, *, parent: wx.Window | None = None) -> None:
	"""A modal message with an OK button, no icon and no sound."""
	MessageDialog(_parent(parent), message, caption).ShowModal()


def show_warning(message: str, caption: str, *, parent: wx.Window | None = None) -> None:
	"""A modal message with the exclamation icon and the Windows alert sound."""
	MessageDialog(_parent(parent), message, caption, DialogType.WARNING).ShowModal()


def show_error(message: str, caption: str, *, parent: wx.Window | None = None) -> None:
	"""A modal message with the cross icon and the Windows error sound."""
	MessageDialog(_parent(parent), message, caption, DialogType.ERROR).ShowModal()


def ask_yes_no(message: str, caption: str, *, parent: wx.Window | None = None) -> bool:
	"""A modal question with Yes and No buttons; True when the user chose Yes."""
	dialog = MessageDialog(_parent(parent), message, caption, buttons=DefaultButtonSet.YES_NO)
	return dialog.ShowModal() == ReturnCode.YES


def run_modal(dialog: wx.Dialog, callback: Callable[[int], object] | None = None) -> None:
	"""Shows `dialog` modally on the next GUI cycle, hands the result to `callback` and destroys it.

	Scripts and menu handlers cannot block on `ShowModal` themselves; this is what
	`gui.runScriptModalDialog` did before it was deprecated.
	"""

	def run() -> None:
		result = displayDialogAsModal(dialog)
		if callback is not None:
			callback(result)
		dialog.Destroy()

	wx.CallAfter(run)


def ask_yes_no_from_script(
	message: str,
	caption: str,
	callback: Callable[[bool], object],
	*,
	parent: wx.Window | None = None,
) -> None:
	"""A Yes/No question asked from a script, which cannot block: the answer goes to `callback`.

	No is the focused button and the answer to Escape, so a question that
	guards a shortcut never lets the same keystroke through by accident.
	"""
	dialog = MessageDialog(_parent(parent), message, caption, buttons=None)
	dialog.addYesButton().addNoButton(defaultFocus=True, fallbackAction=True)
	run_modal(dialog, lambda result: callback(result == ReturnCode.YES))
