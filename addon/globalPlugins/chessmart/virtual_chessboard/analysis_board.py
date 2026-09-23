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

from ..addon_config import get_games_folder, get_move_notation
from ..engine_eval import Advantage, Assessment, MoveVerdict
from ..game_tree import (
	MOVE_MARK_SYMBOLS,
	GameTree,
	PlayResult,
	RecordHeaders,
	record_filename,
	unique_path,
	write_pgn,
)
from ..i18n import _, ngettext
from ..notation import render_san
from ..openings import last_book_node, lookup, opening_of_line
from ..paths import import_bundled
from ..sounds import GameSound
from ..signals import chessboard_closed_signal
from ..speaking import speak_next
from ..spoken_messages import spoken_color_name
from .analysis_engine import DEEP_SECONDS, QUICK_SECONDS, AnalysisEngine, result_of
from .base import PlayedMove
from .actions_bar import ActionsBarMixin
from .ui_components import MenuItemObject, MenuObject
from .user_driven import UserDrivenCell, UserDrivenChessboard


with import_bundled():
	import chess
	import chess.pgn


# Control+1 to Control+6, in the order PGN numbers the marks.
MARK_KEYS = tuple(MOVE_MARK_SYMBOLS)
# How much of the engine's line goes into the game with Control+E, in half-moves:
# four for each side, enough to see the idea without burying the game in engine moves.
ENGINE_LINE_MOVES = 8
# How much of it is spoken by E, in half-moves.
SPOKEN_LINE_MOVES = 6


def spoken_mark(nag):
	"""The mark as words: a screen reader says "!?" badly, and the words are what the mark means."""
	return {
		# Translators: Spoken name of the "!" mark on a move.
		chess.pgn.NAG_GOOD_MOVE: _("good move"),
		# Translators: Spoken name of the "?" mark on a move.
		chess.pgn.NAG_MISTAKE: _("mistake"),
		# Translators: Spoken name of the "!!" mark on a move.
		chess.pgn.NAG_BRILLIANT_MOVE: _("brilliant move"),
		# Translators: Spoken name of the "??" mark on a move.
		chess.pgn.NAG_BLUNDER: _("blunder"),
		# Translators: Spoken name of the "!?" mark on a move.
		chess.pgn.NAG_SPECULATIVE_MOVE: _("interesting move"),
		# Translators: Spoken name of the "?!" mark on a move.
		chess.pgn.NAG_DUBIOUS_MOVE: _("dubious move"),
	}[nag]


def spoken_pawns(centipawns):
	"""+0.4 / -1.3 said with the decimal separator of the user's language."""
	tenths = round(abs(centipawns) / 10)
	whole, tenth = divmod(tenths, 10)
	# Translators: A number of pawns with one decimal, e.g. "0.4"; use your language's decimal separator.
	number = _("{whole}.{tenth}").format(whole=whole, tenth=tenth)
	if tenths == 0:
		return number
	if centipawns > 0:
		# Translators: An evaluation in favour of White, e.g. "plus 0.4".
		return _("plus {number}").format(number=number)
	# Translators: An evaluation in favour of Black, e.g. "minus 1.3".
	return _("minus {number}").format(number=number)


def spoken_assessment(assessment: Assessment) -> str:
	"""The evaluation in words: who is better and by how much."""
	if assessment.mate is not None:
		color = spoken_color_name(chess.WHITE if assessment.mate > 0 else chess.BLACK)
		moves = abs(assessment.mate)
		# Translators: Engine evaluation: a forced mate, e.g. "white mates in 3".
		return ngettext("{color} mates in {moves}", "{color} mates in {moves}", moves).format(
			color=color,
			moves=moves,
		)
	side = assessment.side_ahead
	pawns = spoken_pawns(assessment.centipawns)
	if side is None:
		# Translators: Engine evaluation of a level position, followed by the number, e.g. "equal, plus 0.1".
		return _("equal, {pawns}").format(pawns=pawns)
	color = spoken_color_name(side)
	return {
		# Translators: Engine evaluation, e.g. "white slightly better, plus 0.5".
		Advantage.SLIGHT: _("{color} slightly better, {pawns}"),
		# Translators: Engine evaluation, e.g. "black clearly better, minus 1.4".
		Advantage.CLEAR: _("{color} clearly better, {pawns}"),
		# Translators: Engine evaluation, e.g. "white winning, plus 4.2".
		Advantage.WINNING: _("{color} winning, {pawns}"),
	}[assessment.advantage].format(color=color, pawns=pawns)


