#!/usr/bin/env python3
"""Generates the manifest of 3, 4 and 5-piece Syzygy tables from the Lichess mirror.

    py -3 tools/build_syzygy_manifest.py

Reads the listing of the `3-4-5-wdl` and `3-4-5-dtz` folders (name and size of
each file) and the mirror's `sha256` file, and writes
`addon/globalPlugins/chessmart/endgame/syzygy_manifest.json`. The add-on
downloads file by file from this manifest and checks each one by SHA-256:
the listing doesn't need to be read at runtime, and the total size is known
before starting.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

MIRROR = "https://tablebase.lichess.ovh/tables/standard/"
FOLDERS = {"wdl": "3-4-5-wdl", "dtz": "3-4-5-dtz"}
TARGET = (
	Path(__file__).resolve().parents[1]
	/ "addon"
	/ "globalPlugins"
	/ "chessmart"
	/ "endgame"
	/ "syzygy_manifest.json"
)
LISTING_LINE = re.compile(r'<a href="(?P<name>[^"]+\.rtb[wz])">[^<]*</a>\s+\S+\s+\S+\s+(?P<bytes>\d+)')


def fetch(url: str) -> str:
	request = urllib.request.Request(url, headers={"User-Agent": "chessmart-tools/1.0"})
	with urllib.request.urlopen(request, timeout=60) as response:
		return response.read().decode("utf-8")


def main() -> int:
	checksums = {}
	for line in fetch(MIRROR + "sha256").splitlines():
		digest, _, name = line.strip().partition("  ")
		if name:
			checksums[name] = digest
	files = []
	for kind, folder in FOLDERS.items():
		for match in LISTING_LINE.finditer(fetch(f"{MIRROR}{folder}/")):
			name = match.group("name")
			if name not in checksums:
				print(f"missing sha256: {name}", file=sys.stderr)
				return 1
			files.append(
				{
					"file": name,
					"kind": kind,
					"pieces": len(Path(name).stem.replace("v", "")),
					"bytes": int(match.group("bytes")),
					"sha256": checksums[name],
					"url": f"{MIRROR}{folder}/{name}",
				},
			)
	files.sort(key=lambda f: (f["pieces"], f["file"]))
	manifest = {
		"source": MIRROR,
		"description": "Syzygy endgame tablebases, 3 to 5 pieces, WDL and DTZ, mirrored by Lichess.",
		"files": files,
	}
	TARGET.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
	total = sum(f["bytes"] for f in files)
	print(f"{TARGET.name}: {len(files)} files, {total / 1e6:.0f} MB")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
