# coding: utf-8
# pyright: basic

import random
import wx
import gui
from gui import guiHelper
from ..chessboard import GameInfo
from ..paths import import_bundled
from ..i18n import _
from .components import EnumRadioBox, EnumChoice
from ..game_elements import PlayMode, TimeControl, ChessVariant, PlayerColor
from ..time_control import ChessTimeControl
from .messages import show_error

with import_bundled():
	import chess


class NewGameOptionsDialog(gui.SettingsDialog):
	# Translators: Title of the new game dialog.
	title = _("New Game")

	def __init__(self, *args, callback, fen=None, **kwargs):
		# Before super(): NVDA's SettingsDialog builds the controls inside its constructor.
		# A FEN given here fills the starting position, and the side to move is offered as the player's.
		self._initial_fen = fen
		super().__init__(*args, **kwargs)
		self.callback = callback
		self._uci_options = self._uci_time_limit = None

	def makeSettings(self, sizer):
		sizer.SetOrientation(wx.HORIZONTAL)
		mainSizerHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		primaryOptionsSizerHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		secondaryOptionsSizerHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		intro_label = wx.StaticText(
			self,
			-1,
			# Translators: Intro text of the new game dialog.
			_("Choose the play mode, starting position, and time control."),
			style=wx.ST_ELLIPSIZE_MIDDLE,
		)
		intro_label.Wrap(self.GetSize().Width)
		primaryOptionsSizerHelper.addItem(intro_label)
		# Play mode
		self.playModeRadioBox = EnumRadioBox(
			self,
			wx.ID_ANY,
			# Translators: Label of the play mode choice in the new game dialog.
			label=_("Play Mode"),
			choice_enum=PlayMode,
			majorDimension=0,
			style=wx.RA_SPECIFY_ROWS,
		)
		primaryOptionsSizerHelper.addItem(self.playModeRadioBox)
		# Starting position
		# Translators: Label of the chess variant choice in the new game dialog.
		chessVariantLabel = wx.StaticText(self, -1, _("Variant"))
		self.chessVariantChoice = EnumChoice(
			self,
			wx.ID_ANY,
			choice_enum=ChessVariant,
		)
		primaryOptionsSizerHelper.addItem(chessVariantLabel)
		primaryOptionsSizerHelper.addItem(self.chessVariantChoice)
		# Time Control
		# Translators: Label of the time control choice in the new game dialog.
		timeControlLabel = wx.StaticText(self, -1, _("Time Control"))
		self.timeControlRadioBox = EnumChoice(
			self,
			wx.ID_ANY,
			choice_enum=TimeControl,
		)
		guiHelper.associateElements(timeControlLabel, self.timeControlRadioBox)
		primaryOptionsSizerHelper.addItem(timeControlLabel)
		primaryOptionsSizerHelper.addItem(self.timeControlRadioBox)
		# Player color
		self.playerColorRadioBox = EnumRadioBox(
			self,
			wx.ID_ANY,
			# Translators: Label of the side choice in the new game dialog.
			label=_("Play As"),
			choice_enum=PlayerColor,
			majorDimension=1,
			style=wx.RA_SPECIFY_ROWS,
		)
		secondaryOptionsSizerHelper.addItem(self.playerColorRadioBox)
		# Custom starting FEN
		# Translators: Label of the starting position field (FEN notation) in the new game dialog.
		customFENLabel = wx.StaticText(self, -1, _("Starting FEN"))
		self.customStartingFEN = wx.TextCtrl(self, -1)
		guiHelper.associateElements(customFENLabel, self.customStartingFEN)
		secondaryOptionsSizerHelper.addItem(customFENLabel)
		secondaryOptionsSizerHelper.addItem(self.customStartingFEN)
		if self._initial_fen:
			self.customStartingFEN.SetValue(self._initial_fen)
			turn = chess.Board(self._initial_fen).turn
			self.playerColorRadioBox.SetSelectionByValue(
				PlayerColor.WHITE if turn == chess.WHITE else PlayerColor.BLACK
			)
		# Custom Time Control
		# Translators: Time control choice: the user types their own, e.g. 10+5.
		customTimeControlLable = wx.StaticText(self, -1, _("Custom Time Control"))
		self.customTimeControlTextCtrl = wx.TextCtrl(self, -1)
		guiHelper.associateElements(customTimeControlLable, self.customTimeControlTextCtrl)
		secondaryOptionsSizerHelper.addItem(customTimeControlLable)
		secondaryOptionsSizerHelper.addItem(self.customTimeControlTextCtrl)
		# Engine options
		# Translators: Button of the new game dialog that opens the engine options.
		self.engineOptionsButton = wx.Button(self, -1, _("Engine &Options..."))
		secondaryOptionsSizerHelper.addItem(self.engineOptionsButton)
		# Use visuals
		# Translators: Checkbox of the new game dialog: draw the focused square on the board picture.
		self.useVisualsCheckbox = wx.CheckBox(self, -1, label=_("Visually highlight board interactions"))
		secondaryOptionsSizerHelper.addItem(self.useVisualsCheckbox)
		# Add sizers to the main sizer
		mainSizerHelper.addItem(primaryOptionsSizerHelper)
		mainSizerHelper.addItem(secondaryOptionsSizerHelper)
		# Bind events
		self.Bind(wx.EVT_RADIOBOX, self.onPlayModeRadio, self.playModeRadioBox)
		self.Bind(wx.EVT_CHOICE, self.onTimeControlRadio, self.timeControlRadioBox)
		self.Bind(wx.EVT_BUTTON, self.onEngineOptions, self.engineOptionsButton)

	def postInit(self):
		self.playModeRadioBox.SetFocus()
		self.customTimeControlTextCtrl.Enable(self.timeControlRadioBox.SelectedValue is TimeControl.CUSTOM)
		initial_play_mode = self.playModeRadioBox.GetSelectedValue()
		self.engineOptionsButton.Enable(initial_play_mode is PlayMode.HUMAN_VERSUS_COMPUTER)

	def get_game_info(self):
		try:
			time_control = self._get_time_control()
		except ValueError:
			show_error(
				# Translators: Error about an invalid time control. Keep the line break and the 10+5 notation.
				_(
					"Please enter a valid time control string.\nExample: 10+5 for a 10 minutes base time with 5 seconds increment after each move.",
				),
				# Translators: Title of the error about an invalid time control.
				_("Invalid Time Control String"),
			)
			return
		try:
			pychess_board = self._get_pychess_board()
		except ValueError:
			show_error(
				# Translators: Error about an invalid starting position; {fen} is an example. Keep the line breaks.
				_("Please enter a valid starting FEN.\nExample:\n{fen}\nfor a standard starting FEN.").format(
					fen=chess.STARTING_FEN,
				),
				# Translators: Title of the error about an invalid starting position.
				_("Invalid FEN String"),
			)
			return
		game_info = GameInfo(
			pychess_board=pychess_board,
			variant=self.chessVariantChoice.GetSelectedValue(),
			time_control=time_control,
			prospective=self.playerColorRadioBox.GetSelectedValue().get_color(),
		)
		game_info.vboard_kwargs["use_visuals"] = self.useVisualsCheckbox.IsChecked()
		if self.playModeRadioBox.GetSelectedValue() == PlayMode.HUMAN_VERSUS_COMPUTER:
			game_info.vboard_kwargs.update(
				dict(
					uci_options=self._uci_options,
					uci_time_limit=self._uci_time_limit,
				),
			)
		return game_info

	def onOk(self, event):
		game_info = self.get_game_info()
		if game_info is None:
			# The message box already explained the invalid time control or FEN;
			# keep the dialog open so the value can be corrected.
			return
		vboard_cls = self.playModeRadioBox.GetSelectedValue().get_board_class()
		self.callback(vboard_cls, game_info)
		super().onOk(event)

	def onPlayModeRadio(self, event):
		selectedValue = event.GetEventObject().GetSelectedValue()
		self.playerColorRadioBox.Enable(selectedValue is not PlayMode.HUMAN_VERSUS_HUMAN)
		self.engineOptionsButton.Enable(selectedValue is PlayMode.HUMAN_VERSUS_COMPUTER)

	def onTimeControlRadio(self, event):
		if event.GetEventObject().GetSelectedValue() is not TimeControl.CUSTOM:
			self.customTimeControlTextCtrl.SetValue("")
			self.customTimeControlTextCtrl.Enable(False)
		else:
			self.customTimeControlTextCtrl.Enable()

	def onEngineOptions(self, event):
		saved_options = {}
		if self._uci_options and "UCI_Elo" in self._uci_options:
			saved_options["engine_elo_rating"] = self._uci_options["UCI_Elo"]
		if self._uci_time_limit is not None:
			saved_options["engine_limit"] = self._uci_time_limit
		dialog = UCIEngineOptionsDialog(self, saved_options=saved_options)
		dialog.Show()

	def set_engine_options(self, options):
		self._uci_options, self._uci_time_limit = options

	def _get_pychess_board(self):
		selected_variant = self.chessVariantChoice.GetSelectedValue()
		board_cls = selected_variant.get_board()
		custom_starting_FEN = self.customStartingFEN.GetValue().strip()
		if custom_starting_FEN:
			return board_cls(custom_starting_FEN)
		elif selected_variant is ChessVariant.CHESS960:
			return chess.Board.from_chess960_pos(random.randint(0, 959))
		else:
			return board_cls()

	def _get_time_control(self):
		time_control = self.timeControlRadioBox.GetSelectedValue().get_time_control()
		if time_control is None:
			time_control = ChessTimeControl.from_time_control_notation(
				self.customTimeControlTextCtrl.GetValue(),
			)
		return time_control


