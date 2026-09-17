# coding: utf-8
"""Notação falada dos lances e das casas.

O modelo é o modo cego do Lichess (`ui/nvui`), que deixa escolher como um
lance é lido: SAN cru, UCI, ou o SAN "por extenso", com a coluna dita como
letra, no alfabeto da OTAN ou nos nomes da notação anna (anna, bella, cesar...),
que é a que os jogadores cegos usam à mesa. Aqui só a FALA muda; a entrada
de lances continua a mesma.

`descriptive` é o jeito que o chessmart sempre falou ("white knight from g1
to f3") e fica como padrão; os outros vêm do `render_san`, portado do Lichess.
"""

from __future__ import annotations

from .i18n import _

DESCRIPTIVE = "descriptive"
SAN = "san"
UCI = "uci"
LITERATE = "literate"
NATO = "nato"
ANNA = "anna"

# Ordem da lista de escolha; a primeira é o padrão.
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
	# Função, e não constante, para a tradução ser resolvida na hora de falar.
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
	"""A coluna (a-h) como ela é dita no estilo: letra, OTAN ou anna."""
	if style == NATO:
		return NATO_FILES.get(file_letter, file_letter)
	if style == ANNA:
		return ANNA_FILES.get(file_letter, file_letter)
	return file_letter


def render_square(square_name: str, style: str) -> str:
	"""Uma casa ("f3") dita no estilo. Nos estilos de letra fica como está."""
	if style in (NATO, ANNA) and len(square_name) == 2:
		return f"{render_file(square_name[0], style)} {square_name[1]}"
	return square_name


def render_san(san: str, uci: str, style: str) -> str:
	"""Um lance dito no estilo, a partir do SAN e do UCI dele.

	Porte de `renderSan` do Lichess (ui/nvui/src/nvui.ts): roque vira
	"short/long castling"; `san` e `uci` vão crus (sem o `+`/`#`, que é
	dito por extenso no fim); os demais soletram o SAN trocando a letra da
	peça pelo nome, `x` por "takes", `=` por "promotion", `@` por "at", e a
	coluna pela forma do estilo.
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
