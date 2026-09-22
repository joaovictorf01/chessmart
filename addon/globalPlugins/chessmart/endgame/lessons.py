# coding: utf-8
# pyright: basic

"""The endgame trail: lessons with key positions, the question and the rule.

The order and scope follow the curriculum beginner-level endgame books use:
*Silman's Complete Endgame Course* (Parts 1 to 4, up to 1599) and *100
Endgames You Must Know* (De la Villa), with the matching ending number noted
in each lesson. Each position is a theoretical position -- known result and
a named method -- checked against the Syzygy tablebase; the rule is the
sentence the player should carry into their own games.

The method follows the books: before moving, answer "win or draw?" and why;
then play the position out against perfect defence, with the tablebase as
judge, until the result is held. The moves are not original; the explanations are.

No NVDA here: the board and the dialog live outside this package.
"""

from __future__ import annotations

import dataclasses

from ..i18n import N_, _
from ..paths import import_bundled
from . import judge
from .drills import ENDGAME_DRILLS, EndgameDrill, get_endgame_drill

with import_bundled():
	import chess


@dataclasses.dataclass(frozen=True)
class LessonPosition:
	position_id: str
	fen: str
	# Which side the player is on; the other side is the engine.
	player: chess.Color
	# The theoretical result for the player: judge.WIN, judge.DRAW or judge.LOSS.
	expected: str
	title: str
	rule: str
	# Where the topic is in the books; a reference string, not translated.
	source: str

	@property
	def playable(self) -> bool:
		"""A position lost for the player is not played out: the lesson is just the question and the rule."""
		return self.expected != judge.LOSS


@dataclasses.dataclass(frozen=True)
class EndgameLesson:
	lesson_id: str
	label: str
	description: str
	source: str
	positions: tuple[LessonPosition, ...] = ()
	# Lesson 1 is the elementary mates: drills against the engine, no question.
	drill: EndgameDrill | None = None


def _pos(position_id, fen, expected, title, rule, source, player=chess.WHITE):
	return LessonPosition(position_id, fen, player, expected, title, rule, source)


SILMAN = "Silman, Complete Endgame Course"
VILLA = "De la Villa, 100 Endgames You Must Know"
CAPABLANCA = "Capablanca, Chess Fundamentals, ch. 1"

