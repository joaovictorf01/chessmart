# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The rules of one puzzle attempt and of the session's numbers.

Moved out of the puzzle board (architecture review, finding 15) so they can be
tested without NVDA: when an attempt counts, when the first mistake settles the
rating, what the session reports. The board keeps the speech and the timing.
"""

import dataclasses
import time

from .i18n import _


@dataclasses.dataclass
class AttemptState:
	"""Everything the current puzzle attempt needs to remember. Starts zeroed for each puzzle."""

	# When the player's turn started, i.e. after the automatic move.
	# None means the attempt hasn't started yet.
	started_at: float | None = None
	mistakes: int = 0
	hints_used: int = 0
	# Index in `solution_moves` of the next expected move (the player's or the opponent's).
	solution_index: int = 0
	# Already written to the database. Recording can happen partway through the
	# puzzle (on the first mistake) or at the end, but never twice.
	recorded: bool = False
	# Lichess rule: the first wrong move already settles the rating as a
	# loss. Finishing the puzzle after that is for learning and no longer
	# affects the number.
	settled_by_mistake: bool = False
	# Retry with Control+R: with the solution already known, it measures nothing.
	is_retry: bool = False
	# Already counted in the session numbers. Separate from `recorded` because
	# the session counts the puzzle once, at the end, and the database write may have happened earlier.
	counted_in_session: bool = False
	# Finished with Control+Enter: counts as solved in the database, but the
	# session reports how many were finished this way. A trainer that hides
	# this measures the will to finish, not the tactic.
	auto_solved: bool = False
	# A puzzle from the review queue: recorded as a review, never rated.
	is_review: bool = False

	@property
	def started(self) -> bool:
		return self.started_at is not None

	@property
	def touched(self) -> bool:
		"""The player did something in this puzzle: a move, a mistake, or a hint.

		This separates "gave up" from "never looked at it": a puzzle that was
		loaded and abandoned (immediate Control+N, accidental Escape) is not a
		loss, and doesn't go into the database or the session numbers. A hint
		counts as touched so it can't be used to peek at the solution for free.
		"""
		return self.solution_index > 0 or self.mistakes > 0 or self.hints_used > 0

	def elapsed_ms(self) -> int:
		if self.started_at is None:
			return 0
		return max(1, int((time.monotonic() - self.started_at) * 1000))

	def clean(self, solved: bool) -> bool:
		"""Solved with every move found alone: no wrong move, no hint, nothing revealed."""
		return solved and not self.mistakes and not self.hints_used and not self.auto_solved


@dataclasses.dataclass
class SessionStats:
	"""The session's numbers, in memory. Each puzzle is counted once, when it finishes."""

	attempts: int = 0
	solved: int = 0
	solved_after_mistake: int = 0
	mistakes: int = 0
	hints: int = 0
	revealed: int = 0
	reviews: int = 0
	reviews_clean: int = 0

	def count(self, attempt: AttemptState, solved: bool) -> None:
		if attempt.is_review:
			# Reviews have their own line: mixing them in would pad the session with puzzles already seen.
			self.reviews += 1
			if attempt.clean(solved):
				self.reviews_clean += 1
			return
		self.attempts += 1
		self.mistakes += attempt.mistakes
		self.hints += attempt.hints_used
		if solved and attempt.settled_by_mistake:
			self.solved_after_mistake += 1
		elif solved:
			self.solved += 1
			if attempt.auto_solved:
				self.revealed += 1

	def status_label(self) -> str:
		"""Label for the actions bar button. Memory only: read on every Tab."""
		if not self.attempts:
			# Translators: Button of the tactics actions bar, before any puzzle is finished.
			return _("Session status")
		# Translators: Button of the tactics actions bar, e.g. "Session status: 3 of 4 solved".
		return _("Session status: {solved} of {attempts} solved").format(
			solved=self.solved,
			attempts=self.attempts,
		)

	def summary(self) -> str:
		details = []
		if self.reviews:
			details.append(
				# Translators: Part of the session status: reviews of missed puzzles, e.g. "Reviews: 2 clean out of 3.".
				_("Reviews: {clean} clean out of {reviews}.").format(
					clean=self.reviews_clean,
					reviews=self.reviews,
				),
			)
		if not self.attempts:
			if details:
				return " ".join(details)
			# Translators: Session status before any puzzle is finished.
			return _("Session just started: no finished puzzle yet.")
		# Translators: Start of the session status, e.g. "Session: 3 solved out of 4.".
		summary = _("Session: {solved} solved out of {attempts}.").format(
			solved=self.solved,
			attempts=self.attempts,
		)
		if self.solved_after_mistake:
			details.append(
				# Translators: Part of the session status: puzzles finished after a first wrong move.
				_("Solved after a mistake, not rated: {count}.").format(count=self.solved_after_mistake),
			)
		if self.revealed:
			# Translators: Part of the session status: solved puzzles finished with Control+Enter.
			details.append(_("{count} of them revealed with Control+Enter.").format(count=self.revealed))
		if self.mistakes:
			# Translators: Part of the session status: wrong moves in the whole session.
			details.append(_("Mistakes in the session: {count}.").format(count=self.mistakes))
		if self.hints:
			# Translators: Part of the session status: hints asked in the whole session.
			details.append(_("Hints in the session: {count}.").format(count=self.hints))
		return " ".join([summary, *details])


def player_move_progress(solution_length: int, solution_index: int) -> tuple[int, int]:
	"""Which player move the puzzle is on, as (current, total).

	The solution alternates starting with the player: an even index is their
	move, odd is the opponent's reply. The move that sets up the position
	doesn't count -- it's played before anything else.
	"""
	total = (solution_length + 1) // 2
	played = (solution_index + 1) // 2
	return min(played + 1, total), total
