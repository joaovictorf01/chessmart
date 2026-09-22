# coding: utf-8
# pyright: basic

import typing as t
from functools import wraps
from concurrent.futures import Future, ThreadPoolExecutor
from logHandler import log


THREADED_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="chessmart")


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
			log.debug(f"Failed to submit function {func}: {error}")
			failed: Future = Future()
			failed.set_exception(error)
			return failed

	return wrapper
