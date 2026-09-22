# coding: utf-8
# pyright: basic

"""Endgames dialog: which lesson, which position, and the tables.

Lesson 1 is the mate drills (Capablanca's position or a random one, with an
optional clock); the others are the course positions, each annotated with
what the log says about it: how many times in a row the player got it right
and held the result. Each position's rule is deliberately left out here --
it appears after the answer, on the board.
"""

from __future__ import annotations

import wx
import gui
from gui import guiHelper
from logHandler import log

from ..endgame import log as endgame_log
from ..endgame.lessons import ENDGAME_LESSONS, lesson_description, lesson_label, position_title
from ..i18n import _
from ..time_control import NULL_TIME_CONTROL, ChessTimeControl
from .tablebase_dialog import TablebaseDownloadDialog, installed_sentence
from .messages import show_error


class EndgameDialog(gui.SettingsDialog):
	# Translators: Title of the endgames dialog.
	title = _("Endgames")

	def __init__(self, *args, callback, **kwargs):
		self.callback = callback
		self._stats: dict[str, endgame_log.PositionStats] = {}
		super().__init__(*args, **kwargs)

	def makeSettings(self, sizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		intro_label = wx.StaticText(
			self,
			-1,
			# Translators: Intro text of the endgames dialog.
			_(
				"Lessons follow the endgame course order: first the mates, then what draws and what does not. Each position asks win, draw or loss, tells the rule, and is played out against the engine with the tablebase as judge.",
			),
			style=wx.ST_ELLIPSIZE_END,
		)
		intro_label.Wrap(self.GetSize().Width)
		helper.addItem(intro_label)

		# Translators: Label for the list of endgame lessons.
		lesson_label_ctrl = wx.StaticText(self, -1, _("Lesson"))
		self.lessonChoice = wx.Choice(self, -1, choices=[lesson_label(lesson) for lesson in ENDGAME_LESSONS])
		self.lessonChoice.SetSelection(0)
		guiHelper.associateElements(lesson_label_ctrl, self.lessonChoice)
		helper.addItem(lesson_label_ctrl)
		helper.addItem(self.lessonChoice)

		# Translators: Label for the list of positions of the chosen lesson.
		position_label_ctrl = wx.StaticText(self, -1, _("Position"))
		self.positionChoice = wx.Choice(self, -1, choices=[])
		guiHelper.associateElements(position_label_ctrl, self.positionChoice)
		helper.addItem(position_label_ctrl)
		helper.addItem(self.positionChoice)

		# Translators: Label for the read-only field describing the chosen lesson.
		about_label = wx.StaticText(self, -1, _("About this lesson"))
		self.aboutTextCtrl = wx.TextCtrl(self, -1, style=wx.TE_MULTILINE | wx.TE_READONLY)
		guiHelper.associateElements(about_label, self.aboutTextCtrl)
		helper.addItem(about_label)
		helper.addItem(self.aboutTextCtrl)

		# Translators: Label for the optional clock of the mate drills.
		time_label = wx.StaticText(self, -1, _("Clock for the mate drills (minutes+seconds, empty for none)"))
		self.timeControlTextCtrl = wx.TextCtrl(self, -1, value="")
		guiHelper.associateElements(time_label, self.timeControlTextCtrl)
		helper.addItem(time_label)
		helper.addItem(self.timeControlTextCtrl)

		self.tablebaseText = wx.StaticText(self, -1, installed_sentence())
		helper.addItem(self.tablebaseText)
		# Translators: Button that opens the tablebase download dialog.
		self.tablebaseButton = wx.Button(self, -1, _("Download &tablebases..."))
		helper.addItem(self.tablebaseButton)

		self.Bind(wx.EVT_CHOICE, self.onLessonChanged, self.lessonChoice)
		self.Bind(wx.EVT_BUTTON, self.onTablebases, self.tablebaseButton)
		self._fill_positions()

	def postInit(self):
		self.lessonChoice.SetFocus()

	def _selected_lesson(self):
		return ENDGAME_LESSONS[self.lessonChoice.GetSelection()]

	def onLessonChanged(self, event):
		self._fill_positions()

	def _fill_positions(self):
		lesson = self._selected_lesson()
		self._stats = self._load_stats(lesson.lesson_id)
		self.positionChoice.Clear()
		if lesson.drill is not None:
			# Translators: First choice of position for a mate drill.
			self.positionChoice.Append(_("Capablanca's example"))
			# Translators: Second choice of position for a mate drill.
			self.positionChoice.Append(_("Random position"))
		else:
			for position in lesson.positions:
				self.positionChoice.Append(self._position_label(position))
		self.positionChoice.SetSelection(0)
		self.timeControlTextCtrl.Enable(lesson.drill is not None)
		self.aboutTextCtrl.SetValue(f"{lesson_description(lesson)}\n\n{lesson.source}")

	def _position_label(self, position) -> str:
		label = position_title(position)
		stats = self._stats.get(position.position_id)
		if stats is None or stats.attempts == 0:
			return label
		if stats.streak:
			# Translators: Suffix of a lesson position with its streak, e.g. "The king leads (3 in a row)".
			return _("{title} ({streak} in a row)").format(title=label, streak=stats.streak)
		# Translators: Suffix of a lesson position attempted but not yet held.
		return _("{title} (not held yet)").format(title=label)

	def _load_stats(self, lesson_id: str):
		try:
			connection = endgame_log.open_log()
			try:
				return endgame_log.lesson_stats(connection, lesson_id)
			finally:
				connection.close()
		except Exception as error:
			log.warning("chessmart: could not read the endgame log: %s", error)
			return {}

	def onTablebases(self, event):
		dialog = TablebaseDownloadDialog(self)
		dialog.ShowModal()
		dialog.Destroy()
		self.tablebaseText.SetLabel(installed_sentence())

	def onOk(self, event):
		lesson = self._selected_lesson()
		time_control = NULL_TIME_CONTROL
		text = self.timeControlTextCtrl.GetValue().strip()
		if lesson.drill is not None and text:
			try:
				time_control = ChessTimeControl.from_time_control_notation(text)
			except ValueError:
				show_error(
					_(
						"Please enter a valid time control string.\nExample: 10+5 for a 10 minutes base time with 5 seconds increment after each move.",
					),
					_("Invalid Time Control String"),
				)
				return
		index = max(self.positionChoice.GetSelection(), 0)
		self.callback(lesson, index, time_control)
		super().onOk(event)
