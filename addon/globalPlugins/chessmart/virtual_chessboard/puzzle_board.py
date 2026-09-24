# coding: utf-8
# pyright: basic

import datetime
import functools
import time

import api
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
from ..i18n import _, ngettext
from ..tactic.models import AttemptResult
from ..tactic.review import ReviewOutcome
from ..puzzle_attempt import AttemptState, SessionStats, player_move_progress
from ..training_session import PuzzleInfo, TrainingSession
from .actions_bar import ActionsBarMixin
from .user_driven import UserDrivenCell, UserDrivenChessboard


PUZZLE_FIRST_MOVE_DELAY_MS = 1200
PUZZLE_REPLY_DELAY_MS = 900
PUZZLE_SOLVED_DELAY_MS = 250


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

	@script(
		# Translators: Input help message for the report tactics rating command.
		description=_("Report your current tactics rating"),
		gesture="kb:control+shift+r",
	)
	def script_report_rating(self, gesture):
		self.parent.report_rating()

	@script(gesture="kb:control+n")
	def script_next_puzzle(self, gesture):
		# Puzzle finished: Control+N goes through immediately. Puzzle in
		# progress: requires a second press, because an accidental Control+N
		# throws away the puzzle on the board and its id with it (never
		# reaches the database).
		puzzle = self.parent.puzzle
		if self.parent.review_in_progress:
			# Skipping a review asks in a dialog instead of a second press: the
			# point is to make skipping it a decision, not a reflex.
			self.parent.ask_to_skip_reviews()
			return
		if puzzle is not None and self.parent.current_expected_move is not None:
			if getLastScriptRepeatCount() == 0:
				speak_next(
					[
						# Translators: Spoken after the first Control+N during a puzzle: it asks for a second press.
						_("Press Control+N twice to skip tactic {puzzle_id}.").format(
							puzzle_id=puzzle.puzzle_id,
						),
					],
				)
				return
			log.info("chessmart: tactic %s skipped with Control+N", puzzle.puzzle_id)
			# Translators: Spoken on the second Control+N: the puzzle is skipped.
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
					# Translators: Spoken by Control+Enter on a finished puzzle.
					_("This tactic is already finished."),
				],
			)
			return
		if getLastScriptRepeatCount() > 0:
			self.parent.move_piece_and_check_game_status(solution_move, auto_solved=True)
		else:
			# Translators: Spoken after the first Control+Enter: it asks for a second press.
			speak_next([_("Press Control+Enter twice to play the expected move.")])


