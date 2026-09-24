# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""F7 and Alt+Page Down / Page Up on the analysis board: review the whole game, walk its critical moments.

The engine evaluates every main-line position on a worker thread; the choice of
moments is `game_review.py`, under the options saved in the settings. A moment
opens on the position before the move, so the better move is looked for there;
by default the engine's move is not said (Settings, "What the engine reveals").
Suggested marks go only on moves the user left unmarked.
"""

import threading
import typing

import speech
import speech.commands
import tones
import ui
import wx

from ..addon_config import get_review_options, nvda_progress_bar_output
from ..analysis_words import (
	spoken_accuracy,
	spoken_assessment,
	spoken_mark,
	spoken_review_start,
	spoken_verdict,
)
from ..game_tree import MOVE_MARKS
from ..game_review import (
	PositionEval,
	Reveal,
	ReviewProgress,
	accuracy_by_color,
	critical_moments,
	mainline_nodes,
	review_moves,
	same_line,
	still_in_game,
)
from ..i18n import _, ngettext
from ..paths import import_bundled
from ..sounds import GameSound
from ..speaking import speak_next
from ..spoken_messages import spoken_color_name
from .analysis_engine import result_of


with import_bundled():
	import chess


class ReviewActionsMixin:
	engine: typing.Any
	tree: typing.Any
	unsaved: bool
	_flipped: bool
	_claim_engine: typing.Any
	_san_text: typing.Any
	_numbered_move: typing.Any
	_rebuild_score_sheet: typing.Any
	_show_position: typing.Any
	_engine_name: typing.Any
	_is_open: typing.Any
	dialog: typing.Any
	focus_board_from_actions: typing.Any

	_moments: tuple = ()
	_moment_index: int = -1
	_review_cancel: typing.Optional[threading.Event] = None
	_progress: typing.Optional[ReviewProgress] = None
	_beep_min_hz: int = 110

	def stop_review(self):
		"""Called when the board closes: the engine is about to quit, the review must not go on."""
		if self._review_cancel is not None:
			self._review_cancel.set()

	# -- running the review ---------------------------------------------------------

	def review_game(self):
		if self._review_cancel is not None:
			# F7 while the review runs: stop it.
			self._review_cancel.set()
			return
		nodes = mainline_nodes(self.tree.game)
		if len(nodes) < 2:
			GameSound.invalid.play()
			# Translators: Spoken by F7 when the game has no moves to review.
			ui.message(_("There are no moves to review."))
			return
		if not self._claim_engine():
			return
		options = get_review_options()
		# The user's side is the one at the bottom of the board (an imported game opens from their side).
		my_color = chess.BLACK if self._flipped else chess.WHITE
		self._review_cancel = threading.Event()
		# NVDA's own "Progress bar output" decides: beeps, speech, both or nothing.
		mode, beep_interval, self._beep_min_hz = nvda_progress_bar_output()
		self._progress = ReviewProgress(mode=mode, beep_interval=beep_interval)
		ui.message(spoken_review_start(len(nodes), len(nodes) * options.seconds))
		self.engine.evaluate_positions(
			[node.board() for node in nodes],
			options.seconds,
			self._review_progress,
			self._review_cancel,
		).add_done_callback(
			lambda future: wx.CallAfter(self._on_review_done, nodes, options, my_color, future),
		)

	def _review_progress(self, done, total):
		# Worker thread: speech goes through wx.CallAfter, and not after the board closed.
		if self._review_cancel is None or self._review_cancel.is_set():
			return
		if self._progress is None:
			return
		beep, percent = self._progress.update(done, total)
		if beep is not None:
			# The pitch of NVDA's progress bars: an octave for every quarter.
			wx.CallAfter(tones.beep, int(self._beep_min_hz * 2 ** (beep / 25.0)), 40)
		if percent is not None:
			# Translators: Game review progress, e.g. "50 percent reviewed".
			wx.CallAfter(ui.message, _("{percent} percent reviewed").format(percent=percent))

	def _on_review_done(self, nodes, options, my_color, future):
		cancel = self._review_cancel
		self._review_cancel = None
		evaluations, error = result_of(future)
		if not self._is_open():
			return
		if cancel is not None and cancel.is_set():
			# Translators: Spoken when F7 stopped the game review.
			ui.message(_("Review stopped."))
			return
		if error is not None:
			# Translators: Spoken when the engine failed during the review, followed by the error.
			ui.message(_("The engine could not answer. Details: {error}").format(error=error))
			return
		if evaluations is None:
			return
		game = self.tree.game
		if not same_line(game, nodes):
			# Translators: Spoken when moves were played, taken back or promoted while the review ran.
			ui.message(_("The game changed during the review. F7 reviews it again."))
			return
		position_evals = [
			None
			if evaluation is None
			else PositionEval(evaluation.assessment, evaluation.best_move, evaluation.line, evaluation.depth)
			for evaluation in evaluations
		]
		moments = critical_moments(review_moves(game, position_evals, options, my_color), options)
		self._moments = tuple(moments)
		self._moment_index = -1
		self._review_options = options
		marked = 0
		for moment in moments:
			mark = moment.review.suggested_mark
			if mark is not None and not (moment.node.nags & MOVE_MARKS):
				moment.node.nags.add(mark)
				marked += 1
		if marked:
			self.unsaved = True
			self._rebuild_score_sheet()
		accuracy = spoken_accuracy(accuracy_by_color(game, position_evals), my_color)
		speak_next(
			([accuracy, speech.commands.BreakCommand(200)] if accuracy else []) + self._summary(moments)
		)

	def _summary(self, moments) -> list:
		if not moments:
			# Translators: Spoken when the review found nothing at the chosen level.
			return [_("No critical moments at this level. Settings choose what counts.")]
		items = [
			"; ".join(
				# Translators: One critical moment in the review summary, e.g. "move 14, mistake".
				_("move {move}, {verdict}").format(
					move=moment.move_number, verdict=spoken_verdict(moment.review.verdict)
				)
				for moment in moments
			),
		]
		return [
			# Translators: Start of the review summary, e.g. "3 critical moments:".
			ngettext("{count} critical moment:", "{count} critical moments:", len(moments)).format(
				count=len(moments)
			),
			*items,
			speech.commands.BreakCommand(200),
			# Translators: End of the review summary.
			_("Alt+Page Down goes to the first."),
		]

	def open_review_options(self):
		"""The same options as in Settings, from the Tab bar; they apply to the next F7."""
		from ..graphical_interface.messages import run_modal
		from ..graphical_interface.review_dialog import ReviewOptionsDialog

		dialog = ReviewOptionsDialog(self.dialog)

		def done(result):
			if result == wx.ID_OK:
				dialog.save()
				# Translators: Spoken after the review options were saved from the analysis board.
				wx.CallAfter(ui.message, _("Review options saved. F7 reviews with them."))
			wx.CallAfter(self.focus_board_from_actions)

		run_modal(dialog, done)

	# -- walking the moments ------------------------------------------------------------

	def next_moment(self, step=1):
		if not self._moments:
			GameSound.invalid.play()
			# Translators: Spoken by Alt+Page Down before a review, or when it found nothing.
			ui.message(_("No critical moments. F7 reviews the game."))
			return
		index = self._moment_index + step
		if not 0 <= index < len(self._moments):
			GameSound.invalid.play()
			# Translators: Spoken past the last or before the first critical moment.
			ui.message(_("No more critical moments that way."))
			return
		moment = self._moments[index]
		if not still_in_game(moment):
			self._moments = ()
			GameSound.invalid.play()
			# Translators: Spoken by Alt+Page Down when the reviewed moves were changed since the review.
			ui.message(_("The game changed since the review. F7 reviews it again."))
			return
		self._moment_index = index
		self.tree.node = moment.node.parent
		self._show_position()
		board_before = moment.node.parent.board()
		played = self._san_text(board_before, moment.node.move)
		spoken: list = [
			# Translators: Heading of a critical moment, e.g. "Moment 2 of 3, move 14, black to move.".
			_("Moment {index} of {count}, move {move}, {color} to move.").format(
				index=index + 1,
				count=len(self._moments),
				move=moment.move_number,
				color=spoken_color_name(moment.mover),
			),
			# Translators: What was played at a critical moment, e.g. "Played Bxe5: mistake.".
			_("Played {move}: {verdict}.").format(move=played, verdict=spoken_verdict(moment.review.verdict)),
		]
		reveal = getattr(self, "_review_options", None)
		reveal = reveal.reveal if reveal is not None else Reveal.NOTHING
		best = moment.before.best_move
		if reveal is Reveal.NOTHING or best is None:
			# Translators: Said at a critical moment when the engine's move is kept hidden.
			spoken.append(_("Look for a better move: play it, and Shift+E judges it."))
		else:
			spoken.append(
				# Translators: The engine's move at a critical moment, e.g. "The engine preferred Nf3, equal, plus 0.1.".
				_("The engine preferred {move}, {evaluation}.").format(
					move=self._san_text(board_before, best),
					evaluation=spoken_assessment(moment.before.assessment),
				),
			)
			if reveal is Reveal.LINE and moment.before.line:
				first = self.tree.add_line(
					moment.before.line[:8],
					comment=self._engine_name(),
					score=moment.before.assessment.to_pov_score(),
					depth=moment.before.depth or None,
				)
				if first is not None:
					self.unsaved = True
					self._rebuild_score_sheet()
					# Translators: Said when the engine's line was added at a critical moment.
					spoken.append(_("Its line is a variation here: Alt+Down lists it."))
		mark = moment.review.suggested_mark
		if mark is not None and mark in moment.node.nags:
			# Translators: Said at a critical moment that carries the mark, e.g. "Marked: mistake.".
			spoken.append(_("Marked: {mark}.").format(mark=spoken_mark(mark)))
		speak_next(spoken)
