# coding: utf-8
# pyright: basic

import sys
import functools
import wx
import globalPluginHandler
import gui
import globalVars
import ui
import queueHandler
import winUser
from logHandler import log
from scriptHandler import script
from .paths import import_bundled
from .i18n import _


with import_bundled():
	# Import some packages  replacing NVDA builtin packages
	# with original packages obtained from a Python 3.7 installation
	# to fix some missing sub packages and modules
	if "http" in sys.modules:
		sys.modules.pop("http")
	import http  # noqa: F401 - substitui o pacote do NVDA pela versão completa

	if "xml" in sys.modules:
		sys.modules.pop("xml")
	import xml  # noqa: F401 - idem

	# Normal imports
	import chess

from . import concurrency
from .addon_config import ensure_config_spec
from .time_control import NULL_TIME_CONTROL, ChessTimeControl, NullChessTimeControl
from .chessboard import ChessboardDialog
from .game_elements import GameInfo, ChessVariant
from .graphical_interface.settings_panel import ChessboardSettingsDialog
from .pgn import PGNGame, PGNGameInfo
from .virtual_chessboard import (
	EndgameDrillChessboard,
	EndgameLessonChessboard,
	PGNPlayerChessboard,
	PuzzleChessboard,
)
from .training_session import TrainingSession, default_training_options
from .endgame.drills import opening_fen, random_fen
from .endgame.lessons import EndgameLesson


