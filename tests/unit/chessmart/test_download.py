# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Puzzle database download: manifest, parts, verification and cancellation.

Spins up a local HTTP server with a fake .gz (it doesn't need to be a valid
database: `is_puzzles_database` is mocked out), split into parts, and a
handler that can corrupt or truncate a part on its first request.
"""

import functools
import gzip
import hashlib
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from chessmart.tactic import download as dl


def _sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


class FlakyHandler(http.server.SimpleHTTPRequestHandler):
	"""The first request for a name in `corrupt_once` comes back with mangled bytes;
	for `short_once`, truncated midway; for `missing`, 404. Counts the hits."""

	corrupt_once: set[str] = set()
	short_once: set[str] = set()
	missing: set[str] = set()
	hits: dict[str, int] = {}

	def log_message(self, *args, **kwargs):
		pass

	def do_GET(self):
		name = self.path.rsplit("/", 1)[-1]
		FlakyHandler.hits[name] = FlakyHandler.hits.get(name, 0) + 1
		path = Path(self.directory) / name
		if name in FlakyHandler.missing or not path.is_file():
			self.send_error(404)
			return
		data = path.read_bytes()
		if name in FlakyHandler.corrupt_once:
			FlakyHandler.corrupt_once.discard(name)
			data = data[:-8] + b"\0" * 8
		short = name in FlakyHandler.short_once
		FlakyHandler.short_once.discard(name)
		self.send_response(200)
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		self.wfile.write(data[: len(data) // 2] if short else data)
		if short:
			self.wfile.flush()
			self.connection.close()


class TestPartsDownload(unittest.TestCase):
	PART_SIZE = 4096

	@classmethod
	def setUpClass(cls):
		cls.tmp = tempfile.TemporaryDirectory()
		cls.dist = Path(cls.tmp.name) / "dist"
		cls.dist.mkdir()
		# Random bytes don't compress: the .gz ends up ~50 KB and splits into several parts.
		cls.payload = os.urandom(50_000)
		gz = gzip.compress(cls.payload, compresslevel=1)
		assert len(gz) > 3 * cls.PART_SIZE, "the fixture needs to yield at least four parts"
		parts = [gz[i : i + cls.PART_SIZE] for i in range(0, len(gz), cls.PART_SIZE)]
		for index, part in enumerate(parts, 1):
			(cls.dist / f"puzzles-light.db.gz.part{index}").write_bytes(part)
		(cls.dist / "puzzles-light.db.gz").write_bytes(gz)
		cls.manifest = {
			"schemaVersion": 2,
			"generatedAt": "2026-09-17T00:00:00+00:00",
			"source": {"lastModified": "Wed, 09 Sep 2026 17:40:14 GMT"},
			"tiers": {
				"light": {
					"description": "test",
					"puzzleCount": 1,
					"bytes": len(cls.payload),
					"sha256": _sha256(cls.payload),
					"download": {
						"file": "puzzles-light.db.gz",
						"bytes": len(gz),
						"sha256": _sha256(gz),
						"parts": [
							{"file": f"puzzles-light.db.gz.part{i}", "bytes": len(p), "sha256": _sha256(p)}
							for i, p in enumerate(parts, 1)
						],
					},
				},
			},
		}
		(cls.dist / "manifest.json").write_text(json.dumps(cls.manifest), encoding="utf-8")
		handler = functools.partial(FlakyHandler, directory=str(cls.dist))
		cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
		threading.Thread(target=cls.server.serve_forever, daemon=True).start()
		cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/"
		# The test file isn't a real SQLite database; structural validation is out of scope here.
		cls.patcher = mock.patch("chessmart.tactic.db.is_puzzles_database", return_value=True)
		cls.patcher.start()

	@classmethod
	def tearDownClass(cls):
		cls.patcher.stop()
		cls.server.shutdown()
		cls.tmp.cleanup()

	def setUp(self):
		FlakyHandler.hits.clear()
		FlakyHandler.corrupt_once.clear()
		FlakyHandler.short_once.clear()
		FlakyHandler.missing.clear()
		self.work = Path(tempfile.mkdtemp(dir=self.tmp.name))
		self.tier = dl.fetch_manifest(self.base + "manifest.json").tiers["light"]

	def test_manifest_with_parts_is_parsed_in_order(self):
		names = [p.file for p in self.tier.parts]
		self.assertEqual(names, [f"puzzles-light.db.gz.part{i}" for i in range(1, len(names) + 1)])
		self.assertGreaterEqual(len(names), 4)
		self.assertEqual(sum(p.bytes for p in self.tier.parts), self.tier.download_bytes)

	def test_manifest_without_parts_is_a_single_part(self):
		old = json.loads(json.dumps(self.manifest))
		del old["tiers"]["light"]["download"]["parts"]
		tier = dl.parse_manifest(old, self.base).tiers["light"]
		self.assertEqual([p.file for p in tier.parts], ["puzzles-light.db.gz"])
		dl.download_tier(tier, self.work / "old.db")
		self.assertEqual((self.work / "old.db").read_bytes(), self.payload)

	def test_parts_are_joined_and_the_whole_is_verified(self):
		progress = []
		target = dl.download_tier(
			self.tier,
			self.work / "p.db",
			progress=lambda d, t: progress.append((d, t)),
		)
		self.assertEqual(target.read_bytes(), self.payload)
		self.assertEqual(progress[-1], (self.tier.download_bytes, self.tier.download_bytes))
		self.assertFalse((self.work / "p.db.part").exists())

	def test_corrupt_part_is_retried_alone(self):
		FlakyHandler.corrupt_once.add("puzzles-light.db.gz.part2")
		dl.download_tier(self.tier, self.work / "r.db", retry_delay=0)
		self.assertEqual((self.work / "r.db").read_bytes(), self.payload)
		self.assertEqual(FlakyHandler.hits["puzzles-light.db.gz.part1"], 1)
		self.assertEqual(FlakyHandler.hits["puzzles-light.db.gz.part2"], 2)

	def test_cut_connection_is_retried_alone(self):
		last = self.tier.parts[-1].file
		FlakyHandler.short_once.add(last)
		dl.download_tier(self.tier, self.work / "s.db", retry_delay=0)
		self.assertEqual((self.work / "s.db").read_bytes(), self.payload)
		self.assertEqual(FlakyHandler.hits[last], 2)
		self.assertEqual(FlakyHandler.hits["puzzles-light.db.gz.part1"], 1)

	def test_missing_part_fails_clearly_and_leaves_nothing(self):
		FlakyHandler.missing.add("puzzles-light.db.gz.part2")
		with self.assertRaises(dl.DownloadError) as raised:
			dl.download_tier(self.tier, self.work / "m.db", retry_delay=0, attempts_per_part=2)
		self.assertIn("part2", str(raised.exception))
		self.assertFalse((self.work / "m.db").exists())
		self.assertFalse((self.work / "m.db.part").exists())

	def test_cancel_during_a_later_part_leaves_nothing(self):
		cancel = threading.Event()
		first = self.tier.parts[0].bytes

		def cancel_after_first_part(done, total):
			if done > first:
				cancel.set()

		with self.assertRaises(dl.DownloadCancelled):
			dl.download_tier(self.tier, self.work / "c.db", progress=cancel_after_first_part, cancel=cancel)
		self.assertFalse((self.work / "c.db").exists())
		self.assertFalse((self.work / "c.db.part").exists())

	def test_wrong_whole_checksum_is_rejected(self):
		bad = json.loads(json.dumps(self.manifest))
		bad["tiers"]["light"]["download"]["sha256"] = "0" * 64
		tier = dl.parse_manifest(bad, self.base).tiers["light"]
		with self.assertRaises(dl.DownloadError) as raised:
			dl.download_tier(tier, self.work / "w.db", retry_delay=0)
		self.assertIn("checksum", str(raised.exception))
		self.assertFalse((self.work / "w.db").exists())


class TestUpdateAvailable(unittest.TestCase):
	def _manifest(self, last_modified):
		return dl.parse_manifest(
			{
				"generatedAt": "2026-09-17T00:00:00+00:00",
				"source": {"lastModified": last_modified},
				"tiers": {},
			},
			"http://example/",
		)

	def test_no_installed_database_means_update(self):
		self.assertTrue(dl.update_available(self._manifest("Wed, 09 Sep 2026 17:40:14 GMT"), None))

	def test_same_base_means_no_update(self):
		installed = dl.InstalledInfo("light", 1, "Wed, 09 Sep 2026 17:40:14 GMT", "2026-09-17T00:00:00+00:00")
		self.assertFalse(dl.update_available(self._manifest("Wed, 09 Sep 2026 17:40:14 GMT"), installed))

	def test_newer_base_means_update(self):
		installed = dl.InstalledInfo("light", 1, "Thu, 19 Mar 2026 03:47:38 GMT", "2026-03-19T00:00:00+00:00")
		self.assertTrue(dl.update_available(self._manifest("Wed, 09 Sep 2026 17:40:14 GMT"), installed))
