# coding: utf-8
# pyright: basic

"""Endgame boards: the mate drill and the lesson, both judged via tablebase.

`TablebaseJudgeMixin`, shared by both, reports after each player move
whether the tablebase result changed hands (Control+T for the verdict,
Control+Shift+T for the move that keeps it); without tablebases installed
it stays silent and says why.

Drills chase a move-count goal against the engine; lessons ask "win, draw or
loss?" first, then have the player hold that answer against the engine
(Backspace to undo). The engine always plays at full strength, since perfect
defense is what makes the technique matter. Attempts are recorded to `endgame.log`.
"""

import time
import typing

import api
import eventHandler
import queueHandler
import wx
import speech
import speech.commands
from logHandler import log as nvda_log
from scriptHandler import script

from ..addon_config import get_move_notation
from ..endgame import judge, tablebase
from ..endgame import log as endgame_log
from ..endgame.drills import EndgameDrill, drill_description, drill_label, drill_result_messages
from ..endgame.lessons import (
	EndgameLesson,
	LessonPosition,
	lesson_label,
	play_goal,
	position_rule,
	position_title,
)
from ..i18n import _
from ..notation import render_san
from ..paths import import_bundled
from ..signals import chessboard_closed_signal
from ..sounds import GameSound
from ..speaking import speak_next
from ..time_control import NullChessTimeControl
from .puzzle_board import TrainingActionsBar
from .ui_components import MenuItemObject, MenuObject
from .user_driven import UserDrivenCell
from .user_engine import UserEngineChessboard


with import_bundled():
	import chess


def spoken_move(board: chess.Board, move: chess.Move) -> str:
	"""The move in the notation the user chose in the settings."""
	return render_san(board.san(move), move.uci(), get_move_notation())


# ---------------------------------------------------------------- judge


class TablebaseJudgeMixin:
	"""Queries the tablebase after each player move and on the verdict keys.

	Combined with `UserEngineChessboard`: it uses `board`, `prospective`,
	`game_announcer` and `move_piece_and_check_game_status` from there.
	"""

	board: chess.Board
	prospective: chess.Color
	game_announcer: typing.Any
	tablebase: typing.Any = None
	spoiled_moves: int = 0
	hints_used: int = 0

	_actions_bar: typing.Any = None
	_current_focused_object: typing.Any
	_focused_cell: int

	def build_action_bar(self, items):
		self._actions_bar = TrainingActionsBar(
			parent=self,
			# Translators: Name of the toolbar reached with Tab on the endgame board.
			name=_("Endgame actions"),
			items=items,
		)

	def focus_action_bar(self, reverse=False):
		if not self._actions_bar:
			return
		self._current_focused_object = self._actions_bar
		target_index = len(self._actions_bar) - 1 if reverse else 0
		self._actions_bar.set_current(target_index)
		eventHandler.executeEvent("gainFocus", self._actions_bar)

	def focus_board_from_actions(self):
		self._current_focused_object = None
		self.set_focus_to_cell(self._focused_cell)  # pyright: ignore[reportAttributeAccessIssue]

	def _from_actions(self, callback):
		"""Wraps an actions-bar action: returns focus to the board, then calls it."""

		def run():
			self._current_focused_object = None
			callback()

		return run

	def open_judge(self):
		try:
			self.tablebase = tablebase.open_tablebase()
		except Exception as error:  # corrupted table or unreadable folder: training continues without a judge
			nvda_log.warning("chessmart: could not open the tablebases: %s", error)
			self.tablebase = None
		self.spoiled_moves = 0
		self.hints_used = 0
		# The tablebase closes with the window, not with the end of the game:
		# after checkmate, the verdict and best moves are still available to review the position.
		chessboard_closed_signal.connect(lambda sender: self.close_judge(), sender=self)

	def close_judge(self):
		if self.tablebase is not None:
			try:
				self.tablebase.close()
			except Exception:
				nvda_log.debug("chessmart: tablebase close failed", exc_info=True)
			self.tablebase = None

	def judge_speech(self, move: chess.Move) -> list:
		"""What to say after the player's `move`, if the tablebase has anything to say."""
		verdict = judge.judge_move(self.tablebase, self.board, move)
		if verdict is None:
			return []
		text = judge.describe_spoiled(verdict)
		if text is None:
			return []
		self.spoiled_moves += 1
		return [
			speech.commands.BreakCommand(250),
			speech.commands.WaveFileCommand(GameSound.invalid.filename),
			speech.commands.BreakCommand(150),
			text,
		]

	def _no_judge_speech(self) -> str:
		if self.tablebase is None:
			# Translators: Spoken when a tablebase key is pressed and no tablebases are installed.
			return _("No tablebases installed. Download them from the Endgames dialog.")
		# Translators: Spoken when the position is not covered by the installed tablebases.
		return _("No tablebase for this position.")

	def announce_verdict(self):
		verdict = judge.probe(self.tablebase, self.board)
		if verdict is None:
			speak_next([self._no_judge_speech()])
			return
		color_name = self.game_announcer.color_name(self.board.turn)
		speak_next([judge.describe_verdict(verdict, color_name)])

	def announce_best_moves(self):
		best = judge.best_moves(self.tablebase, self.board)
		if not best:
			speak_next([self._no_judge_speech()])
			return
		self.hints_used += 1
		moves = ", ".join(spoken_move(self.board, move) for move in best[:3])
		if len(best) == 1:
			# Translators: Spoken with the only move that keeps the tablebase result, e.g. "Only move: Kd6".
			speak_next([_("Only move: {moves}").format(moves=moves)])
		else:
			# Translators: Spoken with the moves that keep the tablebase result.
			speak_next([_("Best moves: {moves}").format(moves=moves)])


