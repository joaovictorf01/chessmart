# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The dialog Control+S opens on the analysis board: who played, where, when, the result."""

import datetime

import wx
from gui import guiHelper

from ..game_tree import RecordHeaders
from ..i18n import _
from .messages import show_error


# PGN results, in the order offered; the labels say them in words.
RESULTS = ("1-0", "0-1", "1/2-1/2", "*")


def _result_labels():
	return [
		# Translators: Result choice when saving a game: white won.
		_("White won (1-0)"),
		# Translators: Result choice when saving a game: black won.
		_("Black won (0-1)"),
		# Translators: Result choice when saving a game: draw.
		_("Draw (1/2-1/2)"),
		# Translators: Result choice when saving a game: unknown or unfinished.
		_("Unfinished or unknown (*)"),
	]


class RecordHeadersDialog(wx.Dialog):
	def __init__(self, parent, initial: RecordHeaders):
		# Translators: Title of the dialog that saves the analysed game.
		super().__init__(parent, title=_("Save Game"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: Label of the field with the name of the player with the white pieces.
		self.whiteText = helper.addLabeledControl(_("&White"), wx.TextCtrl, value=initial.white)
		# Translators: Label of the field with the name of the player with the black pieces.
		self.blackText = helper.addLabeledControl(_("&Black"), wx.TextCtrl, value=initial.black)
		# Translators: Label of the field with the event (tournament, training, club...).
		self.eventText = helper.addLabeledControl(_("&Event"), wx.TextCtrl, value=initial.event)
		self.dateText = helper.addLabeledControl(
			# Translators: Label of the date field of the save dialog; the format follows in parentheses.
			_("&Date (year-month-day)"),
			wx.TextCtrl,
			value=initial.date.isoformat(),
		)
		# Translators: Label of the result choice in the save dialog.
		self.resultChoice = helper.addLabeledControl(_("&Result"), wx.Choice, choices=_result_labels())
		self.resultChoice.SetSelection(
			RESULTS.index(initial.result) if initial.result in RESULTS else len(RESULTS) - 1
		)
		helper.addDialogDismissButtons(wx.OK | wx.CANCEL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.whiteText.SetFocus()

	def _date(self):
		try:
			return datetime.date.fromisoformat(self.dateText.GetValue().strip())
		except ValueError:
			return None

	def onOk(self, event):
		if self._date() is None:
			show_error(
				# Translators: Shown when the date typed in the save dialog is not valid.
				_("Type the date as year-month-day, for example {example}.").format(
					example=datetime.date.today().isoformat(),
				),
				# Translators: Title of the error about an invalid date.
				_("Invalid Date"),
				parent=self,
			)
			self.dateText.SetFocus()
			return
		self.EndModal(wx.ID_OK)

	def get_headers(self) -> RecordHeaders:
		return RecordHeaders(
			white=self.whiteText.GetValue(),
			black=self.blackText.GetValue(),
			event=self.eventText.GetValue(),
			date=self._date() or datetime.date.today(),
			result=RESULTS[self.resultChoice.GetSelection()],
		)
