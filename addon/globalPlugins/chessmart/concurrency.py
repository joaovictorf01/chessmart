# coding: utf-8
# pyright: basic

import threading
import typing as t
import asyncio
from functools import wraps
from concurrent.futures import Future, ThreadPoolExecutor
from logHandler import log


THREADED_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="chessmart")
ASYNCIO_EVENT_LOOP = asyncio.new_event_loop()
ASYNCIO_LOOP_THREAD = None


def start_asyncio_event_loop():
	global ASYNCIO_LOOP_THREAD, ASYNCIO_EVENT_LOOP
	if ASYNCIO_LOOP_THREAD:
		log.debug("Attempted to start the asyncio eventloop while it is already running")
		return

	def _thread_target():
		log.info("Starting asyncio event loop")
		asyncio.set_event_loop(ASYNCIO_EVENT_LOOP)
		ASYNCIO_EVENT_LOOP.run_forever()

	ASYNCIO_LOOP_THREAD = threading.Thread(
		target=_thread_target,
		daemon=True,
		name="chessmart.asyncio.thread",
	)
	ASYNCIO_LOOP_THREAD.start()


def terminate():
	global THREADED_EXECUTOR, ASYNCIO_LOOP_THREAD, ASYNCIO_EVENT_LOOP
	log.info("Shutting down the thread pool executor")
	THREADED_EXECUTOR.shutdown()
	if ASYNCIO_LOOP_THREAD:
		log.info("Shutting down asyncio event loop")
		ASYNCIO_EVENT_LOOP.call_soon_threadsafe(ASYNCIO_EVENT_LOOP.stop)


def asyncio_coroutine_to_concurrent_future(func):
	"""Returns a concurrent.futures.Future that wrapps the decorated async function."""

	@wraps(func)
	def wrapper(*args, **kwargs):
		return asyncio.run_coroutine_threadsafe(func(*args, **kwargs), ASYNCIO_EVENT_LOOP)

	return wrapper


def call_threaded(func: t.Callable[..., t.Any]) -> t.Callable[..., Future]:
	"""Roda `func` no pool de threads; a chamada devolve o `Future` do resultado.

	Depois de `terminate()` o pool recusa trabalho novo. Em vez de devolver None
	-- e estourar em quem faz `.add_done_callback` no retorno --, sai um Future
	já falho com a exceção, que segue o caminho normal de erro.
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
