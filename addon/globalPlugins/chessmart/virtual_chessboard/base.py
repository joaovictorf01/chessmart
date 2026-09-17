# coding: utf-8
# pyright: basic

import bisect
import dataclasses
import enum
import functools
import itertools
import math
from typing import Iterable

import wx
import inputCore
import globalVars
import ui
import api
import controlTypes
import eventHandler
import speech
import speech.commands
from NVDAObjects import NVDAObject
from scriptHandler import script
from .ui_components import (
	KeyboardNavigableNVDAObjectMixin,
	MenuItemObject,
	MenuObject,
	SimpleList,
)
from ..time_control import NULL_TIME_CONTROL
from ..spoken_messages import standard_game_announcer, ibca_game_announcer, spoken_color_name
from ..i18n import _
from ..notation import DESCRIPTIVE, render_san, render_square
from ..addon_config import get_move_notation
from ..paths import import_bundled
from ..sounds import GameSound
from ..speaking import intersperse, speak_next
from ..concurrency import call_threaded
from ..signals import (
	move_completed_signal,
	game_started_signal,
	game_over_signal,
	chessboard_closed_signal,
)


with import_bundled():
	import chess
	import chess.pgn
	import chess.svg


class Color(enum.Enum):
	"""Cores do destaque desenhado no tabuleiro (a seta sobre a casa focada)."""

	Red = "#96D454"
	Blue = "#0000FF"
	Green = "#00B050"
	Yellow = "#FFFF00"
	Purple = "#953553"
	DarkGray = "#3C3C3C"


@dataclasses.dataclass(frozen=True)
class PlayedMove:
	"""Tudo o que se precisa saber de um lance para descrevê-lo em voz alta.

	Capturado ANTES de o lance entrar no tabuleiro, porque depois dele a
	posição já é outra: a peça capturada sumiu, o SAN não se calcula mais
	(a desambiguação de "Ngf3" depende das peças que podiam ir à mesma casa) e
	o roque já moveu a torre.
	"""

	move: chess.Move
	mover: chess.Color
	moved_piece: chess.Piece | None
	captured_piece: chess.Piece | None
	is_castling: bool
	is_kingside_castling: bool
	is_en_passant: bool
	san: str

	@classmethod
	def capture(cls, board: chess.Board, move: chess.Move) -> "PlayedMove":
		is_castling = board.is_castling(move)
		is_en_passant = board.is_en_passant(move)
		if is_en_passant:
			# O peão capturado não está na casa de destino, e sim atrás dela.
			captured = board.piece_at(move.to_square - 8)
		else:
			captured = board.piece_at(move.to_square)
		return cls(
			move=move,
			mover=board.turn,
			moved_piece=board.piece_at(move.from_square),
			captured_piece=captured,
			is_castling=is_castling,
			is_kingside_castling=is_castling and board.is_kingside_castling(move),
			is_en_passant=is_en_passant,
			san=board.san(move),
		)

	@property
	def is_capture(self) -> bool:
		return self.captured_piece is not None

	@property
	def sound(self) -> GameSound:
		"""O som que anuncia o tipo do lance."""
		if self.move.promotion is not None:
			return GameSound.promotion
		if self.is_castling:
			return GameSound.castling
		if self.move.drop:
			return GameSound.drop_move
		if self.is_capture:
			return GameSound.en_passant if self.is_en_passant else GameSound.capture
		return GameSound.drop_piece


