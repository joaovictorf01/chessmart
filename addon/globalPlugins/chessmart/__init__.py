# coding: utf-8
# pyright: basic

import functools
import os
import api
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
	import chess
	import chess.pgn

from . import concurrency
from .addon_config import ensure_config_spec, get_games_folder, get_lichess_user, save_lichess_user
from .time_control import NULL_TIME_CONTROL, ChessTimeControl, NullChessTimeControl
from .chessboard import ChessboardDialog
from .game_elements import GameInfo, ChessVariant
from .graphical_interface.settings_panel import ChessboardSettingsDialog
from .game_tree import GameTree, write_pgn
from .lichess_import import fetch_game, imported_filename, parse_reference
from .tactic.download import DownloadError
from .pgn import PGNGame, PGNGameInfo, read_game_at
from .virtual_chessboard import (
	AnalysisChessboard,
	PositionEditorChessboard,
	EndgameDrillChessboard,
	EndgameLessonChessboard,
	PGNPlayerChessboard,
	PuzzleChessboard,
)
from .training_session import TrainingSession, default_training_options
from .endgame.drills import opening_fen, random_fen
from .endgame.lessons import EndgameLesson
from .graphical_interface.messages import ask_yes_no, run_modal, show_error, show_warning


class ChessboardMenu(wx.Menu):
	def __init__(self, global_plugin_object):
		super().__init__()
		self.global_plugin_object = global_plugin_object
		# Append the menu items
		# Translators: Menu item that opens the new game dialog, and its help text.
		new_game_item = self.Append(wx.ID_ANY, _("&New Game..."), _("Start a new chess game"))
		tactics_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens the tactics trainer, and its help text.
			_("&Tactics..."),
			_("Open tactics from the Lichess tactics database"),
		)
		# Translators: Menu item that starts a puzzle with the saved training setup, and its help text.
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
			# Translators: Menu item that replays a PGN file, and its help text.
			_("&Replay PGN File..."),
			_("Load an replay a portable game notation (.pgn) file"),
		)
		record_game_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens an empty analysis board to record a game.
			_("Record and &Analyse Game"),
			# Translators: Help text of the menu item that opens an empty analysis board.
			_(
				"Enter a game move by move, with variations, comments and marks, and save it in your games folder"
			),
		)
		board_editor_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens the board editor.
			_("&Board Editor"),
			# Translators: Help text of the board editor menu item.
			_("Set up a position square by square, check it, and analyse it"),
		)
		import_lichess_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that downloads a game from Lichess and opens it on the analysis board.
			_("&Import Lichess Game..."),
			# Translators: Help text of the menu item that imports a Lichess game.
			_(
				"Download a game from Lichess, with the clock of every move, and open it on the analysis board"
			),
		)
		analyse_pgn_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens a PGN file on the analysis board.
			_("Analyse PGN &File..."),
			# Translators: Help text of the menu item that opens a PGN file on the analysis board.
			_("Open a saved game on the analysis board to go through it and add variations and comments"),
		)
		self.AppendSeparator()
		settings_item = self.Append(
			wx.ID_ANY,
			# Translators: Menu item that opens the add-on settings, and its help text.
			_("&Settings..."),
			_("Open Chessboard settings"),
		)
		# Attach this submenu under NVDA's Tools menu.
		assert gui.mainFrame is not None
		self.itemHandle = gui.mainFrame.sysTrayIcon.toolsMenu.AppendSubMenu(
			self,
			# Translators: Name of the add-on submenu under NVDA's Tools menu.
			_("&Chessboard"),
			# Translators: Help text of the add-on submenu.
			_("Open a chess game, tactics session, replay, or settings"),
		)
		# Bind menu items to events
		self.Bind(wx.EVT_MENU, self.onNewGame, new_game_item)
		self.Bind(wx.EVT_MENU, self.onTactics, tactics_item)
		self.Bind(wx.EVT_MENU, self.onRandomPuzzle, random_puzzle_item)
		self.Bind(wx.EVT_MENU, self.onEndgames, endgames_item)
		self.Bind(wx.EVT_MENU, self.onStudyLog, study_item)
		self.Bind(wx.EVT_MENU, self.onReplayPGN, replay_pgn_file_item)
		self.Bind(wx.EVT_MENU, self.onRecordGame, record_game_item)
		self.Bind(wx.EVT_MENU, self.onAnalysePGN, analyse_pgn_item)
		self.Bind(wx.EVT_MENU, self.onImportLichess, import_lichess_item)
		self.Bind(wx.EVT_MENU, self.onBoardEditor, board_editor_item)
		self.Bind(wx.EVT_MENU, self.onSettings, settings_item)

	def onNewGame(self, event, fen=None):
		from .graphical_interface.new_game_dialog import NewGameOptionsDialog

		dialog = NewGameOptionsDialog(gui.mainFrame, callback=self.create_new_game, fen=fen)
		run_modal(dialog)

	def new_game_from(self, fen):
		"""The analysis board's "Play from here": the New Game dialog on that position."""
		wx.CallAfter(self.onNewGame, None, fen)

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
		run_modal(dialog)

	def open_tactics_session(self, options):
		self._open_session(
			options,
			# Translators: Error when the tactics dialog finds no puzzle database. Keep "puzzles.db" as is.
			_(
				"The tactics database was not found. Use Browse in the tactics dialog to point at your puzzle database, or place it in the add-on's data folder as puzzles.db.",
			),
		)

	def _open_session(self, options, missing_database_message):
		"""Opens a tactics session, or says why it cannot: no database, or no puzzle for these options."""
		session = TrainingSession(options)
		try:
			session.ensure_ready()
		except FileNotFoundError:
			# Translators: Title of the error shown when the puzzle database is missing.
			show_error(missing_database_message, _("Tactics Database Not Found"))
			return
		except LookupError as error:
			# Translators: Title of the warning shown when no puzzle matches the options.
			show_warning(str(error), _("No Tactics Found"))
			return
		self.open_training_session(session)

	def _ensure_puzzle_database(self) -> bool:
		"""Without a puzzle database, offer the download before proceeding."""
		if default_training_options().db_path:
			return True
		answer = ask_yes_no(
			# Translators: Asked when tactics are opened and no puzzle database is installed yet.
			_(
				"Tactics need a puzzle database, which is downloaded once. The next dialog gives the size of each. Download it now?",
			),
			# Translators: Title of the message about the puzzle database.
			_("Puzzle Database"),
		)
		if not answer:
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
		self._open_session(
			default_training_options(),
			# Translators: Error when Random Puzzle finds no puzzle database.
			_("The tactics database was not found. Choose a valid database in Chessboard settings first."),
		)

	def onEndgames(self, event):
		from .graphical_interface.endgame_dialog import EndgameDialog

		dialog = EndgameDialog(gui.mainFrame, callback=self.open_endgame)
		run_modal(dialog)

	def open_endgame(self, lesson: EndgameLesson, index: int, time_control: ChessTimeControl):
		"""Opens what the dialog chose: a mate drill or a lesson position."""
		if lesson.drill is not None:
			fen = opening_fen(lesson.drill) if index == 0 else self._random_drill_fen(lesson.drill)
			self.open_endgame_drill(lesson, time_control, fen)
		else:
			self.open_endgame_lesson(lesson, index)

	def _random_drill_fen(self, drill) -> str:
		"""A random position of the drill, accepted only when the tablebase says White wins.

		The tablebase is opened once for the whole draw: `random_fen` may try
		up to 2000 candidates, and opening scans the syzygy folder every time.
		Without a tablebase nobody can say, and the draw falls back to the examples.
		"""
		from .endgame import judge, tablebase

		try:
			tables = tablebase.open_tablebase()
		except Exception as error:
			log.warning("chessmart: could not open the tablebase for the drill draw: %s", error)
			tables = None
		if tables is None or not drill.needs_judge:
			# Mate drills (queen, rook, ...) are won from any legal position and
			# need no judge; a drill that needs one falls back to its examples.
			if tables is not None:
				tables.close()
			return random_fen(drill)

		def is_won(board) -> bool:
			verdict = judge.probe(tables, board)
			return verdict is not None and verdict.wdl > 0

		try:
			return random_fen(drill, accept=is_won)
		finally:
			tables.close()

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
					self._random_drill_fen(drill),
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
		run_modal(dialog)

	def onSettings(self, event):
		dialog = ChessboardSettingsDialog(gui.mainFrame)
		run_modal(dialog)

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

	def onRecordGame(self, event):
		self.open_analysis_board(GameTree())

	def onAnalysePGN(self, event):
		folder = get_games_folder()
		openFileDialog = wx.FileDialog(
			parent=gui.mainFrame,
			# Translators: Title of the dialog that opens a PGN file on the analysis board.
			message=_("Open Game for Analysis"),
			defaultDir=folder if os.path.isdir(folder) else wx.GetUserHome(),
			wildcard=_("Portable Game Notation *.pgn | *.pgn"),
			style=wx.FD_OPEN,
		)
		run_modal(openFileDialog, functools.partial(self._on_analysis_file_chosen, openFileDialog))

	def _on_analysis_file_chosen(self, dialog, res):
		if res != wx.ID_OK:
			return
		filepath = dialog.GetPath().strip()
		if not filepath:
			return
		try:
			games = tuple(PGNGameInfo.game_info_from_pgn_filename(filepath))
		except (OSError, UnicodeDecodeError, ValueError) as error:
			log.warning("chessmart: could not read PGN file %s: %s", filepath, error)
			self._say_pgn_unreadable(error)
			return
		if not games:
			# Translators: Spoken when the chosen PGN file has no games.
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("The file contains no games"))
			return
		if len(games) == 1:
			self._open_game_for_analysis(games[0], single_game_file=True)
			return
		choiceDg = wx.SingleChoiceDialog(
			gui.mainFrame,
			# Translators: Prompt of the list of games in a PGN file.
			_("The file contains the following games"),
			# Translators: Title of the list of games in a PGN file.
			_("Select Game"),
			choices=[g.description for g in games],
		)
		run_modal(choiceDg, functools.partial(self._on_analysis_game_chosen, choiceDg, games))

	def _on_analysis_game_chosen(self, dialog, games, res):
		if res == wx.ID_OK:
			self._open_game_for_analysis(games[dialog.GetSelection()], single_game_file=False)

	def _open_game_for_analysis(self, game_info, single_game_file):
		try:
			game = read_game_at(game_info.filename, game_info.offset)
		except (OSError, UnicodeDecodeError, ValueError) as error:
			log.warning("chessmart: could not read PGN game %s: %s", game_info.description, error)
			self._say_pgn_unreadable(error)
			return
		# A file with one game is saved back in place; a game out of a collection
		# is saved as a new file, so the rest of the collection is never rewritten.
		self.open_analysis_board(GameTree(game), source_path=game_info.filename if single_game_file else None)

	def onBoardEditor(self, event):
		chess_new_game_info = GameInfo(
			variant=ChessVariant.STANDARD,
			time_control=NULL_TIME_CONTROL,
			pychess_board=None,
			prospective=chess.WHITE,
			vboard_kwargs=dict(on_analyse=self._analyse_edited_position, use_visuals=True),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(
			PositionEditorChessboard,
			chess_new_game_info,
		)

	def _analyse_edited_position(self, board):
		# Game.from_board writes the FEN and SetUp tags, so the saved PGN starts from this position.
		wx.CallAfter(self.open_analysis_board, GameTree(chess.pgn.Game.from_board(board)))

	def onImportLichess(self, event):
		# A Lichess link copied from the browser (Control+L, Control+C) is offered first.
		clipboard = ""
		try:
			clipboard = (api.getClipData() or "").strip()
		except OSError:
			pass
		initial = (
			clipboard if "lichess.org/" in clipboard and parse_reference(clipboard) else get_lichess_user()
		)
		dialog = wx.TextEntryDialog(
			gui.mainFrame,
			# Translators: Prompt of the Lichess import dialog.
			_("Game link or code, or a Lichess username for that player's last game:"),
			# Translators: Title of the Lichess import dialog.
			_("Import Lichess Game"),
			value=initial,
		)
		run_modal(dialog, functools.partial(self._on_lichess_reference, dialog))

	def _on_lichess_reference(self, dialog, res):
		if res != wx.ID_OK:
			return
		ref = parse_reference(dialog.GetValue())
		if ref is None:
			show_error(
				# Translators: Shown when the text in the Lichess import dialog is not a game or a username.
				_("That is not a Lichess game link, game code or username."),
				_("Import Lichess Game"),
			)
			return
		if ref.kind == "user":
			save_lichess_user(ref.value)
		# Translators: Spoken while the game is being downloaded from Lichess.
		ui.message(_("Downloading from Lichess..."))
		concurrency.call_threaded(fetch_game)(ref).add_done_callback(
			lambda future: wx.CallAfter(self._on_lichess_game, future),
		)

	def _on_lichess_game(self, future):
		try:
			game = future.result()
		except DownloadError as error:
			log.warning("chessmart: Lichess import failed: %s", error)
			show_error(
				# Translators: Shown when a Lichess game could not be downloaded; {error} is the reason.
				_("Could not get the game from Lichess: {error}").format(error=error),
				_("Import Lichess Game"),
			)
			return
		folder = get_games_folder()
		path = os.path.join(folder, imported_filename(game))
		if os.path.exists(path):
			# Imported before: the saved copy may already hold comments and variations.
			try:
				game = read_game_at(path, 0)
			except (OSError, UnicodeDecodeError, ValueError) as error:
				log.warning("chessmart: could not read %s: %s", path, error)
				self._say_pgn_unreadable(error)
				return
			# Translators: Spoken when the Lichess game was imported before; its saved copy opens.
			ui.message(_("Already imported: opening your copy, with your notes."))
		else:
			try:
				os.makedirs(folder, exist_ok=True)
				write_pgn(GameTree(game), path)
			except OSError as error:
				show_error(
					# Translators: Shown when the imported game could not be written, followed by the error.
					_("Could not save the game. Details: {error}").format(error=error),
					# Translators: Title of the Lichess import messages.
					_("Import Lichess Game"),
				)
				return
		user = get_lichess_user().lower()
		flipped = bool(user) and game.headers.get("Black", "").lower() == user
		self.open_analysis_board(GameTree(game), source_path=path, flipped=flipped)

	def open_analysis_board(self, tree, source_path=None, flipped=False):
		chess_new_game_info = GameInfo(
			variant=ChessVariant.STANDARD,
			time_control=NULL_TIME_CONTROL,
			pychess_board=None,
			prospective=None,
			vboard_kwargs=dict(
				tree=tree,
				source_path=source_path,
				flipped=flipped,
				on_play_from=self.new_game_from,
				use_visuals=True,
				visual_arrows=True,
			),
		)
		self.global_plugin_object.initialize_and_show_chessboard_dialog(
			AnalysisChessboard, chess_new_game_info
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
		run_modal(openFileDialog, functools.partial(self.list_games_in_pgn, openFileDialog))

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
				# Translators: Prompt of the list of games in a PGN file.
				_("The file contains the following games"),
				# Translators: Title of the list of games in a PGN file.
				_("Select Game"),
				choices=[g.description for g in games],
			)
			run_modal(
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
		super().terminate()
		chessboard_menu = getattr(self, "chessboard_menu", None)
		if chessboard_menu is not None and gui.mainFrame is not None:
			gui.mainFrame.sysTrayIcon.toolsMenu.DestroyItem(chessboard_menu.itemHandle)
		try:
			# Close, not only destroy: closing fires the board's cleanup (a running
			# review is cancelled, engines and tablebases are released) before the
			# thread pool waits for its workers.
			for cdlg in list(self._active_board_dialogs.values()):
				cdlg.Close(force=True)
			concurrency.terminate()
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
