# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""E, Shift+E and Control+E on the analysis board: ask the engine and say the answer.

Combined with `AnalysisChessboard`: it uses the board's tree and its way of
writing moves (`_san_text`, `_numbered_move`). The engine process itself is
`analysis_engine.AnalysisEngine`; the words are in `analysis_words.py`.
"""

import typing

import speech
import speech.commands
import ui
import wx

from ..analysis_words import MARK_KEYS, spoken_assessment, spoken_mark, spoken_pawns, spoken_verdict
from ..i18n import _, ngettext
from ..openings import lookup
from ..sounds import GameSound
from ..speaking import speak_next
from .analysis_engine import DEEP_SECONDS, QUICK_SECONDS, result_of


# How much of the engine's line goes into the game with Control+E, in half-moves:
# four for each side, enough to see the idea without burying the game in engine moves.
ENGINE_LINE_MOVES = 8
# How much of it is spoken by E, in half-moves.
SPOKEN_LINE_MOVES = 6


class EngineActionsMixin:
	engine: typing.Any
	tree: typing.Any
	unsaved: bool
	_last_evaluation: typing.Any
	_deep_pending: bool
	_san_text: typing.Any
	_numbered_move: typing.Any
	_rebuild_score_sheet: typing.Any

	def _engine_name(self):
		return f"Stockfish {self.engine.version}"

	def _claim_engine(self):
		if self.engine.try_start():
			return True
		GameSound.invalid.play()
		# Translators: Spoken when an engine key is pressed while the engine is still thinking.
		ui.message(_("The engine is still thinking"))
		return False

	def evaluate_position(self, deep=False):
		board = self.tree.board()
		if board.is_game_over():
			# Translators: Spoken when E is pressed on a checkmate or stalemate.
			ui.message(_("There is nothing to evaluate: the game is over in this position."))
			return
		if deep and self.engine.busy:
			self._deep_pending = True
			# Translators: Spoken when the engine starts the long think (E pressed twice).
			ui.message(_("Thinking longer, {seconds} seconds").format(seconds=int(DEEP_SECONDS)))
			return
		if not self._claim_engine():
			return
		seconds = DEEP_SECONDS if deep else QUICK_SECONDS
		if deep:
			# Translators: Spoken when the engine starts the long think (E pressed twice).
			ui.message(_("Thinking longer, {seconds} seconds").format(seconds=int(seconds)))
		node = self.tree.node
		self.engine.evaluate(board, seconds).add_done_callback(
			lambda future: wx.CallAfter(self._on_evaluation, node, future),
		)

	def _on_evaluation(self, node, future):
		evaluations, error = result_of(future)
		if error is not None:
			self._say_engine_error(error)
			return
		if not evaluations:
			return
		best = evaluations[0]
		self._last_evaluation = (node, best)
		if node is not self.tree.node:
			# The user moved on while the engine thought: the answer is about another position.
			self._deep_pending = False
			return
		if self._deep_pending:
			self._deep_pending = False
			if self.engine.try_start():
				self.engine.evaluate(best.board, DEEP_SECONDS).add_done_callback(
					lambda future: wx.CallAfter(self._on_evaluation, node, future),
				)
				return
		spoken = [
			# Translators: Start of an engine evaluation, e.g. "Stockfish 16, depth 20:".
			_("{engine}, depth {depth}:").format(engine=self._engine_name(), depth=best.depth),
			spoken_assessment(best.assessment),
		]
		if best.best_move is not None:
			spoken.append(
				# Translators: The engine's best move, e.g. "best: Nf3".
				_("best: {move}").format(move=self._san_text(best.board, best.best_move)),
			)
			line = self._spoken_line(best.board, best.line[1:SPOKEN_LINE_MOVES], after=best.best_move)
			if line:
				# Translators: The rest of the engine's line after its best move.
				spoken.append(_("then {line}").format(line=line))
		others = [
			# Translators: One of the engine's other candidate moves, e.g. "e4, plus 0.3".
			_("{move}, {pawns}").format(
				move=self._san_text(other.board, other.best_move),
				pawns=self._short_value(other.assessment),
			)
			for other in evaluations[1:]
			if other.best_move is not None
		]
		if others:
			# Translators: The engine's other candidate moves, after the best one.
			spoken.append(_("Also: {moves}").format(moves="; ".join(others)))
		sequence: list = [speech.commands.BreakCommand(100), *spoken]
		speak_next(sequence)

	def review_move(self):
		node = self.tree.node
		if node.parent is None:
			GameSound.invalid.play()
			# Translators: Spoken when Shift+E is pressed before any move.
			ui.message(_("Play or go to a move first; the engine reviews the move that led here."))
			return
		opening = lookup(node.board())
		if opening is not None:
			ui.message(
				# Translators: Shift+E on a move that is still opening theory, e.g. "Nf3: theory, Sicilian Defense, B50.".
				_("{move}: theory, {name}, {eco}.").format(
					move=self._san_text(node.parent.board(), node.move),
					name=opening.name,
					eco=opening.eco,
				),
			)
			return
		if not self._claim_engine():
			return
		# Translators: Spoken while the engine reviews the move, e.g. "Reviewing 12. Nf3".
		ui.message(_("Reviewing {move}").format(move=self._numbered_move()))
		self.engine.review_move(node.parent.board(), node.move).add_done_callback(
			lambda future: wx.CallAfter(self._on_review, node, future),
		)

	def _on_review(self, node, future):
		result, error = result_of(future)
		if error is not None:
			self._say_engine_error(error)
			return
		assert result is not None, "no error means a result"
		review, before = result
		self._last_evaluation = (node.parent, before)
		board_before = before.board
		played = self._san_text(board_before, review.played_move)
		spoken = [
			# Translators: Engine review of a move, e.g. "Nf3: inaccuracy.".
			_("{move}: {verdict}.").format(move=played, verdict=spoken_verdict(review.verdict)),
		]
		if not review.is_best:
			spoken.append(
				# Translators: What the engine preferred, e.g. "The engine preferred e4, white slightly better, plus 0.5.".
				_("The engine preferred {move}, {evaluation}.").format(
					move=self._san_text(board_before, review.best_move),
					evaluation=spoken_assessment(review.best),
				),
			)
			spoken.append(
				# Translators: The evaluation after the move actually played, e.g. "After Nf3: equal, plus 0.1.".
				_("After {move}: {evaluation}.").format(
					move=played, evaluation=spoken_assessment(review.played)
				),
			)
		mark = review.suggested_mark
		if mark is not None:
			spoken.append(
				# Translators: The mark the engine's verdict suggests, e.g. "Suggested mark: dubious move, Control+6.".
				_("Suggested mark: {mark}, Control+{key}.").format(
					mark=spoken_mark(mark),
					key=MARK_KEYS.index(mark) + 1,
				),
			)
		speak_next(spoken)

	def add_engine_line(self):
		node = self.tree.node
		last = self._last_evaluation
		if last is None or last[0] is not node:
			GameSound.invalid.play()
			# Translators: Spoken when Control+E is pressed before evaluating this position.
			ui.message(_("Evaluate this position first with E; then Control+E adds the engine's line."))
			return
		evaluation = last[1]
		if not evaluation.line:
			# Translators: Spoken when the engine returned no moves for the position.
			ui.message(_("The engine has no line for this position."))
			return
		line = evaluation.line[:ENGINE_LINE_MOVES]
		first = self.tree.add_line(
			line,
			comment=f"{self._engine_name()}: {self._short_value(evaluation.assessment, written=True)}",
		)
		assert first is not None
		self.unsaved = True
		self._rebuild_score_sheet()
		ui.message(
			# Translators: Spoken after Control+E, e.g. "Engine line added from Nf3, 8 moves. Alt+Down lists it.".
			ngettext(
				"Engine line added from {move}, {count} move. Alt+Down lists it.",
				"Engine line added from {move}, {count} moves. Alt+Down lists it.",
				len(line),
			).format(move=self._san_text(evaluation.board, first.move), count=len(line)),
		)

	def _short_value(self, assessment, written=False):
		"""+0.4 or #3 in the PGN comment; "plus 0.4" or "mate in 3" when spoken."""
		if assessment.mate is not None:
			if written:
				return f"#{assessment.mate}"
			# Translators: Short engine value for a forced mate, e.g. "mate in 3".
			return _("mate in {moves}").format(moves=abs(assessment.mate))
		if written:
			return f"{assessment.pawns:+.1f}"
		return spoken_pawns(assessment.centipawns)

	def _say_engine_error(self, error):
		ui.message(
			# Translators: Spoken when the engine failed, followed by the error.
			_("The engine could not answer. Details: {error}").format(error=error),
		)

	def _spoken_line(self, board, moves, after=None):
		board = board.copy(stack=False)
		if after is not None:
			board.push(after)
		words = []
		for move in moves:
			words.append(self._san_text(board, move))
			board.push(move)
		return ", ".join(words)
