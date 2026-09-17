# coding: utf-8

"""Painel de preferências: o plano de treino que vale por padrão.

O que esta tela tem de próprio é o layout, o texto do resumo e o que acontece
ao confirmar -- salvar as preferências. Todo o resto vem de `TacticsSetupMixin`,
porque é idêntico ao diálogo da sessão.
"""

import wx
import gui
from gui import guiHelper

from ..addon_config import get_move_notation, get_tactics_defaults, save_move_notation, save_tactics_defaults
from ..notation import NOTATION_STYLES
from ..i18n import _
from ..theme_catalog import parse_theme_filter
from ..trainer import (
	challenge_description,
	challenge_label,
	describe_rating_range,
	preset_description,
	preset_label,
	uses_custom_themes,
)
from .tactics_setup import TacticsSetupMixin


class ChessboardSettingsDialog(TacticsSetupMixin, gui.SettingsDialog):
	# Translators: Title of the Chessboard settings dialog.
	title = _("Chessboard")

	def __init__(self, *args, **kwargs):
		# Antes do super: o SettingsDialog do NVDA chama makeSettings() de
		# dentro do próprio construtor. Ver _init_trainer_state.
		self._init_trainer_state()
		super().__init__(*args, **kwargs)

	def makeSettings(self, settingsSizer):
		defaults = get_tactics_defaults()
		self._theme_filter_text = defaults.theme
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		introLabel = wx.StaticText(
			self,
			-1,
			# Translators: Intro text of the Chessboard settings dialog.
			_("Configure the default trainer plan used when you open Chessboard tactics."),
			style=wx.ST_ELLIPSIZE_END,
		)
		introLabel.Wrap(self.GetSize().Width)
		helper.addItem(introLabel)

		self._build_database_row(helper, self._default_database_value(defaults.db_path))
		self._build_choice_rows(
			helper,
			defaults,
			# Translators: Label for the default training plan combo box.
			_("Default training plan"),
			# Translators: Label for the default challenge level combo box.
			_("Default challenge level"),
		)
		self._build_summary_row(helper)
		# Translators: Label for the default themes field.
		self._build_theme_rows(helper, _("Default themes"))

		# Translators: Label of the combo box that chooses how moves are spoken.
		notationLabel = wx.StaticText(self, -1, _("Move &notation"))
		self.notationChoice = wx.Choice(self, -1, choices=[label for _style, label in NOTATION_STYLES])
		current = get_move_notation()
		self.notationChoice.SetSelection(
			next((index for index, (style, _label) in enumerate(NOTATION_STYLES) if style == current), 0),
		)
		guiHelper.associateElements(notationLabel, self.notationChoice)
		helper.addItem(notationLabel)
		helper.addItem(self.notationChoice)
		self._bind_shared_events()

	def postInit(self):
		self._updateTrainerSummary()
		self._updateThemeSummary()
		self._refresh_theme_controls()
		self.databasePathTextCtrl.SetFocus()

	def _theme_picker_prompt(self):
		# Translators: Prompt in the theme picker, when choosing the saved default themes.
		return _("Choose one or more Lichess themes to use in the custom default trainer plan.")

	def _refresh_theme_controls(self):
		is_custom = uses_custom_themes(self._trainer_preset_id())
		self.selectThemesButton.Enable(is_custom)
		self.clearThemesButton.Enable(is_custom and bool(parse_theme_filter(self._theme_filter_text)))

	def _updateTrainerSummary(self):
		resolved = self._resolved_selection()
		# Translators: Summary of the saved default training selection.
		summary = _(
			"{plan}. {plan_desc}\n{challenge}. {challenge_desc}\n{theme_text}\nDefault: {rating_text}; minimum popularity {min_popularity}.",
		).format(
			plan=preset_label(resolved.preset),
			plan_desc=preset_description(resolved.preset),
			challenge=challenge_label(resolved.challenge),
			challenge_desc=challenge_description(resolved.challenge),
			theme_text=self._theme_count_sentence(resolved),
			rating_text=describe_rating_range(resolved),
			min_popularity=resolved.min_popularity,
		)
		self.trainerSummaryTextCtrl.SetValue(summary)

	def onOk(self, event):
		resolved = self._resolved_selection()
		save_tactics_defaults(
			db_path=self.databasePathTextCtrl.GetValue().strip(),
			theme=self._theme_filter_text,
			trainer_preset=self._trainer_preset_id(),
			challenge_level=self._challenge_id(),
			min_rating=resolved.min_rating,
			max_rating=resolved.max_rating,
			min_popularity=resolved.min_popularity,
		)
		save_move_notation(NOTATION_STYLES[self.notationChoice.GetSelection()][0])
		super().onOk(event)
