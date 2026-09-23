# coding: utf-8
# pyright: basic

import bisect
import enum
import functools
import itertools
import math
from typing import Iterable

import inputCore
import globalVars
import ui
import api
import controlTypes
import eventHandler
import speech
import speech.commands
from NVDAObjects import NVDAObject
from scriptHandler import script
from .announcements import AnnouncementsMixin
from .board_files import BoardFilesMixin
from .ui_components import (
	KeyboardNavigableNVDAObjectMixin,
	MenuItemObject,
	MenuObject,
	SimpleList,
)
from ..time_control import NULL_TIME_CONTROL
from ..spoken_messages import (
	standard_game_announcer,
	ibca_game_announcer,
	spoken_color_name,
	spoken_termination_name,
)
from ..i18n import _
from ..notation import DESCRIPTIVE, render_san, render_square
from ..addon_config import get_move_notation
from ..board_geometry import DOWN, LEFT, RIGHT, UP, neighbour, square_color
from ..paths import import_bundled
from ..played_move import PlayedMove
from ..sounds import GameSound
from ..speaking import intersperse, speak_next
from ..signals import (
	move_completed_signal,
	game_started_signal,
	game_over_signal,
	chessboard_closed_signal,
)


with import_bundled():
	import chess
	import chess.pgn
	import chess.svg


class Color(enum.Enum):
	"""Colors of the ring drawn on the focused square, and of the last-move arrow.

	Chosen to stand out on the cream and brown squares for whoever watches the
	screen: the focus ring is blue, a legal destination green, a square the
	dragged piece cannot go to red, the picked-up piece purple.
	"""

	Red = "#d93025"
	Blue = "#1e6fd9"
	Green = "#15a34a"
	Yellow = "#f2c200"
	Purple = "#8e3fbf"
	# The last move, drawn over its highlighted squares.
	DarkGray = "#15781b"


