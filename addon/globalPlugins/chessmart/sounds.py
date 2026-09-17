# coding: utf-8
# pyright: basic

# Copyright (c) 2021 Blind Pandas Team
# This file is covered by the GNU General Public License.

"""Os sons do tabuleiro, um por evento, em `sounds/*.wav`."""

import enum
import os

from nvwave import playWaveFile

from .paths import SOUNDS_DIRECTORY


class GameSound(enum.Enum):
	black_square = "black_square"
	start_game = "start_game"
	chess_pieces = "chess_pieces"
	invalid = "invalid"
	request_promotion = "request_promotion"
	promotion = "promotion"
	capture = "capture"
	en_passant = "en_passant"
	check = "check"
	castling = "castling"
	pick_piece = "pick_piece"
	drop_piece = "drop_piece"
	drop_move = "drop_move"
	drop_target = "drop_target"
	game_over = "game_over"
	error = "error"
	resigned = "resigned"
	drawn = "drawn"
	time_pass = "time_pass"
	time_critical = "time_critical"
	time_forfeit = "time_forfeit"
	score_list_open = "score_list_open"
	score_list_close = "score_list_close"
	menu_open = "menu_open"
	chat = "chat"
	you_won = "you_won"
	puzzle_solved = "puzzle_solved"

	def __init__(self, filename):
		self.filename = os.path.join(SOUNDS_DIRECTORY, f"{filename}.wav")

	def play(self):
		playWaveFile(self.filename)
