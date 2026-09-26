# coding: utf-8
# pyright: basic

"""How much and how study happened: the daily summary and the lesson map.

Everything comes from the player's history (`tactic.db`): tactic attempts and
endgame attempts, with timestamps. Games are deliberately left out -- the real
game is on Lichess, not against the engine. Two views: by day (how many
tactics, how many correct, how many minutes; how many endgame positions, how
many held, minutes; total) and by lesson (which positions are firm, i.e. held
three times in a row, and where the player currently stands).

No NVDA here; the dialog only formats the text.
"""

from __future__ import annotations

import dataclasses
import datetime

from .endgame import log as endgame_log
from .endgame.drills import drill_label
from .endgame.lessons import ENDGAME_LESSONS, EndgameLesson, lesson_label, position_title
from .i18n import _
from .tactic.db import load_store
from .tactic.review import REVIEWS_PER_SESSION, ReviewQueue

FIRM_STREAK = 3


@dataclasses.dataclass(frozen=True)
class DaySummary:
	day: datetime.date
	tactics_attempts: int = 0
	tactics_solved: int = 0
	tactics_ms: int = 0
	endgame_attempts: int = 0
	endgame_held: int = 0
	endgame_ms: int = 0
	reviews: int = 0
	reviews_clean: int = 0
	reviews_ms: int = 0

	@property
	def total_minutes(self) -> int:
		return round((self.tactics_ms + self.endgame_ms + self.reviews_ms) / 60000)

	@property
	def empty(self) -> bool:
		return self.tactics_attempts == 0 and self.endgame_attempts == 0 and self.reviews == 0


@dataclasses.dataclass(frozen=True)
class LessonProgress:
	lesson: EndgameLesson
	firm: tuple[str, ...]  # firm position_ids
	pending: tuple[str, ...]  # position_ids not yet firm
	attempted: int

	@property
	def complete(self) -> bool:
		return not self.pending


def _has_table(connection, name: str) -> bool:
	row = connection.execute(
		"SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
		(name,),
	).fetchone()
	return row is not None


def daily_summaries(connection, days: int, today: datetime.date | None = None) -> list[DaySummary]:
	"""One summary per day, most recent first, only for days with something recorded.

	`created_at` is UTC (SQLite's CURRENT_TIMESTAMP); the day is converted to
	local time by SQLite itself, so a late-night session lands on the right day.
	"""
	today = today or datetime.date.today()
	since = (today - datetime.timedelta(days=days - 1)).isoformat()
	tactics: dict[str, tuple[int, int, int]] = {}
	if _has_table(connection, "attempts"):
		for row in connection.execute(
			"""
			SELECT date(created_at, 'localtime') AS day, COUNT(*) AS n, COALESCE(SUM(solved), 0) AS solved,
			       COALESCE(SUM(elapsed_ms), 0) AS ms
			FROM attempts WHERE date(created_at, 'localtime') >= ? GROUP BY day
			""",
			(since,),
		):
			tactics[row["day"]] = (int(row["n"]), int(row["solved"]), int(row["ms"]))
	reviews: dict[str, tuple[int, int, int]] = {}
	if _has_table(connection, "review_attempts"):
		for row in connection.execute(
			"""
			SELECT date(created_at, 'localtime') AS day, COUNT(*) AS n,
			       COALESCE(SUM(solved = 1 AND mistakes = 0 AND hints_used = 0 AND revealed = 0), 0) AS clean,
			       COALESCE(SUM(elapsed_ms), 0) AS ms
			FROM review_attempts WHERE date(created_at, 'localtime') >= ? GROUP BY day
			""",
			(since,),
		):
			reviews[row["day"]] = (int(row["n"]), int(row["clean"]), int(row["ms"]))
	endgames: dict[str, tuple[int, int, int]] = {}
	if _has_table(connection, "endgame_attempts"):
		for row in connection.execute(
			"""
			SELECT date(created_at, 'localtime') AS day, COUNT(*) AS n, COALESCE(SUM(kept_result), 0) AS held,
			       COALESCE(SUM(elapsed_ms), 0) AS ms
			FROM endgame_attempts WHERE date(created_at, 'localtime') >= ? GROUP BY day
			""",
			(since,),
		):
			endgames[row["day"]] = (int(row["n"]), int(row["held"]), int(row["ms"]))
	summaries = []
	for day in sorted(set(tactics) | set(endgames) | set(reviews), reverse=True):
		t = tactics.get(day, (0, 0, 0))
		e = endgames.get(day, (0, 0, 0))
		r = reviews.get(day, (0, 0, 0))
		summaries.append(
			DaySummary(
				day=datetime.date.fromisoformat(day),
				tactics_attempts=t[0],
				tactics_solved=t[1],
				tactics_ms=t[2],
				endgame_attempts=e[0],
				endgame_held=e[1],
				endgame_ms=e[2],
				reviews=r[0],
				reviews_clean=r[1],
				reviews_ms=r[2],
			),
		)
	return summaries


def review_queue(connection) -> ReviewQueue:
	"""The queue of missed puzzles, from the same history. Creates the tables an old history lacks."""
	store = load_store()
	store.prepare_history(connection)
	return store.review_queue(connection)


def lesson_progress(connection) -> list[LessonProgress]:
	"""Per lesson: firm positions (three in a row), pending ones, and how many were attempted."""
	result = []
	for lesson in ENDGAME_LESSONS:
		if lesson.drill is not None:
			stats = endgame_log.position_stats(connection, lesson.drill.drill_id)
			firm = (lesson.drill.drill_id,) if stats.streak >= FIRM_STREAK else ()
			pending = () if firm else (lesson.drill.drill_id,)
			result.append(LessonProgress(lesson, firm, pending, int(stats.attempts > 0)))
			continue
		firm, pending, attempted = [], [], 0
		for position in lesson.positions:
			stats = endgame_log.position_stats(connection, position.position_id)
			if stats.attempts:
				attempted += 1
			if stats.streak >= FIRM_STREAK:
				firm.append(position.position_id)
			else:
				pending.append(position.position_id)
		result.append(LessonProgress(lesson, tuple(firm), tuple(pending), attempted))
	return result


