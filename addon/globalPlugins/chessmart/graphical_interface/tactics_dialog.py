# coding: utf-8

import wx
import gui
from gui import guiHelper

from ..addon_config import get_tactics_defaults, save_tactics_defaults
from ..i18n import _
from ..puzzle_database import TacticSessionOptions, get_default_tactic_db_path
from ..theme_catalog import describe_theme_filter, format_theme_filter, load_theme_catalog, parse_theme_filter
from ..trainer import (
    iter_challenge_levels,
    iter_trainer_presets,
    resolve_training_selection,
    uses_custom_themes,
)


class TacticsOptionsDialog(gui.SettingsDialog):
    title = _("Tactics")

    def __init__(self, *args, callback, **kwargs):
        # SettingsDialog.__init__ chama makeSettings() por dentro, então tudo
        # que makeSettings lê precisa existir antes desta chamada.
        self.callback = callback
        self._theme_filter_text = ""
        self._trainer_presets = iter_trainer_presets()
        self._challenge_levels = iter_challenge_levels()
        super().__init__(*args, **kwargs)

    def makeSettings(self, sizer):
        defaults = get_tactics_defaults()
        self._theme_filter_text = defaults.theme
        mainSizerHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)

        intro_label = wx.StaticText(
            self,
            -1,
            _(
                "Start a guided training session, or type a puzzle ID to open one exact Lichess tactic."
            ),
            style=wx.ST_ELLIPSIZE_END,
        )
        intro_label.Wrap(self.GetSize().Width)
        mainSizerHelper.addItem(intro_label)

        databasePathLabel = wx.StaticText(self, -1, _("Tactics database"))
        self.databasePathTextCtrl = wx.TextCtrl(
            self,
            -1,
            value=defaults.db_path or get_default_tactic_db_path() or "",
        )
        guiHelper.associateElements(databasePathLabel, self.databasePathTextCtrl)
        self.browseDatabaseButton = wx.Button(self, -1, _("&Browse..."))
        databasePathSizer = wx.BoxSizer(wx.HORIZONTAL)
        databasePathSizer.Add(self.databasePathTextCtrl, 1, wx.RIGHT | wx.EXPAND, 5)
        databasePathSizer.Add(self.browseDatabaseButton, 0)
        mainSizerHelper.addItem(databasePathLabel)
        mainSizerHelper.addItem(databasePathSizer)

        puzzleIdLabel = wx.StaticText(self, -1, _("Puzzle ID"))
        self.puzzleIdTextCtrl = wx.TextCtrl(self, -1)
        guiHelper.associateElements(puzzleIdLabel, self.puzzleIdTextCtrl)
        mainSizerHelper.addItem(puzzleIdLabel)
        mainSizerHelper.addItem(self.puzzleIdTextCtrl)

        trainerPresetLabel = wx.StaticText(self, -1, _("Training plan"))
        self.trainerPresetChoice = wx.Choice(
            self,
            -1,
            choices=[preset.label for preset in self._trainer_presets],
        )
        self._set_choice_by_id(
            self.trainerPresetChoice,
            [preset.preset_id for preset in self._trainer_presets],
            defaults.trainer_preset,
        )
        guiHelper.associateElements(trainerPresetLabel, self.trainerPresetChoice)
        mainSizerHelper.addItem(trainerPresetLabel)
        mainSizerHelper.addItem(self.trainerPresetChoice)

        challengeLabel = wx.StaticText(self, -1, _("Challenge level"))
        self.challengeChoice = wx.Choice(
            self,
            -1,
            choices=[level.label for level in self._challenge_levels],
        )
        self._set_choice_by_id(
            self.challengeChoice,
            [level.challenge_id for level in self._challenge_levels],
            defaults.challenge_level,
        )
        guiHelper.associateElements(challengeLabel, self.challengeChoice)
        mainSizerHelper.addItem(challengeLabel)
        mainSizerHelper.addItem(self.challengeChoice)

        trainerSummaryLabel = wx.StaticText(self, -1, _("Trainer summary"))
        self.trainerSummaryTextCtrl = wx.TextCtrl(
            self,
            -1,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        guiHelper.associateElements(trainerSummaryLabel, self.trainerSummaryTextCtrl)
        mainSizerHelper.addItem(trainerSummaryLabel)
        mainSizerHelper.addItem(self.trainerSummaryTextCtrl)

        themeLabel = wx.StaticText(self, -1, _("Themes"))
        self.themeSummaryTextCtrl = wx.TextCtrl(
            self,
            -1,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        guiHelper.associateElements(themeLabel, self.themeSummaryTextCtrl)
        self.selectThemesButton = wx.Button(self, -1, _("Select &themes..."))
        self.clearThemesButton = wx.Button(self, -1, _("C&lear themes"))
        themeButtonSizer = wx.BoxSizer(wx.HORIZONTAL)
        themeButtonSizer.Add(self.selectThemesButton, 0, wx.RIGHT, 5)
        themeButtonSizer.Add(self.clearThemesButton, 0)
        mainSizerHelper.addItem(themeLabel)
        mainSizerHelper.addItem(self.themeSummaryTextCtrl)
        mainSizerHelper.addItem(themeButtonSizer)

        self.saveDefaultsCheckbox = wx.CheckBox(
            self,
            -1,
            _("&Save training setup as default"),
        )
        mainSizerHelper.addItem(self.saveDefaultsCheckbox)

        self.Bind(wx.EVT_BUTTON, self.onBrowseDatabase, self.browseDatabaseButton)
        self.Bind(wx.EVT_BUTTON, self.onSelectThemes, self.selectThemesButton)
        self.Bind(wx.EVT_BUTTON, self.onClearThemes, self.clearThemesButton)
        self.Bind(wx.EVT_TEXT, self.onPuzzleIdChanged, self.puzzleIdTextCtrl)
        self.Bind(wx.EVT_TEXT, self.onDatabasePathChanged, self.databasePathTextCtrl)
        self.Bind(wx.EVT_CHOICE, self.onTrainerPresetChanged, self.trainerPresetChoice)
        self.Bind(wx.EVT_CHOICE, self.onChallengeChanged, self.challengeChoice)

    def postInit(self):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self.databasePathTextCtrl.SetFocus()
        self._updateTrainingControls()

    def onBrowseDatabase(self, event):
        dialog = wx.FileDialog(
            parent=self,
            message=_("Select tactics database"),
            wildcard=_("SQLite databases (*.db;*.sqlite)|*.db;*.sqlite|All files|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dialog.ShowModal() == wx.ID_OK:
            self.databasePathTextCtrl.SetValue(dialog.GetPath())
            self._updateTrainerSummary()
            self._updateThemeSummary()
        dialog.Destroy()

    def onDatabasePathChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        event.Skip()

    def onPuzzleIdChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self._updateTrainingControls()
        event.Skip()

    def onTrainerPresetChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self._updateTrainingControls()
        event.Skip()

    def onChallengeChanged(self, event):
        self._updateTrainerSummary()
        event.Skip()

    def _trainer_preset_id(self):
        return self._trainer_presets[self.trainerPresetChoice.GetSelection()].preset_id

    def _challenge_id(self):
        return self._challenge_levels[self.challengeChoice.GetSelection()].challenge_id

    def _resolved_db_path(self):
        return self.databasePathTextCtrl.GetValue().strip() or get_default_tactic_db_path() or ""

    def _updateTrainingControls(self):
        filters_enabled = not bool(self.puzzleIdTextCtrl.GetValue().strip())
        is_custom = uses_custom_themes(self._trainer_preset_id())
        for control in (
            self.trainerPresetChoice,
            self.challengeChoice,
        ):
            control.Enable(filters_enabled)
        self.selectThemesButton.Enable(filters_enabled and is_custom)
        self.clearThemesButton.Enable(filters_enabled and is_custom and bool(parse_theme_filter(self._theme_filter_text)))
        self.themeSummaryTextCtrl.Enable(True)

    def _resolved_selection(self):
        return resolve_training_selection(
            self._trainer_preset_id(),
            self._challenge_id(),
            custom_theme_text=self._theme_filter_text,
        )

    def _updateTrainerSummary(self):
        if self.puzzleIdTextCtrl.GetValue().strip():
            self.trainerSummaryTextCtrl.SetValue(_("Specific puzzle mode. Training plan filters are ignored."))
            return
        resolved = self._resolved_selection()
        # Uma ponta sem limite é None, e interpolar None faria o leitor de tela
        # anunciar a palavra "None". Cada caso ganha a frase que descreve o que
        # o filtro realmente faz.
        if resolved.min_rating is None and resolved.max_rating is None:
            rating_text = _("puzzles of any rating")
        elif resolved.min_rating is None:
            rating_text = _("puzzles rated up to {max_rating}").format(
                max_rating=resolved.max_rating
            )
        elif resolved.max_rating is None:
            rating_text = _("puzzles rated {min_rating} and above").format(
                min_rating=resolved.min_rating
            )
        else:
            rating_text = _("puzzles rated {min_rating} to {max_rating}").format(
                min_rating=resolved.min_rating,
                max_rating=resolved.max_rating,
            )
        summary = _(
            "{plan}. {plan_desc}\n{challenge}. {challenge_desc}\nUses {rating_text} and minimum popularity {min_popularity}."
        ).format(
            plan=resolved.preset.label,
            plan_desc=resolved.preset.description,
            challenge=resolved.challenge.label,
            challenge_desc=resolved.challenge.description,
            rating_text=rating_text,
            min_popularity=resolved.min_popularity,
        )
        self.trainerSummaryTextCtrl.SetValue(summary)

    def _updateThemeSummary(self):
        if self.puzzleIdTextCtrl.GetValue().strip():
            self.themeSummaryTextCtrl.SetValue(_("Puzzle ID mode"))
            return
        resolved = self._resolved_selection()
        if uses_custom_themes(self._trainer_preset_id()):
            theme_slugs = parse_theme_filter(self._theme_filter_text)
            if not theme_slugs:
                summary = _("All themes")
            else:
                labels = describe_theme_filter(self._theme_filter_text, db_path=self._resolved_db_path())
                summary = _("{count} selected: {themes}").format(
                    count=len(theme_slugs),
                    themes=labels or ", ".join(theme_slugs),
                )
        else:
            labels = describe_theme_filter(resolved.theme_text, db_path=self._resolved_db_path())
            summary = labels or _("All themes")
        self.themeSummaryTextCtrl.SetValue(summary)

    def onSelectThemes(self, event):
        db_path = self._resolved_db_path()
        if not db_path:
            gui.messageBox(
                _("Choose a tactics database before selecting themes."),
                _("No Database Selected"),
                style=wx.ICON_WARNING,
            )
            return
        try:
            entries = load_theme_catalog(db_path)
        except Exception as error:
            gui.messageBox(
                str(error),
                _("Could Not Load Themes"),
                style=wx.ICON_ERROR,
            )
            return
        if not entries:
            gui.messageBox(
                _("No themes were found in the selected database."),
                _("Themes Not Found"),
                style=wx.ICON_WARNING,
            )
            return
        dialog = wx.MultiChoiceDialog(
            self,
            _("Choose one or more Lichess themes to use in the custom training plan."),
            _("Select Themes"),
            choices=[
                _("{label} ({count} puzzles) [{slug}]").format(
                    label=entry.label,
                    count=entry.count,
                    slug=entry.slug,
                )
                for entry in entries
            ],
        )
        selected_slugs = set(parse_theme_filter(self._theme_filter_text))
        selections = [index for index, entry in enumerate(entries) if entry.slug in selected_slugs]
        if selections:
            dialog.SetSelections(selections)
        if dialog.ShowModal() == wx.ID_OK:
            self._theme_filter_text = format_theme_filter(
                [entries[index].slug for index in dialog.GetSelections()]
            )
            self._updateThemeSummary()
            self._updateTrainingControls()
        dialog.Destroy()

    def onClearThemes(self, event):
        self._theme_filter_text = ""
        self._updateThemeSummary()
        self._updateTrainingControls()

    def _set_choice_by_id(self, choice, ids, selected_id):
        try:
            choice.SetSelection(ids.index(selected_id))
        except ValueError:
            choice.SetSelection(0)

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
