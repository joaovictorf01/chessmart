# coding: utf-8

"""Small local signal implementation compatible with the add-on's usage."""

_ANY_SENDER = object()


class Signal:
	def __init__(self, name, doc=None):
		self.name = name
		self.doc = doc
		self._receivers = []

	def connect(self, receiver, sender=_ANY_SENDER, weak=True):
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


Chessboard_signals = Namespace()
chessboard_opened_signal = Chessboard_signals.signal("chessboard-opened")
chessboard_closed_signal = Chessboard_signals.signal("chessboard-closed")
game_started_signal = Chessboard_signals.signal("game-started")
game_over_signal = Chessboard_signals.signal("game_over", "args: outcome")
move_completed_signal = Chessboard_signals.signal("move-completed", doc="args: move_maker")
