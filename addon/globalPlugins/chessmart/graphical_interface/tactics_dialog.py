# coding: utf-8

"""Diálogo que abre uma sessão de treino de táticas.

O que esta tela tem de próprio: o campo de ID de puzzle -- que desliga os
filtros, porque pedir um puzzle pelo id é pedir aquele puzzle --, a caixa de
salvar como padrão, e o que acontece ao confirmar. O resto vem de
`TacticsSetupMixin`, compartilhado com o painel de preferências.
"""

import wx
import gui
from gui import guiHelper

from ..addon_config import get_tactics_defaults, save_tactics_defaults
from ..i18n import _
from ..puzzle_database import TacticSessionOptions
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

        self._build_database_row(
            helper, self._default_database_value(defaults.db_path)
        )

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
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self.databasePathTextCtrl.SetFocus()
        self._refresh_theme_controls()

    def onPuzzleIdChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
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
            filters_enabled
            and is_custom
            and bool(parse_theme_filter(self._theme_filter_text))
        )
        self.themeSummaryTextCtrl.Enable(True)

    def _theme_summary_text(self):
        if self._in_puzzle_id_mode():
            # Translators: Shown in the themes field when a puzzle id was typed.
            return _("Puzzle ID mode")
        return super()._theme_summary_text()

    def _updateTrainerSummary(self):
        if self._in_puzzle_id_mode():
            self.trainerSummaryTextCtrl.SetValue(
                # Translators: Summary shown when a specific puzzle id was typed.
                _("Specific puzzle mode. Training plan filters are ignored.")
            )
            return
        resolved = self._resolved_selection()
        # Translators: Summary of the training session about to start.
        summary = _(
            "{plan}. {plan_desc}\n{challenge}. {challenge_desc}\n{theme_text}\nUses {rating_text} and minimum popularity {min_popularity}."
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

    def get_options(self):
        puzzle_id = self.puzzleIdTextCtrl.GetValue().strip()
        resolved = self._resolved_selection()
        return TacticSessionOptions(
            db_path=self.databasePathTextCtrl.GetValue().strip() or None,
            puzzle_id=puzzle_id,
            theme="" if puzzle_id else resolved.theme_text,
            trainer_preset=self._trainer_preset_id(),
            challenge_level=self._challenge_id(),
            min_rating=None if puzzle_id else resolved.min_rating,
            max_rating=None if puzzle_id else resolved.max_rating,
            min_popularity=0 if puzzle_id else resolved.min_popularity,
            # Pedir um puzzle pelo ID é pedir aquele puzzle: a calibração
            # automática não tem o que fazer aí.
            adaptive=False if puzzle_id else resolved.adaptive,
        )

    def onOk(self, event):
        options = self.get_options()
        if self.saveDefaultsCheckbox.IsChecked():
            save_tactics_defaults(
                db_path=options.db_path or "",
                theme=self._theme_filter_text,
                trainer_preset=self._trainer_preset_id(),
                challenge_level=self._challenge_id(),
                min_rating=options.min_rating,
                max_rating=options.max_rating,
                min_popularity=options.min_popularity,
            )
        self.callback(options)
        super().onOk(event)
