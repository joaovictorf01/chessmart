# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The game review options: one set of controls, in Settings and in the analysis board's Tab bar."""

import types

import wx
from gui import guiHelper

from ..addon_config import get_review_options, save_review_options
from ..engine_eval import MoveVerdict
from ..game_review import Reveal, ReviewOptions, Side
from ..i18n import _


def build_review_controls(parent, helper):
	"""Adds the review group to `helper` and returns its controls; `options_from(controls)` reads them."""
	controls = types.SimpleNamespace()
	review = get_review_options()
	# Translators: Label of the group with the game review options.
	groupSizer = wx.StaticBoxSizer(wx.VERTICAL, parent, label=_("Game review (F7 on the analysis board)"))
	group = helper.addItem(guiHelper.BoxSizerHelper(parent, sizer=groupSizer))
	box = groupSizer.GetStaticBox()

	def choice(label, options, current):
		control = group.addLabeledControl(label, wx.Choice, choices=[text for _value, text in options])
		values = [value for value, _text in options]
		control.SetSelection(values.index(current) if current in values else 0)
		return control, values

	controls.side, controls.side_values = choice(
		# Translators: Label of the review option: whose moves are reviewed.
		_("&Moves reviewed"),
		# Translators: Review option value.
		[(Side.MINE, _("Only mine (the side at the bottom of the board)")), (Side.BOTH, _("Both sides"))],
		review.side,
	)
	controls.threshold, controls.threshold_values = choice(
		# Translators: Label of the review option: from which verdict a move is a critical moment.
		_("&Critical moments"),
		[
			# Translators: Review option value.
			(MoveVerdict.BLUNDER, _("Blunders only")),
			# Translators: Review option value.
			(MoveVerdict.MISTAKE, _("Mistakes and blunders")),
			# Translators: Review option value.
			(MoveVerdict.INACCURACY, _("Everything, inaccuracies too")),
		],
		review.threshold,
	)
	controls.max_moments, controls.max_values = choice(
		# Translators: Label of the review option: how many critical moments at most.
		_("At &most"),
		# Translators: Review option value: every critical moment.
		[(3, "3"), (5, "5"), (10, "10"), (None, _("All"))],
		review.max_moments,
	)
	controls.reveal, controls.reveal_values = choice(
		# Translators: Label of the review option: what the engine says at a critical moment.
		_("What the engine &reveals"),
		[
			# Translators: Review option value: the engine says only where the move went wrong.
			(Reveal.NOTHING, _("Only where it went wrong: I look for the better move")),
			# Translators: Review option value.
			(Reveal.MOVE, _("Its move too")),
			# Translators: Review option value.
			(Reveal.LINE, _("Its move, and its line as a variation")),
		],
		review.reveal,
	)
	controls.seconds, controls.seconds_values = choice(
		# Translators: Label of the review option: engine time per position.
		_("&Time per position"),
		[
			# Translators: Review option value.
			(0.5, _("Quick, half a second")),
			# Translators: Review option value.
			(1.0, _("Normal, one second")),
			# Translators: Review option value.
			(3.0, _("Deep, three seconds")),
		],
		review.seconds,
	)
	controls.skip_theory = group.addItem(
		# Translators: Checkbox of the review options.
		wx.CheckBox(box, label=_("Skip opening &theory")),
	)
	controls.skip_theory.SetValue(review.skip_theory)
	return controls


def options_from(controls) -> ReviewOptions:
	return ReviewOptions(
		side=controls.side_values[controls.side.GetSelection()],
		threshold=controls.threshold_values[controls.threshold.GetSelection()],
		max_moments=controls.max_values[controls.max_moments.GetSelection()],
		reveal=controls.reveal_values[controls.reveal.GetSelection()],
		seconds=controls.seconds_values[controls.seconds.GetSelection()],
		skip_theory=controls.skip_theory.GetValue(),
	)


class ReviewOptionsDialog(wx.Dialog):
	"""Opened from the analysis board's Tab bar; OK saves, as in Settings."""

	def __init__(self, parent):
		# Translators: Title of the game review options dialog.
		super().__init__(parent, title=_("Game Review Options"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.controls = build_review_controls(self, helper)
		helper.addDialogDismissButtons(wx.OK | wx.CANCEL)
		mainSizer.Add(helper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.controls.side.SetFocus()

	def save(self) -> None:
		save_review_options(options_from(self.controls))
