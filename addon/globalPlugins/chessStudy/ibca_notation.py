# coding: utf-8
# pyright: basic


from .paths import import_bundled

with import_bundled():
	import chess


# German colour names, transliterated like the pieces below; the IBCA words
# are never translated. White used to be "schwarts", which is black.
IBCA_COLOR_NAMES = {chess.WHITE: "weiss", chess.BLACK: "schwarz"}

IBCA_FILE_NAMES = {
	"a": "Anna",
	"b": "Belia",
	"c": "Ceasar",
	"d": "David",
	"e": "Eva",
	"f": "Felix",
	"g": "Gustav",
	"h": "Hector",
}
IBCA_FILE_MAP = dict(enumerate(IBCA_FILE_NAMES.values()))

IBCA_RANK_NAMES = [
	"eyns",
	"tsvey ",
	"dry",
	"feer",
	"fuhnf",
	"zex",
	"Zeebin",
	"akt",
]
IBCA_RANK_MAP = dict(enumerate(IBCA_RANK_NAMES))

IBCA_PIECE_NAMES = {
	chess.KING: "Koenig",
	chess.QUEEN: "Dame",
	chess.BISHOP: "Laeufer",
	chess.KNIGHT: "Springer",
	chess.ROOK: "Turm",
	chess.PAWN: "Bauer",
}


IBCA_KING_SIDE_CASTLING = "Kurtze Rochade"
IBCA_QUEEN_SIDE_CASTLING = "Lange Rochade"
