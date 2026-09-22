#!/usr/bin/env python3
"""Extract, update and compile the add-on's translations, without GNU gettext.

    py -3 tools/i18n.py extract            # generates chessmart.pot at the repo root
    py -3 tools/i18n.py update [pt_BR]     # creates/updates addon/locale/<lang>/LC_MESSAGES/nvda.po
    py -3 tools/i18n.py compile            # generates the .mo files next to each .po
    py -3 tools/i18n.py check              # checks placeholders and untranslated strings

Extraction is AST-based: every `_("...")`, `N_("...")`, `ngettext(...)` and
`pgettext(...)` call in the add-on sources, with the `# Translators:` comment
directly above it, if any. `N_` only marks the literal (translated later via
`_()` on the constant); for the catalog, it's a message like any other.
Requires the `polib` package (pip install polib).
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import re
import sys
from pathlib import Path

try:
	import polib
except ImportError:  # pragma: no cover
	raise SystemExit("Precisa do pacote polib: py -3 -m pip install polib")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import buildVars  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ADDON = REPO / "addon"
PLUGIN = ADDON / "globalPlugins" / "chessmart"
LOCALE = ADDON / "locale"
# At the repo root, like the template's `scons pot`; inside addon/ it would end up in the package.
POT = REPO / "chessmart.pot"
SKIP_DIRS = {"lib", "__pycache__", "bin", "sounds"}
PLACEHOLDER = re.compile(r"\{[^{}]*\}|%\([^)]+\)[sd]|%[sd]")


def source_files():
	files = [REPO / "buildVars.py"]
	for path in sorted(PLUGIN.rglob("*.py")):
		if any(part in SKIP_DIRS for part in path.relative_to(PLUGIN).parts):
			continue
		files.append(path)
	return files


class Extractor(ast.NodeVisitor):
	def __init__(self, path: Path, lines: list[str], catalog: dict):
		self.path = path
		self.lines = lines
		self.catalog = catalog

	def _comment_above(self, lineno: int) -> str:
		comments = []
		line = lineno - 1
		while line >= 1:
			text = self.lines[line - 1].strip()
			if text.startswith("#"):
				comments.insert(0, text.lstrip("#").strip())
				line -= 1
			elif text == "" or text.endswith(("(", "[", ",")) or text.startswith(("_(", "(")):
				# skip structural lines between the comment and the literal
				line -= 1
				if len(comments) or line < lineno - 4:
					break
			else:
				break
		translator = [c for c in comments if c.startswith("Translators:")]
		return " ".join(c[len("Translators:") :].strip() for c in translator)

	def visit_Call(self, node: ast.Call):
		name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
		if (
			name in ("_", "N_", "gettext")
			and node.args
			and isinstance(node.args[0], ast.Constant)
			and isinstance(node.args[0].value, str)
		):
			self._add(node.args[0].value, None, None, node)
		elif (
			name == "ngettext"
			and len(node.args) >= 2
			and all(isinstance(a, ast.Constant) for a in node.args[:2])
		):
			self._add(node.args[0].value, node.args[1].value, None, node)
		elif (
			name == "pgettext"
			and len(node.args) >= 2
			and all(isinstance(a, ast.Constant) for a in node.args[:2])
		):
			self._add(node.args[1].value, None, node.args[0].value, node)
		self.generic_visit(node)

	def _add(self, msgid, plural, context, node):
		key = (context, msgid)
		entry = self.catalog.setdefault(key, {"plural": plural, "comments": [], "occurrences": []})
		comment = self._comment_above(node.lineno)
		if comment and comment not in entry["comments"]:
			entry["comments"].append(comment)
		rel = self.path.relative_to(REPO).as_posix()
		entry["occurrences"].append((rel, node.lineno))


def extract() -> polib.POFile:
	catalog: dict = {}
	for path in source_files():
		source = path.read_text(encoding="utf-8")
		tree = ast.parse(source)
		Extractor(path, source.splitlines(), catalog).visit(tree)
	pot = polib.POFile()
	info = buildVars.addon_info
	pot.metadata = {
		"Project-Id-Version": f"{info['addon_name']} {info['addon_version']}",
		"Report-Msgid-Bugs-To": info.get("addon_url", ""),
		"POT-Creation-Date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M%z"),
		"MIME-Version": "1.0",
		"Content-Type": "text/plain; charset=UTF-8",
		"Content-Transfer-Encoding": "8bit",
	}
	for (context, msgid), data in sorted(
		catalog.items(),
		key=lambda item: (item[0][1].casefold(), item[0][0] or ""),
	):
		entry = polib.POEntry(
			msgid=msgid,
			msgctxt=context,
			msgid_plural=data["plural"] or "",
			msgstr="" if not data["plural"] else None,
			msgstr_plural={0: "", 1: ""} if data["plural"] else {},
			comment=" ".join(data["comments"]),
			occurrences=data["occurrences"],
		)
		pot.append(entry)
	LOCALE.mkdir(parents=True, exist_ok=True)
	pot.save(str(POT))
	print(f"{POT.relative_to(REPO)}: {len(pot)} mensagens")
	return pot


def update(languages: list[str]) -> None:
	pot = extract()
	for lang in languages or [d.name for d in LOCALE.iterdir() if d.is_dir()]:
		po_path = LOCALE / lang / "LC_MESSAGES" / "nvda.po"
		po_path.parent.mkdir(parents=True, exist_ok=True)
		if po_path.is_file():
			po = polib.pofile(str(po_path))
		else:
			po = polib.POFile()
			po.metadata = {**pot.metadata, "Language": lang, "Plural-Forms": "nplurals=2; plural=(n > 1);"}
		po.merge(pot)
		po.save(str(po_path))
		untranslated = len(po.untranslated_entries())
		fuzzy = len(po.fuzzy_entries())
		print(f"{po_path.relative_to(REPO)}: {len(po)} mensagens, {untranslated} sem tradução, {fuzzy} fuzzy")


def compile_all() -> int:
	count = 0
	for po_path in LOCALE.glob("*/LC_MESSAGES/nvda.po"):
		po = polib.pofile(str(po_path))
		mo_path = po_path.with_suffix(".mo")
		po.save_as_mofile(str(mo_path))
		print(f"{mo_path.relative_to(REPO)}: {len(po.translated_entries())} traduzidas")
		count += 1
	return count


def check() -> int:
	problems = 0
	for po_path in LOCALE.glob("*/LC_MESSAGES/nvda.po"):
		po = polib.pofile(str(po_path))
		for entry in po:
			if entry.obsolete:
				continue
			if not entry.translated():
				print(f"{po_path.parent.parent.name}: sem tradução: {entry.msgid!r}")
				problems += 1
				continue
			targets = [entry.msgstr] if entry.msgstr else list(entry.msgstr_plural.values())
			expected = set(PLACEHOLDER.findall(entry.msgid))
			for target in targets:
				got = set(PLACEHOLDER.findall(target))
				if got != expected:
					print(
						f"{po_path.parent.parent.name}: placeholders diferentes em {entry.msgid!r}: {sorted(expected)} -> {sorted(got)}",
					)
					problems += 1
			if "&" in entry.msgid and "&" not in entry.msgstr:
				print(f"{po_path.parent.parent.name}: atalho (&) perdido em {entry.msgid!r}")
				problems += 1
	print("sem problemas" if not problems else f"{problems} problema(s)")
	return problems


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("extract")
	up = sub.add_parser("update")
	up.add_argument("languages", nargs="*")
	sub.add_parser("compile")
	sub.add_parser("check")
	args = parser.parse_args(argv)
	if args.command == "extract":
		extract()
	elif args.command == "update":
		update(args.languages)
	elif args.command == "compile":
		compile_all()
	elif args.command == "check":
		return 1 if check() else 0
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