ENDGAME_LESSONS: tuple[EndgameLesson, ...] = (
	EndgameLesson(
		lesson_id="mateQueen",
		# Translators: Name of the first endgame lesson (a drill).
		label=N_("1a. Mate with queen and king"),
		# Translators: Description of the queen mate lesson.
		description=N_(
			"The queen alone cannot mate: drive the king to the edge, bring your own king up, mind the stalemate. Under 10 moves.",
		),
		source=f"{SILMAN}, Part 1 (King and Queen vs. Lone King); {CAPABLANCA}, example 4",
		drill=ENDGAME_DRILLS[0],
	),
	EndgameLesson(
		lesson_id="mateRook",
		# Translators: Name of the second endgame lesson (a drill).
		label=N_("1b. Mate with rook and king"),
		# Translators: Description of the rook mate lesson.
		description=N_(
			"Keep your king on the same rank or file as the other king, next to the rook, and push the king to the edge. Under 20 moves.",
		),
		source=f"{SILMAN}, Part 1 (King and Rook vs. Lone King); {CAPABLANCA}, examples 1 and 2",
		drill=ENDGAME_DRILLS[1],
	),
	EndgameLesson(
		lesson_id="mateTwoRooks",
		# Translators: Name of the endgame lesson (a drill) with two rooks.
		label=N_("1c. Mate with two rooks"),
		# Translators: Description of the two rooks mate lesson.
		description=N_(
			"The ladder mate: the rooks take turns cutting off a rank and checking on the next, until the king runs out of board. Under 10 moves.",
		),
		source=f"{SILMAN}, Part 1 (Two Rooks vs. Lone King)",
		drill=get_endgame_drill("twoRooksVsKing"),
	),
	EndgameLesson(
		lesson_id="mateTwoBishops",
		# Translators: Name of the endgame lesson (a drill) with two bishops.
		label=N_("1d. Mate with two bishops"),
		# Translators: Description of the two bishops mate lesson.
		description=N_(
			"The bishops side by side make a wall the king cannot cross. Push it to the edge, then into a corner, and mate with the king close behind. Under 20 moves.",
		),
		source=f"{SILMAN}, Part 5 (Two Bishops vs. Lone King); {VILLA}, ending 2",
		drill=get_endgame_drill("twoBishopsVsKing"),
	),
	EndgameLesson(
		lesson_id="mateBishopKnight",
		# Translators: Name of the endgame lesson (a drill) with bishop and knight.
		label=N_("1e. Mate with bishop and knight"),
		# Translators: Description of the bishop and knight mate lesson.
		description=N_(
			"The hardest elementary mate: it only exists in the corner of the bishop's colour. Drive the king to the edge, then along the edge to the right corner, knight and bishop taking turns. Under 35 moves.",
		),
		source=f"{SILMAN}, Part 8 (Bishop and Knight vs. Lone King); {VILLA}, ending 3",
		drill=get_endgame_drill("bishopKnightVsKing"),
	),
	EndgameLesson(
		lesson_id="kingAndOpposition",
		# Translators: Name of the endgame lesson on the king and the opposition.
		label=N_("2. The king and the opposition"),
		# Translators: Description of the lesson on the king and the opposition.
		description=N_(
			"With king and pawn against king the king leads, the pawn goes last. The opposition decides who passes, and the rook pawn is the exception that draws.",
		),
		source=f"{SILMAN}, Part 2 (Use Your King!, Opposition, Rook-Pawns); {VILLA}, endings 1, 4 and 5",
		positions=(
			_pos(
				"kingFirst",
				"8/4k3/8/8/8/8/4PK2/8 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The king leads"),
				# Translators: Rule taught by a lesson position.
				N_(
					"King and pawn against king: the king goes in front of the pawn, and the pawn moves last. Run the king up before touching the pawn.",
				),
				f"{SILMAN}, Part 2, Use Your King!",
			),
			_pos(
				"oppositionWhiteToMove",
				"8/8/8/4k3/8/4K3/4P3/8 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Opposition: the side to move loses it"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Kings face to face with one square between them: that is the opposition, and whoever has to move loses it. White to move here cannot get past: draw.",
				),
				f"{SILMAN}, Part 2, Opposition",
			),
			_pos(
				"oppositionBlackToMove",
				"8/8/8/4k3/8/4K3/4P3/8 b - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The same position, Black to move"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Same pieces, other side to move: now Black must step aside and White has the opposition. The king walks through, and only then the pawn advances.",
				),
				f"{SILMAN}, Part 2, Opposition",
			),
			_pos(
				"rookPawnCorner",
				"7k/8/7K/7P/8/8/8/8 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Rook pawn: the corner draws"),
				# Translators: Rule taught by a lesson position.
				N_(
					"A rook pawn is the exception: if the defending king reaches the corner, or the square in front of the pawn, it is a draw. There is no side to go around.",
				),
				f"{SILMAN}, Part 2, Rook-Pawns; {VILLA}, ending 4",
			),
			_pos(
				"rookPawnPrison",
				"7K/5k2/8/8/8/8/7P/8 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Rook pawn: the attacking king is imprisoned"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The attacking king stuck in the corner in front of its own rook pawn cannot get out: the defender only needs to guard f7 and f8. Draw.",
				),
				f"{SILMAN}, Part 2, Rook-Pawns; {VILLA}, ending 5",
			),
			_pos(
				"rookPawnFarKing",
				"8/8/8/8/8/8/P7/K5k1 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Rook pawn: the defender arrives too late"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The rook pawn wins when the defending king reaches neither the corner nor the square of the pawn. Push it: count the squares first.",
				),
				f"{SILMAN}, Part 2, Rook-Pawns",
			),
		),
	),
	EndgameLesson(
		lesson_id="kingAndPawn",
		# Translators: Name of the endgame lesson on king and pawn against king.
		label=N_("3. King and pawn against king"),
		# Translators: Description of the lesson on king and pawn against king.
		description=N_(
			"The rule of the square, the king in front of the pawn, and the pawn on the sixth: what wins, what draws, and why.",
		),
		source=f"{SILMAN}, Part 3 (King and Pawn vs. Lone King); {VILLA}, endings 1 to 3",
		positions=(
			_pos(
				"squareOutside",
				"8/8/8/1P6/6k1/8/8/K7 b - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The rule of the square: outside"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Draw a square from the pawn to its promotion rank. If the defending king, on its move, cannot step into that square, the pawn promotes on its own. The kings do not matter: just count.",
				),
				f"{VILLA}, ending 1; {SILMAN}, Part 4, Entering the Square of the Pawn",
			),
			_pos(
				"squareInside",
				"8/8/8/1P6/5k2/8/8/K7 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("The rule of the square: inside"),
				# Translators: Rule taught by a lesson position.
				N_(
					"One file closer and the king steps into the square: it catches the pawn. Draw. Diagonal steps cost nothing, so the king moves on the diagonal.",
				),
				f"{VILLA}, ending 1",
			),
			_pos(
				"kingTwoSquaresInFront",
				"8/8/4k3/8/4K3/8/4P3/8 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("King two squares in front of the pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The king two squares in front of its pawn wins whoever is to move: it takes the opposition, or the pawn's spare move gives it back.",
				),
				f"{SILMAN}, Part 3, Non Rook-Pawn (Two Squares in Front)",
			),
			_pos(
				"kingBehindPawn",
				"8/8/8/8/4k3/8/4P3/4K3 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("King behind the pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"With the king behind its pawn and the defending king in front, the attacking king never gets past. Draw. This is why the king must lead.",
				),
				f"{SILMAN}, Part 3, King and Pawn vs. Lone King",
			),
			_pos(
				"kingOnSixthInFront",
				"4k3/8/4K3/4P3/8/8/8/8 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("King on the sixth in front of the pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The king on the sixth rank in front of its pawn wins whoever is to move. Step to the side, the pawn follows, and the defending king cannot cover both squares.",
				),
				f"{VILLA}, ending 3 (key squares); {SILMAN}, Part 3",
			),
			_pos(
				"pawnOnSixthWhiteToMove",
				"3k4/8/3PK3/8/8/8/8/8 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Pawn on the sixth, king beside it, White to move"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Pawn on the sixth with the king beside it and the move: push the pawn. The defending king cannot hold the promotion square. Win.",
				),
				f"{VILLA}, ending 2",
			),
			_pos(
				"pawnOnSixthBlackToMove",
				"3k4/8/3PK3/8/8/8/8/8 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Pawn on the sixth, king beside it, Black to move"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Without the move it is a draw: Black plays the king in front of the pawn, and after the pawn checks on the seventh the attacking king cannot support it without stalemate. A pawn that checks on the seventh is the sign of a draw.",
				),
				f"{VILLA}, ending 2",
			),
		),
	),
	EndgameLesson(
		lesson_id="pieceVsPawn",
		# Translators: Name of the endgame lesson on a piece against a pawn.
		label=N_("4. A piece against a pawn"),
		# Translators: Description of the lesson on a piece against a pawn.
		description=N_(
			"Rook against pawn is counting; the knight holds a seventh-rank pawn except the rook pawn; the bishop holds from a distance.",
		),
		source=f"{SILMAN}, Part 3 (Minor Piece vs. a Lone Pawn, Rook vs. Lone Pawn); {VILLA}, endings 10, 13 and 21",
		positions=(
			_pos(
				"rookVsPawnCounting",
				"R7/8/8/8/1kp5/8/8/7K w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Rook against pawn: just counting"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Count: how many moves the pawn needs to promote, how many the king needs to arrive. The rook stops the pawn from behind and the king comes: here it arrives in time. Win.",
				),
				f"{VILLA}, ending 21",
			),
			_pos(
				"rookVsPawnTooFar",
				"R7/8/8/8/8/1kp5/8/7K w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Rook against pawn: one step too late"),
				# Translators: Rule taught by a lesson position.
				N_(
					"One more step for the pawn and the count turns: the king does not arrive, and the rook alone must give itself up for the pawn. Draw.",
				),
				f"{VILLA}, ending 21",
			),
			_pos(
				"knightHoldsSeventhPawn",
				"8/8/8/8/8/8/2kp1N2/6K1 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Knight against a pawn on the seventh"),
				# Translators: Rule taught by a lesson position.
				N_(
					"A knight that controls the promotion square holds a seventh-rank pawn on its own: it moves away and comes back, and the pawn cannot pass. Draw.",
				),
				f"{VILLA}, ending 10",
			),
			_pos(
				"knightVsRookPawnSeventh",
				"8/8/8/8/8/8/p1k5/N5K1 b - - 0 1",
				judge.LOSS,
				# Translators: Title of a lesson position.
				N_("Knight against a rook pawn on the seventh"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The exception: against a rook pawn the knight in the corner has no square to come back to, and it falls. Lost for the knight.",
				),
				f"{VILLA}, ending 13",
			),
			_pos(
				"bishopHoldsFromDistance",
				"8/8/8/8/8/2k5/3p4/6KB w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Bishop against a pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"A bishop that reaches the diagonal of the promotion square holds the pawn from any distance. Draw.",
				),
				f"{SILMAN}, Part 3, Bishop vs. Lone Pawn",
			),
		),
	),
	EndgameLesson(
		lesson_id="pawnsBothSides",
		# Translators: Name of the endgame lesson on pawns on both sides.
		label=N_("5. Pawns on both sides"),
		# Translators: Description of the lesson on pawns on both sides.
		description=N_(
			"The spare tempo of doubled pawns, the outside passed pawn that decoys, and pawn against pawn where each king holds one.",
		),
		source=f"{SILMAN}, Part 4 (King and Two Doubled Pawns, Outside Passed Pawns); {VILLA}, endings 77, 90",
		positions=(
			_pos(
				"doubledPawnsWin",
				"8/8/8/4k3/8/4P3/4P3/4K3 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Doubled pawns win"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Two doubled pawns win where one draws: the rear pawn is a spare tempo. When the opposition is against you, move the rear pawn and it is against them.",
				),
				f"{SILMAN}, Part 4, King and Two Doubled Pawns vs. Lone King; {VILLA}, ending 77",
			),
			_pos(
				"outsidePassedPawn",
				"8/8/4k3/5p2/5P2/8/P3K3/8 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The outside passed pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The outside passed pawn does not promote: it decoys. The defending king must go and fetch it, and your king eats on the other side.",
				),
				f"{SILMAN}, Part 4, Outside Passed Pawns; {VILLA}, ending 90",
			),
			_pos(
				"pawnAgainstPawn",
				"8/8/8/8/4k3/8/P4K1p/8 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Pawn against pawn, each king holds one"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Each side has a passed pawn and each king can stop the other's: count the squares and nobody promotes. Draw. Do not run the pawn before counting.",
				),
				f"{SILMAN}, Part 4, Entering the Square of the Pawn",
			),
		),
	),
	EndgameLesson(
		lesson_id="rookAndPawnVsRook",
		# Translators: Name of the endgame lesson on rook and pawn against rook.
		label=N_("6. Rook and pawn against rook"),
		# Translators: Description of the lesson on rook and pawn against rook.
		description=N_(
			"The most common endgame in practice. Philidor draws, a passive rook loses, Lucena wins with the bridge.",
		),
		source=f"{SILMAN}, Part 4 (The Lucena Position, The Philidor Position, Passive Rook); {VILLA}, endings 52 and 53",
		positions=(
			_pos(
				"philidor",
				"4k3/8/r7/8/4PK2/8/8/4R3 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Philidor: the rook on the third rank"),
				# Translators: Rule taught by a lesson position.
				N_(
					"You defend. Keep the rook on your third rank (the sixth from the other side) so the attacking king cannot cross. When the pawn reaches that rank, the rook goes to the last rank and checks from behind. Draw.",
				),
				f"{VILLA}, ending 52; {SILMAN}, Part 4, The Philidor Position",
				player=chess.BLACK,
			),
			_pos(
				"philidorChecksFromBehind",
				"4k3/8/4P3/4K3/8/8/r7/4R3 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Philidor: the checks from behind"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The pawn is on the sixth and the attacking king wants the sixth too: now the rook checks from behind, without stopping. The king has nowhere to hide from the checks. Draw.",
				),
				f"{VILLA}, ending 52",
				player=chess.BLACK,
			),
			_pos(
				"passiveRookLoses",
				"3k4/r7/8/3PK3/8/8/8/4R3 b - - 0 1",
				judge.LOSS,
				# Translators: Title of a lesson position.
				N_("The passive rook loses"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The rook on the seventh instead of the third rank, and the king in front of the pawn: the attacking king reaches the sixth and it is lost. Without the third rank there is no Philidor.",
				),
				f"{SILMAN}, Part 4, Passive Rook",
				player=chess.BLACK,
			),
			_pos(
				"lucena",
				"1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Lucena: the bridge"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Pawn on the seventh, your king in front of it, the defending king cut off by your rook. The bridge: rook to the fourth rank, the king steps out, and when the checks come the rook blocks them. Win.",
				),
				f"{VILLA}, ending 53; {SILMAN}, Part 4, The Lucena Position",
			),
		),
	),
	EndgameLesson(
		lesson_id="queenVsPawn",
		# Translators: Name of the endgame lesson on queen against pawn.
		label=N_("7. Queen against a pawn on the seventh"),
		# Translators: Description of the lesson on queen against pawn.
		description=N_(
			"Central and knight pawns lose to the queen; bishop and rook pawns draw by stalemate when the attacking king is far.",
		),
		source=f"{SILMAN}, Part 4 (Queen vs. King and Pawn); {VILLA}, endings 16 to 18",
		positions=(
			_pos(
				"queenVsCentralPawn",
				"7Q/8/8/8/8/8/3pk3/7K w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Queen against a central pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Checks force the defending king in front of its pawn; each time it stands there, your king gains a step. Repeat until your king arrives, then take the pawn. Win.",
				),
				f"{VILLA}, ending 16",
			),
			_pos(
				"queenVsKnightPawn",
				"6Q1/8/8/8/8/8/1pk5/7K w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Queen against a knight pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The knight pawn loses the same way: the king in front of the pawn gives your king a step each time. Win.",
				),
				f"{VILLA}, ending 16",
			),
			_pos(
				"queenVsBishopPawn",
				"7Q/8/8/8/8/8/2pk4/7K w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Queen against a bishop pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The bishop pawn draws: when the queen forces the king in front, it goes to the corner instead, and taking the pawn is stalemate. Draw while your king is far.",
				),
				f"{VILLA}, ending 18",
			),
			_pos(
				"queenVsRookPawn",
				"6Q1/8/8/8/8/8/pk6/7K w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Queen against a rook pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The rook pawn draws: the king hides in the corner in front of it and there is no check that does not stalemate. Draw while your king is far.",
				),
				f"{VILLA}, ending 17",
			),
		),
	),
	EndgameLesson(
		lesson_id="bishopAndRookPawn",
		# Translators: Name of the endgame lesson on bishop and rook pawn.
		label=N_("8. Bishop and rook pawn"),
		# Translators: Description of the lesson on bishop and rook pawn.
		description=N_(
			"The wrong bishop cannot win: it does not control the promotion square, and the king in the corner never leaves.",
		),
		source=f"{SILMAN}, Part 4 (Bishop and Wrong Colored Rook-Pawn vs. Lone King)",
		positions=(
			_pos(
				"wrongBishop",
				"7k/8/8/8/8/8/7P/3B3K w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("The wrong bishop"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The bishop does not control the promotion square and the defending king sits in the corner: nothing can push it out. Draw. Check the color of the corner before trading down.",
				),
				f"{SILMAN}, Part 4, Bishop and Wrong Colored Rook-Pawn vs. Lone King",
			),
			_pos(
				"rightBishop",
				"7k/8/8/8/8/8/7P/2B4K w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The right bishop"),
				# Translators: Rule taught by a lesson position.
				N_(
					"The bishop controls the promotion square: it takes the corner from the king, and the pawn promotes. Win.",
				),
				f"{SILMAN}, Part 4",
			),
		),
	),
	EndgameLesson(
		lesson_id="rookEndingsPractical",
		# Translators: Name of the endgame lesson on practical rook endings.
		label=N_("9. Rook endings: the ones that decide games"),
		# Translators: Description of the lesson on practical rook endings.
		description=N_(
			"Beyond Philidor and Lucena: the short side, Vancura against the rook pawn, the back-rank defence, the rule of five, and the rook behind the passed pawn. Four of them come in pairs, the right way and the wrong way.",
		),
		source=f"{SILMAN}, Parts 5 to 7 (Rook Endgames); {VILLA}, endings 53 to 66",
		positions=(
			_pos(
				"shortSideRight",
				"4K3/4P1k1/8/8/8/8/r7/5R2 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("The short side: king on the short side, rook on the long side"),
				# Translators: Rule taught by a lesson position.
				N_(
					"You defend, and the pawn is already on the seventh. Your king stays on the short side of the pawn, so the rook has the long side to check from: three files of distance or more, and the checks never run out. Draw.",
				),
				f"{VILLA}, ending 61; {SILMAN}, Part 6, The Short Side Defense",
				player=chess.BLACK,
			),
			_pos(
				"shortSideWrong",
				"4K3/2k1P3/8/8/8/8/7r/3R4 b - - 0 1",
				judge.LOSS,
				# Translators: Title of a lesson position.
				N_("The short side: king on the long side"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Same ending, king on the wrong side. Now the rook checks from the short side, two files away, and the king walks up to it: the checks run out and the pawn promotes. Lost.",
				),
				f"{VILLA}, ending 61; {SILMAN}, Part 6, The Short Side Defense",
				player=chess.BLACK,
			),
			_pos(
				"vancura",
				"R7/6k1/P4r2/8/2K5/8/8/8 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Vancura: the rook attacks the rook pawn from the side"),
				# Translators: Rule taught by a lesson position.
				N_(
					"You defend against a rook pawn on the sixth with the attacking rook in front of it. Keep your rook on the third rank, hitting the pawn from the side, and check whenever the king comes to protect it: it never finds shelter. Draw.",
				),
				f"{VILLA}, ending 66; {SILMAN}, Part 7, The Vancura Position",
				player=chess.BLACK,
			),
			_pos(
				"vancuraPassive",
				"R7/6k1/P7/8/2K5/8/8/r7 b - - 0 1",
				judge.LOSS,
				# Translators: Title of a lesson position.
				N_("Vancura: the passive rook behind the pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Same ending with your rook behind the pawn. The attacking king walks to b7, the rook leaves a8 with check, and the pawn promotes. Lost: against the rook pawn, behind is the wrong place.",
				),
				f"{VILLA}, ending 66; {SILMAN}, Part 7, The Vancura Position",
				player=chess.BLACK,
			),
			_pos(
				"backRankDefence",
				"1r4k1/R7/5KP1/8/8/8/8/8 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("The back-rank defence against a knight pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"You defend with the king in front of a knight pawn on the sixth and the rook on the back rank. Just wait: the rook shuffles along the back rank, the king cannot be driven out, and there is no mate. Draw. It only works against a rook pawn or a knight pawn.",
				),
				f"{VILLA}, ending 58; {SILMAN}, Part 5, Rook and Knight Pawn",
				player=chess.BLACK,
			),
			_pos(
				"ruleOfFiveWin",
				"3r4/8/8/6k1/3P4/3K4/8/5R2 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("The rule of five: pawn on the fourth, king cut off by two files"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Add the pawn's rank to the number of files between the defending king and the pawn. Four plus two is six, more than five: the king cannot get back in time. Advance the king ahead of the pawn and win.",
				),
				f"{SILMAN}, Part 6, The Rule of Five",
			),
			_pos(
				"ruleOfFiveDraw",
				"3r4/8/8/6k1/8/3P4/3K4/5R2 w - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("The rule of five: pawn on the third"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Same cut, pawn one rank back. Three plus two is five, not more: the defending king gets back to the pawn's file in time. Draw. Do not force it; keep the pieces active.",
				),
				f"{SILMAN}, Part 6, The Rule of Five",
			),
			_pos(
				"rookBehindPassedPawn",
				"r7/5k2/8/P7/4K3/8/8/R7 w - - 0 1",
				judge.WIN,
				# Translators: Title of a lesson position.
				N_("Tarrasch: the rook behind the passed pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"Your rook stands behind your passed pawn, theirs stands in front of it and is tied to it. Every pawn step gains your rook a rank and costs theirs one. Bring the king to the pawn and win.",
				),
				f"{VILLA}, ending 64; {SILMAN}, Part 6, Rooks Belong Behind Passed Pawns",
			),
			_pos(
				"rookInFrontOfPawn",
				"R7/6k1/P7/8/8/8/6K1/r7 b - - 0 1",
				judge.DRAW,
				# Translators: Title of a lesson position.
				N_("Tarrasch: the rook in front of its own pawn"),
				# Translators: Rule taught by a lesson position.
				N_(
					"You defend, and their rook is in front of its own rook pawn: it cannot leave a8 without losing the pawn. Keep your rook behind the pawn and your king on g7 and h7, and check the king whenever it comes near. Draw as long as the king stays away.",
				),
				f"{VILLA}, ending 64; {SILMAN}, Part 6, Rooks Belong Behind Passed Pawns",
				player=chess.BLACK,
			),
		),
	),
)


