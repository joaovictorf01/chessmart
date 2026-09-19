# coding: utf-8
# pyright: basic

"""Diálogo "Meu estudo": quanto se estudou por dia e até onde as lições foram.

Um texto só, legível linha a linha com o leitor de tela, e um botão que o
copia inteiro para a área de transferência -- para colar num caderno ou
mandar para alguém.
"""

from __future__ import annotations

import api
import wx
import gui
import ui
from gui import guiHelper
from logHandler import log

from .. import study_log
from ..endgame import log as endgame_log
from ..i18n import _

PERIODS = (1, 7, 30)


class StudyLogDialog(gui.SettingsDialog):
	# Translators: Title of the study log dialog.
	title = _("My Study")

	def makeSettings(self, sizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		# Translators: Label of the period selector in the study log.
		period_label = wx.StaticText(self, -1, _("Period"))
		self.periodChoice = wx.Choice(
			self,
			-1,
			choices=[
				# Translators: Period choices of the study log.
				_("Today"),
				_("Last 7 days"),
				_("Last 30 days"),
			],
		)
		self.periodChoice.SetSelection(1)
		guiHelper.associateElements(period_label, self.periodChoice)
		helper.addItem(period_label)
		helper.addItem(self.periodChoice)

		# Translators: Label of the read-only text with the study log.
		text_label = wx.StaticText(self, -1, _("Study log"))
		self.logTextCtrl = wx.TextCtrl(self, -1, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(600, 320))
		guiHelper.associateElements(text_label, self.logTextCtrl)
		helper.addItem(text_label)
		helper.addItem(self.logTextCtrl)

		# Translators: Button that copies the study log to the clipboard.
		self.copyButton = wx.Button(self, -1, _("&Copy to clipboard"))
		helper.addItem(self.copyButton)

		self.Bind(wx.EVT_CHOICE, self.onPeriodChanged, self.periodChoice)
		self.Bind(wx.EVT_BUTTON, self.onCopy, self.copyButton)
		self._refresh()

	def postInit(self):
		self.periodChoice.SetFocus()

	def onPeriodChanged(self, event):
		self._refresh()

	def _refresh(self):
		days = PERIODS[self.periodChoice.GetSelection()]
		try:
			connection = endgame_log.open_log()
			try:
				summaries = study_log.daily_summaries(connection, days)
				progress = study_log.lesson_progress(connection)
			finally:
				connection.close()
		except Exception as error:
			log.warning("chessmart: could not read the study log: %s", error)
			# Translators: Shown when the study log could not be read.
			self.logTextCtrl.SetValue(_("The history could not be read."))
			return
		lines = [
			# Translators: Heading of the daily part of the study log.
			_("By day"),
			*study_log.render_days(summaries, days),
			"",
			# Translators: Heading of the lessons part of the study log.
			_("Endgame lessons: how far you go"),
			*study_log.render_progress(progress),
		]
		self.logTextCtrl.SetValue("\n".join(lines))

	def onCopy(self, event):
		if api.copyToClip(self.logTextCtrl.GetValue()):
			# Translators: Announced after the study log was copied.
			ui.message(_("Copied."))
