# coding: utf-8
# pyright: basic

import os
import subprocess
from typing import TYPE_CHECKING, Callable

import wx
import queueHandler
import eventHandler
import gui
from .i18n import _
from io import BytesIO
from logHandler import log
from .game_elements import GameInfo

if TYPE_CHECKING:
	from .virtual_chessboard.base import BaseVirtualChessboard
from .paths import BIN_DIRECTORY, import_bundled
from .sounds import GameSound
from .signals import chessboard_closed_signal, chessboard_signals
from .concurrency import LatestWins, call_threaded


with import_bundled():
	import chess
	import chess.svg

TIME_CHECK_INTERVAL = 1000
TIME_NOTIFICATION_MINUTES = 7
RSVG_CONVERT_EXECUTABLE = os.path.join(BIN_DIRECTORY, "rsvg_convert", "rsvg_convert.exe")
# Lichess's brown board: cream and brown squares, the last move in yellow-green,
# and the file letters and rank numbers on a dark margin, so someone watching
# the screen can follow along ("the knight on f3").
BOARD_COLOR_MAP = {
	"square light": "#f0d9b5",
	"square dark": "#b58863",
	"square light lastmove": "#cdd26a",
	"square dark lastmove": "#aaa23a",
	"margin": "#262421",
	"coord": "#e8e6e3",
}


