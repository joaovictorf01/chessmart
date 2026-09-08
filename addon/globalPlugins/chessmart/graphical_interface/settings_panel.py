# coding: utf-8

import wx
import gui
from gui import guiHelper

from ..addon_config import get_tactics_defaults, save_tactics_defaults
from ..i18n import _
from ..puzzle_database import get_default_tactic_db_path
from ..theme_catalog import describe_theme_filter, format_theme_filter, load_theme_catalog, parse_theme_filter
from ..trainer import (
    iter_challenge_levels,
    iter_trainer_presets,
    resolve_training_selection,
    uses_custom_themes,
)


class ChessboardSettingsDialog(gui.SettingsDialog):
    title = _("Chessboard")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._theme_filter_text = ""
        self._trainer_presets = iter_trainer_presets()
        self._challenge_levels = iter_challenge_levels()

    def makeSettings(self, settingsSizer):
        defaults = get_tactics_defaults()
        self._theme_filter_text = defaults.theme
        helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

        introLabel = wx.StaticText(
            self,
            -1,
            _(
                "Configure the default trainer plan used when you open Chessboard tactics."
            ),
            style=wx.ST_ELLIPSIZE_END,
        )
        introLabel.Wrap(self.GetSize().Width)
        helper.addItem(introLabel)

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
        helper.addItem(databasePathLabel)
        helper.addItem(databasePathSizer)

        trainerPresetLabel = wx.StaticText(self, -1, _("Default training plan"))
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
        helper.addItem(trainerPresetLabel)
        helper.addItem(self.trainerPresetChoice)

        challengeLabel = wx.StaticText(self, -1, _("Default challenge level"))
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
        helper.addItem(challengeLabel)
        helper.addItem(self.challengeChoice)

        trainerSummaryLabel = wx.StaticText(self, -1, _("Trainer summary"))
        self.trainerSummaryTextCtrl = wx.TextCtrl(
            self,
            -1,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        guiHelper.associateElements(trainerSummaryLabel, self.trainerSummaryTextCtrl)
        helper.addItem(trainerSummaryLabel)
        helper.addItem(self.trainerSummaryTextCtrl)

        themeLabel = wx.StaticText(self, -1, _("Default themes"))
        self.themeSummaryTextCtrl = wx.TextCtrl(
            self,
            -1,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        guiHelper.associateElements(themeLabel, self.themeSummaryTextCtrl)
        self.selectThemesButton = wx.Button(self, -1, _("Select &themes..."))
        self.clearThemesButton = wx.Button(self, -1, _("C&lear themes"))
        themeButtonsSizer = wx.BoxSizer(wx.HORIZONTAL)
        themeButtonsSizer.Add(self.selectThemesButton, 0, wx.RIGHT, 5)
        themeButtonsSizer.Add(self.clearThemesButton, 0)
        helper.addItem(themeLabel)
        helper.addItem(self.themeSummaryTextCtrl)
        helper.addItem(themeButtonsSizer)

        self.Bind(wx.EVT_BUTTON, self.onBrowseDatabase, self.browseDatabaseButton)
        self.Bind(wx.EVT_BUTTON, self.onSelectThemes, self.selectThemesButton)
        self.Bind(wx.EVT_BUTTON, self.onClearThemes, self.clearThemesButton)
        self.Bind(wx.EVT_TEXT, self.onDatabasePathChanged, self.databasePathTextCtrl)
        self.Bind(wx.EVT_CHOICE, self.onTrainerPresetChanged, self.trainerPresetChoice)
        self.Bind(wx.EVT_CHOICE, self.onChallengeChanged, self.challengeChoice)

    def postInit(self):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self._updateThemeControls()
        self.databasePathTextCtrl.SetFocus()

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

    def onTrainerPresetChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self._updateThemeControls()
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

    def _resolved_selection(self):
        return resolve_training_selection(
            self._trainer_preset_id(),
            self._challenge_id(),
            custom_theme_text=self._theme_filter_text,
        )

    def _updateTrainerSummary(self):
        resolved = self._resolved_selection()
        summary = _(
            "{plan}. {plan_desc}\n{challenge}. {challenge_desc}\nDefault range: rating {min_rating} to {max_rating}; minimum popularity {min_popularity}."
        ).format(
            plan=resolved.preset.label,
            plan_desc=resolved.preset.description,
            challenge=resolved.challenge.label,
            challenge_desc=resolved.challenge.description,
            min_rating=resolved.min_rating,
            max_rating=resolved.max_rating,
            min_popularity=resolved.min_popularity,
        )
        self.trainerSummaryTextCtrl.SetValue(summary)

    def _updateThemeSummary(self):
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

    def _updateThemeControls(self):
        is_custom = uses_custom_themes(self._trainer_preset_id())
        self.selectThemesButton.Enable(is_custom)
        self.clearThemesButton.Enable(is_custom and bool(parse_theme_filter(self._theme_filter_text)))

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
            _("Choose one or more Lichess themes to use in the custom default trainer plan."),
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
            self._updateThemeControls()
        dialog.Destroy()

    def onClearThemes(self, event):
        self._theme_filter_text = ""
        self._updateThemeSummary()
        self._updateThemeControls()

    def _set_choice_by_id(self, choice, ids, selected_id):
        try:
            choice.SetSelection(ids.index(selected_id))
        except ValueError:
            choice.SetSelection(0)

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
        super().onOk(event)
