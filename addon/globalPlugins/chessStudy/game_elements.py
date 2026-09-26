# coding: utf-8
# pyright: basic

import typing
import dataclasses
from functools import cached_property
import random
from utils.displayString import DisplayStringIntEnum
from .i18n import _
from .paths import import_bundled
from .time_control import NULL_TIME_CONTROL, ChessTimeControl


with import_bundled():
	import chess
	import chess.variant


@dataclasses.dataclass
class GameInfo:
	"""What's known about a game before the chessboard exists.

	`pychess_board`, `variant` and `prospective` are None when the mode decides
	on its own: PGN replay brings the position from the file, and the tactics
	trainer has no side until the puzzle loads.
	"""

	pychess_board: typing.Optional[chess.BaseBoard]
	variant: typing.Optional["ChessVariant"]
	time_control: ChessTimeControl
	prospective: typing.Optional[chess.Color]
	vboard_kwargs: dict = dataclasses.field(default_factory=dict)


class PlayMode(DisplayStringIntEnum):
	HUMAN_VERSUS_COMPUTER = 0
	HUMAN_VERSUS_HUMAN = 1

	@cached_property
	def _displayStringLabels(self):
		return {
			# Translators: Play mode choice in the new game dialog: two people at the same keyboard.
			PlayMode.HUMAN_VERSUS_HUMAN: _("Human versus human"),
			# Translators: Play mode choice in the new game dialog.
			PlayMode.HUMAN_VERSUS_COMPUTER: _("Human versus computer"),
		}

	def get_board_class(self):
		from .virtual_chessboard import (
			UserUserChessboard,
			UserEngineChessboard,
		)

		if self is PlayMode.HUMAN_VERSUS_HUMAN:
			return UserUserChessboard
		return UserEngineChessboard


class TimeControl(DisplayStringIntEnum):
	CLASSICAL = 0
	RAPID_PLAY_1 = 1
	RAPID_PLAY_2 = 2
	BLITZ_1 = 3
	BLITZ_2 = 4
	BULLET_1 = 5
	BULLET_2 = 6
	CUSTOM = 7
	NUL_TIME_CONTROL = 8

	@cached_property
	def _displayStringLabels(self):
		return {
			# Translators: Time control choice: no clock.
			TimeControl.NUL_TIME_CONTROL: _("No Time Control"),
			# Translators: Time control choice: 90 minutes per player, 30 seconds added per move.
			TimeControl.CLASSICAL: _("Classical  (90+30)"),
			# Translators: Time control choice: 15 minutes per player, 10 seconds added per move.
			TimeControl.RAPID_PLAY_1: _("Rapid Play (15+10)"),
			# Translators: Time control choice: 10 minutes per player, 5 seconds added per move.
			TimeControl.RAPID_PLAY_2: _("Rapid Play (10+5)"),
			# Translators: Time control choice: 5 minutes per player, 5 seconds added per move.
			TimeControl.BLITZ_1: _("Blitz (5+5)"),
			# Translators: Time control choice: 3 minutes per player, 2 seconds added per move.
			TimeControl.BLITZ_2: _("Blitz (3+2)"),
			# Translators: Time control choice: 2 minutes per player, 2 seconds added per move.
			TimeControl.BULLET_1: _("Bullet (2+2)"),
			# Translators: Time control choice: 1 minute per player, no increment.
			TimeControl.BULLET_2: _("Bullet (1+0)"),
			# Translators: Time control choice: the user types their own, e.g. 10+5.
			TimeControl.CUSTOM: _("Custom Time Control"),
		}

	def get_time_control(self):
		if self is TimeControl.NUL_TIME_CONTROL:
			return NULL_TIME_CONTROL
		elif self is TimeControl.CLASSICAL:
			return ChessTimeControl.from_time_control_notation("90+30")
		elif self is TimeControl.RAPID_PLAY_1:
			return ChessTimeControl.from_time_control_notation("15+10")
		elif self is TimeControl.RAPID_PLAY_2:
			return ChessTimeControl.from_time_control_notation("10+5")
		elif self is TimeControl.BLITZ_1:
			return ChessTimeControl.from_time_control_notation("5+5")
		elif self is TimeControl.BLITZ_2:
			return ChessTimeControl.from_time_control_notation("3+2")
		elif self is TimeControl.BULLET_1:
			return ChessTimeControl.from_time_control_notation("2+2")
		elif self is TimeControl.BULLET_2:
			return ChessTimeControl.from_time_control_notation("1+0")
		else:
			return None


class ChessVariant(DisplayStringIntEnum):
	STANDARD = 0
	CHESS960 = 1
	ANTICHESS = 4
	ATOMIC = 5
	KINGOFTHEHILL = 6
	RACINGKINGS = 7
	HORDE = 8
	THREECHECK = 9
	CRAZYHOUSE = 10

	def get_board(self):
		if self is ChessVariant.CHESS960:
			return chess.Board
		return chess.variant.find_variant(self.name.lower())

	@property
	def is_drop_moves_supported(self):
		return self in {
			ChessVariant.CRAZYHOUSE,
		}

	@cached_property
	def _displayStringLabels(self):
		return {
			# Translators: Name of the standard chess variant.
			ChessVariant.STANDARD: _("Standard"),
			# Translators: Name of a chess variant (Fischer random chess).
			ChessVariant.CHESS960: _("Chess 960"),
			# Translators: Name of a chess variant (Antichess: whoever loses all pieces wins).
			ChessVariant.ANTICHESS: _("Anti chess"),
			# Translators: Name of a chess variant (captures explode).
			ChessVariant.ATOMIC: _("Atomic"),
			# Translators: Name of a chess variant (bring the king to the centre).
			ChessVariant.KINGOFTHEHILL: _("King of the hill"),
			# Translators: Name of a chess variant (race the king to the eighth rank).
			ChessVariant.RACINGKINGS: _("Racing kings"),
			# Translators: Name of a chess variant (white has a horde of pawns).
			ChessVariant.HORDE: _("Horde"),
			# Translators: Name of a chess variant (three checks win).
			ChessVariant.THREECHECK: _("Three check"),
			# Translators: Name of a chess variant (captured pieces can be dropped back).
			ChessVariant.CRAZYHOUSE: _("Crazy house"),
		}


class PlayerColor(DisplayStringIntEnum):
	RANDOM = 0
	WHITE = 1
	BLACK = 2

	@cached_property
	def _displayStringLabels(self):
		return {
			# Translators: Side choice in the new game dialog: white or black at random.
			PlayerColor.RANDOM: _("Random"),
			# Translators: Side choice in the new game dialog: play the white pieces.
			PlayerColor.WHITE: _("White"),
			# Translators: Side choice in the new game dialog: play the black pieces.
			PlayerColor.BLACK: _("Black"),
		}

	def get_color(self):
		if self is PlayerColor.RANDOM:
			return random.choice(chess.COLORS)
		return chess.WHITE if self is PlayerColor.WHITE else chess.BLACK
