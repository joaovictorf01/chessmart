# coding: utf-8

import functools
import wx
import tones
import gui
import ui
import queueHandler
import eventHandler
import speech.commands
from scriptHandler import script
from logHandler import log
from ..helpers import import_bundled, speak_next, GameSound
from ..i18n import _
from .ui_components import SimpleList
from .user_driven import UserDrivenChessboard, UserDrivenCell


with import_bundled():
	import chess


class InternetChessboardCell(UserDrivenCell):
	@script(gesture="kb:control+shift+r")
	def script_resign_game(self, gesture):
		"""Resigns the game."""
		# Translators: Spoken while the resignation is sent to the online server.
		ui.message(_("Resigning..."))
		self.parent.client.resign_game().add_done_callback(lambda f: GameSound.resigned.play())

	@script(gesture="kb:control+shift+d")
	def script_offer_draw(self, gesture):
		self.parent.client.offer_draw().add_done_callback(self._on_draw_callback)

	@script(gesture="kb:c")
	def script_send_chat_message(self, gesture):
		dialog = wx.TextEntryDialog(
			gui.mainFrame,
			_("Enter chat message"),
			_("Chat"),
		)
		gui.runScriptModalDialog(dialog, callback=functools.partial(self._on_chat_before_send, dialog))

	@script(gesture="kb:f5")
	def script_show_chat_list(self, gesture):
		if self.parent.chat_list:
			eventHandler.queueEvent("gainFocus", self.parent.chat_list)
		else:
			ui.message(_("No chat messages"))

	def _on_chat_before_send(self, dialog, retval):
		if retval == wx.ID_OK:
			tones.beep(400, 400)
		message = dialog.GetValue().strip()
		if message:
			self.parent.client.send_chat_message(message).add_done_callback(
				functools.partial(self.on_chat_message_sent, message),
			)

	def _on_draw_callback(self, future):
		log.info(future.result())
		tones.beep(2000, 200)

	def on_chat_message_sent(self, message, future):
		try:
			response = future.result()
			if response.entity.content["ok"]:
				# Translators: Chat line for a message the player sent, e.g. "You said good game".
				self.parent.chat_list.add_item(_("You said {message}").format(message=message))
		except Exception:
			log.exception("Failed to send chat message.")
			queueHandler.queueFunction(
				# Translators: Spoken when an online chat message could not be sent.
				queueHandler.eventQueue,
				ui.message,
				_("Failed to send chat message"),
			)


class InternetChessboard(UserDrivenChessboard):
	"""A board for playing internet chess."""

	cell_class = InternetChessboardCell

	def __init__(self, *args, client, **kwargs):
		super().__init__(*args, **kwargs)
		self.client = client(board=self)
		self.prospective = self.prospective if self.prospective is not None else True
		self._is_game_started = False
		# Translators: Name of the online chat list.
		self.chat_list = SimpleList(parent=self, name=_("Chat"), close_gesture="kb:f5")
		# Translators: Window title while an online game is being set up.
		self.dialog.SetTitle(_("Starting Game..."))

	def is_busy(self, index):
		if not self._is_game_started:
			return True
		return super().is_busy(index)

	# -- sair -----------------------------------------------------------------

	def _can_abort(self):
		# Regra do Lichess: até o segundo lance a partida pode ser abortada
		# sem contar; depois disso, sair é desistir.
		return len(self.board.move_stack) < 2

	def leave_prompt(self):
		if not self._is_game_started:
			# Translators: Asked when Escape is pressed while an online game is still being set up.
			return _("Leave? The online game has not started yet and will be dropped.")
		if self._can_abort():
			# Translators: Asked when Escape is pressed in the first moves of an online game.
			return _("Leave the online game? It will be aborted.")
		# Translators: Asked when Escape is pressed during an online game.
		return _("Leave the online game? You will resign it.")

	def leave_game(self):
		"""Avisa o Lichess antes de fechar: abort nos primeiros lances, resign depois.

		Fechar sem avisar deixava a partida correndo no servidor com o relógio
		andando, e a derrota vinha por tempo, sem janela para ver.
		"""
		if not self._is_game_started:
			self._disconnect_quietly()
			super().leave_game()
			return
		# Translators: Spoken while the resignation or abort is sent to the online server.
		ui.message(_("Leaving the game..."))
		request = self.client.abort_game() if self._can_abort() else self.client.resign_game()
		request.add_done_callback(lambda future: wx.CallAfter(self._leave_after_request, future))

	def _leave_after_request(self, future):
		try:
			future.result()
		except Exception:
			log.exception("chessmart: could not resign or abort the online game before leaving")
		self._disconnect_quietly()
		super().leave_game()

	def _disconnect_quietly(self):
		try:
			self.client.disconnect()
		except Exception:
			log.exception("chessmart: failed to disconnect the online client")

	def user_play(self, from_index, to_index):
		self.client.send_move(chess.Move(from_index, to_index)).add_done_callback(
			lambda future: self._execute_user_move(from_index, to_index, future),
		)

	def _execute_user_move(self, from_index, to_index, future):
		try:
			future.result()
			super(InternetChessboard, self).user_play(from_index, to_index)
		except Exception:
			speak_next(
				speech.commands.WaveFileCommand(GameSound.error.filename),
				speech.commands.BreakCommand(100),
				_("Failed to send move"),
			)

	def restore_move_history(self, past_moves):
		for uci_move in past_moves:
			move = chess.Move.from_uci(uci_move)
			self.move_piece_and_check_game_status(move)

	def execute(self, event):
		func_name = f"on_{event.__member_name__}"
		callback = getattr(self, func_name, None)
		if callback is not None:
			wx.CallAfter(callback, event)

	def on_game_started(self, event):
		self._is_game_started = True
		info = event.info
		self.prospective = info.user_color
		self.dialog.SetTitle(
			_("{white} ({white_rating}) versus {black} ({black_rating})").format(
				white=info.white_username,
				black=info.black_username,
				white_rating=info.white_rating,
				black_rating=info.black_rating,
			),
		)
		self.dialog.set_time_control(info.time_control, True)

	def on_game_checkmate(self, event):
		print(f"Checkmate: winner is {event.winner}")

	def on_game_draw(self):
		self.game_drawn()

	def on_game_time_forfeit(self, event):
		self.game_time_forfeit(event.loser)

	def on_game_resign(self, event):
		self.game_resigned(event)

	def on_game_abort(self, event):
		color_name = self.game_announcer.color_name(event.loser)
		# Translators: Shown when the online opponent aborted the game, e.g. "black aborted the game".
		self.game_error(_("{color} aborted the game").format(color=color_name))
		GameSound.error.play()

	def on_game_error(self, event):
		self.game_error()
		GameSound.error.play()

	def on_move_made(self, event):
		if event.player != self.prospective:
			self.move_piece_and_check_game_status(event.move)

	def on_draw_offered(self, event):
		self.handle_draw_offer()

	def respond_to_draw_offer(self, accepted: bool):
		self.client.handle_draw_offer(accepted)

	def on_chat_message_recieved(self, event):
		full_message = f"{event.from_whom} says {event.message}"
		self.chat_list.add_item(full_message)
		GameSound.chat.play()
		queueHandler.queueFunction(queueHandler.eventQueue, ui.message, full_message)

	def on_clock_tick(self, event):
		self.time_control = event.time_control
