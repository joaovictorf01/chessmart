# coding: utf-8
# pyright: basic

"""Diálogo de download das tabelas Syzygy.

Dois conjuntos: até 4 peças (poucos MB, cobre rei e peão contra rei e os
mates) e até 5 (quase 1 GB, cobre torre e peão contra torre, dama contra
peão e o resto da trilha). O download corre numa thread, arquivo por
arquivo, com progresso na barra e na fala; cancelar guarda o que já chegou,
e o próximo download continua de onde parou.
"""

from __future__ import annotations

import threading

import wx
import gui
import ui
from gui import guiHelper
from logHandler import log

from ..endgame import tablebase
from ..i18n import _
from ..tactic import download as puzzle_download


def _megabytes(size: int) -> str:
	# Translators: File size in megabytes, e.g. "76 MB".
	return _("{size} MB").format(size=round(size / 1e6))


def installed_sentence() -> str:
	limit = tablebase.installed_piece_limit()
	if limit == 0:
		# Translators: Shown when no tablebases are installed.
		return _("Tablebases: none installed. The judge is silent until they are.")
	# Translators: Shown with the installed tablebases, e.g. "Tablebases: up to 5 pieces installed."
	return _("Tablebases: up to {pieces} pieces installed.").format(pieces=limit)


class TablebaseDownloadDialog(wx.Dialog):
	def __init__(self, parent):
		# Translators: Title of the tablebase download dialog.
		super().__init__(parent, title=_("Endgame Tablebases"))
		self.sets = tablebase.table_sets()
		self._cancel = threading.Event()
		self._worker = None
		self._last_announced_percent = -1
		self._build()

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.statusText = wx.StaticText(self, -1, installed_sentence())
		helper.addItem(self.statusText)

		choices = []
		for table_set in self.sets:
			missing = tablebase.missing_files(table_set.files)
			remaining = sum(f.bytes for f in missing)
			if table_set.max_pieces == 4:
				# Translators: The smaller set of tablebases.
				name = _("Up to 4 pieces: king and pawn against king, and the elementary mates")
			else:
				# Translators: The full set of tablebases.
				name = _(
					"Up to 5 pieces: rook and pawn against rook, queen against pawn, everything in the lessons"
				)
			if missing:
				# Translators: One set of tablebases with its download size, e.g. "Up to 5 pieces (...): 984 MB, 120 MB still to download".
				choices.append(
					_("{name}: {total}, {remaining} still to download").format(
						name=name,
						total=_megabytes(table_set.total_bytes),
						remaining=_megabytes(remaining),
					),
				)
			else:
				# Translators: One set of tablebases that is fully installed.
				choices.append(
					_("{name}: {total}, installed").format(name=name, total=_megabytes(table_set.total_bytes))
				)
		# Translators: Label of the list where the user picks which tablebases to download.
		self.setRadio = wx.RadioBox(
			self, -1, _("Tables to download"), choices=choices, majorDimension=1, style=wx.RA_SPECIFY_COLS
		)
		self.setRadio.SetSelection(len(self.sets) - 1)
		helper.addItem(self.setRadio)

		note = wx.StaticText(
			self,
			-1,
			# Translators: Note in the tablebase download dialog.
			_(
				"Source: the Syzygy tables mirrored by Lichess (tablebase.lichess.ovh). Each file is checked before it is kept; a cancelled download resumes where it stopped."
			),
		)
		note.Wrap(520)
		helper.addItem(note)

		self.gauge = wx.Gauge(self, -1, range=100)
		helper.addItem(self.gauge)
		self.progressText = wx.StaticText(self, -1, "")
		helper.addItem(self.progressText)

		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: Button that starts the tablebase download.
		self.downloadButton = buttons.addButton(self, wx.ID_OK, _("&Download"))
		# Translators: Button that cancels the download or closes the dialog.
		self.cancelButton = buttons.addButton(self, wx.ID_CANCEL, _("&Cancel"))
		helper.addDialogDismissButtons(buttons)

		self.Bind(wx.EVT_BUTTON, self.onDownload, self.downloadButton)
		self.Bind(wx.EVT_BUTTON, self.onCancel, self.cancelButton)
		self.Bind(wx.EVT_CLOSE, self.onCancel)
		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.setRadio.SetFocus()

	def onDownload(self, event):
		if self._worker is not None:
			return
		table_set = self.sets[self.setRadio.GetSelection()]
		missing = tablebase.missing_files(table_set.files)
		if not missing:
			# Translators: Announced when the chosen tablebases are already installed.
			ui.message(_("These tables are already installed."))
			return
		self._cancel.clear()
		self._last_announced_percent = -1
		self.downloadButton.Disable()
		self.setRadio.Disable()
		# Translators: Announced when the tablebase download starts.
		ui.message(
			_("Downloading {count} files, {size}.").format(
				count=len(missing), size=_megabytes(sum(f.bytes for f in missing))
			)
		)

		def work():
			try:
				tablebase.download_tables(table_set.files, progress=self._progress, cancel=self._cancel)
			except puzzle_download.DownloadCancelled:
				wx.CallAfter(self._finished_cancelled)
				return
			except puzzle_download.DownloadError as error:
				log.error("chessmart: tablebase download failed: %s", error)
				wx.CallAfter(self._finished_failed, str(error))
				return
			wx.CallAfter(self._finished_ok, table_set)

		self._worker = threading.Thread(target=work, name="chessmart.tablebases", daemon=True)
		self._worker.start()

	def _progress(self, done: int, total: int):
		percent = int(done * 100 / total) if total else 0
		wx.CallAfter(self._show_progress, done, total, percent)
		if percent // 10 > self._last_announced_percent // 10:
			self._last_announced_percent = percent
			# Translators: Download progress announced by speech, e.g. "40 percent".
			wx.CallAfter(ui.message, _("{percent} percent").format(percent=percent))

	def _show_progress(self, done, total, percent):
		if not self:
			return
		self.gauge.SetValue(min(percent, 100))
		# Translators: Download progress text, e.g. "30 MB of 76 MB (40%)".
		self.progressText.SetLabel(
			_("{done} of {total} ({percent}%)").format(
				done=_megabytes(done), total=_megabytes(total), percent=percent
			)
		)

	def _finished_ok(self, table_set):
		self._worker = None
		if not self:
			return
		self.gauge.SetValue(100)
		# Translators: Message shown when the tablebases were installed.
		message = _("Tablebases up to {pieces} pieces installed. The judge is on.").format(
			pieces=table_set.max_pieces
		)
		gui.messageBox(message, _("Endgame Tablebases"), style=wx.ICON_INFORMATION, parent=self)
		self.EndModal(wx.ID_OK)

	def _finished_cancelled(self):
		self._worker = None
		if not self:
			return
		# Translators: Shown after the user cancels the tablebase download.
		message = _("Download cancelled. What arrived is kept; the next download resumes from there.")
		self.progressText.SetLabel(message)
		ui.message(message)
		self.setRadio.Enable()
		self.downloadButton.Enable()
		self.statusText.SetLabel(installed_sentence())

	def _finished_failed(self, reason: str):
		self._worker = None
		if not self:
			return
		# Translators: Message shown when the tablebase download failed.
		message = _("The download failed: {reason}").format(reason=reason)
		gui.messageBox(message, _("Endgame Tablebases"), style=wx.ICON_ERROR, parent=self)
		self.progressText.SetLabel("")
		self.setRadio.Enable()
		self.downloadButton.Enable()
		self.statusText.SetLabel(installed_sentence())

	def onCancel(self, event):
		if self._worker is not None and self._worker.is_alive():
			self._cancel.set()
			return
		self.EndModal(wx.ID_CANCEL)
