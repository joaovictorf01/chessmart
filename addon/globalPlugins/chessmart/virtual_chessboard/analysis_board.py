# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The analysis board: record a game move by move, with variations, comments and marks.

Both sides are played from the keyboard, as in a game between two people, but
nothing ends the session: a checkmate inside a variation is just a position.
Where the pieces go is kept in a `GameTree` (game_tree.py); this module turns
keys into calls on it and says what happened.

Keys, on any square (README, "Record and Analyse a Game"):
Alt+Left / Alt+Right  back / forward one move along the current line
Alt+Home / Alt+End    start of the game / end of the current line
Alt+Up                leave the variation, back to where it branched off
Alt+Down              the moves recorded from this position
Backspace             take back the last move of a line (to fix a slip)
C / Shift+C           write / read the comment of the current move
Control+1 to 6        mark the move ! ? !! ?? !? ?!; Control+0 clears it
Control+P             make the current variation the main line
E                     evaluate the position (twice: think longer)
Shift+E               review the move just played against the engine's best
Control+E             add the engine's line as a variation
O                     the opening the game is in (names from Lichess)
Tab                   every action above as a list, for when a key is forgotten
Control+S             save the game in the games folder
"""

import datetime
import functools
import os

import eventHandler
import globalVars
import queueHandler
import speech
import speech.commands
import ui
import wx
from logHandler import log
from scriptHandler import getLastScriptRepeatCount, script

from ..addon_config import get_autosave_analysis, get_games_folder, get_move_notation
from ..game_tree import (
	MOVE_MARK_SYMBOLS,
	GameTree,
	PlayResult,
	RecordHeaders,
	record_filename,
	unique_path,
	write_pgn,
)
from ..analysis_words import MARK_KEYS, spoken_clock_summary, spoken_mark, spoken_move_clock
from ..game_clock import move_clocks, node_clock, plain_comment, summarize
from ..i18n import _, ngettext
from ..notation import render_san
from ..openings import last_book_node, lookup, opening_of_line
from ..paths import import_bundled
from ..sounds import GameSound
from ..signals import chessboard_closed_signal
from ..speaking import speak_next
from ..spoken_messages import spoken_color_name
from .analysis_engine import AnalysisEngine
from ..played_move import PlayedMove
from .actions_bar import ActionsBarMixin
from .engine_actions import EngineActionsMixin
from .review_actions import ReviewActionsMixin
from .ui_components import MenuItemObject, MenuObject
from .user_driven import UserDrivenCell, UserDrivenChessboard


with import_bundled():
	import chess
	import chess.pgn


class MarkMenuItem(MenuItemObject):
	def __init__(self, nag: "int | None", *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.nag = nag


class MarkMenu(MenuObject):
	"""Control+1 to 6 as a list: the six marks, each with its key, and "no mark"."""

	def __init__(self, choice_callback, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.choice_callback = choice_callback
		items = [
			MarkMenuItem(
				nag=nag,
				# Translators: One entry of the mark menu, e.g. "dubious move, ?!, Control+6".
				name=_("{name}, {symbol}, Control+{key}").format(
					name=spoken_mark(nag),
					symbol=symbol,
					key=number,
				),
				parent=self,
			)
			for number, (nag, symbol) in enumerate(MOVE_MARK_SYMBOLS.items(), start=1)
		]
		# Translators: Last entry of the mark menu: removes the mark.
		items.append(MarkMenuItem(nag=None, name=_("No mark, Control+0"), parent=self))
		self.init_container_state(items)

	def on_item_activated(self, item):
		self.choice_callback(item.nag)

	def close_menu(self):
		self.choice_callback(False)


class AnalysisCell(UserDrivenCell):
	parent: "AnalysisChessboard"

	@script(gesture="kb:alt+leftarrow")
	def script_back(self, gesture):
		self.parent.go_back()

	@script(gesture="kb:alt+rightarrow")
	def script_forward(self, gesture):
		self.parent.go_forward()

	@script(gesture="kb:alt+home")
	def script_to_start(self, gesture):
		self.parent.go_to_start()

	@script(gesture="kb:alt+end")
	def script_to_end(self, gesture):
		self.parent.go_to_end()

	@script(gesture="kb:alt+uparrow")
	def script_leave_variation(self, gesture):
		self.parent.leave_variation()

	@script(gesture="kb:alt+downarrow")
	def script_alternatives(self, gesture):
		self.parent.announce_alternatives()

	@script(gesture="kb:backspace")
	def script_take_back(self, gesture):
		self.parent.take_back()

	@script(gesture="kb:c")
	def script_edit_comment(self, gesture):
		self.parent.edit_comment()

	@script(gesture="kb:shift+c")
	def script_read_comment(self, gesture):
		self.parent.read_comment()

	# Six keys for one script: bound through the class's gesture map.
	__gestures = {f"kb:control+{number}": "mark_move" for number in range(1, len(MARK_KEYS) + 1)}

	def script_mark_move(self, gesture):
		number = int(gesture.mainKeyName)
		self.parent.mark_move(MARK_KEYS[number - 1])

	@script(gesture="kb:control+0")
	def script_clear_mark(self, gesture):
		self.parent.mark_move(None)

	@script(gesture="kb:control+p")
	def script_promote_variation(self, gesture):
		self.parent.promote_variation()

	@script(gesture="kb:e")
	def script_evaluate(self, gesture):
		# A second press while the first is running asks for the long think.
		self.parent.evaluate_position(deep=getLastScriptRepeatCount() > 0)

	@script(gesture="kb:shift+e")
	def script_review_move(self, gesture):
		self.parent.review_move()

	@script(gesture="kb:control+e")
	def script_add_engine_line(self, gesture):
		self.parent.add_engine_line()

	@script(gesture="kb:o")
	def script_opening(self, gesture):
		self.parent.announce_opening()

	@script(gesture="kb:x")
	def script_threat(self, gesture):
		self.parent.show_threat()

	@script(gesture="kb:f7")
	def script_review_game(self, gesture):
		self.parent.review_game()

	@script(gesture="kb:alt+pagedown")
	def script_next_moment(self, gesture):
		self.parent.next_moment(1)

	@script(gesture="kb:alt+pageup")
	def script_previous_moment(self, gesture):
		self.parent.next_moment(-1)

	@script(gesture="kb:control+alt+s")
	def script_save_with_details(self, gesture):
		if globalVars.appArgs.secure:
			# Translators: Spoken when saving is refused because NVDA runs in secure mode.
			return ui.message(_("Could not save game. NVDA running in secure mode."))
		self.parent.save_game_with_details()

	@script(gesture="kb:t")
	def script_clock(self, gesture):
		self.parent.announce_clock_summary()

	@script(gesture="kb:tab")
	def script_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)


class AnalysisChessboard(ReviewActionsMixin, EngineActionsMixin, ActionsBarMixin, UserDrivenChessboard):
	cell_class = AnalysisCell
	can_draw = False

	def __init__(self, *args, tree=None, source_path=None, flipped=False, on_play_from=None, **kwargs):
		# Before super(): the base constructor already asks which side is at the bottom.
		self._flipped = flipped
		self.tree = tree if tree is not None else GameTree()
		self.source_path = source_path
		# Opens the New Game dialog on a FEN; given by the menu that opened this board.
		self.on_play_from = on_play_from
		self._unsaved = False
		# Said once: a failing automatic save must not speak on every move.
		self._autosave_failed = False
		kwargs["pychess_board"] = self.tree.board()
		super().__init__(*args, **kwargs)
		self.engine = AnalysisEngine()
		# The engine's last answer and the node it is about, so Control+E can reuse it.
		self._last_evaluation = None
		# E pressed twice: the first press already started the quick think; the
		# second is remembered and turns into the long one when the quick one ends.
		self._deep_pending = False
		chessboard_closed_signal.connect(
			lambda sender: (self.stop_review(), self.engine.quit(), self.close_tablebase()),
			sender=self,
		)
		self.install_actions_bar(
			# Translators: Name of the Tab bar on the analysis board.
			name=_("Analysis actions"),
			items=[
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Evaluate the position, E"), self._from_actions(self.evaluate_position)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Threat: what the other side would play, X"), self._from_actions(self.show_threat)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Review the move played, Shift+E"), self._from_actions(self.review_move)),
				# Translators: Tab bar action on the analysis board, with its key.
				(
					_("Add the engine's line as a variation, Control+E"),
					self._from_actions(self.add_engine_line),
				),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Opening, O"), self._from_actions(self.announce_opening)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Review the game, F7"), self._from_actions(self.review_game)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Next critical moment, Alt+Page Down"), self._from_actions(self.next_moment)),
				(
					# Translators: Tab bar action on the analysis board, with its key.
					_("Previous critical moment, Alt+Page Up"),
					self._from_actions(functools.partial(self.next_moment, -1)),
				),
				# Translators: Tab bar action on the analysis board: opens the game review options.
				(_("Review options..."), self.open_review_options),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Clock of the game, T"), self._from_actions(self.announce_clock_summary)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Write a comment, C"), self._from_actions(self.edit_comment)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Read the comment, Shift+C"), self._from_actions(self.read_comment)),
				# Translators: Tab bar action on the analysis board, with its keys.
				(_("Mark the move, Control+1 to 6"), self.open_mark_menu),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Moves recorded from here, Alt+Down"), self._from_actions(self.announce_alternatives)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Leave the variation, Alt+Up"), self._from_actions(self.leave_variation)),
				# Translators: Tab bar action on the analysis board, with its key.
				(
					_("Make this variation the main line, Control+P"),
					self._from_actions(self.promote_variation),
				),
				# Translators: Tab bar action on the analysis board: plays the current position against the engine.
				(_("Play from here against the computer..."), self.play_from_here),
				# Translators: Tab bar action on the analysis board: turns the board around.
				(_("Flip the board"), self._from_actions(self.flip_board)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Save, Control+S"), self._from_actions(self.save_game)),
				(
					# Translators: Tab bar action on the analysis board: edit players, event, date and result, then save.
					_("Game details and save, Control+Alt+S"),
					self._from_actions(self.save_game_with_details),
				),
				# Translators: Tab bar action that returns to the board.
				(_("Back to board"), self.focus_board_from_actions),
			],
		)
		self._rebuild_score_sheet()

	# -- the Tab bar ------------------------------------------------------------------

	def open_mark_menu(self):
		if self.tree.at_start:
			self.focus_board_from_actions()
			GameSound.invalid.play()
			# Translators: Spoken when a mark is set before any move on the analysis board.
			ui.message(_("Play or go to a move first; the mark belongs to a move."))
			return
		menu = MarkMenu(
			choice_callback=self._on_mark_chosen,
			# Translators: Name of the menu that marks the current move, e.g. "Mark 12. Nf3".
			name=_("Mark {move}").format(move=self._numbered_move()),
			parent=self,
		)
		self._current_focused_object = menu
		GameSound.menu_open.play()
		eventHandler.queueEvent("gainFocus", menu)

	def _on_mark_chosen(self, nag):
		self.focus_board_from_actions()
		# False: the menu was closed without a choice; None: "no mark".
		if nag is not False:
			queueHandler.queueFunction(queueHandler.eventQueue, self.mark_move, nag)

	def _is_open(self) -> bool:
		"""False once the window closed: answers from the engine arriving later are not spoken."""
		return bool(self.dialog)

	def play_from_here(self):
		"""The New Game dialog, with this position as the start and its side to move as the player's."""
		self.focus_board_from_actions()
		board = self.tree.board()
		if self.on_play_from is None:
			return
		if board.is_game_over():
			GameSound.invalid.play()
			# Translators: Spoken by "Play from here" on a checkmate or stalemate.
			ui.message(_("The game is over in this position: there is nothing to play."))
			return
		self.on_play_from(board.fen())

	def flip_board(self):
		self._flipped = not self._flipped
		if self.dialog:
			self.dialog.set_board_image()
		# Translators: Spoken after flipping the analysis board, e.g. "black at the bottom".
		ui.message(_("{color} at the bottom").format(color=spoken_color_name(not self._flipped)))

	# Both sides move; the side to move is the one whose pieces can be picked up.
	@property
	def prospective(self):
		return self.board.turn

	@prospective.setter
	def prospective(self, value):
		pass

	# The board stays the way the user set it up, instead of turning every move.
	@property
	def is_board_flipped(self):
		return self._flipped

	@property
	def material_side(self):
		# M counts from the side at the bottom of the board, which does not change every move.
		return chess.BLACK if self._flipped else chess.WHITE

	def is_busy(self, index):
		return False

	def leave_prompt(self):
		if not self.unsaved:
			return None
		# Translators: Asked when Escape is pressed on the analysis board with changes not saved.
		return _("Leave the analysis? The changes since the last save will be lost.")

	# -- playing and walking the tree ------------------------------------------

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		if move not in self.board.legal_moves:
			# Translators: Spoken when the requested move is not legal.
			speak_next([speech.commands.WaveFileCommand(GameSound.invalid.filename), _("Illegal move")])
			return
		played = PlayedMove.capture(self.board, move)
		result = self.tree.play(move)
		if result is not PlayResult.FOLLOWED:
			self.unsaved = True
		self._show_position(lastmove=move)
		spoken: list = []
		if result is PlayResult.NEW_VARIATION:
			spoken.append(speech.commands.WaveFileCommand(GameSound.menu_open.filename))
			# Translators: Spoken before a move that starts a new variation.
			spoken.append(_("new variation"))
		elif self.tree.starts_variation():
			# Translators: Spoken before a move that enters a variation already recorded.
			spoken.append(_("variation"))
		spoken += list(self._describe_move(played))
		spoken += self._node_details()
		spoken += self._book_note()
		spoken += self._position_state()
		speak_next(spoken)

	def go_back(self):
		node = self.tree.node
		if not self.tree.back():
			GameSound.invalid.play()
			# Translators: Spoken when going back at the start of the game.
			ui.message(_("Start of the game"))
			return
		self._show_position()
		spoken: list = []
		if node.parent is not None and self.tree.starts_variation(node):
			# Translators: Spoken when going back past the first move of a variation.
			spoken.append(_("out of the variation"))
		spoken += self._current_move_text()
		speak_next(spoken)

	def go_forward(self):
		if not self.tree.forward():
			GameSound.invalid.play()
			# Translators: Spoken when going forward at the last move of a line.
			ui.message(_("End of the line"))
			return
		self._show_position(lastmove=self.tree.node.move)
		spoken: list = []
		if self.tree.starts_variation():
			# Translators: Spoken before a move that enters a variation already recorded.
			spoken.append(_("variation"))
		spoken += self._current_move_text()
		spoken += self._book_note()
		spoken += self._position_state()
		speak_next(spoken)

	def go_to_start(self):
		self.tree.to_start()
		self._show_position()
		# Translators: Spoken when going back at the start of the game.
		ui.message(_("Start of the game"))

	def go_to_end(self):
		self.tree.to_end_of_line()
		self._show_position(lastmove=getattr(self.tree.node, "move", None))
		spoken: list = self._current_move_text() + self._position_state()
		speak_next(spoken)

	def leave_variation(self):
		if not self.tree.leave_variation():
			GameSound.invalid.play()
			# Translators: Spoken when Alt+Up is pressed on the main line.
			ui.message(_("Not in a variation"))
			return
		self._show_position()
		# Translators: Spoken after leaving a variation; followed by the move the position comes after.
		speak_next([_("back from the variation")] + self._current_move_text())

	def announce_alternatives(self):
		alternatives = self.tree.alternatives()
		if not alternatives:
			# Translators: Spoken by Alt+Down when no move was recorded from this position.
			ui.message(_("No moves recorded from here"))
			return
		board = self.tree.board()
		names = [self._san_text(board, child.move) for child in alternatives]
		if len(names) == 1:
			# Translators: Spoken by Alt+Down: the only move recorded from this position.
			ui.message(_("Continues with {move}").format(move=names[0]))
			return
		ui.message(
			# Translators: Spoken by Alt+Down: the main continuation, then the variations recorded here.
			_("Continues with {move}; variations: {others}").format(
				move=names[0],
				others=", ".join(names[1:]),
			),
		)

	def take_back(self):
		node = self.tree.node
		if node.parent is None:
			GameSound.invalid.play()
			# Translators: Spoken by Alt+Home: the start of the game.
			ui.message(_("Start of the game"))
			return
		board_before = node.parent.board()
		if not self.tree.delete_last_move():
			GameSound.invalid.play()
			# Translators: Spoken when Backspace is pressed on a move that has moves after it.
			ui.message(_("Only the last move of a line can be taken back. Use Alt+Left to go back."))
			return
		self.unsaved = True
		self._show_position()
		# Translators: Spoken after Backspace removed a move, e.g. "took back e4".
		ui.message(_("Took back {move}").format(move=self._san_text(board_before, node.move)))

	# -- comments and marks ------------------------------------------------------

	def edit_comment(self):
		if globalVars.appArgs.secure:
			return
		if self.tree.at_start:
			GameSound.invalid.play()
			# Translators: Spoken when C is pressed before any move.
			ui.message(_("Play or go to a move first; the comment belongs to a move."))
			return
		from ..graphical_interface.messages import run_modal

		dialog = wx.TextEntryDialog(
			self.dialog,
			# Translators: Prompt of the dialog that writes the comment of a move, e.g. "Comment on 12. Nf3".
			_("Comment on {move}").format(move=self._numbered_move()),
			# Translators: Title of the dialog that writes the comment of a move.
			_("Comment"),
			# One line: Enter saves the comment, as quickly as it was thought.
			value=self.tree.comment,
		)
		run_modal(dialog, functools.partial(self._on_comment_dialog, dialog, self.tree.node))

	def _on_comment_dialog(self, dialog, node, result):
		if result == wx.ID_OK and node is self.tree.node:
			old = self.tree.comment
			self.tree.set_comment(dialog.GetValue())
			if self.tree.comment != old:
				self.unsaved = True
				self._rebuild_score_sheet()
			# Translators: Spoken after the comment dialog was confirmed.
			message = _("Comment saved") if self.tree.comment else _("Comment removed")
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, message)
		queueHandler.queueFunction(queueHandler.eventQueue, self.set_focus_to_cell, self._focused_cell)

	def read_comment(self):
		comment = self.tree.comment
		if not comment:
			# Translators: Spoken by Shift+C when the current move has no comment.
			ui.message(_("No comment"))
			return
		ui.message(comment)

	def mark_move(self, nag):
		if not self.tree.set_move_mark(nag):
			GameSound.invalid.play()
			# Translators: Spoken when a mark is set before any move on the analysis board.
			ui.message(_("Play or go to a move first; the mark belongs to a move."))
			return
		self.unsaved = True
		self._rebuild_score_sheet()
		if nag is None:
			# Translators: Spoken when Control+0 removed the mark of a move.
			ui.message(_("Mark removed"))
		else:
			ui.message(spoken_mark(nag))

	def promote_variation(self):
		if not self.tree.promote_variation():
			GameSound.invalid.play()
			# Translators: Spoken by Control+P on the main line.
			ui.message(_("Not in a variation"))
			return
		self.unsaved = True
		self._rebuild_score_sheet()
		# Translators: Spoken after Control+P made the current variation the main line.
		ui.message(_("This variation is now the main line"))

	# -- saving --------------------------------------------------------------------

	@property
	def unsaved(self) -> bool:
		return self._unsaved

	@unsaved.setter
	def unsaved(self, value: bool) -> None:
		# Every change goes through here (moves, comments, marks, the engine's
		# lines, the review's marks), so this is the one place that saves by itself.
		self._unsaved = value
		if value:
			self._autosave()

	def _autosave(self):
		if not self.source_path or not get_autosave_analysis():
			return
		try:
			self._write(self.source_path)
		except OSError as error:
			log.warning("chessmart: automatic save failed: %s", error)
			if not self._autosave_failed:
				self._autosave_failed = True
				# Translators: Spoken once when the automatic save fails, followed by the error.
				ui.message(_("Could not save automatically. Details: {error}").format(error=error))

	def _write(self, path):
		self._set_opening_headers()
		write_pgn(self.tree, path)
		self._unsaved = False
		self._autosave_failed = False

	def save_game(self):
		"""Control+S: a game that already has a file is saved there, quietly; a new one asks for its details first."""
		if not self.source_path:
			self.save_game_with_details()
			return
		try:
			self._write(self.source_path)
		except OSError as error:
			log.warning("chessmart: could not save the analysed game: %s", error)
			# Translators: Spoken when the game could not be written, followed by the error.
			ui.message(_("Could not save the game. Details: {error}").format(error=error))
			return
		# Translators: Spoken after saving, with the file name, e.g. "Saved: 2026-09-23_Joao-vs-Ana.pgn".
		ui.message(_("Saved: {name}").format(name=os.path.basename(self.source_path)))

	def save_game_with_details(self):
		from ..graphical_interface.record_dialog import RecordHeadersDialog
		from ..graphical_interface.messages import run_modal

		headers = self.tree.game.headers
		initial = RecordHeaders(
			white=_known(headers.get("White")),
			black=_known(headers.get("Black")),
			event=_known(headers.get("Event")),
			date=_parse_pgn_date(headers.get("Date")) or datetime.date.today(),
			result=headers.get("Result", "*"),
		)
		dialog = RecordHeadersDialog(self.dialog, initial)
		run_modal(dialog, functools.partial(self._on_headers_dialog, dialog))

	def _on_headers_dialog(self, dialog, result):
		if result == wx.ID_OK:
			record = dialog.get_headers()
			record.apply(self.tree)
			try:
				path = self._save_path(record)
				self._write(path)
			except OSError as error:
				log.warning("chessmart: could not save the analysed game: %s", error)
				# The new headers are in the tree but not on disk: Escape must still ask.
				self._unsaved = True
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					# Translators: Spoken when the game could not be written, followed by the error.
					_("Could not save the game. Details: {error}").format(error=error),
				)
			else:
				self.source_path = path
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					# Translators: Spoken after saving, with the file name, e.g. "Saved: 2026-09-23_Joao-vs-Ana.pgn".
					_("Saved: {name}").format(name=os.path.basename(path)),
				)
		queueHandler.queueFunction(queueHandler.eventQueue, self.set_focus_to_cell, self._focused_cell)

	def _save_path(self, record):
		# A game opened from a file goes back to that file; a new one gets a name in the folder.
		if self.source_path:
			return self.source_path
		folder = get_games_folder()
		os.makedirs(folder, exist_ok=True)
		return unique_path(folder, record_filename(record.date, record.white, record.black))

	def _set_opening_headers(self):
		"""ECO and Opening, as Lichess writes them, from where the main line left theory."""
		book_node = last_book_node(self.tree.game)
		opening = lookup(book_node.board()) if book_node is not None else None
		if opening is None:
			return
		headers = self.tree.game.headers
		headers["ECO"] = opening.eco
		headers["Opening"] = opening.name

	# -- the clock of an imported game ------------------------------------------------

	def announce_clock_summary(self):
		clocks = move_clocks(self.tree.game)
		if not clocks:
			# Translators: Spoken by T when the game carries no clock (entered by hand, or an old PGN).
			ui.message(_("This game has no clock. Games imported from Lichess have one."))
			return
		speak_next(
			[
				spoken_clock_summary(summarize(clocks, chess.WHITE)),
				speech.commands.BreakCommand(300),
				spoken_clock_summary(summarize(clocks, chess.BLACK)),
			],
		)

	# -- openings ---------------------------------------------------------------------

	def announce_opening(self):
		opening = opening_of_line(self.tree.node)
		if opening is None:
			# Translators: Spoken by O when no position of the line has an opening name.
			ui.message(_("No named opening yet"))
			return
		in_book = lookup(self.tree.board()) is not None
		ui.message(
			# Translators: Spoken by O, e.g. "Sicilian Defense: Najdorf Variation, B90, still theory".
			_("{name}, {eco}, still theory").format(name=opening.name, eco=opening.eco)
			if in_book
			# Translators: Spoken by O after the game left theory, e.g. "Sicilian Defense, B20, out of theory".
			else _("{name}, {eco}, out of theory").format(name=opening.name, eco=opening.eco),
		)

	def _book_note(self) -> list:
		"""The opening's name when a move reaches a new one, and the moment a line leaves theory."""
		node = self.tree.node
		if node.parent is None:
			return []
		opening = lookup(node.board())
		if opening is not None:
			if opening != opening_of_line(node.parent):
				return [speech.commands.BreakCommand(150), opening.name]
			return []
		if lookup(node.parent.board()) is not None:
			# Translators: Spoken after the first move that is not in the opening table.
			return [speech.commands.BreakCommand(150), _("out of theory")]
		return []

	# -- what is said and shown ----------------------------------------------------

	def _show_position(self, lastmove=None):
		self.board = self.tree.board()
		self._rebuild_score_sheet()
		if self.dialog:
			self.dialog.set_board_image(lastmove=lastmove)
		eventHandler.queueEvent("stateChange", self._chess_cells[self._focused_cell])

	def _rebuild_score_sheet(self):
		self.score_sheet_menu.clear()
		node = self.tree.node
		nodes = []
		while node.parent is not None:
			nodes.append(node)
			node = node.parent
		# The score sheet lists the latest move first (SimpleList.add_item inserts at the top).
		for child in reversed(nodes):
			text = self._numbered_move(child)
			comment = plain_comment(child.comment)
			if comment:
				text += " " + comment
			self.score_sheet_menu.add_item(text)

	def _san_text(self, board, move):
		return render_san(board.san(move), move.uci(), get_move_notation())

	def _numbered_move(self, node=None):
		"""`12. Nf3` or `12... Nf6`, with the mark: how the move is written in the score sheet."""
		node = self.tree.node if node is None else node
		assert node.parent is not None, "the start of the game has no move to write"
		board = node.parent.board()
		number = board.fullmove_number
		prefix = f"{number}." if board.turn == chess.WHITE else f"{number}..."
		marks = node.nags & set(MOVE_MARK_SYMBOLS)
		mark = MOVE_MARK_SYMBOLS[min(marks)] if marks else ""
		return f"{prefix} {self._san_text(board, node.move)}{mark}"

	def _current_move_text(self) -> list:
		"""Where the pointer is, said after a jump: the move just played there, its mark and comment."""
		if self.tree.at_start:
			# Translators: Where the pointer is, before any move.
			return [_("Start of the game")]
		spoken = [self._numbered_move()]
		spoken += self._node_details()
		return spoken

	def _node_details(self) -> list:
		details = []
		if self.tree.move_mark is not None:
			details.append(spoken_mark(self.tree.move_mark))
		if self.tree.comment:
			details += [speech.commands.BreakCommand(200), self.tree.comment]
		clock = node_clock(self.tree.node)
		if clock is not None:
			details += [speech.commands.BreakCommand(150), spoken_move_clock(*clock)]
		others = len(self.tree.alternatives()) - 1
		if others > 0:
			details.append(
				# Translators: Spoken when the position has variations recorded besides the main continuation.
				ngettext("{count} variation from here", "{count} variations from here", others).format(
					count=others,
				),
			)
		return details

	def _position_state(self) -> list:
		board = self.board
		if board.is_checkmate():
			# Translators: Spoken when a position on the analysis board is checkmate.
			return [speech.commands.WaveFileCommand(GameSound.game_over.filename), _("checkmate")]
		if board.is_stalemate():
			# Translators: Spoken when a position on the analysis board is stalemate.
			return [speech.commands.WaveFileCommand(GameSound.game_over.filename), _("stalemate")]
		if board.is_check():
			return [
				speech.commands.WaveFileCommand(GameSound.check.filename),
				# Translators: Spoken when a king is in check, e.g. "white is in check".
				_("{color} is in check").format(color=spoken_color_name(board.turn)),
			]
		return []


def _known(value):
	return "" if value in (None, "?", "") else value


def _parse_pgn_date(value):
	try:
		return datetime.datetime.strptime(value or "", "%Y.%m.%d").date()
	except ValueError:
		return None