def _record(lesson_id: str, position_id: str, **fields) -> None:
	"""Records an attempt; logging is a convenience and never breaks training."""
	try:
		connection = endgame_log.open_log()
		try:
			endgame_log.record(connection, lesson_id, position_id, **fields)
		finally:
			connection.close()
	except Exception as error:
		nvda_log.warning("chessmart: could not record the endgame attempt: %s", error)


# ---------------------------------------------------------------- mate drill


class EndgameDrillCell(UserDrivenCell):
	parent: "EndgameDrillChessboard"

	# Gestures live here, not in a mixin: NVDA's metaclass only collects
	# `script_*` from the class's own namespace (see baseObject.ScriptableType).

	@script(gesture="kb:tab")
	def script_open_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_open_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)

	@script(gesture="kb:control+f1")
	def script_drill_goal(self, gesture):
		self.parent.announce_goal()

	@script(gesture="kb:control+n")
	def script_new_position(self, gesture):
		self.parent.new_position()

	@script(gesture="kb:control+t")
	def script_verdict(self, gesture):
		self.parent.announce_verdict()

	@script(gesture="kb:control+shift+t")
	def script_best_move(self, gesture):
		self.parent.announce_best_moves()


class EndgameDrillChessboard(TablebaseJudgeMixin, UserEngineChessboard):
	cell_class = EndgameDrillCell
	can_draw = False

	def __init__(
		self,
		*args,
		drill: EndgameDrill,
		lesson_id: str = "",
		new_position_callback: typing.Callable[[], None] | None = None,
		**kwargs,
	):
		super().__init__(*args, **kwargs)
		self.drill = drill
		self.lesson_id = lesson_id or drill.drill_id
		self.new_position_callback = new_position_callback
		self._started_at = time.monotonic()
		self._recorded = False
		self._start_fen = self.board.fen()
		self.open_judge()
		self.build_action_bar(
			[
				# Translators: Action in the endgame toolbar.
				(_("Repeat goal"), self._from_actions(self.announce_goal)),
				# Translators: Action in the endgame toolbar.
				(_("Tablebase verdict"), self._from_actions(self.announce_verdict)),
				# Translators: Action in the endgame toolbar.
				(_("Best moves"), self._from_actions(self.announce_best_moves)),
				# Translators: Action in the endgame toolbar.
				(_("New position"), self._from_actions(self.new_position)),
				# Translators: Action in the endgame toolbar.
				(_("Back to board"), self.focus_board_from_actions),
			],
		)
		self.dialog.SetTitle(drill_label(drill))
		queueHandler.queueFunction(queueHandler.eventQueue, self.announce_goal, True)

	def leave_prompt(self):
		if not self.board.move_stack:
			return None
		# Translators: Asked when Escape is pressed during an endgame drill.
		return _("Leave the drill? The position will be lost.")

	def announce_goal(self, with_shortcuts=False):
		spoken: list = [
			drill_label(self.drill),
			speech.commands.BreakCommand(150),
			drill_description(self.drill),
		]
		if with_shortcuts:
			spoken.extend(
				[
					speech.commands.BreakCommand(150),
					# Translators: Spoken once when an endgame drill opens.
					_(
						"Control+F1 repeats the goal. Control+N opens another position. Control+T asks the tablebase. Tab opens the actions.",
					),
				],
			)
		speak_next(spoken)

	def new_position(self):
		"""Another position of the same endgame: closes this board and whoever opened it opens the next one.

		Closing goes through the dialog's `onClose`, which shuts down the engine
		and the clock; reopening is the menu's job, since it knows how to set
		up the game. No confirmation: restarting is normal training use.
		"""
		callback = self.new_position_callback
		self.hide_board_gui()
		if callback is not None:
			queueHandler.queueFunction(queueHandler.eventQueue, callback)

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		extra = []
		if self.board.turn is self.prospective and move in self.board.legal_moves:
			extra = self.judge_speech(move)
		super().move_piece_and_check_game_status(move, pre_speech, list(post_speech) + extra)

	def _seconds_left(self) -> float | None:
		try:
			return self.time_control.chess_clocks[chess.WHITE].remaining
		except (KeyError, AttributeError):
			return None

	def _get_game_over_messages(self):
		yield from super()._get_game_over_messages()
		seconds = None if isinstance(self.time_control, NullChessTimeControl) else self._seconds_left()
		for message in drill_result_messages(self.drill, self.board, seconds):
			yield speech.commands.BreakCommand(250)
			yield message
		if self.hints_used:
			yield speech.commands.BreakCommand(250)
			# Translators: Spoken at the end of a drill or lesson that used tablebase hints; {hints} is a number.
			yield _("With {hints} hints from the tablebase: it counts as practice, not as held.").format(
				hints=self.hints_used,
			)
		yield speech.commands.BreakCommand(250)
		# Translators: Spoken when an endgame drill ends.
		yield _("Control+N opens another position.")

	def game_time_forfeit(self, losing_color):
		super().game_time_forfeit(losing_color)
		if losing_color is chess.WHITE:
			speak_next(
				[
					speech.commands.BreakCommand(250),
					# Translators: Spoken when the player runs out of time in an endgame drill.
					_("Time over with the position won. The technique is what saves the clock."),
					speech.commands.BreakCommand(250),
					_("Control+N opens another position."),
				],
			)

	def game_over(self, dialog_title=None):
		was_over = self.is_game_over
		super().game_over(dialog_title)
		if not was_over:
			self._record_attempt()

	def _record_attempt(self):
		if self._recorded or not self.board.move_stack:
			return
		self._recorded = True
		outcome = self.board.outcome()
		mated = outcome is not None and outcome.termination is chess.Termination.CHECKMATE
		_record(
			self.lesson_id,
			self.drill.drill_id,
			answer_correct=None,
			kept_result=mated and self.spoiled_moves == 0,
			moves=(len(self.board.move_stack) + 1) // 2,
			elapsed_ms=int((time.monotonic() - self._started_at) * 1000),
			outcome=outcome.termination.name.lower() if outcome else "abandoned",
			line=" ".join(move.uci() for move in self.board.move_stack),
			fen=self._start_fen,
			hints=self.hints_used,
		)