class PuzzleChessboard(ActionsBarMixin, UserDrivenChessboard):
	cell_class = PuzzleCell
	can_draw = False

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
		# Same, for a review: where the puzzle stands in the queue after it.
		self._last_review: ReviewOutcome | None = None
		# "Reviews done" is said once, when the first new puzzle follows the reviews.
		self._announced_reviews_done = False
		self.install_actions_bar(
			# Translators: Name of the tactics actions bar, reached with Tab.
			name=_("Training actions"),
			items=[
				# Translators: Button of the tactics actions bar.
				(_("Repeat instruction"), self.repeat_current_instruction),
				# Translators: Button of the tactics actions bar.
				(_("Puzzle goal"), self.announce_puzzle_goal),
				# Translators: Button of the tactics actions bar.
				(_("Hint"), self.speak_hint),
				# Translators: Button of the tactics actions bar.
				(_("Puzzle details"), self.announce_puzzle_info),
				(_("Session status"), self.announce_training_status),
				# Translators: Button of the tactics actions bar.
				(_("Restart puzzle"), self.restart_puzzle_from_actions),
				# Translators: Button of the tactics actions bar.
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
	def review_in_progress(self) -> bool:
		"""A review puzzle is on the board and not finished yet."""
		return self.puzzle is not None and self.puzzle.review and self.current_expected_move is not None

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

	def _clear_action_focus(self):
		self._current_focused_object = None

	def restart_puzzle_from_actions(self):
		self._clear_action_focus()
		self.retry_current_puzzle()

	def next_puzzle_from_actions(self):
		self._clear_action_focus()
		if self.review_in_progress:
			self.ask_to_skip_reviews()
			return
		self.next_puzzle()

	# -- reviews ---------------------------------------------------------------

	def ask_to_skip_reviews(self):
		"""The nudge: skipping the reviews is allowed, but it takes a Yes in a dialog where No is the default."""
		from ..graphical_interface.messages import ask_yes_no_from_script

		left = self.session.reviews_left + 1
		ask_yes_no_from_script(
			ngettext(
				# Translators: Asked when the player tries to skip a review of a puzzle they missed; {count} is how many reviews are left, the current one included.
				"Skip the review? Come on, going back to what you missed is what makes the pattern stick. {count} puzzle left to review. Skip it anyway?",
				"Skip the review? Come on, going back to what you missed is what makes the pattern stick. {count} puzzles left to review. Skip them anyway?",
				left,
			).format(count=left),
			# Translators: Title of the dialog asked when the player tries to skip the reviews.
			_("Skip review"),
			self._on_skip_reviews_answer,
			parent=self.dialog,
		)

	def _on_skip_reviews_answer(self, skip: bool):
		if not self.dialog:
			return
		if skip:
			log.info("chessmart: reviews skipped, %d left", self.session.reviews_left + 1)
			self.session.skip_reviews()
			# The current review closes as it stands: untouched, it is not
			# counted and stays due; with a slip, it is recorded as one.
			self._announced_reviews_done = True
			self.next_puzzle()
			return
		# Translators: Spoken when the player chose not to skip the reviews.
		message = _("Good choice. Back to the review.")
		queueHandler.queueFunction(queueHandler.eventQueue, ui.message, message)
		queueHandler.queueFunction(queueHandler.eventQueue, self.set_focus_to_cell, self._focused_cell)

	# -- loading puzzles -----------------------------------------------------

	def next_puzzle(self):
		self._finish_attempt(solved=False)
		next_puzzle = self.session.next_puzzle()
		if next_puzzle is None:
			if self.puzzle is None:
				speak_next(
					[
						speech.commands.WaveFileCommand(GameSound.invalid.filename),
						# Translators: Message shown when no puzzle matches the selection.
						_("No tactics were found for the current selection."),
					],
				)
				# Translators: Title of the message shown when no puzzle matches the selection.
				self.game_over(_("No tactics available"))
				return
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					# Translators: Spoken when the session has no puzzle left for its filters.
					_("No more tactics in this session."),
					speech.commands.BreakCommand(100),
					# Translators: Spoken when the session has no puzzle left.
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
			# Translators: Spoken when a puzzle action is used before a puzzle is on the board.
			ui.message(_("No puzzle loaded."))
			return
		self._finish_attempt(solved=False)
		self._load_current_puzzle(is_retry=True)

	def _load_current_puzzle(self, is_retry=False):
		puzzle = self.puzzle
		assert puzzle is not None, "load is only called right after a puzzle was drawn"
		self._callback_token += 1
		self._attempt = AttemptState(is_review=puzzle.review)
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
			# Translators: Spoken when the puzzle starts again.
			pre_speech = [_("Restarting puzzle.")]
		elif puzzle.review:
			pre_speech = [
				# Translators: Spoken when a review puzzle loads, e.g. "Review 1 of 3: a puzzle you missed. Not rated.".
				_("Review {number} of {total}: a puzzle you missed. Not rated.").format(
					number=self.session.reviews_served,
					total=self.session.reviews_total,
				),
			]
		elif self._announced_puzzle_shortcuts:
			# Translators: Spoken while the next puzzle loads.
			pre_speech = [_("Loading next training puzzle.")]
		else:
			# Translators: Spoken while the first puzzle loads.
			pre_speech = [_("Loading training puzzle.")]
		if (
			not puzzle.review
			and not is_retry
			and self.session.reviews_served
			and not self._announced_reviews_done
		):
			self._announced_reviews_done = True
			# Translators: Spoken when the first new puzzle follows the reviews.
			pre_speech[:0] = [_("Reviews done. Now new puzzles."), speech.commands.BreakCommand(120)]
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
			# Translators: Title of the tactics window before a puzzle is loaded.
			self.dialog.SetTitle(_("Chessboard Tactics"))
			return
		rating = self.puzzle.rating if self.puzzle.rating is not None else _("unknown")
		if self.puzzle.review:
			self.dialog.SetTitle(
				# Translators: Window title during a review of a missed puzzle.
				_("Review of tactic {puzzle_id} - rating {rating}").format(
					puzzle_id=self.puzzle.puzzle_id,
					rating=rating,
				),
			)
			return
		self.dialog.SetTitle(
			# Translators: Window title during a puzzle.
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
			# Translators: Spoken when a puzzle starts; {color} is white or black.
			_("{color} to move.").format(color=color_name),
		]
		if not self._announced_puzzle_shortcuts:
			post_speech.extend(
				[
					speech.commands.BreakCommand(150),
					# Translators: Part of the puzzle shortcuts announcement.
					_("Control+H for a hint."),
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle shortcuts announcement.
					_("Control+N for the next puzzle."),
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle shortcuts announcement.
					_("Control+R to restart this puzzle."),
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle shortcuts announcement.
					_("Control+F1 for puzzle details."),
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle shortcuts announcement.
					_("Press Tab for training actions."),
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle shortcuts announcement.
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
					# Translators: Spoken by Control+Enter on a finished puzzle.
					_("This tactic is already finished."),
				],
			)
			return

		if move != expected_move:
			self._attempt.mistakes += 1
			spoken = [
				speech.commands.WaveFileCommand(GameSound.invalid.filename),
				# Translators: Spoken after a wrong move in a puzzle.
				_("That move does not solve the tactic."),
			]
			if self._attempt.mistakes == 1 and self._attempt.is_review and not self._attempt.recorded:
				# Nothing to settle: a review is recorded once, when it ends.
				self._attempt.settled_by_mistake = True
				spoken.extend(
					[
						speech.commands.BreakCommand(120),
						# Translators: Spoken after the first wrong move of a review: it will be reviewed again.
						_("It comes back tomorrow. Keep going to learn the solution."),
					],
				)
			elif self._attempt.mistakes == 1 and not self._attempt.recorded:
				self._write_attempt(solved=False)
				self._attempt.settled_by_mistake = True
				spoken.extend(
					[
						speech.commands.BreakCommand(120),
						# Translators: Spoken after the first wrong move of a puzzle: the rating is settled, the puzzle goes on.
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
					# Translators: Spoken after a correct move in a puzzle that is not finished yet.
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
				# Translators: Spoken when a puzzle starts; {color} is white or black.
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
		# Translators: Window title after a puzzle is solved.
		self.dialog.SetTitle(_("Solved tactic {puzzle_id}").format(puzzle_id=self.puzzle.puzzle_id))
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		speak_next(
			[
				speech.commands.BreakCommand(200),
				speech.commands.WaveFileCommand(GameSound.puzzle_solved.filename),
				speech.commands.BreakCommand(150),
				# Translators: Spoken when a puzzle is solved.
				_("Tactic solved."),
				speech.commands.BreakCommand(120),
				*self._solved_rating_speech(),
				# Translators: Spoken after a puzzle ends: how to go on.
				_("Control+N loads another puzzle."),
				speech.commands.BreakCommand(100),
				# Translators: Part of the puzzle shortcuts announcement.
				_("Press Tab for training actions."),
				speech.commands.BreakCommand(100),
				# Translators: Spoken after a puzzle ends: how to try it again.
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
			# Translators: Spoken after solving a retried puzzle: retries do not change the rating.
			return [_("Retry: not rated."), speech.commands.BreakCommand(120)]
		if self._attempt.is_review:
			return self._review_speech()
		if self._attempt.settled_by_mistake:
			return [
				# Translators: Spoken when a puzzle is finished after a wrong move.
				_("Solved after a mistake: already counted as a failure."),
				speech.commands.BreakCommand(120),
			]
		return self._rating_speech()

	def _review_speech(self):
		"""Where the reviewed puzzle stands now, and what comes next when it was the last review."""
		outcome = self._last_review
		spoken = []
		if outcome is None:
			pass
		elif outcome.firm:
			# Translators: Spoken after a clean review that makes the puzzle firm.
			spoken.append(_("Clean review. This one is firm: it leaves the review queue."))
		elif outcome.clean and outcome.due is not None:
			days = max(1, (outcome.due - datetime.date.today()).days)
			spoken.append(
				ngettext(
					# Translators: Spoken after a clean review; the puzzle returns once more before it is firm.
					"Clean review. It comes back in {days} day for the last check.",
					"Clean review. It comes back in {days} days for the last check.",
					days,
				).format(days=days),
			)
		elif self._attempt.settled_by_mistake:
			# Translators: Spoken when a review is finished after a wrong move.
			spoken.append(_("Solved after a mistake: it comes back tomorrow."))
		else:
			# Translators: Spoken after a review finished with a hint or Control+Enter.
			spoken.append(_("Solved with help: it comes back tomorrow."))
		if spoken:
			spoken.append(speech.commands.BreakCommand(120))
		if not self.session.reviews_left:
			# Translators: Spoken after the last review of the session.
			spoken.extend([_("That was the last review."), speech.commands.BreakCommand(120)])
		return spoken

	def _rating_speech(self):
		"""The rating sentence for the announcement, or nothing when there's nothing to say.

		Returns a list meant to be unpacked inside speak_next: this way, when
		there is no rating, nothing is added and no leftover pause sounds like hesitation.
		"""
		result = self._last_rating
		if result is None:
			return []
		delta = result.rating_delta
		# While the deviation is high the number is still a guess, and saying
		# so is more useful than announcing a precise value that will swing by
		# hundreds of points over the next few attempts. Whole sentences, not
		# a prefix: the word order changes with the language.
		if result.provisional:
			if delta > 0:
				# Translators: Spoken after a rated puzzle while the rating is uncertain, e.g. "Provisional rating 1450, up 40.".
				text = _("Provisional rating {rating}, up {delta}.")
			elif delta < 0:
				# Translators: Spoken after a rated puzzle while the rating is uncertain, e.g. "Provisional rating 1410, down 40.".
				text = _("Provisional rating {rating}, down {delta}.")
			else:
				# Translators: Spoken after a rated puzzle while the rating is uncertain and did not change.
				text = _("Provisional rating {rating}, unchanged.")
		elif delta > 0:
			# Translators: Spoken after a rated puzzle, e.g. "Rating 1450, up 13.".
			text = _("Rating {rating}, up {delta}.")
		elif delta < 0:
			# Translators: Spoken after a rated puzzle, e.g. "Rating 1432, down 12.".
			text = _("Rating {rating}, down {delta}.")
		else:
			# Translators: Spoken after a rated puzzle that did not change the rating.
			text = _("Rating {rating}, unchanged.")
		return [
			text.format(rating=result.rating, delta=abs(delta)),
			speech.commands.BreakCommand(120),
		]

	def report_rating(self):
		"""Speaks the current rating at any time, without waiting for the puzzle to end.

		Control+Shift+R reaches it through PuzzleCell: the focus is always on a
		square, and NVDA does not run a script of the board (a focus ancestor)
		unless it sets canPropagate.
		"""
		try:
			summary = self.session.rating()
		except Exception:
			log.exception("chessmart: failed to read the rating")
			summary = None
		if summary is None:
			# Translators: Spoken by Control+Shift+R before any rated puzzle.
			ui.message(_("No tactics rating yet."))
			return
		if summary.rated_attempts:
			# Translators: Completes the rating report, e.g. "Rating 1450, from 40 rated attempts".
			attempts_text = _("from {count} rated attempts").format(count=summary.rated_attempts)
		else:
			# Translators: Completes the rating report, e.g. "Provisional rating 1500, ..., no rated attempts yet".
			attempts_text = _("no rated attempts yet")
		if summary.provisional:
			ui.message(
				# Translators: Rating report while the rating is uncertain, e.g. "Provisional rating 1500, somewhere between 1200 and 1800, from 3 rated attempts".
				_("Provisional rating {rating}, somewhere between {low} and {high}, {attempts}.").format(
					rating=summary.rating,
					low=summary.interval_low,
					high=summary.interval_high,
					attempts=attempts_text,
				),
			)
		else:
			ui.message(
				# Translators: Rating report, e.g. "Rating 1450, from 40 rated attempts.".
				_("Rating {rating}, {attempts}.").format(rating=summary.rating, attempts=attempts_text),
			)

	# -- spoken actions --------------------------------------------------------

	def repeat_current_instruction(self):
		if self.puzzle is None:
			# Translators: Spoken when a puzzle action is used before a puzzle is on the board.
			ui.message(_("No puzzle loaded."))
			return
		if self.current_expected_move is None:
			speak_next(
				[
					# Translators: Spoken when a puzzle is solved.
					_("Puzzle solved."),
					speech.commands.BreakCommand(100),
					# Translators: Spoken after a puzzle ends.
					_("Use Tab for next puzzle or restart."),
				],
			)
			return
		color_name = self.game_announcer.color_name(self.prospective)
		speak_next(
			[
				# Translators: Spoken when a puzzle starts; {color} is white or black.
				_("{color} to move.").format(color=color_name),
				speech.commands.BreakCommand(100),
				# Translators: Part of the first-puzzle instructions.
				_("Use the arrow keys to inspect the board."),
				speech.commands.BreakCommand(100),
				# Translators: Part of the first-puzzle instructions.
				_("Use Enter to make a move on the virtual board."),
				speech.commands.BreakCommand(100),
				# Translators: Part of the first-puzzle instructions.
				_("Use Tab for training actions."),
			],
		)

	def announce_puzzle_goal(self):
		if self.puzzle is None:
			# Translators: Spoken when a puzzle action is used before a puzzle is on the board.
			ui.message(_("No puzzle loaded."))
			return
		color_name = self.game_announcer.color_name(self.prospective)
		messages = [
			# Translators: The puzzle goal; {color} is white or black.
			_("Goal: find the best continuation for {color}.").format(color=color_name),
		]
		if self.puzzle.themes:
			messages.extend(
				[
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle goal: its tactical themes.
					_("This puzzle trains {themes}.").format(
						themes=", ".join(theme.label for theme in self.puzzle.themes[:3]),
					),
				],
			)
		speak_next(messages)

	def announce_puzzle_info(self):
		puzzle = self.puzzle
		if puzzle is None:
			# Translators: Spoken when a puzzle action is used before a puzzle is on the board.
			ui.message(_("No puzzle loaded."))
			return
		# Translators: Puzzle details when the puzzle has no themes.
		theme_names = ", ".join(theme.label for theme in puzzle.themes) or _("No themes")
		spoken_msgs = [
			# Translators: Part of the puzzle details: the Lichess puzzle id.
			_("Puzzle {puzzle_id}.").format(puzzle_id=puzzle.puzzle_id),
			speech.commands.BreakCommand(100),
			# Translators: Part of the puzzle details: the puzzle rating.
			_("Rating: {rating}.").format(rating=puzzle.rating or _("unknown")),
			speech.commands.BreakCommand(100),
			# Translators: Part of the puzzle details: the Lichess popularity score.
			_("Popularity: {popularity}.").format(
				popularity=puzzle.popularity if puzzle.popularity is not None else _("unknown"),
			),
			speech.commands.BreakCommand(100),
			# Translators: Part of the puzzle details: how many times it was played on Lichess.
			_("Plays: {plays}.").format(
				plays=puzzle.nb_plays if puzzle.nb_plays is not None else _("unknown"),
			),
			speech.commands.BreakCommand(100),
			# Translators: Part of the puzzle details: its tactical themes.
			_("Themes: {themes}.").format(themes=theme_names),
		]
		if puzzle.opening_tags:
			spoken_msgs.extend(
				[
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle details: the opening of the source game.
					_("Opening tags: {opening}.").format(opening=puzzle.opening_tags),
				],
			)
		if puzzle.game_url:
			spoken_msgs.extend(
				[
					speech.commands.BreakCommand(100),
					# Translators: Part of the puzzle details.
					_("Source game available on Lichess."),
				],
			)
		speak_next(spoken_msgs)

	def speak_hint(self):
		expected_move = self.current_expected_move
		if expected_move is None:
			# Translators: Spoken by Control+H when the puzzle is finished.
			ui.message(_("There are no more hints for this puzzle."))
			return

		puzzle = self.puzzle
		assert puzzle is not None, "there is an expected move, so there is a puzzle"
		hint_messages = []
		if puzzle.themes:
			hint_messages.append(
				# Translators: First hint of a puzzle: its tactical themes.
				_("Hint: themes include {themes}.").format(
					themes=", ".join(theme.label for theme in puzzle.themes[:3]),
				),
			)
		hint_messages.extend(
			[
				# Translators: Second hint of a puzzle: the square the piece moves from.
				_("Hint: the move starts from {square}.").format(
					square=self.spoken_square_name(expected_move.from_square),
				),
				# Translators: Third hint of a puzzle: the destination square.
				_("Hint: the move ends on {square}.").format(
					square=self.spoken_square_name(expected_move.to_square),
				),
			],
		)
		if self._attempt.hints_used >= len(hint_messages):
			# Translators: Spoken when every hint of the puzzle was already given.
			ui.message(_("No more hints for this puzzle."))
			return
		message = hint_messages[self._attempt.hints_used]
		self._attempt.hints_used += 1
		speak_next([message])

	def _player_move_progress(self):
		"""Which player move the puzzle is on, as (current, total); see `player_move_progress`."""
		assert self.puzzle is not None
		return player_move_progress(len(self.puzzle.solution_moves), self._attempt.solution_index)

	def _current_puzzle_summary(self):
		if self.current_expected_move is None:
			# Translators: Part of the puzzle details.
			return _("This puzzle is already solved.")
		current_move, total_moves = self._player_move_progress()
		# Translators: Part of the puzzle details, e.g. "your move 2 of 3".
		summary = _("This puzzle: your move {current} of {total}.").format(
			current=current_move,
			total=total_moves,
		)
		details = []
		if self._attempt.mistakes:
			# Translators: Part of the puzzle details: wrong moves in this puzzle.
			details.append(_("Mistakes here: {count}.").format(count=self._attempt.mistakes))
		if self._attempt.hints_used:
			# Translators: Part of the puzzle details: hints used in this puzzle.
			details.append(_("Hints here: {count}.").format(count=self._attempt.hints_used))
		if not details:
			# Translators: Part of the puzzle details.
			details.append(_("No mistakes and no hints so far."))
		return " ".join([summary, *details])

	def announce_training_status(self):
		"""Speaks what changes first, and omits counters that are at zero.

		The order is deliberate: session, current puzzle, history, filters. The
		filters used to come first, and that's precisely the part that doesn't
		change during training.
		"""
		if self.puzzle is None:
			# Translators: Spoken when a puzzle action is used before a puzzle is on the board.
			ui.message(_("No puzzle loaded."))
			return
		history = self.session.attempt_stats()
		parts = [
			self._stats.summary(),
			self._current_puzzle_summary(),
			# Translators: Part of the session status: all puzzles ever tried.
			_("Database history: {solved} solved out of {total} attempts.").format(
				solved=history.solved,
				total=history.total,
			),
			# Translators: Part of the session status: the themes and levels in use; "none" when there are none.
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
		if self._attempt.is_review:
			self._write_review(solved)
			return
		try:
			self._last_rating = self.session.record_attempt(
				puzzle_id=self.puzzle.puzzle_id,
				solved=solved,
				mistakes=self._attempt.mistakes,
				hints_used=self._attempt.hints_used,
				elapsed_ms=self._attempt.elapsed_ms(),
				revealed=self._attempt.auto_solved,
			)
		except Exception:
			# Losing the rating for one attempt is annoying; losing the solved
			# puzzle because the database choked would be worse.
			log.exception("chessmart: failed to record the attempt")
			self._last_rating = None
		self._attempt.recorded = True

	def _write_review(self, solved: bool):
		"""A review goes to its own table, once, and never touches the rating."""
		assert self.puzzle is not None
		try:
			self._last_review = self.session.record_review(
				puzzle_id=self.puzzle.puzzle_id,
				solved=solved,
				mistakes=self._attempt.mistakes,
				hints_used=self._attempt.hints_used,
				revealed=self._attempt.auto_solved,
				elapsed_ms=self._attempt.elapsed_ms(),
			)
		except Exception:
			log.exception("chessmart: failed to record the review")
			self._last_review = None
		self._attempt.recorded = True
