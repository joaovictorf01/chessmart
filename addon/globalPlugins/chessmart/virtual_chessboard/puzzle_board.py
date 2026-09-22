# coding: utf-8
# pyright: basic

import dataclasses
import functools
import time

import api
import controlTypes
import eventHandler
import queueHandler
import speech
import speech.commands
import ui
import wx
from logHandler import log
from scriptHandler import getLastScriptRepeatCount, script

from ..sounds import GameSound
from ..speaking import speak_next
from ..i18n import _
from ..tactic.models import AttemptResult
from ..training_session import PuzzleInfo, TrainingSession
from .ui_components import MenuItemObject, MenuObject
from .user_driven import UserDrivenCell, UserDrivenChessboard


PUZZLE_FIRST_MOVE_DELAY_MS = 1200
PUZZLE_REPLY_DELAY_MS = 900
PUZZLE_SOLVED_DELAY_MS = 250


@dataclasses.dataclass
class AttemptState:
	"""Everything the current puzzle attempt needs to remember. Starts zeroed for each puzzle."""

	# When the player's turn started, i.e. after the automatic move.
	# None means the attempt hasn't started yet.
	started_at: float | None = None
	mistakes: int = 0
	hints_used: int = 0
	# Index in `solution_moves` of the next expected move (the player's or the opponent's).
	solution_index: int = 0
	# Already written to the database. Recording can happen partway through the
	# puzzle (on the first mistake) or at the end, but never twice.
	recorded: bool = False
	# Lichess rule: the first wrong move already settles the rating as a
	# loss. Finishing the puzzle after that is for learning and no longer
	# affects the number.
	settled_by_mistake: bool = False
	# Retry with Control+R: with the solution already known, it measures nothing.
	is_retry: bool = False
	# Already counted in the session numbers. Separate from `recorded` because
	# the session counts the puzzle once, at the end, and the database write may have happened earlier.
	counted_in_session: bool = False
	# Finished with Control+Enter: counts as solved in the database, but the
	# session reports how many were finished this way. A trainer that hides
	# this measures the will to finish, not the tactic.
	auto_solved: bool = False

	@property
	def started(self) -> bool:
		return self.started_at is not None

	@property
	def touched(self) -> bool:
		"""The player did something in this puzzle: a move, a mistake, or a hint.

		This separates "gave up" from "never looked at it": a puzzle that was
		loaded and abandoned (immediate Control+N, accidental Escape) is not a
		loss, and doesn't go into the database or the session numbers. A hint
		counts as touched so it can't be used to peek at the solution for free.
		"""
		return self.solution_index > 0 or self.mistakes > 0 or self.hints_used > 0

	def elapsed_ms(self) -> int:
		if self.started_at is None:
			return 0
		return max(1, int((time.monotonic() - self.started_at) * 1000))


@dataclasses.dataclass
class SessionStats:
	"""The session's numbers, in memory. Each puzzle is counted once, when it finishes."""

	attempts: int = 0
	solved: int = 0
	solved_after_mistake: int = 0
	mistakes: int = 0
	hints: int = 0
	revealed: int = 0

	def count(self, attempt: AttemptState, solved: bool) -> None:
		self.attempts += 1
		self.mistakes += attempt.mistakes
		self.hints += attempt.hints_used
		if solved and attempt.settled_by_mistake:
			self.solved_after_mistake += 1
		elif solved:
			self.solved += 1
			if attempt.auto_solved:
				self.revealed += 1

	def status_label(self) -> str:
		"""Label for the actions bar button. Memory only: read on every Tab."""
		if not self.attempts:
			return _("Session status")
		return _("Session status: {solved} of {attempts} solved").format(
			solved=self.solved,
			attempts=self.attempts,
		)

	def summary(self) -> str:
		if not self.attempts:
			return _("Session just started: no finished puzzle yet.")
		summary = _("Session: {solved} solved out of {attempts}.").format(
			solved=self.solved,
			attempts=self.attempts,
		)
		details = []
		if self.solved_after_mistake:
			details.append(
				_("Solved after a mistake, not rated: {count}.").format(count=self.solved_after_mistake),
			)
		if self.revealed:
			details.append(_("{count} of them revealed with Control+Enter.").format(count=self.revealed))
		if self.mistakes:
			details.append(_("Mistakes in the session: {count}.").format(count=self.mistakes))
		if self.hints:
			details.append(_("Hints in the session: {count}.").format(count=self.hints))
		return " ".join([summary, *details])


