# coding: utf-8
# pyright: basic
"""Spoken notation for moves and squares.

The model is Lichess's blind mode (`ui/nvui`), which lets the player choose
how a move is read aloud: raw SAN, UCI, or SAN "spelled out", with the file
read as a letter, in the NATO alphabet, or in the anna notation names (anna,
bella, cesar...), which is what blind players use over the board. Only the
SPEECH changes here; move input stays the same.

`descriptive` is how chessStudy has always spoken moves ("white knight from g1
to f3") and remains the default; the others come from `render_san`, ported
from Lichess.
"""

from __future__ import annotations

from .i18n import _

DESCRIPTIVE = "descriptive"
SAN = "san"
UCI = "uci"
LITERATE = "literate"
NATO = "nato"
ANNA = "anna"

# Order of the choice list; the first one is the default.
NOTATION_STYLES = (
	# Translators: Move notation style that describes moves in full sentences.
	(DESCRIPTIVE, _("Descriptive: white knight from g1 to f3")),
	# Translators: Move notation style using standard algebraic notation as written.
	(SAN, _("SAN: Nf3")),
	# Translators: Move notation style using origin and destination squares.
	(UCI, _("UCI: g1f3")),
	# Translators: Move notation style that spells the algebraic notation out.
	(LITERATE, _("Literate: knight f 3")),
	# Translators: Move notation style that reads files with the NATO alphabet.
	(NATO, _("NATO: knight foxtrot 3")),
	# Translators: Move notation style that reads files with the names used by blind players (anna, bella, cesar...).
	(ANNA, _("Anna: knight felix 3")),
)
STYLE_IDS = tuple(style for style, _label in NOTATION_STYLES)
DEFAULT_STYLE = DESCRIPTIVE

NATO_FILES = {
	"a": "alpha",
	"b": "bravo",
	"c": "charlie",
	"d": "delta",
	"e": "echo",
	"f": "foxtrot",
	"g": "golf",
	"h": "hotel",
}
ANNA_FILES = {
	"a": "anna",
	"b": "bella",
	"c": "cesar",
	"d": "david",
	"e": "eva",
	"f": "felix",
	"g": "gustav",
	"h": "hector",
}


def _piece_names() -> dict[str, str]:
	# A function, not a constant, so the translation is resolved at speech time.
	return {
		# Translators: Piece name used when reading moves aloud.
		"P": _("pawn"),
		# Translators: Piece name used when reading moves aloud.
		"R": _("rook"),
		# Translators: Piece name used when reading moves aloud.
		"N": _("knight"),
		# Translators: Piece name used when reading moves aloud.
		"B": _("bishop"),
		# Translators: Piece name used when reading moves aloud.
		"Q": _("queen"),
		# Translators: Piece name used when reading moves aloud.
		"K": _("king"),
	}


def render_file(file_letter: str, style: str) -> str:
	"""The file (a-h) as spoken in the given style: letter, NATO or anna."""
	if style == NATO:
		return NATO_FILES.get(file_letter, file_letter)
	if style == ANNA:
		return ANNA_FILES.get(file_letter, file_letter)
	return file_letter


def render_square(square_name: str, style: str) -> str:
	"""A square ("f3") spoken in the given style. In letter styles it stays as-is."""
	if style in (NATO, ANNA) and len(square_name) == 2:
		return f"{render_file(square_name[0], style)} {square_name[1]}"
	return square_name


def render_san(san: str, uci: str, style: str) -> str:
	"""A move spoken in the given style, from its SAN and UCI.

	Port of Lichess's `renderSan` (ui/nvui/src/nvui.ts): castling becomes
	"short/long castling"; `san` and `uci` are used raw (without `+`/`#`, which
	are spoken out at the end); the other styles spell out the SAN, replacing
	the piece letter with its name, `x` with "takes", `=` with "promotion", `@`
	with "at", and the file with the style's form.
	"""
	if not san:
		return ""
	if "O-O-O" in san:
		# Translators: Spoken for queen-side castling.
		move = _("long castling")
	elif "O-O" in san:
		# Translators: Spoken for king-side castling.
		move = _("short castling")
	elif style == SAN:
		move = san.replace("+", "").replace("#", "")
	elif style == UCI:
		move = uci or san
	else:
		pieces = _piece_names()
		words = []
		for char in san.replace("+", "").replace("#", ""):
			if char == "x":
				# Translators: Spoken in place of the capture sign "x" when reading a move.
				words.append(_("takes"))
			elif char == "=":
				# Translators: Spoken in place of the promotion sign "=" when reading a move.
				words.append(_("promotion"))
			elif char == "@":
				# Translators: Spoken in place of the drop sign "@" when reading a move.
				words.append(_("at"))
			elif "1" <= char <= "8":
				words.append(char)
			elif "a" <= char <= "h":
				words.append(render_file(char, style))
			else:
				words.append(pieces.get(char, char))
		move = " ".join(words)
	if "+" in san:
		# Translators: Spoken after a move that gives check.
		move += " " + _("check")
	if "#" in san:
		# Translators: Spoken after a move that gives checkmate.
		move += " " + _("checkmate")
	return move
