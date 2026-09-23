# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The picture of the board follows the latest key, not every key (architecture review, finding 9).

`LatestWins` is what keeps a burst of arrow presses from starting one
conversion process per key, and a late picture from covering a newer one.
"""

import unittest

from chessmart.concurrency import LatestWins


class LatestWinsTest(unittest.TestCase):
	def test_the_first_request_starts_at_once(self):
		queue = LatestWins()
		self.assertEqual(queue.request("a1"), (1, "a1"))

	def test_requests_while_running_collapse_into_the_newest(self):
		queue = LatestWins()
		queue.request("a1")
		for square in ("a2", "a3", "a4"):
			self.assertIsNone(queue.request(square))
		self.assertEqual(queue.finished(), (4, "a4"))
		self.assertIsNone(queue.finished())

	def test_a_finished_job_knows_it_was_superseded(self):
		queue = LatestWins()
		generation, _item = queue.request("a1")
		queue.request("a2")
		self.assertFalse(queue.is_current(generation))
		next_generation, _item = queue.finished()
		self.assertTrue(queue.is_current(next_generation))

	def test_after_the_last_job_the_next_request_starts_at_once_again(self):
		queue = LatestWins()
		queue.request("a1")
		self.assertIsNone(queue.finished())
		self.assertEqual(queue.request("b1"), (2, "b1"))


if __name__ == "__main__":
	unittest.main()