class UCIEngineOptionsDialog(gui.SettingsDialog):
	# Translators: Title of the engine options dialog.
	title = _("Engine Options")

	def __init__(self, *args, saved_options=None, **kwargs):
		self.saved_options = saved_options or {}
		super().__init__(*args, **kwargs)

	def makeSettings(self, sizer):
		mainSizerHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		primaryOptionsSizerHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: Label of the engine strength field, in Elo points.
		engineSkillLevelLabel = wx.StaticText(self, -1, _("Engine Strength (ELO Rating)"))
		self.engineSkillLevel = wx.SpinCtrl(self, -1, min=1350, max=2850)
		guiHelper.associateElements(engineSkillLevelLabel, self.engineSkillLevel)
		primaryOptionsSizerHelper.addItem(engineSkillLevelLabel)
		primaryOptionsSizerHelper.addItem(self.engineSkillLevel)
		# Thinking time
		# Translators: Label of the engine thinking time field.
		thinkingLimitLabel = wx.StaticText(self, -1, _("Engine Thinking Time (in seconds)"))
		self.thinkingLimitSpin = wx.SpinCtrl(self, -1, min=1, max=300)
		guiHelper.associateElements(thinkingLimitLabel, self.thinkingLimitSpin)
		primaryOptionsSizerHelper.addItem(thinkingLimitLabel)
		primaryOptionsSizerHelper.addItem(self.thinkingLimitSpin)
		mainSizerHelper.addItem(primaryOptionsSizerHelper)

	def postInit(self):
		self.engineSkillLevel.SetValue(self.saved_options.get("engine_elo_rating", 1350))
		self.thinkingLimitSpin.SetValue(self.saved_options.get("engine_limit", 2))
		self.engineSkillLevel.SetFocus()

	def onOk(self, event):
		# The parent is always NewGameOptionsDialog, which has set_engine_options.
		self.Parent.set_engine_options(self.get_options())  # pyright: ignore[reportAttributeAccessIssue]
		super().onOk(event)

	def get_options(self):
		uci_options = dict(
			UCI_LimitStrength=True,
			UCI_Elo=self.engineSkillLevel.GetValue(),
		)
		return (
			uci_options,
			self.thinkingLimitSpin.GetValue(),
		)
