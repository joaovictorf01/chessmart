# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The board editor: set up a position square by square, check it, use it.

The piece letters that jump to pieces on the other boards place pieces here,
as in FEN: Shift+letter (upper case) for White, the letter alone for Black.
What the position is and what is wrong with it is `position_editor.py`.

Keys, on any square (README, "Board Editor"):
K Q R B N P           a black king, queen, rook, bishop, knight, pawn on the square
Shift+K ... Shift+P   the same piece, white
Delete or Backspace   empty the square
Enter                 what is on the square
Control+C / Control+V copy the position as FEN / take a FEN from the clipboard
Tab                   the editor's actions: whose move, castling, check, standard
                      position, clear, analyse, flip
"""

import functools

import api
import eventHandler
import inputCore
import ui
from scriptHandler import script

from ..i18n import _
from ..paths import import_bundled
from ..position_editor import CASTLING_ROOKS, PositionDraft, spoken_piece
from ..sounds import GameSound
from ..speaking import speak_next
from ..spoken_messages import spoken_color_name
from .actions_bar import ActionsBarMixin
from .base import BaseChessboardCell, BaseVirtualChessboard


with import_bundled():
	import chess


def castling_name(rook_square):
	return {
		# Translators: A castling right in the board editor.
		chess.H1: _("white short castling"),
		# Translators: A castling right in the board editor.
		chess.A1: _("white long castling"),
		# Translators: A castling right in the board editor.
		chess.H8: _("black short castling"),
		# Translators: A castling right in the board editor.
		chess.A8: _("black long castling"),
	}[rook_square]


class EditorCell(BaseChessboardCell):
	parent: "PositionEditorChessboard"

	def _add_multiple_scripts(self):
		# Here the piece letters place pieces instead of jumping to them.
		gestures = {}
		place = getattr(self.__class__, "script_place_piece")
		for letter, piece_type in self.PIECE_LETTERS.items():
			gestures[f"kb:{letter}"] = functools.partialmethod(place, piece_type, chess.BLACK)
			gestures[f"kb:shift+{letter}"] = functools.partialmethod(place, piece_type, chess.WHITE)
		self._gestureMap.update({inputCore.normalizeGestureIdentifier(k): v for (k, v) in gestures.items()})

	def script_place_piece(self, piece_type, color, gesture):
		self.parent.place_piece(self.index, chess.Piece(piece_type, color))

	# Two keys for one script: bound through the class's gesture map.
	__gestures = {"kb:delete": "clear_square", "kb:backspace": "clear_square"}

	def script_clear_square(self, gesture):
		self.parent.clear_square(self.index)

	@script(gesture="kb:control+c")
	def script_copy_fen(self, gesture):
		self.parent.copy_fen()

	@script(gesture="kb:control+v")
	def script_paste_fen(self, gesture):
		self.parent.paste_fen()

	@script(gesture="kb:tab")
	def script_actions(self, gesture):
		self.parent.focus_action_bar()

	@script(gesture="kb:shift+tab")
	def script_actions_reverse(self, gesture):
		self.parent.focus_action_bar(reverse=True)


class PositionEditorChessboard(ActionsBarMixin, BaseVirtualChessboard):
	cell_class = EditorCell
	can_draw = False

	def __init__(self, *args, fen=None, on_analyse=None, flipped=False, **kwargs):
		# Before super(): the base constructor already asks which side is at the bottom.
		self._flipped = flipped
		self.draft = PositionDraft(fen)
		self.on_analyse = on_analyse
		kwargs["pychess_board"] = self.draft.board
		super().__init__(*args, **kwargs)
		items = [
			# Translators: Board editor action: says whose move it is and switches it.
			(_("Switch whose move it is"), self._from_actions(self.switch_turn)),
		]
		for rook_square in CASTLING_ROOKS:
			items.append(
				(
					# Translators: Board editor action, e.g. "Switch white short castling".
					_("Switch {castling}").format(castling=castling_name(rook_square)),
					self._from_actions(functools.partial(self.switch_castling, rook_square)),
				),
			)
		items += [
			# Translators: Board editor action: says what is wrong with the position, or that it is valid.
			(_("Check the position"), self._from_actions(self.check_position)),
			# Translators: Board editor action: opens the position on the analysis board.
			(_("Analyse this position"), self._from_actions(self.analyse)),
			# Translators: Board editor action, with its key.
			(_("Copy as FEN, Control+C"), self._from_actions(self.copy_fen)),
			# Translators: Board editor action, with its key.
			(_("Paste a FEN, Control+V"), self._from_actions(self.paste_fen)),
			# Translators: Board editor action: the starting position of a game.
			(_("Starting position"), self._from_actions(self.standard_position)),
			# Translators: Board editor action: removes every piece.
			(_("Clear the board"), self._from_actions(self.clear_board)),
			# Translators: Board editor action: turns the board around.
			(_("Flip the board"), self._from_actions(self.flip_board)),
			# Translators: Tab bar action that returns to the board.
			(_("Back to board"), self.focus_board_from_actions),
		]
		# Translators: Name of the Tab bar of the board editor.
		self.install_actions_bar(name=_("Editor actions"), items=items)

	# The material count and the overviews speak from White's side.
	@property
	def prospective(self):
		return chess.WHITE

	@prospective.setter
	def prospective(self, value):
		pass

	@property
	def is_board_flipped(self):
		return self._flipped

	@property
	def material_side(self):
		# M counts from the side at the bottom of the board, which does not change every move.
		return chess.BLACK if self._flipped else chess.WHITE

	def leave_prompt(self):
		if not self.draft.board.occupied:
			return None
		# Translators: Asked when Escape is pressed in the board editor with pieces on the board.
		return _("Leave the editor? The position will be lost. Control+C copies it first.")

	def activate_cell(self, cell):
		piece = self.board.piece_at(cell.index)
		square = self.spoken_square_name(cell.index)
		if piece is None:
			# Translators: Spoken by Enter on an empty square of the board editor, e.g. "e4 empty".
			ui.message(_("{square} empty").format(square=square))
		else:
			# Translators: A piece and its square in the board editor, e.g. "white king, e1".
			ui.message(_("{piece}, {square}").format(piece=spoken_piece(piece), square=square))

	# -- editing -------------------------------------------------------------------

	def place_piece(self, index, piece):
		self.draft.place(index, piece)
		self._sync()
		GameSound.drop_piece.play()
		# Translators: A piece and its square in the board editor, e.g. "white king, e1".
		ui.message(
			_("{piece}, {square}").format(piece=spoken_piece(piece), square=self.spoken_square_name(index)),
		)

	def clear_square(self, index):
		removed = self.draft.clear(index)
		if removed is None:
			GameSound.invalid.play()
			# Translators: Spoken when Delete is pressed on an empty square of the board editor.
			ui.message(_("Already empty"))
			return
		self._sync()
		# Translators: Spoken after a piece was removed in the board editor, e.g. "removed white knight".
		ui.message(_("removed {piece}").format(piece=spoken_piece(removed)))

	def switch_turn(self):
		self.draft.set_turn(not self.draft.board.turn)
		self._sync()
		# Translators: Spoken after switching whose move it is, e.g. "black to move".
		ui.message(_("{color} to move").format(color=spoken_color_name(self.draft.board.turn)))

	def switch_castling(self, rook_square):
		name = castling_name(rook_square)
		if not self.draft.castling_available(rook_square):
			GameSound.invalid.play()
			# Translators: Spoken when a castling right is asked for while king or rook is not on its square.
			ui.message(
				_("{castling}: not possible, the king or the rook is not on its starting square").format(
					castling=name,
				),
			)
			return
		on = self.draft.toggle_castling(rook_square)
		self._sync()
		# Translators: Spoken after switching a castling right, e.g. "white short castling: allowed".
		ui.message((_("{castling}: allowed") if on else _("{castling}: not allowed")).format(castling=name))

	def standard_position(self):
		self.draft.standard()
		self._sync()
		# Translators: Spoken after the board editor was set to the starting position.
		ui.message(_("Starting position"))

	def clear_board(self):
		self.draft.clear_all()
		self._sync()
		# Translators: Spoken after the board editor was cleared.
		ui.message(_("Board cleared"))

	def flip_board(self):
		self._flipped = not self._flipped
		self._sync()
		# Translators: Spoken after flipping the board, e.g. "black at the bottom".
		ui.message(_("{color} at the bottom").format(color=spoken_color_name(not self._flipped)))

	# -- checking and using ------------------------------------------------------------

	def check_position(self):
		problems = self.draft.problems()
		if problems:
			GameSound.invalid.play()
			spoken: list = list(problems)
			speak_next(spoken)
			return
		board = self.draft.board
		if board.is_checkmate():
			# Translators: Board editor check: a legal position that is already checkmate.
			ui.message(_("Valid position: checkmate."))
		elif board.is_stalemate():
			# Translators: Board editor check: a legal position that is already stalemate.
			ui.message(_("Valid position: stalemate."))
		else:
			# Translators: Board editor check, e.g. "Valid position, white to move.".
			ui.message(_("Valid position, {color} to move.").format(color=spoken_color_name(board.turn)))

	def analyse(self):
		if not self.draft.is_valid():
			GameSound.invalid.play()
			spoken: list = self.draft.problems()
			speak_next(spoken)
			return
		board = self.draft.board.copy(stack=False)
		callback = self.on_analyse
		self.leave_game()
		if callback is not None:
			callback(board)

	def copy_fen(self):
		fen = self.draft.fen()
		if api.copyToClip(fen):
			# Translators: Spoken after the position was copied as FEN.
			ui.message(_("FEN copied: {fen}").format(fen=fen))

	def paste_fen(self):
		text = (api.getClipData() or "").strip()
		try:
			self.draft.set_fen(text)
		except ValueError:
			GameSound.invalid.play()
			# Translators: Spoken when the clipboard does not hold a FEN.
			ui.message(_("The clipboard does not hold a FEN."))
			return
		self._sync()
		# Translators: Spoken after a FEN was pasted into the board editor.
		ui.message(
			_("Position pasted, {color} to move.").format(color=spoken_color_name(self.draft.board.turn)),
		)

	def _sync(self):
		self.board = self.draft.board
		if self.dialog:
			self.dialog.set_board_image()
		eventHandler.queueEvent("nameChange", self._chess_cells[self._focused_cell])
