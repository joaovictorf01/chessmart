# coding: utf-8
# pyright: basic

"""Sinais entre o tabuleiro, o diálogo e os jogadores (engine, Lichess).

Implementação mínima no estilo do blinker: um `Signal` guarda receptores, cada
um opcionalmente preso a um `sender`, e `send` chama os que casam. As
referências aos receptores são fortes: um tabuleiro conecta lambdas e métodos
próprios e vive enquanto a janela dele viver, e é `disconnect` (ou o fim do
processo) que os solta.
"""

_ANY_SENDER = object()


class Signal:
	def __init__(self, name, doc=None):
		self.name = name
		self.doc = doc
		self._receivers = []

	def connect(self, receiver, sender=_ANY_SENDER):
		self._receivers.append((receiver, sender))
		return receiver

	def disconnect(self, receiver, sender=_ANY_SENDER):
		self._receivers = [
			(registered_receiver, registered_sender)
			for (registered_receiver, registered_sender) in self._receivers
			if not (
				registered_receiver == receiver and (sender is _ANY_SENDER or registered_sender == sender)
			)
		]

	def send(self, sender=None, **kwargs):
		results = []
		for receiver, expected_sender in tuple(self._receivers):
			if expected_sender is not _ANY_SENDER and expected_sender != sender:
				continue
			results.append((receiver, receiver(sender, **kwargs)))
		return results


class Namespace:
	def __init__(self):
		self._signals = {}

	def signal(self, name, doc=None):
		if name not in self._signals:
			self._signals[name] = Signal(name=name, doc=doc)
		return self._signals[name]


chessboard_signals = Namespace()
chessboard_opened_signal = chessboard_signals.signal("chessboard-opened")
chessboard_closed_signal = chessboard_signals.signal("chessboard-closed")
game_started_signal = chessboard_signals.signal("game-started")
game_over_signal = chessboard_signals.signal("game_over", "args: outcome")
move_completed_signal = chessboard_signals.signal("move-completed", doc="args: move_maker")
