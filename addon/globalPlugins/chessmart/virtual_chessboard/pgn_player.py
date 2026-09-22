# coding: utf-8
# pyright: basic

import queueHandler
import ui
import speech
import speech.commands
from scriptHandler import script
from ..addon_config import get_move_notation
from ..i18n import _
from ..notation import render_san
from ..sounds import GameSound
from ..speaking import speak_next
from .base import BaseVirtualChessboard, BaseChessboardCell


class PGNChessboardCell(BaseChessboardCell):
	parent: "PGNPlayerChessboard"

	@script(gesture="kb:backspace")
	def script_backspace(self, gesture):
		self.parent.rewind()


class PGNPlayerChessboard(BaseVirtualChessboard):
	cell_class = PGNChessboardCell
	can_draw = False
	can_resign = False

	def __init__(self, *args, **kwargs):
		game = kwargs.pop("game")
		super().__init__(*args, **kwargs)
		self.game = game
		self.board = self.game.get_board()
		self.current_move = -1
		# GUI Stuff
		info = self.game.info
		self._title = f"{info.white} versus {info.black} {info.date} {info.event} "
		self.dialog.SetTitle(self._title)

	def activate_cell(self, index):
		self.fast_forward()

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		post_speech = list(post_speech) + [
			speech.commands.BreakCommand(150),
			speech.commands.CallbackCommand(
				lambda: queueHandler.queueFunction(
					queueHandler.eventQueue,
					self.set_focus_to_cell,
					move.to_square,
				),
			),
		]
		super().move_piece_and_check_game_status(move, pre_speech, post_speech=post_speech)

	def fast_forward(self):
		next_move = self.current_move + 1
		if next_move < len(self.game.moves):
			self.move_piece_and_check_game_status(self.game.moves[next_move])
			self.current_move = next_move
		else:
			if self.game.info.termination is not None:
				# Translators: Spoken at the end of a replayed PGN game, with the Termination tag of the file.
				message = _("The game has been terminated because of: {reason}").format(
					reason=self.game.info.termination,
				)
			else:
				message = self.game.info.result
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, message)

	def rewind(self):
		"""Backspace: takes the last replayed move off the board and focuses its origin square."""
		if self.current_move < 0:
			GameSound.invalid.play()
			return
		undone = self.board.pop()
		self.current_move -= 1
		if self.score_sheet_menu.items:
			self.score_sheet_menu.items.pop(0)
		if self.is_game_over:
			# The last move of the game was taken back: the replay is open again.
			# Nothing listens to `game_over_signal` on this board, so resetting the
			# flag is enough; the title goes back to the game's.
			self.is_game_over = False
			self.dialog.SetTitle(self._title)
		self.dialog.set_board_image()
		# The board is back at the position before the move, so `san` is valid here.
		spoken = render_san(self.board.san(undone), undone.uci(), get_move_notation())
		speak_next(
			[
				# Translators: Spoken after Backspace took a move back in a PGN replay, e.g. "Took back Nf3".
				_("Took back {move}").format(move=spoken),
				speech.commands.BreakCommand(150),
				speech.commands.CallbackCommand(
					lambda: queueHandler.queueFunction(
						queueHandler.eventQueue,
						self.set_focus_to_cell,
						undone.from_square,
					),
				),
			],
		)
