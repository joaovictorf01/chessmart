# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Control+S and Control+Shift+S: the game as PGN, the board as a picture. Combined with a board class."""

import typing

import wx

from ..i18n import _
from ..paths import import_bundled


with import_bundled():
	import chess
	import chess.pgn


class BoardFilesMixin:
	board: typing.Any
	dialog: typing.Any

	def save_game(self):
		# wx dialogs must be created and shown on the GUI thread (NVDA developer
		# guide); this runs from a script, which is already on that thread. The
		# PGN write is small enough to stay here too.
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the game as a PGN file.
			message=_("Save Game As"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the PGN save dialog.
			wildcard=_("Chess Game *.pgn | *.pgn"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		try:
			if saveFileDialog.ShowModal() != wx.ID_OK:
				return
			save_as_filename = saveFileDialog.GetPath().strip()
		finally:
			saveFileDialog.Destroy()
		if not save_as_filename:
			return
		game = chess.pgn.Game.from_board(self.board)
		with open(save_as_filename, "w", encoding="utf-8") as file:
			exporter = chess.pgn.FileExporter(file)
			game.accept(exporter)

	def save_board_image(self):
		# Same rule as `save_game`: dialog and bitmap access on the GUI thread.
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the board as an image.
			message=_("Save Board To Image"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the image save dialog.
			wildcard=_("Portable Network Graphics *.png | *.png"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		try:
			if saveFileDialog.ShowModal() != wx.ID_OK:
				return
			save_as_filename = saveFileDialog.GetPath().strip()
		finally:
			saveFileDialog.Destroy()
		if not save_as_filename:
			return
		self.dialog.bitmap_buffer.SaveFile(save_as_filename, wx.BITMAP_TYPE_PNG)
