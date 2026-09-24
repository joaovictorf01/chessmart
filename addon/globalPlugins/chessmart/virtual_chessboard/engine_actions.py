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
from logHandler import log

from ..analysis_words import MARK_KEYS, spoken_assessment, spoken_mark, spoken_pawns, spoken_verdict
from ..endgame import judge, tablebase
from ..engine_eval import threat_position
from ..i18n import _, ngettext
from ..openings import lookup
from ..paths import import_bundled
from ..sounds import GameSound
from ..speaking import speak_next
from ..spoken_messages import spoken_color_name
from .analysis_engine import DEEP_SECONDS, QUICK_SECONDS, result_of


with import_bundled():
	import chess


# How much of the engine's line goes into the game with Control+E, in half-moves:
# four for each side, enough to see the idea without burying the game in engine moves.
ENGINE_LINE_MOVES = 8
# How much of it is spoken by E, in half-moves.
# Moves of the engine's line said after its first move: three can be held by ear; the
# whole line goes into the game with Control+E.
SPOKEN_LINE_MOVES = 3


class EngineActionsMixin:
	engine: typing.Any
	tree: typing.Any
	unsaved: bool
	_last_evaluation: typing.Any
	_deep_pending: bool = False
	# An E is thinking (not X, Shift+E or F7): only then does a second E wait for it.
	_evaluating: bool = False
	_is_open: typing.Any
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
		if self._say_tablebase(board):
			return
		if deep and self._evaluating:
			# E pressed twice: the first press is thinking; the second turns into the long think after it.
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
		self._evaluating = True
		self.engine.evaluate(board, seconds).add_done_callback(
			lambda future: wx.CallAfter(self._on_evaluation, node, future),
		)

	def _on_evaluation(self, node, future):
		self._evaluating = False
		deep_pending, self._deep_pending = self._deep_pending, False
		evaluations, error = result_of(future)
		if not self._is_open():
			return
		if error is not None:
			self._say_engine_error(error)
			return
		if not evaluations:
			return
		best = evaluations[0]
		self._last_evaluation = (node, best)
		if node is not self.tree.node:
			# The user moved on while the engine thought: the answer is about another position.
			return
		if deep_pending:
			if self.engine.try_start():
				self._evaluating = True
				self.engine.evaluate(best.board, DEEP_SECONDS).add_done_callback(
					lambda future: wx.CallAfter(self._on_evaluation, node, future),
				)
				return
		# What matters first: who is better. Then the move, a short line, the
		# other candidates; each a sentence of its own, so the pauses fall between them.
		# The engine's name and depth are not said: Control+E writes them in the game.
		spoken = [
			# Translators: The engine's evaluation as a sentence, e.g. "white slightly better, plus 0.4.".
			_("{evaluation}.").format(evaluation=spoken_assessment(best.assessment)),
		]
		if best.best_move is not None:
			spoken.append(
				# Translators: The engine's best move, e.g. "Best move: Nf3.".
				_("Best move: {move}.").format(move=self._san_text(best.board, best.best_move)),
			)
			line = self._spoken_line(best.board, best.line[1 : 1 + SPOKEN_LINE_MOVES], after=best.best_move)
			if line:
				# Translators: The engine's line after its best move, e.g. "Line: e5, Bc4, Nc6.".
				spoken.append(_("Line: {line}.").format(line=line))
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
			# Translators: The engine's other candidate moves, e.g. "Others: e4, plus 0.3; d4, plus 0.2.".
			spoken.append(_("Others: {moves}.").format(moves="; ".join(others)))
		sequence: list = [speech.commands.BreakCommand(100)]
		for sentence in spoken:
			sequence.extend([sentence, speech.commands.BreakCommand(150)])
		speak_next(sequence)

	# -- the tablebase: exact answers with few pieces ------------------------------------

	_tablebase: typing.Any = None
	_tablebase_opened: bool = False

	def _open_tablebase(self):
		"""The Syzygy tables the endgames downloaded, opened once per board; None without them."""
		if not self._tablebase_opened:
			self._tablebase_opened = True
			try:
				self._tablebase = tablebase.open_tablebase()
			except (
				Exception
			) as error:  # a damaged table must not stop the analysis: the engine answers instead
				log.warning("chessmart: could not open the tablebases for analysis: %s", error)
				self._tablebase = None
		return self._tablebase

	def close_tablebase(self):
		if self._tablebase is not None:
			self._tablebase.close()
			self._tablebase = None

	def _say_tablebase(self, board) -> bool:
		"""With few enough pieces and the tables installed, the exact result replaces the engine."""
		if chess.popcount(board.occupied) > judge.MAX_PIECES:
			return False
		tables = self._open_tablebase()
		verdict = judge.probe(tables, board)
		if verdict is None:
			return False
		spoken: list = [
			# Translators: Start of a tablebase answer on the analysis board.
			_("Tablebase:"),
			judge.describe_verdict(verdict, spoken_color_name(board.turn)),
		]
		best = judge.best_moves(tables, board)
		if best:
			# Translators: The moves that keep the tablebase result, e.g. "Best: Kd6, Qe7.".
			spoken.append(
				_("Best: {moves}.").format(moves=", ".join(self._san_text(board, move) for move in best[:4])),
			)
		speak_next(spoken)
		return True

	def show_threat(self):
		"""X, as on Lichess: what the other side would play if it were its move."""
		board = self.tree.board()
		passed = threat_position(board)
		if passed is None:
			GameSound.invalid.play()
			if board.is_check():
				# Translators: Spoken by X when the side to move is in check.
				ui.message(_("In check: the threat is already on the board."))
			else:
				ui.message(_("There is nothing to evaluate: the game is over in this position."))
			return
		if not self._claim_engine():
			return
		node = self.tree.node
		self.engine.evaluate(passed, QUICK_SECONDS).add_done_callback(
			lambda future: wx.CallAfter(self._on_threat, node, future),
		)

	def _on_threat(self, node, future):
		evaluations, error = result_of(future)
		if not self._is_open():
			return
		if error is not None:
			self._say_engine_error(error)
			return
		if node is not self.tree.node or not evaluations:
			return
		threat = evaluations[0]
		if threat.best_move is None:
			# Translators: Spoken by X when the engine finds no move for the other side.
			ui.message(_("No threat found."))
			return
		spoken: list = [
			# Translators: The threat found by X, e.g. "Threat: Qxf7, white mates in 1.".
			_("Threat: {move}, {evaluation}.").format(
				move=self._san_text(threat.board, threat.best_move),
				evaluation=spoken_assessment(threat.assessment),
			),
		]
		line = self._spoken_line(threat.board, threat.line[1 : 1 + SPOKEN_LINE_MOVES], after=threat.best_move)
		if line:
			spoken.append(_("Line: {line}.").format(line=line))
		speak_next(spoken)

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
		if not self._is_open():
			return
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
			# Also as [%eval ...], the annotation Lichess and ChessBase read and chart.
			score=evaluation.assessment.to_pov_score(),
			depth=evaluation.depth,
		)
		if first is None:
			# Translators: Spoken by Control+E when every move of the engine's line is already recorded.
			ui.message(_("The engine's line is already recorded here."))
			return
		self.unsaved = True
		self._rebuild_score_sheet()
		followed = first.ply() - self.tree.node.ply() - 1
		added = len(line) - followed
		if followed == 0:
			ui.message(
				# Translators: Spoken after Control+E, e.g. "Engine line added from 12. Nf3, 8 moves. Alt+Down lists it.".
				ngettext(
					"Engine line added from {move}, {count} move. Alt+Down lists it.",
					"Engine line added from {move}, {count} moves. Alt+Down lists it.",
					added,
				).format(move=self._numbered_move(first), count=added),
			)
			return
		ui.message(
			# Translators: Spoken after Control+E when the engine agrees with recorded moves first, e.g. "The engine follows 2 recorded moves, then branches at 13. Bb5: 6 moves added.".
			ngettext(
				"The engine follows {followed} recorded move, then branches at {move}: {count} moves added.",
				"The engine follows {followed} recorded moves, then branches at {move}: {count} moves added.",
				followed,
			).format(followed=followed, move=self._numbered_move(first), count=added),
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