class ChessboardMenu(wx.Menu):
	def __init__(self, global_plugin_object):
		super().__init__()
		self.global_plugin_object = global_plugin_object
		# Append the menu items
		new_game_item = self.Append(wx.ID_ANY, _("&New Game..."), _("Start a new chess game"))
		tactics_item = self.Append(
			wx.ID_ANY,
			_("&Tactics..."),
			_("Open tactics from the Lichess tactics database"),
		)
		random_puzzle_item = self.Append(wx.ID_ANY, _("&Random Puzzle"), _("Play a random puzzle"))
		endgames_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens the endgame drills.
			_("&Endgames..."),
			_("Practice elementary endgames against the engine"),
		)
		study_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens the study log.
			_("&My Study..."),
			_("How much and how you studied, by day, and how far the endgame lessons go"),
		)
		replay_pgn_file_item = self.Append(
			wx.ID_ANY,
			_("&Replay PGN File..."),
			_("Load an replay a portable game notation (.pgn) file"),
		)
		self.AppendSeparator()
		settings_item = self.Append(
			wx.ID_ANY,
			_("&Settings..."),
			_("Open Chessboard settings"),
		)
		# Attach this submenu under NVDA's Tools menu.
		assert gui.mainFrame is not None
		self.itemHandle = gui.mainFrame.sysTrayIcon.toolsMenu.AppendSubMenu(
			self,
			_("&Chessboard"),
			_("Open a chess game, tactics session, replay, or settings"),
		)
		# Bind menu items to events
		self.Bind(wx.EVT_MENU, self.onNewGame, new_game_item)
		self.Bind(wx.EVT_MENU, self.onTactics, tactics_item)
		self.Bind(wx.EVT_MENU, self.onRandomPuzzle, random_puzzle_item)
		self.Bind(wx.EVT_MENU, self.onEndgames, endgames_item)
		self.Bind(wx.EVT_MENU, self.onStudyLog, study_item)
		self.Bind(wx.EVT_MENU, self.onReplayPGN, replay_pgn_file_item)
		self.Bind(wx.EVT_MENU, self.onSettings, settings_item)

	def onNewGame(self, event):
		from .graphical_interface.new_game_dialog import NewGameOptionsDialog

		dialog = NewGameOptionsDialog(gui.mainFrame, callback=self.create_new_game)
		gui.runScriptModalDialog(dialog)

	def create_new_game(self, vboard_cls, game_info):
		self.global_plugin_object.initialize_and_show_chessboard_dialog(vboard_cls, game_info)

	def onTactics(self, event):
		from .graphical_interface.tactics_dialog import TacticsOptionsDialog

		if not self._ensure_puzzle_database():
			return
		dialog = TacticsOptionsDialog(
			gui.mainFrame,
			callback=self.open_tactics_session,
		)
		gui.runScriptModalDialog(dialog)

	def open_tactics_session(self, options):
		session = TrainingSession(options)
		try:
			session.ensure_ready()
		except FileNotFoundError:
			gui.messageBox(
				_(
					"The tactics database was not found. Use Browse in the tactics dialog to point at your puzzle database, or place it in the add-on's data folder as puzzles.db.",
				),
				_("Tactics Database Not Found"),
				style=wx.ICON_ERROR,
			)
			return
		except LookupError as error:
			gui.messageBox(
				str(error),
				_("No Tactics Found"),
				style=wx.ICON_WARNING,
			)
			return
		self.open_training_session(session)

	def _ensure_puzzle_database(self) -> bool:
		"""Without a puzzle database, offer the download before proceeding."""
		if default_training_options().db_path:
			return True
		answer = gui.messageBox(
			# Translators: Asked when tactics are opened and no puzzle database is installed yet.
			_(
				"Tactics need a puzzle database, which is downloaded once (about 76 MB for the light version). Download it now?",
			),
			_("Puzzle Database"),
			style=wx.YES_NO | wx.ICON_QUESTION,
		)
		if answer != wx.YES:
			return False
		from .graphical_interface.download_dialog import PuzzleDownloadDialog

		dialog = PuzzleDownloadDialog(gui.mainFrame)
		result = dialog.ShowModal()
		dialog.Destroy()
		return result == wx.ID_OK

	def onRandomPuzzle(self, event):
		"""A session using the options saved in the configuration, without going through the dialog."""
		if not self._ensure_puzzle_database():
			return
		session = TrainingSession(default_training_options())
		try:
			session.ensure_ready()
		except FileNotFoundError:
			gui.messageBox(
				_(
					"The tactics database was not found. Choose a valid database in Chessboard settings first.",
				),
				_("Tactics Database Not Found"),
				style=wx.ICON_ERROR,
			)
			return
		except LookupError as error:
			gui.messageBox(str(error), _("No Tactics Found"), style=wx.ICON_WARNING)
			return
		self.open_training_session(session)

	def onEndgames(self, event):
		from .graphical_interface.endgame_dialog import EndgameDialog

		dialog = EndgameDialog(gui.mainFrame, callback=self.open_endgame)
		gui.runScriptModalDialog(dialog)

	def open_endgame(self, lesson: EndgameLesson, index: int, time_control: ChessTimeControl):
		"""Opens what the dialog chose: a mate drill or a lesson position."""
		if lesson.drill is not None:
			fen = (
				opening_fen(lesson.drill)
				if index == 0
				else random_fen(lesson.drill, accept=self._drill_position_is_won)
			)
			self.open_endgame_drill(lesson, time_control, fen)
		else:
			self.open_endgame_lesson(lesson, index)

	def _drill_position_is_won(self, board) -> bool:
		"""Does the tablebase say White wins? Without a tablebase, nobody can say, and the draw falls back to the examples."""
		from .endgame import judge, tablebase

		try:
			tables = tablebase.open_tablebase()
		except Exception:
			return False
		verdict = judge.probe(tables, board)
		return verdict is not None and verdict.wdl > 0

	def open_endgame_drill(self, lesson: EndgameLesson, time_control: ChessTimeControl, fen: str):
		"""The mate drill against the engine, at maximum strength.

		The board receives this same function as `new_position_callback`, with
		a newly drawn position and a new clock: Control+N closes the board and
		comes back here. The clock is recreated because `ChessTimeControl`
		keeps track of the clocks already used; with no clock, the null one
		serves again.
		"""
		drill = lesson.drill
		assert drill is not None
		if isinstance(time_control, NullChessTimeControl):
			next_clock = time_control
		else:
			next_clock = ChessTimeControl(*time_control.astuple())
		game_info = GameInfo(
			pychess_board=chess.Board(fen),
			variant=ChessVariant.STANDARD,
			time_control=time_control,
			prospective=chess.WHITE,
			vboard_kwargs=dict(
				drill=drill,
				lesson_id=lesson.lesson_id,
				# Maximum strength: perfect defense is what makes the technique worth learning.
				uci_options={},
				uci_time_limit=0.5,
				new_position_callback=functools.partial(
					self.open_endgame_drill,
					lesson,
					next_clock,
					random_fen(drill, accept=self._drill_position_is_won),
				),
			),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(EndgameDrillChessboard, game_info)

	def open_endgame_lesson(self, lesson: EndgameLesson, index: int):
		"""A lesson position, with no clock; Control+N opens the next one, Control+R repeats this one."""
		position = lesson.positions[index]
		next_callback = None
		if index + 1 < len(lesson.positions):
			next_callback = functools.partial(self.open_endgame_lesson, lesson, index + 1)
		game_info = GameInfo(
			pychess_board=chess.Board(position.fen),
			variant=ChessVariant.STANDARD,
			time_control=NULL_TIME_CONTROL,
			prospective=position.player,
			vboard_kwargs=dict(
				lesson=lesson,
				position=position,
				uci_options={},
				uci_time_limit=0.5,
				next_callback=next_callback,
				restart_callback=functools.partial(self.open_endgame_lesson, lesson, index),
			),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(EndgameLessonChessboard, game_info)

	def onStudyLog(self, event):
		from .graphical_interface.study_dialog import StudyLogDialog

		assert gui.mainFrame is not None
		dialog = StudyLogDialog(gui.mainFrame)
		gui.runScriptModalDialog(dialog)

	def onSettings(self, event):
		dialog = ChessboardSettingsDialog(gui.mainFrame)
		gui.runScriptModalDialog(dialog)

	def open_training_session(self, session):
		game_info = GameInfo(
			pychess_board=chess.Board(),
			variant=ChessVariant.STANDARD,
			time_control=NULL_TIME_CONTROL,
			prospective=None,
			vboard_kwargs=dict(session=session),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(
			PuzzleChessboard,
			game_info,
		)

	def onReplayPGN(self, event):
		openFileDialog = wx.FileDialog(
			parent=gui.mainFrame,
			# Translators: Title of the dialog that opens a PGN file.
			message=_("Open PGN File"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the PGN open dialog.
			wildcard=_("Portable Game Notation *.pgn | *.pgn"),
			style=wx.FD_OPEN,
		)
		gui.runScriptModalDialog(openFileDialog, functools.partial(self.list_games_in_pgn, openFileDialog))

	def list_games_in_pgn(self, dialog, res):
		if res != wx.ID_OK:
			return
		filepath = dialog.GetPath().strip()
		if not filepath:
			return
		try:
			games = tuple(PGNGameInfo.game_info_from_pgn_filename(filepath))
		except (OSError, UnicodeDecodeError, ValueError) as error:
			# A file that cannot be read or that python-chess refuses (truncated,
			# not a PGN at all): say so instead of leaving a traceback in the log.
			log.warning("chessmart: could not read PGN file %s: %s", filepath, error)
			self._say_pgn_unreadable(error)
			return
		if not games:
			queueHandler.queueFunction(
				# Translators: Spoken when the chosen PGN file has no games.
				queueHandler.eventQueue,
				ui.message,
				_("The file contains no games"),
			)
		elif len(games) == 1:
			self.open_pgn_game(games[0])
		else:
			choiceDg = wx.SingleChoiceDialog(
				gui.mainFrame,
				_("The file contains the following games"),
				_("Select Game"),
				choices=[g.description for g in games],
			)
			gui.runScriptModalDialog(
				choiceDg,
				functools.partial(self.on_pgn_game_chosen, filepath, choiceDg, games),
			)

	def on_pgn_game_chosen(self, filepath, dialog, games, res):
		if res != wx.ID_OK:
			return
		selected_game_info = games[dialog.GetSelection()]
		self.open_pgn_game(selected_game_info)

	def _say_pgn_unreadable(self, error):
		queueHandler.queueFunction(
			queueHandler.eventQueue,
			ui.message,
			# Translators: Spoken when the chosen PGN file cannot be read, followed by the error.
			_("Could not read the PGN file. Details: {error}").format(error=error),
		)

	def open_pgn_game(self, game_info):
		try:
			pgn_game = PGNGame.from_game_info(game_info)
		except (OSError, UnicodeDecodeError, ValueError) as error:
			log.warning("chessmart: could not read PGN game %s: %s", game_info.description, error)
			self._say_pgn_unreadable(error)
			return
		chess_new_game_info = GameInfo(
			variant=None,
			time_control=NULL_TIME_CONTROL,
			pychess_board=None,
			prospective=None,
			vboard_kwargs=dict(game=pgn_game, use_visuals=True, visual_arrows=True),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(
			PGNPlayerChessboard,
			chess_new_game_info,
		)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: Category of the add-on's scripts in the Input Gestures dialog.
	scriptCategory = _("Chessmart")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._active_board_dialogs = {}
		# The following is the GUI part
		if not globalVars.appArgs.secure:
			ensure_config_spec()
			self.chessboard_menu = ChessboardMenu(self)

	# -- shortcuts ----------------------------------------------------------------
	# The menu lives under NVDA > Tools > Chessmart; daily training shouldn't
	# require three levels of menu. Only Tactics has a default key; the
	# others the user enables in Input Gestures, under the Chessmart category.

	def _menu_action(self, handler_name: str):
		menu = getattr(self, "chessboard_menu", None)
		if menu is None:
			# Translators: Spoken when a shortcut is used while NVDA runs in secure mode.
			ui.message(_("Chessmart is not available in secure mode."))
			return
		wx.CallAfter(getattr(menu, handler_name), None)

	@script(
		# Translators: Description of the shortcut that opens the tactics trainer.
		description=_("Opens Chessmart tactics"),
		gesture="kb:NVDA+alt+x",
	)
	def script_open_tactics(self, gesture):
		self._menu_action("onTactics")

	@script(
		# Translators: Description of the shortcut that starts a random puzzle.
		description=_("Starts a random Chessmart puzzle with the saved training setup"),
	)
	def script_random_puzzle(self, gesture):
		self._menu_action("onRandomPuzzle")

	@script(
		# Translators: Description of the shortcut that opens the endgame lessons.
		description=_("Opens Chessmart endgames"),
	)
	def script_open_endgames(self, gesture):
		self._menu_action("onEndgames")

	@script(
		# Translators: Description of the shortcut that opens the study log.
		description=_("Opens Chessmart My Study"),
	)
	def script_open_study(self, gesture):
		self._menu_action("onStudyLog")

	@script(
		# Translators: Description of the shortcut that starts a new game.
		description=_("Starts a new Chessmart game"),
	)
	def script_new_game(self, gesture):
		self._menu_action("onNewGame")

	def terminate(self):
		chessboard_menu = getattr(self, "chessboard_menu", None)
		if chessboard_menu is not None and gui.mainFrame is not None:
			gui.mainFrame.sysTrayIcon.toolsMenu.DestroyItem(chessboard_menu.itemHandle)
		try:
			concurrency.terminate()
			for cdlg in list(self._active_board_dialogs.values()):
				cdlg.Destroy()
		except Exception:
			log.exception("Failed to terminate concurrency primitives")

	def initialize_and_show_chessboard_dialog(self, vboard_cls, game_info):
		chessboard_dialog = ChessboardDialog.from_game_info(vboard_cls, game_info)
		chessboard_dialog.on_closed = self._forget_board_dialog
		self._active_board_dialogs[chessboard_dialog.GetHandle()] = chessboard_dialog
		chessboard_dialog.Show()
		winUser.setForegroundWindow(chessboard_dialog.GetHandle())

	def _forget_board_dialog(self, dialog):
		"""Called when the window closes: without this, every game would stay in the list forever."""
		self._active_board_dialogs.pop(dialog.GetHandle(), None)

	def event_gainFocus(self, obj, nextHandler):
		nextHandler()
		board_dialog = self._active_board_dialogs.get(obj.windowHandle)
		if (not board_dialog) or (not board_dialog.IsActive()):
			return
		if board_dialog.IsShown():
			queueHandler.queueFunction(queueHandler.eventQueue, board_dialog.set_focus_to_board)
