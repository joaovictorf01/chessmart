# coding: utf-8
# pyright: basic

import os
import threading
import subprocess
import wx
import queueHandler
from logHandler import log
from ..paths import BIN_DIRECTORY, import_bundled
from ..i18n import _
from ..signals import move_completed_signal, game_started_signal, game_over_signal
from ..concurrency import call_threaded
from ..engine_eval import engine_accepts_draw
from ..speaking import speak_next
from .user_driven import UserDrivenChessboard


STOCKFISH_VERSION = "16"
# The official Stockfish 16 build for any 64-bit x86 processor; see bin/stockfish_16/info.txt.
STOCKFISH_EXECUTABLE_PATH = os.path.join(BIN_DIRECTORY, "stockfish_16", "stockfish_16_x86-64.exe")
FAIRY_STOCKFISH_EXECUTABLE_PATH = os.path.join(
	BIN_DIRECTORY,
	"fairy_stockfish",
	"fairy-stockfish-largeboard_x86-64.exe",
)


with import_bundled():
	import chess
	import chess.engine


class UserEngineChessboard(UserDrivenChessboard):
	def __init__(self, *args, uci_options, uci_time_limit, **kwargs):
		super().__init__(*args, **kwargs)
		self.uci_options = uci_options or {}
		self.uci_time_limit = uci_time_limit or 2.0
		self.prospective = self.prospective if self.prospective is not None else True
		self.uci_engine = self.get_uci_engine(self._get_uci_engine_path())
		# Events
		move_completed_signal.connect(self.on_move_completed, sender=self)
		game_started_signal.connect(self.on_game_started, sender=self)
		game_over_signal.connect(self.on_game_over, sender=self)
		game_started_signal.send(self)

	def _get_uci_engine_path(self):
		if self.board.uci_variant == "chess":
			return STOCKFISH_EXECUTABLE_PATH
		else:
			return FAIRY_STOCKFISH_EXECUTABLE_PATH

	def get_uci_engine(self, executable):
		startupinfo = subprocess.STARTUPINFO()
		startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		uci_engine = chess.engine.SimpleEngine.popen_uci(
			executable,
			creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
			startupinfo=startupinfo,
			close_fds=True,
		)
		uci_engine.configure(self.uci_options)
		return uci_engine

	def on_game_over(self, sender, board_outcome):
		try:
			self.uci_engine.quit()
		except chess.engine.EngineError:
			# Already gone (an engine error ended the game): nothing to shut down.
			log.debug("chessStudy: engine already gone at game over")

	def leave_prompt(self):
		if not self.board.move_stack:
			return None
		# Translators: Asked when Escape is pressed during a game against the engine.
		return _("Leave the game? The game against the engine will be abandoned.")

	def on_move_completed(self, sender, move, move_maker):
		if self.is_game_over:
			return
		if self.board.turn is not self.prospective:
			self.get_next_move_from_engine().add_done_callback(
				lambda future: wx.CallAfter(self.engine_play, future),
			)

	def engine_play(self, future):
		# Always reached through `wx.CallAfter` from the engine future's callback,
		# so this already runs on the main thread: no further deferral needed.
		if self.is_game_over:
			# The game ended while the engine was thinking (time, or the window
			# closed and the engine was shut down): its answer no longer counts.
			return
		try:
			play_result = future.result()
		except chess.engine.EngineError:
			self.game_error()
			return
		if play_result.resigned:
			# The engine plays the side the user does not.
			self.game_resigned(not self.prospective)
			return
		if self.draw_offered:
			# The player's offer (Control+D) is answered on the engine's turn,
			# with the score from the search that just chose its move.
			self.draw_offered = False
			if self.answer_draw_offer(play_result.info.get("score")):
				return
		self.move_piece_and_check_game_status(play_result.move)

	def answer_draw_offer(self, score):
		"""Speaks the engine's answer to the player's draw offer; True when it ends the game."""
		accepted = engine_accepts_draw(score, not self.prospective, self.board.fullmove_number)
		log.debug("chessStudy: engine answers draw offer, score %s, accepted %s", score, accepted)
		if accepted:
			# Translators: Spoken when the player offered a draw in a game against the computer and it agrees; the game then ends as a draw.
			speak_next([_("The computer accepts the draw.")])
			self.game_drawn()
			return True
		# Translators: Spoken when the player offered a draw in a game against the computer and it refuses; the computer's move follows.
		speak_next([_("The computer declines the draw.")])
		return False

	@call_threaded
	def get_next_move_from_engine(self):
		white_clock, black_clock = [self.time_control.chess_clocks[color] for color in chess.COLORS]
		limit = chess.engine.Limit(
			time=self.uci_time_limit,
			white_clock=white_clock.remaining,
			black_clock=black_clock.remaining,
			white_inc=white_clock.increment,
			black_inc=black_clock.increment,
		)
		# The score comes along with the move, so a pending draw offer is
		# answered without a second search.
		return self.uci_engine.play(
			self.board,
			limit,
			info=chess.engine.INFO_SCORE,
		)

	def make_first_move(self):
		if self.prospective is not chess.BLACK:
			return

		def first_move_task():
			self.get_next_move_from_engine().add_done_callback(
				lambda future: wx.CallAfter(self.engine_play, future),
			)

		t = threading.Timer(interval=2, function=first_move_task)
		t.daemon = True
		t.start()

	def on_game_started(self, sender):
		queueHandler.queueFunction(queueHandler.eventQueue, self.make_first_move)
