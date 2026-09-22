# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The signals between a board, its dialog and its players, and their release on close."""

import unittest

from chessmart.signals import Namespace, Signal


class TestSignal(unittest.TestCase):
	def test_send_reaches_only_receivers_of_that_sender_or_of_any_sender(self):
		signal = Signal("s")
		calls = []
		signal.connect(lambda sender, **kw: calls.append(("a", sender)), sender="a")
		signal.connect(lambda sender, **kw: calls.append(("b", sender)), sender="b")
		signal.connect(lambda sender, **kw: calls.append(("any", sender)))
		signal.send("a")
		self.assertEqual(calls, [("a", "a"), ("any", "a")])

	def test_disconnect_sender_drops_that_sender_and_keeps_the_rest(self):
		signal = Signal("s")
		calls = []
		signal.connect(lambda sender, **kw: calls.append("a"), sender="a")
		signal.connect(lambda sender, **kw: calls.append("b"), sender="b")
		signal.connect(lambda sender, **kw: calls.append("any"))
		signal.disconnect_sender("a")
		signal.send("a")
		signal.send("b")
		self.assertEqual(calls, ["any", "b", "any"])
		self.assertEqual(len(signal._receivers), 2)

	def test_namespace_disconnect_sender_covers_every_signal(self):
		# What the chessboard dialog does on close: one call releases the board's
		# receivers on game-started, game-over, move-completed and closed alike.
		namespace = Namespace()
		first = namespace.signal("first")
		second = namespace.signal("second")
		board = object()
		first.connect(lambda sender: None, sender=board)
		second.connect(lambda sender: None, sender=board)
		second.connect(lambda sender: None, sender="other")
		namespace.disconnect_sender(board)
		self.assertEqual(first._receivers, [])
		self.assertEqual(len(second._receivers), 1)
