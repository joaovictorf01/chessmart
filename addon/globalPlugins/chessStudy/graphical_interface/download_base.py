# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What the puzzle and tablebase download dialogs share (architecture review, finding 11).

A worker thread that can be cancelled, progress on the gauge and spoken every
ten percent, and Escape that cancels a running download before it closes the
dialog. Each dialog keeps what is its own: what to download and what to say
when it ends.
"""

from __future__ import annotations

import threading
from typing import Callable

import ui
import wx

from ..i18n import _


def format_megabytes(size: int) -> str:
	# Translators: File size in megabytes, e.g. "76 MB".
	return _("{size} MB").format(size=round(size / 1e6))


class DownloadDialogBase(wx.Dialog):
	"""Subclasses create `self.gauge` and `self.progressText` and call `start_worker`."""

	gauge: wx.Gauge
	progressText: wx.StaticText

	def __init__(self, parent, title: str):
		super().__init__(parent, title=title)
		self._cancel = threading.Event()
		self._worker: threading.Thread | None = None
		self._last_announced_percent = -1

	def start_worker(self, work: Callable[[], None], name: str) -> None:
		self._cancel.clear()
		self._last_announced_percent = -1
		self._worker = threading.Thread(target=work, name=name, daemon=True)
		self._worker.start()

	def _progress(self, done: int, total: int):
		"""Called from the worker thread."""
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
				done=format_megabytes(done),
				total=format_megabytes(total),
				percent=percent,
			),
		)

	def onCancel(self, event):
		if self._worker is not None and self._worker.is_alive():
			self._cancel.set()
			return
		self.EndModal(wx.ID_CANCEL)
