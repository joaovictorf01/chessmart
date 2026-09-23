# coding: utf-8
# pyright: basic
"""Puzzle database download and update dialog.

Opens, fetches the release manifest in the background, and shows what is
installed against what is published. The user picks the tier (light or
full) and the download runs on a thread, with progress on the gauge and
speech announcements every ten percent. NVDA stays responsive throughout;
Escape or the Cancel button interrupt without leaving a half-downloaded
file behind.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import wx
import ui
from gui import guiHelper
from logHandler import log

from ..i18n import _
from ..tactic import download as puzzle_download
from ..tactic.db import ADDON_DATA_DIRECTORY, PUZZLES_DB_NAME
from .download_base import DownloadDialogBase, format_megabytes
from .messages import show_error, show_message

# Order in which the tiers appear; light comes first because it's the right
# choice for someone installing for the first time.
TIER_ORDER = ("light", "full")
TIER_LABELS = {
	# Translators: Name of the smaller puzzle database.
	"light": _("Light"),
	# Translators: Name of the complete puzzle database.
	"full": _("Complete"),
}


class PuzzleDownloadDialog(DownloadDialogBase):
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
		self._build()
		self._start_manifest_fetch()

	# -- build -----------------------------------------------------------

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.statusText = wx.StaticText(
			self,
			-1,
			# Translators: First status of the download dialog, while the list of databases is fetched.
			_(
				"Checking for the latest puzzle database. Please wait: the choices and the Download button come alive when the list arrives.",
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

	# -- manifest ------------------------------------------------------------

	def _start_manifest_fetch(self):
		def work():
			try:
				manifest = puzzle_download.fetch_manifest()
			except puzzle_download.DownloadError as error:
				log.warning("chessmart: could not fetch the puzzle manifest: %s", error)
				wx.CallAfter(self._manifest_failed, str(error))
				return
			wx.CallAfter(self._manifest_ready, manifest)

		threading.Thread(target=work, name="chessmart.manifest", daemon=True).start()

	def _manifest_failed(self, reason: str = ""):
		if not self:
			return
		# The reason goes right into the message: someone reporting "it didn't
		# work" rarely opens the log, and the reason is what tells whether it
		# was the network, a proxy, or a certificate.
		self.statusText.SetLabel(
			# Translators: Shown when the list of available puzzle databases could not be downloaded; {reason} is the technical error.
			_(
				"Could not reach the download server. Check your internet connection and try again. Details: {reason}",
			).format(
				reason=reason or _("unknown"),
			),
		)
		# The button becomes "Try again": without it the user is left with a
		# dialog where nothing is enabled and concludes there's nothing to
		# download.
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
					download=format_megabytes(info.download_bytes),
					disk=format_megabytes(info.disk_bytes),
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
			# "Try again" after a failure to fetch the list.
			self.downloadButton.Disable()
			self.statusText.SetLabel(
				# Translators: Status while the list of databases is fetched again.
				_(
					"Checking for the latest puzzle database. Please wait: the choices and the Download button come alive when the list arrives.",
				),
			)
			ui.message(self.statusText.GetLabel())
			self._start_manifest_fetch()
			return
		info = self._selected_tier()
		if info is None or self._worker is not None:
			return
		self.downloadButton.Disable()
		self.tierRadio.Disable()
		# Translators: Announced when the puzzle database download starts.
		ui.message(
			_("Downloading {name}, {size}.").format(
				name=TIER_LABELS[info.tier],
				size=format_megabytes(info.download_bytes),
			),
		)

		def work():
			try:
				puzzle_download.download_tier(
					info,
					self.target_path,
					progress=self._progress,
					cancel=self._cancel,
					on_retry=self._retrying,
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

		self.start_worker(work, "chessmart.download")

	def _retrying(self, file: str, attempt: int, attempts: int, reason: str):
		"""A part is being downloaded again: the progress goes back, so say why."""
		log.warning(
			"chessmart: %s failed (attempt %d of %d): %s; downloading it again",
			file,
			attempt,
			attempts,
			reason,
		)
		self._last_announced_percent = -1
		# Translators: Announced when a piece of the download has to be fetched again; {reason} is the technical error.
		message = _(
			"{file} did not arrive whole (attempt {attempt} of {attempts}: {reason}). Downloading it again."
		).format(
			file=file,
			attempt=attempt,
			attempts=attempts,
			reason=reason,
		)
		wx.CallAfter(self._show_retry, message)

	def _show_retry(self, message: str):
		if not self:
			return
		self.progressText.SetLabel(message)
		ui.message(message)

	def _prepare_catalog_status(self):
		if not self:
			return
		# Translators: Announced after the download, while the list of puzzle themes is being prepared.
		message = _("Download complete. Preparing the theme catalog, this takes a moment...")
		self.progressText.SetLabel(message)
		ui.message(message)

	def _rebuild_theme_catalog(self):
		# Done here, still on the thread, so the first time tactics open
		# doesn't have to scan the whole database with NVDA frozen.
		try:
			from ..theme_catalog import rebuild_theme_catalog

			rebuild_theme_catalog(self.target_path)
		except Exception as error:  # the cache is a convenience; tactics still open without it
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
		show_message(message, _("Puzzle Database"), parent=self)
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
		show_error(message, _("Puzzle Database"), parent=self)
		self.progressText.SetLabel("")
		self.gauge.SetValue(0)
		self.tierRadio.Enable()
		self.downloadButton.Enable()
