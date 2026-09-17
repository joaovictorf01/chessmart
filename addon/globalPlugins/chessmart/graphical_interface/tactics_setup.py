# coding: utf-8

"""Base comum das duas telas que configuram o treino de táticas.

São duas: o diálogo da sessão (`tactics_dialog`) e o painel de preferências
(`settings_panel`). Elas mostram os mesmos controles -- caminho do banco, plano,
nível, resumo e seleção de temas -- e diferiam só no layout e no que fazem ao
confirmar. Ainda assim eram duas cópias, e a conta chegou: o mesmo erro de ordem
no `__init__` precisou ser corrigido nos dois arquivos, e a correção do resumo
que anunciava a palavra "None" foi feita num e esquecida no outro.

O que mora aqui é o que era idêntico. Cada tela continua dona do próprio
`makeSettings`, porque a ordem dos controles é decisão de interface, e do
próprio `onOk`, porque uma inicia sessão e a outra salva preferências.

Os pontos de variação são explícitos, como métodos que a subclasse sobrescreve:
`_refresh_theme_controls` e `_theme_picker_prompt`.
"""

from pathlib import Path

import wx
import gui
from gui import guiHelper

from ..i18n import _
from ..puzzle_database import get_default_tactic_db_path, usable_db_path
from ..theme_catalog import (
    describe_theme_filter,
    format_theme_filter,
    load_theme_catalog,
    parse_theme_filter,
)
from ..trainer import (
    challenge_label,
    iter_challenge_levels,
    iter_trainer_presets,
    preset_label,
    resolve_training_selection,
    uses_custom_themes,
)


class TacticsSetupMixin:
    """Controles e regras compartilhados pelas telas de configuração de táticas."""

    # -- estado ---------------------------------------------------------------

    def _init_trainer_state(self):
        """Cria os atributos que `makeSettings` vai ler.

        Precisa ser chamado ANTES de `super().__init__()`: o `SettingsDialog` do
        NVDA chama `makeSettings()` de dentro do próprio construtor, então tudo
        que `makeSettings` lê tem que existir antes daquela linha. Foi
        exatamente esse detalhe que quebrou as duas telas.
        """
        self._theme_filter_text = ""
        self._trainer_presets = iter_trainer_presets()
        self._challenge_levels = iter_challenge_levels()

    # -- montagem dos controles ----------------------------------------------

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
        """As duas caixas de combinação: plano e nível.

        Os rótulos entram como parâmetro porque o painel de preferências diz
        "padrão" ("Default training plan") e o diálogo da sessão não.
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

    # -- leitura do estado ----------------------------------------------------

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
        """O banco que esta tela deve consultar, já validado.

        Preenchido não é o mesmo que existente: o caminho pode ter sido salvo
        meses atrás e o arquivo ter mudado de pasta. Sem esta checagem, o campo
        entrega um caminho morto ao catálogo de temas e o usuário recebe "No
        themes were found in the selected database" -- uma mensagem que culpa o
        banco quando o problema é o caminho.
        """
        typed = self.databasePathTextCtrl.GetValue().strip()
        return usable_db_path(typed) or get_default_tactic_db_path() or ""

    def _default_database_value(self, saved_path):
        """O que mostrar no campo do banco ao abrir a tela.

        Um caminho salvo que não existe mais não deve ser oferecido como se
        valesse: é preferível mostrar o banco que o add-on realmente encontrou.
        """
        return usable_db_path(saved_path) or get_default_tactic_db_path() or ""

    def _resolved_selection(self):
        return resolve_training_selection(
            self._trainer_preset_id(),
            self._challenge_id(),
            custom_theme_text=self._theme_filter_text,
        )

    # -- pontos de variação ---------------------------------------------------

    def _refresh_theme_controls(self):
        """Reavalia o que fica habilitado. Cada tela tem a sua regra."""

    def _theme_picker_prompt(self):
        # Translators: Prompt in the theme picker dialog.
        return _("Choose one or more Lichess themes to use in the custom training plan.")

    # -- resumo dos temas -----------------------------------------------------

    def _theme_summary_text(self):
        """O texto do campo de temas, ou None para deixar a tela decidir."""
        resolved = self._resolved_selection()
        if uses_custom_themes(self._trainer_preset_id()):
            theme_slugs = parse_theme_filter(self._theme_filter_text)
            if not theme_slugs:
                # Translators: Shown when no theme filter is applied.
                return _("All themes")
            labels = describe_theme_filter(
                self._theme_filter_text, db_path=self._resolved_db_path()
            )
            # Translators: {count} is a number of themes, {themes} their names.
            return _("{count} selected: {themes}").format(
                count=len(theme_slugs),
                themes=labels or ", ".join(theme_slugs),
            )
        labels = describe_theme_filter(
            resolved.theme_text, db_path=self._resolved_db_path()
        )
        # Translators: Shown when no theme filter is applied.
        return labels or _("All themes")

    def _updateThemeSummary(self):
        self.themeSummaryTextCtrl.SetValue(self._theme_summary_text())

    def _theme_count_sentence(self, resolved):
        """Quantos temas a sessão vai usar, dito em uma frase.

        Existe porque o plano decide QUAIS temas e o nível decide QUÃO DIFÍCIL,
        e nada nos rótulos das caixas diz isso -- então o resumo precisa dizer.
        """
        count = len(parse_theme_filter(resolved.theme_text))
        if not count:
            # Translators: Part of the training summary when every theme is in play.
            return _("Themes: all of them.")
        # Translators: Part of the training summary. {count} is a number of themes.
        return _(
            "Themes: {count} in play, chosen by the training plan and not by the level."
        ).format(count=count)

    # -- eventos compartilhados -----------------------------------------------

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
            self._updateTrainerSummary()
            self._updateThemeSummary()
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
        # O download vai sempre para a pasta padrão; o campo passa a apontar
        # para lá, mesmo que antes apontasse para um arquivo em outro lugar.
        self.databasePathTextCtrl.SetValue(str(path))
        self._updateTrainerSummary()
        self._updateThemeSummary()

    def onDatabasePathChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        event.Skip()

    def onTrainerPresetChanged(self, event):
        self._updateTrainerSummary()
        self._updateThemeSummary()
        self._refresh_theme_controls()
        event.Skip()

    def onChallengeChanged(self, event):
        self._updateTrainerSummary()
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
        try:
            entries = load_theme_catalog(db_path)
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
                # Translators: One theme in the picker. {label} is its name,
                # {count} how many puzzles have it, {slug} its Lichess id.
                _("{label} ({count} puzzles) [{slug}]").format(
                    label=entry.label,
                    count=entry.count,
                    slug=entry.slug,
                )
                for entry in entries
            ],
        )
        selected_slugs = set(parse_theme_filter(self._theme_filter_text))
        selections = [
            index for index, entry in enumerate(entries) if entry.slug in selected_slugs
        ]
        if selections:
            dialog.SetSelections(selections)
        if dialog.ShowModal() == wx.ID_OK:
            self._theme_filter_text = format_theme_filter(
                [entries[index].slug for index in dialog.GetSelections()]
            )
            self._updateThemeSummary()
            self._refresh_theme_controls()
        dialog.Destroy()

    def onClearThemes(self, event):
        self._theme_filter_text = ""
        self._updateThemeSummary()
        self._refresh_theme_controls()
