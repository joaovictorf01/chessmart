# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Control+S and Control+Shift+S: the game as PGN, the board as a picture. Combined with a board class."""

import typing

import ui
import wx
from logHandler import log

from ..i18n import _
from ..paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


class BoardFilesMixin:
	board: typing.Any
	dialog: typing.Any

	def _ask_path(self, dialog, write):
		"""Shows the save dialog through run_modal (a script must not block on ShowModal) and writes on OK."""
		from ..graphical_interface.messages import run_modal

		def done(result):
			path = dialog.GetPath().strip() if result == wx.ID_OK else ""
			if not path:
				return
			try:
				write(path)
			except OSError as error:
				log.warning("chessmart: could not save %s: %s", path, error)
				# Translators: Spoken when a game or picture could not be written, followed by the error.
				wx.CallAfter(ui.message, _("Could not save. Details: {error}").format(error=error))

		run_modal(dialog, done)

	def save_game(self):
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the game as a PGN file.
			message=_("Save Game As"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the PGN save dialog.
			wildcard=_("Chess Game *.pgn | *.pgn"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		# The position as it is now, not when the dialog closes.
		game = chess.pgn.Game.from_board(self.board)

		def write(path):
			with open(path, "w", encoding="utf-8") as file:
				game.accept(chess.pgn.FileExporter(file))

		self._ask_path(saveFileDialog, write)

	def save_board_image(self):
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the board as an image.
			message=_("Save Board To Image"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the image save dialog.
			wildcard=_("Portable Network Graphics *.png | *.png"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)

		def write(path):
			if not self.dialog.bitmap_buffer.SaveFile(path, wx.BITMAP_TYPE_PNG):
				raise OSError(path)

		self._ask_path(saveFileDialog, write)