def current_lesson(progress: list[LessonProgress]) -> LessonProgress | None:
	"""The first lesson with something pending: where the player currently stands."""
	for item in progress:
		if not item.complete:
			return item
	return None


# ---------------------------------------------------------------- text


def _minutes(ms: int) -> int:
	return round(ms / 60000)


def render_days(summaries: list[DaySummary], days: int) -> list[str]:
	lines = []
	if not summaries:
		# Translators: Shown in the study log when nothing was recorded in the period.
		lines.append(_("Nothing recorded in the last {days} days.").format(days=days))
		return lines
	total_ms = 0
	for s in summaries:
		parts = []
		if s.tactics_attempts:
			# Translators: One day's tactics in the study log, e.g. "tactics: 3 puzzles, 2 solved, 25 min".
			parts.append(
				_("tactics: {n} puzzles, {solved} solved, {minutes} min").format(
					n=s.tactics_attempts,
					solved=s.tactics_solved,
					minutes=_minutes(s.tactics_ms),
				),
			)
		if s.reviews:
			# Translators: One day's reviews of missed puzzles in the study log, e.g. "reviews: 3, 2 clean, 6 min".
			parts.append(
				_("reviews: {n}, {clean} clean, {minutes} min").format(
					n=s.reviews,
					clean=s.reviews_clean,
					minutes=_minutes(s.reviews_ms),
				),
			)
		if s.endgame_attempts:
			# Translators: One day's endgame work in the study log, e.g. "endgames: 4 positions, 3 held, 18 min".
			parts.append(
				_("endgames: {n} positions, {held} held, {minutes} min").format(
					n=s.endgame_attempts,
					held=s.endgame_held,
					minutes=_minutes(s.endgame_ms),
				),
			)
		total_ms += s.tactics_ms + s.endgame_ms + s.reviews_ms
		# Translators: One day in the study log, e.g. "2026-09-19: tactics: ...; endgames: ... Total 43 min."
		lines.append(
			_("{day}: {parts}. Total {minutes} min.").format(
				day=s.day.isoformat(),
				parts="; ".join(parts),
				minutes=s.total_minutes,
			),
		)
	# Translators: Closing line of the study log, e.g. "6 days with study in the last 7, 210 min in all."
	lines.append(
		_("{active} days with study in the last {days}, {minutes} min in all.").format(
			active=len(summaries),
			days=days,
			minutes=_minutes(total_ms),
		),
	)
	return lines


def render_reviews(queue: ReviewQueue, today: datetime.date) -> list[str]:
	"""The review queue in two lines: where it stands, and what firm means."""
	if not queue.items and not queue.firm:
		# Translators: Shown in the study log when no puzzle was ever missed.
		return [_("No missed puzzles to review.")]
	return [
		# Translators: The review queue in the study log, e.g. "In the queue: 3 due today, 5 waiting for their day. Firm: 2.".
		_("In the queue: {due} due today, {waiting} waiting for their day. Firm: {firm}.").format(
			due=len(queue.due(today)),
			waiting=queue.waiting(today),
			firm=queue.firm,
		),
		# Translators: Explains the review queue in the study log.
		_(
			"A missed puzzle comes back the next day; two clean reviews in a row, days apart, make it firm. Up to {count} reviews open each tactics session.",
		).format(count=REVIEWS_PER_SESSION),
	]


def render_progress(progress: list[LessonProgress]) -> list[str]:
	lines = []
	titles = {
		position.position_id: position_title(position)
		for lesson in ENDGAME_LESSONS
		for position in lesson.positions
	}
	# A drill lesson's only item is the drill itself, logged under its drill id.
	titles.update(
		{
			lesson.drill.drill_id: drill_label(lesson.drill)
			for lesson in ENDGAME_LESSONS
			if lesson.drill is not None
		},
	)
	for item in progress:
		total = len(item.firm) + len(item.pending)
		label = lesson_label(item.lesson)
		if item.complete:
			# Translators: A lesson whose positions are all firm, e.g. "2. The king and the opposition: firm, 6 of 6."
			lines.append(
				_("{lesson}: firm, {firm} of {total}.").format(
					lesson=label,
					firm=len(item.firm),
					total=total,
				),
			)
		elif item.attempted == 0:
			# Translators: A lesson not started yet.
			lines.append(_("{lesson}: not started.").format(lesson=label))
		else:
			pending_titles = ", ".join(titles.get(pid, pid) for pid in item.pending)
			# Translators: A lesson in progress, e.g. "3. King and pawn: 4 of 7 firm. Pending: ...".
			lines.append(
				_("{lesson}: {firm} of {total} firm. Pending: {pending}.").format(
					lesson=label,
					firm=len(item.firm),
					total=total,
					pending=pending_titles,
				),
			)
	current = current_lesson(progress)
	if current is None:
		# Translators: Shown when every lesson is firm.
		lines.append(_("Every lesson is firm. Time for the next book."))
	else:
		# Translators: Where the player is in the endgame lessons, e.g. "You are at: 3. King and pawn against king."
		lines.append(_("You are at: {lesson}.").format(lesson=lesson_label(current.lesson)))
	# Translators: Explains what "firm" means in the study log.
	lines.append(
		_(
			"Firm means held {streak} times in a row, question answered right and result kept without a slip.",
		).format(streak=FIRM_STREAK),
	)
	return lines