class ChessboardDialog(wx.Frame):
	"""GUI of the chessboard."""

	def __init__(self, chessboard_class, **vboard_kwargs):
		super().__init__()
		# Translators: Title of the chessboard window.
		super().Create(title=_("Chess Board"), parent=gui.mainFrame, style=wx.NO_BORDER)
		self.chessboard_class = chessboard_class
		self.vboard_kwargs = vboard_kwargs
		# Translators: Accessible name of the chessboard window.
		self.SetName(_("Chessboard"))
		self.SetBackgroundColour(wx.WHITE)
		self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
		size = wx.Size(900, 900)
		self.width, self.height = size
		self.SetMinSize(size)
		self.SetSize(size)
		self.CenterOnScreen()
		self.bitmap_buffer = wx.Bitmap(*size)
		# Board pictures: one conversion at a time, and only the newest request
		# is drawn (see set_board_image).
		self._renders = LatestWins()
		self.Bind(wx.EVT_PAINT, self.onPaint, self)
		self.Bind(wx.EVT_CLOSE, self.onClose, self)
		# The virtual chessboard is created the first time the window receives focus (set_focus_to_board).
		self.chessboard: "BaseVirtualChessboard | None" = None
		# Whoever opened the window may want to know when it closes (the plugin,
		# to forget it). Receives this dialog.
		self.on_closed: "Callable[[ChessboardDialog], None] | None" = None
		# Time related stuff
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onChessTimer, id=self.timer.GetId())
		self.notification_records = {
			color: {i: False for i in range(1, TIME_NOTIFICATION_MINUTES + 1)} for color in chess.COLORS
		}

	@classmethod
	def from_game_info(cls, vboard_cls, game_info: GameInfo):
		vboard_kwargs = dict(
			pychess_board=game_info.pychess_board,
			variant=game_info.variant,
			prospective=game_info.prospective,
			time_control=game_info.time_control,
		)
		vboard_kwargs.update(game_info.vboard_kwargs)
		return cls(chessboard_class=vboard_cls, **vboard_kwargs)

	def set_focus_to_board(self):
		if self.chessboard is None:
			self.chessboard = self.chessboard_class(dialog=self, **self.vboard_kwargs)
			queueHandler.queueFunction(queueHandler.eventQueue, GameSound.start_game.play)
			self.timer.Start(TIME_CHECK_INTERVAL, wx.TIMER_CONTINUOUS)
			self.set_board_image()
		assert self.chessboard is not None
		eventHandler.executeEvent("gainFocus", self.chessboard)

	def get_board_svg(self, board=None, **chess_svg_kwargs):
		assert self.chessboard is not None, "the board is drawn only after it exists"
		if "flipped" not in chess_svg_kwargs:
			chess_svg_kwargs["flipped"] = self.chessboard.is_board_visually_flipped
		board = board or self.chessboard.board
		if "check" not in chess_svg_kwargs and board.is_check():
			# The king in check glows red, as on Lichess.
			chess_svg_kwargs["check"] = board.king(board.turn)
		return chess.svg.board(
			board,
			colors=BOARD_COLOR_MAP,
			**chess_svg_kwargs,
		).encode("utf-8")

	def onPaint(self, event):
		dc = wx.BufferedPaintDC(self)
		dc.SetBackground(wx.Brush("white"))
		dc.Clear()
		if self.chessboard is not None:
			dc.DrawBitmap(self.bitmap_buffer, 0, 0)

	def onClose(self, event):
		event.Skip()
		self.timer.Stop()
		if self.chessboard is not None:
			chessboard_closed_signal.send(self.chessboard)
			# The board connected lambdas and bound methods for itself; drop them
			# or the board, its cells and its engine wrapper outlive the window.
			chessboard_signals.disconnect_sender(self.chessboard)
		if self.on_closed is not None:
			self.on_closed(self)

	def onChessTimer(self, event):
		if self.chessboard is None:
			return
		time_control = self.chessboard.time_control
		if self.chessboard.is_game_over:
			time_control.stop()
			self.timer.Stop()
			return
		time_forfeit = time_control.is_time_forfeit()
		if any(time_forfeit.values()):
			losing_color = chess.WHITE if time_forfeit[chess.WHITE] else chess.BLACK
			self.chessboard.game_time_forfeit(losing_color)
			return
		current_player = self.chessboard.board.turn
		# Tenths of the total time still remaining (7 = 70%); the dictionary keys are integers.
		remaining = time_control.percentage_remaining(current_player) // 10
		if self.notification_records[current_player].get(remaining, True):
			return
		self.notification_records[current_player][remaining] = True
		if remaining >= 3:
			sound = GameSound.time_pass
		else:
			sound = GameSound.time_critical
		sound.play()

	def set_board_image(self, **chess_svg_kwargs):
		"""Redraws the picture of the board, for whoever is watching the screen.

		Called on every move and every focus change. The SVG is built here, from
		the board as it is now; turning it into pixels takes an rsvg_convert
		process, so at most one runs at a time and a burst of arrow presses
		collapses into the latest one instead of queueing a process per key.
		"""
		job = self._renders.request(self.get_board_svg(**chess_svg_kwargs))
		if job is not None:
			self._start_render(job)

	def _start_render(self, job):
		generation, board_svg_bytes = job
		self._get_png_from_svg(board_svg_bytes).add_done_callback(
			lambda future: self._on_rendered(generation, future),
		)

	def _on_rendered(self, generation, future):
		next_job = self._renders.finished()
		if next_job is not None:
			self._start_render(next_job)
		# A newer picture was asked for while this one was drawn: it will land next.
		if self._renders.is_current(generation):
			self.set_background_png(future)

	@call_threaded
	def _get_png_from_svg(self, board_svg_bytes):
		startupinfo = subprocess.STARTUPINFO()
		startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		return subprocess.run(
			[
				RSVG_CONVERT_EXECUTABLE,
				"-f",
				"png",
				"-w",
				str(self.width),
				"-h",
				str(self.height),
			],
			input=board_svg_bytes,
			capture_output=True,
			startupinfo=startupinfo,
		)

	def set_background_png(self, future):
		try:
			sp_result = future.result()
		except (OSError, RuntimeError) as error:
			log.error("chessStudy: could not run the board picture converter: %s", error)
			return
		if sp_result.returncode != 0:
			# Not an exception: the converter simply returned an error code.
			log.error("chessStudy: failed to convert the board SVG to PNG: %s", sp_result.stderr)
			return
		board_image = wx.Image(BytesIO(sp_result.stdout))
		wx.CallAfter(self._set_bitmap_data, board_image.GetData())

	def _set_bitmap_data(self, data):
		if not self:
			# The SVG conversion runs in a thread; the window may have closed in the meantime.
			return
		self.bitmap_buffer.CopyFromBuffer(data)
		self.Refresh(eraseBackground=False)
		self.Update()