class BaseChessboardCell(KeyboardNavigableNVDAObjectMixin, NVDAObject):
	role = controlTypes.Role.TABLECELL
	# O NVDA declara `parent` como Optional[NVDAObject], preenchido por `_get_parent`.
	# Uma casa pertence sempre ao tabuleiro que a criou; o tipo aqui diz isso.
	parent: "BaseVirtualChessboard"
	PIECE_LETTERS = {
		"r": chess.ROOK,
		"n": chess.KNIGHT,
		"b": chess.BISHOP,
		"q": chess.QUEEN,
		"k": chess.KING,
		"p": chess.PAWN,
	}

	def __init__(self, parent, index, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.parent = parent
		self.game_announcer = self.parent.game_announcer
		self.index = index
		self.processID = self.parent.processID
		self._add_multiple_scripts()

	def _add_multiple_scripts(self):
		gestures = {}
		jump_script_func = getattr(self.__class__, "script_jump_to_piece_handler")
		for letter, piece_type in self.PIECE_LETTERS.items():
			gestures[f"kb:{letter}"] = functools.partialmethod(jump_script_func, piece_type, False)
			gestures[f"kb:shift+{letter}"] = functools.partialmethod(jump_script_func, piece_type, True)
		self._gestureMap.update({inputCore.normalizeGestureIdentifier(k): v for (k, v) in gestures.items()})

	@property
	def roleText(self):
		if self.parent.board.piece_at(self.index) is None:
			# Translators: Role of an empty board square, spoken by the screen reader.
			return _("Square")

	@property
	def states(self):
		return {
			controlTypes.State.FOCUSABLE,
			controlTypes.State.FOCUSED,
		}

	@property
	def description(self):
		return self.parent.spoken_square_name(self.index)

	@property
	def name(self):
		return self.parent.get_piece_name_at_square(self.index)

	def on_activate(self):
		self.parent.activate_cell(self)

	@property
	def square_color(self):
		square_number = self.index
		file_index, rank_index = (
			chess.square_file(square_number) + 1,
			chess.square_rank(square_number) + 1,
		)
		is_row_even = (file_index % 2) == 0
		is_cell_even = (rank_index % 2) == 0
		return chess.WHITE if (is_row_even != is_cell_even) else chess.BLACK

	def get_remaining_time(self, color: chess.Color):
		color_name = spoken_color_name(color)
		total_seconds = self.parent.time_control.get_remaining_time()[color]
		minutes = math.floor(total_seconds / 60)
		seconds = math.floor(total_seconds % 60)
		if not minutes:
			# Translators: Remaining clock time, e.g. "45 seconds remaining for white".
			return _("{seconds} seconds remaining for {color}").format(seconds=seconds, color=color_name)
		elif not seconds:
			# Translators: Remaining clock time, e.g. "5 minutes remaining for white".
			return _("{minutes} minutes remaining for {color}").format(minutes=minutes, color=color_name)
		# Translators: Remaining clock time, e.g. "5 minutes and 30 seconds remaining for white".
		return _("{minutes} minutes and {seconds} seconds remaining for {color}").format(
			minutes=minutes,
			seconds=seconds,
			color=color_name,
		)

	def get_highlight_color(self):
		return Color.Blue

	def update_visual_highlight(self):
		if not self.parent.use_visuals:
			return
		arrows = [chess.svg.Arrow(self.index, self.index, color=self.get_highlight_color().value)]
		last_move = None
		if self.parent.board.move_stack:
			last_move = self.parent.board.move_stack[-1]
			if self.parent.visual_arrows:
				arrows.append(
					chess.svg.Arrow(
						last_move.from_square,
						last_move.to_square,
						color=Color.DarkGray.value,
					),
				)
		self.parent.dialog.set_board_image(arrows=arrows, lastmove=last_move)

	def event_gainFocus(self):
		super().event_gainFocus()
		self.parent._focused_cell = self.index
		if self.square_color is chess.BLACK:
			GameSound.black_square.play()
		self.update_visual_highlight()

	def script_activate_cell(self, gesture):
		self.on_activate()

	def script_jump_to_piece_handler(self, piece_type, to_opponent_piece, gesture):
		if self.parent.prospective is not None:
			piece_color = self.parent.prospective
		else:
			piece_color = chess.WHITE
		piece_color = piece_color if not to_opponent_piece else not piece_color
		self.parent.jump_to_piece(piece_type, piece_color)

	@script(gesture="kb:f1")
	def script_player_overview(self, gesture):
		self.parent.announce_player_overview(self.parent.prospective)

	@script(gesture="kb:shift+f1")
	def script_opponent_overview(self, gesture):
		self.parent.announce_player_overview(not self.parent.prospective)

	@script(gesture="kb:f3")
	def script_cell_info(self, gesture):
		color = spoken_color_name(self.square_color)
		spoken_commands = [
			ibca_game_announcer.square_file(self.index),
			speech.commands.BreakCommand(100),
			ibca_game_announcer.square_rank(self.index),
			speech.commands.BreakCommand(250),
			# Translators: Color of the focused square, e.g. "square color: white,".
			_("square color: {color},").format(color=color),
		]
		piece_type = self.parent.board.piece_type_at(self.index)
		if piece_type is not None:
			spoken_commands.insert(0, ibca_game_announcer.piece_name(piece_type))
			spoken_commands.insert(1, speech.commands.BreakCommand(100))
		speak_next(spoken_commands)

	@script(gesture="kb:f2")
	def script_announce_time_for_current_turn(self, gesture):
		if self.parent.time_control is NULL_TIME_CONTROL:
			GameSound.invalid.play()
			# Translators: Spoken when the clock is asked for in a game without time control.
			return ui.message(_("No Time Control"))
		color = self.parent.board.turn
		remaining = self.get_remaining_time(color)
		ui.message(remaining)

	@script(gesture="kb:shift+f2")
	def script_announce_time_for_other_turn(self, gesture):
		if self.parent.time_control is NULL_TIME_CONTROL:
			GameSound.invalid.play()
			return ui.message(_("No Time Control"))
		color = not self.parent.board.turn
		remaining = self.get_remaining_time(color)
		ui.message(remaining)

	@script(gesture="kb:a")
	def script_announce_attackers(self, gesture):
		self.parent.announce_attackers(self.index)

	@script(gesture="kb:m")
	def script_announce_material(self, gesture):
		self.parent.announce_material()

	@script(gesture="kb:f4")
	def script_score_sheet(self, gesture):
		if self.parent.score_sheet_menu:
			eventHandler.queueEvent("gainFocus", self.parent.score_sheet_menu)
		else:
			# Translators: Spoken when the score sheet is opened before any move.
			ui.message(_("Score sheet is empty"))

	@script(gesture="kb:control+s")
	def script_save_board_pgn(self, gesture):
		if globalVars.appArgs.secure:
			# Translators: Spoken when saving is refused because NVDA runs in secure mode.
			return ui.message(_("Could not save game. NVDA running in secure mode."))
		self.parent.save_game()

	@script(gesture="kb:control+shift+s")
	def script_save_board_image(self, gesture):
		if globalVars.appArgs.secure:
			return ui.message(_("Could not save game. NVDA running in secure mode."))
		self.parent.save_board_image()

	@script(gesture="kb:escape")
	def script_escape(self, gesture):
		self.parent.request_leave()

	@script(gesture="kb:rightarrow")
	def script_rightarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_right(self)
		else:
			self.parent.navigate_left(self)

	@script(gesture="kb:leftarrow")
	def script_leftarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_left(self)
		else:
			self.parent.navigate_right(self)

	@script(gesture="kb:downarrow")
	def script_downarrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_down(self)
		else:
			self.parent.navigate_up(self)

	@script(gesture="kb:uparrow")
	def script_uparrow(self, gesture):
		if not self.parent.is_board_flipped:
			self.parent.navigate_up(self)
		else:
			self.parent.navigate_down(self)

	__gestures = {
		"kb:enter": "activate_cell",
		"kb:numpadenter": "activate_cell",
		"kb:space": "activate_cell",
	}


class LeaveGameMenu(MenuObject):
	"""A pergunta que o Escape faz antes de fechar um jogo em andamento.

	Duas opções, e a primeira é ficar: um Escape a mais (dentro do menu) volta
	ao tabuleiro em vez de sair. Sair exige escolher "Yes" de propósito.
	"""

	def __init__(self, choice_callback, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.choice_callback = choice_callback
		self.init_container_state(
			[
				# Translators: Option in the menu shown when Escape is pressed during a game.
				MenuItemObject(name=_("No, keep playing"), parent=self),
				# Translators: Option in the menu shown when Escape is pressed during a game.
				MenuItemObject(name=_("Yes, leave"), parent=self),
			],
		)

	def on_item_activated(self, item):
		self.choice_callback(bool(self.index_of(item)))

	def close_menu(self):
		self.choice_callback(False)


class BaseVirtualChessboard(KeyboardNavigableNVDAObjectMixin, NVDAObject):
	role = controlTypes.Role.TABLE
	# Translators: Role of the chessboard control, spoken by the screen reader.
	roleText = _("Board")
	# Translators: Name of the chessboard control, spoken by the screen reader.
	name = _("Chess")
	row_ranges = tuple(
		range(i, j) for (i, j) in zip([i * 8 for i in range(0, 8)], [j * 8 for j in range(1, 9)])
	)
	cell_class = BaseChessboardCell
	can_draw = True
	can_resign = True

	def __init__(
		self,
		dialog,
		*,
		variant,
		prospective=None,
		time_control=NULL_TIME_CONTROL,
		game_announcer=standard_game_announcer,
		use_visuals=True,
		visual_arrows=False,
		pychess_board=None,
	):
		super().__init__()
		self.parent = api.getFocusObject()
		self.processID = self.parent.processID
		self.dialog = dialog
		self.variant = variant
		self.game_announcer = game_announcer
		self.prospective = prospective
		self.time_control = time_control
		self.use_visuals = use_visuals
		self.visual_arrows = visual_arrows
		self.board = pychess_board or chess.Board()
		self._chess_cells = [self.cell_class(parent=self, index=i) for i in range(0, 64)]
		self._focused_cell = self.get_initial_focus_cell()
		self.is_game_over = False
		self._current_focused_object = None
		self.score_sheet_menu = SimpleList(
			# Translators: Name of the list of moves played so far.
			parent=self,
			name=_("Score sheet"),
			close_gesture="kb:f4",
		)
		# Connect to events
		game_started_signal.connect(lambda s: self.time_control.start_game(), sender=self)
		chessboard_closed_signal.connect(lambda s: self.game_over(), sender=self)

	def get_initial_focus_cell(self):
		return 4 if not self.is_board_flipped else 60

	@property
	def is_board_flipped(self):
		return not self.prospective

	@property
	def is_board_visually_flipped(self):
		return self.is_board_flipped

	def get_highlighted_squares(self):
		yield self._focused_cell

	def get_containing_row(self, index):
		for rng in self.row_ranges:
			if index in rng:
				return rng

	def game_over(self, dialog_title=None):
		was_over = self.is_game_over
		self.is_game_over = True
		# Translators: Window title when a game has ended.
		self.dialog.SetTitle(dialog_title or _("Game Over"))
		eventHandler.queueEvent("stateChange", api.getFocusObject())
		# Uma vez só: fechar a janela de um jogo já terminado chama isto de
		# novo, e quem escuta o sinal (a engine, por exemplo) já se despediu.
		if not was_over:
			game_over_signal.send(self, board_outcome=self.board.outcome())

	def game_resigned(self, resigning_color):
		self.game_over()
		color_name = spoken_color_name(resigning_color)
		# Translators: Window title after a resignation, e.g. "white resigned".
		self.dialog.SetTitle(_("{color} resigned").format(color=color_name))
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.resigned.filename),
				speech.commands.BreakCommand(200),
				# Translators: Spoken after a resignation, e.g. "white resigned the game".
				_("{color} resigned the game").format(color=color_name),
			],
		)

	def game_drawn(self):
		self.game_over()
		# Translators: Window title when the game ended in a draw.
		self.dialog.SetTitle(_("Game Drawn"))
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.drawn.filename),
				speech.commands.BreakCommand(200),
				# Translators: Spoken when the game ended in a draw.
				_("Game is drawn"),
			],
		)

	def game_time_forfeit(self, losing_color: chess.Color):
		self.game_over(
			# Translators: Window title when a game was lost on time, e.g. "Game Over: Time Forfeit - white is the winner".
			_("Game Over: Time Forfeit - {color} is the winner").format(
				color=self.game_announcer.color_name(not losing_color),
			),
		)
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.time_forfeit.filename),
				speech.commands.BreakCommand(300),
				# Translators: Spoken when a side ran out of time, e.g. "black, time over".
				_("{color}, time over").format(color=self.game_announcer.color_name(losing_color)),
				speech.commands.BreakCommand(150),
				# Translators: Spoken to name the winner, e.g. "white is the winner".
				_("{color} is the winner").format(color=self.game_announcer.color_name(not losing_color)),
			],
		)

	def game_error(self, error_message=None):
		# Translators: Window title and message when a game stopped because of an error.
		error_message = error_message or _("Game terminated due to an error")
		self.game_over()
		self.dialog.SetTitle(error_message)
		speak_next(
			[
				speech.commands.WaveFileCommand(GameSound.error.filename),
				speech.commands.BreakCommand(200),
				error_message,
			],
		)

	def set_focus_to_cell(self, index):
		eventHandler.executeEvent("gainFocus", self._chess_cells[index])

	def activate_cell(self, cell):
		GameSound.invalid.play()

	def move_piece_and_check_game_status(self, move, pre_speech=(), post_speech=()):
		if move not in self.board.legal_moves:
			speak_next(
				[
					speech.commands.WaveFileCommand(GameSound.invalid.filename),
					speech.commands.BreakCommand(100),
					# Translators: Spoken when the requested move is not legal.
					_("Illegal move"),
				],
			)
			return
		played = PlayedMove.capture(self.board, move)
		move_maker = played.mover
		self.board.push(move)
		self.time_control.time_move(not self.board.turn, total_moves=len(self.board.move_stack))
		desc_generator = tuple(self._describe_move(played))
		self.score_sheet_menu.add_item(" ".join(i for i in desc_generator if type(i) is str))
		spoken_commands: list[Iterable] = [desc_generator]
		spoken_commands.append(pre_speech)
		if self.board.is_game_over():
			spoken_commands.append(self._get_game_over_messages())
			spoken_commands.append([speech.commands.CallbackCommand(self.game_over)])
		elif self.board.is_check():
			spoken_commands.append(
				[
					speech.commands.WaveFileCommand(GameSound.check.filename),
					speech.commands.BreakCommand(250),
					# Translators: Spoken when a king is in check, e.g. "white is in check".
					_("{color} is in check").format(color=spoken_color_name(self.board.turn)),
				],
			)
			if (move_maker != self.prospective) or (self.prospective is None):
				spoken_commands.append(
					[
						speech.commands.BreakCommand(250),
						speech.commands.CallbackCommand(
							functools.partial(self.jump_to_piece, chess.KING, self.board.turn),
						),
						speech.commands.BreakCommand(250),
						speech.commands.CallbackCommand(
							functools.partial(
								self.announce_attackers,
								self.board.king(self.board.turn),
								True,
							),
						),
					],
				)
		spoken_commands.append(post_speech)
		# O list() aqui não é estilo, é o conserto: itertools.chain devolve um
		# ITERADOR preguiçoso, e a fala do NVDA espera uma sequência de
		# verdade. Recebendo o iterador, o NVDA o percorre uma vez ao inspecionar
		# a sequência e depois não sobra nada para falar -- o lance ia para o
		# tabuleiro e o anúncio simplesmente desaparecia, sem erro nenhum.
		# Medido com o log de io do NVDA: a sequência tinha 15 itens e 7 textos,
		# e mesmo assim não havia registro de "Speaking".
		speak_next(list(itertools.chain(*spoken_commands)))
		self.dialog.set_board_image(lastmove=move)
		move_completed_signal.send(self, move=move, move_maker=move_maker)

	def _describe_move(self, played: PlayedMove):
		"""A sequência falada de um lance já jogado: som do tipo do lance e o texto."""
		move = played.move
		style = get_move_notation()
		if style != DESCRIPTIVE and played.san:
			# Estilo curto (SAN, UCI, anna...): o som do tipo de lance continua,
			# e o texto vem de uma só vez, como o Lichess fala.
			yield speech.commands.WaveFileCommand(played.sound.filename)
			yield speech.commands.BreakCommand(150)
			yield render_san(played.san, move.uci(), style)
			return
		if move.promotion is not None:
			yield speech.commands.WaveFileCommand(GameSound.promotion.filename)
			yield speech.commands.BreakCommand(300)
			yield from intersperse(
				self.game_announcer.promotion_move(move, move_maker=played.mover),
				speech.commands.BreakCommand(200),
			)
			return
		if played.is_castling:
			yield speech.commands.WaveFileCommand(GameSound.castling.filename)
			yield speech.commands.BreakCommand(250)
			yield from intersperse(
				self.game_announcer.castling_move(played.mover, played.is_kingside_castling),
				speech.commands.BreakCommand(200),
			)
			return
		# Depois do push a peça movida está na casa de destino (já promovida, se for o caso).
		moved_piece = self.board.piece_at(move.to_square)
		assert moved_piece is not None, "a legal move always leaves a piece on its destination"
		if move.drop:
			yield speech.commands.WaveFileCommand(GameSound.drop_move.filename)
			yield from intersperse(
				self.game_announcer.drop_move(played.mover, move=move),
				speech.commands.BreakCommand(200),
			)
			yield speech.commands.BreakCommand(300)
		if played.captured_piece is not None:
			yield speech.commands.WaveFileCommand(played.sound.filename)
			yield from intersperse(
				self.game_announcer.capture_move(move, moved_piece, played.captured_piece),
				speech.commands.BreakCommand(200),
			)
			if played.is_en_passant:
				# Translators: Spoken after an en passant capture.
				yield _("en passant")
			return
		yield speech.commands.WaveFileCommand(GameSound.drop_piece.filename)
		yield from intersperse(
			self.game_announcer.normal_move(move, moved_piece, move_maker=played.mover),
			speech.commands.BreakCommand(50),
		)

	def jump_to_piece(self, piece_type, piece_color):
		target_squares = tuple(self.board.pieces(piece_type, piece_color))
		if not target_squares:
			piece = chess.Piece(piece_type, piece_color)
			piece_name = self.game_announcer.describe_piece(piece)
			# Translators: Spoken when jumping to a piece that is no longer on the board, e.g. "No white knight".
			ui.message(_("No {piece}").format(piece=piece_name))
			return
		target_pos = bisect.bisect_right(target_squares, self._focused_cell)
		if target_pos == len(target_squares):
			target_pos = 0
		target_cell = target_squares[target_pos]
		self.set_focus_to_cell(target_cell)

	def notify_invalid_navigation(self):
		GameSound.invalid.play()
		speech.speakObject(api.getFocusObject(), controlTypes.OutputReason.FOCUS)

	def spoken_square_name(self, square):
		"""A casa como ela é falada: "f3", ou "felix 3" / "foxtrot 3" nesses estilos."""
		return render_square(self.game_announcer.square_name(square), get_move_notation())

	def get_piece_name_at_square(self, index):
		piece = self.board.piece_at(index)
		if piece is None:
			return ""
		return self.game_announcer.describe_piece(piece)

	def _get_game_over_messages(self):
		outcome = self.board.outcome()
		assert outcome is not None, "called only when board.is_game_over()"
		termination_reason = outcome.termination.name.replace("_", " ")
		yield from [
			speech.commands.WaveFileCommand(GameSound.game_over.filename),
			speech.commands.BreakCommand(250),
			termination_reason,
		]
		game_winner = "" if outcome.winner is None else self.game_announcer.color_name(outcome.winner)
		if game_winner:
			yield from [
				speech.commands.BreakCommand(250),
				_("{color} is the winner").format(color=game_winner),
			]

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
			square_name = chess.square_name(attacking_square)
			piece_name = self.get_piece_name_at_square(attacking_square)
			spoken_commands += [
				piece_name,
				speech.commands.BreakCommand(250),
				# Translators: Spoken between an attacking piece and its square, e.g. "knight, at, f3".
				_("at"),
				speech.commands.BreakCommand(250),
				square_name,
			]
			spoken_commands.append(speech.commands.BreakCommand(350))
		speak_next(spoken_commands)

	# Valores classicos. Bispo e cavalo valem o mesmo de proposito: contar os
	# dois juntos e o que evita se perder quando houve troca de um pelo outro.
	MATERIAL_VALUES = {
		chess.QUEEN: 9,
		chess.ROOK: 5,
		chess.BISHOP: 3,
		chess.KNIGHT: 3,
		chess.PAWN: 1,
	}

	def announce_material(self):
		"""Conta o material pela foto do tabuleiro, tipo a tipo, e da o saldo.

		Nada de historico de trocas: e o que esta no tabuleiro agora, do ponto
		de vista de quem joga neste tabuleiro (brancas quando nao ha lado).
		"""
		me = self.prospective if self.prospective is not None else chess.WHITE
		them = not me

		def count(piece_type, color):
			return len(self.board.pieces(piece_type, color))

		lines = [
			# Translators: Plural piece name in the material count.
			(_("queens"), count(chess.QUEEN, me), count(chess.QUEEN, them)),
			# Translators: Plural piece name in the material count.
			(_("rooks"), count(chess.ROOK, me), count(chess.ROOK, them)),
			(
				# Translators: Bishops and knights together, in the material count.
				_("minor pieces"),
				count(chess.BISHOP, me) + count(chess.KNIGHT, me),
				count(chess.BISHOP, them) + count(chess.KNIGHT, them),
			),
			# Translators: Plural piece name in the material count.
			(_("pawns"), count(chess.PAWN, me), count(chess.PAWN, them)),
		]
		balance = sum(
			value * (count(piece_type, me) - count(piece_type, them))
			for piece_type, value in self.MATERIAL_VALUES.items()
		)
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
		my_bishops = count(chess.BISHOP, me)
		their_bishops = count(chess.BISHOP, them)
		if my_bishops == 2 and their_bishops < 2:
			# Translators: Spoken in the material count.
			spoken_commands.append(_("You have the bishop pair."))
		elif their_bishops == 2 and my_bishops < 2:
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

	def event_gainFocus(self):
		if self._current_focused_object is not None:
			eventHandler.queueEvent("gainFocus", self._current_focused_object)
		else:
			self.set_focus_to_cell(self._focused_cell)

	def navigate_left(self, anchor):
		row_range = self.get_containing_row(anchor.index) or range(0, 64)
		prev_index = anchor.index - 1
		if prev_index not in row_range:
			return self.notify_invalid_navigation()
		self.set_focus_to_cell(prev_index)

	def navigate_right(self, anchor):
		row_range = self.get_containing_row(anchor.index) or range(0, 64)
		next_index = anchor.index + 1
		if next_index not in row_range:
			return self.notify_invalid_navigation()
		self.set_focus_to_cell(next_index)

	def navigate_up(self, anchor):
		next_index = anchor.index + 8
		if next_index > 63:
			return self.notify_invalid_navigation()
		self.set_focus_to_cell(next_index)

	def navigate_down(self, anchor):
		prev_index = anchor.index - 8
		if prev_index < 0:
			return self.notify_invalid_navigation()
		self.set_focus_to_cell(prev_index)

	# -- sair do tabuleiro ----------------------------------------------------

	def leave_prompt(self):
		"""A pergunta a fazer antes de sair, ou None para sair sem perguntar.

		Cada modo diz o que se perde: a partida contra a engine, a partida
		online, o puzzle em andamento. O replay de PGN não perde nada e não
		pergunta. Com o jogo terminado ninguém pergunta.
		"""
		return None

	def request_leave(self):
		"""Escape no tabuleiro: pergunta se houver o que perder, senão sai."""
		prompt = None if self.is_game_over else self.leave_prompt()
		if prompt is None:
			self.leave_game()
			return
		menu = LeaveGameMenu(choice_callback=self._on_leave_choice, name=prompt, parent=self)
		self._current_focused_object = menu
		GameSound.menu_open.play()
		eventHandler.queueEvent("gainFocus", menu)

	def _on_leave_choice(self, leave):
		self._current_focused_object = None
		if leave:
			self.leave_game()
		else:
			eventHandler.queueEvent("gainFocus", self)

	def leave_game(self):
		"""Sai de vez. Modos com adversário do outro lado avisam antes (ver subclasses)."""
		self.hide_board_gui()

	def hide_board_gui(self):
		"""Fecha a janela do tabuleiro de verdade.

		Era `Hide()`: a janela sumia, mas o `onClose` do diálogo nunca rodava,
		então o timer seguia batendo, a engine continuava viva e o diálogo ficava
		para sempre na lista de janelas ativas do plugin. `Close()` passa pelo
		`onClose`, que para o timer, dispara o sinal de fechamento (e com ele o
		fim do jogo) e destrói a janela.
		"""
		eventHandler.queueEvent("gainFocus", self.parent)
		self.dialog.Close()

	@call_threaded
	def save_game(self):
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the game as a PGN file.
			message=_("Save Game As"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the PGN save dialog.
			wildcard=_("Chess Game *.pgn | *.pgn"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		try:
			if saveFileDialog.ShowModal() != wx.ID_OK:
				return
			save_as_filename = saveFileDialog.GetPath().strip()
		finally:
			saveFileDialog.Destroy()
		if not save_as_filename:
			return
		game = chess.pgn.Game.from_board(self.board)
		with open(save_as_filename, "w", encoding="utf-8") as file:
			exporter = chess.pgn.FileExporter(file)
			game.accept(exporter)

	@call_threaded
	def save_board_image(self):
		saveFileDialog = wx.FileDialog(
			parent=None,
			# Translators: Title of the dialog that saves the board as an image.
			message=_("Save Board To Image"),
			defaultDir=wx.GetUserHome(),
			# Translators: File type filter of the image save dialog.
			wildcard=_("Portable Network Graphics *.png | *.png"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		try:
			if saveFileDialog.ShowModal() != wx.ID_OK:
				return
			save_as_filename = saveFileDialog.GetPath().strip()
		finally:
			saveFileDialog.Destroy()
		if not save_as_filename:
			return
		self.dialog.bitmap_buffer.SaveFile(save_as_filename, wx.BITMAP_TYPE_PNG)
