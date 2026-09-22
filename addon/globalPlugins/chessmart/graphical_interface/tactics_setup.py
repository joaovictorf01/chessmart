# coding: utf-8
# pyright: basic

"""Shared base for the two screens that configure tactics training.

The session dialog (`tactics_dialog`) and the preferences panel
(`settings_panel`) show the same controls -- database path, plan, level,
summary and theme selection -- and used to be two separate copies, which let
the same `__init__` ordering bug and a summary fix diverge between them. What
lives here is what was identical; each screen still owns its own
`makeSettings` and `onOk`. Points of variation are explicit overridable
methods: `_refresh_theme_controls` and `_theme_picker_prompt`.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import wx
import gui
import ui
from gui import guiHelper

from ..i18n import _
from ..training_session import default_db_path, usable_db_path
from ..theme_catalog import (
	ensure_theme_catalog_async,
	describe_theme_filter,
	format_theme_filter,
	load_theme_catalog,
	parse_theme_filter,
)
from ..trainer import (
	CHALLENGE_LEVELS,
	TRAINER_PRESETS,
	challenge_description,
	challenge_label,
	preset_description,
	preset_label,
	resolve_training_selection,
	uses_custom_themes,
)


if TYPE_CHECKING:
	# Only for the type checker: the mixin is always combined with a
	# SettingsDialog, and that is where Bind, GetSize and the other wx
	# methods come from.
	_MixinBase = gui.SettingsDialog
else:
	_MixinBase = object


class TacticsSetupMixin(_MixinBase):
	"""Controls and rules shared by the tactics configuration screens."""

	# -- state ------------------------------------------------------------------

	def _init_trainer_state(self):
		"""Creates the attributes that `makeSettings` will read.

		Must be called BEFORE `super().__init__()`: NVDA's `SettingsDialog`
		calls `makeSettings()` from within its own constructor, so everything
		`makeSettings` reads must exist before that line. This exact detail is
		what broke both screens.
		"""
		self._theme_filter_text = ""
		self._trainer_presets = TRAINER_PRESETS
		self._challenge_levels = CHALLENGE_LEVELS

	# -- building the controls --------------------------------------------------

	def _build_database_row(self, helper, default_path):
		# Translators: Label for the tactics database path field.
		label = wx.StaticText(self, -1, _("Tactics database"))
		self.databasePathTextCtrl = wx.TextCtrl(self, -1, value=default_path)
		guiHelper.associateElements(label, self.databasePathTextCtrl)
		# Translators: Button that opens a file picker for the tactics database.
		self.browseDatabaseButton = wx.Button(self, -1, _("&Browse..."))
		# Translators: Button that opens the dialog to download or update the puzzle database.
		self.downloadDatabaseButton = wx.Button(self, -1, _("Do&wnload or update..."))
		row = wx.BoxSizer(wx.HORIZONTAL)
		row.Add(self.databasePathTextCtrl, 1, wx.RIGHT | wx.EXPAND, 5)
		row.Add(self.browseDatabaseButton, 0, wx.RIGHT, 5)
		row.Add(self.downloadDatabaseButton, 0)
		helper.addItem(label)
		helper.addItem(row)

	def _build_choice_rows(self, helper, defaults, plan_text, level_text):
		"""The two combo boxes: plan and level.

		The labels are passed as a parameter because the preferences panel
		says "default" ("Default training plan") and the session dialog does
		not.
		"""
		plan_label_ctrl = wx.StaticText(self, -1, plan_text)
		self.trainerPresetChoice = wx.Choice(
			self,
			-1,
			choices=[preset_label(preset) for preset in self._trainer_presets],
		)
		self._set_choice_by_id(
			self.trainerPresetChoice,
			[preset.preset_id for preset in self._trainer_presets],
			defaults.trainer_preset,
		)
		guiHelper.associateElements(plan_label_ctrl, self.trainerPresetChoice)
		helper.addItem(plan_label_ctrl)
		helper.addItem(self.trainerPresetChoice)

		level_label_ctrl = wx.StaticText(self, -1, level_text)
		self.challengeChoice = wx.Choice(
			self,
			-1,
			choices=[challenge_label(level) for level in self._challenge_levels],
		)
		self._set_choice_by_id(
			self.challengeChoice,
			[level.challenge_id for level in self._challenge_levels],
			defaults.challenge_level,
		)
		guiHelper.associateElements(level_label_ctrl, self.challengeChoice)
		helper.addItem(level_label_ctrl)
		helper.addItem(self.challengeChoice)

	def _build_summary_row(self, helper):
		# Translators: Label for the read-only field summarising the training setup.
		label = wx.StaticText(self, -1, _("Trainer summary"))
		self.trainerSummaryTextCtrl = wx.TextCtrl(
			self,
			-1,
			style=wx.TE_MULTILINE | wx.TE_READONLY,
		)
		guiHelper.associateElements(label, self.trainerSummaryTextCtrl)
		helper.addItem(label)
		helper.addItem(self.trainerSummaryTextCtrl)

	def _build_theme_rows(self, helper, theme_text):
		label = wx.StaticText(self, -1, theme_text)
		self.themeSummaryTextCtrl = wx.TextCtrl(
			self,
			-1,
			style=wx.TE_MULTILINE | wx.TE_READONLY,
		)
		guiHelper.associateElements(label, self.themeSummaryTextCtrl)
		# Translators: Button that opens the theme picker.
		self.selectThemesButton = wx.Button(self, -1, _("Select &themes..."))
		# Translators: Button that clears the selected themes.
		self.clearThemesButton = wx.Button(self, -1, _("C&lear themes"))
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		buttons.Add(self.selectThemesButton, 0, wx.RIGHT, 5)
		buttons.Add(self.clearThemesButton, 0)
		helper.addItem(label)
		helper.addItem(self.themeSummaryTextCtrl)
		helper.addItem(buttons)

	def _bind_shared_events(self):
		self.Bind(wx.EVT_BUTTON, self.onBrowseDatabase, self.browseDatabaseButton)
		self.Bind(wx.EVT_BUTTON, self.onDownloadDatabase, self.downloadDatabaseButton)
		self.Bind(wx.EVT_BUTTON, self.onSelectThemes, self.selectThemesButton)
		self.Bind(wx.EVT_BUTTON, self.onClearThemes, self.clearThemesButton)
		self.Bind(wx.EVT_TEXT, self.onDatabasePathChanged, self.databasePathTextCtrl)
		self.Bind(wx.EVT_CHOICE, self.onTrainerPresetChanged, self.trainerPresetChoice)
		self.Bind(wx.EVT_CHOICE, self.onChallengeChanged, self.challengeChoice)

	# -- reading the state --------------------------------------------------

	def _set_choice_by_id(self, choice, ids, selected_id):
		try:
			choice.SetSelection(ids.index(selected_id))
		except ValueError:
			choice.SetSelection(0)

	def _trainer_preset_id(self):
		return self._trainer_presets[self.trainerPresetChoice.GetSelection()].preset_id

	def _challenge_id(self):
		return self._challenge_levels[self.challengeChoice.GetSelection()].challenge_id

	def _resolved_db_path(self):
		"""The database this screen should query, already validated.

		Filled in is not the same as existing: the path may have been saved
		months ago and the file may have moved since. Without this check, the
		field hands a dead path to the theme catalog and the user gets "No
		themes were found in the selected database" -- a message that blames
		the database when the problem is the path.
		"""
		typed = self.databasePathTextCtrl.GetValue().strip()
		return usable_db_path(typed) or default_db_path() or ""

	def _default_database_value(self, saved_path):
		"""What to show in the database field when the screen opens.

		A saved path that no longer exists should not be offered as if it
		were valid: it is better to show the database the add-on actually
		found.
		"""
		return usable_db_path(saved_path) or default_db_path() or ""

	def _resolved_selection(self):
		return resolve_training_selection(
			self._trainer_preset_id(),
			self._challenge_id(),
			custom_theme_text=self._theme_filter_text,
		)

	# -- variation points ----------------------------------------------------

	def _refresh_theme_controls(self):
		"""Re-evaluates what is enabled. Each screen has its own rule."""

	def _theme_picker_prompt(self):
		# Translators: Prompt in the theme picker dialog.
		return _("Choose one or more Lichess themes to use in the custom training plan.")

	# -- theme summary ---------------------------------------------------------

	def _theme_summary_text(self):
		"""The text for the themes field, or None to let the screen decide."""
		resolved = self._resolved_selection()
		if uses_custom_themes(self._trainer_preset_id()):
			theme_slugs = parse_theme_filter(self._theme_filter_text)
			if not theme_slugs:
				# Translators: Shown when no theme filter is applied.
				return _("All themes")
			# Translators: {count} is a number of themes, {themes} their names.
			return _("{count} selected: {themes}").format(
				count=len(theme_slugs),
				themes=describe_theme_filter(self._theme_filter_text),
			)
		labels = describe_theme_filter(resolved.theme_text)
		# Translators: Shown when no theme filter is applied.
		return labels or _("All themes")

	def _update_theme_summary(self):
		self.themeSummaryTextCtrl.SetValue(self._theme_summary_text())

	def _theme_count_sentence(self, resolved):
		"""How many themes the session will use, said in one sentence.

		Exists because the plan decides WHICH themes and the level decides HOW
		HARD, and nothing in the box labels says that -- so the summary has to.
		"""
		count = len(parse_theme_filter(resolved.theme_text))
		if not count:
			# Translators: Part of the training summary when every theme is in play.
			return _("Themes: all of them.")
		# Translators: Part of the training summary. {count} is a number of themes.
		return _("Themes: {count} in play, chosen by the training plan and not by the level.").format(
			count=count,
		)

	def _trainer_summary_text(self):
		"""Plan, level and themes in three lines. The level already carries the rating range in its name."""
		resolved = self._resolved_selection()
		# Translators: Summary of the training setup: plan, level and themes, one per line.
		return _(
			"{plan}. {plan_desc}\n{challenge}. {challenge_desc}\n{theme_text} Minimum popularity {min_popularity}.",
		).format(
			plan=preset_label(resolved.preset),
			plan_desc=preset_description(resolved.preset),
			challenge=challenge_label(resolved.challenge),
			challenge_desc=challenge_description(resolved.challenge),
			theme_text=self._theme_count_sentence(resolved),
			min_popularity=resolved.min_popularity,
		)

	def _update_trainer_summary(self):
		self.trainerSummaryTextCtrl.SetValue(self._trainer_summary_text())

	# -- shared events ---------------------------------------------------------

	def onBrowseDatabase(self, event):
		dialog = wx.FileDialog(
			parent=self,
			# Translators: Title of the file picker for the tactics database.
			message=_("Select tactics database"),
			# Translators: File type filter in the tactics database picker.
			wildcard=_("SQLite databases (*.db;*.sqlite)|*.db;*.sqlite|All files|*.*"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		if dialog.ShowModal() == wx.ID_OK:
			self.databasePathTextCtrl.SetValue(dialog.GetPath())
			self._update_trainer_summary()
			self._update_theme_summary()
		dialog.Destroy()

	def onDownloadDatabase(self, event):
		from .download_dialog import PuzzleDownloadDialog

		current = self._resolved_db_path()
		dialog = PuzzleDownloadDialog(
			self,
			installed_path=Path(current) if current else None,
			on_installed=self._on_database_installed,
		)
		dialog.ShowModal()
		dialog.Destroy()

	def _on_database_installed(self, path):
		# The download always goes to the default folder; the field then
		# points there, even if it previously pointed to a file elsewhere.
		self.databasePathTextCtrl.SetValue(str(path))
		self._update_trainer_summary()
		self._update_theme_summary()

	def onDatabasePathChanged(self, event):
		self._update_trainer_summary()
		self._update_theme_summary()
		event.Skip()

	def onTrainerPresetChanged(self, event):
		self._update_trainer_summary()
		self._update_theme_summary()
		self._refresh_theme_controls()
		event.Skip()

	def onChallengeChanged(self, event):
		self._update_trainer_summary()
		event.Skip()

	def onSelectThemes(self, event):
		db_path = self._resolved_db_path()
		if not db_path:
			gui.messageBox(
				# Translators: Error shown when no database is set yet.
				_("Choose a tactics database before selecting themes."),
				# Translators: Title of the no-database error.
				_("No Database Selected"),
				style=wx.ICON_WARNING,
			)
			return
		if not ensure_theme_catalog_async(db_path, on_done=self._theme_catalog_ready):
			# Translators: Shown the first time themes are requested for a database, while the catalog is built in the background.
			message = _(
				"Preparing the theme catalog for this database. This can take up to a minute; you will hear a message when it is ready.",
			)
			ui.message(message)
			return
		try:
			entries = load_theme_catalog(db_path, allow_rebuild=False)
		except Exception as error:
			gui.messageBox(
				str(error),
				# Translators: Title of the error shown when themes cannot be read.
				_("Could Not Load Themes"),
				style=wx.ICON_ERROR,
			)
			return
		if not entries:
			gui.messageBox(
				# Translators: Shown when the database has no themes at all.
				_("No themes were found in the selected database."),
				# Translators: Title of the no-themes warning.
				_("Themes Not Found"),
				style=wx.ICON_WARNING,
			)
			return
		dialog = wx.MultiChoiceDialog(
			self,
			self._theme_picker_prompt(),
			# Translators: Title of the theme picker dialog.
			_("Select Themes"),
			choices=[
				# Translators: One theme in the picker. {label} is its name, {description} what it means,
				# {count} how many puzzles have it.
				_("{label}: {description} ({count:,} puzzles)").format(
					label=entry.label,
					description=entry.description,
					count=entry.count,
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
				[entries[index].slug for index in dialog.GetSelections()],
			)
			self._update_theme_summary()
			self._refresh_theme_controls()
		dialog.Destroy()

	def _theme_catalog_ready(self, entries):
		# Arrives from the scanning thread; speech can only happen on the main
		# thread.
		if entries:
			# Translators: Announced when the theme catalog finished building in the background.
			wx.CallAfter(ui.message, _("Theme catalog ready. You can select themes now."))
		else:
			# Translators: Announced when the theme catalog could not be built.
			wx.CallAfter(ui.message, _("The theme catalog could not be built."))

	def onClearThemes(self, event):
		self._theme_filter_text = ""
		self._update_theme_summary()
		self._refresh_theme_controls()