# ---------------------------------------------------------------- lesson


class ResultQuestionMenu(MenuObject):
	"""The lesson question: win, draw, or loss, for the player's side."""

	def __init__(self, choice_callback, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.choice_callback = choice_callback
		names = judge.result_names()
		self.answers = (judge.WIN, judge.DRAW, judge.LOSS)
		self.init_container_state(
			[MenuItemObject(name=names[answer], parent=self) for answer in self.answers],
		)

	def on_item_activated(self, item):
		index = self.index_of(item)
		if index is not None:
			self.choice_callback(self.answers[index])

	def close_menu(self):
		# Escape doesn't escape the question: the lesson starts with it.
		return


class EndgameLessonCell(UserDrivenCell):
	parent: "EndgameLessonChessboard"

	@script(gesture="kb:tab")
	def script_open_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_open_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)

	@script(gesture="kb:control+f1")
	def script_lesson_rule(self, gesture):
		self.parent.announce_rule()

	@script(gesture="kb:control+n")
	def script_next_position(self, gesture):
		self.parent.next_position()

	@script(gesture="kb:control+r")
	def script_restart_position(self, gesture):
		self.parent.restart_position()

	@script(gesture="kb:backspace")
	def script_take_back(self, gesture):
		self.parent.take_back()

	@script(gesture="kb:control+t")
	def script_verdict(self, gesture):
		self.parent.announce_verdict()

	@script(gesture="kb:control+shift+t")
	def script_best_move(self, gesture):
		self.parent.announce_best_moves()