class TrainingActionItem(MenuItemObject):
	role = controlTypes.Role.BUTTON

	def __init__(self, *args, callback, **kwargs):
		super().__init__(*args, **kwargs)
		self.callback = callback
		self.bindGesture("kb:tab", "go_next")
		self.bindGesture("kb:shift+tab", "go_prev")
		self.bindGesture("kb:rightarrow", "go_next")
		self.bindGesture("kb:leftarrow", "go_prev")


class TrainingActionsBar(MenuObject):
	role = controlTypes.Role.TOOLBAR
	use_default_navigation_scripts = False

	def __init__(self, *args, items, **kwargs):
		super().__init__(*args, **kwargs)
		action_items = [
			TrainingActionItem(parent=self, name=name, callback=callback) for name, callback in items
		]
		self.init_container_state(
			action_items,
			on_top_edge=self.parent.focus_board_from_actions,
			on_bottom_edge=self.parent.focus_board_from_actions,
		)

	def close_menu(self):
		self.parent.focus_board_from_actions()

	def on_item_activated(self, item):
		item.callback()


class PuzzleCell(UserDrivenCell):
	parent: "PuzzleChessboard"

	@script(gesture="kb:tab")
	def script_open_training_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_open_training_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)

	@script(gesture="kb:control+f1")
	def script_puzzle_info(self, gesture):
		self.parent.announce_puzzle_info()

	@script(gesture="kb:control+f2")
	def script_session_status(self, gesture):
		self.parent.announce_training_status()

	@script(gesture="kb:control+h")
	def script_hint(self, gesture):
		self.parent.speak_hint()

	@script(gesture="kb:control+n")
	def script_next_puzzle(self, gesture):
		# Puzzle finished: Control+N goes through immediately. Puzzle in
		# progress: requires a second press, because an accidental Control+N
		# throws away the puzzle on the board and its id with it (never
		# reaches the database).
		puzzle = self.parent.puzzle
		if puzzle is not None and self.parent.current_expected_move is not None:
			if getLastScriptRepeatCount() == 0:
				speak_next(
					[
						_("Press Control+N twice to skip tactic {puzzle_id}.").format(
							puzzle_id=puzzle.puzzle_id,
						),
					],
				)
				return
			log.info(f"chessmart: tactic {puzzle.puzzle_id} skipped with Control+N")
			speak_next([_("Skipping tactic {puzzle_id}.").format(puzzle_id=puzzle.puzzle_id)])
		self.parent.next_puzzle()

	@script(gesture="kb:control+r")
	def script_retry_puzzle(self, gesture):
		self.parent.retry_current_puzzle()

	@script(gesture="kb:control+enter")
	def script_solve_puzzle(self, gesture):
		solution_move = self.parent.current_expected_move
		if solution_move is None:
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					_("This tactic is already finished."),
				],
			)
			return
		if getLastScriptRepeatCount() > 0:
			self.parent.move_piece_and_check_game_status(solution_move, auto_solved=True)
		else:
			speak_next([_("Press Control+Enter twice to play the expected move.")])


