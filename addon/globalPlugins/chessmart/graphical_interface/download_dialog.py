# coding: utf-8
# pyright: basic
"""Diálogo de download e atualização do banco de puzzles.

Abre, consulta o manifesto da release em segundo plano e mostra o que está
instalado contra o que está publicado. O usuário escolhe o nível (leve ou
completo) e o download corre numa thread, com progresso na barra e anúncios
de fala a cada dez por cento. O NVDA continua livre o tempo todo; Escape ou
o botão Cancelar interrompem sem deixar arquivo pela metade.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import wx
import gui
import ui
from gui import guiHelper
from logHandler import log

from ..i18n import _
from ..tactic import download as puzzle_download
from ..tactic.db import ADDON_DATA_DIRECTORY, PUZZLES_DB_NAME

# Ordem em que os níveis aparecem; o leve primeiro porque é a escolha certa
# para quem está instalando pela primeira vez.
TIER_ORDER = ("light", "full")
TIER_LABELS = {
	# Translators: Name of the smaller puzzle database.
	"light": _("Light"),
	# Translators: Name of the complete puzzle database.
	"full": _("Complete"),
}


def _megabytes(size: int) -> str:
	# Translators: File size in megabytes, e.g. "76 MB".
	return _("{size} MB").format(size=round(size / 1e6))


class PuzzleDownloadDialog(wx.Dialog):
	def __init__(
		self,
		parent,
		installed_path: Path | None = None,
		on_installed: Callable[[Path], None] | None = None,
	):
		# Translators: Title of the puzzle database download dialog.
		super().__init__(parent, title=_("Puzzle Database"))
		self.installed_path = installed_path
		self.on_installed = on_installed
		self.target_path = ADDON_DATA_DIRECTORY / PUZZLES_DB_NAME
		self.manifest = None
		self.installed = puzzle_download.installed_info(installed_path)
		self._cancel = threading.Event()
		self._worker = None
		self._last_announced_percent = -1
		self._build()
		self._start_manifest_fetch()

	# -- construção -----------------------------------------------------------

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.statusText = wx.StaticText(
			self,
			-1,
			# Translators: First status of the download dialog, while the list of databases is fetched.
			_(
				"Checking for the latest puzzle database. Please wait: the choices and the Download button come alive when the list arrives."
			),
		)
		helper.addItem(self.statusText)

		self.installedText = wx.StaticText(self, -1, self._installed_sentence())
		helper.addItem(self.installedText)

		# Translators: Label of the list where the user picks which database to download.
		self.tierRadio = wx.RadioBox(
			self,
			-1,
			_("Database to download"),
			choices=[TIER_LABELS[tier] for tier in TIER_ORDER],
			majorDimension=1,
			style=wx.RA_SPECIFY_COLS,
		)
		self.tierRadio.Disable()
		helper.addItem(self.tierRadio)

		self.tierDescriptionText = wx.StaticText(self, -1, "")
		helper.addItem(self.tierDescriptionText)

		self.gauge = wx.Gauge(self, -1, range=100)
		helper.addItem(self.gauge)
		self.progressText = wx.StaticText(self, -1, "")
		helper.addItem(self.progressText)

		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: Button that starts the download of the puzzle database.
		self.downloadButton = buttons.addButton(self, wx.ID_OK, _("&Download"))
		self.downloadButton.Disable()
		# Translators: Button that cancels the download or closes the dialog.
		self.cancelButton = buttons.addButton(self, wx.ID_CANCEL, _("&Cancel"))
		helper.addDialogDismissButtons(buttons)

		self.Bind(wx.EVT_BUTTON, self.onDownload, self.downloadButton)
		self.Bind(wx.EVT_BUTTON, self.onCancel, self.cancelButton)
		self.Bind(wx.EVT_RADIOBOX, self.onTierChanged, self.tierRadio)
		self.Bind(wx.EVT_CLOSE, self.onCancel)

		self.SetSizerAndFit(sizer)
		self.CentreOnParent()
		self.statusText.SetFocus()

	def _installed_sentence(self) -> str:
		if self.installed is None:
			if self.installed_path and Path(self.installed_path).is_file():
				# Translators: Shown when a puzzle database exists but carries no version information.
				return _("Installed: a puzzle database of unknown version.")
			# Translators: Shown when no puzzle database is installed yet.
			return _("Installed: none. Tactics need a puzzle database to work.")
		label = TIER_LABELS.get(self.installed.tier, self.installed.tier)
		date = self.installed.source_date
		when = date.strftime("%Y-%m") if date else self.installed.generated_at[:10]
		# Translators: Describes the installed puzzle database, e.g. "Installed: Light, 745,164 puzzles, Lichess base of 2026-09."
		return _("Installed: {tier}, {count:,} puzzles, Lichess base of {when}.").format(
			tier=label,
			count=self.installed.puzzle_count,
			when=when,
		)

	# -- manifesto ------------------------------------------------------------

	def _start_manifest_fetch(self):
		def work():
			try:
				manifest = puzzle_download.fetch_manifest()
			except puzzle_download.DownloadError as error:
				log.warning("chessmart: could not fetch the puzzle manifest: %s", error)
				wx.CallAfter(self._manifest_failed)
				return
			wx.CallAfter(self._manifest_ready, manifest)

		threading.Thread(target=work, name="chessmart.manifest", daemon=True).start()

	def _manifest_failed(self):
		if not self:
			return
		self.statusText.SetLabel(
			# Translators: Shown when the list of available puzzle databases could not be downloaded.
			_("Could not reach the download server. Check your internet connection and try again."),
		)
		# O botão vira "Tentar de novo": sem isso o usuário fica num diálogo
		# em que nada está habilitado e conclui que não há o que baixar.
		# Translators: Label of the download button after the list of databases could not be fetched.
		self.downloadButton.SetLabel(_("&Try again"))
		self.downloadButton.Enable()
		self.Fit()
		ui.message(self.statusText.GetLabel())

	def _manifest_ready(self, manifest):
		if not self:
			return
		self.manifest = manifest
		# Translators: Button that starts the download of the puzzle database.
		self.downloadButton.SetLabel(_("&Download"))
		date = manifest.source_date
		when = date.strftime("%Y-%m") if date else manifest.generated_at[:10]
		if puzzle_download.update_available(manifest, self.installed):
			if self.installed is None:
				# Translators: Shown when a puzzle database is available and none is installed.
				status = _("Available: Lichess base of {when}.").format(when=when)
			else:
				# Translators: Shown when a newer puzzle database than the installed one is available.
				status = _("A newer Lichess base of {when} is available.").format(when=when)
		else:
			# Translators: Shown when the installed puzzle database is already the latest.
			status = _("Your puzzle database is up to date (Lichess base of {when}).").format(when=when)
		self.statusText.SetLabel(status)
		available = [tier for tier in TIER_ORDER if tier in manifest.tiers]
		if not available:
			ui.message(status)
			return
		for index, tier in enumerate(TIER_ORDER):
			info = manifest.tiers.get(tier)
			if info is None:
				self.tierRadio.EnableItem(index, False)
				continue
			self.tierRadio.SetItemLabel(
				index,
				# Translators: One choice of puzzle database: name, puzzle count, download size and disk size.
				_("{name}: {count:,} puzzles, {download} to download, {disk} on disk").format(
					name=TIER_LABELS[tier],
					count=info.puzzle_count,
					download=_megabytes(info.download_bytes),
					disk=_megabytes(info.disk_bytes),
				),
			)
		default = self.installed.tier if self.installed and self.installed.tier in available else available[0]
		self.tierRadio.SetSelection(TIER_ORDER.index(default))
		self.tierRadio.Enable()
		self.downloadButton.Enable()
		self.onTierChanged(None)
		self.Fit()
		ui.message(status)
		self.tierRadio.SetFocus()

	def onTierChanged(self, event):
		info = self._selected_tier()
		self.tierDescriptionText.SetLabel(info.description if info else "")

	def _selected_tier(self):
		if self.manifest is None:
			return None
		return self.manifest.tiers.get(TIER_ORDER[self.tierRadio.GetSelection()])

	# -- download -------------------------------------------------------------

	def onDownload(self, event):
		if self.manifest is None:
			# "Tentar de novo" depois de uma falha na lista.
			self.downloadButton.Disable()
			self.statusText.SetLabel(
				# Translators: Status while the list of databases is fetched again.
				_(
					"Checking for the latest puzzle database. Please wait: the choices and the Download button come alive when the list arrives."
				),
			)
			ui.message(self.statusText.GetLabel())
			self._start_manifest_fetch()
			return
		info = self._selected_tier()
		if info is None or self._worker is not None:
			return
		self._cancel.clear()
		self._last_announced_percent = -1
		self.downloadButton.Disable()
		self.tierRadio.Disable()
		# Translators: Announced when the puzzle database download starts.
		ui.message(
			_("Downloading {name}, {size}.").format(
				name=TIER_LABELS[info.tier],
				size=_megabytes(info.download_bytes),
			),
		)

		def work():
			try:
				puzzle_download.download_tier(
					info,
					self.target_path,
					progress=self._progress,
					cancel=self._cancel,
				)
				wx.CallAfter(self._prepare_catalog_status)
				self._rebuild_theme_catalog()
			except puzzle_download.DownloadCancelled:
				wx.CallAfter(self._finished_cancelled)
				return
			except puzzle_download.DownloadError as error:
				log.error("chessmart: puzzle database download failed: %s", error)
				wx.CallAfter(self._finished_failed, str(error))
				return
			wx.CallAfter(self._finished_ok, info)

		self._worker = threading.Thread(target=work, name="chessmart.download", daemon=True)
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
		self.progressText.SetLabel(
			# Translators: Download progress text, e.g. "30 MB of 76 MB (40%)".
			_("{done} of {total} ({percent}%)").format(
				done=_megabytes(done),
				total=_megabytes(total),
				percent=percent,
			),
		)

	def _prepare_catalog_status(self):
		if not self:
			return
		# Translators: Announced after the download, while the list of puzzle themes is being prepared.
		message = _("Download complete. Preparing the theme catalog, this takes a moment...")
		self.progressText.SetLabel(message)
		ui.message(message)

	def _rebuild_theme_catalog(self):
		# Feito aqui, ainda na thread, para a primeira abertura da tática não
		# ter que varrer o banco inteiro com o NVDA parado.
		try:
			from ..theme_catalog import rebuild_theme_catalog

			rebuild_theme_catalog(self.target_path)
		except Exception as error:  # cache é conveniência; a tática abre sem ele
			log.warning("chessmart: theme catalog rebuild after download failed: %s", error)

	def _finished_ok(self, info):
		self._worker = None
		if not self:
			return
		self.gauge.SetValue(100)
		# Translators: Message shown when the puzzle database was installed successfully.
		message = _("The {name} puzzle database is installed: {count:,} puzzles.").format(
			name=TIER_LABELS[info.tier],
			count=info.puzzle_count,
		)
		gui.messageBox(message, _("Puzzle Database"), style=wx.ICON_INFORMATION, parent=self)
		if self.on_installed is not None:
			self.on_installed(self.target_path)
		self.EndModal(wx.ID_OK)

	def _finished_cancelled(self):
		self._worker = None
		if not self:
			return
		# Translators: Shown after the user cancels the puzzle database download.
		message = _("Download cancelled.")
		self.progressText.SetLabel(message)
		ui.message(message)
		self.gauge.SetValue(0)
		self.tierRadio.Enable()
		self.downloadButton.Enable()

	def _finished_failed(self, reason: str):
		self._worker = None
		if not self:
			return
		# Translators: Message shown when the puzzle database download failed.
		message = _("The download failed: {reason}").format(reason=reason)
		gui.messageBox(message, _("Puzzle Database"), style=wx.ICON_ERROR, parent=self)
		self.progressText.SetLabel("")
		self.gauge.SetValue(0)
		self.tierRadio.Enable()
		self.downloadButton.Enable()

	def onCancel(self, event):
		if self._worker is not None and self._worker.is_alive():
			self._cancel.set()
			return
		self.EndModal(wx.ID_CANCEL)
