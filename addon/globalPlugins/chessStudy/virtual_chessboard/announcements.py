# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What A, M and F1 / Shift+F1 say about the position. Combined with a board class.

Split out of base.py so the board file keeps to squares, moves and the game's
end. The counting itself is in board_geometry.py, where it is tested.
"""

import itertools
import typing

import speech
import speech.commands
import ui

from ..board_geometry import count_material
from ..i18n import _
from ..paths import import_bundled
from ..speaking import intersperse, speak_next


with import_bundled():
	import chess


class AnnouncementsMixin:
	board: typing.Any
	prospective: typing.Any

	@property
	def material_side(self) -> bool:
		"""Whose side M counts from: the player's, or White when no side is set. Boards may override."""
		return self.prospective if self.prospective is not None else chess.WHITE

	get_piece_name_at_square: typing.Any
	spoken_square_name: typing.Any

	def announce_attackers(self, cell_index, announce_piece_name=False):
		piece = self.board.piece_at(cell_index)
		if piece is not None:
			attacking_color = not piece.color
			attackers = list(self.board.attackers(attacking_color, cell_index))
		else:
			attackers = list(self.board.attackers(not self.board.turn, cell_index))
		attackers.sort()
		if not attackers:
			# Translators: Spoken when the focused square has no attackers.
			ui.message(_("This square is not under attack"))
			return
		spoken_commands = []
		if announce_piece_name:
			piece_name = self.get_piece_name_at_square(cell_index)
			spoken_commands.append(f"{piece_name}")
			spoken_commands.append(speech.commands.BreakCommand(250))
		spoken_commands += [
			# Translators: Spoken before the list of pieces attacking a square.
			_("Attacked by"),
			speech.commands.BreakCommand(250),
		]
		for attacking_square in attackers:
			spoken_commands += [
				# Translators: One attacker of a square, e.g. "knight at f3".
				_("{piece} at {square}").format(
					piece=self.get_piece_name_at_square(attacking_square),
					square=chess.square_name(attacking_square),
				),
				speech.commands.BreakCommand(350),
			]
		speak_next(spoken_commands)

	def announce_material(self):
		"""Counts material from a snapshot of the board, type by type, and gives the balance.

		No trade history: it's what's on the board right now, from the
		perspective of whoever plays on this board (white when no side is set).
		"""
		me = self.material_side
		material = count_material(self.board, me)
		lines = [
			# Translators: Plural piece name in the material count.
			(_("queens"), *material.queens),
			# Translators: Plural piece name in the material count.
			(_("rooks"), *material.rooks),
			# Translators: Bishops and knights together, in the material count.
			(_("minor pieces"), *material.minor_pieces),
			# Translators: Plural piece name in the material count.
			(_("pawns"), *material.pawns),
		]
		balance = material.balance
		# Translators: Heading of the material count announcement.
		spoken_commands = [_("Material.")]
		for label, mine, theirs in lines:
			# Translators: One line of the material count, e.g. "rooks: 2 to 1.".
			spoken_commands.append(
				_("{pieces}: {mine} to {theirs}.").format(pieces=label, mine=mine, theirs=theirs),
			)
		if balance > 0:
			# Translators: Material balance in the player's favor, in pawn units.
			spoken_commands.append(_("You are up {points}.").format(points=balance))
		elif balance < 0:
			# Translators: Material balance against the player, in pawn units.
			spoken_commands.append(_("You are down {points}.").format(points=abs(balance)))
		else:
			# Translators: Spoken when both sides have the same material.
			spoken_commands.append(_("Material is even."))
		if material.bishop_pair is True:
			# Translators: Spoken in the material count.
			spoken_commands.append(_("You have the bishop pair."))
		elif material.bishop_pair is False:
			# Translators: Spoken in the material count.
			spoken_commands.append(_("Opponent has the bishop pair."))
		speak_next(intersperse(spoken_commands, speech.commands.BreakCommand(150)))

	def announce_player_overview(self, color):
		square_set = itertools.chain(
			*[self.board.pieces(piece_type, color) for piece_type in sorted(chess.PIECE_TYPES, reverse=True)],
		)
		spoken_commands = [
			f"{self.get_piece_name_at_square(square)}, {self.spoken_square_name(square)}"
			for square in square_set
		]
		speak_next(intersperse(spoken_commands, speech.commands.BreakCommand(250)))
