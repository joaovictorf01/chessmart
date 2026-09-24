#!/usr/bin/env python3
"""Checks that a puzzle manifest describes the files it is published with.

The add-on refuses any part whose SHA-256 differs from the manifest, retries it
three times and then gives up. A manifest that does not match its own files
therefore breaks the download for everyone, while looking, from the outside,
like a download that restarts by itself. That is what happened to the light
database in September 2026: the .gz came from one run of `build_puzzles.py` and
the manifest from a later one, so the sizes matched to the byte and the hashes
did not.

Two modes:

    py -3 tools/verify_puzzles.py --local dist/puzzles
    py -3 tools/verify_puzzles.py --release puzzles-latest

`--local` hashes the files next to the manifest: run it right after a build and
before uploading anything. `--release` asks the GitHub API for each published
asset (its size and SHA-256 digest) and compares; with `--download` it fetches
every asset and hashes it here instead of trusting the API. Exit code 0 when
everything matches, 1 when it does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Iterator, NamedTuple

CHUNK = 1 << 20
USER_AGENT = "chessmart-verify"


class Expected(NamedTuple):
	"""One file the manifest names, with the size and hash it claims for it."""

	file: str
	bytes: int
	sha256: str
	what: str


def expected_files(manifest: dict, *, include_databases: bool) -> Iterator[Expected]:
	"""Every downloadable file the manifest names, tier by tier.

	The uncompressed `.db` is only listed with `include_databases`: it is what a
	local build has on disk, never what is published.
	"""
	for tier, info in manifest.get("tiers", {}).items():
		download = info.get("download", {})
		if include_databases:
			yield Expected(info["file"], info["bytes"], info["sha256"], f"{tier} database")
		parts = download.get("parts") or []
		for part in parts:
			yield Expected(part["file"], part["bytes"], part["sha256"], f"{tier} part")
		whole = download.get("file")
		# The whole .gz is only a file of its own when it was not split; otherwise
		# its hash is checked by the add-on over the joined parts, and no asset
		# carries that name.
		if whole and len(parts) == 1 and parts[0]["file"] == whole:
			continue
		if whole and not parts:
			yield Expected(whole, download["bytes"], download["sha256"], f"{tier} archive")


def sha256_of(path: Path) -> tuple[int, str]:
	digest = hashlib.sha256()
	size = 0
	with path.open("rb") as handle:
		for chunk in iter(lambda: handle.read(CHUNK), b""):
			digest.update(chunk)
			size += len(chunk)
	return size, digest.hexdigest()


def sha256_of_url(url: str) -> tuple[int, str]:
	request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
	digest = hashlib.sha256()
	size = 0
	with urllib.request.urlopen(request, timeout=120) as response:
		for chunk in iter(lambda: response.read(CHUNK), b""):
			digest.update(chunk)
			size += len(chunk)
	return size, digest.hexdigest()


def check(expected: Expected, size: int | None, sha256: str | None) -> str | None:
	"""Returns the complaint about this file, or None when it checks out."""
	if size is None:
		return f"{expected.file}: missing ({expected.what})"
	if size != expected.bytes:
		return f"{expected.file}: {size} bytes, the manifest says {expected.bytes}"
	if sha256 is not None and sha256 != expected.sha256:
		return f"{expected.file}: sha256 {sha256}, the manifest says {expected.sha256}"
	return None


def verify_local(directory: Path) -> list[str]:
	manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
	complaints = []
	for expected in expected_files(manifest, include_databases=True):
		path = directory / expected.file
		if not path.is_file():
			complaints.append(check(expected, None, None) or "")
			continue
		size, digest = sha256_of(path)
		if complaint := check(expected, size, digest):
			complaints.append(complaint)
	return complaints


def release_assets(tag: str, repo: str | None) -> dict[str, dict]:
	"""The release's assets by name, read with the GitHub CLI (`gh api`)."""
	where = repo or "{owner}/{repo}"
	result = subprocess.run(
		["gh", "api", f"repos/{where}/releases/tags/{tag}"],
		capture_output=True,
		check=True,
		text=True,
	)
	payload = json.loads(result.stdout)
	return {asset["name"]: asset for asset in payload.get("assets", [])}


def verify_release(tag: str, repo: str | None, *, download: bool) -> list[str]:
	assets = release_assets(tag, repo)
	manifest_asset = assets.get("manifest.json")
	if manifest_asset is None:
		return [f"{tag}: the release has no manifest.json"]
	request = urllib.request.Request(
		manifest_asset["browser_download_url"],
		headers={"User-Agent": USER_AGENT},
	)
	with urllib.request.urlopen(request, timeout=60) as response:
		manifest = json.loads(response.read().decode("utf-8"))
	complaints = []
	for expected in expected_files(manifest, include_databases=False):
		asset = assets.get(expected.file)
		if asset is None:
			complaints.append(check(expected, None, None) or "")
			continue
		if download:
			size, digest = sha256_of_url(asset["browser_download_url"])
		else:
			size = asset["size"]
			digest = (asset.get("digest") or "").removeprefix("sha256:") or None
		if complaint := check(expected, size, digest):
			complaints.append(complaint)
	return complaints


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	source = parser.add_mutually_exclusive_group(required=True)
	source.add_argument(
		"--local",
		type=Path,
		metavar="DIR",
		help="a directory holding manifest.json and its files",
	)
	source.add_argument("--release", metavar="TAG", help="a published release, read through the GitHub CLI")
	parser.add_argument("--repo", help="owner/name, when the release is not in the current repository")
	parser.add_argument(
		"--list",
		action="store_true",
		dest="list_files",
		help="with --local: print the files that should be published, one per line, and check nothing",
	)
	parser.add_argument(
		"--download",
		action="store_true",
		help="with --release: fetch every asset and hash it here instead of trusting the API digest",
	)
	args = parser.parse_args(argv)

	if args.list_files:
		if args.local is None:
			parser.error("--list only makes sense with --local")
		manifest = json.loads((args.local / "manifest.json").read_text(encoding="utf-8"))
		for expected in expected_files(manifest, include_databases=False):
			print(expected.file)
		return 0

	if args.local is not None:
		where = str(args.local)
		complaints = verify_local(args.local)
	else:
		where = args.release
		complaints = verify_release(args.release, args.repo, download=args.download)

	if complaints:
		print(f"{where}: the manifest does not describe these files:", file=sys.stderr)
		for complaint in complaints:
			print(f"  {complaint}", file=sys.stderr)
		return 1
	print(f"{where}: every file the manifest names checks out.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
