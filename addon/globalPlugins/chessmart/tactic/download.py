# coding: utf-8
# pyright: basic
"""Download and update of the puzzle database.

The database is published as an asset of the fixed `puzzles-latest` release
of the repository, regenerated monthly by the workflow from the Lichess
database. There is no UI here: the caller passes a progress function and a
cancellation `Event`, and takes care of displaying that however it likes.
"""

from __future__ import annotations

import dataclasses
import email.utils
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Callable

DEFAULT_MANIFEST_URL = (
	"https://github.com/joaovictorf01/chessmart/releases/download/puzzles-latest/manifest.json"
)


def manifest_url() -> str:
	"""Where the manifest comes from: environment variable, an override file in
	the data folder (for testing against a local server), or the release."""
	from .db import ADDON_DATA_DIRECTORY

	override = os.environ.get("CHESSMART_PUZZLES_MANIFEST_URL")
	if override:
		return override
	override_file = ADDON_DATA_DIRECTORY / "manifest_url.txt"
	if override_file.is_file():
		value = override_file.read_text(encoding="utf-8").strip()
		if value:
			return value
	return DEFAULT_MANIFEST_URL


USER_AGENT = "chessmart-nvda-addon/1.0"
CHUNK = 256 * 1024

ProgressCallback = Callable[[int, int], None]
RetryCallback = Callable[[str, int, int, str], None]
"""Called when a part has to be downloaded again: file, attempt, attempts, reason."""


class DownloadCancelled(Exception):
	pass


class DownloadError(Exception):
	pass


@dataclasses.dataclass(frozen=True)
class DownloadPart:
	"""A file to download: a slice of the .gz, or the whole thing when it's small."""

	file: str
	bytes: int
	sha256: str
	url: str


@dataclasses.dataclass(frozen=True)
class TierInfo:
	tier: str
	description: str
	puzzle_count: int
	disk_bytes: int
	download_bytes: int
	download_file: str
	download_sha256: str
	download_url: str
	# The parts, in order; concatenated they form the whole .gz. An older
	# manifest, without `parts`, becomes a single part: the file itself.
	parts: tuple[DownloadPart, ...] = ()


@dataclasses.dataclass(frozen=True)
class Manifest:
	generated_at: str
	source_last_modified: str
	tiers: dict[str, TierInfo]

	@property
	def source_date(self):
		return _parse_http_date(self.source_last_modified)


@dataclasses.dataclass(frozen=True)
class InstalledInfo:
	tier: str
	puzzle_count: int
	source_last_modified: str
	generated_at: str

	@property
	def source_date(self):
		return _parse_http_date(self.source_last_modified)


def _parse_http_date(value: str):
	try:
		return email.utils.parsedate_to_datetime(value)
	except (TypeError, ValueError, IndexError):
		return None


# ---------------------------------------------------------------- manifest


def fetch_manifest(url: str | None = None, timeout: float = 30.0) -> Manifest:
	url = url or manifest_url()
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			payload = json.loads(response.read().decode("utf-8"))
	except (urllib.error.URLError, OSError, ValueError) as error:
		raise DownloadError(f"manifest: {error}") from error
	return parse_manifest(payload, base_url=url)


def parse_manifest(payload: dict, base_url: str) -> Manifest:
	tiers = {}
	for name, entry in (payload.get("tiers") or {}).items():
		download = entry.get("download") or {}
		raw_parts = download.get("parts") or [download]
		parts = tuple(
			DownloadPart(
				file=str(part.get("file", "")),
				bytes=int(part.get("bytes", 0)),
				sha256=str(part.get("sha256", "")),
				url=urllib.parse.urljoin(base_url, str(part.get("file", ""))),
			)
			for part in raw_parts
			if part.get("file")
		)
		tiers[name] = TierInfo(
			tier=name,
			description=str(entry.get("description", "")),
			puzzle_count=int(entry.get("puzzleCount", 0)),
			disk_bytes=int(entry.get("bytes", 0)),
			download_bytes=int(download.get("bytes", 0)),
			download_file=str(download.get("file", "")),
			download_sha256=str(download.get("sha256", "")),
			download_url=urllib.parse.urljoin(base_url, str(download.get("file", ""))),
			parts=parts,
		)
	source = payload.get("source") or {}
	return Manifest(
		generated_at=str(payload.get("generatedAt", "")),
		source_last_modified=str(source.get("lastModified", "")),
		tiers=tiers,
	)


# ---------------------------------------------------------------- installed


def installed_info(db_path: Path | None) -> InstalledInfo | None:
	"""Read the `meta` table of the installed database; None if there is no database or meta."""
	if db_path is None or not Path(db_path).is_file():
		return None
	from .db import load_store

	store = load_store()
	import sqlite3

	try:
		connection = sqlite3.connect(store.read_only_uri(Path(db_path)), uri=True)
	except sqlite3.Error:
		return None
	try:
		rows = dict(connection.execute("SELECT key, value FROM meta"))
	except sqlite3.Error:
		return None
	finally:
		connection.close()
	return InstalledInfo(
		tier=rows.get("tier", ""),
		puzzle_count=int(rows.get("puzzleCount", 0) or 0),
		source_last_modified=rows.get("sourceLastModified", ""),
		generated_at=rows.get("generatedAt", ""),
	)


def update_available(manifest: Manifest, installed: InstalledInfo | None) -> bool:
	"""Is there a newer database than the installed one? With no `meta` on the installed one, yes."""
	if installed is None:
		return True
	new, old = manifest.source_date, installed.source_date
	if new is None or old is None:
		return manifest.generated_at > installed.generated_at
	return new > old


