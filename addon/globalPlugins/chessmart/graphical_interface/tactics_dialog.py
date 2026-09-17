# coding: utf-8
# pyright: basic

"""Diálogo que abre uma sessão de treino de táticas.

O que esta tela tem de próprio: o campo de ID de puzzle -- que desliga os
filtros, porque pedir um puzzle pelo id é pedir aquele puzzle --, a caixa de
salvar como padrão, e o que acontece ao confirmar. O resto vem de
`TacticsSetupMixin`, compartilhado com o painel de preferências.
"""

import wx
import gui
from gui import guiHelper

from ..addon_config import TacticsDefaults, get_tactics_defaults, save_tactics_defaults
from ..i18n import _
from ..theme_catalog import parse_theme_filter
from ..training_session import TrainingOptions
from ..trainer import uses_custom_themes
from .tactics_setup import TacticsSetupMixin


class TacticsOptionsDialog(TacticsSetupMixin, gui.SettingsDialog):
	# Translators: Title of the tactics session dialog.
	title = _("Tactics")

	def __init__(self, *args, callback, **kwargs):
		# Antes do super: o SettingsDialog do NVDA chama makeSettings() de
		# dentro do próprio construtor. Ver _init_trainer_state.
		self.callback = callback
		self._init_trainer_state()
		super().__init__(*args, **kwargs)

	def makeSettings(self, sizer):
		defaults = get_tactics_defaults()
		self._theme_filter_text = defaults.theme
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		intro_label = wx.StaticText(
			self,
			-1,
			# Translators: Intro text of the tactics session dialog.
			_("Start a guided training session, or type a puzzle ID to open one exact Lichess tactic."),
			style=wx.ST_ELLIPSIZE_END,
		)
		intro_label.Wrap(self.GetSize().Width)
		helper.addItem(intro_label)

		self._build_database_row(helper, self._default_database_value(defaults.db_path))

		# Translators: Label for the field where a single puzzle id can be typed.
		puzzleIdLabel = wx.StaticText(self, -1, _("Puzzle ID"))
		self.puzzleIdTextCtrl = wx.TextCtrl(self, -1)
		guiHelper.associateElements(puzzleIdLabel, self.puzzleIdTextCtrl)
		helper.addItem(puzzleIdLabel)
		helper.addItem(self.puzzleIdTextCtrl)

		self._build_choice_rows(
			helper,
			defaults,
			# Translators: Label for the training plan combo box.
			_("Training plan"),
			# Translators: Label for the challenge level combo box.
			_("Challenge level"),
		)
		self._build_summary_row(helper)
		# Translators: Label for the themes field.
		self._build_theme_rows(helper, _("Themes"))

		self.saveDefaultsCheckbox = wx.CheckBox(
			self,
			-1,
			# Translators: Checkbox that stores the current setup as the default.
			_("&Save training setup as default"),
		)
		helper.addItem(self.saveDefaultsCheckbox)

		self._bind_shared_events()
		self.Bind(wx.EVT_TEXT, self.onPuzzleIdChanged, self.puzzleIdTextCtrl)

	def postInit(self):
		self._update_trainer_summary()
		self._update_theme_summary()
		self.databasePathTextCtrl.SetFocus()
		self._refresh_theme_controls()

	def onPuzzleIdChanged(self, event):
		self._update_trainer_summary()
		self._update_theme_summary()
		self._refresh_theme_controls()
		event.Skip()

	def _in_puzzle_id_mode(self):
		return bool(self.puzzleIdTextCtrl.GetValue().strip())

	def _refresh_theme_controls(self):
		# Com um id digitado os filtros não valem, então as caixas de plano e
		# nível também são desligadas -- senão a tela sugere uma escolha que
		# não terá efeito nenhum.
		filters_enabled = not self._in_puzzle_id_mode()
		is_custom = uses_custom_themes(self._trainer_preset_id())
		self.trainerPresetChoice.Enable(filters_enabled)
		self.challengeChoice.Enable(filters_enabled)
		self.selectThemesButton.Enable(filters_enabled and is_custom)
		self.clearThemesButton.Enable(
			filters_enabled and is_custom and bool(parse_theme_filter(self._theme_filter_text)),
		)
		self.themeSummaryTextCtrl.Enable(True)

	def _theme_summary_text(self):
		if self._in_puzzle_id_mode():
			# Translators: Shown in the themes field when a puzzle id was typed.
			return _("Puzzle ID mode")
		return super()._theme_summary_text()

	def _trainer_summary_text(self):
		if self._in_puzzle_id_mode():
			# Translators: Summary shown when a specific puzzle id was typed.
			return _("Specific puzzle mode. Training plan filters are ignored.")
		return super()._trainer_summary_text()

	def get_options(self):
		# Com um id digitado, plano e nível ficam guardados nas opções mas não
		# filtram nada: pedir um puzzle pelo id é pedir aquele puzzle.
		return TrainingOptions(
			db_path=self.databasePathTextCtrl.GetValue().strip() or None,
			puzzle_id=self.puzzleIdTextCtrl.GetValue().strip(),
			trainer_preset=self._trainer_preset_id(),
			challenge_level=self._challenge_id(),
			custom_theme_text=self._theme_filter_text,
		)

	def onOk(self, event):
		options = self.get_options()
		if self.saveDefaultsCheckbox.IsChecked():
			save_tactics_defaults(
				TacticsDefaults(
					db_path=options.db_path or "",
					theme=options.custom_theme_text,
					trainer_preset=options.trainer_preset,
					challenge_level=options.challenge_level,
				),
			)
		self.callback(options)
		super().onOk(event)
