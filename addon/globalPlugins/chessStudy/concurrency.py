# coding: utf-8
# pyright: basic

import threading
import typing as t
from functools import wraps
from concurrent.futures import Future, ThreadPoolExecutor
from logHandler import log


THREADED_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="chessStudy")


def terminate():
	log.info("Shutting down the thread pool executor")
	THREADED_EXECUTOR.shutdown()


def call_threaded(func: t.Callable[..., t.Any]) -> t.Callable[..., Future]:
	"""Runs `func` in the thread pool; the call returns the result's `Future`.

	After `terminate()` the pool refuses new work. Instead of returning None --
	and blowing up whoever calls `.add_done_callback` on the result --, a Future
	that has already failed with the exception comes back, following the normal
	error path.
	"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return THREADED_EXECUTOR.submit(func, *args, **kwargs)
		except RuntimeError as error:
			log.debug("Failed to submit function %s: %s", func, error)
			failed: Future = Future()
			failed.set_exception(error)
			return failed

	return wrapper


class LatestWins:
	"""At most one job at a time; requests made meanwhile replace each other, and only the newest runs next.

	For work whose result is only worth having for the latest request, such as
	the picture of the board: ten arrow presses in a row start two renders, not
	ten, and `is_current` tells a finished job whether a newer one superseded it.
	Each job is a `(generation, item)` pair; `request` returns the job to start
	now, or None when one is already running.
	"""

	def __init__(self):
		self._lock = threading.Lock()
		self._running = False
		self._pending: "tuple[int, t.Any] | None" = None
		self._generation = 0

	def request(self, item: t.Any) -> "tuple[int, t.Any] | None":
		with self._lock:
			self._generation += 1
			job = (self._generation, item)
			if self._running:
				self._pending = job
				return None
			self._running = True
			return job

	def finished(self) -> "tuple[int, t.Any] | None":
		"""Called when the running job ends: the next job to start, if one was requested meanwhile."""
		with self._lock:
			job, self._pending = self._pending, None
			if job is None:
				self._running = False
			return job

	def is_current(self, generation: int) -> bool:
		with self._lock:
			return generation == self._generation