# ---------------------------------------------------------------- download


class _PartFailed(Exception):
	"""A part did not arrive whole or did not check out; worth retrying that part."""


def download_tier(
	tier: TierInfo,
	target_path: Path,
	progress: ProgressCallback | None = None,
	cancel: threading.Event | None = None,
	timeout: float = 60.0,
	attempts_per_part: int = 3,
	retry_delay: float = 5.0,
	on_retry: RetryCallback | None = None,
) -> Path:
	"""Download the tier's `.db.gz`, decompress it as a stream and install it at `target_path`.

	The .gz can arrive in parts (large assets fail on GitHub); they pass, in
	order, through the same decompressor, as if they were a single file. The
	compressed file never touches disk: each chunk goes to zlib and the
	result to `target.part`.

	Checked at two levels: the SHA-256 of each part as soon as it finishes (an
	error shows up early, not after 600 MB) and that of the whole .gz at the
	end, which is what the manifest signs. A part that fails is retried on
	its own: before each part, copies of the decompressor and of the running
	hash are kept, and the output rewinds to where the part started. Only
	once everything checks out does `.part` replace the current database --
	anyone mid-session keeps using the old one until the next startup.
	"""
	target_path = Path(target_path)
	parts = tier.parts or (
		DownloadPart(tier.download_file, tier.download_bytes, tier.download_sha256, tier.download_url),
	)
	# The manifest is the trust root: without its hashes nothing verifies the
	# file, so a manifest that lacks one is refused before a byte is fetched.
	if not tier.download_sha256:
		raise DownloadError(f"manifest has no checksum for {tier.download_file or tier.tier}")
	for part in parts:
		if not part.sha256:
			raise DownloadError(f"manifest has no checksum for {part.file}")
	target_path.parent.mkdir(parents=True, exist_ok=True)
	partial = target_path.with_name(target_path.name + ".part")
	total = tier.download_bytes or sum(part.bytes for part in parts)
	whole_digest = hashlib.sha256()
	inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
	done = 0
	try:
		with partial.open("wb") as out:
			if progress:
				progress(0, total)
			for part in parts:
				out_offset = out.tell()
				done_before = done
				digest_before = whole_digest.copy()
				inflater_before = inflater.copy()
				for attempt in range(1, attempts_per_part + 1):
					try:
						done = _download_part(
							part,
							out,
							inflater,
							whole_digest,
							done,
							total,
							progress,
							cancel,
							timeout,
						)
						break
					except (_PartFailed, urllib.error.URLError, OSError, zlib.error) as error:
						if attempt == attempts_per_part:
							raise DownloadError(f"download: {part.file}: {error}") from error
						# Say what happened: a retry that says nothing looks like the
						# download starting over on its own, and the reason (a checksum
						# that does not match the manifest, a connection that dropped)
						# is what tells the two apart.
						if on_retry is not None:
							on_retry(part.file, attempt, attempts_per_part, str(error))
						# Rewind to the state before this part and retry just that one.
						out.seek(out_offset)
						out.truncate()
						done = done_before
						whole_digest = digest_before.copy()
						inflater = inflater_before.copy()
						if cancel is not None and cancel.wait(retry_delay):
							raise DownloadCancelled()
						elif cancel is None:
							time.sleep(retry_delay)
			out.write(inflater.flush())
	except DownloadCancelled:
		partial.unlink(missing_ok=True)
		raise
	except DownloadError:
		partial.unlink(missing_ok=True)
		raise
	except (OSError, zlib.error) as error:
		partial.unlink(missing_ok=True)
		raise DownloadError(f"download: {error}") from error

	if whole_digest.hexdigest() != tier.download_sha256:
		partial.unlink(missing_ok=True)
		raise DownloadError("download: checksum mismatch, the file is corrupt or was changed in transit")

	from .db import is_puzzles_database

	if not is_puzzles_database(partial):
		partial.unlink(missing_ok=True)
		raise DownloadError("download: the file is not a puzzle database")

	try:
		partial.replace(target_path)
	except OSError as error:
		partial.unlink(missing_ok=True)
		raise DownloadError(f"install: {error}") from error
	return target_path


def _download_part(
	part: DownloadPart,
	out,
	inflater,
	whole_digest,
	done: int,
	total: int,
	progress: ProgressCallback | None,
	cancel: threading.Event | None,
	timeout: float,
) -> int:
	"""Download one part into the stream in progress; return the total bytes received.

	Raises `_PartFailed` if the part came with a size or SHA-256 different
	from the manifest, `DownloadCancelled` if the user gave up, and lets
	network and zlib errors pass through for the caller to decide on a retry.
	"""
	request = urllib.request.Request(part.url, headers={"User-Agent": USER_AGENT})
	part_digest = hashlib.sha256()
	received = 0
	with urllib.request.urlopen(request, timeout=timeout) as response:
		while True:
			if cancel is not None and cancel.is_set():
				raise DownloadCancelled()
			chunk = response.read(CHUNK)
			if not chunk:
				break
			part_digest.update(chunk)
			whole_digest.update(chunk)
			out.write(inflater.decompress(chunk))
			received += len(chunk)
			done += len(chunk)
			if progress:
				progress(done, total)
	if part.bytes and received != part.bytes:
		raise _PartFailed(f"expected {part.bytes} bytes, received {received}")
	if part_digest.hexdigest() != part.sha256:
		raise _PartFailed("checksum mismatch")
	return done