class EndgameLessonChessboard(TablebaseJudgeMixin, UserEngineChessboard):
	cell_class = EndgameLessonCell
	can_draw = False

	def __init__(
		self,
		*args,
		lesson: EndgameLesson,
		position: LessonPosition,
		next_callback: typing.Callable[[], None] | None = None,
		restart_callback: typing.Callable[[], None] | None = None,
		**kwargs,
	):
		super().__init__(*args, **kwargs)
		self.lesson = lesson
		self.position = position
		self.next_callback = next_callback
		self.restart_callback = restart_callback
		self.answer: str | None = None
		self.playing = False
		self.take_backs = 0
		self._started_at = time.monotonic()
		self._recorded = False
		self._start_fen = self.board.fen()
		self.open_judge()
		self.build_action_bar(
			[
				# Translators: Action in the endgame toolbar.
				(_("Repeat rule"), self._from_actions(self.announce_rule)),
				(_("Tablebase verdict"), self._from_actions(self.announce_verdict)),
				(_("Best moves"), self._from_actions(self.announce_best_moves)),
				# Translators: Action in the endgame toolbar.
				(_("Take back"), self._from_actions(self.take_back)),
				# Translators: Action in the endgame toolbar.
				(_("Restart position"), self._from_actions(self.restart_position)),
				# Translators: Action in the endgame toolbar.
				(_("Next position"), self._from_actions(self.next_position)),
				(_("Back to board"), self.focus_board_from_actions),
			],
		)
		self.dialog.SetTitle(f"{lesson_label(lesson)}: {position_title(position)}")
		queueHandler.queueFunction(queueHandler.eventQueue, self._ask)

	# -- the question -----------------------------------------------------------

	def make_first_move(self):
		# The engine only plays after the answer, and only if the move is its turn.
		return

	def _ask(self):
		color_name = self.game_announcer.color_name(self.prospective)
		turn_name = self.game_announcer.color_name(self.board.turn)
		question = ResultQuestionMenu(
			choice_callback=self._on_answer,
			# Translators: The lesson question, e.g. "The king leads. You play white, white to move. Win, draw or loss for white?".
			name=_("{title}. You play {color}, {turn} to move. Win, draw or loss for {color}?").format(
				title=position_title(self.position),
				color=color_name,
				turn=turn_name,
			),
			parent=self,
		)
		self._current_focused_object = question
		GameSound.menu_open.play()
		eventHandler.queueEvent("gainFocus", question)

	def _on_answer(self, answer: str):
		self._current_focused_object = None
		self.answer = answer
		correct = answer == self.position.expected
		names = judge.result_names()
		spoken: list = [
			speech.commands.WaveFileCommand((GameSound.game_over if correct else GameSound.invalid).filename),
			speech.commands.BreakCommand(200),
		]
		if correct:
			# Translators: Spoken when the lesson question was answered correctly.
			spoken.append(_("Correct: {result}.").format(result=names[self.position.expected]))
		else:
			# Translators: Spoken when the lesson question was answered wrongly, e.g. "No: it is a draw."
			spoken.append(_("No: it is a {result}.").format(result=names[self.position.expected].lower()))
		spoken.extend([speech.commands.BreakCommand(300), position_rule(self.position)])
		spoken.extend([speech.commands.BreakCommand(300), play_goal(self.position)])
		if self.position.playable:
			spoken.extend(
				[
					speech.commands.BreakCommand(200),
					# Translators: Spoken once before the play phase of a lesson.
					_(
						"Control+F1 repeats the rule. Backspace takes a move back. Control+T asks the tablebase. Control+N goes to the next position. Tab opens the actions.",
					),
				],
			)
		speak_next(spoken)
		if self.position.playable:
			self.playing = True
			self._started_at = time.monotonic()
			self.set_focus_to_cell(self._focused_cell)
			if self.board.turn is not self.prospective:
				self.get_next_move_from_engine().add_done_callback(
					lambda future: wx.CallAfter(self.engine_play, future),
				)
		else:
			self._record_attempt(outcome="question", kept=correct)
			self.game_over(dialog_title=self.dialog.GetTitle())
			self.set_focus_to_cell(self._focused_cell)

	def announce_rule(self):
		if self.answer is None:
			self._ask()
			return
		speak_next(
			[position_title(self.position), speech.commands.BreakCommand(150), position_rule(self.position)],
		)

	# -- playing ------------------------------------------------------------------

	def leave_prompt(self):
		if not self.playing or self.is_game_over or not self.board.move_stack:
			return None
		# Translators: Asked when Escape is pressed while playing out a lesson position.
		return _("Leave the lesson? This attempt will count as not held.")

	def activate_cell(self, cell):
		if not self.playing:
			GameSound.invalid.play()
			return
		super().activate_cell(cell)

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		extra = []
		if self.board.turn is self.prospective and move in self.board.legal_moves:
			extra = self.judge_speech(move)
			if extra:
				extra.extend(
					[
						speech.commands.BreakCommand(150),
						# Translators: Spoken after the judge flagged a move in a lesson.
						_("Backspace takes it back."),
					],
				)
		super().move_piece_and_check_game_status(move, pre_speech, list(post_speech) + extra)

	def take_back(self):
		"""Undoes the last pair of moves (the player's and the engine's reply)."""
		if not self.playing or self.is_game_over or self.board.turn is not self.prospective:
			GameSound.invalid.play()
			return
		if len(self.board.move_stack) < 2:
			GameSound.invalid.play()
			return
		self.board.pop()
		undone = self.board.pop()
		for _unused in range(2):
			if self.score_sheet_menu.items:
				self.score_sheet_menu.items.pop(0)
		self.take_backs += 1
		self.dialog.set_board_image()
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		speak_next(
			[
				# Translators: Spoken after a move was taken back in a lesson, e.g. "Took back Kd6. Your move."
				_("Took back {move}. Your move.").format(move=spoken_move(self.board, undone)),
			],
		)

	def _get_game_over_messages(self):
		yield from super()._get_game_over_messages()
		kept = self._kept_result()
		yield speech.commands.BreakCommand(250)
		if kept and self.spoiled_moves == 0 and self.take_backs == 0:
			# Translators: Spoken when a lesson position was played out keeping the theoretical result.
			yield _("Result held, with no slip. This one is yours.")
		elif kept:
			# Translators: Spoken when the result was kept but with slips or take-backs along the way.
			yield _(
				"Result held, with {slips} slips and {takebacks} take-backs. Once more without them.",
			).format(
				slips=self.spoiled_moves,
				takebacks=self.take_backs,
			)
		else:
			# Translators: Spoken when the lesson position was not held.
			yield _("The result slipped. Control+R plays the same position again.")
		if self.hints_used:
			yield speech.commands.BreakCommand(250)
			yield _("With {hints} hints from the tablebase: it counts as practice, not as held.").format(
				hints=self.hints_used,
			)
		yield speech.commands.BreakCommand(250)
		# Translators: Spoken at the end of a lesson position.
		yield _("Control+N goes to the next position.")

	def _kept_result(self) -> bool:
		outcome = self.board.outcome()
		if outcome is None:
			return False
		if outcome.winner is None:
			actual = judge.DRAW
		else:
			actual = judge.WIN if outcome.winner is self.prospective else judge.LOSS
		return actual == self.position.expected

	def game_over(self, dialog_title=None):
		was_over = self.is_game_over
		super().game_over(dialog_title)
		if not was_over:
			if self.playing:
				outcome = self.board.outcome()
				self._record_attempt(
					outcome=outcome.termination.name.lower() if outcome else "abandoned",
					kept=self._kept_result() and self.spoiled_moves == 0 and self.take_backs == 0,
				)

	def _record_attempt(self, *, outcome: str, kept: bool):
		if self._recorded or self.answer is None:
			return
		if self.playing and not self.board.move_stack and outcome == "abandoned":
			return
		self._recorded = True
		_record(
			self.lesson.lesson_id,
			self.position.position_id,
			answer_correct=self.answer == self.position.expected,
			kept_result=kept,
			moves=(len(self.board.move_stack) + 1) // 2,
			elapsed_ms=int((time.monotonic() - self._started_at) * 1000),
			outcome=outcome,
			line=" ".join(move.uci() for move in self.board.move_stack),
			fen=self._start_fen,
			hints=self.hints_used,
		)

	# -- navigation ------------------------------------------------------------------

	def next_position(self):
		callback = self.next_callback
		if callback is None:
			# Translators: Spoken when Control+N is pressed on the last position of a lesson.
			speak_next([_("This was the last position of the lesson.")])
			return
		self.hide_board_gui()
		queueHandler.queueFunction(queueHandler.eventQueue, callback)

	def restart_position(self):
		callback = self.restart_callback
		if callback is None:
			return
		self.hide_board_gui()
		queueHandler.queueFunction(queueHandler.eventQueue, callback)