class BaseChessboardCell(KeyboardNavigableNVDAObjectMixin, NVDAObject):
	role = controlTypes.Role.TABLECELL
	# NVDA declares `parent` as Optional[NVDAObject], populated by `_get_parent`.
	# A square always belongs to the board that created it; the type here reflects that.
	parent: "BaseVirtualChessboard"
	PIECE_LETTERS = {
		"r": chess.ROOK,
		"n": chess.KNIGHT,
		"b": chess.BISHOP,
		"q": chess.QUEEN,
		"k": chess.KING,
		"p": chess.PAWN,
	}

	def __init__(self, parent, index, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.parent = parent
		self.game_announcer = self.parent.game_announcer
		self.index = index
		self.processID = self.parent.processID
		self._add_multiple_scripts()

	def _add_multiple_scripts(self):
		gestures = {}
		jump_script_func = getattr(self.__class__, "script_jump_to_piece_handler")
		for letter, piece_type in self.PIECE_LETTERS.items():
			gestures[f"kb:{letter}"] = functools.partialmethod(jump_script_func, piece_type, False)
			gestures[f"kb:shift+{letter}"] = functools.partialmethod(jump_script_func, piece_type, True)
		self._gestureMap.update({inputCore.normalizeGestureIdentifier(k): v for (k, v) in gestures.items()})

	@property
	def roleText(self):
		if self.parent.board.piece_at(self.index) is None:
			# Translators: Role of an empty board square, spoken by the screen reader.
			return _("Square")

	@property
	def states(self):
		return {
			controlTypes.State.FOCUSABLE,
			controlTypes.State.FOCUSED,
		}

	@property
	def description(self):
		return self.parent.spoken_square_name(self.index)

	@property
	def name(self):
		return self.parent.get_piece_name_at_square(self.index)

	def on_activate(self):
		self.parent.activate_cell(self)

	@property
	def square_color(self):
		return square_color(self.index)

	def get_remaining_time(self, color: chess.Color):
		color_name = spoken_color_name(color)
		total_seconds = self.parent.time_control.get_remaining_time()[color]
		minutes = math.floor(total_seconds / 60)
		seconds = math.floor(total_seconds % 60)
		if not minutes:
			# Translators: Remaining clock time, e.g. "45 seconds remaining for white".
			return _("{seconds} seconds remaining for {color}").format(seconds=seconds, color=color_name)
		elif not seconds:
			# Translators: Remaining clock time, e.g. "5 minutes remaining for white".
			return _("{minutes} minutes remaining for {color}").format(minutes=minutes, color=color_name)
		# Translators: Remaining clock time, e.g. "5 minutes and 30 seconds remaining for white".
		return _("{minutes} minutes and {seconds} seconds remaining for {color}").format(
			minutes=minutes,
			seconds=seconds,
			color=color_name,
		)

	def get_highlight_color(self):
		return Color.Blue

	def update_visual_highlight(self):
		if not self.parent.use_visuals:
			return
		arrows = [chess.svg.Arrow(self.index, self.index, color=self.get_highlight_color().value)]
		last_move = None
		if self.parent.board.move_stack:
			last_move = self.parent.board.move_stack[-1]
			if self.parent.visual_arrows:
				arrows.append(
					chess.svg.Arrow(
						last_move.from_square,
						last_move.to_square,
						color=Color.DarkGray.value,
					),
				)
		self.parent.dialog.set_board_image(arrows=arrows, lastmove=last_move)

	def event_gainFocus(self):
		super().event_gainFocus()
		self.parent._focused_cell = self.index
		if self.square_color is chess.BLACK:
			GameSound.black_square.play()
		self.update_visual_highlight()

	def script_activate_cell(self, gesture):
		self.on_activate()

	def script_jump_to_piece_handler(self, piece_type, to_opponent_piece, gesture):
		if self.parent.prospective is not None:
			piece_color = self.parent.prospective
		else:
			piece_color = chess.WHITE
		piece_color = piece_color if not to_opponent_piece else not piece_color
		self.parent.jump_to_piece(piece_type, piece_color)

	@script(gesture="kb:f1")
	def script_player_overview(self, gesture):
		self.parent.announce_player_overview(self.parent.prospective)

	@script(gesture="kb:shift+f1")
	def script_opponent_overview(self, gesture):
		self.parent.announce_player_overview(not self.parent.prospective)

	@script(gesture="kb:f3")
	def script_cell_info(self, gesture):
		color = spoken_color_name(self.square_color)
		spoken_commands = [
			ibca_game_announcer.square_file(self.index),
			speech.commands.BreakCommand(100),
			ibca_game_announcer.square_rank(self.index),
			speech.commands.BreakCommand(250),
			# Translators: Color of the focused square, e.g. "square color: white,".
			_("square color: {color},").format(color=color),
		]
		piece_type = self.parent.board.piece_type_at(self.index)
		if piece_type is not None:
			spoken_commands.insert(0, ibca_game_announcer.piece_name(piece_type))
			spoken_commands.insert(1, speech.commands.BreakCommand(100))
		speak_next(spoken_commands)

	@script(gesture="kb:f2")
	def script_announce_time_for_current_turn(self, gesture):
		if self.parent.time_control is NULL_TIME_CONTROL:
			GameSound.invalid.play()
			# Translators: Spoken when the clock is asked for in a game without time control.
			return ui.message(_("No Time Control"))
		color = self.parent.board.turn
		remaining = self.get_remaining_time(color)
		ui.message(remaining)

	@script(gesture="kb:shift+f2")
	def script_announce_time_for_other_turn(self, gesture):
		if self.parent.time_control is NULL_TIME_CONTROL:
			GameSound.invalid.play()
			return ui.message(_("No Time Control"))
		color = not self.parent.board.turn
		remaining = self.get_remaining_time(color)
		ui.message(remaining)

	@script(gesture="kb:a")
	def script_announce_attackers(self, gesture):
		self.parent.announce_attackers(self.index)

	@script(gesture="kb:m")
	def script_announce_material(self, gesture):
		self.parent.announce_material()

	@script(gesture="kb:f4")
	def script_score_sheet(self, gesture):
		if self.parent.score_sheet_menu:
			eventHandler.queueEvent("gainFocus", self.parent.score_sheet_menu)
		else:
			# Translators: Spoken when the score sheet is opened before any move.
			ui.message(_("Score sheet is empty"))

	@script(gesture="kb:control+s")
	def script_save_board_pgn(self, gesture):
		if globalVars.appArgs.secure:
			# Translators: Spoken when saving is refused because NVDA runs in secure mode.
			return ui.message(_("Could not save game. NVDA running in secure mode."))
		self.parent.save_game()

	@script(gesture="kb:control+shift+s")
	def script_save_board_image(self, gesture):
		if globalVars.appArgs.secure:
			return ui.message(_("Could not save game. NVDA running in secure mode."))
		self.parent.save_board_image()

	@script(gesture="kb:escape")
	def script_escape(self, gesture):
		self.parent.request_leave()

	@script(gesture="kb:rightarrow")
	def script_rightarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_right(self)
		else:
			self.parent.navigate_left(self)

	@script(gesture="kb:leftarrow")
	def script_leftarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_left(self)
		else:
			self.parent.navigate_right(self)

	@script(gesture="kb:downarrow")
	def script_downarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_down(self)
		else:
			self.parent.navigate_up(self)

	@script(gesture="kb:uparrow")
	def script_uparrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_up(self)
		else:
			self.parent.navigate_down(self)

	__gestures = {
		"kb:enter": "activate_cell",
		"kb:numpadenter": "activate_cell",
		"kb:space": "activate_cell",
	}


class LeaveGameMenu(MenuObject):
	"""The confirmation Escape triggers before closing a game in progress.

	Two options, with staying listed first: pressing Escape again (inside the
	menu) returns to the board instead of leaving. Leaving requires
	deliberately choosing "Yes".
	"""

	def __init__(self, choice_callback, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.choice_callback = choice_callback
		self.init_container_state(
			[
				# Translators: Option in the menu shown when Escape is pressed during a game.
				MenuItemObject(name=_("No, keep playing"), parent=self),
				# Translators: Option in the menu shown when Escape is pressed during a game.
				MenuItemObject(name=_("Yes, leave"), parent=self),
			],
		)

	def on_item_activated(self, item):
		self.choice_callback(bool(self.index_of(item)))

	def close_menu(self):
		self.choice_callback(False)


class BaseVirtualChessboard(
	AnnouncementsMixin, BoardFilesMixin, KeyboardNavigableNVDAObjectMixin, NVDAObject
):
	role = controlTypes.Role.TABLE
	# Translators: Role of the chessboard control, spoken by the screen reader.
	roleText = _("Board")
	# Translators: Name of the chessboard control, spoken by the screen reader.
	name = _("Chess")
	cell_class = BaseChessboardCell
	can_draw = True

	def __init__(
		self,
		dialog,
		*,
		variant,
		prospective=None,
		time_control=NULL_TIME_CONTROL,
		game_announcer=standard_game_announcer,
		use_visuals=True,
		visual_arrows=False,
		pychess_board=None,
	):
		super().__init__()
		self.parent = api.getFocusObject()
		self.processID = self.parent.processID
		self.dialog = dialog
		self.variant = variant
		self.game_announcer = game_announcer
		self.prospective = prospective
		self.time_control = time_control
		self.use_visuals = use_visuals
		self.visual_arrows = visual_arrows
		self.board = pychess_board or chess.Board()
		self._chess_cells = [self.cell_class(parent=self, index=i) for i in range(0, 64)]
		self._focused_cell = self.get_initial_focus_cell()
		self.is_game_over = False
		self._current_focused_object = None
		self.score_sheet_menu = SimpleList(
			# Translators: Name of the list of moves played so far.
			parent=self,
			name=_("Score sheet"),
			close_gesture="kb:f4",
		)
		# Connect to events
		game_started_signal.connect(lambda s: self.time_control.start_game(), sender=self)
		chessboard_closed_signal.connect(lambda s: self.game_over(), sender=self)

	def get_initial_focus_cell(self):
		return 4 if not self.is_board_flipped else 60

	@property
	def is_board_flipped(self):
		return not self.prospective

	@property
	def is_board_visually_flipped(self):
		return self.is_board_flipped

	def game_over(self, dialog_title=None):
		was_over = self.is_game_over
		self.is_game_over = True
		# Closing the window of an already-finished game runs through here again,
		# and the window may already have been destroyed by wx: a deleted wx object is falsy.
		if self.dialog:
			# Translators: Window title when a game has ended.
			self.dialog.SetTitle(dialog_title or _("Game Over"))
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		# Only once: closing the window of an already-finished game calls this
		# again, and whoever listens to the signal (the engine, for instance) has already detached.
		if not was_over:
			game_over_signal.send(self, board_outcome=self.board.outcome())

	def game_resigned(self, resigning_color):
		self.game_over()
		color_name = spoken_color_name(resigning_color)
		# Translators: Window title after a resignation, e.g. "white resigned".
		self.dialog.SetTitle(_("{color} resigned").format(color=color_name))
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.resigned.filename),
				speech.commands.BreakCommand(200),
				# Translators: Spoken after a resignation, e.g. "white resigned the game".
				_("{color} resigned the game").format(color=color_name),
			],
		)

	def game_drawn(self):
		self.game_over()
		# Translators: Window title when the game ended in a draw.
		self.dialog.SetTitle(_("Game Drawn"))
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.drawn.filename),
				speech.commands.BreakCommand(200),
				# Translators: Spoken when the game ended in a draw.
				_("Game is drawn"),
			],
		)

	def game_time_forfeit(self, losing_color: chess.Color):
		self.game_over(
			# Translators: Window title when a game was lost on time, e.g. "Game Over: Time Forfeit - white is the winner".
			_("Game Over: Time Forfeit - {color} is the winner").format(
				color=self.game_announcer.color_name(not losing_color),
			),
		)
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.time_forfeit.filename),
				speech.commands.BreakCommand(300),
				# Translators: Spoken when a side ran out of time, e.g. "black, time over".
				_("{color}, time over").format(color=self.game_announcer.color_name(losing_color)),
				speech.commands.BreakCommand(150),
				# Translators: Spoken to name the winner, e.g. "white is the winner".
				_("{color} is the winner").format(color=self.game_announcer.color_name(not losing_color)),
			],
		)

	def game_error(self, error_message=None):
		# Translators: Window title and message when a game stopped because of an error.
		error_message = error_message or _("Game terminated due to an error")
		self.game_over()
		self.dialog.SetTitle(error_message)
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.error.filename),
				speech.commands.BreakCommand(200),
				error_message,
			],
		)

	def set_focus_to_cell(self, index):
		eventHandler.executeEvent("gainFocus", self._chess_cells[index])

	def activate_cell(self, cell):
		GameSound.invalid.play()

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		if move not in self.board.legal_moves:
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					speech.commands.BreakCommand(100),
					# Translators: Spoken when the requested move is not legal.
					_("Illegal move"),
				],
			)
			return
		played = PlayedMove.capture(self.board, move)
		move_maker = played.mover
		self.board.push(move)
		self.time_control.time_move(not self.board.turn, total_moves=len(self.board.move_stack))
		desc_generator = tuple(self._describe_move(played))
		self.score_sheet_menu.add_item(" ".join(i for i in desc_generator if type(i) is str))
		spoken_commands: list[Iterable] = [desc_generator]
		spoken_commands.append(pre_speech)
		if self.board.is_game_over():
			spoken_commands.append(self._get_game_over_messages())
			spoken_commands.append([speech.commands.CallbackCommand(self.game_over)])
		elif self.board.is_check():
			spoken_commands.append(
				[
					speech.commands.WaveFileCommand(GameSound.check.filename),
					speech.commands.BreakCommand(250),
					# Translators: Spoken when a king is in check, e.g. "white is in check".
					_("{color} is in check").format(color=spoken_color_name(self.board.turn)),
				],
			)
			if (move_maker != self.prospective) or (self.prospective is None):
				spoken_commands.append(
					[
						speech.commands.BreakCommand(250),
						speech.commands.CallbackCommand(
							functools.partial(self.jump_to_piece, chess.KING, self.board.turn),
						),
						speech.commands.BreakCommand(250),
						speech.commands.CallbackCommand(
							functools.partial(
								self.announce_attackers,
								self.board.king(self.board.turn),
								True,
							),
						),
					],
				)
		spoken_commands.append(post_speech)
		# list() here isn't a style choice, it's the fix: itertools.chain returns a
		# lazy ITERATOR, and NVDA's speech expects an actual sequence. Given an
		# iterator, NVDA consumes it once while inspecting the sequence, leaving
		# nothing left to speak -- the move would land on the board and the
		# announcement would simply vanish, with no error raised.
		speak_next(list(itertools.chain(*spoken_commands)))
		self.dialog.set_board_image(lastmove=move)
		move_completed_signal.send(self, move=move, move_maker=move_maker)

	def _describe_move(self, played: PlayedMove):
		"""The spoken sequence for an already-played move: the move-type sound followed by the text."""
		move = played.move
		style = get_move_notation()
		if style != DESCRIPTIVE and played.san:
			# Short style (SAN, UCI, anna...): the move-type sound still plays,
			# and the text comes as a single chunk, the way Lichess announces it.
			yield speech.commands.WaveFileCommand(GameSound(played.sound_name).filename)
			yield speech.commands.BreakCommand(150)
			yield render_san(played.san, move.uci(), style)
			return
		if move.promotion is not None:
			yield speech.commands.WaveFileCommand(GameSound.promotion.filename)
			yield speech.commands.BreakCommand(300)
			yield from intersperse(
				self.game_announcer.promotion_move(move, move_maker=played.mover),
				speech.commands.BreakCommand(200),
			)
			return
		if played.is_castling:
			yield speech.commands.WaveFileCommand(GameSound.castling.filename)
			yield speech.commands.BreakCommand(250)
			yield from intersperse(
				self.game_announcer.castling_move(played.mover, played.is_kingside_castling),
				speech.commands.BreakCommand(200),
			)
			return
		# After the push, the moved piece is on the destination square (already promoted, if applicable).
		moved_piece = self.board.piece_at(move.to_square)
		assert moved_piece is not None, "a legal move always leaves a piece on its destination"
		if move.drop:
			yield speech.commands.WaveFileCommand(GameSound.drop_move.filename)
			yield from intersperse(
				self.game_announcer.drop_move(played.mover, move=move),
				speech.commands.BreakCommand(200),
			)
			yield speech.commands.BreakCommand(300)
		if played.captured_piece is not None:
			yield speech.commands.WaveFileCommand(GameSound(played.sound_name).filename)
			yield from intersperse(
				self.game_announcer.capture_move(move, moved_piece, played.captured_piece),
				speech.commands.BreakCommand(200),
			)
			if played.is_en_passant:
				# Translators: Spoken after an en passant capture.
				yield _("en passant")
			return
		yield speech.commands.WaveFileCommand(GameSound.drop_piece.filename)
		yield from intersperse(
			self.game_announcer.normal_move(move, moved_piece, move_maker=played.mover),
			speech.commands.BreakCommand(50),
		)

	def jump_to_piece(self, piece_type, piece_color):
		target_squares = tuple(self.board.pieces(piece_type, piece_color))
		if not target_squares:
			piece = chess.Piece(piece_type, piece_color)
			piece_name = self.game_announcer.describe_piece(piece)
			# Translators: Spoken when jumping to a piece that is no longer on the board, e.g. "No white knight".
			ui.message(_("No {piece}").format(piece=piece_name))
			return
		target_pos = bisect.bisect_right(target_squares, self._focused_cell)
		if target_pos == len(target_squares):
			target_pos = 0
		target_cell = target_squares[target_pos]
		self.set_focus_to_cell(target_cell)

	def notify_invalid_navigation(self):
		GameSound.invalid.play()
		speech.speakObject(api.getFocusObject(), controlTypes.OutputReason.FOCUS)

	def spoken_square_name(self, square):
		"""The square as it is spoken: "f3", or "felix 3" / "foxtrot 3" in those styles."""
		return render_square(self.game_announcer.square_name(square), get_move_notation())

	def get_piece_name_at_square(self, index):
		piece = self.board.piece_at(index)
		if piece is None:
			return ""
		return self.game_announcer.describe_piece(piece)

	def _get_game_over_messages(self):
		outcome = self.board.outcome()
		assert outcome is not None, "called only when board.is_game_over()"
		termination_reason = spoken_termination_name(outcome.termination)
		yield from [
			speech.commands.WaveFileCommand(GameSound.game_over.filename),
			speech.commands.BreakCommand(250),
			termination_reason,
		]
		game_winner = "" if outcome.winner is None else self.game_announcer.color_name(outcome.winner)
		if game_winner:
			yield from [
				speech.commands.BreakCommand(250),
				_("{color} is the winner").format(color=game_winner),
			]

	def event_gainFocus(self):
		if self._current_focused_object is not None:
			eventHandler.queueEvent("gainFocus", self._current_focused_object)
		else:
			self.set_focus_to_cell(self._focused_cell)

	def _navigate(self, anchor, direction):
		target = neighbour(anchor.index, direction)
		if target is None:
			return self.notify_invalid_navigation()
		self.set_focus_to_cell(target)

	def navigate_left(self, anchor):
		self._navigate(anchor, LEFT)

	def navigate_right(self, anchor):
		self._navigate(anchor, RIGHT)

	def navigate_up(self, anchor):
		self._navigate(anchor, UP)

	def navigate_down(self, anchor):
		self._navigate(anchor, DOWN)

	# -- leaving the board ----------------------------------------------------

	def leave_prompt(self):
		"""The confirmation to show before leaving, or None to leave without asking.

		Each mode states what would be lost: the game against the engine, the
		online game, the puzzle in progress. PGN replay loses nothing and never
		asks. With the game already over, nothing asks either.
		"""
		return None

	def request_leave(self):
		"""Escape on the board: asks if there's something to lose, otherwise leaves."""
		prompt = None if self.is_game_over else self.leave_prompt()
		if prompt is None:
			self.leave_game()
			return
		menu = LeaveGameMenu(choice_callback=self._on_leave_choice, name=prompt, parent=self)
		self._current_focused_object = menu
		GameSound.menu_open.play()
		eventHandler.queueEvent("gainFocus", menu)

	def _on_leave_choice(self, leave):
		self._current_focused_object = None
		if leave:
			self.leave_game()
		else:
			eventHandler.queueEvent("gainFocus", self)

	def leave_game(self):
		"""Leaves for good. Modes with an opponent on the other end warn first (see subclasses)."""
		self.hide_board_gui()

	def hide_board_gui(self):
		"""Actually closes the board window.

		Used to be `Hide()`: the window disappeared, but the dialog's `onClose`
		never ran, so the timer kept ticking, the engine stayed alive, and the
		dialog remained forever in the plugin's list of active windows. `Close()`
		goes through `onClose`, which stops the timer, fires the close signal
		(and with it, the end of the game), and destroys the window.
		"""
		eventHandler.queueEvent("gainFocus", self.parent)
		self.dialog.Close()
