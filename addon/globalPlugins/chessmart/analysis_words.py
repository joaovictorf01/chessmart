# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""How the analysis board says marks, evaluations and verdicts.

Free of NVDA imports so the sentences can be tested: "white slightly better,
plus 0.4", "black mates in 3", "dubious move".
"""

from .engine_eval import Advantage, Assessment, MoveVerdict
from .game_clock import TIME_TROUBLE_SECONDS, ClockSummary, format_clock
from .game_tree import MOVE_MARK_SYMBOLS
from .i18n import _, ngettext
from .paths import import_bundled
from .spoken_messages import spoken_color_name


with import_bundled():
	import chess
	import chess.pgn


# Control+1 to Control+6, in the order PGN numbers the marks.
MARK_KEYS = tuple(MOVE_MARK_SYMBOLS)


def spoken_mark(nag):
	"""The mark as words: a screen reader says "!?" badly, and the words are what the mark means."""
	return {
		# Translators: Spoken name of the "!" mark on a move.
		chess.pgn.NAG_GOOD_MOVE: _("good move"),
		# Translators: Spoken name of the "?" mark on a move.
		chess.pgn.NAG_MISTAKE: _("mistake"),
		# Translators: Spoken name of the "!!" mark on a move.
		chess.pgn.NAG_BRILLIANT_MOVE: _("brilliant move"),
		# Translators: Spoken name of the "??" mark on a move.
		chess.pgn.NAG_BLUNDER: _("blunder"),
		# Translators: Spoken name of the "!?" mark on a move.
		chess.pgn.NAG_SPECULATIVE_MOVE: _("interesting move"),
		# Translators: Spoken name of the "?!" mark on a move.
		chess.pgn.NAG_DUBIOUS_MOVE: _("dubious move"),
	}[nag]


def spoken_pawns(centipawns):
	"""+0.4 / -1.3 said with the decimal separator of the user's language."""
	tenths = round(abs(centipawns) / 10)
	whole, tenth = divmod(tenths, 10)
	# Translators: A number of pawns with one decimal, e.g. "0.4"; use your language's decimal separator.
	number = _("{whole}.{tenth}").format(whole=whole, tenth=tenth)
	if tenths == 0:
		return number
	if centipawns > 0:
		# Translators: An evaluation in favour of White, e.g. "plus 0.4".
		return _("plus {number}").format(number=number)
	# Translators: An evaluation in favour of Black, e.g. "minus 1.3".
	return _("minus {number}").format(number=number)


def spoken_assessment(assessment: Assessment) -> str:
	"""The evaluation in words: who is better and by how much."""
	if assessment.mate is not None:
		color = spoken_color_name(chess.WHITE if assessment.mate > 0 else chess.BLACK)
		moves = abs(assessment.mate)
		# Translators: Engine evaluation: a forced mate, e.g. "white mates in 3".
		return ngettext("{color} mates in {moves}", "{color} mates in {moves}", moves).format(
			color=color,
			moves=moves,
		)
	side = assessment.side_ahead
	pawns = spoken_pawns(assessment.centipawns)
	if side is None:
		# Translators: Engine evaluation of a level position, followed by the number, e.g. "equal, plus 0.1".
		return _("equal, {pawns}").format(pawns=pawns)
	color = spoken_color_name(side)
	return {
		# Translators: Engine evaluation, e.g. "white slightly better, plus 0.5".
		Advantage.SLIGHT: _("{color} slightly better, {pawns}"),
		# Translators: Engine evaluation, e.g. "black clearly better, minus 1.4".
		Advantage.CLEAR: _("{color} clearly better, {pawns}"),
		# Translators: Engine evaluation, e.g. "white winning, plus 4.2".
		Advantage.WINNING: _("{color} winning, {pawns}"),
	}[assessment.advantage].format(color=color, pawns=pawns)


def spoken_verdict(verdict: MoveVerdict) -> str:
	return {
		# Translators: Engine verdict on a move: the engine's own choice.
		MoveVerdict.BEST: _("the engine's move"),
		# Translators: Engine verdict on a move: not the best, but loses almost nothing.
		MoveVerdict.GOOD: _("good, almost nothing lost"),
		# Translators: Engine verdict on a move (?!).
		MoveVerdict.INACCURACY: _("inaccuracy"),
		# Translators: Engine verdict on a move (?).
		MoveVerdict.MISTAKE: _("mistake"),
		# Translators: Engine verdict on a move (??).
		MoveVerdict.BLUNDER: _("blunder"),
	}[verdict]


def spoken_move_clock(left: float, spent: "float | None") -> str:
	"""After a move of an imported game: the clock left, the time the move took, and time trouble."""
	# Whole sentences for each case, never a piece glued on: word order changes with the language.
	trouble = left < TIME_TROUBLE_SECONDS
	if spent is None and trouble:
		# Translators: The clock after a move, under a minute, e.g. "clock 0:48, under a minute".
		text = _("clock {left}, under a minute")
	elif spent is None:
		# Translators: The clock after a move, e.g. "clock 14:52".
		text = _("clock {left}")
	elif trouble:
		# Translators: The clock after a move, the time it took, under a minute, e.g. "clock 0:48, took 0:12, under a minute".
		text = _("clock {left}, took {spent}, under a minute")
	else:
		# Translators: The clock after a move and the time it took, e.g. "clock 14:52, took 0:25".
		text = _("clock {left}, took {spent}")
	return text.format(left=format_clock(left), spent=format_clock(spent) if spent is not None else "")


def spoken_clock_summary(summary: ClockSummary) -> str:
	"""One side's clock over the game: time trouble, the lowest clock, the longest think."""
	color = spoken_color_name(summary.color)
	if summary.lowest is None:
		# Translators: Clock summary of a side whose moves carry no clock, e.g. "white: no clock".
		return _("{color}: no clock").format(color=color)
	parts = []
	trouble = summary.first_in_time_trouble
	if trouble is None:
		# Translators: Part of the clock summary, e.g. "white: never under a minute".
		parts.append(_("{color}: never under a minute").format(color=color))
	else:
		# Translators: Part of the clock summary, e.g. "black: under a minute from move 34".
		parts.append(
			_("{color}: under a minute from move {move}").format(color=color, move=trouble.move_number)
		)
	# Translators: Part of the clock summary, e.g. "lowest clock 0:41 at move 36".
	parts.append(
		_("lowest clock {clock} at move {move}").format(
			clock=format_clock(summary.lowest.left),
			move=summary.lowest.move_number,
		),
	)
	think = summary.longest_think
	if think is not None and think.spent is not None:
		dots = "." if think.color == chess.WHITE else "..."
		# Translators: Part of the clock summary, e.g. "longest think 5... Qxg5, 3:10".
		parts.append(
			_("longest think {move}, {spent}").format(
				move=f"{think.move_number}{dots} {think.san}",
				spent=format_clock(think.spent),
			),
		)
	return "; ".join(parts) + "."
