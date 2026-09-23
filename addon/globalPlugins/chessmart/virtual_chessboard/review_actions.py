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
import ui
import wx

from ..addon_config import get_review_options
from ..analysis_words import spoken_assessment, spoken_mark, spoken_verdict
from ..game_tree import MOVE_MARKS
from ..game_review import PositionEval, Reveal, critical_moments, mainline_nodes, review_moves
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

	_moments: tuple = ()
	_moment_index: int = -1
	_review_cancel: typing.Optional[threading.Event] = None
	_announced_percent: int = 0

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
		self._announced_percent = 0
		seconds_total = int(len(nodes) * options.seconds)
		ui.message(
			# Translators: Spoken when the game review starts, e.g. "Reviewing 70 positions, about 70 seconds. F7 again stops.".
			_("Reviewing {count} positions, about {seconds} seconds. F7 again stops.").format(
				count=len(nodes),
				seconds=seconds_total,
			),
		)
		game = self.tree.game
		self.engine.evaluate_positions(
			[node.board() for node in nodes],
			options.seconds,
			self._review_progress,
			self._review_cancel,
		).add_done_callback(
			lambda future: wx.CallAfter(self._on_review_done, game, options, my_color, future),
		)

	def _review_progress(self, done, total):
		# Worker thread: speech goes through wx.CallAfter.
		percent = done * 100 // total
		if percent // 25 > self._announced_percent // 25 and percent < 100:
			self._announced_percent = percent
			# Translators: Game review progress, e.g. "50 percent reviewed".
			wx.CallAfter(ui.message, _("{percent} percent reviewed").format(percent=percent - percent % 25))

	def _on_review_done(self, game, options, my_color, future):
		cancel = self._review_cancel
		self._review_cancel = None
		evaluations, error = result_of(future)
		if cancel is not None and cancel.is_set():
			# Translators: Spoken when F7 stopped the game review.
			ui.message(_("Review stopped."))
			return
		if error is not None:
			ui.message(_("The engine could not answer. Details: {error}").format(error=error))
			return
		if game is not self.tree.game or evaluations is None:
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
		speak_next(self._summary(moments))

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
		self._moment_index = index
		moment = self._moments[index]
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
				first = self.tree.add_line(moment.before.line[:8], comment=f"{self._engine_name()}")
				if first is not None:
					first.set_eval(moment.before.assessment.to_pov_score(), moment.before.depth or None)
					self.unsaved = True
					self._rebuild_score_sheet()
					# Translators: Said when the engine's line was added at a critical moment.
					spoken.append(_("Its line is a variation here: Alt+Down lists it."))
		mark = moment.review.suggested_mark
		if mark is not None and mark in moment.node.nags:
			# Translators: Said at a critical moment that carries the mark, e.g. "Marked: mistake.".
			spoken.append(_("Marked: {mark}.").format(mark=spoken_mark(mark)))
		speak_next(spoken)