def get_lesson(lesson_id: str | None) -> EndgameLesson:
	for lesson in ENDGAME_LESSONS:
		if lesson.lesson_id == lesson_id:
			return lesson
	return ENDGAME_LESSONS[0]


def lesson_label(lesson: EndgameLesson) -> str:
	return _(lesson.label)


def lesson_description(lesson: EndgameLesson) -> str:
	return _(lesson.description)


def position_title(position: LessonPosition) -> str:
	return _(position.title)


def position_rule(position: LessonPosition) -> str:
	return _(position.rule)


def all_positions() -> tuple[tuple[EndgameLesson, LessonPosition], ...]:
	return tuple((lesson, position) for lesson in ENDGAME_LESSONS for position in lesson.positions)


def play_goal(position: LessonPosition) -> str:
	"""What to do after the question: win it, or hold the draw."""
	if position.expected == judge.WIN:
		# Translators: Instruction after the question in a lesson: the position is won.
		return _("Now win it: play the position out against the engine.")
	if position.expected == judge.DRAW:
		# Translators: Instruction after the question in a lesson: the position is a draw.
		return _("Now hold the draw: play the position out against the engine.")
	# Translators: Instruction after the question in a lesson: the position is lost, nothing to play.
	return _("This one is lost with best play; there is nothing to play out. Control+N goes on.")
