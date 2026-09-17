# coding: utf-8

"""Nome e descrição de cada tema de puzzle do Lichess, traduzíveis.

Os slugs vêm da base de puzzles (`mateIn1`, `attackingF2F7`, `superGM`...).
Quebrar o slug por maiúscula, como se fazia antes, dava "Mate In1", "Attacking
F2 F7" e "Super G M": nem inglês nem português. Aqui cada slug tem um nome que
uma pessoa diria e uma frase que explica o motivo tático, e os dois passam pela
tradução.

Os textos são nossos; a licença do Lichess (AGPL) não permitiria copiar os dele
para um projeto GPLv2.

Um slug que não estiver aqui (tema novo no Lichess) cai em `humanize_theme_slug`,
para o add-on não quebrar; o nome sai feio, mas sai.
"""

from __future__ import annotations

import re

from .i18n import N_, _

_CAMEL_CASE_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")

# slug -> (nome, descrição). Os nomes aparecem em listas e resumos; as
# descrições, na dica do puzzle e no seletor de temas.
THEME_TEXTS: dict[str, tuple[str, str]] = {
	# Translators: Name of a puzzle theme.
	"advancedPawn": (N_("Advanced pawn"), N_("A pawn deep in enemy territory, often about to promote.")),
	# Translators: Name of a puzzle theme.
	"advantage": (
		N_("Decisive advantage"),
		N_("The solution wins a clear advantage, worth roughly two to four pawns."),
	),
	# Translators: Name of a puzzle theme.
	"anastasiaMate": (
		N_("Anastasia's mate"),
		N_(
			"A knight and a rook or queen trap the king between the edge of the board and one of its own pieces."
		),
	),
	# Translators: Name of a puzzle theme.
	"arabianMate": (N_("Arabian mate"), N_("A knight and a rook combine to mate the king in a corner.")),
	# Translators: Name of a puzzle theme.
	"attackingF2F7": (
		N_("Attack on f2 or f7"),
		N_("An attack on the weak pawn in front of the uncastled king, as in the fried liver attack."),
	),
	# Translators: Name of a puzzle theme.
	"attraction": (
		N_("Attraction"),
		N_(
			"A sacrifice or exchange lures an enemy piece, often the king, onto a square where it can be hit."
		),
	),
	# Translators: Name of a puzzle theme.
	"backRankMate": (
		N_("Back rank mate"),
		N_("The king is mated on its home rank, trapped by its own pieces."),
	),
	# Translators: Name of a puzzle theme.
	"balestraMate": (N_("Balestra mate"), N_("A queen and a bishop mate the king on the edge of the board.")),
	# Translators: Name of a puzzle theme.
	"bishopEndgame": (N_("Bishop endgame"), N_("An endgame with only bishops and pawns.")),
	# Translators: Name of a puzzle theme.
	"blindSwineMate": (N_("Blind swine mate"), N_("Two rooks on the seventh rank mate the castled king.")),
	# Translators: Name of a puzzle theme.
	"bodenMate": (
		N_("Boden's mate"),
		N_("Two bishops on crossing diagonals mate a king blocked by its own pieces."),
	),
	# Translators: Name of a puzzle theme.
	"capturingDefender": (
		N_("Capturing the defender"),
		N_("Remove the piece that protects another, then take what it was guarding."),
	),
	# Translators: Name of a puzzle theme.
	"castling": (N_("Castling"), N_("Bring the king to safety and the rook into play.")),
	# Translators: Name of a puzzle theme.
	"clearance": (
		N_("Clearance"),
		N_("A move, often with tempo, that clears a square, file or diagonal for the follow-up idea."),
	),
	# Translators: Name of a puzzle theme.
	"collinearMove": (
		N_("Collinear move"),
		N_("The winning move slides along the same line as the opponent's last move."),
	),
	# Translators: Name of a puzzle theme.
	"cornerMate": (N_("Corner mate"), N_("A knight, helped by a rook, mates the king in the corner.")),
	# Translators: Name of a puzzle theme.
	"crushing": (
		N_("Crushing"),
		N_("Spot the blunder and win overwhelming material, six pawns' worth or more."),
	),
	# Translators: Name of a puzzle theme.
	"defensiveMove": (N_("Defensive move"), N_("A precise move needed to avoid losing material or worse.")),
	# Translators: Name of a puzzle theme.
	"deflection": (
		N_("Deflection"),
		N_("Drag an enemy piece away from a duty it performs, such as guarding a key square."),
	),
	# Translators: Name of a puzzle theme.
	"discoveredAttack": (
		N_("Discovered attack"),
		N_("Move one piece out of the way to unleash an attack from the piece behind it."),
	),
	# Translators: Name of a puzzle theme.
	"discoveredCheck": (
		N_("Discovered check"),
		N_("Move a piece aside to give check with the piece behind it."),
	),
	# Translators: Name of a puzzle theme.
	"doubleBishopMate": (
		N_("Double bishop mate"),
		N_("Two bishops on adjacent diagonals mate a king blocked by its own pieces."),
	),
	# Translators: Name of a puzzle theme.
	"doubleCheck": (N_("Double check"), N_("Two pieces give check at once, so the king has to move.")),
	# Translators: Name of a puzzle theme.
	"dovetailMate": (
		N_("Dovetail mate"),
		N_(
			"A queen next to the king mates it, with the two escape squares behind blocked by its own pieces."
		),
	),
	# Translators: Name of a puzzle theme.
	"endgame": (N_("Endgame"), N_("A tactic from the last phase of the game.")),
	# Translators: Name of a puzzle theme.
	"enPassant": (N_("En passant"), N_("The tactic involves capturing a pawn en passant.")),
	# Translators: Name of a puzzle theme.
	"epauletteMate": (
		N_("Epaulette mate"),
		N_(
			"The king's two sideways escape squares are taken by its own pieces, and the queen mates from the front."
		),
	),
	# Translators: Name of a puzzle theme.
	"equality": (
		N_("Equality"),
		N_("Come back from a losing position and secure a draw or a balanced game."),
	),
	# Translators: Name of a puzzle theme.
	"exposedKing": (N_("Exposed king"), N_("A king with few defenders around it, open to attack.")),
	# Translators: Name of a puzzle theme.
	"fork": (N_("Fork"), N_("One piece attacks two enemy pieces at the same time.")),
	# Translators: Name of a puzzle theme.
	"hangingPiece": (N_("Hanging piece"), N_("An undefended or poorly defended piece is free to take.")),
	# Translators: Name of a puzzle theme.
	"hookMate": (
		N_("Hook mate"),
		N_("A rook, a knight and a pawn work together to mate the king, whose escape the pawn cuts off."),
	),
	# Translators: Name of a puzzle theme.
	"interference": (
		N_("Interference"),
		N_("Place a piece between two connected enemy pieces, leaving one or both undefended."),
	),
	# Translators: Name of a puzzle theme.
	"intermezzo": (
		N_("Intermezzo"),
		N_("Instead of the expected move, insert one that poses an immediate threat, then continue."),
	),
	# Translators: Name of a puzzle theme.
	"killBoxMate": (
		N_("Kill box mate"),
		N_("A rook next to the king, supported by the queen, mates it inside a three by three box."),
	),
	# Translators: Name of a puzzle theme.
	"kingsideAttack": (N_("Kingside attack"), N_("An attack on the king after it castled short.")),
	# Translators: Name of a puzzle theme.
	"knightEndgame": (N_("Knight endgame"), N_("An endgame with only knights and pawns.")),
	# Translators: Name of a puzzle theme.
	"long": (N_("Long puzzle"), N_("Three moves to win.")),
	# Translators: Name of a puzzle theme.
	"master": (N_("From master games"), N_("Puzzles taken from games played by titled players.")),
	# Translators: Name of a puzzle theme.
	"masterVsMaster": (
		N_("Master against master"),
		N_("Puzzles taken from games between two titled players."),
	),
	# Translators: Name of a puzzle theme.
	"mate": (N_("Checkmate"), N_("The solution ends in checkmate.")),
	# Translators: Name of a puzzle theme.
	"mateIn1": (N_("Mate in one"), N_("Deliver checkmate in a single move.")),
	# Translators: Name of a puzzle theme.
	"mateIn2": (N_("Mate in two"), N_("Deliver checkmate in two moves.")),
	# Translators: Name of a puzzle theme.
	"mateIn3": (N_("Mate in three"), N_("Deliver checkmate in three moves.")),
	# Translators: Name of a puzzle theme.
	"mateIn4": (N_("Mate in four"), N_("Deliver checkmate in four moves.")),
	# Translators: Name of a puzzle theme.
	"mateIn5": (N_("Mate in five"), N_("Deliver checkmate in five moves.")),
	# Translators: Name of a puzzle theme.
	"middlegame": (N_("Middlegame"), N_("A tactic from the second phase of the game.")),
	# Translators: Name of a puzzle theme.
	"morphysMate": (
		N_("Morphy's mate"),
		N_("A bishop and a rook mate the king in the corner, with a pawn blocking its escape."),
	),
	# Translators: Name of a puzzle theme.
	"oneMove": (N_("One-move puzzle"), N_("The solution is a single move.")),
	# Translators: Name of a puzzle theme.
	"opening": (N_("Opening"), N_("A tactic from the first phase of the game.")),
	# Translators: Name of a puzzle theme.
	"operaMate": (
		N_("Opera mate"),
		N_("A rook and a bishop mate the king on its back rank, one of its own pieces blocking the escape."),
	),
	# Translators: Name of a puzzle theme.
	"pawnEndgame": (N_("Pawn endgame"), N_("An endgame with only kings and pawns.")),
	# Translators: Name of a puzzle theme.
	"pillsburysMate": (
		N_("Pillsbury's mate"),
		N_("A rook on the open g-file and a bishop on the long diagonal mate the king in the corner."),
	),
	# Translators: Name of a puzzle theme.
	"pin": (N_("Pin"), N_("A piece cannot move without exposing a more valuable piece behind it.")),
	# Translators: Name of a puzzle theme.
	"promotion": (N_("Promotion"), N_("Promoting a pawn is part of the tactic.")),
	# Translators: Name of a puzzle theme.
	"queenEndgame": (N_("Queen endgame"), N_("An endgame with only queens and pawns.")),
	# Translators: Name of a puzzle theme.
	"queenRookEndgame": (N_("Queen and rook endgame"), N_("An endgame with queens, rooks and pawns.")),
	# Translators: Name of a puzzle theme.
	"queensideAttack": (N_("Queenside attack"), N_("An attack on the king after it castled long.")),
	# Translators: Name of a puzzle theme.
	"quietMove": (
		N_("Quiet move"),
		N_("A move that neither checks nor captures, but prepares an unavoidable threat."),
	),
	# Translators: Name of a puzzle theme.
	"rookEndgame": (N_("Rook endgame"), N_("An endgame with only rooks and pawns.")),
	# Translators: Name of a puzzle theme.
	"sacrifice": (
		N_("Sacrifice"),
		N_("Give up material to gain a bigger advantage after a forced sequence."),
	),
	# Translators: Name of a puzzle theme.
	"short": (N_("Short puzzle"), N_("Two moves to win.")),
	# Translators: Name of a puzzle theme.
	"skewer": (
		N_("Skewer"),
		N_("A valuable piece is attacked and, when it moves away, the piece behind it is captured."),
	),
	# Translators: Name of a puzzle theme.
	"smotheredMate": (
		N_("Smothered mate"),
		N_("A knight mates the king, which is boxed in by its own pieces."),
	),
	# Translators: Name of a puzzle theme.
	"superGM": (
		N_("From super grandmaster games"),
		N_("Puzzles taken from games of the strongest players in the world."),
	),
	# Translators: Name of a puzzle theme.
	"swallowstailMate": (
		N_("Swallow's tail mate"),
		N_(
			"A queen mates the king, whose two diagonal escape squares behind it are blocked by its own pieces."
		),
	),
	# Translators: Name of a puzzle theme.
	"trappedPiece": (N_("Trapped piece"), N_("A piece with no safe square left to escape capture.")),
	# Translators: Name of a puzzle theme.
	"triangleMate": (
		N_("Triangle mate"),
		N_("A queen and a rook form a triangle around the king to mate it."),
	),
	# Translators: Name of a puzzle theme.
	"underPromotion": (
		N_("Underpromotion"),
		N_("Promote a pawn to a knight, bishop or rook instead of a queen."),
	),
	# Translators: Name of a puzzle theme.
	"veryLong": (N_("Very long puzzle"), N_("Four moves or more to win.")),
	# Translators: Name of a puzzle theme.
	"vukovicMate": (
		N_("Vukovic mate"),
		N_("A rook and a knight, supported by a third piece, mate the king on the edge of the board."),
	),
	# Translators: Name of a puzzle theme.
	"xRayAttack": (N_("X-ray attack"), N_("A piece attacks or defends a square through an enemy piece.")),
	# Translators: Name of a puzzle theme.
	"zugzwang": (N_("Zugzwang"), N_("Every move available to the opponent makes their position worse.")),
}


def humanize_theme_slug(slug: str) -> str:
	"""Reserva para slug desconhecido: quebra por maiúscula e capitaliza ("someNewTheme" -> "Some New Theme")."""
	humanized = _CAMEL_CASE_PATTERN.sub(" ", slug).replace("_", " ").strip()
	return humanized[:1].upper() + humanized[1:] if humanized else slug


def theme_label(slug: str) -> str:
	texts = THEME_TEXTS.get(slug)
	return _(texts[0]) if texts else humanize_theme_slug(slug)


def theme_description(slug: str) -> str:
	texts = THEME_TEXTS.get(slug)
	if texts:
		return _(texts[1])
	# Translators: Description of a puzzle theme the add-on does not know yet. {label} is its name.
	return _("Lichess theme: {label}.").format(label=humanize_theme_slug(slug))