def spoken_verdict(verdict: MoveVerdict) -> str:
	return {
		# Translators: Engine verdict on a move: the engine's own choice.
		MoveVerdict.BEST: _("the engine's move"),
		# Translators: Engine verdict on a move: not the best, but loses almost nothing.
		MoveVerdict.GOOD: _("good, almost nothing lost"),
		# Translators: Engine verdict on a move (?!).
		MoveVerdict.INACCURACY: _("inaccuracy"),
		# Translators: Engine verdict on a move (?).
		MoveVerdict.MISTAKE: _("mistake"),
		# Translators: Engine verdict on a move (??).
		MoveVerdict.BLUNDER: _("blunder"),
	}[verdict]


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

	@script(gesture="kb:tab")
	def script_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)


class AnalysisChessboard(ActionsBarMixin, UserDrivenChessboard):
	cell_class = AnalysisCell
	can_draw = False

	def __init__(self, *args, tree=None, source_path=None, flipped=False, **kwargs):
		# Before super(): the base constructor already asks which side is at the bottom.
		self._flipped = flipped
		self.tree = tree if tree is not None else GameTree()
		self.source_path = source_path
		self.unsaved = False
		kwargs["pychess_board"] = self.tree.board()
		super().__init__(*args, **kwargs)
		self.engine = AnalysisEngine()
		# The engine's last answer and the node it is about, so Control+E can reuse it.
		self._last_evaluation = None
		# E pressed twice: the first press already started the quick think; the
		# second is remembered and turns into the long one when the quick one ends.
		self._deep_pending = False
		chessboard_closed_signal.connect(lambda sender: self.engine.quit(), sender=self)
		self.install_actions_bar(
			# Translators: Name of the Tab bar on the analysis board.
			name=_("Analysis actions"),
			items=[
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Evaluate the position, E"), self._from_actions(self.evaluate_position)),
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
				# Translators: Tab bar action on the analysis board: turns the board around.
				(_("Flip the board"), self._from_actions(self.flip_board)),
				# Translators: Tab bar action on the analysis board, with its key.
				(_("Save, Control+S"), self._from_actions(self.save_game)),
				# Translators: Tab bar action that returns to the board.
				(_("Back to board"), self.focus_board_from_actions),
			],
		)
		self._rebuild_score_sheet()

	# -- the Tab bar ------------------------------------------------------------------

	def _from_actions(self, action):
		"""An action run from the Tab bar: back to the board first, so what it says is heard there."""

		def run():
			self.focus_board_from_actions()
			queueHandler.queueFunction(queueHandler.eventQueue, action)

		return run

	def open_mark_menu(self):
		if self.tree.at_start:
			self.focus_board_from_actions()
			GameSound.invalid.play()
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

	def flip_board(self):
		self._flipped = not self._flipped
		if self.dialog:
			self.dialog.set_board_image()
		# Translators: Spoken after flipping the analysis board, e.g. "black at the bottom".
		ui.message(_("{color} at the bottom").format(color=spoken_color_name(not self._flipped)))

	# -- the engine ---------------------------------------------------------------------

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
			spoken.append(_("variation"))
		spoken += self._current_move_text()
		spoken += self._book_note()
		spoken += self._position_state()
		speak_next(spoken)

	def go_to_start(self):
		self.tree.to_start()
		self._show_position()
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
				move=names[0], others=", ".join(names[1:])
			),
		)

	def take_back(self):
		node = self.tree.node
		if node.parent is None:
			GameSound.invalid.play()
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
			ui.message(_("Not in a variation"))
			return
		self.unsaved = True
		self._rebuild_score_sheet()
		# Translators: Spoken after Control+P made the current variation the main line.
		ui.message(_("This variation is now the main line"))

	# -- saving --------------------------------------------------------------------

	def save_game(self):
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
			self._set_opening_headers()
			try:
				path = self._save_path(record)
				write_pgn(self.tree, path)
			except OSError as error:
				log.warning("chessmart: could not save the analysed game: %s", error)
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					# Translators: Spoken when the game could not be written, followed by the error.
					_("Could not save the game. Details: {error}").format(error=error),
				)
			else:
				self.source_path = path
				self.unsaved = False
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
			if child.comment:
				text += " " + child.comment
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
		others = len(self.tree.alternatives()) - 1
		if others > 0:
			# Translators: Spoken when the position has variations recorded besides the main continuation.
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
			return [speech.commands.WaveFileCommand(GameSound.game_over.filename), _("checkmate")]
		if board.is_stalemate():
			return [speech.commands.WaveFileCommand(GameSound.game_over.filename), _("stalemate")]
		if board.is_check():
			return [
				speech.commands.WaveFileCommand(GameSound.check.filename),
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
