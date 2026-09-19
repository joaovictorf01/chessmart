#!/usr/bin/env python3
"""Gera o manifesto das tabelas Syzygy de 3, 4 e 5 peças a partir do espelho do Lichess.

    py -3 tools/build_syzygy_manifest.py

Lê a listagem das pastas `3-4-5-wdl` e `3-4-5-dtz` (nome e tamanho de cada
arquivo) e o arquivo `sha256` do espelho, e escreve
`addon/globalPlugins/chessmart/endgame/syzygy_manifest.json`. O add-on baixa
arquivo por arquivo a partir desse manifesto e confere cada um pelo SHA-256:
a listagem não precisa ser lida em tempo de execução, e o tamanho total é
conhecido antes de começar.
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
				print(f"sem sha256: {name}", file=sys.stderr)
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
	print(f"{TARGET.name}: {len(files)} arquivos, {total / 1e6:.0f} MB")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
