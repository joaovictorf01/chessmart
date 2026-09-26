# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""What counts in a puzzle attempt and in the session (README, "Tactics training").

A puzzle that was never touched is not a loss; a hint counts as touching it;
a puzzle finished after a mistake is solved but not rated; one finished with
Control+Enter is reported apart.
"""

import unittest

from chessStudy.puzzle_attempt import AttemptState, SessionStats, player_move_progress


class AttemptTest(unittest.TestCase):
	def test_an_untouched_puzzle_is_not_touched(self):
		self.assertFalse(AttemptState().touched)

	def test_a_move_a_mistake_or_a_hint_touches_it(self):
		self.assertTrue(AttemptState(solution_index=1).touched)
		self.assertTrue(AttemptState(mistakes=1).touched)
		self.assertTrue(AttemptState(hints_used=1).touched)

	def test_elapsed_is_zero_before_the_player_turn(self):
		self.assertEqual(AttemptState().elapsed_ms(), 0)
		self.assertFalse(AttemptState().started)


class SessionTest(unittest.TestCase):
	def test_a_clean_solve_counts_as_solved(self):
		stats = SessionStats()
		stats.count(AttemptState(), solved=True)
		self.assertEqual((stats.attempts, stats.solved, stats.solved_after_mistake), (1, 1, 0))

	def test_solved_after_a_mistake_is_not_counted_as_solved(self):
		stats = SessionStats()
		stats.count(AttemptState(mistakes=1, settled_by_mistake=True), solved=True)
		self.assertEqual((stats.solved, stats.solved_after_mistake, stats.mistakes), (0, 1, 1))

	def test_revealed_puzzles_are_reported_apart(self):
		stats = SessionStats()
		stats.count(AttemptState(auto_solved=True), solved=True)
		self.assertEqual((stats.solved, stats.revealed), (1, 1))
		self.assertIn("Control+Enter", stats.summary())

	def test_summary_before_and_after_the_first_puzzle(self):
		stats = SessionStats()
		self.assertEqual(stats.status_label(), "Session status")
		stats.count(AttemptState(hints_used=2), solved=False)
		self.assertEqual(stats.status_label(), "Session status: 0 of 1 solved")
		self.assertIn("Hints in the session: 2.", stats.summary())


class ProgressTest(unittest.TestCase):
	def test_three_player_moves_in_a_five_move_solution(self):
		# Player, reply, player, reply, player.
		self.assertEqual(player_move_progress(5, 0), (1, 3))
		self.assertEqual(player_move_progress(5, 2), (2, 3))
		self.assertEqual(player_move_progress(5, 4), (3, 3))

	def test_progress_never_passes_the_total(self):
		self.assertEqual(player_move_progress(1, 1), (1, 1))


if __name__ == "__main__":
	unittest.main()