class PuzzleChessboard(UserDrivenChessboard):
	cell_class = PuzzleCell
	can_draw = False
	can_resign = False

	def __init__(self, *args, session: TrainingSession, **kwargs):
		super().__init__(*args, **kwargs)
		self.session = session
		self.puzzle: PuzzleInfo | None = None
		self._attempt = AttemptState()
		self._stats = SessionStats()
		self._announced_puzzle_shortcuts = False
		# Incremented for each puzzle loaded; callbacks scheduled with
		# wx.CallLater carry the value from when they were scheduled and bail out if it changed.
		self._callback_token = 0
		# What the last write changed in the rating. Kept around because
		# recording the attempt and announcing the result happen at different moments.
		self._last_rating: AttemptResult | None = None
		self._actions_bar = TrainingActionsBar(
			parent=self,
			name=_("Training actions"),
			items=[
				(_("Repeat instruction"), self.repeat_current_instruction),
				(_("Puzzle goal"), self.announce_puzzle_goal),
				(_("Hint"), self.speak_hint),
				(_("Puzzle details"), self.announce_puzzle_info),
				(_("Session status"), self.announce_training_status),
				(_("Restart puzzle"), self.restart_puzzle_from_actions),
				(_("Next puzzle"), self.next_puzzle_from_actions),
				(_("Back to board"), self.focus_board_from_actions),
			],
		)
		# Found by callback, not by index: the button order changes.
		self._session_status_item = next(
			(item for item in self._actions_bar if item.callback == self.announce_training_status),
			None,
		)
		self.next_puzzle()

	@property
	def current_expected_move(self):
		if self.puzzle is None:
			return None
		if not (0 <= self._attempt.solution_index < len(self.puzzle.solution_moves)):
			return None
		return self.puzzle.solution_moves[self._attempt.solution_index]

	def leave_prompt(self):
		# Always asks: leaving loses the session scoreboard too, not just the
		# puzzle. The text says whether the current puzzle will count as unsolved.
		if self._attempt.touched and not self._attempt.recorded:
			# Translators: Asked when Escape is pressed during a puzzle the player has already started solving.
			return _("Leave training? The current puzzle will count as unsolved.")
		# Translators: Asked when Escape is pressed during tactics training.
		return _("Leave training? The session status will be lost.")

	def hide_board_gui(self):
		# Invalidates any pending first move or opponent reply still scheduled:
		# they must not land on a closed window.
		self._callback_token += 1
		self._finish_attempt(solved=False)
		super().hide_board_gui()

	# -- focus: board and actions bar --------------------------------------

	def focus_action_bar(self, reverse=False):
		if not self._actions_bar:
			return
		self._current_focused_object = self._actions_bar
		target_index = len(self._actions_bar) - 1 if reverse else 0
		self._actions_bar.set_current(target_index)
		eventHandler.executeEvent("gainFocus", self._actions_bar)

	def focus_board_from_actions(self):
		self._current_focused_object = None
		self.set_focus_to_cell(self._focused_cell)

	def _clear_action_focus(self):
		self._current_focused_object = None

	def restart_puzzle_from_actions(self):
		self._clear_action_focus()
		self.retry_current_puzzle()

	def next_puzzle_from_actions(self):
		self._clear_action_focus()
		self.next_puzzle()

	# -- loading puzzles -----------------------------------------------------

	def next_puzzle(self):
		self._finish_attempt(solved=False)
		next_puzzle = self.session.next_puzzle()
		if next_puzzle is None:
			if self.puzzle is None:
				speak_next(
					[
						speech.commands.WaveFileCommand(GameSound.invalid.filename),
						_("No tactics were found for the current selection."),
					],
				)
				self.game_over(_("No tactics available"))
				return
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					_("No more tactics in this session."),
					speech.commands.BreakCommand(100),
					_("Press Control+R to retry the current puzzle."),
				],
			)
			return

		self.puzzle = next_puzzle
		self._load_current_puzzle(is_retry=False)
		# With this puzzle on the board, the next one is already being drawn.
		self.session.prefetch_next()

	def retry_current_puzzle(self):
		if self.puzzle is None:
			ui.message(_("No puzzle loaded."))
			return
		self._finish_attempt(solved=False)
		self._load_current_puzzle(is_retry=True)

	def _load_current_puzzle(self, is_retry=False):
		puzzle = self.puzzle
		assert puzzle is not None, "load is only called right after a puzzle was drawn"
		self._callback_token += 1
		self._attempt = AttemptState()
		if is_retry:
			# The first attempt at this puzzle was already recorded (as a
			# failure when the restart was requested, or on the first wrong
			# move). Retrying with the solution already known measures
			# nothing: not the rating, not the session.
			self._attempt.is_retry = True
			self._attempt.recorded = True
			self._attempt.counted_in_session = True
		self.is_game_over = False
		self.board.reset()
		self.board.set_fen(puzzle.fen)
		self.prospective = not self.board.turn
		self.score_sheet_menu.clear()
		self._update_dialog_title()
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		if is_retry:
			pre_speech = [_("Restarting puzzle.")]
		elif self._announced_puzzle_shortcuts:
			pre_speech = [_("Loading next training puzzle.")]
		else:
			pre_speech = [_("Loading training puzzle.")]
		filters_text = self.session.describe_filters()
		if filters_text and not self._announced_puzzle_shortcuts:
			pre_speech.extend(
				[
					speech.commands.BreakCommand(120),
					filters_text,
				],
			)
		queueHandler.queueFunction(queueHandler.eventQueue, speak_next, pre_speech)
		current_token = self._callback_token
		wx.CallLater(
			PUZZLE_FIRST_MOVE_DELAY_MS,
			functools.partial(self._perform_puzzle_first_move, current_token),
		)

	def _update_dialog_title(self):
		if self.puzzle is None:
			self.dialog.SetTitle(_("Chessboard Tactics"))
			return
		rating = self.puzzle.rating if self.puzzle.rating is not None else _("unknown")
		self.dialog.SetTitle(
			_("Tactic {puzzle_id} - rating {rating}").format(
				puzzle_id=self.puzzle.puzzle_id,
				rating=rating,
			),
		)

	def _perform_puzzle_first_move(self, callback_token):
		if callback_token != self._callback_token or self.puzzle is None:
			return
		king_square = self.board.king(self.prospective)
		king_square_focus_callback = functools.partial(self.set_focus_to_cell, king_square)
		color_name = self.game_announcer.color_name(self.prospective)
		post_speech = [
			"",
			speech.commands.BreakCommand(250),
			_("{color} to move.").format(color=color_name),
		]
		if not self._announced_puzzle_shortcuts:
			post_speech.extend(
				[
					speech.commands.BreakCommand(150),
					_("Control+H for a hint."),
					speech.commands.BreakCommand(100),
					_("Control+N for the next puzzle."),
					speech.commands.BreakCommand(100),
					_("Control+R to restart this puzzle."),
					speech.commands.BreakCommand(100),
					_("Control+F1 for puzzle details."),
					speech.commands.BreakCommand(100),
					_("Press Tab for training actions."),
					speech.commands.BreakCommand(100),
					_("Control+Enter twice to play the expected move."),
				],
			)
			self._announced_puzzle_shortcuts = True
		post_speech.extend(
			[
				speech.commands.BreakCommand(100),
				speech.commands.CallbackCommand(king_square_focus_callback),
			],
		)
		super().move_piece_and_check_game_status(
			self.puzzle.auto_performed_move,
			pre_speech=(),
			post_speech=post_speech,
		)
		self._attempt.started_at = time.monotonic()

	# -- moves ---------------------------------------------------------------

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=(), auto_solved=False):
		if self.board.turn != self.prospective:
			super().move_piece_and_check_game_status(move, pre_speech, post_speech)
			return

		expected_move = self.current_expected_move
		if expected_move is None:
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					_("This tactic is already finished."),
				],
			)
			return

		if move != expected_move:
			self._attempt.mistakes += 1
			spoken = [
				speech.commands.WaveFileCommand(GameSound.invalid.filename),
				_("That move does not solve the tactic."),
			]
			if self._attempt.mistakes == 1 and not self._attempt.recorded:
				self._write_attempt(solved=False)
				self._attempt.settled_by_mistake = True
				spoken.extend(
					[
						speech.commands.BreakCommand(120),
						_("Counted as a failure. Keep going to learn the solution."),
						speech.commands.BreakCommand(120),
						*self._rating_speech(),
					],
				)
			speak_next(spoken)
			return

		follow_up = list(post_speech)
		if auto_solved:
			self._attempt.auto_solved = True
		else:
			follow_up.extend(
				[
					speech.commands.BreakCommand(100),
					_("Good move."),
				],
			)
		super().move_piece_and_check_game_status(move, pre_speech, follow_up)
		self._attempt.solution_index += 1
		if self.current_expected_move is None:
			self._finish_attempt(solved=True)
			current_token = self._callback_token
			wx.CallLater(
				PUZZLE_SOLVED_DELAY_MS,
				functools.partial(self._announce_puzzle_solved, current_token),
			)
			return

		current_token = self._callback_token
		wx.CallLater(
			PUZZLE_REPLY_DELAY_MS,
			functools.partial(self._play_opponent_reply, current_token),
		)

	def _play_opponent_reply(self, callback_token):
		if callback_token != self._callback_token or self.puzzle is None:
			return
		reply = self.current_expected_move
		if reply is None or self.board.turn == self.prospective:
			return

		# The focus change must be DEFERRED to the event queue, not called
		# directly from here. Called directly, it runs in the middle of speech
		# processing: the focus event cancels the very sequence that was being
		# spoken, and the description of the opponent's move never comes out --
		# that was the bug. pgn_player, which plays moves the same way and
		# always worked, already used this pattern.
		# Focuses the square WHERE THE PIECE LANDED, not the king: whoever is
		# solving the tactic needs to know where the opponent played, since
		# that's what they'll calculate from. It's the same destination pgn_player uses.
		def focus_callback():
			queueHandler.queueFunction(queueHandler.eventQueue, self.set_focus_to_cell, reply.to_square)

		color_name = self.game_announcer.color_name(self.prospective)
		super().move_piece_and_check_game_status(
			reply,
			pre_speech=(),
			post_speech=[
				speech.commands.BreakCommand(150),
				_("{color} to move.").format(color=color_name),
				speech.commands.BreakCommand(100),
				speech.commands.CallbackCommand(focus_callback),
			],
		)
		self._attempt.solution_index += 1

	def _announce_puzzle_solved(self, callback_token):
		if callback_token != self._callback_token or self.puzzle is None:
			return
		self.is_game_over = True
		self.dialog.SetTitle(_("Solved tactic {puzzle_id}").format(puzzle_id=self.puzzle.puzzle_id))
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		speak_next(
			[
				speech.commands.BreakCommand(200),
				speech.commands.WaveFileCommand(GameSound.puzzle_solved.filename),
				speech.commands.BreakCommand(150),
				_("Tactic solved."),
				speech.commands.BreakCommand(120),
				*self._solved_rating_speech(),
				_("Control+N loads another puzzle."),
				speech.commands.BreakCommand(100),
				_("Press Tab for training actions."),
				speech.commands.BreakCommand(100),
				_("Control+R restarts this one."),
			],
		)

	# -- rating ---------------------------------------------------------------

	def _solved_rating_speech(self):
		"""What to say about the rating when the puzzle finishes solved.

		Only a clean attempt affects the rating. In the other two situations the
		outcome was already settled earlier, and saying so is better than
		repeating the loss's number right after "Tactic solved".
		"""
		if self._attempt.is_retry:
			return [_("Retry: not rated."), speech.commands.BreakCommand(120)]
		if self._attempt.settled_by_mistake:
			return [
				_("Solved after a mistake: already counted as a failure."),
				speech.commands.BreakCommand(120),
			]
		return self._rating_speech()

	def _rating_speech(self):
		"""The rating sentence for the announcement, or nothing when there's nothing to say.

		Returns a list meant to be unpacked inside speak_next: this way, when
		there is no rating, nothing is added and no leftover pause sounds like hesitation.
		"""
		result = self._last_rating
		if result is None:
			return []
		delta = result.rating_delta
		if delta > 0:
			text = _("Rating {rating}, up {delta}.")
		elif delta < 0:
			text = _("Rating {rating}, down {delta}.")
		else:
			text = _("Rating {rating}, unchanged.")
		if result.provisional:
			# While the deviation is high the number is still a guess, and
			# saying so is more useful than announcing a precise value that
			# will swing by hundreds of points over the next few attempts.
			text = _("Provisional ") + text
		return [
			text.format(rating=result.rating, delta=abs(delta)),
			speech.commands.BreakCommand(120),
		]

	@script(
		# Translators: Input help message for the report tactics rating command.
		description=_("Report your current tactics rating"),
		gesture="kb:control+shift+r",
	)
	def script_report_rating(self, gesture):
		"""Speaks the current rating at any time, without waiting for the puzzle to end."""
		try:
			summary = self.session.rating()
		except Exception:
			log.exception("chessmart: failed to read the rating")
			summary = None
		if summary is None:
			ui.message(_("No tactics rating yet."))
			return
		if summary.rated_attempts:
			attempts_text = _("from {count} rated attempts").format(count=summary.rated_attempts)
		else:
			attempts_text = _("no rated attempts yet")
		if summary.provisional:
			ui.message(
				_("Provisional rating {rating}, somewhere between {low} and {high}, {attempts}.").format(
					rating=summary.rating,
					low=summary.interval_low,
					high=summary.interval_high,
					attempts=attempts_text,
				),
			)
		else:
			ui.message(
				_("Rating {rating}, {attempts}.").format(rating=summary.rating, attempts=attempts_text),
			)

	# -- spoken actions --------------------------------------------------------

	def repeat_current_instruction(self):
		if self.puzzle is None:
			ui.message(_("No puzzle loaded."))
			return
		if self.current_expected_move is None:
			speak_next(
				[
					_("Puzzle solved."),
					speech.commands.BreakCommand(100),
					_("Use Tab for next puzzle or restart."),
				],
			)
			return
		color_name = self.game_announcer.color_name(self.prospective)
		speak_next(
			[
				_("{color} to move.").format(color=color_name),
				speech.commands.BreakCommand(100),
				_("Use the arrow keys to inspect the board."),
				speech.commands.BreakCommand(100),
				_("Use Enter to make a move on the virtual board."),
				speech.commands.BreakCommand(100),
				_("Use Tab for training actions."),
			],
		)

	def announce_puzzle_goal(self):
		if self.puzzle is None:
			ui.message(_("No puzzle loaded."))
			return
		color_name = self.game_announcer.color_name(self.prospective)
		messages = [
			_("Goal: find the best continuation for {color}.").format(color=color_name),
		]
		if self.puzzle.themes:
			messages.extend(
				[
					speech.commands.BreakCommand(100),
					_("This puzzle trains {themes}.").format(
						themes=", ".join(theme.label for theme in self.puzzle.themes[:3]),
					),
				],
			)
		speak_next(messages)

	def announce_puzzle_info(self):
		puzzle = self.puzzle
		if puzzle is None:
			ui.message(_("No puzzle loaded."))
			return
		theme_names = ", ".join(theme.label for theme in puzzle.themes) or _("No themes")
		spoken_msgs = [
			_("Puzzle {puzzle_id}.").format(puzzle_id=puzzle.puzzle_id),
			speech.commands.BreakCommand(100),
			_("Rating: {rating}.").format(rating=puzzle.rating or _("unknown")),
			speech.commands.BreakCommand(100),
			_("Popularity: {popularity}.").format(
				popularity=puzzle.popularity if puzzle.popularity is not None else _("unknown"),
			),
			speech.commands.BreakCommand(100),
			_("Plays: {plays}.").format(
				plays=puzzle.nb_plays if puzzle.nb_plays is not None else _("unknown"),
			),
			speech.commands.BreakCommand(100),
			_("Themes: {themes}.").format(themes=theme_names),
		]
		if puzzle.opening_tags:
			spoken_msgs.extend(
				[
					speech.commands.BreakCommand(100),
					_("Opening tags: {opening}.").format(opening=puzzle.opening_tags),
				],
			)
		if puzzle.game_url:
			spoken_msgs.extend(
				[
					speech.commands.BreakCommand(100),
					_("Source game available on Lichess."),
				],
			)
		speak_next(spoken_msgs)

	def speak_hint(self):
		expected_move = self.current_expected_move
		if expected_move is None:
			ui.message(_("There are no more hints for this puzzle."))
			return

		puzzle = self.puzzle
		assert puzzle is not None, "there is an expected move, so there is a puzzle"
		hint_messages = []
		if puzzle.themes:
			hint_messages.append(
				_("Hint: themes include {themes}.").format(
					themes=", ".join(theme.label for theme in puzzle.themes[:3]),
				),
			)
		hint_messages.extend(
			[
				_("Hint: the move starts from {square}.").format(
					square=self.spoken_square_name(expected_move.from_square),
				),
				_("Hint: the move ends on {square}.").format(
					square=self.spoken_square_name(expected_move.to_square),
				),
			],
		)
		if self._attempt.hints_used >= len(hint_messages):
			ui.message(_("No more hints for this puzzle."))
			return
		message = hint_messages[self._attempt.hints_used]
		self._attempt.hints_used += 1
		speak_next([message])

	def _player_move_progress(self):
		"""Which player move the puzzle is on, as (current, total).

		`solution_moves` alternates starting with the player: an even index is
		their move, odd is the opponent's reply. The move that sets up the
		position doesn't count -- it's the `auto_performed_move`, played before anything else.
		"""
		assert self.puzzle is not None
		moves = self.puzzle.solution_moves
		total = (len(moves) + 1) // 2
		played = (self._attempt.solution_index + 1) // 2
		return min(played + 1, total), total

	def _current_puzzle_summary(self):
		if self.current_expected_move is None:
			return _("This puzzle is already solved.")
		current_move, total_moves = self._player_move_progress()
		summary = _("This puzzle: your move {current} of {total}.").format(
			current=current_move,
			total=total_moves,
		)
		details = []
		if self._attempt.mistakes:
			details.append(_("Mistakes here: {count}.").format(count=self._attempt.mistakes))
		if self._attempt.hints_used:
			details.append(_("Hints here: {count}.").format(count=self._attempt.hints_used))
		if not details:
			details.append(_("No mistakes and no hints so far."))
		return " ".join([summary, *details])

	def announce_training_status(self):
		"""Speaks what changes first, and omits counters that are at zero.

		The order is deliberate: session, current puzzle, history, filters. The
		filters used to come first, and that's precisely the part that doesn't
		change during training.
		"""
		if self.puzzle is None:
			ui.message(_("No puzzle loaded."))
			return
		history = self.session.attempt_stats()
		parts = [
			self._stats.summary(),
			self._current_puzzle_summary(),
			_("Database history: {solved} solved out of {total} attempts.").format(
				solved=history.solved,
				total=history.total,
			),
			_("Filters: {filters}.").format(filters=self.session.describe_filters() or _("none")),
		]
		spoken = []
		for part in parts:
			if spoken:
				spoken.append(speech.commands.BreakCommand(120))
			spoken.append(part)
		speak_next(spoken)

	# -- closing out the attempt ---------------------------------------------------

	def _finish_attempt(self, solved: bool):
		"""Closes out the current attempt: database (if not already closed) and session.

		A puzzle the player never touched doesn't close as anything: no loss in
		the database, no number in the session. See `AttemptState.touched`.
		"""
		if self.puzzle is None or not self._attempt.started or not self._attempt.touched:
			return
		self._write_attempt(solved=solved)
		if not self._attempt.counted_in_session:
			self._attempt.counted_in_session = True
			self._stats.count(self._attempt, solved)
			if self._session_status_item is not None:
				self._session_status_item.name = self._stats.status_label()

	def _write_attempt(self, solved: bool):
		"""Writes to the database once per attempt. The caller decides when."""
		if self.puzzle is None or not self._attempt.started or self._attempt.recorded:
			return
		try:
			self._last_rating = self.session.record_attempt(
				puzzle_id=self.puzzle.puzzle_id,
				solved=solved,
				mistakes=self._attempt.mistakes,
				hints_used=self._attempt.hints_used,
				elapsed_ms=self._attempt.elapsed_ms(),
			)
		except Exception:
			# Losing the rating for one attempt is annoying; losing the solved
			# puzzle because the database choked would be worse.
			log.exception("chessmart: failed to record the attempt")
			self._last_rating = None
		self._attempt.recorded = True
